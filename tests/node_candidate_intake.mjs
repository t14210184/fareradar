import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { persistCandidatePlan } from '../dist/intake.js';
import { ingestOfferSnapshot } from '../dist/offers.js';

class Stmt {
  constructor(s){this.s=s;this.args=[]}
  bind(...v){this.args=v;return this}
  async run(){const r=this.s.run(...this.args);return {success:true,meta:r}}
  async first(){return this.s.get(...this.args)??null}
  async all(){return {results:this.s.all(...this.args)}}
}
class DB {
  constructor(db){this.db=db}
  prepare(sql){return new Stmt(this.db.prepare(sql))}
  async batch(stmts){
    this.db.exec('BEGIN IMMEDIATE');
    try { const out=[]; for(const s of stmts) out.push(await s.run()); this.db.exec('COMMIT'); return out; }
    catch(e){ this.db.exec('ROLLBACK'); throw e; }
  }
}
const raw=new DatabaseSync(':memory:'); for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8')); const db=new DB(raw);
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner) values('test-provider','OFFICIAL_API','2026-09-01T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test')").run();
await ingestOfferSnapshot(db,{provider_offer_id:'off1',query_fingerprint:'q1',provider:'test-provider',currency:'TWD',observed_at:'2026-09-15T00:00:00Z',expires_at:'2026-09-15T12:00:00Z',raw_sha256:'f'.repeat(64),offer_total:5000,fare_freshness:'LIVE',cached_or_live:'LIVE'});
const payload=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const r1=await persistCandidatePlan(db,payload,'2026-09-15T00:00:00Z');
const r2=await persistCandidatePlan(db,payload,'2026-09-15T00:01:00Z');
const counts={}; for(const t of ['itinerary_candidates','candidate_plan_intakes','ticket_components','transfer_boundaries','cost_components','readiness_facets','document_requirements','four_leg_liabilities']) counts[t]=raw.prepare(`select count(*) n from ${t}`).get().n;
let conflict=false; const changed=structuredClone(payload); changed.itinerary.cash_trip_cost_twd=9999; try{await persistCandidatePlan(db,changed)}catch(e){conflict=String(e).includes('IDEMPOTENCY_CONFLICT')}
let missingRefBlocked=false; const missing=structuredClone(payload); missing.intake_id='intake-missing'; missing.itinerary.itinerary_id='itin-missing'; for(const c of missing.costs)c.source_offer_id='missing-offer'; try{await persistCandidatePlan(db,missing)}catch(e){missingRefBlocked=String(e).includes('SOURCE_OFFER_NOT_FOUND')}
console.log(JSON.stringify({r1,r2,counts,conflict,missingRefBlocked}));
