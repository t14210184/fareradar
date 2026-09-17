import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { enqueueCandidateSignal } from '../dist/priority.js';
import { ingestOfferSnapshot } from '../dist/offers.js';
import { enqueueProviderSearch, completeProviderJob } from '../dist/provider_jobs.js';
import { upsertRuntimeProfile } from '../dist/profile.js';
import { expireLiveProviderOffers } from '../dist/offer_lifecycle.js';

class Stmt {
  constructor(s, counter){ this.s=s; this.args=[]; this.counter=counter; }
  bind(...v){ this.args=v; return this; }
  async run(){ this.counter.n++; return {success:true,meta:this.s.run(...this.args)}; }
  async first(){ this.counter.n++; return this.s.get(...this.args)??null; }
  async all(){ this.counter.n++; return {results:this.s.all(...this.args)}; }
}
class DB {
  constructor(db){ this.db=db; this.counter={n:0}; }
  prepare(sql){ return new Stmt(this.db.prepare(sql),this.counter); }
  async batch(stmts){ this.db.exec('BEGIN IMMEDIATE'); try { const o=[]; for(const s of stmts)o.push(await s.run()); this.db.exec('COMMIT'); return o; } catch(e){ this.db.exec('ROLLBACK'); throw e; } }
}
const raw=new DatabaseSync(':memory:');
for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));
const db=new DB(raw);
const provider='airline:test';
raw.prepare("insert into source_registry(source_id,source_class,canonical_domain_or_account,access_basis,fetch_method,lifecycle_state,verification_authority,terms_snapshot_at,min_interval_ms,kill_switch) values('src-live','OFFICIAL_PROMOTION','airline.test','PUBLIC_OFFICIAL_PAGE','WEBHOOK','SHADOW','HIGH','2026-09-15T00:00:00Z',300000,0)").run();
raw.prepare("insert into source_observations(observation_id,source_id,observed_at,canonical_url,content_sha256,parser_version,access_basis,privacy_class,access_basis_snapshot,retention_until,content_version) values('obs-live','src-live','2026-09-15T00:00:00Z','https://airline.test/promo',?,'test','PUBLIC_OFFICIAL_PAGE','PUBLIC','PUBLIC_OFFICIAL_PAGE','2026-12-15T00:00:00Z',1)").run('a'.repeat(64));
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner,connector_state,supported_verification_json,credential_binding,background_allowed) values(?, 'OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','airline','IMPLEMENTED','[\"LIVE_REPRICE\"]','TEST_TOKEN',1)").run(provider);
await upsertRuntimeProfile(db,{profile_id:'synthetic',home_city:'Synthetic',home_airports:['TPE'],checked_bag_pattern:'NONE',baggage_kg:0,seat_required:false,red_eye_ok:true,self_transfer_ok:true,overnight_transfer_ok:false,airport_change_ok:false,mainland_permit_status:'UNKNOWN',korea_entry_profile:'CHECK_AT_QUERY_TIME',foreign_origin_ok:true,positioning_cost_attribution:'FULL',max_positioning_cost_twd:2500,value_of_time_twd_per_hour:300,min_savings_for_self_transfer_twd:2500,currency:'TWD'},'2026-09-15T00:00:00Z');
await enqueueCandidateSignal(db,{signal_type:'PROMOTION',signal_id:'promo-live-expiry',required_verification:'LIVE_REPRICE',priority_score:95,route_scope:['TPE-KIX'],source_evidence_id:'obs-live',observed_at:'2026-09-15T00:00:00Z'},'2026-09-15T00:00:00Z');
const queueId='promotion:promo-live-expiry';
const query={slices:[{origin:'TPE',destination:'KIX',departure_date:'2026-11-02'},{origin:'KIX',destination:'TPE',departure_date:'2026-11-05'}],passengers:[{type:'adult'}],cabin_class:'economy',max_connections:0};
const original=await enqueueProviderSearch(db,{provider_id:provider,mode:'USER_REQUEST',query},'2026-09-15T00:00:00Z');
const qfp=original.query_fingerprint;
raw.prepare("insert into search_campaigns(campaign_id,profile_id,provider_id,origin_airports_json,destination_airports_json,departure_dates_json,trip_lengths_json,passengers_json,max_queries_per_signal,enabled,expires_at,created_at,updated_at) values('c-live','synthetic',?,'[\"TPE\"]','[\"KIX\"]','[\"2026-11-02\"]','[3]','[{\"type\":\"adult\"}]',1,1,'2026-12-31T00:00:00Z','2026-09-15T00:00:00Z','2026-09-15T00:00:00Z')").run(provider);
raw.prepare("insert into provider_search_plans(plan_id,campaign_id,queue_id,provider_id,query_fingerprint,query_json,state,provider_job_id,attempts,next_attempt_at,created_at,updated_at) values('plan-live','c-live',?,?,?,?,'DISPATCHED',?,1,'2026-09-15T00:00:00Z','2026-09-15T00:00:00Z','2026-09-15T00:00:00Z')").run(queueId,provider,qfp,JSON.stringify(query),original.job_id);
raw.prepare("insert into provider_job_consumers(job_id,plan_id,queue_id,created_at) values(?,'plan-live',?,'2026-09-15T00:00:00Z')").run(original.job_id,queueId);
raw.prepare("update verification_jobs set state='LEASED',attempts=1,claimed_by='worker-airline',lease_until='2026-09-15T00:10:00Z' where job_id=?").run(original.job_id);
const structure={slices:[{segments:[{origin:'TPE',destination:'KIX',departing_at:'2026-11-02T01:00:00Z',arriving_at:'2026-11-02T03:30:00Z',marketing_carrier:'TT',operating_carrier:'TT',flight_number:'101'}]},{segments:[{origin:'KIX',destination:'TPE',departing_at:'2026-11-05T08:00:00Z',arriving_at:'2026-11-05T11:00:00Z',marketing_carrier:'TT',operating_carrier:'TT',flight_number:'102'}]}]};
await ingestOfferSnapshot(db,{provider_offer_id:'offer-live-old',query_fingerprint:qfp,provider,currency:'TWD',observed_at:'2026-09-15T00:01:00Z',expires_at:'2026-09-15T01:00:00+00:00',raw_sha256:'b'.repeat(64),source_snapshot_id:original.job_id,offer_total:4999,fare_freshness:'LIVE',cached_or_live:'LIVE',offer_structure:structure});
await completeProviderJob(db,{job_id:original.job_id,provider_id:provider,worker_id:'worker-airline',success:true},'2026-09-15T00:02:00Z');
const verifiedBefore=raw.prepare("select result_id,verification_state,best_offer_id from candidate_verification_results where queue_id=? and query_fingerprint=?").get(queueId,qfp);
const supportBefore=raw.prepare("select provider_offer_id,support_role from candidate_verification_supports where result_id=? order by provider_offer_id").all(verifiedBefore.result_id);
const itineraryId=raw.prepare("select itinerary_id from itinerary_candidates").get().itinerary_id;
raw.prepare("insert into candidate_alert_intents(intent_id,itinerary_id,alert_class,payload_json,projected_at,created_at) values('deal-before',?,'DEAL','{\"kind\":\"P0-COMPLEX\"}','2026-09-15T00:03:00Z','2026-09-15T00:03:00Z')").run(itineraryId);
raw.prepare("insert into notification_outbox(notification_id,channel_class,payload_json,state,attempts,created_at) values('deal-before','DEAL','{\"kind\":\"P0-COMPLEX\"}','DELIVERED',1,'2026-09-15T00:03:00Z')").run();
raw.prepare("insert into candidate_alert_intents(intent_id,itinerary_id,alert_class,payload_json,projected_at,created_at) values('deal-pending',?,'DEAL','{\"kind\":\"P0-COMPLEX\"}','2026-09-15T00:03:30Z','2026-09-15T00:03:30Z')").run(itineraryId);
raw.prepare("insert into notification_outbox(notification_id,channel_class,payload_json,state,attempts,created_at) values('deal-pending','DEAL','{\"kind\":\"P0-COMPLEX\"}','PENDING',0,'2026-09-15T00:03:30Z')").run();
raw.prepare("insert into candidate_alert_intents(intent_id,itinerary_id,alert_class,payload_json,created_at) values('deal-unprojected',?,'DEAL','{\"kind\":\"P0-COMPLEX\"}','2026-09-15T00:03:40Z')").run(itineraryId);
const beforeExpiryQueries=db.counter.n;
const expiry=await expireLiveProviderOffers(db,'2026-09-15T01:00:01Z',1);
const expiryQueries=db.counter.n-beforeExpiryQueries;
const verifiedExpired=raw.prepare("select verification_state,reason,best_offer_id,live_offer_count,provider_count from candidate_verification_results where result_id=?").get(verifiedBefore.result_id);
const supportExpired=raw.prepare("select provider_offer_id from candidate_verification_supports where result_id=?").all(verifiedBefore.result_id);
const fareFacetExpired=raw.prepare("select status,reason_code,evidence_id from readiness_facets where itinerary_id=? and facet_type='FARE_VERIFIED'").get(itineraryId);
const lifecycle=raw.prepare("select event_id,reason,effective_at,had_visible_notification,correction_state,reprice_state,last_error from live_offer_lifecycle_events where result_id=?").get(verifiedBefore.result_id);
const correction=raw.prepare("select intent_id,payload_json from candidate_alert_intents where intent_id like 'live-offer-expiry:%'").get();
const refreshJobs=raw.prepare("select job_id,state,provider_id,query_fingerprint,payload_json from verification_jobs where job_id<>? order by created_at,job_id").all(original.job_id);
const refreshConsumers=raw.prepare("select job_id,plan_id,queue_id from provider_job_consumers where job_id<>?").all(original.job_id);
const oldNotice=raw.prepare("select state,last_error from notification_outbox where notification_id='deal-before'").get();
const pendingNotice=raw.prepare("select state,last_error from notification_outbox where notification_id='deal-pending'").get();
const unprojected=raw.prepare("select projected_at from candidate_alert_intents where intent_id='deal-unprojected'").get();
const replay=await expireLiveProviderOffers(db,'2026-09-15T01:00:02Z',1);
if(refreshJobs.length!==1) throw new Error(`EXPECTED_ONE_REFRESH_JOB:${refreshJobs.length}`);
const refreshJob=refreshJobs[0];
raw.prepare("update verification_jobs set state='LEASED',attempts=1,claimed_by='worker-airline',lease_until='2026-09-15T01:10:00Z' where job_id=?").run(refreshJob.job_id);
await ingestOfferSnapshot(db,{provider_offer_id:'offer-live-new',query_fingerprint:qfp,provider,currency:'TWD',observed_at:'2026-09-15T01:01:00Z',expires_at:'2026-09-15T03:00:00Z',raw_sha256:'c'.repeat(64),source_snapshot_id:refreshJob.job_id,offer_total:5199,fare_freshness:'LIVE',cached_or_live:'LIVE',offer_structure:structure});
const refreshed=await completeProviderJob(db,{job_id:refreshJob.job_id,provider_id:provider,worker_id:'worker-airline',success:true},'2026-09-15T01:02:00Z');
const verifiedAfter=raw.prepare("select verification_state,reason,best_offer_id,best_offer_total,live_offer_count,provider_count from candidate_verification_results where result_id=?").get(verifiedBefore.result_id);
const supportAfter=raw.prepare("select provider_offer_id,support_role from candidate_verification_supports where result_id=?").all(verifiedBefore.result_id);
const fareFacetAfter=raw.prepare("select status,reason_code,evidence_id,expires_at from readiness_facets where itinerary_id=? and facet_type='FARE_VERIFIED'").get(itineraryId);
const costAfter=raw.prepare("select amount,source_offer_id,evidence_expires_at from cost_components where itinerary_id=? and type='OFFER_TOTAL'").get(itineraryId);
console.log(JSON.stringify({verifiedBefore,supportBefore,expiry,expiryQueries,verifiedExpired,supportExpired,fareFacetExpired,lifecycle,correction:{intent_id:correction?.intent_id??null,payload:correction?JSON.parse(correction.payload_json):null},refreshJobs,refreshConsumers,oldNotice,pendingNotice,unprojected,replay,refreshed,verifiedAfter,supportAfter,fareFacetAfter,costAfter}));
