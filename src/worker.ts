import type { CandidatePlanInput, D1Database } from "./types.js";
import { persistCandidatePlan } from "./intake.js";
import { enqueueAlertIntent, projectAlertIntents, leaseNotifications, ackNotification, claimDomainEvents, ackDomainEvent } from "./outbox.js";
import { scheduleDueSources, completeSourceFetch, leaseVerificationJobs, completeVerificationJob } from "./scheduler.js";
import { ingestSourceObservation, projectDomainEvents } from "./ingest.js";
import { ingestAgencyOffer, ingestEmailEvidence } from "./partner_ingest.js";
import { ingestOfferSnapshot } from "./offers.js";
import { recordAuditEvidence, recordSourceDiscoveryEdge } from "./audit.js";
import { leaseCandidateSignals, ackCandidateSignal } from "./priority.js";
import { applySourceOnboardingReview, disableSource } from "./source_onboarding.js";
import { recordProviderRuntimeReadback, providerReady } from "./provider_runtime.js";
import { enqueueProviderSearch, leaseProviderJobs, completeProviderJob } from "./provider_jobs.js";
import { upsertSearchCampaign, planSearchesForQueue, planDueCandidateSearches, dispatchProviderSearchPlans } from "./search_planner.js";

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
    if(req.method==="POST"&&u.pathname==="/audit/evidence"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await recordAuditEvidence(env.DB,JSON.parse(body))},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==='AUDIT_EVIDENCE_CONFLICT'?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/source-discovery/edge"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json(await recordSourceDiscoveryEdge(env.DB,JSON.parse(body)),202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/offers/ingest"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestOfferSnapshot(env.DB,JSON.parse(body))},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==='OFFER_ID_CONFLICT'?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/candidate-plan/intake"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body) as CandidatePlanInput;const r=await persistCandidatePlan(env.DB,payload);return json({ok:true,...r},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="IDEMPOTENCY_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/ingest/agency"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestAgencyOffer(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/ingest/email"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestEmailEvidence(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
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
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {job_id:string;source_id:string;success:boolean;duplicate?:boolean;schema_drift?:boolean;etag?:string;last_modified?:string;content_sha256?:string;error?:string}; const now=new Date().toISOString(); const health=await completeSourceFetch(env.DB,p,now); const state=await completeVerificationJob(env.DB,p,now); return json({ok:true,health,state});
    }
    if(req.method==="POST"&&u.pathname==="/candidate-priority/lease"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {provider_id:string;worker_id:string;verification_type:"LIVE_REPRICE"|"SELLER_RECHECK";limit?:number}; const now=new Date().toISOString(); const ready=await providerReady(env.DB,{...p,background:true},now); if(!ready.ready)return json({error:ready.reason},409); return json({signals:await leaseCandidateSignals(env.DB,now,p.worker_id,Math.min(p.limit??5,5),90,p.verification_type)});
    }
    if(req.method==="POST"&&u.pathname==="/candidate-priority/ack"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401); return json({state:await ackCandidateSignal(env.DB,JSON.parse(body),new Date().toISOString())});
    }
    if(req.method==="POST"&&u.pathname==="/sources/onboarding/review"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await applySourceOnboardingReview(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m.includes("IDEMPOTENCY_CONFLICT")?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/sources/disable"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await disableSource(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/providers/runtime/readback"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await recordProviderRuntimeReadback(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/provider-search/enqueue"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await enqueueProviderSearch(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/provider-jobs/lease"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({jobs:await leaseProviderJobs(env.DB,JSON.parse(body),new Date().toISOString())});}catch(e){return json({error:e instanceof Error?e.message:String(e)},409);}
    }
    if(req.method==="POST"&&u.pathname==="/provider-jobs/complete"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({state:await completeProviderJob(env.DB,JSON.parse(body),new Date().toISOString())});}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/search-campaigns/upsert"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await upsertSearchCampaign(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/search-planner/plan"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body);return json({ok:true,...await planSearchesForQueue(env.DB,p.campaign_id,p.queue_id,new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/search-planner/dispatch"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body);return json({ok:true,...await dispatchProviderSearchPlans(env.DB,new Date().toISOString(),Math.min(p.limit??2,2))},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    return json({error:"NOT_FOUND"},404);
  }
  ,async scheduled(event:any,env:Env):Promise<void>{ const now=new Date().toISOString(); if(event?.cron==="*/5 * * * *"){await planDueCandidateSearches(env.DB,now,8,4);await dispatchProviderSearchPlans(env.DB,now,2);return;} await projectAlertIntents(env.DB,now,10); await projectDomainEvents(env.DB,now,"cron",2); await scheduleDueSources(env.DB,now,10); }
};
export default worker;
