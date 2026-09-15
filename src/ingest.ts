import type { D1Database } from "./types.js";
import { promotionFingerprint } from "./source.js";
import { claimDomainEvents, ackDomainEvent } from "./outbox.js";

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
    db.prepare("INSERT OR IGNORE INTO source_observations(observation_id,source_id,observed_at,canonical_url,content_sha256,parser_version,access_basis,privacy_class) VALUES(?,?,?,?,?,?,?,?)").bind(input.observation_id,input.source_id,input.observed_at,input.canonical_url,input.content_sha256,input.parser_version??null,src.access_basis,input.privacy_class),
    db.prepare("INSERT OR IGNORE INTO domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) VALUES('SOURCE_OBSERVED',?,?,'PENDING',0,?)").bind(input.observation_id,JSON.stringify({observation_id:input.observation_id}),nowIso)
  ];
  if(extractionJson&&input.extraction_type)statements.splice(1,0,db.prepare("INSERT OR IGNORE INTO source_extractions(extraction_id,observation_id,extraction_type,payload_json,created_at) VALUES(?,?,?,?,?)").bind(`${input.observation_id}:${input.extraction_type}`,input.observation_id,input.extraction_type,extractionJson,nowIso));
  await db.batch(statements); return {observation_id:input.observation_id,stored_extraction:!!extractionJson};
}

function eventIdFromFingerprint(fp:string){let h=2166136261;for(const c of fp){h^=c.charCodeAt(0);h=Math.imul(h,16777619)}return `promo-${(h>>>0).toString(16).padStart(8,'0')}`}
export async function projectDomainEvents(db:D1Database,nowIso:string,workerId="cron",limit=2){
  const events=await claimDomainEvents(db,nowIso,workerId,limit,60); let done=0;
  for(const e of events as any[]){
    try{
      if(e.event_type!=="SOURCE_OBSERVED"){await ackDomainEvent(db,{id:Number(e.id),ok:true},nowIso);done++;continue}
      const obs=await db.prepare("SELECT observation_id,source_id,observed_at FROM source_observations WHERE observation_id=?").bind(e.entity_id).first<any>();
      if(!obs)throw new Error("OBSERVATION_MISSING");
      const ex=(await db.prepare("SELECT extraction_type,payload_json FROM source_extractions WHERE observation_id=? ORDER BY created_at").bind(e.entity_id).all<any>()).results;
      for(const x of ex){
        const p=JSON.parse(x.payload_json);
        if(x.extraction_type==="PROMOTION_SIGNAL"){
          const fp=promotionFingerprint({market:p.market??"UNKNOWN",airline:p.airline,routes:p.routes??[],sale_start:p.sale_start,travel_start:p.travel_start,promo_code:p.promo_code}); const id=eventIdFromFingerprint(fp);
          await db.batch([
            db.prepare("INSERT INTO promotion_events(event_id,fingerprint,state,market,airline,routes_json,prices_json,promo_code,observed_at,updated_at) VALUES(?,?,'DISCOVERED',?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET updated_at=excluded.updated_at").bind(id,fp,p.market??null,p.airline??null,JSON.stringify(p.routes??[]),JSON.stringify(p.prices??[]),p.promo_code??null,obs.observed_at,nowIso),
            db.prepare("INSERT OR IGNORE INTO promotion_event_evidence(event_id,observation_id) VALUES(?,?)").bind(id,e.entity_id)
          ]);
        } else if(x.extraction_type==="ROUTE_UNIVERSE"){
          for(const route of p.routes??[]){const [origin,destination]=String(route).split('-');if(origin&&destination)await db.prepare("INSERT OR IGNORE INTO route_universe(route_key,origin,destination,state,source_observation_id,observed_at) VALUES(?,?,?,'DISCOVERED',?,?)").bind(`${origin}-${destination}`,origin,destination,e.entity_id,obs.observed_at).run();}
        }
      }
      await ackDomainEvent(db,{id:Number(e.id),ok:true},nowIso);done++;
    }catch(err){await ackDomainEvent(db,{id:Number((e as any).id),ok:false,error:err instanceof Error?err.message:String(err)},nowIso)}
  }
  return {claimed:events.length,done};
}
