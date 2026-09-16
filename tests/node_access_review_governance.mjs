import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import worker from '../dist/worker.js';
import { installKey, authEnv, signedRequest } from './scoped_auth_helper.mjs';

class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const enc=new TextEncoder();
async function sha256(text){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(text)))].map(x=>x.toString(16).padStart(2,'0')).join('');}
function sourceCanonical(r){const checks={access_basis_valid:!!r.access_basis_valid,privacy_review_pass:!!r.privacy_review_pass,parser_contract_pass:!!r.parser_contract_pass,provenance_hash_pass:!!r.provenance_hash_pass,rate_budget_pass:!!r.rate_budget_pass,shadow_pass:!!r.shadow_pass};return JSON.stringify({review_id:r.review_id,source_id:r.source_id,target_state:r.target_state,terms_snapshot_at:r.terms_snapshot_at,checks});}
function providerCanonical(r){return JSON.stringify({review_id:r.review_id,provider_id:r.provider_id,access_basis:r.access_basis,terms_snapshot_at:r.terms_snapshot_at,rate_policy:r.rate_policy,look_to_book_budget:r.look_to_book_budget??null});}
async function call(env,keyId,secret,path,payload){const body=JSON.stringify(payload);const res=await worker.fetch(await signedRequest(`https://fare.example${path}`,body,{keyId,secret}),env);let data=null;try{data=await res.json()}catch{}return {status:res.status,data};}

const raw=new DatabaseSync(':memory:');
for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));
raw.exec(fs.readFileSync(new URL('../generated/seed.generated.sql',import.meta.url),'utf8'));
const db=new DB(raw);const secret='access-review-secret-0123456789';const runtime='c'.repeat(40);const env={...authEnv(db,secret),FARE_COMMIT_SHA:runtime};
const paths=['/audit/evidence','/audit/evidence/readback','/sources/onboarding/review','/providers/access/review','/access/reviews/readback'];
installKey(raw,{keyId:'wrong-role',role:'TEST',allowedPaths:paths});
installKey(raw,{keyId:'global-reviewer',role:'ACCESS_REVIEWER',allowedPaths:paths});
installKey(raw,{keyId:'source-reviewer',role:'ACCESS_REVIEWER',sourceId:'trinity_airways_official',allowedPaths:paths});
installKey(raw,{keyId:'provider-reviewer',role:'ACCESS_REVIEWER',providerId:'duffel',allowedPaths:paths});

const sourceReview={review_id:'source-review-1',source_id:'trinity_airways_official',target_state:'SHADOW',terms_snapshot_at:'2026-09-16T00:00:00Z',evidence_id:'source-evidence-1',access_basis_valid:true,privacy_review_pass:true,parser_contract_pass:true};
const wrongRole=await call(env,'wrong-role',secret,'/sources/onboarding/review',sourceReview);
const sourceHash=await sha256(sourceCanonical(sourceReview));
const sourceEvidence={evidence_id:sourceReview.evidence_id,gate_id:'TERMS_AND_PRIVACY_REVIEW',spec_version:'1.3',commit_sha:runtime,test_report_hash:sourceHash,provider_readback:{kind:'human_access_review'},unresolved_items:[],created_at:'2026-09-16T00:00:01Z',entity_type:'SOURCE',entity_id:sourceReview.source_id,review_id:sourceReview.review_id};
const sourceEvidenceWrite=await call(env,'global-reviewer',secret,'/audit/evidence',sourceEvidence);
const sourceEvidenceRead=await call(env,'global-reviewer',secret,'/audit/evidence/readback',{evidence_id:sourceReview.evidence_id});
const reviewerMismatch=await call(env,'source-reviewer',secret,'/sources/onboarding/review',sourceReview);
const sourceApply=await call(env,'global-reviewer',secret,'/sources/onboarding/review',sourceReview);
const sourceReplay=await call(env,'global-reviewer',secret,'/sources/onboarding/review',sourceReview);
const sourceRead=await call(env,'global-reviewer',secret,'/access/reviews/readback',{kind:'source',entity_id:sourceReview.source_id,review_id:sourceReview.review_id});
const sourceCross=await call(env,'source-reviewer',secret,'/sources/onboarding/review',{...sourceReview,review_id:'cross-source',source_id:'jejuair_events',evidence_id:'does-not-matter'});
const changedReview={...sourceReview,terms_snapshot_at:'2026-09-16T00:05:00Z',evidence_id:'source-evidence-changed'};
const changedHash=await sha256(sourceCanonical(changedReview));
await call(env,'global-reviewer',secret,'/audit/evidence',{...sourceEvidence,evidence_id:changedReview.evidence_id,test_report_hash:changedHash,created_at:'2026-09-16T00:05:01Z'});
const sourceConflict=await call(env,'global-reviewer',secret,'/sources/onboarding/review',changedReview);
const finalGateForbidden=await call(env,'global-reviewer',secret,'/audit/evidence',{evidence_id:'forbidden-pg25',gate_id:'PG25',spec_version:'1.3',commit_sha:runtime,test_report_hash:'a'.repeat(64),unresolved_items:[],created_at:'2026-09-16T00:00:02Z'});

