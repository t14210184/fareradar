import type { CandidatePlanInput, D1Database, ReadinessFacetInput } from "./types.js";
import { persistCandidatePlan } from "./intake.js";
import { evaluateBaggageEvidence } from "./baggage.js";

function safe(v:string){return v.replace(/[^A-Za-z0-9._:-]/g,"_");}
function plusMinutes(iso:string,n:number){return new Date(Date.parse(iso)+n*60000).toISOString();}
function parseStructure(raw:string|null|undefined):any|null{try{return raw?JSON.parse(raw):null;}catch{return null;}}
function directSlices(s:any){return Array.isArray(s?.slices)&&s.slices.length>=1&&s.slices.length<=2&&s.slices.every((x:any)=>Array.isArray(x?.segments)&&x.segments.length===1&&x.segments[0]?.origin&&x.segments[0]?.destination&&x.segments[0]?.departing_at&&x.segments[0]?.arriving_at);}
function strategyFor(s:any){if(s.slices.length===1)return "S01_DIRECT_OW";const a=s.slices[0].segments[0],b=s.slices[1].segments[0];return a.origin===b.destination&&a.destination===b.origin?"S00_DIRECT_RT":"UNSUPPORTED";}
function facet(type:any,status:any,reason:string,observedAt:string,expires:string,evidence:string):ReadinessFacetInput{return {facet_type:type,status,reason_code:reason,observed_at:observedAt,expires_at:expires,authority:"SYSTEM_EVIDENCE",evidence_id:evidence};}

export function directItineraryId(queueId:string,queryFingerprint:string){return `direct:${safe(queueId)}:${queryFingerprint}`;}

export async function markDirectCandidateFareStale(db:D1Database,input:{queue_id:string;query_fingerprint:string;reason:string;evidence_id:string},nowIso:string){
  const itineraryId=directItineraryId(input.queue_id,input.query_fingerprint);
  const existing=await db.prepare("SELECT itinerary_id FROM itinerary_candidates WHERE itinerary_id=?").bind(itineraryId).first<any>();
  if(!existing)return {updated:false,itinerary_id:itineraryId};
  await db.batch([
    db.prepare("UPDATE itinerary_candidates SET verification_state='PROBABLE',updated_at=? WHERE itinerary_id=?").bind(nowIso,itineraryId),
    db.prepare(`INSERT INTO readiness_facets(itinerary_id,facet_type,status,reason_code,observed_at,expires_at,authority,evidence_id)
      VALUES(?,'FARE_VERIFIED','STALE',?,?,?,'SYSTEM_EVIDENCE',?)
      ON CONFLICT(itinerary_id,facet_type) DO UPDATE SET status='STALE',reason_code=excluded.reason_code,observed_at=excluded.observed_at,expires_at=excluded.expires_at,authority=excluded.authority,evidence_id=excluded.evidence_id`)
      .bind(itineraryId,input.reason,nowIso,nowIso,input.evidence_id)
  ]);
  return {updated:true,itinerary_id:itineraryId};
}

