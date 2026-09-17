import { DatabaseSync } from 'node:sqlite'; import fs from 'node:fs';
import { enqueueCandidateSignal, leaseCandidateSignals } from '../dist/priority.js';
import { recordProviderRuntimeReadback, providerReady } from '../dist/provider_runtime.js';
class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:'); for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8')); raw.exec(fs.readFileSync(new URL('../generated/seed.generated.sql',import.meta.url),'utf8')); const db=new DB(raw);
await enqueueCandidateSignal(db,{signal_type:'PROMOTION',signal_id:'promo1',required_verification:'LIVE_REPRICE',priority_score:80,route_scope:['TPE-KIX'],source_evidence_id:'obs1',observed_at:'2026-09-15T00:00:00Z'},'2026-09-15T00:00:00Z');
await enqueueCandidateSignal(db,{signal_type:'AGENCY_CLEARANCE',signal_id:'agency1',required_verification:'SELLER_RECHECK',priority_score:90,route_scope:['TPE-OKA'],source_evidence_id:'obs2',observed_at:'2026-09-15T00:00:00Z'},'2026-09-15T00:00:00Z');
const rb=await recordProviderRuntimeReadback(db,{provider_id:'duffel',worker_id:'pw1',connector_version:'test-1',credentials_present:true,capabilities:['LIVE_REPRICE'],ttl_seconds:300},'2026-09-15T00:00:00Z');
const before=await providerReady(db,{provider_id:'duffel',worker_id:'pw1',verification_type:'LIVE_REPRICE'},'2026-09-15T00:00:01Z');
raw.prepare("update provider_access_registry set connector_state='IMPLEMENTED',terms_snapshot_at='2026-09-15T00:00:00Z',supported_verification_json='[\"LIVE_REPRICE\"]',kill_switch_state='CLEAR' where provider_id='duffel'").run();
const ready=await providerReady(db,{provider_id:'duffel',worker_id:'pw1',verification_type:'LIVE_REPRICE'},'2026-09-15T00:00:02Z');
const seller=await providerReady(db,{provider_id:'duffel',worker_id:'pw1',verification_type:'SELLER_RECHECK'},'2026-09-15T00:00:02Z');
const leased=ready.ready?await leaseCandidateSignals(db,'2026-09-15T00:00:03Z','pw1',5,90,'LIVE_REPRICE'):[];
const expired=await providerReady(db,{provider_id:'duffel',worker_id:'pw1',verification_type:'LIVE_REPRICE'},'2026-09-15T00:06:00Z');
console.log(JSON.stringify({rb,before,ready,seller,leased:leased.map(x=>({signal_type:x.signal_type,required_verification:x.required_verification})),expired,pendingAgency:raw.prepare("select count(*) n from candidate_priority_queue where signal_type='AGENCY_CLEARANCE' and state='PENDING'").get().n}));
