import type { D1Database } from "./types.js";

const APPROVABLE_ACCESS_BASES=new Set(["OFFICIAL_API","PARTNER_CONTRACT","AIRLINE_DIRECT","MANUAL_ORACLE","PUBLIC_PAGE_MONITOR"]);
async function sha256Hex(text:string){const b=new TextEncoder().encode(text);const h=await crypto.subtle.digest("SHA-256",b);return [...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,"0")).join("");}
function validIso(v:string){return typeof v==="string"&&Number.isFinite(Date.parse(v))&&v!=="RECHECK_REQUIRED";}
function validSha40(v:string){return /^[a-f0-9]{40}$/i.test(v);}
function unresolvedEmpty(raw:unknown){try{const v=typeof raw==="string"?JSON.parse(raw):raw;return Array.isArray(v)&&v.length===0;}catch{return false;}}
export function requireRuntimeCommit(runtimeCommit:string|undefined){if(!runtimeCommit||!validSha40(runtimeCommit))throw new Error("RUNTIME_COMMIT_UNAVAILABLE");return runtimeCommit;}

export function sourceHumanReviewCanonical(r:any){
  const checks={access_basis_valid:!!r.access_basis_valid,privacy_review_pass:!!r.privacy_review_pass,parser_contract_pass:!!r.parser_contract_pass,provenance_hash_pass:!!r.provenance_hash_pass,rate_budget_pass:!!r.rate_budget_pass,shadow_pass:!!r.shadow_pass};
  return JSON.stringify({review_id:r.review_id,source_id:r.source_id,target_state:r.target_state,terms_snapshot_at:r.terms_snapshot_at,checks});
}
export async function sourceHumanReviewSha(r:any){return sha256Hex(sourceHumanReviewCanonical(r));}

export interface ProviderAccessReviewInput {review_id:string;provider_id:string;access_basis:string;terms_snapshot_at:string;rate_policy:string;look_to_book_budget?:number|null;evidence_id:string;}
export function providerHumanReviewCanonical(r:ProviderAccessReviewInput){return JSON.stringify({review_id:r.review_id,provider_id:r.provider_id,access_basis:r.access_basis,terms_snapshot_at:r.terms_snapshot_at,rate_policy:r.rate_policy,look_to_book_budget:r.look_to_book_budget??null});}
export async function providerHumanReviewSha(r:ProviderAccessReviewInput){return sha256Hex(providerHumanReviewCanonical(r));}

async function exactReviewEvidence(db:D1Database,input:{evidence_id:string;stage:string;commit_sha:string;entity_type:"SOURCE"|"PROVIDER";entity_id:string;review_id:string;reviewer_key_id:string;human_review_sha256:string}){
  const ev=await db.prepare("SELECT gate_id,spec_version,commit_sha,test_report_hash,unresolved_items,entity_type,entity_id,review_id,reviewer_key_id FROM audit_evidence WHERE evidence_id=?").bind(input.evidence_id).first<any>();
  if(!ev||ev.spec_version!=="1.3"||ev.gate_id!==input.stage||ev.commit_sha!==input.commit_sha||ev.test_report_hash!==input.human_review_sha256||ev.entity_type!==input.entity_type||ev.entity_id!==input.entity_id||ev.review_id!==input.review_id||ev.reviewer_key_id!==input.reviewer_key_id||!unresolvedEmpty(ev.unresolved_items))throw new Error("ACCESS_REVIEW_EVIDENCE_INVALID");
  return ev;
}

