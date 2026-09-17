import { DatabaseSync } from 'node:sqlite'; import fs from 'node:fs';
import { upsertFourLegCycle, transitionFourLegCycle, fourLegLiabilitySummary } from '../dist/four_leg.js';
class Stmt{constructor(s){this.s=s;this.args=[]}bind(...x){this.args=x;return this}async run(){return{success:true,meta:this.s.run(...this.args)}}async first(){return this.s.get(...this.args)??null}async all(){return{results:this.s.all(...this.args)}}}
class DB{constructor(x){this.x=x}prepare(q){return new Stmt(this.x.prepare(q))}async batch(a){this.x.exec('BEGIN');try{const o=[];for(const s of a)o.push(await s.run());this.x.exec('COMMIT');return o}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const db=new DB(raw);
raw.prepare("insert into itinerary_candidates(itinerary_id,strategy_type,cash_trip_cost_twd,cost_complete,risk_class,verification_state,updated_at) values('i4','S14_FOREIGN_ORIGIN_FOUR_LEG',NULL,0,'MEDIUM','PROBABLE','2026-09-15T00:00:00Z')").run();
for(const r of [['p','POSITIONING',2500,2500,0],['m','MAIN_TICKET',8000,6000,1000],['t','TAIL_RETURN',1800,1800,0],['h','HOTEL',1200,600,600]]) raw.prepare("insert into four_leg_liabilities(liability_id,itinerary_id,cycle_id,component_type,amount,paid_state,refundable,remaining_exposure,recoverable_amount) values(?,'i4','c4',?,?,'PAID',0,?,?)").run(...r);
const created=await upsertFourLegCycle(db,{cycle_id:'c4',itinerary_id:'i4'},'2026-09-15T00:00:00Z');
const before=await fourLegLiabilitySummary(db,'c4');
let illegal='';try{await transitionFourLegCycle(db,{cycle_id:'c4',to_state:'LEG1_FLOWN'},'2026-09-15T00:01:00Z')}catch(e){illegal=e.message}
const sequence=[];for(const s of ['POSITIONING_BOOKED','AT_EXTERNAL_ORIGIN','LEG1_FLOWN','HOME_STOPOVER','MAIN_TRIP_ACTIVE','LEG3_FLOWN','TAIL_PENDING','CYCLE_COMPLETED']) sequence.push(await transitionFourLegCycle(db,{cycle_id:'c4',to_state:s},'2026-09-15T00:02:00Z'));
const after=await fourLegLiabilitySummary(db,'c4');
let terminal='';try{await transitionFourLegCycle(db,{cycle_id:'c4',to_state:'BROKEN',reason:'late'},'2026-09-15T00:03:00Z')}catch(e){terminal=e.message}
raw.prepare("insert into itinerary_candidates(itinerary_id,strategy_type,cash_trip_cost_twd,cost_complete,risk_class,verification_state,updated_at) values('i5','S14',NULL,0,'MEDIUM','PROBABLE','2026-09-15T00:00:00Z')").run();await upsertFourLegCycle(db,{cycle_id:'c5',itinerary_id:'i5'},'2026-09-15T00:00:00Z');const broken=await transitionFourLegCycle(db,{cycle_id:'c5',to_state:'BROKEN',reason:'POSITIONING_MISSED'},'2026-09-15T00:01:00Z');
console.log(JSON.stringify({created,before,illegal,sequence:sequence.map(x=>x.to),after,terminal,broken,state:raw.prepare("select state,broken_reason from four_leg_cycles where cycle_id='c5'").get()}));
