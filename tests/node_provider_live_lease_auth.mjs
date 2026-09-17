import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import worker from '../dist/worker.js';
import { installKey, authEnv, signedRequest } from './scoped_auth_helper.mjs';
class S{constructor(s){this.s=s;this.a=[]}bind(...a){this.a=a;return this}async run(){return{success:true,meta:this.s.run(...this.a)}}async first(){return this.s.get(...this.a)??null}async all(){return{results:this.s.all(...this.a)}}}
class D{constructor(x){this.x=x}prepare(q){return new S(this.x.prepare(q))}async batch(a){this.x.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of a)o.push(await s.run());this.x.exec('COMMIT');return o}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const db=new D(raw);
for(const p of ['duffel','other'])raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner,connector_state,supported_verification_json,background_allowed) values(?,'OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test','IMPLEMENTED','[\"LIVE_REPRICE\"]',0)").run(p);
const secret='provider-lease-secret-0123456789';installKey(raw,{keyId:'duffel-key',role:'PROVIDER_WORKER',providerId:'duffel',allowedPaths:['/offers/ingest','/provider-jobs/complete']});const env=authEnv(db,secret);
const lease='2099-01-01T00:00:00Z';
raw.prepare("insert into verification_jobs(job_id,job_type,target_class,payload_json,state,attempts,available_at,created_at,provider_id,query_fingerprint,provider_mode,claimed_by,lease_until) values('job-duffel','LIVE_REPRICE','PROVIDER_API','{}','LEASED',1,'2026-09-15T00:00:00Z','2026-09-15T00:00:00Z','duffel','q1','USER_REQUEST','worker-1',?)").run(lease);
raw.prepare("insert into verification_jobs(job_id,job_type,target_class,payload_json,state,attempts,available_at,created_at,provider_id,query_fingerprint,provider_mode,claimed_by,lease_until) values('job-other','LIVE_REPRICE','PROVIDER_API','{}','LEASED',1,'2026-09-15T00:00:00Z','2026-09-15T00:00:00Z','other','q1','USER_REQUEST','worker-1',?)").run(lease);
const base={provider_offer_id:'off-live',query_fingerprint:'q1',provider:'duffel',currency:'TWD',observed_at:new Date().toISOString(),expires_at:'2099-01-01T00:00:00Z',raw_sha256:'a'.repeat(64),source_snapshot_id:'job-duffel',offer_total:5000,fare_freshness:'REFRESHED_LIVE',cached_or_live:'LIVE'};
async function post(path,payload,nonce){const body=JSON.stringify(payload);return worker.fetch(await signedRequest(`https://fare.example${path}`,body,{keyId:'duffel-key',secret,nonce}),env)}
const ok=await post('/offers/ingest',{...base,worker_id:'worker-1'},'nonce-provider-ok-abcdef');
const wrongWorker=await post('/offers/ingest',{...base,provider_offer_id:'off-wrong-worker',raw_sha256:'b'.repeat(64),worker_id:'worker-2'},'nonce-provider-worker-abcdef');
const wrongJob=await post('/offers/ingest',{...base,provider_offer_id:'off-wrong-job',raw_sha256:'c'.repeat(64),source_snapshot_id:'job-other',worker_id:'worker-1'},'nonce-provider-job-abcdef');
const done=await post('/provider-jobs/complete',{job_id:'job-duffel',provider_id:'duffel',worker_id:'worker-1',success:true},'nonce-provider-done-abcdef');
const replay=await post('/provider-jobs/complete',{job_id:'job-duffel',provider_id:'duffel',worker_id:'worker-1',success:true},'nonce-provider-replay-abcdef');
const afterDone=await post('/offers/ingest',{...base,provider_offer_id:'off-after',raw_sha256:'d'.repeat(64),worker_id:'worker-1'},'nonce-provider-after-abcdef');
console.log(JSON.stringify({ok:ok.status,wrong_worker:wrongWorker.status,wrong_job:wrongJob.status,done:done.status,replay:replay.status,after_done:afterDone.status,offers:raw.prepare('select count(*) n from offer_snapshots').get().n,state:raw.prepare("select state from verification_jobs where job_id='job-duffel'").get().state}));
