import type { D1Database } from "./types.js";

function assert(c:boolean,m:string):asserts c{if(!c)throw new Error(m);}
function currentTerms(v:string|null|undefined){return !!v&&v!=="RECHECK_REQUIRED"&&Number.isFinite(Date.parse(v));}
function parseJson(raw:string|null|undefined){try{return raw?JSON.parse(raw):null}catch{return null}}
function stable(v:any):string{if(v===null||typeof v!=="object")return JSON.stringify(v);if(Array.isArray(v))return `[${v.map(stable).join(",")}]`;return `{${Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+stable(v[k])).join(",")}}`;}
async function sha256Hex(text:string){const h=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));return [...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,"0")).join("");}

export interface PaymentProfileInput {payment_profile_id:string;provider_id:string;payment_method_class:"CARD";credential_binding:string;enabled:boolean;expires_at:string;}
export async function upsertPaymentProfile(db:D1Database,input:PaymentProfileInput,nowIso:string){
  assert(!!input.payment_profile_id&&!!input.provider_id,"PAYMENT_PROFILE_IDENTITY_REQUIRED");
  assert(input.payment_method_class==="CARD","PAYMENT_METHOD_UNSUPPORTED");
  assert(/^[A-Z][A-Z0-9_]{2,63}$/.test(input.credential_binding),"CREDENTIAL_BINDING_INVALID");
  if(input.provider_id==="duffel")assert(input.credential_binding==="DUFFEL_PAYMENT_CARD_ID","DUFFEL_PAYMENT_BINDING_REQUIRED");
  assert(Number.isFinite(Date.parse(input.expires_at))&&Date.parse(input.expires_at)>Date.parse(nowIso),"PAYMENT_PROFILE_EXPIRED");
  const p=await db.prepare("SELECT provider_id FROM provider_access_registry WHERE provider_id=?").bind(input.provider_id).first();assert(!!p,"PROVIDER_NOT_FOUND");
  await db.prepare(`INSERT INTO runtime_payment_profiles(payment_profile_id,provider_id,payment_method_class,credential_binding,enabled,expires_at,created_at,updated_at)
    VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(payment_profile_id) DO UPDATE SET provider_id=excluded.provider_id,payment_method_class=excluded.payment_method_class,credential_binding=excluded.credential_binding,enabled=excluded.enabled,expires_at=excluded.expires_at,updated_at=excluded.updated_at`)
    .bind(input.payment_profile_id,input.provider_id,input.payment_method_class,input.credential_binding,input.enabled?1:0,input.expires_at,nowIso,nowIso).run();
  return {payment_profile_id:input.payment_profile_id};
}

export interface SelectedService {id:string;quantity:number;}
function validateServices(structureRaw:string|null|undefined,selected:SelectedService[]){
  assert(Array.isArray(selected)&&selected.length<=16,"SELECTED_SERVICES_INVALID");
  const unique=new Set<string>();const structure=parseJson(structureRaw);const available=Array.isArray(structure?.available_services)?structure.available_services:[];
  const byId=new Map(available.map((x:any)=>[String(x?.id??""),x]));
  const normalized=selected.map(s=>{assert(!!s.id&&!unique.has(s.id),"SELECTED_SERVICE_DUPLICATE");unique.add(s.id);assert(Number.isInteger(s.quantity)&&s.quantity>=1,"SELECTED_SERVICE_QUANTITY_INVALID");const a:any=byId.get(s.id);assert(!!a,"SELECTED_SERVICE_NOT_AVAILABLE");const max=Number(a.maximum_quantity??1);assert(s.quantity<=max,"SELECTED_SERVICE_QUANTITY_EXCEEDS_MAX");return {id:s.id,quantity:s.quantity};});
  return normalized.sort((a,b)=>a.id.localeCompare(b.id));
}

