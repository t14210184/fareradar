import type { D1Database } from "./types.js";
import { emailTrust } from "./source.js";
import { assertAgencyUrlAllowed } from "./agency_security.js";
function shaOK(x:string){return /^[a-f0-9]{64}$/i.test(x)}
function timeOK(x:string){return Number.isFinite(Date.parse(x))}
export async function ingestAgencyOffer(db:D1Database,input:any,nowIso:string){
  const required=['agency_offer_id','agency_id','source_id','observation_id','product_id','allotment_type','origin','destination','departure_at','price','currency','tax_inclusion','booking_or_contact_channel','observed_at','content_sha256'];
  for(const k of required)if(input[k]===undefined||input[k]===null||input[k]==='')throw new Error(`AGENCY_${k.toUpperCase()}_REQUIRED`);
  if(!shaOK(input.content_sha256)||!timeOK(input.observed_at)||!timeOK(input.departure_at))throw new Error('AGENCY_EVIDENCE_INVALID');
  const agency=await db.prepare("SELECT source_id,status,verified_business,terms_snapshot_at FROM agency_partner_registry WHERE agency_id=?").bind(input.agency_id).first<any>();
  if(!agency||agency.status!=="ENABLED"||Number(agency.verified_business)!==1||agency.source_id!==input.source_id||!agency.terms_snapshot_at||agency.terms_snapshot_at==='RECHECK_REQUIRED')throw new Error('AGENCY_PARTNER_NOT_ENABLED');
  const src=await db.prepare("SELECT access_basis FROM source_registry WHERE source_id=?").bind(input.source_id).first<any>(); if(!src)throw new Error('SOURCE_NOT_ALLOWED');
  await assertAgencyUrlAllowed(db,input.agency_id,input.booking_or_contact_channel); if(input.canonical_url)await assertAgencyUrlAllowed(db,input.agency_id,input.canonical_url,input.booking_or_contact_channel);
  const offerPayload={agency_offer_id:input.agency_offer_id,agency_id:input.agency_id,product_id:input.product_id,origin:input.origin,destination:input.destination,price:input.price,currency:input.currency,state:'AGENCY_CLAIMED'};
  await db.batch([
    db.prepare("INSERT OR IGNORE INTO source_observations(observation_id,source_id,observed_at,canonical_url,content_sha256,parser_version,access_basis,privacy_class,access_basis_snapshot,retention_until,content_version) VALUES(?,?,?,?,?,?,?,'PARTNER_STRUCTURED',?,?,1)").bind(input.observation_id,input.source_id,input.observed_at,input.canonical_url??null,input.content_sha256,input.parser_version??'agency-intake-1',src.access_basis,src.access_basis,new Date(Date.parse(input.observed_at)+180*86400000).toISOString()),
    db.prepare("INSERT INTO agency_inventory_offers(agency_offer_id,agency_id,seller_verification_state,product_id,allotment_type,origin,destination,flight_number,departure_at,return_at,price,currency,tax_inclusion,baggage,seats_total,seats_available,inventory_hint,minimum_group_size,booking_deadline,ticketing_deadline,refund_change_terms,booking_or_contact_channel,observed_at,source_evidence_id,state) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(agency_offer_id) DO UPDATE SET seats_available=excluded.seats_available,inventory_hint=excluded.inventory_hint,booking_deadline=excluded.booking_deadline,ticketing_deadline=excluded.ticketing_deadline,observed_at=excluded.observed_at,state=CASE WHEN agency_inventory_offers.state IN ('SELLER_CONFIRMED','CHECKOUT_REPRODUCED') THEN agency_inventory_offers.state ELSE excluded.state END")
      .bind(input.agency_offer_id,input.agency_id,'VERIFIED_BUSINESS',input.product_id,input.allotment_type,input.origin,input.destination,input.flight_number??null,input.departure_at,input.return_at??null,input.price,input.currency,input.tax_inclusion,input.baggage??null,input.seats_total??null,input.seats_available??null,input.inventory_hint??null,input.minimum_group_size??null,input.booking_deadline??null,input.ticketing_deadline??null,input.refund_change_terms??null,input.booking_or_contact_channel,input.observed_at,input.observation_id,'AGENCY_CLAIMED'),
    db.prepare("INSERT OR IGNORE INTO domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) VALUES('AGENCY_OFFER',?,?,'PENDING',0,?)").bind(input.agency_offer_id,JSON.stringify(offerPayload),nowIso)
  ]);
  return {agency_offer_id:input.agency_offer_id,state:'AGENCY_CLAIMED'};
}

export async function ingestEmailEvidence(db:D1Database,input:any,nowIso:string){
  if('raw_body' in input || 'body' in input)throw new Error('RAW_EMAIL_BODY_FORBIDDEN');
  const required=['message_id','source_id','observation_id','from_address','from_domain','received_at','subject','body_sha256','dkim_result','spf_result','dmarc_result','canonical_links','expanded_links','link_risk_class','retention_until'];
  for(const k of required)if(input[k]===undefined||input[k]===null)throw new Error(`EMAIL_${k.toUpperCase()}_REQUIRED`);
  if(!shaOK(input.body_sha256)||!timeOK(input.received_at)||!timeOK(input.retention_until))throw new Error('EMAIL_EVIDENCE_INVALID');
  const src=await db.prepare("SELECT access_basis,lifecycle_state FROM source_registry WHERE source_id=?").bind(input.source_id).first<any>(); if(!src||src.lifecycle_state==='DISABLED')throw new Error('SOURCE_NOT_ALLOWED');
  const trust=emailTrust({dkim:input.dkim_result,spf:input.spf_result,dmarc:input.dmarc_result,links:input.expanded_links});
  await db.batch([
    db.prepare("INSERT OR IGNORE INTO source_observations(observation_id,source_id,observed_at,canonical_url,content_sha256,parser_version,access_basis,privacy_class,access_basis_snapshot,retention_until,content_version) VALUES(?,?,?,?,?,?,?,'PRIVATE_NOTIFICATION',?,?,1)").bind(input.observation_id,input.source_id,input.received_at,input.canonical_links[0]??null,input.body_sha256,input.parser_version??'email-intake-1',src.access_basis,src.access_basis,input.retention_until),
    db.prepare("INSERT INTO email_evidence(message_id,source_id,observation_id,from_address,from_domain,received_at,subject,body_sha256,attachment_sha256_json,dkim_result,spf_result,dmarc_result,canonical_links_json,expanded_links_json,link_risk_class,trust_class,retention_until) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(message_id) DO NOTHING")
      .bind(input.message_id,input.source_id,input.observation_id,input.from_address,input.from_domain,input.received_at,input.subject,input.body_sha256,JSON.stringify(input.attachment_sha256??[]),input.dkim_result,input.spf_result,input.dmarc_result,JSON.stringify(input.canonical_links),JSON.stringify(input.expanded_links),input.link_risk_class,trust,input.retention_until),
    db.prepare("INSERT OR IGNORE INTO domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) VALUES('EMAIL_EVIDENCE',?,?,'PENDING',0,?)").bind(input.message_id,JSON.stringify({message_id:input.message_id,trust_class:trust,observation_id:input.observation_id}),nowIso)
  ]);
  return {message_id:input.message_id,trust_class:trust};
}
