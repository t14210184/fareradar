import type { D1Database } from "./types.js";

const PROVIDER_ACCESS_BASES=new Set(["OFFICIAL_API","PARTNER_CONTRACT","AIRLINE_DIRECT","MANUAL_ORACLE","PUBLIC_PAGE_MONITOR"]);
const SHA256=/^[a-f0-9]{64}$/i;
const COMMIT=/^[a-f0-9]{40}$/i;

async function sha256Hex(text:string){const b=new TextEncoder().encode(text);const h=await crypto.subtle.digest("SHA-256",b);return [...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,"0")).join("");}
function iso(v:unknown){return typeof v==="string"&&v!=="RECHECK_REQUIRED"&&Number.isFinite(Date.parse(v));}
function explicitBool(v:unknown){return typeof v==="boolean";}
function parseJson(v:unknown){if(typeof v!=="string")return v;try{return JSON.parse(v);}catch{return null;}}
function unresolvedEmpty(v:unknown){const x=parseJson(v);return Array.isArray(x)&&x.length===0;}

export interface SourceAccessReview {
  review_id:string; source_id:string; target_state:"SHADOW"|"ENABLED"; access_basis:string;
  terms_snapshot_at:string; evidence_id:string; access_basis_valid:boolean; privacy_review_pass:boolean;
  parser_contract_pass:boolean; provenance_hash_pass:boolean; rate_budget_pass:boolean; shadow_pass:boolean;
}
export interface ProviderAccessReview {
  review_id:string; provider_id:string; access_basis:string; terms_snapshot_at:string; rate_policy:string;
  evidence_id:string; access_basis_valid:boolean; terms_review_pass:boolean; rate_policy_review_pass:boolean;
}
export type AccessReviewKind="source"|"provider";

function sourceCanonical(r:SourceAccessReview){return JSON.stringify({review_id:r.review_id,source_id:r.source_id,target_state:r.target_state,access_basis:r.access_basis,terms_snapshot_at:r.terms_snapshot_at,evidence_id:r.evidence_id,access_basis_valid:r.access_basis_valid,privacy_review_pass:r.privacy_review_pass,parser_contract_pass:r.parser_contract_pass,provenance_hash_pass:r.provenance_hash_pass,rate_budget_pass:r.rate_budget_pass,shadow_pass:r.shadow_pass});}
function providerCanonical(r:ProviderAccessReview){return JSON.stringify({review_id:r.review_id,provider_id:r.provider_id,access_basis:r.access_basis,terms_snapshot_at:r.terms_snapshot_at,rate_policy:r.rate_policy,evidence_id:r.evidence_id,access_basis_valid:r.access_basis_valid,terms_review_pass:r.terms_review_pass,rate_policy_review_pass:r.rate_policy_review_pass});}
export async function sourceAccessReviewPayloadHash(r:SourceAccessReview){return sha256Hex(sourceCanonical(r));}
export async function providerAccessReviewPayloadHash(r:ProviderAccessReview){return sha256Hex(providerCanonical(r));}

export function runtimeCommitOrNull(v:string|undefined){return v&&COMMIT.test(v)?v.toLowerCase():null;}
export function validateAccessAuditEvidenceInput(e:any,runtimeCommitSha:string){
  if(!COMMIT.test(runtimeCommitSha))throw new Error("RUNTIME_COMMIT_UNAVAILABLE");
  if(!e||!e.evidence_id||e.spec_version!=="1.3"||String(e.commit_sha??"").toLowerCase()!==runtimeCommitSha.toLowerCase()||!SHA256.test(String(e.test_report_hash??""))||!iso(e.created_at)||!unresolvedEmpty(e.unresolved_items))throw new Error("ACCESS_AUDIT_EVIDENCE_INVALID");
  const binding=e.provider_readback?.access_review;
  if(!binding||!['source','provider'].includes(binding.kind)||!binding.entity_id||!binding.review_id||binding.human_review_payload_sha256!==e.test_report_hash)throw new Error("ACCESS_AUDIT_BINDING_INVALID");
  const expectedGate=binding.kind==="source"?"TERMS_AND_PRIVACY_REVIEW":"ACCESS_BASIS_REVIEW";
  if(e.gate_id!==expectedGate)throw new Error("ACCESS_AUDIT_STAGE_INVALID");
  return {kind:binding.kind as AccessReviewKind,entity_id:String(binding.entity_id),review_id:String(binding.review_id),payload_sha256:String(binding.human_review_payload_sha256)};
}

