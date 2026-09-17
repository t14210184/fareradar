import type { D1Database } from "./types.js";
function nonempty(v:unknown,n:string){if(typeof v!=="string"||!v.trim())throw new Error(`${n}_REQUIRED`)}
function sha(v:string){return /^[a-f0-9]{64}$/i.test(v)}
function termsCurrent(v:string|null|undefined){return !!v&&v!=="RECHECK_REQUIRED"&&Number.isFinite(Date.parse(v))}
export interface OfferSnapshotInput { provider_offer_id:string; itinerary_id?:string|null; query_fingerprint:string; provider:string; market?:string|null; locale?:string|null; currency:string; passenger_mix?:string|null; baggage_query?:string|null; observed_at:string; expires_at?:string|null; raw_sha256:string; source_snapshot_id?:string|null; offer_total:number; fare_freshness:string; cached_or_live:"CACHED"|"LIVE"; contains_lcc?:boolean; offer_structure?:unknown|null; }
export async function ingestOfferSnapshot(db:D1Database,o:OfferSnapshotInput){
  for(const [v,n] of [[o.provider_offer_id,'PROVIDER_OFFER_ID'],[o.query_fingerprint,'QUERY_FINGERPRINT'],[o.provider,'PROVIDER'],[o.currency,'CURRENCY'],[o.observed_at,'OBSERVED_AT']] as const)nonempty(v,n);
  if(!sha(o.raw_sha256)||!Number.isFinite(Date.parse(o.observed_at))||!Number.isFinite(o.offer_total)||o.offer_total<0)throw new Error('OFFER_INVALID');
  const access=await db.prepare("SELECT access_basis,terms_snapshot_at,rate_policy,kill_switch_state FROM provider_access_registry WHERE provider_id=?").bind(o.provider).first<any>();
  if(!access||!termsCurrent(access.terms_snapshot_at)||access.kill_switch_state==='TRIPPED')throw new Error('PROVIDER_ACCESS_NOT_READY');
  if(o.provider==='amadeus_self_service'&&o.contains_lcc)throw new Error('AMADEUS_LCC_EXCLUDED');
  const structureJson=o.offer_structure==null?null:JSON.stringify(o.offer_structure); if(structureJson&&structureJson.length>65536)throw new Error('OFFER_STRUCTURE_TOO_LARGE');
  const prior=await db.prepare("SELECT raw_sha256,query_fingerprint FROM offer_snapshots WHERE provider_offer_id=?").bind(o.provider_offer_id).first<any>();
  if(prior){if(prior.raw_sha256!==o.raw_sha256||prior.query_fingerprint!==o.query_fingerprint)throw new Error('OFFER_ID_CONFLICT');await db.prepare("INSERT OR IGNORE INTO domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) VALUES('OFFER_SNAPSHOT',?,?,'PENDING',0,?)").bind(o.provider_offer_id,JSON.stringify({provider_offer_id:o.provider_offer_id}),o.observed_at).run();return {provider_offer_id:o.provider_offer_id,idempotent:true};}
  await db.batch([
    db.prepare("INSERT INTO offer_snapshots(provider_offer_id,itinerary_id,query_fingerprint,provider,market,locale,currency,passenger_mix,baggage_query,observed_at,expires_at,raw_sha256,source_snapshot_id,offer_total,fare_freshness,cached_or_live,offer_structure_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
      .bind(o.provider_offer_id,o.itinerary_id??null,o.query_fingerprint,o.provider,o.market??null,o.locale??null,o.currency,o.passenger_mix??null,o.baggage_query??null,o.observed_at,o.expires_at??null,o.raw_sha256,o.source_snapshot_id??null,o.offer_total,o.fare_freshness,o.cached_or_live,structureJson),
    db.prepare("INSERT OR IGNORE INTO domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) VALUES('OFFER_SNAPSHOT',?,?,'PENDING',0,?)").bind(o.provider_offer_id,JSON.stringify({provider_offer_id:o.provider_offer_id}),o.observed_at)
  ]);
  return {provider_offer_id:o.provider_offer_id,idempotent:false};
}
