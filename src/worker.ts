import type { CandidatePlanInput, D1Database } from "./types.js";
import { persistCandidatePlan } from "./intake.js";
import { enqueueAlertIntent, projectAlertIntents, leaseNotifications, ackNotification, claimDomainEvents, ackDomainEvent } from "./outbox.js";
import { scheduleDueSources, completeSourceFetch, leaseVerificationJobs, completeVerificationJob } from "./scheduler.js";
import { ingestSourceObservation, projectDomainEvents } from "./ingest.js";
import { ingestAgencyOffer, ingestEmailEvidence } from "./partner_ingest.js";
import { leaseAgencyRechecks, completeAgencyRecheck } from "./agency_recheck.js";
import { leaseAgencyCheckouts, completeAgencyCheckout } from "./agency_checkout.js";
import { expireAgencyOffers } from "./agency_expiry.js";
import { expireLiveProviderOffers } from "./offer_lifecycle.js";
import { ingestOfferSnapshot } from "./offers.js";
import { recordAuditEvidence, recordSourceDiscoveryEdge } from "./audit.js";
import { leaseCandidateSignals, ackCandidateSignal } from "./priority.js";
import { applySourceOnboardingReview, disableSource } from "./source_onboarding.js";
import { recordProviderRuntimeReadback, providerReady } from "./provider_runtime.js";
import { enqueueProviderSearch, leaseProviderJobs, completeProviderJob } from "./provider_jobs.js";
import { upsertSearchCampaign, planSearchesForQueue, planDueCandidateSearches, dispatchProviderSearchPlans } from "./search_planner.js";
import { ingestPolicyRecord, enrichItineraryPolicy } from "./policy_registry.js";
import { upsertRuntimeProfile, upsertRuntimeEntitlement } from "./profile.js";
import { upsertPaymentProfile, enqueueCheckoutReprice, ingestPricingQuote } from "./checkout_pricing.js";
import { ingestFxSnapshot, ingestCostEvidenceSnapshot, upsertMandatoryCostEvidence, upsertCostCoverageAssertion, attachFxToCost, recomputeDirectAllInCost } from "./cost_runtime.js";
import { upsertFourLegCycle, transitionFourLegCycle, fourLegLiabilitySummary } from "./four_leg.js";
import { ingestCarrierTicketingPolicy, evaluateTicketingGuards } from "./ticketing_guard.js";
import { ingestConnectionBufferPolicy, ingestAirportChangePolicy, evaluateTransferBoundary } from "./transfer_runtime.js";
import { evaluateActionableFromDb } from "./readiness_runtime.js";
import { evaluateDueProvisionals } from "./provisional.js";
import { evaluateDuePromotionBursts } from "./social_heat.js";
import { ingestProviderPricingSnapshot, recordProviderConfirmedOrder } from "./provider_pricing.js";
import { buildCanonicalCandidateAlert } from "./alert_runtime.js";
import { authorizeRequest, principalAllowsPayload, cleanupExpiredNonces, workerTokenAuthorized, workerLeaseAllowsSource, providerLeaseAllowsJob, type AuthEnv } from "./auth.js";

