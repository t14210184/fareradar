import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { persistCandidatePlan } from '../dist/intake.js';

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
const migration=fs.readFileSync(new URL('../migrations/0001_core.sql',import.meta.url),'utf8');
const payload=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const raw=new DatabaseSync(':memory:'); raw.exec(migration); const db=new DB(raw);
const r1=await persistCandidatePlan(db,payload,'2026-09-15T00:00:00Z');
const r2=await persistCandidatePlan(db,payload,'2026-09-15T00:01:00Z');
const counts={}; for(const t of ['itinerary_candidates','candidate_plan_intakes','ticket_components','transfer_boundaries','cost_components','readiness_facets','document_requirements','four_leg_liabilities']) counts[t]=raw.prepare(`select count(*) n from ${t}`).get().n;
let conflict=false; const changed=structuredClone(payload); changed.itinerary.cash_trip_cost_twd=9999; try{await persistCandidatePlan(db,changed)}catch(e){conflict=String(e).includes('IDEMPOTENCY_CONFLICT')}
console.log(JSON.stringify({r1,r2,counts,conflict}));
