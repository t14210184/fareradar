import type { D1Database } from "./types.js";
import { baselineForOffer } from "./baseline.js";
import { buildCanonicalCandidateAlert } from "./alert_runtime.js";
import { enqueueAlertIntent } from "./outbox.js";

function parse(raw:string|null|undefined){try{return raw?JSON.parse(raw):null}catch{return null}}
function currentTerms(v:string|null|undefined){return !!v&&v!=="RECHECK_REQUIRED"&&Number.isFinite(Date.parse(v));}
function routeFromStructure(raw:string|null|undefined){const x=parse(raw);const segs=Array.isArray(x?.slices?.[0]?.segments)?x.slices[0].segments:[];if(!segs.length)return null;const o=String(segs[0]?.origin??"").toUpperCase(),d=String(segs[segs.length-1]?.destination??"").toUpperCase(),departing=String(segs[0]?.departing_at??"");const departureDate=/^\d{4}-\d{2}-\d{2}/.test(departing)?departing.slice(0,10):null;return /^[A-Z]{3}$/.test(o)&&/^[A-Z]{3}$/.test(d)&&departureDate?{origin:o,destination:d,departure_date:departureDate}:null;}
function parseList(raw:string|null|undefined){const x=parse(raw);return Array.isArray(x)?x.map(String):[];}
async function sourceTrust(db:D1Database,evidenceIds:string[]){
  if(!evidenceIds.length)return {trusted:false,sources:[] as string[]};const marks=evidenceIds.map(()=>'?').join(',');
  const rows=(await db.prepare(`SELECT DISTINCT s.source_id,s.lifecycle_state,s.kill_switch,s.kill_switch_state,s.discovery_trust,s.terms_snapshot_at FROM source_observations o JOIN source_registry s ON s.source_id=o.source_id WHERE o.observation_id IN (${marks})`).bind(...evidenceIds).all<any>()).results;
  const trusted=rows.filter(r=>r.lifecycle_state==="ENABLED"&&Number(r.kill_switch)===0&&(r.kill_switch_state??"CLEAR")==="CLEAR"&&r.discovery_trust==="HIGH"&&currentTerms(r.terms_snapshot_at));
  return {trusted:trusted.length>0,sources:trusted.map(r=>r.source_id).sort()};
}
async function routeRelevant(db:D1Database,profileId:string|null,offerStructure:string|null|undefined,nowIso:string){
  if(!profileId)return false;const route=routeFromStructure(offerStructure);if(!route)return false;
  const rows=(await db.prepare("SELECT origin_airports_json,destination_airports_json,departure_dates_json FROM search_campaigns WHERE profile_id=? AND enabled=1 AND expires_at>?").bind(profileId,nowIso).all<any>()).results;
  return rows.some(r=>parseList(r.origin_airports_json).includes(route.origin)&&parseList(r.destination_airports_json).includes(route.destination)&&parseList(r.departure_dates_json).includes(route.departure_date));
}
export async function evaluateProvisionalCandidate(db:D1Database,itineraryId:string,nowIso:string,threshold=0.70,minSamples=5){
  const i=await db.prepare("SELECT itinerary_id,profile_id,verification_state,updated_at FROM itinerary_candidates WHERE itinerary_id=?").bind(itineraryId).first<any>();
  if(!i)return {triggered:false,reason:"ITINERARY_NOT_FOUND"};if(i.verification_state!=="PROBABLE")return {triggered:false,reason:"NOT_PROBABLE"};
  const o=await db.prepare(`SELECT o.provider_offer_id,o.offer_total,o.currency,o.cached_or_live,o.offer_structure_json FROM cost_components c JOIN offer_snapshots o ON o.provider_offer_id=c.source_offer_id WHERE c.itinerary_id=? AND c.source_offer_id IS NOT NULL ORDER BY CASE WHEN o.cached_or_live='LIVE' THEN 0 ELSE 1 END,o.offer_total LIMIT 1`).bind(itineraryId).first<any>();
  if(!o||o.cached_or_live!=="LIVE"||o.currency!=="TWD")return {triggered:false,reason:"LIVE_TWD_OFFER_REQUIRED"};
  const baseline=await baselineForOffer(db,o.provider_offer_id,nowIso,180,minSamples);if(!baseline.ready||!baseline.median)return {triggered:false,reason:baseline.reason,baseline};
  const ratio=Number(o.offer_total)/Number(baseline.median);if(!Number.isFinite(ratio)||ratio>threshold)return {triggered:false,reason:"ANOMALY_THRESHOLD_NOT_MET",ratio,baseline};
  const plan=await db.prepare("SELECT discovery_evidence_json FROM candidate_plan_intakes WHERE itinerary_id=? ORDER BY observed_at DESC LIMIT 1").bind(itineraryId).first<any>();const evidenceIds=parseList(plan?.discovery_evidence_json);
  const trust=await sourceTrust(db,evidenceIds);if(!trust.trusted)return {triggered:false,reason:"DISCOVERY_SOURCE_NOT_TRUSTED",ratio,baseline};
  if(!await routeRelevant(db,i.profile_id??null,o.offer_structure_json,nowIso))return {triggered:false,reason:"ROUTE_NOT_RELEVANT",ratio,baseline};
  const payload:any=await buildCanonicalCandidateAlert(db,itineraryId,nowIso,true);payload.provisional_trigger={rule:"HISTORICAL_ANOMALY_V1",offer_total_twd:Number(o.offer_total),baseline_median_twd:Number(baseline.median),sample_count:baseline.sample_count,ratio,threshold,baseline_key:baseline.baseline_key,trusted_sources:trust.sources};
  const intentId=`provisional:${itineraryId}:${o.provider_offer_id}:${baseline.baseline_key}`;await enqueueAlertIntent(db,{intent_id:intentId,itinerary_id:itineraryId,alert_class:"DEAL",payload},nowIso);
  return {triggered:true,reason:"HISTORICAL_ANOMALY",intent_id:intentId,ratio,baseline,trusted_sources:trust.sources};
}
export async function evaluateDueProvisionals(db:D1Database,nowIso:string,limit=1){
  const rows=(await db.prepare("SELECT itinerary_id FROM itinerary_candidates WHERE verification_state='PROBABLE' ORDER BY updated_at DESC LIMIT ?").bind(Math.min(Math.max(limit,0),2)).all<any>()).results;let triggered=0;
  for(const r of rows){const x=await evaluateProvisionalCandidate(db,r.itinerary_id,nowIso);if(x.triggered)triggered++;}
  return {considered:rows.length,triggered};
}