export async function applyProviderAccessReview(db:D1Database,r:ProviderAccessReviewInput,ctx:{reviewer_key_id:string;runtime_commit:string},nowIso:string){
  if(!r.review_id||!r.provider_id||!r.evidence_id||!APPROVABLE_ACCESS_BASES.has(r.access_basis)||!validIso(r.terms_snapshot_at)||!r.rate_policy?.trim()||(r.look_to_book_budget!=null&&(!Number.isInteger(r.look_to_book_budget)||r.look_to_book_budget<0)))throw new Error("PROVIDER_ACCESS_REVIEW_INVALID");
  const provider=await db.prepare("SELECT provider_id FROM provider_access_registry WHERE provider_id=?").bind(r.provider_id).first();if(!provider)throw new Error("PROVIDER_NOT_FOUND");
  const humanHash=await providerHumanReviewSha(r);
  await exactReviewEvidence(db,{evidence_id:r.evidence_id,stage:"ACCESS_BASIS_REVIEW",commit_sha:ctx.runtime_commit,entity_type:"PROVIDER",entity_id:r.provider_id,review_id:r.review_id,reviewer_key_id:ctx.reviewer_key_id,human_review_sha256:humanHash});
  const canonical=JSON.stringify({...JSON.parse(providerHumanReviewCanonical(r)),evidence_id:r.evidence_id,reviewer_key_id:ctx.reviewer_key_id,human_review_sha256:humanHash});
  const payloadHash=await sha256Hex(canonical);
  const prior=await db.prepare("SELECT payload_sha256 FROM provider_access_reviews WHERE review_id=?").bind(r.review_id).first<{payload_sha256:string}>();
  if(prior){if(prior.payload_sha256!==payloadHash)throw new Error("PROVIDER_ACCESS_REVIEW_IDEMPOTENCY_CONFLICT");return {provider_id:r.provider_id,idempotent:true,payload_sha256:payloadHash};}
  await db.batch([
    db.prepare("INSERT INTO provider_access_reviews(review_id,provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,evidence_id,reviewer_key_id,human_review_sha256,payload_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)").bind(r.review_id,r.provider_id,r.access_basis,r.terms_snapshot_at,r.rate_policy,r.look_to_book_budget??null,r.evidence_id,ctx.reviewer_key_id,humanHash,payloadHash,nowIso),
    db.prepare("UPDATE provider_access_registry SET access_basis=?,terms_snapshot_at=?,rate_policy=?,look_to_book_budget=? WHERE provider_id=?").bind(r.access_basis,r.terms_snapshot_at,r.rate_policy,r.look_to_book_budget??null,r.provider_id)
  ]);
  return {provider_id:r.provider_id,idempotent:false,payload_sha256:payloadHash};
}

export async function readAccessReview(db:D1Database,input:{kind:"source"|"provider";entity_id:string;review_id?:string|null}){
  if(!input.entity_id||(input.kind!=="source"&&input.kind!=="provider"))throw new Error("ACCESS_REVIEW_READBACK_INVALID");
  if(input.kind==="source"){
    const review=input.review_id?await db.prepare("SELECT * FROM source_onboarding_reviews WHERE review_id=? AND source_id=?").bind(input.review_id,input.entity_id).first<any>():await db.prepare("SELECT * FROM source_onboarding_reviews WHERE source_id=? AND reviewer_key_id IS NOT NULL ORDER BY created_at DESC,review_id DESC LIMIT 1").bind(input.entity_id).first<any>();
    const registry=await db.prepare("SELECT source_id,lifecycle_state,status,access_basis,terms_snapshot_at,kill_switch,kill_switch_state FROM source_registry WHERE source_id=?").bind(input.entity_id).first<any>();
    return {kind:"source",review,registry,approval_valid:!!review?.reviewer_key_id};
  }
  const review=input.review_id?await db.prepare("SELECT * FROM provider_access_reviews WHERE review_id=? AND provider_id=?").bind(input.review_id,input.entity_id).first<any>():await db.prepare("SELECT * FROM provider_access_reviews WHERE provider_id=? ORDER BY created_at DESC,review_id DESC LIMIT 1").bind(input.entity_id).first<any>();
  const registry=await db.prepare("SELECT provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,connector_state,background_allowed FROM provider_access_registry WHERE provider_id=?").bind(input.entity_id).first<any>();
  return {kind:"provider",review,registry,approval_valid:!!review?.reviewer_key_id};
}
