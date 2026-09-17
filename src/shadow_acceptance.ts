import type { D1Database } from "./types.js";

const SUBJECT_TYPES=new Set(["ITINERARY","PROMOTION","AGENCY_OFFER","SOURCE_EVENT","EMAIL","ROUTE"]);
const COMPLEX_STRATEGIES=new Set(["S09","S11","S12","S14","S15"]);
const LABELS=new Set([
  "TRUE_DEAL","NORMAL","GHOST","EXPIRED","BAG_ERASED_SAVINGS","GROUND_ERASED_SAVINGS","SELF_TRANSFER_NOT_WORTH_IT","DOCUMENT_BLOCKED",
  "FOUR_LEG_WORTH_IT","FOUR_LEG_POSITIONING_ERASED_SAVINGS","AMADEUS_LCC_MISS","BEAT_WINDOW_MISS","TAX_EXEMPT_MISS","COST_DEDUP_MISS",
  "POLICY_STALE_MISS","PROTECTION_CLASS_MISS","PROMO_NOT_BOOKABLE","AGENCY_CLEARANCE_TRUE","AGENCY_CLEARANCE_GHOST","AGENCY_SELLER_UNVERIFIED",
  "EMAIL_AUTH_FAIL","EMAIL_LINK_RISK","SOURCE_DUPLICATE_HEAVY","SOURCE_FIRST_WIN","SOURCE_LATE_REPOST","SOURCE_ACCESS_STALE","SOURCE_DELETION_OBSERVED",
  "CACHED_FARE_REPRICE_MISS","ROUTE_UNIVERSE_NEW_SIGNAL"
]);
const enc=new TextEncoder();
async function sha256Hex(text:string){const h=await crypto.subtle.digest("SHA-256",enc.encode(text));return [...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,"0")).join("");}
function validCommit(v:string|undefined){return !!v&&/^[a-f0-9]{40}$/i.test(v);}
function bool(v:unknown){return typeof v==="boolean";}
function validIso(v:unknown){return typeof v==="string"&&Number.isFinite(Date.parse(v));}
export function requireShadowCommit(v:string|undefined){if(!validCommit(v))throw new Error("RUNTIME_COMMIT_UNAVAILABLE");return v!;}

