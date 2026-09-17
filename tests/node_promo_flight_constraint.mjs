import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { ingestOfferSnapshot } from '../dist/offers.js';
import { projectProviderJobResults } from '../dist/provider_results.js';

class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:');
for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));
const db=new DB(raw); const now='2026-09-15T00:00:00Z', qfp='qfp-flight-rule';
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner,connector_state,supported_verification_json,credential_binding,background_allowed) values('p1','OFFICIAL_API',?,'TARGETED_ONLY',1000,'CLEAR','test','IMPLEMENTED','[\"LIVE_REPRICE\"]','TOKEN',1)").run(now);
raw.prepare("insert into promotion_events(event_id,fingerprint,state,market,airline,routes_json,prices_json,observed_at,updated_at,constraint_json) values('promo-flight','fp-flight','DISCOVERED','TW','MM','[\"TPE-KIX\"]','[]',?,?,?)").run(now,now,JSON.stringify({eligible_flight_numbers:['MM627']}));
raw.prepare("insert into candidate_priority_queue(queue_id,signal_type,signal_id,required_verification,priority_score,route_scope_json,source_evidence_id,state,attempts,available_at,first_observed_at,last_observed_at,created_at,updated_at) values('promotion:promo-flight','PROMOTION','promo-flight','LIVE_REPRICE',90,'[\"TPE-KIX\"]','obs-flight','PENDING',0,?,?,?,?,?)").run(now,now,now,now,now);
raw.prepare("insert into search_campaigns(campaign_id,profile_id,provider_id,origin_airports_json,destination_airports_json,departure_dates_json,trip_lengths_json,passengers_json,max_queries_per_signal,enabled,expires_at,created_at,updated_at) values('camp','synthetic','p1','[\"TPE\"]','[\"KIX\"]','[\"2026-11-02\"]','[3]','[{\"type\":\"adult\"}]',2,1,'2026-12-31T00:00:00Z',?,?)").run(now,now);
raw.prepare("insert into verification_jobs(job_id,job_type,target_class,payload_json,state,attempts,available_at,created_at,provider_id,query_fingerprint,provider_mode) values('job','LIVE_REPRICE','PROVIDER_API','{}','PENDING',0,?,?, 'p1',?,'USER_REQUEST')").run(now,now,qfp);
raw.prepare("insert into provider_search_plans(plan_id,campaign_id,queue_id,provider_id,query_fingerprint,query_json,state,provider_job_id,attempts,next_attempt_at,created_at,updated_at) values('plan','camp','promotion:promo-flight','p1',?,'{}','DISPATCHED','job',1,?,?,?)").run(qfp,now,now,now);
raw.prepare("insert into provider_job_consumers(job_id,plan_id,queue_id,created_at) values('job','plan','promotion:promo-flight',?)").run(now);
const structure=(flight)=>({slices:[{segments:[{origin:'TPE',destination:'KIX',departing_at:'2026-11-02T01:00:00Z',arriving_at:'2026-11-02T04:00:00Z',marketing_carrier:'MM',flight_number:flight}]}]});
await ingestOfferSnapshot(db,{provider_offer_id:'offer-wrong',query_fingerprint:qfp,provider:'p1',currency:'TWD',observed_at:'2026-09-15T00:01:00Z',expires_at:'2026-09-15T04:00:00Z',raw_sha256:'1'.repeat(64),source_snapshot_id:'job',offer_total:3999,fare_freshness:'LIVE',cached_or_live:'LIVE',offer_structure:structure('999')});
const mismatchProjection=await projectProviderJobResults(db,'job','2026-09-15T00:02:00Z');
const mismatch=raw.prepare("select verification_state,reason,best_offer_id,best_offer_total,live_offer_count,provider_count from candidate_verification_results where queue_id='promotion:promo-flight'").get();
const queueAfterMismatch=raw.prepare("select state from candidate_priority_queue where queue_id='promotion:promo-flight'").get().state;
await ingestOfferSnapshot(db,{provider_offer_id:'offer-right',query_fingerprint:qfp,provider:'p1',currency:'TWD',observed_at:'2026-09-15T00:03:00Z',expires_at:'2026-09-15T04:00:00Z',raw_sha256:'2'.repeat(64),source_snapshot_id:'job',offer_total:4200,fare_freshness:'LIVE',cached_or_live:'LIVE',offer_structure:structure('627')});
const eligibleProjection=await projectProviderJobResults(db,'job','2026-09-15T00:04:00Z');
const eligible=raw.prepare("select verification_state,reason,best_offer_id,best_offer_total,live_offer_count,provider_count from candidate_verification_results where queue_id='promotion:promo-flight'").get();
const queueAfterEligible=raw.prepare("select state from candidate_priority_queue where queue_id='promotion:promo-flight'").get().state;
raw.prepare("update promotion_events set constraint_json=? where event_id='promo-flight'").run(JSON.stringify({eligible_flight_numbers:['MM627'],sales_currency:'JPY'}));
await projectProviderJobResults(db,'job','2026-09-15T00:05:00Z');
const currencyMismatch=raw.prepare("select verification_state,reason,best_offer_id,live_offer_count from candidate_verification_results where queue_id='promotion:promo-flight'").get();
raw.prepare("update promotion_events set constraint_json=? where event_id='promo-flight'").run(JSON.stringify({eligible_flight_numbers:['MM627'],sales_currency:'TWD',coupon_required:true}));
await projectProviderJobResults(db,'job','2026-09-15T00:06:00Z');
const couponUnverified=raw.prepare("select verification_state,reason,best_offer_id,live_offer_count from candidate_verification_results where queue_id='promotion:promo-flight'").get();
console.log(JSON.stringify({mismatchProjection,mismatch,queueAfterMismatch,eligibleProjection,eligible,queueAfterEligible,currencyMismatch,couponUnverified}));
