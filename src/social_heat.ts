import type { D1Database } from "./types.js";
import { enqueueAlertIntent } from "./outbox.js";
import { promotionEntitlementAccess } from "./profile.js";

function parse<T>(raw:string|null|undefined,fallback:T):T{try{return raw?JSON.parse(raw) as T:fallback;}catch{return fallback;}}
function termsCurrent(v:string|null|undefined){return !!v&&v!=="RECHECK_REQUIRED"&&Number.isFinite(Date.parse(v));}
function routePair(v:unknown):[string,string]|null{if(typeof v!=="string")return null;const m=v.toUpperCase().match(/^([A-Z]{3})-([A-Z]{3})$/);return m?[m[1],m[2]]:null;}
function windowDate(raw:string|null|undefined){const x=parse<any>(raw,{});const start=typeof x?.start==="string"?x.start.slice(0,10):null,end=typeof x?.end==="string"?x.end.slice(0,10):null;return {start,end};}
function isoWeekday(date:string){const d=new Date(`${date}T00:00:00Z`).getUTCDay();return d===0?7:d;}
function saleBoundary(v:string|null,end=false){if(!v)return null;const s=/^\d{4}-\d{2}-\d{2}$/.test(v)?`${v}T${end?"23:59:59.999":"00:00:00.000"}Z`:v;const t=Date.parse(s);return Number.isFinite(t)?t:null;}
function addDays(d:string,n:number){const x=new Date(`${d}T00:00:00Z`);x.setUTCDate(x.getUTCDate()+n);return x.toISOString().slice(0,10);}

async function relevantCampaign(db:D1Database,event:any,nowIso:string){
  const routes=parse<unknown[]>(event.routes_json,[]).map(routePair).filter((x):x is [string,string]=>!!x);if(!routes.length)return {relevant:false,reason:"PROMOTION_ROUTE_UNKNOWN"};
  const tw=windowDate(event.travel_window),sw=windowDate(event.sale_window),pc=parse<any>(event.constraint_json,{}),now=Date.parse(nowIso);
  const saleStart=saleBoundary(sw.start,false),saleEnd=saleBoundary(sw.end,true);if(saleStart!==null&&now<saleStart)return {relevant:false,reason:"PROMOTION_SALE_NOT_ACTIVE"};if(saleEnd!==null&&now>saleEnd)return {relevant:false,reason:"PROMOTION_SALE_EXPIRED"};
  const rows=(await db.prepare("SELECT campaign_id,profile_id,origin_airports_json,destination_airports_json,departure_dates_json,trip_lengths_json,market FROM search_campaigns WHERE enabled=1 AND expires_at>? ORDER BY updated_at DESC LIMIT 8").bind(nowIso).all<any>()).results;
  const blackout=new Set(Array.isArray(pc.blackout_dates)?pc.blackout_dates.map(String):[]),weekdays=new Set(Array.isArray(pc.eligible_weekdays)?pc.eligible_weekdays.map(Number):[]);
  for(const c of rows){
    const origins=new Set(parse<string[]>(c.origin_airports_json,[])),dests=new Set(parse<string[]>(c.destination_airports_json,[]));if(!routes.some(([o,d])=>origins.has(o)&&dests.has(d)))continue;
    if(pc.origin_market&&(c.market??null)!==pc.origin_market)continue;
    const dates=parse<string[]>(c.departure_dates_json,[]).filter(d=>(!tw.start||d>=tw.start)&&(!tw.end||d<=tw.end)&&!blackout.has(d)&&(!weekdays.size||weekdays.has(isoWeekday(d))));if(!dates.length)continue;
    const lengths=parse<number[]>(c.trip_lengths_json,[]).filter(n=>(!pc.required_roundtrip||n>0)&&(pc.minimum_stay==null||n>=Number(pc.minimum_stay))&&(pc.maximum_stay==null||n<=Number(pc.maximum_stay))&&dates.some(d=>!tw.end||addDays(d,n)<=tw.end));if(!lengths.length)continue;
    const access=await promotionEntitlementAccess(db,c.profile_id,{member_requirement:event.member_requirement??null,channel_requirement:event.channel_requirement??null,member_only:!!pc.member_only,subscription_only:!!pc.subscription_only},nowIso);if(!access.allowed)continue;
    return {relevant:true,campaign_id:c.campaign_id,profile_id:c.profile_id,matching_dates:dates};
  }
  return {relevant:false,reason:"ROUTE_NOT_RELEVANT"};
}

