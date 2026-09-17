import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { ingestOfferSnapshot } from '../dist/offers.js';
import { projectDomainEvents } from '../dist/ingest.js';
import { evaluateProvisionalCandidate } from '../dist/provisional.js';

class S{constructor(s){this.s=s;this.a=[]}bind(...a){this.a=a;return this}async run(){return{success:true,meta:this.s.run(...this.a)}}async first(){return this.s.get(...this.a)??null}async all(){return{results:this.s.all(...this.a)}}}
class D{constructor(x){this.x=x}prepare(q){return new S(this.x.prepare(q))}async batch(a){this.x.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of a)o.push(await s.run());this.x.exec('COMMIT');return o}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');
for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));
const db=new D(raw);
const now='2026-09-21T00:00:00Z';
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner) values('p1','OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test')").run();
raw.prepare("insert into runtime_profiles(profile_id,home_city,home_airports_json,checked_bag_pattern,baggage_kg,seat_required,red_eye_ok,self_transfer_ok,overnight_transfer_ok,airport_change_ok,mainland_permit_status,korea_entry_profile,foreign_origin_ok,positioning_cost_attribution,max_positioning_cost_twd,value_of_time_twd_per_hour,min_savings_for_self_transfer_twd,currency,created_at,updated_at) values('prof','Taipei','[\"TPE\"]','NONE',0,0,1,1,1,1,'UNKNOWN','UNKNOWN',1,'FULL',10000,300,2000,'TWD',?,?)").run(now,now);
raw.prepare("insert into search_campaigns(campaign_id,profile_id,provider_id,origin_airports_json,destination_airports_json,departure_dates_json,trip_lengths_json,passengers_json,max_queries_per_signal,enabled,expires_at,created_at,updated_at) values('camp','prof','p1','[\"TPE\"]','[\"KIX\"]','[\"2026-11-03\"]','[3]','[{\"type\":\"adult\"}]',2,1,'2026-12-31T00:00:00Z',?,?)").run(now,now);
raw.prepare("insert into source_registry(source_id,source_class,canonical_domain_or_account,access_basis,fetch_method,lifecycle_state,verification_authority,terms_snapshot_at,min_interval_ms,kill_switch,discovery_trust,kill_switch_state) values('s-trusted','SOCIAL','example.test','PUBLIC','PUSH','ENABLED','DISCOVERY','2026-09-15T00:00:00Z',300000,0,'HIGH','CLEAR')").run();
raw.prepare("insert into source_observations(observation_id,source_id,observed_at,content_sha256,access_basis,privacy_class) values('obs-trusted','s-trusted','2026-09-20T00:00:00Z',?,'PUBLIC','PUBLIC')").run('a'.repeat(64));
const structure={slices:[{segments:[{origin:'TPE',destination:'KIX',departing_at:'2026-11-03T01:00:00Z',arriving_at:'2026-11-03T03:30:00Z'}]}]};
const bag='{"checked_bags_by_slice":[0],"checked_bag_kg":0,"seat_required":false}';
async function add(id,amount,day){await ingestOfferSnapshot(db,{provider_offer_id:id,query_fingerprint:`q-${id}`,provider:'p1',currency:'TWD',baggage_query:bag,observed_at:`2026-09-${String(day).padStart(2,'0')}T00:00:00Z`,expires_at:'2026-10-01T00:00:00Z',raw_sha256:(String(day%10)).repeat(64),offer_total:amount,fare_freshness:'REFRESHED_LIVE',cached_or_live:'LIVE',offer_structure:structure});}
for(const [i,a] of [7000,6800,7200,6900,7100].entries())await add(`hist-${i}`,a,15+i);
await add('current',4000,20);
await projectDomainEvents(db,now,'baseline-provisional',20);
raw.prepare("insert into itinerary_candidates(itinerary_id,profile_id,strategy_type,cash_trip_cost_twd,cost_complete,risk_class,verification_state,updated_at) values('itin','prof','S00_DIRECT_RT',4000,0,'LOW','PROBABLE',?)").run(now);
raw.prepare("insert into candidate_plan_intakes(intake_id,itinerary_id,payload_sha256,observed_at,discovery_evidence_json) values('intake','itin',?,?,?)").run('b'.repeat(64),now,'["obs-trusted"]');
raw.prepare("insert into cost_components(cost_id,itinerary_id,type,amount,currency,twd_amount,inclusion_state,source_offer_id,dedupe_key,certainty,paid_state,refundable,observed_at) values('cost','itin','FLIGHT',4000,'TWD',4000,'INCLUDED_IN_OFFER','current','flight','CONFIRMED','UNPAID',0,?)").run(now);
const positive=await evaluateProvisionalCandidate(db,'itin',now);
const positiveReplay=await evaluateProvisionalCandidate(db,'itin',now);
const intentCount=raw.prepare("select count(*) n from candidate_alert_intents where intent_id like 'provisional:%'").get().n;
const payload=JSON.parse(raw.prepare("select payload_json from candidate_alert_intents where intent_id like 'provisional:%'").get().payload_json);
raw.prepare("update source_registry set lifecycle_state='SHADOW' where source_id='s-trusted'").run();
const shadow=await evaluateProvisionalCandidate(db,'itin',now);
raw.prepare("update source_registry set lifecycle_state='ENABLED' where source_id='s-trusted'").run();
raw.prepare("delete from fare_baseline_observations where provider_offer_id like 'hist-%'").run();
const insufficient=await evaluateProvisionalCandidate(db,'itin',now);
for(const [i,a] of [7000,6800,7200,6900,7100].entries())await add(`hist2-${i}`,a,15+i);
await projectDomainEvents(db,now,'baseline-provisional-2',20);
raw.prepare("update search_campaigns set destination_airports_json='[\"NRT\"]' where campaign_id='camp'").run();
const routeMismatch=await evaluateProvisionalCandidate(db,'itin',now);
raw.prepare("update search_campaigns set destination_airports_json='[\"KIX\"]' where campaign_id='camp'").run();
raw.prepare("update search_campaigns set departure_dates_json='[\"2026-12-03\"]' where campaign_id='camp'").run();
const dateMismatch=await evaluateProvisionalCandidate(db,'itin',now);
raw.prepare("update search_campaigns set departure_dates_json='[\"2026-11-03\"]' where campaign_id='camp'").run();
raw.prepare("update offer_snapshots set offer_total=6000 where provider_offer_id='current'").run();
const expensive=await evaluateProvisionalCandidate(db,'itin',now);
raw.prepare("update itinerary_candidates set verification_state='CONFIRMED' where itinerary_id='itin'").run();
const confirmed=await evaluateProvisionalCandidate(db,'itin',now);
console.log(JSON.stringify({positive,positiveReplay,intentCount,payload,shadow,insufficient,routeMismatch,dateMismatch,expensive,confirmed}));
