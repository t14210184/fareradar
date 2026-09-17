import { DatabaseSync } from 'node:sqlite'; import fs from 'node:fs';
import { enqueueCandidateSignal } from '../dist/priority.js';
import { ingestOfferSnapshot } from '../dist/offers.js';
import { completeProviderJob } from '../dist/provider_jobs.js';
class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const db=new DB(raw);
for(const p of ['p1','p2'])raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner,connector_state,supported_verification_json,credential_binding,background_allowed) values(?, 'OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test','IMPLEMENTED','[\"LIVE_REPRICE\"]','TOKEN',1)").run(p);
await enqueueCandidateSignal(db,{signal_type:'PROMOTION',signal_id:'promo-result',required_verification:'LIVE_REPRICE',priority_score:80,route_scope:['TPE-KIX'],source_evidence_id:'obs-result',observed_at:'2026-09-15T00:00:00Z'},'2026-09-15T00:00:00Z');
const queueId='promotion:promo-result', qfp='qfp-shared';
for(const [n,p] of [[1,'p1'],[2,'p2']]){
  raw.prepare("insert into search_campaigns(campaign_id,profile_id,provider_id,origin_airports_json,destination_airports_json,departure_dates_json,trip_lengths_json,passengers_json,max_queries_per_signal,enabled,expires_at,created_at,updated_at) values(?,?,?,?,?,?,?,?,2,1,'2026-12-31T00:00:00Z','2026-09-15T00:00:00Z','2026-09-15T00:00:00Z')").run(`c${n}`,'synthetic',p,'["TPE"]','["KIX"]','["2026-11-02"]','[3]','[{"type":"adult"}]');
  raw.prepare("insert into verification_jobs(job_id,job_type,target_class,payload_json,state,attempts,available_at,created_at,provider_id,query_fingerprint,provider_mode,claimed_by,lease_until) values(?, 'LIVE_REPRICE','PROVIDER_API','{}','LEASED',1,'2026-09-15T00:00:00Z','2026-09-15T00:00:00Z',?,?,'USER_REQUEST',?,?)").run(`job${n}`,p,qfp,`worker-${p}`,'2026-09-15T00:10:00Z');
  raw.prepare("insert into provider_search_plans(plan_id,campaign_id,queue_id,provider_id,query_fingerprint,query_json,state,provider_job_id,attempts,next_attempt_at,created_at,updated_at) values(?,?,?,?,?,'{}','DISPATCHED',?,1,'2026-09-15T00:00:00Z','2026-09-15T00:00:00Z','2026-09-15T00:00:00Z')").run(`plan${n}`,`c${n}`,queueId,p,qfp,`job${n}`);
  raw.prepare("insert into provider_job_consumers(job_id,plan_id,queue_id,created_at) values(?,?,?,'2026-09-15T00:00:00Z')").run(`job${n}`,`plan${n}`,queueId);
}
await ingestOfferSnapshot(db,{provider_offer_id:'offer-p1',query_fingerprint:qfp,provider:'p1',currency:'TWD',observed_at:'2026-09-15T00:01:00Z',expires_at:'2026-09-15T04:00:00Z',raw_sha256:'1'.repeat(64),source_snapshot_id:'job1',offer_total:5000,fare_freshness:'LIVE',cached_or_live:'LIVE'});
const first=await completeProviderJob(db,{job_id:'job1',provider_id:'p1',worker_id:'worker-p1',success:true},'2026-09-15T00:02:00Z');
const afterFirst=raw.prepare("select verification_state,reason,live_offer_count,provider_count from candidate_verification_results where queue_id=?").get(queueId);
const stateAfterFirst=raw.prepare("select state from candidate_priority_queue where queue_id=?").get(queueId).state;
await ingestOfferSnapshot(db,{provider_offer_id:'offer-p2',query_fingerprint:qfp,provider:'p2',currency:'TWD',observed_at:'2026-09-15T00:03:00Z',expires_at:'2026-09-15T04:00:00Z',raw_sha256:'2'.repeat(64),source_snapshot_id:'job2',offer_total:5050,fare_freshness:'LIVE',cached_or_live:'LIVE'});
const second=await completeProviderJob(db,{job_id:'job2',provider_id:'p2',worker_id:'worker-p2',success:true},'2026-09-15T00:04:00Z');
const final=raw.prepare("select verification_state,reason,best_offer_id,best_offer_total,live_offer_count,provider_count from candidate_verification_results where queue_id=?").get(queueId);
const state=raw.prepare("select state from candidate_priority_queue where queue_id=?").get(queueId).state;
const links=raw.prepare("select provider_offer_id,job_id from candidate_offer_links where queue_id=? order by provider_offer_id").all(queueId);
await completeProviderJob(db,{job_id:'job2',provider_id:'p2',worker_id:'worker-p2',success:true},'2026-09-15T00:05:00Z');
const linksAfterReplay=raw.prepare("select count(*) n from candidate_offer_links where queue_id=?").get(queueId).n;
console.log(JSON.stringify({first,afterFirst,stateAfterFirst,second,final,state,links,linksAfterReplay}));
