import type { D1Database } from "./types.js";
import { verifyMultiProvider } from "./verification.js";
import { ackCandidateSignal } from "./priority.js";
import { markDirectCandidateFareStale, projectDirectVerifiedCandidate } from "./direct_candidate.js";

function safe(v:string){return v.replace(/[^A-Za-z0-9._:-]/g,"_");}
function parseJson<T>(raw:string|null|undefined,fallback:T):T{try{return raw?JSON.parse(raw) as T:fallback;}catch{return fallback;}}
function flightToken(v:unknown){return String(v??"").toUpperCase().replace(/[^A-Z0-9]/g,"");}
function textToken(v:unknown){return String(v??"").trim().toUpperCase();}
function freshOffer(o:any,nowIso:string){return !o.expires_at||Date.parse(o.expires_at)>Date.parse(nowIso);}
function offerMatchesEligibleFlights(structure:any,eligibleRaw:unknown):boolean{
  const eligible=Array.isArray(eligibleRaw)?eligibleRaw.map(flightToken).filter(Boolean):[];
  if(!eligible.length)return true;
  const allow=new Set(eligible);
  if(!structure||!Array.isArray(structure.slices)||!structure.slices.length)return false;
  let count=0;
  for(const slice of structure.slices){
    if(!Array.isArray(slice?.segments)||!slice.segments.length)return false;
    for(const segment of slice.segments){
      const number=flightToken(segment?.flight_number);
      if(!number)return false;
      const marketing=flightToken(segment?.marketing_carrier);
      const candidates=[number,marketing?`${marketing}${number}`:""];
      if(!candidates.some(x=>x&&allow.has(x)))return false;
      count++;
    }
  }
  return count>0;
}
type PromotionConstraintDecision={status:"PASS"|"MISMATCH"|"UNVERIFIED";reason:string};
function evaluatePromotionOfferConstraints(offer:any,constraint:any):PromotionConstraintDecision{
  const structure=parseJson<any>(offer?.offer_structure_json,null);
  if(Array.isArray(constraint?.eligible_flight_numbers)&&constraint.eligible_flight_numbers.length&&!offerMatchesEligibleFlights(structure,constraint.eligible_flight_numbers))return {status:"MISMATCH",reason:"PROMOTION_FLIGHT_NUMBER_MISMATCH"};
  if(constraint?.sales_currency&&textToken(offer?.currency)!==textToken(constraint.sales_currency))return {status:"MISMATCH",reason:"PROMOTION_SALES_CURRENCY_MISMATCH"};
  const promoEvidence=structure?.promotion_evidence??{};
  if(constraint?.coupon_required&&promoEvidence?.coupon_applied!==true)return {status:"UNVERIFIED",reason:"PROMOTION_COUPON_UNVERIFIED"};
  if(constraint?.fare_brand){
    const observed=structure?.fare_brand??promoEvidence?.fare_brand;
    if(!observed)return {status:"UNVERIFIED",reason:"PROMOTION_FARE_BRAND_UNVERIFIED"};
    if(textToken(observed)!==textToken(constraint.fare_brand))return {status:"MISMATCH",reason:"PROMOTION_FARE_BRAND_MISMATCH"};
  }
  if(constraint?.baggage_bundle){
    const observed=structure?.baggage_bundle??promoEvidence?.baggage_bundle;
    if(!observed)return {status:"UNVERIFIED",reason:"PROMOTION_BAGGAGE_BUNDLE_UNVERIFIED"};
    if(textToken(observed)!==textToken(constraint.baggage_bundle))return {status:"MISMATCH",reason:"PROMOTION_BAGGAGE_BUNDLE_MISMATCH"};
  }
  return {status:"PASS",reason:"PROMOTION_CONSTRAINTS_SATISFIED"};
}
async function promotionConstraintForQueue(db:D1Database,queueId:string):Promise<any|null>{
  const q=await db.prepare("SELECT signal_type,signal_id FROM candidate_priority_queue WHERE queue_id=?").bind(queueId).first<any>();
  if(!q||q.signal_type!=="PROMOTION")return null;
  const p=await db.prepare("SELECT constraint_json FROM promotion_events WHERE event_id=?").bind(q.signal_id).first<any>();
  return parseJson<any>(p?.constraint_json,{});
}

