import type { D1Database } from "./types.js";
import { promotionFingerprint, extractPromotionText } from "./source.js";
import { claimDomainEvents, ackDomainEvent } from "./outbox.js";
import { enqueueCandidateSignal } from "./priority.js";

function validSha(x:string){return /^[a-f0-9]{64}$/i.test(x)}
export async function ingestSourceObservation(db:D1Database,input:{observation_id:string;source_id:string;observed_at:string;canonical_url:string;content_sha256:string;parser_version?:string|null;privacy_class:"PUBLIC"|"PARTNER_STRUCTURED"|"PRIVATE_NOTIFICATION";extraction_type?:"PROMOTION_SIGNAL"|"ROUTE_UNIVERSE";structured_payload?:unknown},nowIso:string){
  if(!input.observation_id||!input.source_id||!validSha(input.content_sha256)||!input.canonical_url.startsWith("https://"))throw new Error("OBSERVATION_INVALID");
  if(!Number.isFinite(Date.parse(input.observed_at)))throw new Error("OBSERVED_AT_INVALID");
  const src=await db.prepare("SELECT access_basis,lifecycle_state FROM source_registry WHERE source_id=?").bind(input.source_id).first<{access_basis:string;lifecycle_state:string}>();
  if(!src||src.lifecycle_state==="DISABLED")throw new Error("SOURCE_NOT_ALLOWED");
  let extractionJson:string|null=null;
  if(input.structured_payload!==undefined){
    if(input.privacy_class==="PRIVATE_NOTIFICATION")throw new Error("PRIVATE_STRUCTURED_PAYLOAD_FORBIDDEN");
    extractionJson=JSON.stringify(input.structured_payload); if(extractionJson.length>65536)throw new Error("EXTRACTION_TOO_LARGE");
  }
  const statements=[
    db.prepare("INSERT OR IGNORE INTO source_observations(observation_id,source_id,observed_at,canonical_url,content_sha256,parser_version,access_basis,privacy_class,access_basis_snapshot,retention_until,content_version) VALUES(?,?,?,?,?,?,?,?,?,?,1)").bind(input.observation_id,input.source_id,input.observed_at,input.canonical_url,input.content_sha256,input.parser_version??null,src.access_basis,input.privacy_class,src.access_basis,new Date(Date.parse(input.observed_at)+90*86400000).toISOString()),
    db.prepare("INSERT OR IGNORE INTO domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) VALUES('SOURCE_OBSERVED',?,?,'PENDING',0,?)").bind(input.observation_id,JSON.stringify({observation_id:input.observation_id}),nowIso)
  ];
  if(extractionJson&&input.extraction_type)statements.splice(1,0,db.prepare("INSERT OR IGNORE INTO source_extractions(extraction_id,observation_id,extraction_type,payload_json,created_at) VALUES(?,?,?,?,?)").bind(`${input.observation_id}:${input.extraction_type}`,input.observation_id,input.extraction_type,extractionJson,nowIso));
  await db.batch(statements); return {observation_id:input.observation_id,stored_extraction:!!extractionJson};
}

