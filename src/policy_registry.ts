import type { D1Database, ReadinessFacetInput } from "./types.js";
import { policyUsable } from "./policy.js";

export type PolicyDecision = "CLEAR"|"REQUIRES_DOCUMENT"|"BLOCKED"|"RECHECK_REQUIRED";
export interface PolicyRecordInput {
  policy_record_id:string; policy_code:string; jurisdiction:string; traveler_document_class:string;
  announced_at?:string|null; observed_at:string; effective_from?:string|null; effective_to?:string|null;
  jurisdiction_timezone:string; travel_event:string; ticket_issue_rule?:string|null; source_url:string;
  source_authority:string; source_snapshot_hash:string; refresh_margin_hours:number; ttl_hours:number;
  watch_window_hours?:number|null; decision_status:PolicyDecision; status:"CURRENT"|"RECHECK_REQUIRED"|"STALE";
}
export type EventSelector = "FIRST_DEPARTURE"|"FIRST_ARRIVAL"|"FINAL_DEPARTURE"|"FINAL_ARRIVAL";
export interface PolicyRequirementBinding { document_id:string; policy_code:string; event_selector:EventSelector; }

function assert(c:boolean,m:string):asserts c{if(!c)throw new Error(m);}
function validIso(v:string|null|undefined){return !!v&&Number.isFinite(Date.parse(v));}
async function sha256Hex(text:string){const b=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,"0")).join("");}
function eventFromSegments(segments:any[],selector:EventSelector){
  assert(segments.length>0,"TICKET_SEGMENTS_REQUIRED");
  const first=segments[0],last=segments[segments.length-1];
  const v=selector==="FIRST_DEPARTURE"?first.departing_at:selector==="FIRST_ARRIVAL"?first.arriving_at:selector==="FINAL_DEPARTURE"?last.departing_at:last.arriving_at;
  assert(validIso(v),"TRAVEL_EVENT_TIME_INVALID"); return String(v);
}
function policyExpiry(p:any){
  const ttl=new Date(Date.parse(p.observed_at)+Number(p.ttl_hours)*3600000).toISOString();
  if(validIso(p.effective_to)&&Date.parse(p.effective_to)<Date.parse(ttl))return new Date(Date.parse(p.effective_to)-1).toISOString();
  return ttl;
}
export async function ingestPolicyRecord(db:D1Database,p:PolicyRecordInput,nowIso=new Date().toISOString()){
  for(const k of ["policy_record_id","policy_code","jurisdiction","traveler_document_class","observed_at","jurisdiction_timezone","travel_event","source_url","source_authority","source_snapshot_hash"] as const)assert(typeof p[k]==="string"&&String(p[k]).length>0,`${String(k).toUpperCase()}_REQUIRED`);
  assert(validIso(p.observed_at),"POLICY_OBSERVED_AT_INVALID"); assert(p.ttl_hours>0,"POLICY_TTL_INVALID");
  assert(/^[a-f0-9]{64}$/i.test(p.source_snapshot_hash),"POLICY_SNAPSHOT_HASH_INVALID");
  const existing=await db.prepare("SELECT policy_record_id,source_snapshot_hash FROM policy_records WHERE policy_record_id=?").bind(p.policy_record_id).first<any>();
  if(existing){if(existing.source_snapshot_hash!==p.source_snapshot_hash)throw new Error("POLICY_RECORD_IMMUTABLE_CONFLICT");return {inserted:false,policy_record_id:p.policy_record_id};}
  await db.prepare(`INSERT INTO policy_records(policy_record_id,policy_code,jurisdiction,traveler_document_class,announced_at,observed_at,effective_from,effective_to,jurisdiction_timezone,travel_event,ticket_issue_rule,source_url,source_authority,source_snapshot_hash,refresh_margin_hours,ttl_hours,watch_window_hours,decision_status,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).bind(p.policy_record_id,p.policy_code,p.jurisdiction,p.traveler_document_class,p.announced_at??null,p.observed_at,p.effective_from??null,p.effective_to??null,p.jurisdiction_timezone,p.travel_event,p.ticket_issue_rule??null,p.source_url,p.source_authority,p.source_snapshot_hash,p.refresh_margin_hours,p.ttl_hours,p.watch_window_hours??null,p.decision_status,p.status,nowIso).run();
  return {inserted:true,policy_record_id:p.policy_record_id,content_fingerprint:await sha256Hex(JSON.stringify(p))};
}

export async function enrichItineraryPolicy(db:D1Database,input:{itinerary_id:string;traveler_document_class:string;requirements:PolicyRequirementBinding[]},nowIso=new Date().toISOString()){
  assert(input.requirements.length>0&&input.requirements.length<=8,"POLICY_REQUIREMENT_COUNT_INVALID");
  const tickets=(await db.prepare("SELECT segments_json FROM ticket_components WHERE itinerary_id=? ORDER BY ticket_id").bind(input.itinerary_id).all<any>()).results;
  assert(tickets.length>0,"ITINERARY_TICKETS_NOT_FOUND"); const segments=tickets.flatMap(t=>JSON.parse(t.segments_json));
  let allFresh=true,allClear=true,blocked=false; const docs:any[]=[]; const evidenceIds:string[]=[]; const expiries:string[]=[];
  for(const r of input.requirements){
    const eventAt=eventFromSegments(segments,r.event_selector);
    const p=await db.prepare(`SELECT * FROM policy_records WHERE policy_code=? AND traveler_document_class=? ORDER BY observed_at DESC LIMIT 1`).bind(r.policy_code,input.traveler_document_class).first<any>();
    if(!p){allFresh=false;allClear=false;docs.push({r,eventAt,status:"RECHECK_REQUIRED",p:null});continue;}
    const fresh=policyUsable({observed_at:p.observed_at,effective_from:p.effective_from,effective_to:p.effective_to,ttl_hours:Number(p.ttl_hours),watch_window_hours:p.watch_window_hours==null?undefined:Number(p.watch_window_hours),status:p.status},eventAt,nowIso);
    const decision:PolicyDecision=fresh?p.decision_status:"RECHECK_REQUIRED"; allFresh&&=fresh; allClear&&=decision==="CLEAR"; blocked ||= decision==="BLOCKED";
    evidenceIds.push(`policy:${p.policy_record_id}`); expiries.push(policyExpiry(p)); docs.push({r,eventAt,status:decision,p});
  }
  const statements:any[]=[];
  for(const d of docs){const p=d.p;statements.push(db.prepare(`INSERT INTO document_requirements(document_id,itinerary_id,jurisdiction,travel_event,traveler_document_class,status,announced_at,observed_at,effective_from,effective_to,valid_for_event_at,jurisdiction_timezone,authority_source,source_snapshot_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET status=excluded.status,observed_at=excluded.observed_at,effective_from=excluded.effective_from,effective_to=excluded.effective_to,valid_for_event_at=excluded.valid_for_event_at,authority_source=excluded.authority_source,source_snapshot_id=excluded.source_snapshot_id`).bind(d.r.document_id,input.itinerary_id,p?.jurisdiction??"UNKNOWN",p?.travel_event??d.r.event_selector,input.traveler_document_class,d.status,p?.announced_at??null,p?.observed_at??nowIso,p?.effective_from??null,p?.effective_to??null,d.eventAt,p?.jurisdiction_timezone??"UTC",p?.source_authority??"MISSING_POLICY",p?.policy_record_id??`missing:${d.r.policy_code}`));}
  const fallback=new Date(Date.parse(nowIso)+15*60000).toISOString(); const expiry=expiries.length?new Date(Math.min(...expiries.map(Date.parse))).toISOString():fallback;
  const docStatus=blocked?"FAIL":allClear?"PASS":"UNKNOWN"; const docReason=blocked?"POLICY_BLOCKS_TRAVEL":allClear?"POLICY_DOCUMENT_REQUIREMENTS_CLEAR":"DOCUMENT_REQUIREMENT_UNRESOLVED";
  const policyStatus=allFresh?"PASS":"STALE"; const evidence=evidenceIds.join(",")||"policy:MISSING";
  const facets:ReadinessFacetInput[]=[
    {facet_type:"DOCUMENT_CLEAR",status:docStatus,reason_code:docReason,observed_at:nowIso,expires_at:expiry,authority:"POLICY_REGISTRY",evidence_id:evidence},
    {facet_type:"POLICY_FRESH",status:policyStatus,reason_code:allFresh?"EVENT_TIME_POLICY_FRESH":"POLICY_STALE_OR_MISSING",observed_at:nowIso,expires_at:expiry,authority:"POLICY_REGISTRY",evidence_id:evidence}
  ];
  for(const f of facets)statements.push(db.prepare(`INSERT INTO readiness_facets(itinerary_id,facet_type,status,reason_code,observed_at,expires_at,authority,evidence_id) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(itinerary_id,facet_type) DO UPDATE SET status=excluded.status,reason_code=excluded.reason_code,observed_at=excluded.observed_at,expires_at=excluded.expires_at,authority=excluded.authority,evidence_id=excluded.evidence_id`).bind(input.itinerary_id,f.facet_type,f.status,f.reason_code,f.observed_at,f.expires_at,f.authority,f.evidence_id));
  await db.batch(statements); return {itinerary_id:input.itinerary_id,document_status:docStatus,policy_status:policyStatus,documents:docs.length};
}
