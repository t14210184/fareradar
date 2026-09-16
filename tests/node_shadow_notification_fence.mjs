import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { enqueueAlertIntent, projectAlertIntents, leaseNotifications, ackNotification, normalizeDeploymentMode } from '../dist/outbox.js';
class Stmt{constructor(s){this.s=s;this.a=[]}bind(...a){this.a=a;return this}async run(){return{success:true,meta:this.s.run(...this.a)}}async first(){return this.s.get(...this.a)??null}async all(){return{results:this.s.all(...this.a)}}}
class DB{constructor(x){this.x=x}prepare(q){return new Stmt(this.x.prepare(q))}async batch(xs){const out=[];this.x.exec('BEGIN IMMEDIATE');try{for(const x of xs)out.push(await x.run());this.x.exec('COMMIT');return out}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const db=new DB(raw);
const t='2026-09-16T00:00:00Z';
await enqueueAlertIntent(db,{intent_id:'shadow-deal',itinerary_id:'i1',alert_class:'DEAL',payload:{kind:'P0-ACTIONABLE'}},t);
await enqueueAlertIntent(db,{intent_id:'shadow-admin',itinerary_id:'i1',alert_class:'ADMIN',payload:{kind:'ADMIN'}},t);
await projectAlertIntents(db,t,10,normalizeDeploymentMode(undefined));
const shadowStates=raw.prepare("select notification_id,state from notification_outbox order by notification_id").all();
const shadowLease=await leaseNotifications(db,t,'n1',10,60);
for(const row of shadowLease)await ackNotification(db,{notification_id:row.notification_id,worker_id:'n1',ok:true,retryable:false},'2026-09-16T00:00:01Z');
await enqueueAlertIntent(db,{intent_id:'production-deal',itinerary_id:'i2',alert_class:'DEAL',payload:{kind:'P0-ACTIONABLE'}},'2026-09-16T00:01:00Z');
await projectAlertIntents(db,'2026-09-16T00:01:00Z',10,normalizeDeploymentMode('PRODUCTION'));
const productionLease=await leaseNotifications(db,'2026-09-16T00:01:00Z','n2',10,60);
console.log(JSON.stringify({missing_mode:normalizeDeploymentMode(undefined),bad_mode:normalizeDeploymentMode('oops'),prod_mode:normalizeDeploymentMode('PRODUCTION'),shadowStates,shadowLease:shadowLease.map(x=>x.notification_id),productionLease:productionLease.map(x=>x.notification_id),oldShadow:raw.prepare("select state from notification_outbox where notification_id='shadow-deal'").get().state}));
