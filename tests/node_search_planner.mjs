import { DatabaseSync } from 'node:sqlite'; import fs from 'node:fs';
import { enqueueCandidateSignal } from '../dist/priority.js';
import { upsertSearchCampaign, planDueCandidateSearches, dispatchProviderSearchPlans } from '../dist/search_planner.js';
class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));raw.exec(fs.readFileSync(new URL('../generated/seed.generated.sql',import.meta.url),'utf8'));const db=new DB(raw);
raw.prepare("insert into promotion_events(event_id,fingerprint,state,market,airline,routes_json,prices_json,promo_code,observed_at,updated_at,travel_window) values('promo1','fp1','DISCOVERED','TW','TEST','[\"TPE-KIX\"]','[]',NULL,'2026-09-15T00:00:00Z','2026-09-15T00:00:00Z','{\"start\":\"2026-11-01\",\"end\":\"2026-11-10\"}')").run();
await enqueueCandidateSignal(db,{signal_type:'PROMOTION',signal_id:'promo1',required_verification:'LIVE_REPRICE',priority_score:80,route_scope:['TPE-KIX'],source_evidence_id:'obs-synthetic',observed_at:'2026-09-15T00:00:00Z'},'2026-09-15T00:00:00Z');
await upsertSearchCampaign(db,{campaign_id:'campaign-synthetic',profile_id:'synthetic-private-profile',provider_id:'duffel',origin_airports:['TPE'],destination_airports:['KIX'],departure_dates:['2026-10-31','2026-11-02','2026-11-09'],trip_lengths_nights:[3,7],passengers:[{type:'adult'}],cabin_class:'economy',max_connections:1,market:'TW',locale:'zh-TW',max_queries_per_signal:3,enabled:true,expires_at:'2026-12-31T00:00:00Z'},'2026-09-15T00:00:00Z');
const planned=await planDueCandidateSearches(db,'2026-09-15T00:01:00Z',8,4);
const plansBefore=raw.prepare("select plan_id,query_json,state from provider_search_plans order by query_json").all();
const deferred=await dispatchProviderSearchPlans(db,'2026-09-15T00:02:00Z',2);
raw.prepare("update provider_access_registry set terms_snapshot_at='2026-09-15T00:00:00Z',background_allowed=1 where provider_id='duffel'").run();
const dispatched=await dispatchProviderSearchPlans(db,'2026-09-15T01:03:00Z',2);
const plansAfter=raw.prepare("select state,provider_job_id,last_error from provider_search_plans order by plan_id").all();
const jobs=raw.prepare("select target_class,provider_mode,provider_id,payload_json from verification_jobs where target_class='PROVIDER_API' order by job_id").all();
const consumers=raw.prepare("select count(*) n from provider_job_consumers").get().n;
console.log(JSON.stringify({planned,plansBefore:plansBefore.map(x=>({state:x.state,query:JSON.parse(x.query_json)})),deferred,dispatched,plansAfter,jobs:jobs.map(x=>({target_class:x.target_class,provider_mode:x.provider_mode,provider_id:x.provider_id,query:JSON.parse(x.payload_json).query})),consumers}));
