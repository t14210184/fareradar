import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import worker from '../dist/worker.js';
import { ingestOfferSnapshot } from '../dist/offers.js';
import { installKey, authEnv, signedRequest } from './scoped_auth_helper.mjs';

class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:'); for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8')); const db=new DB(raw);
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner) values('test-provider','OFFICIAL_API','2026-09-01T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test')").run();
await ingestOfferSnapshot(db,{provider_offer_id:'off1',query_fingerprint:'q1',provider:'test-provider',currency:'TWD',observed_at:'2026-09-15T00:00:00Z',expires_at:'2026-09-15T12:00:00Z',raw_sha256:'f'.repeat(64),offer_total:5000,fare_freshness:'LIVE',cached_or_live:'LIVE'});
const body=fs.readFileSync(process.argv[2],'utf8'); const secret='test-secret-0123456789';
installKey(raw,{allowedPaths:['/candidate-plan/']}); const env=authEnv(db,secret);
const req=await signedRequest('https://fare.example/candidate-plan/intake',body,{secret});
const res=await worker.fetch(req,env); const payload=await res.json();
const bad=await signedRequest('https://fare.example/candidate-plan/intake',body,{secret}); bad.headers.set('x-fare-signature','00'); const badRes=await worker.fetch(bad,env);
const staleReq=await signedRequest('https://fare.example/candidate-plan/intake',body,{secret,ts:String(Date.now()-600000)}); const staleRes=await worker.fetch(staleReq,env);
console.log(JSON.stringify({status:res.status,payload,bad_status:badRes.status,stale_status:staleRes.status,count:raw.prepare('select count(*) n from itinerary_candidates').get().n}));
