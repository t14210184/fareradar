import type { D1Database } from "./types.js";
export interface AuditEvidenceInput { evidence_id:string; gate_id:string; spec_version:string; commit_sha?:string|null; dependency_lock_hash?:string|null; build_run_id?:string|null; deployed_version?:string|null; test_report_hash:string; provider_readback?:unknown; unresolved_items?:unknown; created_at:string; }
export async function recordAuditEvidence(db:D1Database,e:AuditEvidenceInput){
  if(!e.evidence_id||!e.gate_id||!e.spec_version||!/^[a-f0-9]{64}$/i.test(e.test_report_hash)||!Number.isFinite(Date.parse(e.created_at)))throw new Error('AUDIT_EVIDENCE_INVALID');
  const prior=await db.prepare("SELECT test_report_hash,commit_sha FROM audit_evidence WHERE evidence_id=?").bind(e.evidence_id).first<any>();
  if(prior){if(prior.test_report_hash!==e.test_report_hash||(prior.commit_sha??null)!==(e.commit_sha??null))throw new Error('AUDIT_EVIDENCE_CONFLICT');return {evidence_id:e.evidence_id,idempotent:true};}
  await db.prepare("INSERT INTO audit_evidence(evidence_id,gate_id,spec_version,commit_sha,dependency_lock_hash,build_run_id,deployed_version,test_report_hash,provider_readback,unresolved_items,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)")
    .bind(e.evidence_id,e.gate_id,e.spec_version,e.commit_sha??null,e.dependency_lock_hash??null,e.build_run_id??null,e.deployed_version??null,e.test_report_hash,JSON.stringify(e.provider_readback??null),JSON.stringify(e.unresolved_items??null),e.created_at).run();
  return {evidence_id:e.evidence_id,idempotent:false};
}
export async function recordSourceDiscoveryEdge(db:D1Database,e:{from_source_id:string;to_candidate_source_key:string;relation_type:string;observed_at:string;evidence_id:string;confidence:number;onboarding_state:string}){
  if(!e.from_source_id||!e.to_candidate_source_key||!e.relation_type||!e.evidence_id||!Number.isFinite(Date.parse(e.observed_at))||e.confidence<0||e.confidence>1)throw new Error('SOURCE_DISCOVERY_EDGE_INVALID');
  await db.prepare("INSERT OR IGNORE INTO source_discovery_edges(from_source_id,to_candidate_source_key,relation_type,observed_at,evidence_id,confidence,onboarding_state) VALUES(?,?,?,?,?,?,?)").bind(e.from_source_id,e.to_candidate_source_key,e.relation_type,e.observed_at,e.evidence_id,e.confidence,e.onboarding_state).run();
  return {ok:true};
}
