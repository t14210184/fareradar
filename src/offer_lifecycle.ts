import type { D1Database } from "./types.js";
import { enqueueAlertIntent } from "./outbox.js";
import { enqueueProviderSearch } from "./provider_jobs.js";
import { directItineraryId } from "./direct_candidate.js";
import { recomputeCandidateVerification } from "./provider_results.js";

type LifecycleRow={
  event_id:string; result_id:string; queue_id:string; query_fingerprint:string; itinerary_id:string|null;
  provider_offer_id:string; previous_verification_state:string; new_verification_state:string; reason:string;
  effective_at:string; support_provider_ids_json:string; had_visible_notification:number;
  correction_state:"PENDING"|"NOT_REQUIRED"|"ENQUEUED"; reprice_state:"PENDING"|"NOT_REQUIRED"|"ENQUEUED"|"PARTIAL"|"FAILED";
  last_error:string|null;
};
function safe(v:string){return v.replace(/[^A-Za-z0-9._:-]/g,"_");}
function parseList(raw:string|null|undefined){try{const x=raw?JSON.parse(raw):[];return Array.isArray(x)?x.map(String):[];}catch{return [];}}
function isExpired(v:string|null|undefined,nowIso:string){return !!v&&Number.isFinite(Date.parse(v))&&Date.parse(v)<=Date.parse(nowIso);}

async function finishLifecycleEvent(db:D1Database,event:LifecycleRow,nowIso:string){
  let repriceState=event.reprice_state;let correctionState=event.correction_state;const jobs:string[]=[];const errors:string[]=[];
  if(repriceState==="PENDING"){
    const plans=(await db.prepare("SELECT plan_id,provider_id,query_json,created_at FROM provider_search_plans WHERE queue_id=? AND query_fingerprint=? ORDER BY created_at,plan_id").bind(event.queue_id,event.query_fingerprint).all<any>()).results;
    const supportProviders=new Set(parseList(event.support_provider_ids_json));
    const ranked=[...plans].sort((a,b)=>(supportProviders.has(a.provider_id)?0:1)-(supportProviders.has(b.provider_id)?0:1)||String(a.created_at).localeCompare(String(b.created_at))||String(a.plan_id).localeCompare(String(b.plan_id)));
    const chosen:any[]=[];const seen=new Set<string>();for(const p of ranked){if(seen.has(p.provider_id))continue;seen.add(p.provider_id);chosen.push(p);if(chosen.length>=2)break;}
    if(!chosen.length){repriceState="FAILED";errors.push("REPRICE_PLAN_MISSING");}
    for(const plan of chosen){
      try{
        const out=await enqueueProviderSearch(db,{provider_id:plan.provider_id,mode:"BACKGROUND",query:JSON.parse(plan.query_json),refresh_key:event.event_id},nowIso);
        await db.prepare("INSERT OR IGNORE INTO provider_job_consumers(job_id,plan_id,queue_id,created_at) VALUES(?,?,?,?)").bind(out.job_id,plan.plan_id,event.queue_id,nowIso).run();
        jobs.push(out.job_id);
      }catch(e){errors.push(`${plan.provider_id}:${e instanceof Error?e.message:String(e)}`);}
    }
    if(jobs.length&&errors.length)repriceState="PARTIAL";else if(jobs.length)repriceState="ENQUEUED";else if(repriceState!=="FAILED")repriceState="FAILED";
    await db.prepare("UPDATE live_offer_lifecycle_events SET reprice_state=?,last_error=?,updated_at=? WHERE event_id=?").bind(repriceState,errors.length?errors.join("|"):null,nowIso,event.event_id).run();
    if(errors.length){await enqueueAlertIntent(db,{intent_id:`admin-live-offer-refresh:${event.event_id}`,itinerary_id:event.itinerary_id??event.queue_id,alert_class:"ADMIN",payload:{type:"LIVE_OFFER_REFRESH_ENQUEUE_FAILED",event_id:event.event_id,queue_id:event.queue_id,query_fingerprint:event.query_fingerprint,errors}},nowIso);}
  }
  if(correctionState==="PENDING"){
    if(event.had_visible_notification){
      const intentId=`live-offer-expiry:${event.event_id}`;
      await enqueueAlertIntent(db,{intent_id:intentId,itinerary_id:event.itinerary_id??event.queue_id,alert_class:"DEAL",payload:{kind:"DEAL-UPDATE",verification_state:"PROBABLE",actionable:false,bookable:false,subject_type:"LIVE_PROVIDER_OFFER",itinerary_id:event.itinerary_id,queue_id:event.queue_id,query_fingerprint:event.query_fingerprint,expired_offer_id:event.provider_offer_id,reason:"LIVE_OFFER_EXPIRED",effective_at:event.effective_at,reprice_state:repriceState,reprice_job_ids:jobs}},nowIso);
      correctionState="ENQUEUED";
    }else correctionState="NOT_REQUIRED";
    await db.prepare("UPDATE live_offer_lifecycle_events SET correction_state=?,updated_at=? WHERE event_id=?").bind(correctionState,nowIso,event.event_id).run();
  }
  return {event_id:event.event_id,reprice_state:repriceState,correction_state:correctionState,reprice_jobs:jobs,errors};
}