export interface Env extends AuthEnv { WORKER_TOKEN?:string; }
async function authorized(req:Request,body:string,env:Env){return authorizeRequest(req,body,env);}
function json(data:unknown,status=200){return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json"}});}

const worker={
  async fetch(req:Request,env:Env):Promise<Response>{
    const u=new URL(req.url);
    if(req.method==="GET"&&u.pathname==="/health")return json({ok:true,spec:"1.3"});
    if(req.method==="POST"&&u.pathname==="/audit/evidence"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await recordAuditEvidence(env.DB,JSON.parse(body))},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==='AUDIT_EVIDENCE_CONFLICT'?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/source-discovery/edge"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json(await recordSourceDiscoveryEdge(env.DB,JSON.parse(body)),202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/profiles/upsert"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await upsertRuntimeProfile(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/profiles/entitlements/upsert"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await upsertRuntimeEntitlement(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/policies/ingest"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestPolicyRecord(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="POLICY_RECORD_IMMUTABLE_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/itineraries/policy-enrich"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await enrichItineraryPolicy(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/offers/ingest"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);if(principal.provider_id&&(!payload.worker_id||!payload.source_snapshot_id||!await providerLeaseAllowsJob(env.DB,{job_id:payload.source_snapshot_id,worker_id:payload.worker_id,provider_id:principal.provider_id,job_type:"LIVE_REPRICE"},new Date().toISOString())))return json({error:"LIVE_PROVIDER_LEASE_REQUIRED"},403);return json({ok:true,...await ingestOfferSnapshot(env.DB,payload)},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==='OFFER_ID_CONFLICT'?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/candidate-plan/intake"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body) as CandidatePlanInput;const r=await persistCandidatePlan(env.DB,payload);return json({ok:true,...r},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="IDEMPOTENCY_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/ingest/agency"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);return json({ok:true,...await ingestAgencyOffer(env.DB,payload,new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/ingest/email"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);return json({ok:true,...await ingestEmailEvidence(env.DB,payload,new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/ingest"){
      const body=await req.text(); if(!workerTokenAuthorized(req,env.WORKER_TOKEN))return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body) as {worker_id:string;lease_job_id:string;source_id:string};const now=new Date().toISOString();if(!payload.worker_id||!payload.lease_job_id||!payload.source_id||!await workerLeaseAllowsSource(env.DB,{job_id:payload.lease_job_id,worker_id:payload.worker_id,source_id:payload.source_id},now))return json({error:"LIVE_SOURCE_LEASE_REQUIRED"},403);return json({ok:true,...await ingestSourceObservation(env.DB,payload as any,now)},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/candidate/evaluate"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{
        const p=JSON.parse(body) as {itinerary_id:string;provisional_trigger?:boolean;actionable?:boolean;payload?:unknown;intent_id?:string;alert_class?:"DEAL"|"ADMIN"};
        if(Object.prototype.hasOwnProperty.call(p,"actionable"))throw new Error("CLIENT_ACTIONABLE_FORBIDDEN");
        if(Object.prototype.hasOwnProperty.call(p,"provisional_trigger"))throw new Error("CLIENT_PROVISIONAL_TRIGGER_FORBIDDEN");
        if(Object.prototype.hasOwnProperty.call(p,"payload")||Object.prototype.hasOwnProperty.call(p,"intent_id"))throw new Error("CLIENT_ALERT_CONTENT_FORBIDDEN");
        if((p.alert_class??"DEAL")!=="DEAL")throw new Error("CANDIDATE_ALERT_CLASS_INVALID");
        const now=new Date().toISOString(); const readiness=await evaluateActionableFromDb(env.DB,p.itinerary_id,now);
        if(!readiness.actionable)return json({ok:true,queued:false,...readiness},200);
        const payload=await buildCanonicalCandidateAlert(env.DB,p.itinerary_id,now,false);
        const intentId=`deal:${p.itinerary_id}:${payload.updated_at}`;
        await enqueueAlertIntent(env.DB,{intent_id:intentId,itinerary_id:p.itinerary_id,alert_class:"DEAL",payload},now);
        return json({ok:true,queued:true,provisional:false,intent_id:intentId,...readiness},202);
      }catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/notifications/lease"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {worker_id:string;limit?:number}; return json({jobs:await leaseNotifications(env.DB,new Date().toISOString(),p.worker_id,Math.min(p.limit??10,10))});
    }
    if(req.method==="POST"&&u.pathname==="/notifications/ack"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body); if(!p.worker_id)return json({error:"WORKER_ID_REQUIRED"},400); try{return json({state:await ackNotification(env.DB,p,new Date().toISOString())});}catch(e){return json({error:e instanceof Error?e.message:String(e)},409);}
    }
    if(req.method==="POST"&&u.pathname==="/domain/lease"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {worker_id:string;limit?:number}; return json({events:await claimDomainEvents(env.DB,new Date().toISOString(),p.worker_id,Math.min(p.limit??2,2))});
    }
    if(req.method==="POST"&&u.pathname==="/domain/ack"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body); if(!p.worker_id)return json({error:"WORKER_ID_REQUIRED"},400); try{return json({state:await ackDomainEvent(env.DB,p,new Date().toISOString())});}catch(e){return json({error:e instanceof Error?e.message:String(e)},409);}
    }
    if(req.method==="POST"&&u.pathname==="/verification-jobs/lease"){
      const body=await req.text(); if(!workerTokenAuthorized(req,env.WORKER_TOKEN))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {worker_id:string;limit?:number}; if(!p.worker_id)return json({error:"WORKER_ID_REQUIRED"},400); return json({jobs:await leaseVerificationJobs(env.DB,new Date().toISOString(),p.worker_id,Math.min(p.limit??5,5))});
    }
    if(req.method==="POST"&&u.pathname==="/verification-jobs/complete"){
      const body=await req.text(); if(!workerTokenAuthorized(req,env.WORKER_TOKEN))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {job_id:string;worker_id:string;source_id:string;success:boolean;duplicate?:boolean;schema_drift?:boolean;etag?:string;last_modified?:string;content_sha256?:string;error?:string}; const now=new Date().toISOString(); if(!p.worker_id||!await workerLeaseAllowsSource(env.DB,{job_id:p.job_id,worker_id:p.worker_id,source_id:p.source_id},now))return json({error:"LIVE_SOURCE_LEASE_REQUIRED"},403); const health=await completeSourceFetch(env.DB,p,now); const state=await completeVerificationJob(env.DB,p,now); return json({ok:true,health,state});
    }
    if(req.method==="POST"&&u.pathname==="/agency-rechecks/lease"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);return json({signals:await leaseAgencyRechecks(env.DB,payload,new Date().toISOString())});}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/agency-rechecks/complete"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);return json({ok:true,...await completeAgencyRecheck(env.DB,payload,new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="AGENCY_RECHECK_IMMUTABLE_CONFLICT"?409:m.includes("LIVE_LEASE")?403:400);}
    }
    if(req.method==="POST"&&u.pathname==="/agency-checkouts/lease"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);return json({jobs:await leaseAgencyCheckouts(env.DB,payload,new Date().toISOString())});}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/agency-checkouts/complete"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);return json({ok:true,...await completeAgencyCheckout(env.DB,payload,new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="AGENCY_CHECKOUT_IMMUTABLE_CONFLICT"?409:m.includes("LIVE_LEASE")?403:400);}
    }
    if(req.method==="POST"&&u.pathname==="/candidate-priority/lease"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body) as {provider_id:string;worker_id:string;verification_type:"LIVE_REPRICE"|"SELLER_RECHECK";limit?:number}; const now=new Date().toISOString(); const ready=await providerReady(env.DB,{...p,background:true},now); if(!ready.ready)return json({error:ready.reason},409); return json({signals:await leaseCandidateSignals(env.DB,now,p.worker_id,Math.min(p.limit??5,5),90,p.verification_type)});
    }
    if(req.method==="POST"&&u.pathname==="/candidate-priority/ack"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401); const p=JSON.parse(body); if(!p.worker_id)return json({error:"WORKER_ID_REQUIRED"},400); try{return json({state:await ackCandidateSignal(env.DB,p,new Date().toISOString())});}catch(e){return json({error:e instanceof Error?e.message:String(e)},409);}
    }
    if(req.method==="POST"&&u.pathname==="/sources/onboarding/review"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await applySourceOnboardingReview(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m.includes("IDEMPOTENCY_CONFLICT")?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/sources/disable"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await disableSource(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/providers/runtime/readback"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);return json({ok:true,...await recordProviderRuntimeReadback(env.DB,payload,new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/provider-pricing/ingest"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestProviderPricingSnapshot(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="PROVIDER_PRICING_IMMUTABLE_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/provider-pricing/order-confirmed"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body);return json({ok:true,...await recordProviderConfirmedOrder(env.DB,p.provider_id,new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/provider-search/enqueue"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await enqueueProviderSearch(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/payment-profiles/upsert"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await upsertPaymentProfile(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/checkout-reprice/enqueue"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await enqueueCheckoutReprice(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/pricing-quotes/ingest"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);if(principal.provider_id&&(!payload.worker_id||!payload.source_job_id||!await providerLeaseAllowsJob(env.DB,{job_id:payload.source_job_id,worker_id:payload.worker_id,provider_id:principal.provider_id,job_type:"CHECKOUT_REPRICE"},new Date().toISOString())))return json({error:"LIVE_PROVIDER_LEASE_REQUIRED"},403);return json({ok:true,...await ingestPricingQuote(env.DB,payload)},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="PRICING_QUOTE_ID_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/fx-snapshots/ingest"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestFxSnapshot(env.DB,JSON.parse(body))},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="FX_SNAPSHOT_ID_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/cost-evidence-snapshots/ingest"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestCostEvidenceSnapshot(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="COST_EVIDENCE_ID_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/cost-evidence/upsert"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await upsertMandatoryCostEvidence(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/cost-coverage/upsert"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await upsertCostCoverageAssertion(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/cost/fx-attach"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await attachFxToCost(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/cost/recompute-direct"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body);return json({ok:true,...await recomputeDirectAllInCost(env.DB,p.itinerary_id,new Date().toISOString())},200);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/four-leg/cycles/upsert"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await upsertFourLegCycle(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/four-leg/cycles/transition"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await transitionFourLegCycle(env.DB,JSON.parse(body),new Date().toISOString())},200);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/four-leg/cycles/summary"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body);return json({ok:true,...await fourLegLiabilitySummary(env.DB,p.cycle_id)},200);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/ticketing-policies/ingest"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestCarrierTicketingPolicy(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="TICKETING_POLICY_IMMUTABLE_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/ticketing/evaluate"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body);return json({ok:true,...await evaluateTicketingGuards(env.DB,p.itinerary_id,new Date().toISOString())},200);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/connection-buffer-policies/ingest"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestConnectionBufferPolicy(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="BUFFER_POLICY_IMMUTABLE_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/airport-change-policies/ingest"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await ingestAirportChangePolicy(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="AIRPORT_CHANGE_POLICY_IMMUTABLE_CONFLICT"?409:400);}
    }
    if(req.method==="POST"&&u.pathname==="/transfers/evaluate"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body);return json({ok:true,...await evaluateTransferBoundary(env.DB,p.boundary_id,new Date().toISOString())},200);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/provider-jobs/lease"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);return json({jobs:await leaseProviderJobs(env.DB,payload,new Date().toISOString())});}catch(e){return json({error:e instanceof Error?e.message:String(e)},409);}
    }
    if(req.method==="POST"&&u.pathname==="/provider-jobs/complete"){
      const body=await req.text(); const principal=await authorized(req,body,env); if(!principal)return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body);if(!principalAllowsPayload(principal,payload,u.pathname))return json({error:"AUTH_SCOPE_MISMATCH"},403);return json(await completeProviderJob(env.DB,payload,new Date().toISOString()));}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/search-campaigns/upsert"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{return json({ok:true,...await upsertSearchCampaign(env.DB,JSON.parse(body),new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/search-planner/plan"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body);return json({ok:true,...await planSearchesForQueue(env.DB,p.campaign_id,p.queue_id,new Date().toISOString())},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    if(req.method==="POST"&&u.pathname==="/search-planner/dispatch"){
      const body=await req.text(); if(!await authorized(req,body,env))return json({error:"UNAUTHORIZED"},401);
      try{const p=JSON.parse(body);return json({ok:true,...await dispatchProviderSearchPlans(env.DB,new Date().toISOString(),Math.min(p.limit??2,2))},202);}catch(e){return json({error:e instanceof Error?e.message:String(e)},400);}
    }
    return json({error:"NOT_FOUND"},404);
  }
  ,async scheduled(event:any,env:Env):Promise<void>{ const now=new Date().toISOString(); await cleanupExpiredNonces(env.DB,now); if(event?.cron==="*/5 * * * *"){const agencyExpiry=await expireAgencyOffers(env.DB,now,1);if(agencyExpiry.expired)return;const liveExpiry=await expireLiveProviderOffers(env.DB,now,1);if(liveExpiry.processed||liveExpiry.resumed)return;await planDueCandidateSearches(env.DB,now,8,4);await dispatchProviderSearchPlans(env.DB,now,2);await evaluateDueProvisionals(env.DB,now,1);await evaluateDuePromotionBursts(env.DB,now,1);return;} await projectAlertIntents(env.DB,now,10); await projectDomainEvents(env.DB,now,"cron",2); await scheduleDueSources(env.DB,now,10); }
};
export default worker;
