import { DatabaseSync } from 'node:sqlite'; import fs from 'node:fs';
import { enqueueProviderSearch, leaseProviderJobs } from '../dist/provider_jobs.js';
import { recordProviderRuntimeReadback } from '../dist/provider_runtime.js';
import { leaseVerificationJobs } from '../dist/scheduler.js';
class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:'); for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8')); raw.exec(fs.readFileSync(new URL('../generated/seed.generated.sql',import.meta.url),'utf8')); const db=new DB(raw);
const query={slices:[{origin:'TPE',destination:'KIX',departure_date:'2026-11-03'}],passengers:[{type:'adult'}],cabin_class:'economy',max_connections:1};
let backgroundBlocked=false; raw.prepare("update provider_access_registry set terms_snapshot_at='2026-09-15T00:00:00Z' where provider_id='duffel'").run();
try{await enqueueProviderSearch(db,{provider_id:'duffel',mode:'BACKGROUND',query},'2026-09-15T00:00:00Z')}catch(e){backgroundBlocked=String(e).includes('PROVIDER_BACKGROUND_NOT_ALLOWED')}
raw.prepare("update provider_access_registry set background_allowed=1 where provider_id='duffel'").run();
const enq=await enqueueProviderSearch(db,{provider_id:'duffel',mode:'BACKGROUND',query},'2026-09-15T00:00:01Z');
raw.prepare("insert into verification_jobs(job_id,job_type,target_class,source_id,payload_json,state,available_at,created_at) values('source-job','SOURCE_FETCH','EXTERNAL_HEAVY','s1','{}','PENDING','2026-09-15T00:00:00Z','2026-09-15T00:00:00Z')").run();
await recordProviderRuntimeReadback(db,{provider_id:'duffel',worker_id:'provider-w1',connector_version:'duffel-v2-1',credentials_present:true,capabilities:['LIVE_REPRICE'],ttl_seconds:300},'2026-09-15T00:00:02Z');
const sourceJobs=await leaseVerificationJobs(db,'2026-09-15T00:00:03Z','source-w1',5,90);
raw.prepare("update provider_access_registry set background_allowed=0 where provider_id='duffel'").run();
const revokedBackgroundJobs=await leaseProviderJobs(db,{provider_id:'duffel',worker_id:'provider-w1',limit:5},'2026-09-15T00:00:03Z');
const userQuery={...query,slices:[{...query.slices[0],departure_date:'2026-11-04'}]};
const userEnq=await enqueueProviderSearch(db,{provider_id:'duffel',mode:'USER_REQUEST',query:userQuery},'2026-09-15T00:00:04Z');
const providerJobs=await leaseProviderJobs(db,{provider_id:'duffel',worker_id:'provider-w1',limit:5},'2026-09-15T00:00:05Z');
console.log(JSON.stringify({backgroundBlocked,enq,userEnq,revokedBackgroundJobs:revokedBackgroundJobs.map(x=>x.job_id),sourceJobs:sourceJobs.map(x=>x.job_id),providerJobs:providerJobs.map(x=>x.job_id),providerModes:providerJobs.map(x=>x.provider_mode),sourceTarget:raw.prepare("select target_class from verification_jobs where job_id='source-job'").get().target_class,providerApiCount:raw.prepare("select count(*) n from verification_jobs where target_class='PROVIDER_API'").get().n}));