export async function enqueueCheckoutReprice(db:D1Database,input:{provider_id:string;provider_offer_id:string;payment_profile_id:string;selected_services:SelectedService[]},nowIso:string){
  const access=await db.prepare("SELECT terms_snapshot_at,kill_switch_state,connector_state,supported_verification_json FROM provider_access_registry WHERE provider_id=?").bind(input.provider_id).first<any>();
  assert(!!access&&access.kill_switch_state==="CLEAR"&&access.connector_state==="IMPLEMENTED"&&currentTerms(access.terms_snapshot_at),"PROVIDER_ACCESS_NOT_READY");
  let caps:string[]=[];try{caps=JSON.parse(access.supported_verification_json??"[]")}catch{}assert(caps.includes("CHECKOUT_REPRICE"),"CHECKOUT_REPRICE_NOT_ALLOWED");
  const offer=await db.prepare("SELECT provider,query_fingerprint,expires_at,offer_structure_json FROM offer_snapshots WHERE provider_offer_id=?").bind(input.provider_offer_id).first<any>();
  assert(!!offer&&offer.provider===input.provider_id,"CHECKOUT_OFFER_NOT_FOUND");assert(!offer.expires_at||Date.parse(offer.expires_at)>Date.parse(nowIso),"CHECKOUT_OFFER_EXPIRED");
  const profile=await db.prepare("SELECT provider_id,payment_method_class,credential_binding,enabled,expires_at FROM runtime_payment_profiles WHERE payment_profile_id=?").bind(input.payment_profile_id).first<any>();
  assert(!!profile&&profile.provider_id===input.provider_id&&profile.enabled===1&&Date.parse(profile.expires_at)>Date.parse(nowIso),"PAYMENT_PROFILE_NOT_READY");
  const services=validateServices(offer.offer_structure_json,input.selected_services);
  const identity={provider_offer_id:input.provider_offer_id,payment_profile_id:input.payment_profile_id,selected_services:services};const fp=await sha256Hex(stable(identity));const jobId=`checkout:${input.provider_id}:${fp}`;
  const payload={provider_id:input.provider_id,provider_offer_id:input.provider_offer_id,query_fingerprint:offer.query_fingerprint,payment_profile_id:input.payment_profile_id,payment_method_class:profile.payment_method_class,credential_binding:profile.credential_binding,selected_services:services};
  await db.prepare("INSERT OR IGNORE INTO verification_jobs(job_id,job_type,target_class,source_id,payload_json,state,available_at,created_at,provider_id,query_fingerprint,provider_mode) VALUES(?,'CHECKOUT_REPRICE','PROVIDER_API',NULL,?,'PENDING',?,?,?,?, 'USER_REQUEST')")
    .bind(jobId,JSON.stringify(payload),nowIso,nowIso,input.provider_id,offer.query_fingerprint).run();
  return {job_id:jobId,query_fingerprint:offer.query_fingerprint,selected_services:services};
}