export async function projectDirectVerifiedCandidate(db:D1Database,input:{queue_id:string;query_fingerprint:string;verification_state:"PROBABLE"|"CONFIRMED";best_offer_id:string},nowIso:string){
  const offer=await db.prepare("SELECT provider_offer_id,provider,currency,offer_total,observed_at,expires_at,offer_structure_json,baggage_query FROM offer_snapshots WHERE provider_offer_id=?").bind(input.best_offer_id).first<any>();
  if(!offer)return {projected:false,reason:"OFFER_NOT_FOUND"};
  const structure=parseStructure(offer.offer_structure_json);if(!directSlices(structure))return {projected:false,reason:"COMPLEX_OR_INCOMPLETE_STRUCTURE"};
  const strategy=strategyFor(structure);if(strategy==="UNSUPPORTED")return {projected:false,reason:"NON_ROUNDTRIP_TWO_SLICE"};
  const q=await db.prepare("SELECT source_evidence_id FROM candidate_priority_queue WHERE queue_id=?").bind(input.queue_id).first<any>();if(!q)return {projected:false,reason:"QUEUE_NOT_FOUND"};
  const profileRows=(await db.prepare("SELECT DISTINCT c.profile_id FROM provider_search_plans p JOIN search_campaigns c ON c.campaign_id=p.campaign_id WHERE p.queue_id=? AND p.query_fingerprint=?").bind(input.queue_id,input.query_fingerprint).all<{profile_id:string}>()).results;
  const profileIds=[...new Set(profileRows.map(x=>x.profile_id).filter(Boolean))];if(profileIds.length!==1)return {projected:false,reason:profileIds.length?"PROFILE_LINEAGE_AMBIGUOUS":"PROFILE_LINEAGE_MISSING"};
  const profileExists=await db.prepare("SELECT profile_id FROM runtime_profiles WHERE profile_id=?").bind(profileIds[0]).first();if(!profileExists)return {projected:false,reason:"PROFILE_LINEAGE_MISSING"};
  const itineraryId=directItineraryId(input.queue_id,input.query_fingerprint);
  const intakeId=`direct-project:${safe(input.queue_id)}:${input.query_fingerprint}:${input.verification_state}:${safe(offer.provider_offer_id)}`;
  const evidence=`offer:${offer.provider_offer_id}`;
  const basis=Number.isFinite(Date.parse(offer.observed_at))?offer.observed_at:nowIso;
  const fallbackExpiry=plusMinutes(basis,15);const offerExpiry=offer.expires_at&&Number.isFinite(Date.parse(offer.expires_at))?offer.expires_at:null;
  const farePass=input.verification_state==="CONFIRMED"&&offerExpiry&&Date.parse(offerExpiry)>Date.parse(nowIso);const expiry=offerExpiry??fallbackExpiry;
  const baggage=evaluateBaggageEvidence(structure,offer.baggage_query);
  const segments=structure.slices.flatMap((x:any)=>x.segments);const carriers:string[]=[...new Set<string>(segments.map((x:any)=>String(x.marketing_carrier??"")).filter(Boolean))];
  const readiness:ReadinessFacetInput[]=[
    facet("FARE_VERIFIED",farePass?"PASS":"UNKNOWN",farePass?"CONFIRMED_LIVE_OFFER":"OFFER_OR_EXPIRY_NOT_CONFIRMED",basis,expiry,evidence),
    facet("DOCUMENT_CLEAR","UNKNOWN","DOCUMENT_POLICY_REQUIRED",basis,fallbackExpiry,evidence),
    facet("CONNECTION_ACCEPTABLE","PASS","DIRECT_NO_CONNECTION",basis,expiry,evidence),
    facet("BAGGAGE_FEASIBLE",baggage.status,baggage.reason,basis,baggage.status==="PASS"?expiry:fallbackExpiry,evidence),
    facet("COST_COMPLETE","FAIL","MANDATORY_EXTRAS_NOT_PROVEN",basis,fallbackExpiry,evidence),
    facet("COUPON_SEQUENCE_CLEAR","PASS","ALL_PLANNED_SLICES_FLOWN",basis,expiry,evidence),
    facet("POLICY_FRESH","UNKNOWN","POLICY_SNAPSHOT_REQUIRED",basis,fallbackExpiry,evidence)
  ];
  const plan:CandidatePlanInput={
    intake_id:intakeId,discovery_evidence_ids:q.source_evidence_id?[q.source_evidence_id]:[],
    itinerary:{itinerary_id:itineraryId,profile_id:profileIds[0],strategy_type:strategy,cash_trip_cost_twd:null,cost_complete:false,risk_adjusted_cost_twd:null,scenario_cost_twd:null,generalized_cost_twd:null,risk_class:"LOW_COMPLEXITY_INCOMPLETE",verification_state:input.verification_state},
    tickets:[{ticket_id:`ticket:${itineraryId}`,pnr_group:`offer:${offer.provider_offer_id}`,provider:offer.provider,ticket_type:structure.slices.length===1?"ONE_WAY":"ROUND_TRIP",connection_protection_type:"NOT_APPLICABLE_DIRECT",validating_carrier:carriers.length===1?carriers[0]:null,segments}],
    transfers:[],
    costs:[{cost_id:`cost:${itineraryId}:offer`,type:"OFFER_TOTAL",amount:Number(offer.offer_total),currency:offer.currency,twd_amount:offer.currency==="TWD"?Number(offer.offer_total):null,inclusion_state:"INCLUDED_IN_OFFER",source_offer_id:offer.provider_offer_id,dedupe_key:"offer-total",certainty:input.verification_state,paid_state:"UNPAID",refundable:false,observed_at:offer.observed_at,evidence_expires_at:offerExpiry}],
    readiness,documents:[],four_leg_liabilities:[]
  };
  const persisted=await persistCandidatePlan(db,plan,nowIso);return {projected:true,itinerary_id:itineraryId,statements:persisted.statements};
}