async function requireBoundEvidence(db:D1Database,input:{evidence_id:string;kind:AccessReviewKind;entity_id:string;review_id:string;payload_sha256:string;runtime_commit_sha:string}){
  const ev=await db.prepare("SELECT gate_id,spec_version,commit_sha,test_report_hash,provider_readback,unresolved_items FROM audit_evidence WHERE evidence_id=?").bind(input.evidence_id).first<any>();
  const expectedGate=input.kind==="source"?"TERMS_AND_PRIVACY_REVIEW":"ACCESS_BASIS_REVIEW";
  if(!ev||ev.gate_id!==expectedGate||ev.spec_version!=="1.3"||String(ev.commit_sha??"").toLowerCase()!==input.runtime_commit_sha.toLowerCase()||ev.test_report_hash!==input.payload_sha256||!unresolvedEmpty(ev.unresolved_items))throw new Error("ACCESS_REVIEW_EVIDENCE_INVALID");
  const b=parseJson(ev.provider_readback)?.access_review;
  if(!b||b.kind!==input.kind||b.entity_id!==input.entity_id||b.review_id!==input.review_id||b.human_review_payload_sha256!==input.payload_sha256)throw new Error("ACCESS_REVIEW_EVIDENCE_BINDING_MISMATCH");
}

export async function applyAccessSourceReview(db:D1Database,r:SourceAccessReview,ctx:{nowIso:string;reviewerKeyId:string;runtimeCommitSha:string}){
  if(!r||!r.review_id||!r.source_id||!r.evidence_id||!r.access_basis?.trim()||!iso(r.terms_snapshot_at)||!['SHADOW','ENABLED'].includes(r.target_state)||![r.access_basis_valid,r.privacy_review_pass,r.parser_contract_pass,r.provenance_hash_pass,r.rate_budget_pass,r.shadow_pass].every(explicitBool))throw new Error("SOURCE_REVIEW_INVALID");
  if(!ctx.reviewerKeyId||!COMMIT.test(ctx.runtimeCommitSha))throw new Error("RUNTIME_COMMIT_UNAVAILABLE");
  const payloadHash=await sourceAccessReviewPayloadHash(r);
  const prior=await db.prepare("SELECT payload_sha256,reviewer_key_id FROM source_onboarding_reviews WHERE review_id=?").bind(r.review_id).first<any>();
  if(prior){if(prior.payload_sha256!==payloadHash||prior.reviewer_key_id!==ctx.reviewerKeyId)throw new Error("SOURCE_REVIEW_IDEMPOTENCY_CONFLICT");return {source_id:r.source_id,state:r.target_state,payload_sha256:payloadHash,reviewer_key_id:prior.reviewer_key_id,idempotent:true};}
  const src=await db.prepare("SELECT lifecycle_state,parser FROM source_registry WHERE source_id=?").bind(r.source_id).first<any>();
  if(!src)throw new Error("SOURCE_NOT_FOUND");
  await requireBoundEvidence(db,{evidence_id:r.evidence_id,kind:"source",entity_id:r.source_id,review_id:r.review_id,payload_sha256:payloadHash,runtime_commit_sha:ctx.runtimeCommitSha});
  if(!r.access_basis_valid||!r.privacy_review_pass||!r.parser_contract_pass)throw new Error("SOURCE_SHADOW_GATES_INCOMPLETE");
  if(!src.parser)throw new Error("SOURCE_CONTRACT_INCOMPLETE");
  if(r.target_state==="ENABLED"){
    if(src.lifecycle_state!=="SHADOW")throw new Error("SOURCE_MUST_PASS_SHADOW_FIRST");
    if(!r.provenance_hash_pass||!r.rate_budget_pass||!r.shadow_pass)throw new Error("SOURCE_ENABLE_GATES_INCOMPLETE");
  }
  const checks={access_basis_valid:r.access_basis_valid,privacy_review_pass:r.privacy_review_pass,parser_contract_pass:r.parser_contract_pass,provenance_hash_pass:r.provenance_hash_pass,rate_budget_pass:r.rate_budget_pass,shadow_pass:r.shadow_pass};
  await db.batch([
    db.prepare("INSERT INTO source_onboarding_reviews(review_id,source_id,target_state,terms_snapshot_at,evidence_id,checks_json,payload_sha256,created_at,access_basis,reviewer_key_id) VALUES(?,?,?,?,?,?,?,?,?,?)").bind(r.review_id,r.source_id,r.target_state,r.terms_snapshot_at,r.evidence_id,JSON.stringify(checks),payloadHash,ctx.nowIso,r.access_basis,ctx.reviewerKeyId),
    db.prepare("UPDATE source_registry SET lifecycle_state=?,status=?,access_basis=?,terms_snapshot_at=?,kill_switch=0,kill_switch_state='CLEAR' WHERE source_id=?").bind(r.target_state,r.target_state,r.access_basis,r.terms_snapshot_at,r.source_id)
  ]);
  return {source_id:r.source_id,state:r.target_state,payload_sha256:payloadHash,reviewer_key_id:ctx.reviewerKeyId,idempotent:false};
}