function eventIdFromFingerprint(fp:string){let h=2166136261;for(const c of fp){h^=c.charCodeAt(0);h=Math.imul(h,16777619)}return `promo-${(h>>>0).toString(16).padStart(8,'0')}`}
async function projectPromotionSignal(db:D1Database,obs:{observation_id:string;observed_at:string},p:any,nowIso:string){
  const fp=promotionFingerprint({market:p.market??"UNKNOWN",airline:p.airline,routes:p.routes??[],sale_start:p.sale_start,travel_start:p.travel_start,promo_code:p.promo_code}); const id=eventIdFromFingerprint(fp);
  await db.batch([
    db.prepare("INSERT INTO promotion_events(event_id,fingerprint,state,market,airline,routes_json,prices_json,promo_code,observed_at,updated_at,promotion_type,carrier_or_seller,route_scope,sale_window,travel_window,price_claim,currency,member_requirement,channel_requirement,first_observed_at,last_observed_at,cluster_fingerprint,primary_evidence_id) VALUES(?,?,'DISCOVERED',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET updated_at=excluded.updated_at,last_observed_at=excluded.last_observed_at").bind(id,fp,p.market??null,p.airline??null,JSON.stringify(p.routes??[]),JSON.stringify(p.prices??[]),p.promo_code??null,obs.observed_at,nowIso,p.promotion_type??'FARE_PROMOTION',p.airline??p.seller??null,JSON.stringify(p.routes??[]),JSON.stringify({start:p.sale_start??null,end:p.sale_end??null}),JSON.stringify({start:p.travel_start??null,end:p.travel_end??null}),JSON.stringify(p.prices??[]),(p.prices??[])[0]?.currency??null,p.member_requirement??null,p.channel_requirement??null,obs.observed_at,obs.observed_at,fp,obs.observation_id),
    db.prepare("INSERT OR IGNORE INTO promotion_event_evidence(event_id,observation_id) VALUES(?,?)").bind(id,obs.observation_id)
  ]);
  await enqueueCandidateSignal(db,{signal_type:"PROMOTION",signal_id:id,required_verification:"LIVE_REPRICE",priority_score:(p.prices??[]).length?70:50,route_scope:p.routes??[],price_claim:p.prices??[],source_evidence_id:obs.observation_id,observed_at:obs.observed_at},nowIso);
  return id;
}
async function projectRouteSignal(db:D1Database,obs:{observation_id:string;observed_at:string},p:any){
  for(const route of p.routes??[]){const [origin,destination]=String(route).split('-');if(origin&&destination){const routeId=`${origin}-${destination}:${p.carrier_alias_id??'ANY'}:${p.service_type??'SCHEDULED'}`;await db.batch([db.prepare("INSERT OR IGNORE INTO route_universe(route_key,origin,destination,state,source_observation_id,observed_at) VALUES(?,?,?,'DISCOVERED',?,?)").bind(`${origin}-${destination}`,origin,destination,obs.observation_id,obs.observed_at),db.prepare("INSERT INTO route_universe_entries(route_id,origin_airport,destination_airport,carrier_alias_id,service_type,first_seen_at,last_seen_at,status,official_evidence_id) VALUES(?,?,?,?,?,?,?,'DISCOVERED',?) ON CONFLICT(route_id) DO UPDATE SET last_seen_at=excluded.last_seen_at,status=excluded.status,official_evidence_id=excluded.official_evidence_id").bind(routeId,origin,destination,p.carrier_alias_id??null,p.service_type??'SCHEDULED',obs.observed_at,obs.observed_at,obs.observation_id)]);}}
}
export async function projectDomainEvents(db:D1Database,nowIso:string,workerId="cron",limit=2){
  const events=await claimDomainEvents(db,nowIso,workerId,limit,60); let done=0;
  for(const e of events as any[]){
    try{
      if(e.event_type==="SOURCE_OBSERVED"){
        const obs=await db.prepare("SELECT observation_id,source_id,observed_at FROM source_observations WHERE observation_id=?").bind(e.entity_id).first<any>(); if(!obs)throw new Error("OBSERVATION_MISSING");
        const ex=(await db.prepare("SELECT extraction_type,payload_json FROM source_extractions WHERE observation_id=? ORDER BY created_at").bind(e.entity_id).all<any>()).results;
        for(const x of ex){const p=JSON.parse(x.payload_json); if(x.extraction_type==="PROMOTION_SIGNAL")await projectPromotionSignal(db,obs,p,nowIso); else if(x.extraction_type==="ROUTE_UNIVERSE")await projectRouteSignal(db,obs,p);}
      } else if(e.event_type==="EMAIL_EVIDENCE"){
        const mail=await db.prepare("SELECT e.observation_id,e.subject,e.trust_class,s.market,o.observed_at FROM email_evidence e JOIN source_registry s ON s.source_id=e.source_id JOIN source_observations o ON o.observation_id=e.observation_id WHERE e.message_id=?").bind(e.entity_id).first<any>();
        if(!mail)throw new Error("EMAIL_EVIDENCE_MISSING");
        if(mail.trust_class==="TRUSTED"){const signal=extractPromotionText(mail.subject,mail.market??"TW"); if(signal)await projectPromotionSignal(db,{observation_id:mail.observation_id,observed_at:mail.observed_at},signal,nowIso);}
      } else if(e.event_type==="AGENCY_OFFER"){
        const a=await db.prepare("SELECT agency_offer_id,origin,destination,price,currency,source_evidence_id,observed_at,seller_verification_state,state FROM agency_inventory_offers WHERE agency_offer_id=?").bind(e.entity_id).first<any>();
        if(!a)throw new Error("AGENCY_OFFER_MISSING");
        const priority=(a.seller_verification_state==="VERIFIED"||a.state==="SELLER_CONFIRMED"||a.state==="CHECKOUT_REPRODUCED")?90:75;
        await enqueueCandidateSignal(db,{signal_type:"AGENCY_CLEARANCE",signal_id:a.agency_offer_id,required_verification:"SELLER_RECHECK",priority_score:priority,route_scope:[`${a.origin}-${a.destination}`],price_claim:[{currency:a.currency,amount:a.price}],source_evidence_id:a.source_evidence_id,observed_at:a.observed_at},nowIso);
      }
      await ackDomainEvent(db,{id:Number(e.id),ok:true},nowIso);done++;
    }catch(err){await ackDomainEvent(db,{id:Number((e as any).id),ok:false,error:err instanceof Error?err.message:String(err)},nowIso)}
  }
  return {claimed:events.length,done};
}