export async function evaluatePromotionBurst(db:D1Database,eventId:string,nowIso:string,windowMinutes=20,minIndependentSources=3){
  if(!Number.isFinite(Date.parse(nowIso)))throw new Error("SOCIAL_HEAT_TIME_INVALID");
  if(!Number.isInteger(windowMinutes)||windowMinutes<5||windowMinutes>120)throw new Error("SOCIAL_HEAT_WINDOW_INVALID");
  if(!Number.isInteger(minIndependentSources)||minIndependentSources<2||minIndependentSources>8)throw new Error("SOCIAL_HEAT_THRESHOLD_INVALID");
  const event=await db.prepare("SELECT event_id,state,routes_json,prices_json,promo_code,sale_window,travel_window,member_requirement,channel_requirement,constraint_json,carrier_or_seller,first_observed_at,last_observed_at FROM promotion_events WHERE event_id=?").bind(eventId).first<any>();
  if(!event)return {triggered:false,reason:"PROMOTION_NOT_FOUND"};if(event.state!=="DISCOVERED")return {triggered:false,reason:"PROMOTION_NOT_ACTIVE"};
  const queue=await db.prepare("SELECT queue_id,state,priority_score FROM candidate_priority_queue WHERE signal_type='PROMOTION' AND signal_id=?").bind(eventId).first<any>();
  if(!queue||!['PENDING','LEASED'].includes(queue.state))return {triggered:false,reason:"PROMOTION_QUEUE_NOT_ACTIVE"};
  const windowStart=new Date(Date.parse(nowIso)-windowMinutes*60000).toISOString();
  const rows=(await db.prepare(`SELECT o.source_id,o.observed_at,s.canonical_domain_or_account,s.lifecycle_state,s.kill_switch,s.kill_switch_state,s.discovery_trust,s.terms_snapshot_at
    FROM promotion_event_evidence e JOIN source_observations o ON o.observation_id=e.observation_id JOIN source_registry s ON s.source_id=o.source_id
    WHERE e.event_id=? AND o.observed_at>=? AND o.observed_at<=? ORDER BY o.observed_at ASC`).bind(eventId,windowStart,nowIso).all<any>()).results;
  const eligible=rows.filter(r=>r.lifecycle_state==="ENABLED"&&Number(r.kill_switch)===0&&(r.kill_switch_state??"CLEAR")==="CLEAR"&&termsCurrent(r.terms_snapshot_at)&&["HIGH","MEDIUM"].includes(String(r.discovery_trust??"").toUpperCase()));
  const byKey=new Map<string,any>();for(const r of eligible){const key=String(r.canonical_domain_or_account??r.source_id).trim().toLowerCase();if(key&&!byKey.has(key))byKey.set(key,r);}
  const independent=[...byKey.values()],sourceIds=[...new Set(independent.map(r=>String(r.source_id)))].sort(),keys=[...byKey.keys()].sort();const high=independent.filter(r=>String(r.discovery_trust).toUpperCase()==="HIGH").length;
  const heat=Math.min(100,independent.length*20+high*10+(independent.length>=5?10:0));
  const route=await relevantCampaign(db,event,nowIso);
  await db.prepare(`INSERT INTO promotion_social_heat(event_id,window_start,window_end,independent_source_count,high_trust_source_count,source_ids_json,independence_keys_json,heat_score,route_relevant,last_evaluated_at,updated_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET window_start=excluded.window_start,window_end=excluded.window_end,independent_source_count=excluded.independent_source_count,high_trust_source_count=excluded.high_trust_source_count,source_ids_json=excluded.source_ids_json,independence_keys_json=excluded.independence_keys_json,heat_score=excluded.heat_score,route_relevant=excluded.route_relevant,last_evaluated_at=excluded.last_evaluated_at,updated_at=excluded.updated_at`)
    .bind(eventId,windowStart,nowIso,independent.length,high,JSON.stringify(sourceIds),JSON.stringify(keys),heat,route.relevant?1:0,nowIso,nowIso).run();
  if(independent.length<minIndependentSources)return {triggered:false,reason:"INDEPENDENT_SOURCE_THRESHOLD_NOT_MET",independent_source_count:independent.length,heat_score:heat};
  if(!route.relevant)return {triggered:false,reason:route.reason??"ROUTE_NOT_RELEVANT",independent_source_count:independent.length,heat_score:heat};
  await db.prepare("UPDATE candidate_priority_queue SET priority_score=CASE WHEN priority_score<90 THEN 90 ELSE priority_score END,updated_at=? WHERE queue_id=? AND state IN ('PENDING','LEASED')").bind(nowIso,queue.queue_id).run();
  const payload={kind:"P0-PROVISIONAL",verification_state:"UNVERIFIED",actionable:false,bookable:false,subject_type:"PROMOTION",event_id:eventId,carrier_or_seller:event.carrier_or_seller??null,routes:parse(event.routes_json,[]),price_claim:parse(event.prices_json,[]),promo_code:event.promo_code??null,member_requirement:event.member_requirement??null,channel_requirement:event.channel_requirement??null,provisional_trigger:{rule:"INDEPENDENT_SOURCE_BURST_V1",window_minutes:windowMinutes,independent_source_count:independent.length,high_trust_source_count:high,heat_score:heat,sources:sourceIds},route_match:route};
  const intentId=`provisional:burst:${eventId}`;await enqueueAlertIntent(db,{intent_id:intentId,itinerary_id:`promotion:${eventId}`,alert_class:"DEAL",payload},nowIso);
  await db.prepare("UPDATE promotion_social_heat SET provisional_triggered_at=COALESCE(provisional_triggered_at,?),updated_at=? WHERE event_id=?").bind(nowIso,nowIso,eventId).run();
  return {triggered:true,reason:"INDEPENDENT_SOURCE_BURST",intent_id:intentId,independent_source_count:independent.length,heat_score:heat,sources:sourceIds,route_match:route};
}

export async function evaluateDuePromotionBursts(db:D1Database,nowIso:string,limit=1){
  const rows=(await db.prepare(`SELECT p.event_id FROM promotion_events p JOIN candidate_priority_queue q ON q.signal_type='PROMOTION' AND q.signal_id=p.event_id LEFT JOIN promotion_social_heat h ON h.event_id=p.event_id
    WHERE p.state='DISCOVERED' AND q.state IN ('PENDING','LEASED') AND h.provisional_triggered_at IS NULL ORDER BY p.last_observed_at DESC LIMIT ?`).bind(Math.min(Math.max(limit,0),1)).all<any>()).results;
  let triggered=0;for(const r of rows){const x=await evaluatePromotionBurst(db,r.event_id,nowIso);if(x.triggered)triggered++;}return {considered:rows.length,triggered};
}