export interface PricingQuoteInput {quote_id:string;provider_offer_id:string;provider_id:string;source_job_id?:string|null;payment_profile_id:string;selected_services:SelectedService[];payment_method_class:"CARD";currency:string;fare_and_services_total:number;surcharge_total:number;grand_total:number;priced_at:string;expires_at?:string|null;raw_sha256:string;price_scope:"CHECKOUT_TOTAL_WITH_SELECTED_SERVICES_AND_PAYMENT_SURCHARGE";}
export async function ingestPricingQuote(db:D1Database,q:PricingQuoteInput){
  assert(!!q.quote_id&&!!q.provider_offer_id&&!!q.provider_id,"PRICING_QUOTE_IDENTITY_REQUIRED");assert(/^[a-f0-9]{64}$/i.test(q.raw_sha256),"PRICING_QUOTE_HASH_INVALID");assert(Number.isFinite(Date.parse(q.priced_at)),"PRICING_QUOTE_TIME_INVALID");
  for(const v of [q.fare_and_services_total,q.surcharge_total,q.grand_total])assert(Number.isFinite(v)&&v>=0,"PRICING_QUOTE_AMOUNT_INVALID");
  assert(Math.abs((q.fare_and_services_total+q.surcharge_total)-q.grand_total)<0.02,"PRICING_QUOTE_TOTAL_MISMATCH");assert(q.price_scope==="CHECKOUT_TOTAL_WITH_SELECTED_SERVICES_AND_PAYMENT_SURCHARGE","PRICING_SCOPE_INVALID");
  const offer=await db.prepare("SELECT provider,offer_structure_json FROM offer_snapshots WHERE provider_offer_id=?").bind(q.provider_offer_id).first<any>();assert(!!offer&&offer.provider===q.provider_id,"PRICING_OFFER_NOT_FOUND");
  const profile=await db.prepare("SELECT provider_id,payment_method_class FROM runtime_payment_profiles WHERE payment_profile_id=?").bind(q.payment_profile_id).first<any>();assert(!!profile&&profile.provider_id===q.provider_id&&profile.payment_method_class===q.payment_method_class,"PRICING_PROFILE_MISMATCH");
  const services=validateServices(offer.offer_structure_json,q.selected_services);const servicesJson=JSON.stringify(services);
  const prior=await db.prepare("SELECT raw_sha256 FROM provider_pricing_quotes WHERE quote_id=?").bind(q.quote_id).first<any>();if(prior){if(prior.raw_sha256!==q.raw_sha256)throw new Error("PRICING_QUOTE_ID_CONFLICT");await db.prepare("INSERT OR IGNORE INTO domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) VALUES('PRICING_QUOTE',?,?,'PENDING',0,?)").bind(q.quote_id,JSON.stringify({quote_id:q.quote_id}),q.priced_at).run();return {quote_id:q.quote_id,idempotent:true};}
  await db.batch([
    db.prepare(`INSERT INTO provider_pricing_quotes(quote_id,provider_offer_id,provider_id,source_job_id,payment_profile_id,selected_services_json,payment_method_class,currency,fare_and_services_total,surcharge_total,grand_total,priced_at,expires_at,raw_sha256,price_scope)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).bind(q.quote_id,q.provider_offer_id,q.provider_id,q.source_job_id??null,q.payment_profile_id,servicesJson,q.payment_method_class,q.currency,q.fare_and_services_total,q.surcharge_total,q.grand_total,q.priced_at,q.expires_at??null,q.raw_sha256,q.price_scope),
    db.prepare("INSERT OR IGNORE INTO domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) VALUES('PRICING_QUOTE',?,?,'PENDING',0,?)").bind(q.quote_id,JSON.stringify({quote_id:q.quote_id}),q.priced_at)
  ]);
  return {quote_id:q.quote_id,idempotent:false};
}

export async function applyPricingQuoteEvidence(db:D1Database,quoteId:string,nowIso:string){
  const q=await db.prepare("SELECT quote_id,provider_offer_id,currency,grand_total,priced_at,expires_at,price_scope FROM provider_pricing_quotes WHERE quote_id=?").bind(quoteId).first<any>();assert(!!q,"PRICING_QUOTE_NOT_FOUND");assert(q.price_scope==="CHECKOUT_TOTAL_WITH_SELECTED_SERVICES_AND_PAYMENT_SURCHARGE","PRICING_SCOPE_INVALID");
  const rows=(await db.prepare("SELECT DISTINCT itinerary_id FROM cost_components WHERE source_offer_id=?").bind(q.provider_offer_id).all<{itinerary_id:string}>()).results;let updated=0;
  for(const r of rows){const twd=q.currency==="TWD"?Number(q.grand_total):null;await db.batch([
      db.prepare("UPDATE cost_components SET type='CHECKOUT_TOTAL',amount=?,currency=?,twd_amount=?,inclusion_state='INCLUDED_IN_OFFER',certainty='CHECKOUT_REPRICE',pricing_quote_id=?,observed_at=? WHERE itinerary_id=? AND source_offer_id=? AND dedupe_key='offer-total'").bind(q.grand_total,q.currency,twd,q.quote_id,q.priced_at,r.itinerary_id,q.provider_offer_id),
      db.prepare("INSERT INTO readiness_facets(itinerary_id,facet_type,status,reason_code,observed_at,expires_at,authority,evidence_id) VALUES(?,'COST_COMPLETE','FAIL','FLIGHT_CHECKOUT_PRICED_OTHER_COSTS_PENDING',?,?, 'PROVIDER_CHECKOUT_QUOTE',?) ON CONFLICT(itinerary_id,facet_type) DO UPDATE SET status=excluded.status,reason_code=excluded.reason_code,observed_at=excluded.observed_at,expires_at=excluded.expires_at,authority=excluded.authority,evidence_id=excluded.evidence_id").bind(r.itinerary_id,nowIso,q.expires_at??new Date(Date.parse(nowIso)+15*60000).toISOString(),`pricing:${q.quote_id}`)
    ]);updated++;}
  return {quote_id:quoteId,itineraries_updated:updated};
}