export async function expireLiveProviderOffers(db:D1Database,nowIso:string,limit=1){
  if(!Number.isFinite(Date.parse(nowIso)))throw new Error("LIVE_OFFER_EXPIRY_TIME_INVALID");
  const pending=await db.prepare("SELECT * FROM live_offer_lifecycle_events WHERE correction_state='PENDING' OR reprice_state='PENDING' ORDER BY created_at,event_id LIMIT 1").first<LifecycleRow>();
  if(pending){const finished=await finishLifecycleEvent(db,pending,nowIso);return {processed:0,resumed:1,...finished};}
  const due=(await db.prepare(`SELECT v.result_id,v.queue_id,v.query_fingerprint,v.verification_state,s.provider_offer_id,o.provider,o.expires_at
    FROM candidate_verification_results v
    JOIN candidate_verification_supports s ON s.result_id=v.result_id
    JOIN offer_snapshots o ON o.provider_offer_id=s.provider_offer_id
    LEFT JOIN live_offer_lifecycle_events e ON e.result_id=v.result_id AND e.provider_offer_id=s.provider_offer_id
    WHERE v.verification_state='CONFIRMED' AND o.cached_or_live='LIVE' AND o.expires_at IS NOT NULL
      AND datetime(o.expires_at)<=datetime(?) AND e.event_id IS NULL
    ORDER BY datetime(o.expires_at),v.updated_at,v.result_id LIMIT ?`).bind(nowIso,Math.min(Math.max(limit,1),1)).all<any>()).results;
  if(!due.length)return {processed:0,resumed:0};
  const trigger=due[0];
  const supports=(await db.prepare(`SELECT s.provider_offer_id,o.provider,o.expires_at FROM candidate_verification_supports s JOIN offer_snapshots o ON o.provider_offer_id=s.provider_offer_id WHERE s.result_id=? ORDER BY s.support_role,s.provider_offer_id`).bind(trigger.result_id).all<any>()).results;
  const expired=supports.filter((x:any)=>isExpired(x.expires_at,nowIso));if(!expired.length)return {processed:0,resumed:0};
  const expiredOffer=expired[0];const itineraryId=directItineraryId(trigger.queue_id,trigger.query_fingerprint);
  const eventId=`live-life:${safe(trigger.result_id)}:${safe(expiredOffer.provider_offer_id)}`;
  const supportProviders=[...new Set(supports.map((x:any)=>String(x.provider)).filter(Boolean))];
  // Re-evaluate all already-linked fresh evidence before creating user-visible churn. If redundant
  // live evidence can immediately sustain CONFIRMED, rotate the support lineage and record the
  // expiry event without a false downgrade/correction/reprice.
  const reevaluated=await recomputeCandidateVerification(db,trigger.queue_id,trigger.query_fingerprint,nowIso);
  if(reevaluated.verification_state==="CONFIRMED"){
    await db.prepare("INSERT OR IGNORE INTO live_offer_lifecycle_events(event_id,result_id,queue_id,query_fingerprint,itinerary_id,provider_offer_id,previous_verification_state,new_verification_state,reason,effective_at,support_provider_ids_json,had_visible_notification,correction_state,reprice_state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'CONFIRMED','LIVE_OFFER_EXPIRED',?,?,0,'NOT_REQUIRED','NOT_REQUIRED',?,?)")
      .bind(eventId,trigger.result_id,trigger.queue_id,trigger.query_fingerprint,itineraryId,expiredOffer.provider_offer_id,trigger.verification_state,expiredOffer.expires_at,JSON.stringify(supportProviders),nowIso,nowIso).run();
    return {processed:1,resumed:0,expired_offer_id:expiredOffer.provider_offer_id,event_id:eventId,reprice_state:"NOT_REQUIRED",correction_state:"NOT_REQUIRED",preserved_confirmation:true,supporting_offer_ids:reevaluated.supporting_offer_ids};
  }
  const visible=await db.prepare(`SELECT COUNT(*) AS n FROM notification_outbox n JOIN candidate_alert_intents a ON a.intent_id=n.notification_id WHERE a.itinerary_id=? AND a.alert_class='DEAL' AND n.state IN ('DELIVERED','SENDING')`).bind(itineraryId).first<any>();
  await db.batch([
    db.prepare("INSERT OR IGNORE INTO live_offer_lifecycle_events(event_id,result_id,queue_id,query_fingerprint,itinerary_id,provider_offer_id,previous_verification_state,new_verification_state,reason,effective_at,support_provider_ids_json,had_visible_notification,correction_state,reprice_state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'PROBABLE','LIVE_OFFER_EXPIRED',?,?,?,'PENDING','PENDING',?,?)")
      .bind(eventId,trigger.result_id,trigger.queue_id,trigger.query_fingerprint,itineraryId,expiredOffer.provider_offer_id,trigger.verification_state,expiredOffer.expires_at,JSON.stringify(supportProviders),Number(visible?.n??0)>0?1:0,nowIso,nowIso),
    db.prepare("UPDATE candidate_verification_results SET verification_state='PROBABLE',reason='SUPPORTING_LIVE_OFFER_EXPIRED',updated_at=? WHERE result_id=?").bind(nowIso,trigger.result_id),
    db.prepare("DELETE FROM candidate_verification_supports WHERE result_id=?").bind(trigger.result_id),
    db.prepare("UPDATE itinerary_candidates SET verification_state='PROBABLE',updated_at=? WHERE itinerary_id=?").bind(nowIso,itineraryId),
    db.prepare(`UPDATE readiness_facets SET status='STALE',reason_code='LIVE_OFFER_EXPIRED',observed_at=?,expires_at=?,authority='SYSTEM_EVIDENCE',evidence_id=? WHERE itinerary_id=? AND facet_type='FARE_VERIFIED'`).bind(nowIso,nowIso,eventId,itineraryId),
    db.prepare("UPDATE candidate_alert_intents SET projected_at=? WHERE itinerary_id=? AND alert_class='DEAL' AND projected_at IS NULL").bind(nowIso,itineraryId),
    db.prepare("UPDATE notification_outbox SET state='CANCELLED',lease_until=NULL,last_error='LIVE_OFFER_EXPIRED' WHERE notification_id IN (SELECT intent_id FROM candidate_alert_intents WHERE itinerary_id=? AND alert_class='DEAL') AND state IN ('PENDING','SHADOW_HELD')").bind(itineraryId)
  ]);
  const event=await db.prepare("SELECT * FROM live_offer_lifecycle_events WHERE event_id=?").bind(eventId).first<LifecycleRow>();
  if(!event)throw new Error("LIVE_OFFER_LIFECYCLE_EVENT_MISSING");
  const finished=await finishLifecycleEvent(db,event,nowIso);
  return {processed:1,resumed:0,expired_offer_id:expiredOffer.provider_offer_id,...finished};
}
