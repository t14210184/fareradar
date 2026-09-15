import type { D1Database } from "./types.js";
import { providerReady } from "./provider_runtime.js";
import { completeVerificationJob } from "./scheduler.js";
import { projectProviderJobResults } from "./provider_results.js";

async function sha256Hex(text:string){const d=new TextEncoder().encode(text);const h=await crypto.subtle.digest("SHA-256",d);return [...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,"0")).join("");}
function stable(v:any):string{if(v===null||typeof v!=="object")return JSON.stringify(v);if(Array.isArray(v))return `[${v.map(stable).join(",")}]`;return `{${Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+stable(v[k])).join(",")}}`;}
function currentTerms(v:string|null|undefined){return !!v&&v!=="RECHECK_REQUIRED"&&Number.isFinite(Date.parse(v));}
export interface ExactFlightQuery { slices:{origin:string;destination:string;departure_date:string}[]; passengers:{type?:string;age?:number}[]; cabin_class?:"economy"|"premium_economy"|"business"|"first"; max_connections?:number; market?:string; locale?:string; baggage_query?:unknown; }
export function validateExactFlightQuery(q:ExactFlightQuery){
  if(!Array.isArray(q.slices)||q.slices.length<1||q.slices.length>4)throw new Error("QUERY_SLICES_INVALID");
  for(const s of q.slices){if(!/^[A-Z]{3}$/.test(s.origin)||!/^[A-Z]{3}$/.test(s.destination)||!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(s.departure_date)||!Number.isFinite(Date.parse(`${s.departure_date}T00:00:00Z`)))throw new Error("QUERY_SLICE_INVALID");}
  if(!Array.isArray(q.passengers)||q.passengers.length<1||q.passengers.length>9)throw new Error("QUERY_PASSENGERS_INVALID");
  for(const p of q.passengers){if((p.type?1:0)+(Number.isFinite(p.age)?1:0)!==1)throw new Error("QUERY_PASSENGER_IDENTITY_INVALID");}
  if(q.max_connections!==undefined&&(!Number.isInteger(q.max_connections)||q.max_connections<0||q.max_connections>3))throw new Error("QUERY_CONNECTIONS_INVALID");
  return true;
}
export async function enqueueProviderSearch(db:D1Database,input:{provider_id:string;mode:"BACKGROUND"|"USER_REQUEST";query:ExactFlightQuery},nowIso:string){
  validateExactFlightQuery(input.query);
  const p=await db.prepare("SELECT terms_snapshot_at,kill_switch_state,connector_state,supported_verification_json,background_allowed FROM provider_access_registry WHERE provider_id=?").bind(input.provider_id).first<any>();
  if(!p||p.kill_switch_state!=="CLEAR"||p.connector_state!=="IMPLEMENTED"||!currentTerms(p.terms_snapshot_at))throw new Error("PROVIDER_ACCESS_NOT_READY");
  let caps:string[]=[];try{caps=JSON.parse(p.supported_verification_json??"[]");}catch{} if(!caps.includes("LIVE_REPRICE"))throw new Error("PROVIDER_CAPABILITY_NOT_ALLOWED");
  if(input.mode==="BACKGROUND"&&!p.background_allowed)throw new Error("PROVIDER_BACKGROUND_NOT_ALLOWED");
  const fp=await sha256Hex(stable(input.query)); const jobId=`provider:${input.provider_id}:${fp}`;
  const payload={provider_id:input.provider_id,query_fingerprint:fp,mode:input.mode,query:input.query};
  await db.prepare("INSERT OR IGNORE INTO verification_jobs(job_id,job_type,target_class,source_id,payload_json,state,available_at,created_at,provider_id,query_fingerprint,provider_mode) VALUES(?,'LIVE_REPRICE','PROVIDER_API',NULL,?,'PENDING',?,?,?,?,?)")
    .bind(jobId,JSON.stringify(payload),nowIso,nowIso,input.provider_id,fp,input.mode).run();
  return {job_id:jobId,query_fingerprint:fp};
}
export async function leaseProviderJobs(db:D1Database,input:{provider_id:string;worker_id:string;limit?:number;verification_types?:string[]},nowIso:string){
  const requested=[...new Set(input.verification_types?.length?input.verification_types:["LIVE_REPRICE"])].filter(x=>["LIVE_REPRICE","CHECKOUT_REPRICE"].includes(x));
  if(!requested.length)throw new Error("PROVIDER_CAPABILITY_REQUEST_INVALID");
  const allowed:string[]=[];for(const verification_type of requested){const r=await providerReady(db,{provider_id:input.provider_id,worker_id:input.worker_id,verification_type},nowIso);if(r.ready)allowed.push(verification_type);}
  if(!allowed.length)throw new Error("PROVIDER_RUNTIME_NOT_READY");
  const policy=await db.prepare("SELECT background_allowed FROM provider_access_registry WHERE provider_id=?").bind(input.provider_id).first<any>();
  const backgroundAllowed=policy?.background_allowed?1:0;
  await db.prepare("UPDATE verification_jobs SET state='PENDING',claimed_by=NULL,lease_until=NULL WHERE target_class='PROVIDER_API' AND state='LEASED' AND lease_until IS NOT NULL AND lease_until<=?").bind(nowIso).run();
  const until=new Date(Date.parse(nowIso)+90_000).toISOString();const marks=allowed.map(()=>'?').join(',');
  return (await db.prepare(`UPDATE verification_jobs SET state='LEASED',claimed_by=?,lease_until=?,attempts=attempts+1
    WHERE job_id IN (SELECT job_id FROM verification_jobs WHERE target_class='PROVIDER_API' AND provider_id=? AND job_type IN (${marks}) AND state='PENDING' AND available_at<=? AND (provider_mode='USER_REQUEST' OR ?=1) ORDER BY created_at LIMIT ?)
    AND state='PENDING' RETURNING job_id,job_type,provider_id,query_fingerprint,provider_mode,payload_json,attempts,lease_until`)
    .bind(input.worker_id,until,input.provider_id,...allowed,nowIso,backgroundAllowed,Math.min(input.limit??5,5)).all()).results;
}
export async function completeProviderJob(db:D1Database,input:{job_id:string;provider_id:string;success:boolean;error?:string|null},nowIso:string){const state=await completeVerificationJob(db,{job_id:input.job_id,source_id:input.provider_id,success:input.success,error:input.error??null},nowIso); const projection=input.success&&state==="DONE"?await projectProviderJobResults(db,input.job_id,nowIso):{consumers:0,projected:0}; return {state,projection};}
