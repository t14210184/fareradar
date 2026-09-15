import { DatabaseSync } from 'node:sqlite'; import fs from 'node:fs';
import { enqueueCandidateSignal } from '../dist/priority.js';
import { upsertSearchCampaign, planDueCandidateSearches } from '../dist/search_planner.js';
class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const db=new DB(raw);
for(const p of ['p1','p2'])raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,kill_switch_state,owner,connector_state,supported_verification_json,background_allowed) values(?,'OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY','CLEAR','test','IMPLEMENTED','[\"LIVE_REPRICE\"]',1)").run(p);
raw.prepare("insert into promotion_events(event_id,fingerprint,state,market,routes_json,observed_at,updated_at,travel_window) values('promo-seq','fp-seq','DISCOVERED','TW','[\"TPE-KIX\"]','2026-09-15T00:00:00Z','2026-09-15T00:00:00Z','{\"start\":\"2026-11-01\",\"end\":\"2026-11-10\"}')").run();
await enqueueCandidateSignal(db,{signal_type:'PROMOTION',signal_id:'promo-seq',required_verification:'LIVE_REPRICE',priority_score:90,route_scope:['TPE-KIX'],source_evidence_id:'obs',observed_at:'2026-09-15T00:00:00Z'},'2026-09-15T00:00:00Z');
for(const [id,p] of [['c1','p1'],['c2','p2']])await upsertSearchCampaign(db,{campaign_id:id,profile_id:'synthetic',provider_id:p,origin_airports:['TPE'],destination_airports:['KIX'],departure_dates:['2026-11-02'],trip_lengths_nights:[3],passengers:[{type:'adult'}],max_queries_per_signal:1,enabled:true,expires_at:'2026-12-31T00:00:00Z'},'2026-09-15T00:00:00Z');
const first=await planDueCandidateSearches(db,'2026-09-15T00:01:00Z',8,4);
const second=await planDueCandidateSearches(db,'2026-09-15T00:02:00Z',8,4);
const third=await planDueCandidateSearches(db,'2026-09-15T00:03:00Z',8,4);
console.log(JSON.stringify({first,second,third,campaigns:raw.prepare("select campaign_id from provider_search_plans order by campaign_id").all().map(x=>x.campaign_id)}));
