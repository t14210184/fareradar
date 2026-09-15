import type { D1Database } from "./types.js";

function currentTerms(v:string|null|undefined){return !!v&&v!=="RECHECK_REQUIRED"&&Number.isFinite(Date.parse(v));}
function parseCaps(raw:string|null|undefined){try{const x=JSON.parse(raw??"[]");return Array.isArray(x)?x.map(String):[];}catch{return [];}}
export async function recordProviderRuntimeReadback(db:D1Database,input:{provider_id:string;worker_id:string;connector_version:string;credentials_present:boolean;capabilities:string[];ttl_seconds?:number},nowIso:string){
  if(!input.provider_id||!input.worker_id||!input.connector_version)throw new Error("PROVIDER_READBACK_INVALID");
  const provider=await db.prepare("SELECT provider_id FROM provider_access_registry WHERE provider_id=?").bind(input.provider_id).first();if(!provider)throw new Error("PROVIDER_NOT_FOUND");
  const ttl=Math.min(900,Math.max(30,input.ttl_seconds??300)); const expires=new Date(Date.parse(nowIso)+ttl*1000).toISOString();
  await db.prepare("INSERT INTO provider_runtime_readbacks(provider_id,worker_id,connector_version,credentials_present,capabilities_json,checked_at,expires_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(provider_id,worker_id) DO UPDATE SET connector_version=excluded.connector_version,credentials_present=excluded.credentials_present,capabilities_json=excluded.capabilities_json,checked_at=excluded.checked_at,expires_at=excluded.expires_at")
    .bind(input.provider_id,input.worker_id,input.connector_version,input.credentials_present?1:0,JSON.stringify([...new Set(input.capabilities)].sort()),nowIso,expires).run();
  return {provider_id:input.provider_id,worker_id:input.worker_id,expires_at:expires};
}
export async function providerReady(db:D1Database,input:{provider_id:string;worker_id:string;verification_type:string;background?:boolean},nowIso:string){
  const p=await db.prepare("SELECT terms_snapshot_at,kill_switch_state,connector_state,supported_verification_json,background_allowed FROM provider_access_registry WHERE provider_id=?").bind(input.provider_id).first<any>();
  if(!p||p.kill_switch_state!=="CLEAR"||p.connector_state!=="IMPLEMENTED"||!currentTerms(p.terms_snapshot_at))return {ready:false,reason:"PROVIDER_ACCESS_NOT_READY"};
  if(input.background&&!p.background_allowed)return {ready:false,reason:"PROVIDER_BACKGROUND_NOT_ALLOWED"};
  const supported=parseCaps(p.supported_verification_json); if(!supported.includes(input.verification_type))return {ready:false,reason:"CAPABILITY_NOT_ALLOWED"};
  const r=await db.prepare("SELECT credentials_present,capabilities_json,expires_at FROM provider_runtime_readbacks WHERE provider_id=? AND worker_id=?").bind(input.provider_id,input.worker_id).first<any>();
  if(!r||!r.credentials_present||Date.parse(r.expires_at)<=Date.parse(nowIso))return {ready:false,reason:"RUNTIME_READBACK_MISSING"};
  const runtime=parseCaps(r.capabilities_json); if(!runtime.includes(input.verification_type))return {ready:false,reason:"RUNTIME_CAPABILITY_MISSING"};
  return {ready:true,reason:"READY"};
}
