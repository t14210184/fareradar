import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { enqueueCandidateSignal } from '../dist/priority.js';
import { ingestOfferSnapshot } from '../dist/offers.js';
import { expireLiveProviderOffers } from '../dist/offer_lifecycle.js';
class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const db=new DB(raw);
await enqueueCandidateSignal(db,{signal_type:'PROMOTION',signal_id:'redundant',required_verification:'LIVE_REPRICE',priority_score:80,route_scope:['TPE-KIX'],source_evidence_id:'obs-x',observed_at:'2026-09-15T00:00:00Z'},'2026-09-15T00:00:00Z');
const queueId='promotion:redundant',qfp='same-query';
for(const [i,p,price,expires] of [[1,'p1',5000,'2026-09-15T01:00:00Z'],[2,'p2',5010,'2026-09-15T03:00:00Z'],[3,'p3',5020,'2026-09-15T03:00:00Z']]){
  raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner,connector_state,supported_verification_json,credential_binding,background_allowed) values(?, 'OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test','IMPLEMENTED','[\"LIVE_REPRICE\"]','TOKEN',1)").run(p);
  raw.prepare("insert into search_campaigns(campaign_id,profile_id,provider_id,origin_airports_json,destination_airports_json,departure_dates_json,trip_lengths_json,passengers_json,max_queries_per_signal,enabled,expires_at,created_at,updated_at) values(?,?,?,?,?,?,?,?,2,1,'2026-12-31T00:00:00Z','2026-09-15T00:00:00Z','2026-09-15T00:00:00Z')").run(`c${i}`,'synthetic',p,'["TPE"]','["KIX"]','["2026-11-02"]','[3]','[{"type":"adult"}]');
  raw.prepare("insert into verification_jobs(job_id,job_type,target_class,payload_json,state,attempts,available_at,created_at,provider_id,query_fingerprint,provider_mode) values(?, 'LIVE_REPRICE','PROVIDER_API','{}','DONE',1,'2026-09-15T00:00:00Z','2026-09-15T00:00:00Z',?,?,'USER_REQUEST')").run(`job${i}`,p,qfp);
  raw.prepare("insert into provider_search_plans(plan_id,campaign_id,queue_id,provider_id,query_fingerprint,query_json,state,provider_job_id,attempts,next_attempt_at,created_at,updated_at) values(?,?,?,?,?,'{}','DISPATCHED',?,1,'2026-09-15T00:00:00Z','2026-09-15T00:00:00Z','2026-09-15T00:00:00Z')").run(`plan${i}`,`c${i}`,queueId,p,qfp,`job${i}`);
  await ingestOfferSnapshot(db,{provider_offer_id:`offer${i}`,query_fingerprint:qfp,provider:p,currency:'TWD',observed_at:'2026-09-15T00:10:00Z',expires_at:expires,raw_sha256:String(i).repeat(64),source_snapshot_id:`job${i}`,offer_total:price,fare_freshness:'LIVE',cached_or_live:'LIVE'});
  raw.prepare("insert into candidate_offer_links(queue_id,plan_id,job_id,provider_offer_id,query_fingerprint,created_at) values(?,?,?,?,?,'2026-09-15T00:10:00Z')").run(queueId,`plan${i}`,`job${i}`,`offer${i}`,qfp);
}
const resultId='verify:promotion:redundant:same-query';
raw.prepare("insert into candidate_verification_results(result_id,queue_id,query_fingerprint,verification_state,reason,best_offer_id,best_offer_total,currency,live_offer_count,provider_count,updated_at) values(?,?,?,'CONFIRMED','INDEPENDENT_LIVE_MATCH','offer1',5000,'TWD',3,3,'2026-09-15T00:11:00Z')").run(resultId,queueId,qfp);
raw.prepare("insert into candidate_verification_supports(result_id,provider_offer_id,support_role,created_at) values(?, 'offer1','PRIMARY','2026-09-15T00:11:00Z'),(?, 'offer2','SUPPORT','2026-09-15T00:11:00Z')").run(resultId,resultId);
const out=await expireLiveProviderOffers(db,'2026-09-15T01:00:01Z',1);
const result=raw.prepare("select verification_state,reason,best_offer_id,best_offer_total,live_offer_count,provider_count from candidate_verification_results where result_id=?").get(resultId);
const supports=raw.prepare("select provider_offer_id,support_role from candidate_verification_supports where result_id=? order by provider_offer_id").all(resultId);
const event=raw.prepare("select new_verification_state,correction_state,reprice_state from live_offer_lifecycle_events where result_id=?").get(resultId);
const alerts=raw.prepare("select count(*) n from candidate_alert_intents").get().n;
const jobs=raw.prepare("select count(*) n from verification_jobs where job_id like '%:refresh:%'").get().n;
console.log(JSON.stringify({out,result,supports,event,alerts,jobs}));