async function writeVerificationSupports(db:D1Database,resultId:string,supportIds:string[],bestOfferId:string|null,nowIso:string){
  const stmts=[db.prepare("DELETE FROM candidate_verification_supports WHERE result_id=?").bind(resultId)];
  for(const id of [...new Set(supportIds)])stmts.push(db.prepare("INSERT INTO candidate_verification_supports(result_id,provider_offer_id,support_role,created_at) VALUES(?,?,?,?)").bind(resultId,id,id===bestOfferId?"PRIMARY":"SUPPORT",nowIso));
  await db.batch(stmts);
}

export async function recomputeCandidateVerification(db:D1Database,queueId:string,queryFingerprint:string,nowIso:string){
  const linkedRaw=(await db.prepare(`SELECT o.provider_offer_id,o.query_fingerprint,o.provider,o.offer_total,o.currency,o.observed_at,o.expires_at,o.offer_structure_json
      FROM candidate_offer_links l JOIN offer_snapshots o ON o.provider_offer_id=l.provider_offer_id
      WHERE l.queue_id=? AND l.query_fingerprint=? AND o.cached_or_live='LIVE'`).bind(queueId,queryFingerprint).all<any>()).results;
  const resultId=`verify:${safe(queueId)}:${queryFingerprint}`;
  if(!linkedRaw.length){
    await db.prepare(`INSERT INTO candidate_verification_results(result_id,queue_id,query_fingerprint,verification_state,reason,best_offer_id,best_offer_total,currency,live_offer_count,provider_count,updated_at)
      VALUES(?,?,?,'PROBABLE','NO_LIVE_CONFIRMATION',NULL,NULL,NULL,0,0,?) ON CONFLICT(queue_id,query_fingerprint) DO UPDATE SET verification_state='PROBABLE',reason='NO_LIVE_CONFIRMATION',best_offer_id=NULL,best_offer_total=NULL,currency=NULL,live_offer_count=0,provider_count=0,updated_at=excluded.updated_at`)
      .bind(resultId,queueId,queryFingerprint,nowIso).run();
    await writeVerificationSupports(db,resultId,[],null,nowIso);
    const stale=await markDirectCandidateFareStale(db,{queue_id:queueId,query_fingerprint:queryFingerprint,reason:"NO_LIVE_CONFIRMATION",evidence_id:`verification:${resultId}`},nowIso);
    return {verification_state:"PROBABLE" as const,reason:"NO_LIVE_CONFIRMATION",best_offer_id:null,live_offer_count:0,provider_count:0,supporting_offer_ids:[] as string[],projection:stale};
  }
  const promoConstraint=await promotionConstraintForQueue(db,queueId);
  const decisions=promoConstraint?linkedRaw.map(o=>({offer:o,decision:evaluatePromotionOfferConstraints(o,promoConstraint)})):linkedRaw.map(o=>({offer:o,decision:{status:"PASS" as const,reason:"NOT_PROMOTION"}}));
  const eligible=decisions.filter(x=>x.decision.status==="PASS").map(x=>x.offer);
  if(!eligible.length){
    const unverified=decisions.find(x=>x.decision.status==="UNVERIFIED");
    const reason=unverified?"PROMOTION_CONSTRAINT_UNVERIFIED":"PROMOTION_CONSTRAINT_MISMATCH";
    await db.prepare(`INSERT INTO candidate_verification_results(result_id,queue_id,query_fingerprint,verification_state,reason,best_offer_id,best_offer_total,currency,live_offer_count,provider_count,updated_at)
      VALUES(?,?,?,?,?,NULL,NULL,NULL,0,0,?) ON CONFLICT(queue_id,query_fingerprint) DO UPDATE SET verification_state=excluded.verification_state,reason=excluded.reason,best_offer_id=NULL,best_offer_total=NULL,currency=NULL,live_offer_count=0,provider_count=0,updated_at=excluded.updated_at`)
      .bind(resultId,queueId,queryFingerprint,"PROBABLE",reason,nowIso).run();
    await writeVerificationSupports(db,resultId,[],null,nowIso);
    const stale=await markDirectCandidateFareStale(db,{queue_id:queueId,query_fingerprint:queryFingerprint,reason,evidence_id:`verification:${resultId}`},nowIso);
    return {verification_state:"PROBABLE" as const,reason,best_offer_id:null,live_offer_count:0,provider_count:0,supporting_offer_ids:[] as string[],projection:stale};
  }
  const verdict=verifyMultiProvider(eligible.map(o=>({evidence_id:o.provider_offer_id,provider:o.provider,kind:"LIVE_OFFER" as const,price:Number(o.offer_total),query_fingerprint:o.query_fingerprint,observed_at:o.observed_at,expires_at:o.expires_at,coverage_allowed:true})),nowIso);
  const fresh=eligible.filter(o=>freshOffer(o,nowIso));
  const supportSet=new Set(verdict.supporting_evidence_ids??[]);
  const bestPool=verdict.state==="CONFIRMED"&&supportSet.size?fresh.filter(o=>supportSet.has(o.provider_offer_id)):fresh;
  const best=bestPool.length?[...bestPool].sort((a,b)=>Number(a.offer_total)-Number(b.offer_total)||String(a.provider_offer_id).localeCompare(String(b.provider_offer_id)))[0]:null;
  const providers=new Set(fresh.map(o=>o.provider));
  const verificationState:"PROBABLE"|"CONFIRMED"=verdict.state==="CONFIRMED"?"CONFIRMED":"PROBABLE";
  await db.prepare(`INSERT INTO candidate_verification_results(result_id,queue_id,query_fingerprint,verification_state,reason,best_offer_id,best_offer_total,currency,live_offer_count,provider_count,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(queue_id,query_fingerprint) DO UPDATE SET verification_state=excluded.verification_state,reason=excluded.reason,best_offer_id=excluded.best_offer_id,best_offer_total=excluded.best_offer_total,currency=excluded.currency,live_offer_count=excluded.live_offer_count,provider_count=excluded.provider_count,updated_at=excluded.updated_at`)
      .bind(resultId,queueId,queryFingerprint,verificationState,verdict.reason,best?.provider_offer_id??null,best?Number(best.offer_total):null,best?.currency??null,fresh.length,providers.size,nowIso).run();
  await writeVerificationSupports(db,resultId,verificationState==="CONFIRMED"?(verdict.supporting_evidence_ids??[]):[],best?.provider_offer_id??null,nowIso);
  const projection=best?await projectDirectVerifiedCandidate(db,{queue_id:queueId,query_fingerprint:queryFingerprint,verification_state:verificationState,best_offer_id:best.provider_offer_id},nowIso):await markDirectCandidateFareStale(db,{queue_id:queueId,query_fingerprint:queryFingerprint,reason:verdict.reason,evidence_id:`verification:${resultId}`},nowIso);
  return {verification_state:verificationState,reason:verdict.reason,best_offer_id:best?.provider_offer_id??null,best_offer_total:best?Number(best.offer_total):null,live_offer_count:fresh.length,provider_count:providers.size,supporting_offer_ids:verificationState==="CONFIRMED"?(verdict.supporting_evidence_ids??[]):[],projection};
}

