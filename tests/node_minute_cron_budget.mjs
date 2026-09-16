import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { cleanupExpiredNonces } from '../dist/auth.js';
import { projectAlertIntents } from '../dist/outbox.js';
import { projectDomainEvents } from '../dist/ingest.js';
import { scheduleDueSources } from '../dist/scheduler.js';
class S{constructor(s,c){this.s=s;this.c=c;this.a=[]}bind(...a){this.a=a;return this}async run(){this.c.n++;return{success:true,meta:this.s.run(...this.a)}}async first(){this.c.n++;return this.s.get(...this.a)??null}async all(){this.c.n++;return{results:this.s.all(...this.a)}}}
class D{constructor(x,c){this.x=x;this.c=c}prepare(q){return new S(this.x.prepare(q),this.c)}async batch(a){this.x.exec('BEGIN IMMEDIATE');try{const out=[];for(const s of a)out.push(await s.run());this.x.exec('COMMIT');return out}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const counter={n:0},db=new D(raw,counter);
const now='2026-09-15T03:46:00Z';
for(let i=0;i<10;i++)raw.prepare("insert into candidate_alert_intents(intent_id,itinerary_id,alert_class,payload_json,created_at) values(?,?,?,?,?)").run(`deal-${i}`,`itin-${i}`,'DEAL','{}',now);
for(let i=0;i<2;i++)raw.prepare("insert into domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) values('NOOP',?,'{}','PENDING',0,?)").run(`noop-${i}`,now);
for(let i=0;i<10;i++)raw.prepare("insert into source_registry(source_id,source_class,canonical_domain_or_account,entrypoint_url,access_basis,fetch_method,lifecycle_state,verification_authority,terms_snapshot_at,min_interval_ms,kill_switch,discovery_trust,kill_switch_state) values(?,?,?,?,?,'PUSH','ENABLED','DISCOVERY',?,60000,0,'HIGH','CLEAR')").run(`source-${i}`,'SOCIAL',`source-${i}.example`,`https://source-${i}.example/feed`,'PUBLIC','2026-09-15T00:00:00Z');
counter.n=0;const steps={};let q=0;
q=counter.n;await cleanupExpiredNonces(db,now);steps.cleanup=counter.n-q;
q=counter.n;const projected=await projectAlertIntents(db,now,10,'SHADOW_ACCEPTANCE');steps.projectAlertIntents=counter.n-q;
q=counter.n;const domain=await projectDomainEvents(db,now,'cron',2);steps.projectDomainEvents=counter.n-q;
q=counter.n;const sources=await scheduleDueSources(db,now,10);steps.scheduleDueSources=counter.n-q;
console.log(JSON.stringify({queries:counter.n,steps,projected,domain,sources,held:raw.prepare("select count(*) n from notification_outbox where state='SHADOW_HELD'").get().n,jobs:raw.prepare("select count(*) n from verification_jobs where job_type='SOURCE_FETCH'").get().n}));