export interface ShadowReviewInput {sample_id:string;subject_id:string;subject_type:string;observed_at:string;label:string;complex:boolean;source_discovery:boolean;agency_clearance:boolean;false_actionable:boolean;safety_error_code:string|null;evidence_id:string;}
interface CanonicalSubject {observed_at:string;strategy_type:string|null;}
async function canonicalSubject(db:D1Database,r:ShadowReviewInput):Promise<CanonicalSubject>{
  if(r.subject_type==="ITINERARY"){
    const row=await db.prepare("SELECT p.observed_at,i.strategy_type FROM candidate_plan_intakes p JOIN itinerary_candidates i ON i.itinerary_id=p.itinerary_id WHERE p.intake_id=? AND p.itinerary_id=?").bind(r.evidence_id,r.subject_id).first<any>();
    if(!row)throw new Error("SHADOW_CANONICAL_EVIDENCE_MISMATCH");return {observed_at:row.observed_at,strategy_type:row.strategy_type??null};
  }
  if(r.subject_type==="PROMOTION"){
    const row=await db.prepare("SELECT o.observed_at FROM promotion_event_evidence pe JOIN source_observations o ON o.observation_id=pe.observation_id WHERE pe.event_id=? AND pe.observation_id=?").bind(r.subject_id,r.evidence_id).first<any>();
    if(!row)throw new Error("SHADOW_CANONICAL_EVIDENCE_MISMATCH");return {observed_at:row.observed_at,strategy_type:null};
  }
  if(r.subject_type==="AGENCY_OFFER"){
    const row=await db.prepare("SELECT o.observed_at FROM agency_inventory_offers a JOIN source_observations o ON o.observation_id=a.source_evidence_id WHERE a.agency_offer_id=? AND a.source_evidence_id=?").bind(r.subject_id,r.evidence_id).first<any>();
    if(!row)throw new Error("SHADOW_CANONICAL_EVIDENCE_MISMATCH");return {observed_at:row.observed_at,strategy_type:null};
  }
  if(r.subject_type==="SOURCE_EVENT"){
    const row=await db.prepare("SELECT observed_at FROM source_observations WHERE observation_id=?").bind(r.subject_id).first<any>();
    if(!row||r.evidence_id!==r.subject_id)throw new Error("SHADOW_CANONICAL_EVIDENCE_MISMATCH");return {observed_at:row.observed_at,strategy_type:null};
  }
  if(r.subject_type==="EMAIL"){
    const row=await db.prepare("SELECT o.observed_at,e.observation_id FROM email_evidence e JOIN source_observations o ON o.observation_id=e.observation_id WHERE e.message_id=?").bind(r.subject_id).first<any>();
    if(!row||row.observation_id!==r.evidence_id)throw new Error("SHADOW_CANONICAL_EVIDENCE_MISMATCH");return {observed_at:row.observed_at,strategy_type:null};
  }
  if(r.subject_type==="ROUTE"){
    const row=await db.prepare("SELECT o.observed_at,r.official_evidence_id FROM route_universe_entries r JOIN source_observations o ON o.observation_id=r.official_evidence_id WHERE r.route_id=?").bind(r.subject_id).first<any>();
    if(!row||row.official_evidence_id!==r.evidence_id)throw new Error("SHADOW_CANONICAL_EVIDENCE_MISMATCH");return {observed_at:row.observed_at,strategy_type:null};
  }
  throw new Error("SHADOW_REVIEW_SUBJECT_TYPE_INVALID");
}
function validateFlags(r:ShadowReviewInput,strategy:string|null){
  if(!SUBJECT_TYPES.has(r.subject_type)||!LABELS.has(r.label)||!bool(r.complex)||!bool(r.source_discovery)||!bool(r.agency_clearance)||!bool(r.false_actionable)||!validIso(r.observed_at)||!r.sample_id||!r.subject_id||!r.evidence_id)throw new Error("SHADOW_REVIEW_INVALID");
  if(r.safety_error_code!==null&&(typeof r.safety_error_code!=="string"||!r.safety_error_code.trim()))throw new Error("SHADOW_REVIEW_INVALID");
  const derivedComplex=r.subject_type==="ITINERARY"&&!!strategy&&COMPLEX_STRATEGIES.has(strategy);
  if(r.complex!==derivedComplex)throw new Error("SHADOW_COMPLEX_FLAG_MISMATCH");
  if(r.source_discovery&&r.subject_type!=="SOURCE_EVENT"&&r.subject_type!=="ROUTE")throw new Error("SHADOW_SOURCE_DISCOVERY_FLAG_MISMATCH");
  if(r.agency_clearance&&r.subject_type!=="AGENCY_OFFER")throw new Error("SHADOW_AGENCY_CLEARANCE_FLAG_MISMATCH");
}
export async function writeShadowReview(db:D1Database,r:ShadowReviewInput,ctx:{reviewer_key_id:string;runtime_commit:string},nowIso:string){
  const canonical=await canonicalSubject(db,r);validateFlags(r,canonical.strategy_type);
  if(r.observed_at!==canonical.observed_at)throw new Error("SHADOW_OBSERVED_AT_MISMATCH");
  const normalized={sample_id:r.sample_id,subject_id:r.subject_id,subject_type:r.subject_type,observed_at:canonical.observed_at,label:r.label,complex:r.complex,source_discovery:r.source_discovery,agency_clearance:r.agency_clearance,false_actionable:r.false_actionable,safety_error_code:r.safety_error_code,evidence_id:r.evidence_id,strategy_type:canonical.strategy_type,reviewer_key_id:ctx.reviewer_key_id,commit_sha:ctx.runtime_commit};
  const hash=await sha256Hex(JSON.stringify(normalized));
  const prior=await db.prepare("SELECT review_payload_sha256 FROM shadow_review_samples WHERE sample_id=?").bind(r.sample_id).first<any>();
  if(prior){if(prior.review_payload_sha256!==hash)throw new Error("SHADOW_REVIEW_IDEMPOTENCY_CONFLICT");return {sample_id:r.sample_id,idempotent:true,review_payload_sha256:hash};}
  const unit=await db.prepare("SELECT sample_id FROM shadow_review_samples WHERE subject_type=? AND subject_id=? AND evidence_id=?").bind(r.subject_type,r.subject_id,r.evidence_id).first<any>();
  if(unit)throw new Error("SHADOW_REVIEW_UNIT_CONFLICT");
  await db.prepare("INSERT INTO shadow_review_samples(sample_id,subject_type,subject_id,evidence_id,observed_at,label,complex,source_discovery,agency_clearance,false_actionable,safety_error_code,strategy_type,reviewer_key_id,review_payload_sha256,commit_sha,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    .bind(r.sample_id,r.subject_type,r.subject_id,r.evidence_id,canonical.observed_at,r.label,r.complex?1:0,r.source_discovery?1:0,r.agency_clearance?1:0,r.false_actionable?1:0,r.safety_error_code,canonical.strategy_type,ctx.reviewer_key_id,hash,ctx.runtime_commit,nowIso).run();
  return {sample_id:r.sample_id,idempotent:false,review_payload_sha256:hash};
}
export async function readShadowReview(db:D1Database,sampleId:string){if(!sampleId)throw new Error("SHADOW_REVIEW_READBACK_INVALID");return db.prepare("SELECT * FROM shadow_review_samples WHERE sample_id=?").bind(sampleId).first<any>();}

export async function recordShadowRuntimeDay(db:D1Database,runtimeCommit:string|undefined,deploymentMode:string,nowIso:string){
  if(deploymentMode!=="SHADOW_ACCEPTANCE"||!validCommit(runtimeCommit)||!validIso(nowIso))return {recorded:false};
  const day=nowIso.slice(0,10);await db.prepare("INSERT OR IGNORE INTO shadow_runtime_days(commit_sha,runtime_date,deployment_mode,observed_at) VALUES(?,?,'SHADOW_ACCEPTANCE',?)").bind(runtimeCommit,day,nowIso).run();return {recorded:true,runtime_date:day};
}
export async function shadowAcceptanceReadback(db:D1Database,runtimeCommit:string,deploymentMode:string){
  const days=await db.prepare("SELECT COUNT(*) n FROM shadow_runtime_days WHERE commit_sha=? AND deployment_mode='SHADOW_ACCEPTANCE'").bind(runtimeCommit).first<any>();
  const rows=(await db.prepare("SELECT subject_type,complex,source_discovery,agency_clearance,false_actionable,safety_error_code,strategy_type FROM shadow_review_samples WHERE commit_sha=?").bind(runtimeCommit).all<any>()).results??[];
  const candidates=rows.filter((r:any)=>r.subject_type==="ITINERARY").length;
  const complexRows=rows.filter((r:any)=>r.subject_type==="ITINERARY"&&r.complex===1);
  const coverage=[...new Set(complexRows.map((r:any)=>r.strategy_type).filter((x:any)=>COMPLEX_STRATEGIES.has(x)))].sort();
  const missing=[...COMPLEX_STRATEGIES].filter(x=>!coverage.includes(x)).sort();
  const sourceDiscovery=rows.filter((r:any)=>r.source_discovery===1).length;
  const agency=rows.filter((r:any)=>r.agency_clearance===1).length;
  const falseComplex=complexRows.filter((r:any)=>r.false_actionable===1).length;
  const safety=rows.filter((r:any)=>typeof r.safety_error_code==="string"&&r.safety_error_code.length>0).length;
  const shadowDays=Number(days?.n??0);
  const pass=deploymentMode==="SHADOW_ACCEPTANCE"&&shadowDays>=14&&candidates>=150&&complexRows.length>=30&&sourceDiscovery>=30&&agency>=10&&missing.length===0&&falseComplex===0&&safety===0;
  return {pass,commit_sha:runtimeCommit,deployment_mode:deploymentMode,shadow_days:shadowDays,labeled_candidates:candidates,labeled_complex_candidates:complexRows.length,labeled_source_discovery_events:sourceDiscovery,labeled_agency_clearance_events:agency,complex_strategy_coverage:coverage,complex_strategy_missing:missing,false_actionable_complex:falseComplex,safety_critical_errors:safety,total_reviews:rows.length};
}