const providerReview={review_id:'provider-review-1',provider_id:'duffel',access_basis:'OFFICIAL_API',terms_snapshot_at:'2026-09-16T00:00:00Z',rate_policy:'TARGETED_ONLY',look_to_book_budget:120,evidence_id:'provider-evidence-1'};
const providerHash=await sha256(providerCanonical(providerReview));
const providerEvidence={evidence_id:providerReview.evidence_id,gate_id:'ACCESS_BASIS_REVIEW',spec_version:'1.3',commit_sha:runtime,test_report_hash:providerHash,provider_readback:{kind:'human_access_review'},unresolved_items:[],created_at:'2026-09-16T00:00:03Z',entity_type:'PROVIDER',entity_id:providerReview.provider_id,review_id:providerReview.review_id};
const providerEvidenceWrite=await call(env,'provider-reviewer',secret,'/audit/evidence',providerEvidence);
const providerApply=await call(env,'provider-reviewer',secret,'/providers/access/review',providerReview);
const providerRead=await call(env,'provider-reviewer',secret,'/access/reviews/readback',{kind:'provider',entity_id:'duffel',review_id:providerReview.review_id});
const providerCross=await call(env,'provider-reviewer',secret,'/providers/access/review',{...providerReview,review_id:'provider-cross',provider_id:'other',evidence_id:'none'});
const invalidBasis=await call(env,'global-reviewer',secret,'/providers/access/review',{...providerReview,review_id:'provider-invalid',access_basis:'UNSUPPORTED_WRAPPER',evidence_id:'none'});
const wrongReadbackRole=await call(env,'wrong-role',secret,'/access/reviews/readback',{kind:'source',entity_id:sourceReview.source_id,review_id:sourceReview.review_id});

raw.prepare("INSERT INTO source_onboarding_reviews(review_id,source_id,target_state,terms_snapshot_at,evidence_id,checks_json,payload_sha256,created_at,reviewer_key_id,human_review_sha256) VALUES('legacy-review','trinity_airways_official','SHADOW','2026-09-15T00:00:00Z','source-evidence-1','{}',?,'2026-09-15T00:00:00Z',NULL,NULL)").run('f'.repeat(64));
const legacyRead=await call(env,'global-reviewer',secret,'/access/reviews/readback',{kind:'source',entity_id:'trinity_airways_official',review_id:'legacy-review'});
const envNoCommit=authEnv(db,secret);
const missingCommitAudit=await call(envNoCommit,'global-reviewer',secret,'/audit/evidence',{...sourceEvidence,evidence_id:'missing-commit-evidence'});
const missingCommitReview=await call(envNoCommit,'global-reviewer',secret,'/sources/onboarding/review',{...sourceReview,review_id:'missing-commit-review',evidence_id:'missing'});

console.log(JSON.stringify({
  wrong_role:wrongRole.status,
  source_evidence_write:sourceEvidenceWrite.status,
  source_evidence_reviewer:sourceEvidenceRead.data?.evidence?.reviewer_key_id,
  reviewer_mismatch:reviewerMismatch.status,
  source_apply:sourceApply.status,
  source_replay:sourceReplay.status,
  source_read:sourceRead.status,
  source_read_reviewer:sourceRead.data?.review?.reviewer_key_id,
  source_read_valid:sourceRead.data?.approval_valid,
  source_registry_state:sourceRead.data?.registry?.lifecycle_state,
  source_cross:sourceCross.status,
  source_conflict:sourceConflict.status,
  final_gate_forbidden:finalGateForbidden.status,
  provider_evidence_write:providerEvidenceWrite.status,
  provider_apply:providerApply.status,
  provider_read:providerRead.status,
  provider_read_reviewer:providerRead.data?.review?.reviewer_key_id,
  provider_read_valid:providerRead.data?.approval_valid,
  provider_registry_budget:providerRead.data?.registry?.look_to_book_budget,
  provider_cross:providerCross.status,
  invalid_basis:invalidBasis.status,
  wrong_readback_role:wrongReadbackRole.status,
  legacy_valid:legacyRead.data?.approval_valid,
  missing_commit_audit:missingCommitAudit.status,
  missing_commit_review:missingCommitReview.status,
  source_review_rows:raw.prepare("SELECT count(*) n FROM source_onboarding_reviews WHERE reviewer_key_id IS NOT NULL").get().n,
  provider_review_rows:raw.prepare("SELECT count(*) n FROM provider_access_reviews").get().n
}));
