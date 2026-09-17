import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import worker from '../dist/worker.js';
import { ingestOfferSnapshot } from '../dist/offers.js';
import { installKey, authEnv, signedRequest } from './scoped_auth_helper.mjs';
class Stmt{constructor(s,c){this.s=s;this.c=c;this.a=[]}bind(...a){this.a=a;return this}async run(){this.c.n++;return{success:true,meta:this.s.run(...this.a)}}async first(){this.c.n++;return this.s.get(...this.a)??null}async all(){this.c.n++;return{results:this.s.all(...this.a)}}}
class DB{constructor(x,c){this.x=x;this.c=c}prepare(q){return new Stmt(this.x.prepare(q),this.c)}async batch(a){this.x.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of a)o.push(await s.run());this.x.exec('COMMIT');return o}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const counter={n:0};const db=new DB(raw,counter);
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner) values('test-provider','OFFICIAL_API','2026-09-01T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test')").run();
await ingestOfferSnapshot(db,{provider_offer_id:'off1',query_fingerprint:'q1',provider:'test-provider',currency:'TWD',observed_at:'2026-09-15T00:00:00Z',expires_at:'2026-09-15T12:00:00Z',raw_sha256:'f'.repeat(64),offer_total:5000,fare_freshness:'LIVE',cached_or_live:'LIVE'});counter.n=0;
const secret='budget-secret-0123456789';installKey(raw,{keyId:'budget-key',secretSlot:'test-slot',allowedPaths:['/candidate-plan/']});const env=authEnv(db,secret);
const base=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
function maxPlan(extraLiability=false){const p=structuredClone(base);p.intake_id=extraLiability?'intake-budget-over':'intake-budget-ok';p.itinerary.itinerary_id=extraLiability?'itin-budget-over':'itin-budget-ok';p.itinerary.verification_state='CONFIRMED';
 p.tickets=[];for(let i=0;i<8;i++){const t=structuredClone(base.tickets[0]);t.ticket_id=`tb-${i}`;t.pnr_group=`pb-${i}`;p.tickets.push(t)}
 p.transfers=[];p.costs=[];for(let i=0;i<16;i++){const c=structuredClone(base.costs[0]);c.cost_id=`cb-${i}`;c.dedupe_key=`db-${i}`;c.source_offer_id='off1';c.policy_evidence_id=null;c.source_evidence_id=null;p.costs.push(c)}
 p.documents=[];for(let i=0;i<8;i++){const d=structuredClone(base.documents[0]);d.document_id=`docb-${i}`;p.documents.push(d)}
 p.four_leg_liabilities=[];for(let i=0;i<(extraLiability?5:4);i++)p.four_leg_liabilities.push({liability_id:`lb-${i}`,cycle_id:`cycle-${i}`,component_type:'TAIL_RETURN',amount:100,paid_state:'UNPAID',refundable:false,remaining_exposure:100,recoverable_amount:0});
 p.discovery_evidence_ids=['obs-budget'];return p;}
async function send(p,nonce){const body=JSON.stringify(p);return worker.fetch(await signedRequest('https://fare.example/candidate-plan/intake',body,{keyId:'budget-key',secret,nonce}),env)}
counter.n=0;const okRes=await send(maxPlan(false),'nonce-budget-ok-abcdef');const ok=await okRes.json();const okQueries=counter.n;
counter.n=0;const overRes=await send(maxPlan(true),'nonce-budget-over-abcdef');const over=await overRes.json();const overQueries=counter.n;
console.log(JSON.stringify({ok_status:okRes.status,ok_statements:ok.statements,ok_queries:okQueries,over_status:overRes.status,over_error:over.error,over_queries:overQueries,intakes:raw.prepare('select count(*) n from candidate_plan_intakes').get().n}));
