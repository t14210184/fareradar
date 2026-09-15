import type { CandidatePlanInput, D1Database } from "./types.js";
import { persistCandidatePlan } from "./intake.js";
import { enqueueAlertIntent, projectAlertIntents, leaseNotifications, ackNotification, claimDomainEvents, ackDomainEvent } from "./outbox.js";
import { scheduleDueSources, completeSourceFetch, leaseVerificationJobs } from "./scheduler.js";
import { ingestSourceObservation, projectDomainEvents } from "./ingest.js";

export interface Env { DB:D1Database; INGEST_HMAC_SECRET:string; }
const enc=new TextEncoder();
function hex(a:ArrayBuffer){return [...new Uint8Array(a)].map(x=>x.toString(16).padStart(2,"0")).join("");}
async function sign(secret:string,msg:string){const k=await crypto.subtle.importKey("raw",enc.encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);return hex(await crypto.subtle.sign("HMAC",k,enc.encode(msg)));}
function safeEq(a:string,b:string){if(a.length!==b.length)return false;let x=0;for(let i=0;i<a.length;i++)x|=a.charCodeAt(i)^b.charCodeAt(i);return x===0;}
async function authorized(req:Request,body:string,secret:string){const ts=req.headers.get("x-fare-timestamp")??"";const sig=req.headers.get("x-fare-signature")??"";const n=Number(ts);if(!Number.isFinite(n)||Math.abs(Date.now()-n)>300000)return false;return safeEq(sig,await sign(secret,`${ts}.${body}`));}
function json(data:unknown,status=200){return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json"}});}

const worker={
  async fetch(req:Request,env:Env):Promise<Response>{
    const u=new URL(req.url);
    if(req.method==="GET"&&u.pathname==="/health")return json({ok:true,spec:"1.3"});
    if(req.method==="POST"&&u.pathname==="/candidate-plan/intake"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body) as CandidatePlanInput;const r=await persistCandidatePlan(env.DB,payload);return json({ok:true,...r},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="IDEMPOTENCY_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/ingest"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestSourceObservation(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/candidate/evaluate"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body) as {intent_id:string;itinerary_id:string;alert_class:"DEAL"|"ADMIN";payload:unknown;actionable?:boolean;provisional_trigger?:boolean}; if(!p.actionable&&!p.provisional_trigger)return json({ok:true,queued:false},200); await enqueueAlertIntent(env.DB,p,new Date().toISOString()); return json({ok:true,queued:true},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/notifications/lease"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {worker_id:string;limit?:number}; return json({jobs:await leaseNotifications(env.DB,new Date().toISOString(),p.worker_id,Math.min(p.limit??10,10))});
    }
    if(req.method==="POST"&&u.pathname==="/notifications/ack"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body); return json({state:await ackNotification(env.DB,p,new Date().toISOString())});
    }
    if(req.method==="POST"&&u.pathname==="/domain/lease"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {worker_id:string;limit?:number}; return json({events:await claimDomainEvents(env.DB,new Date().toISOString(),p.worker_id,Math.min(p.limit??2,2))});
    }
    if(req.method==="POST"&&u.pathname==="/domain/ack"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401); return json({state:await ackDomainEvent(env.DB,JSON.parse(body),new Date().toISOString())});
    }
    if(req.method==="POST"&&u.pathname==="/verification-jobs/lease"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {worker_id:string;limit?:number}; return json({jobs:await leaseVerificationJobs(env.DB,new Date().toISOString(),p.worker_id,Math.min(p.limit??5,5))});
    }
    if(req.method==="POST"&&u.pathname==="/verification-jobs/complete"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {job_id:string;source_id:string;success:boolean;duplicate?:boolean;schema_drift?:boolean;etag?:string;last_modified?:string;content_sha256?:string}; const now=new Date().toISOString(); const health=await completeSourceFetch(env.DB,p,now); await env.DB.prepare("UPDATE verification_jobs SET state=?,claimed_by=NULL,lease_until=NULL,last_error=? WHERE job_id=?").bind(p.success?'DONE':'FAILED',p.success?null:'FETCH_FAILED',p.job_id).run(); return json({ok:true,health});
    }
    return json({error:"NOT_FOUND"},404);
  }
  ,async scheduled(_event:unknown,env:Env):Promise<void>{ const now=new Date().toISOString(); await projectAlertIntents(env.DB,now,10); await projectDomainEvents(env.DB,now,"cron",2); await scheduleDueSources(env.DB,now,10); }
};
export default worker;
