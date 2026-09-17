import type { D1Database } from "./types.js";

export async function buildCanonicalCandidateAlert(db:D1Database,itineraryId:string,nowIso:string,provisional:boolean){
  const i=await db.prepare("SELECT itinerary_id,profile_id,strategy_type,cash_trip_cost_twd,cost_complete,risk_adjusted_cost_twd,scenario_cost_json,generalized_cost_twd,risk_class,verification_state,updated_at FROM itinerary_candidates WHERE itinerary_id=?").bind(itineraryId).first<any>();
  if(!i)throw new Error("ITINERARY_NOT_FOUND");
  const facets=(await db.prepare("SELECT facet_type,status,reason_code,observed_at,expires_at,authority,evidence_id FROM readiness_facets WHERE itinerary_id=? ORDER BY facet_type").bind(itineraryId).all<any>()).results;
  const tickets=(await db.prepare("SELECT ticket_id,provider,ticket_type,connection_protection_type,validating_carrier,segments_json FROM ticket_components WHERE itinerary_id=? ORDER BY ticket_id").bind(itineraryId).all<any>()).results.map(t=>({...t,segments:JSON.parse(t.segments_json??"[]"),segments_json:undefined}));
  const offers=(await db.prepare("SELECT DISTINCT o.provider_offer_id,o.provider,o.query_fingerprint,o.currency,o.offer_total,o.observed_at,o.expires_at,o.cached_or_live FROM cost_components c JOIN offer_snapshots o ON o.provider_offer_id=c.source_offer_id WHERE c.itinerary_id=? ORDER BY o.provider,o.provider_offer_id").bind(itineraryId).all<any>()).results;
  const provenance=(await db.prepare("SELECT DISTINCT source_id,observation_id,first_win FROM source_outcome_attributions WHERE itinerary_id=? ORDER BY first_win DESC,source_id").bind(itineraryId).all<any>()).results;
  return {
    kind:provisional?"P0-PROVISIONAL":"P0-ACTIONABLE",
    itinerary_id:i.itinerary_id, profile_id:i.profile_id??null, strategy_type:i.strategy_type,
    cash_trip_cost_twd:i.cash_trip_cost_twd==null?null:Number(i.cash_trip_cost_twd), cost_complete:Number(i.cost_complete)===1,
    risk_adjusted_cost_twd:i.risk_adjusted_cost_twd==null?null:Number(i.risk_adjusted_cost_twd),
    scenario_cost_twd:i.scenario_cost_json?JSON.parse(i.scenario_cost_json):null,
    generalized_cost_twd:i.generalized_cost_twd==null?null:Number(i.generalized_cost_twd), risk_class:i.risk_class,
    verification_state:i.verification_state, updated_at:i.updated_at, generated_at:nowIso,
    readiness:facets, tickets, offers, source_provenance:provenance
  };
}