export async function projectProviderJobResults(db:D1Database,jobId:string,nowIso:string){
  const consumers=(await db.prepare("SELECT c.plan_id,c.queue_id,p.query_fingerprint FROM provider_job_consumers c JOIN provider_search_plans p ON p.plan_id=c.plan_id WHERE c.job_id=?").bind(jobId).all<any>()).results;
  let projected=0;const seen=new Set<string>();
  for(const c of consumers){
    const offers=(await db.prepare("SELECT provider_offer_id,query_fingerprint,provider,offer_total,currency,observed_at,expires_at,cached_or_live FROM offer_snapshots WHERE source_snapshot_id=? AND query_fingerprint=? AND cached_or_live='LIVE'").bind(jobId,c.query_fingerprint).all<any>()).results;
    for(const o of offers)await db.prepare("INSERT OR IGNORE INTO candidate_offer_links(queue_id,plan_id,job_id,provider_offer_id,query_fingerprint,created_at) VALUES(?,?,?,?,?,?)").bind(c.queue_id,c.plan_id,jobId,o.provider_offer_id,c.query_fingerprint,nowIso).run();
    const key=`${c.queue_id}|${c.query_fingerprint}`;if(seen.has(key))continue;seen.add(key);
    const result=await recomputeCandidateVerification(db,c.queue_id,c.query_fingerprint,nowIso);
    if(result.verification_state==="CONFIRMED")await ackCandidateSignal(db,{queue_id:c.queue_id,ok:true},nowIso);
    projected++;
  }
  return {consumers:consumers.length,projected};
}
