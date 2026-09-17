import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { ingestSourceObservation, projectDomainEvents } from '../dist/ingest.js';
import { evaluatePromotionBurst } from '../dist/social_heat.js';

class S{constructor(s){this.s=s;this.a=[]}bind(...a){this.a=a;return this}async run(){return{success:true,meta:this.s.run(...this.a)}}async first(){return this.s.get(...this.a)??null}async all(){return{results:this.s.all(...this.a)}}}
class D{constructor(x){this.x=x}prepare(q){return new S(this.x.prepare(q))}async batch(a){this.x.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of a)o.push(await s.run());this.x.exec('COMMIT');return o}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');
for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));
const db=new D(raw),now='2026-09-21T00:10:00Z';
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,kill_switch_state,owner) values('p','OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY','CLEAR','test')").run();
raw.prepare("insert into runtime_profiles(profile_id,home_city,home_airports_json,checked_bag_pattern,baggage_kg,seat_required,red_eye_ok,self_transfer_ok,overnight_transfer_ok,airport_change_ok,mainland_permit_status,korea_entry_profile,foreign_origin_ok,positioning_cost_attribution,max_positioning_cost_twd,value_of_time_twd_per_hour,min_savings_for_self_transfer_twd,currency,created_at,updated_at) values('prof','Taipei','[\"TPE\"]','NONE',0,0,1,1,1,1,'UNKNOWN','UNKNOWN',1,'FULL',10000,300,2000,'TWD',?,?)").run(now,now);
raw.prepare("insert into search_campaigns(campaign_id,profile_id,provider_id,origin_airports_json,destination_airports_json,departure_dates_json,trip_lengths_json,passengers_json,market,max_queries_per_signal,enabled,expires_at,created_at,updated_at) values('camp','prof','p','[\"TPE\"]','[\"KIX\"]','[\"2026-11-03\"]','[3]','[{\"type\":\"adult\"}]','TW',2,1,'2026-12-31T00:00:00Z',?,?)").run(now,now);
function source(id,domain,state='ENABLED',terms='2026-09-15T00:00:00Z',trust='MEDIUM'){
  raw.prepare("insert into source_registry(source_id,source_class,canonical_domain_or_account,access_basis,fetch_method,lifecycle_state,verification_authority,terms_snapshot_at,min_interval_ms,kill_switch,discovery_trust,kill_switch_state) values(?, 'SOCIAL',?,'PUBLIC','PUSH',?,'DISCOVERY',?,300000,0,?,'CLEAR')").run(id,domain,state,terms,trust);
}
source('s1','one.example','ENABLED','2026-09-15T00:00:00Z','HIGH');source('s2','two.example');source('s3','three.example');source('s4','one.example');source('shadow','shadow.example','SHADOW');source('stale','stale.example','ENABLED','RECHECK_REQUIRED');
const signal={market:'TW',airline:'XX',routes:['TPE-KIX'],prices:[{amount:112,currency:'TWD'}],promo_code:'BURST',travel_start:'2026-11-01',travel_end:'2026-11-30'};
async function obs(id,src,minute){await ingestSourceObservation(db,{observation_id:id,source_id:src,observed_at:`2026-09-21T00:${String(minute).padStart(2,'0')}:00Z`,canonical_url:`https://${src}.example/post`,content_sha256:String(minute%10).repeat(64),privacy_class:'PUBLIC',extraction_type:'PROMOTION_SIGNAL',structured_payload:signal},now);}
await obs('obs1','s1',1);await obs('obs2','s2',2);await projectDomainEvents(db,now,'proj-a',2);
const eventId=raw.prepare("select event_id from promotion_events where promo_code='BURST'").get().event_id;
const two=await evaluatePromotionBurst(db,eventId,now,20,3);
await obs('obs3','s3',3);await obs('obs4','s4',4);await obs('obs5','shadow',5);await obs('obs6','stale',6);await projectDomainEvents(db,now,'proj-b',2);await projectDomainEvents(db,now,'proj-c',2);
const positive=await evaluatePromotionBurst(db,eventId,now,20,3);const replay=await evaluatePromotionBurst(db,eventId,now,20,3);
const heat=raw.prepare('select independent_source_count,high_trust_source_count,heat_score,route_relevant,provisional_triggered_at from promotion_social_heat where event_id=?').get(eventId);
const priority=raw.prepare("select priority_score from candidate_priority_queue where signal_type='PROMOTION' and signal_id=?").get(eventId).priority_score;
const intents=raw.prepare("select count(*) n from candidate_alert_intents where intent_id=?").get(`provisional:burst:${eventId}`).n;
const payloadRow=raw.prepare("select payload_json from candidate_alert_intents where intent_id=?").get(`provisional:burst:${eventId}`);const payload=payloadRow?JSON.parse(payloadRow.payload_json):null;
raw.prepare("update search_campaigns set destination_airports_json='[\"NRT\"]' where campaign_id='camp'").run();
raw.prepare("insert into promotion_events(event_id,fingerprint,state,routes_json,prices_json,promo_code,observed_at,updated_at,travel_window,constraint_json,first_observed_at,last_observed_at) values('route-miss','route-miss-fp','DISCOVERED','[\"TPE-KIX\"]','[{\"amount\":112,\"currency\":\"TWD\"}]','MISS',?,?,?,?,?,?)").run(now,now,'{"start":"2026-11-01","end":"2026-11-30"}','{}',now,now);
for(const oid of ['obs1','obs2','obs3'])raw.prepare('insert into promotion_event_evidence(event_id,observation_id) values(?,?)').run('route-miss',oid);
raw.prepare("insert into candidate_priority_queue(queue_id,signal_type,signal_id,required_verification,priority_score,route_scope_json,source_evidence_id,state,attempts,available_at,first_observed_at,last_observed_at,created_at,updated_at) values('promotion:route-miss','PROMOTION','route-miss','LIVE_REPRICE',50,'[\"TPE-KIX\"]','obs1','PENDING',0,?,?,?,?,?)").run(now,now,now,now,now);
const routeMismatch=await evaluatePromotionBurst(db,'route-miss',now,20,3);
console.log(JSON.stringify({eventId,two,positive,replay,heat,priority,intents,payload,routeMismatch}));