export async function applyProviderAccessReview(db:D1Database,r:ProviderAccessReview,ctx:{nowIso:string;reviewerKeyId:string;runtimeCommitSha:string}){
  if(!r||!r.review_id||!r.provider_id||!r.evidence_id||!PROVIDER_ACCESS_BASES.has(r.access_basis)||!iso(r.terms_snapshot_at)||!r.rate_policy?.trim()||![r.access_basis_valid,r.terms_review_pass,r.rate_policy_review_pass].every(explicitBool))throw new Error("PROVIDER_ACCESS_REVIEW_INVALID");
  if(!ctx.reviewerKeyId||!COMMIT.test(ctx.runtimeCommitSha))throw new Error("RUNTIME_COMMIT_UNAVAILABLE");
  if(!r.access_basis_valid||!r.terms_review_pass||!r.rate_policy_review_pass)throw new Error("PROVIDER_ACCESS_REVIEW_INCOMPLETE");
  const payloadHash=await providerAccessReviewPayloadHash(r);
  const prior=await db.prepare("SELECT payload_sha256,reviewer_key_id FROM provider_access_reviews WHERE review_id=?").bind(r.review_id).first<any>();
  if(prior){if(prior.payload_sha256!==payloadHash||prior.reviewer_key_id!==ctx.reviewerKeyId)throw new Error("PROVIDER_ACCESS_REVIEW_IDEMPOTENCY_CONFLICT");return {provider_id:r.provider_id,payload_sha256:payloadHash,reviewer_key_id:prior.reviewer_key_id,idempotent:true};}
  const provider=await db.prepare("SELECT provider_id FROM provider_access_registry WHERE provider_id=?").bind(r.provider_id).first<any>();
  if(!provider)throw new Error("PROVIDER_NOT_FOUND");
  await requireBoundEvidence(db,{evidence_id:r.evidence_id,kind:"provider",entity_id:r.provider_id,review_id:r.review_id,payload_sha256:payloadHash,runtime_commit_sha:ctx.runtimeCommitSha});
  const checks={access_basis_valid:r.access_basis_valid,terms_review_pass:r.terms_review_pass,rate_policy_review_pass:r.rate_policy_review_pass};
  await db.batch([
    db.prepare("INSERT INTO provider_access_reviews(review_id,provider_id,access_basis,terms_snapshot_at,rate_policy,evidence_id,checks_json,payload_sha256,reviewer_key_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)").bind(r.review_id,r.provider_id,r.access_basis,r.terms_snapshot_at,r.rate_policy,r.evidence_id,JSON.stringify(checks),payloadHash,ctx.reviewerKeyId,ctx.nowIso),
    db.prepare("UPDATE provider_access_registry SET access_basis=?,terms_snapshot_at=?,rate_policy=? WHERE provider_id=?").bind(r.access_basis,r.terms_snapshot_at,r.rate_policy,r.provider_id)
  ]);
  return {provider_id:r.provider_id,payload_sha256:payloadHash,reviewer_key_id:ctx.reviewerKeyId,idempotent:false};
}

export async function readAccessReview(db:D1Database,input:{kind:AccessReviewKind;entity_id:string;review_id?:string|null}){
  if(!input||!['source','provider'].includes(input.kind)||!input.entity_id)throw new Error("ACCESS_REVIEW_READBACK_INVALID");
  if(input.kind==="source"){
    const review=input.review_id?await db.prepare("SELECT review_id,source_id,target_state,access_basis,terms_snapshot_at,evidence_id,checks_json,payload_sha256,reviewer_key_id,created_at FROM source_onboarding_reviews WHERE source_id=? AND review_id=?").bind(input.entity_id,input.review_id).first<any>():await db.prepare("SELECT review_id,source_id,target_state,access_basis,terms_snapshot_at,evidence_id,checks_json,payload_sha256,reviewer_key_id,created_at FROM source_onboarding_reviews WHERE source_id=? ORDER BY created_at DESC,review_id DESC LIMIT 1").bind(input.entity_id).first<any>();
    const registry=await db.prepare("SELECT source_id,lifecycle_state,status,access_basis,terms_snapshot_at,kill_switch,kill_switch_state FROM source_registry WHERE source_id=?").bind(input.entity_id).first<any>();
    return {kind:"source",review:review?{...review,checks_json:parseJson(review.checks_json)}:null,registry};
  }
  const review=input.review_id?await db.prepare("SELECT review_id,provider_id,access_basis,terms_snapshot_at,rate_policy,evidence_id,checks_json,payload_sha256,reviewer_key_id,created_at FROM provider_access_reviews WHERE provider_id=? AND review_id=?").bind(input.entity_id,input.review_id).first<any>():await db.prepare("SELECT review_id,provider_id,access_basis,terms_snapshot_at,rate_policy,evidence_id,checks_json,payload_sha256,reviewer_key_id,created_at FROM provider_access_reviews WHERE provider_id=? ORDER BY created_at DESC,review_id DESC LIMIT 1").bind(input.entity_id).first<any>();
  const registry=await db.prepare("SELECT provider_id,access_basis,terms_snapshot_at,rate_policy,kill_switch_state,connector_state FROM provider_access_registry WHERE provider_id=?").bind(input.entity_id).first<any>();
  return {kind:"provider",review:review?{...review,checks_json:parseJson(review.checks_json)}:null,registry};
}
