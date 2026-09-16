import type { D1Database } from "./types.js";
import { sourceHumanReviewSha } from "./access_reviews.js";

async function sha256Hex(text:string){const b=new TextEncoder().encode(text);const h=await crypto.subtle.digest("SHA-256",b);return [...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,"0")).join("");}
function iso(v:string){return Number.isFinite(Date.parse(v));}
export interface SourceOnboardingReview {
  review_id:string;
  source_id:string;
  target_state:"SHADOW"|"ENABLED";
  terms_snapshot_at:string;
  evidence_id:string;
  access_basis_valid:boolean;
  privacy_review_pass:boolean;
  parser_contract_pass:boolean;
  provenance_hash_pass?:boolean;
  rate_budget_pass?:boolean;
  shadow_pass?:boolean;
}
export async function applySourceOnboardingReview(db:D1Database,r:SourceOnboardingReview,nowIso:string,ctx?:{reviewer_key_id:string;runtime_commit:string}){
  if(!r.review_id||!r.source_id||!r.evidence_id||!iso(r.terms_snapshot_at)||r.terms_snapshot_at==="RECHECK_REQUIRED")throw new Error("SOURCE_REVIEW_INVALID");
  const src=await db.prepare("SELECT lifecycle_state,access_basis,parser FROM source_registry WHERE source_id=?").bind(r.source_id).first<any>();
  if(!src)throw new Error("SOURCE_NOT_FOUND");
  const ev=await db.prepare("SELECT gate_id,spec_version,commit_sha,test_report_hash,unresolved_items,entity_type,entity_id,review_id,reviewer_key_id FROM audit_evidence WHERE evidence_id=?").bind(r.evidence_id).first<any>();
  if(!ev||ev.spec_version!=="1.3")throw new Error("SOURCE_REVIEW_EVIDENCE_INVALID");
  const humanHash=await sourceHumanReviewSha(r);
  if(ctx){
    if(ev.gate_id!=="TERMS_AND_PRIVACY_REVIEW"||ev.commit_sha!==ctx.runtime_commit||ev.test_report_hash!==humanHash||ev.entity_type!=="SOURCE"||ev.entity_id!==r.source_id||ev.review_id!==r.review_id||ev.reviewer_key_id!==ctx.reviewer_key_id)throw new Error("SOURCE_REVIEW_EVIDENCE_INVALID");
  }else if((r.target_state==="SHADOW"&&ev.gate_id!=="PG25")||(r.target_state==="ENABLED"&&ev.gate_id!=="PG31"))throw new Error("SOURCE_REVIEW_GATE_MISMATCH");
  try{const u=JSON.parse(ev.unresolved_items??"[]");if(Array.isArray(u)&&u.length)throw new Error("SOURCE_REVIEW_UNRESOLVED_ITEMS");}catch(e){if(e instanceof Error&&e.message==="SOURCE_REVIEW_UNRESOLVED_ITEMS")throw e;throw new Error("SOURCE_REVIEW_EVIDENCE_INVALID");}
  if(!r.access_basis_valid||!r.privacy_review_pass||!r.parser_contract_pass)throw new Error("SOURCE_SHADOW_GATES_INCOMPLETE");
  if(!src.access_basis||!src.parser)throw new Error("SOURCE_CONTRACT_INCOMPLETE");
  const checks={access_basis_valid:r.access_basis_valid,privacy_review_pass:r.privacy_review_pass,parser_contract_pass:r.parser_contract_pass,provenance_hash_pass:!!r.provenance_hash_pass,rate_budget_pass:!!r.rate_budget_pass,shadow_pass:!!r.shadow_pass};
  const canonical=JSON.stringify({review_id:r.review_id,source_id:r.source_id,target_state:r.target_state,terms_snapshot_at:r.terms_snapshot_at,evidence_id:r.evidence_id,checks,reviewer_key_id:ctx?.reviewer_key_id??null,human_review_sha256:ctx?humanHash:null});
  const payloadHash=await sha256Hex(canonical);
  const prior=await db.prepare("SELECT payload_sha256,reviewer_key_id FROM source_onboarding_reviews WHERE review_id=?").bind(r.review_id).first<{payload_sha256:string;reviewer_key_id:string|null}>();
  if(prior){if(prior.payload_sha256!==payloadHash)throw new Error("SOURCE_REVIEW_IDEMPOTENCY_CONFLICT");return {source_id:r.source_id,state:r.target_state,idempotent:true};}
  if(r.target_state==="ENABLED"){
    if(src.lifecycle_state!=="SHADOW")throw new Error("SOURCE_MUST_PASS_SHADOW_FIRST");
    if(!r.provenance_hash_pass||!r.rate_budget_pass||!r.shadow_pass)throw new Error("SOURCE_ENABLE_GATES_INCOMPLETE");
  }
  await db.batch([
    db.prepare("INSERT INTO source_onboarding_reviews(review_id,source_id,target_state,terms_snapshot_at,evidence_id,checks_json,payload_sha256,created_at,reviewer_key_id,human_review_sha256) VALUES(?,?,?,?,?,?,?,?,?,?)").bind(r.review_id,r.source_id,r.target_state,r.terms_snapshot_at,r.evidence_id,JSON.stringify(checks),payloadHash,nowIso,ctx?.reviewer_key_id??null,ctx?humanHash:null),
    db.prepare("UPDATE source_registry SET lifecycle_state=?,status=?,terms_snapshot_at=?,kill_switch=0,kill_switch_state='CLEAR' WHERE source_id=?").bind(r.target_state,r.target_state,r.terms_snapshot_at,r.source_id)
  ]);
  return {source_id:r.source_id,state:r.target_state,idempotent:false};
}

export async function disableSource(db:D1Database,input:{source_id:string;reason:string},nowIso:string){
  if(!input.source_id||!input.reason?.trim())throw new Error("SOURCE_DISABLE_REASON_REQUIRED");
  const row=await db.prepare("SELECT source_id FROM source_registry WHERE source_id=?").bind(input.source_id).first();if(!row)throw new Error("SOURCE_NOT_FOUND");
  await db.prepare("UPDATE source_registry SET lifecycle_state='DISABLED',status='DISABLED',kill_switch=1,kill_switch_state='TRIPPED' WHERE source_id=?").bind(input.source_id).run();
  return {source_id:input.source_id,state:"DISABLED",at:nowIso,reason:input.reason};
}
