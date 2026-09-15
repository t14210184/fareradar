import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { enqueueAlertIntent, projectAlertIntents, leaseNotifications, ackNotification } from '../dist/outbox.js';
class S{constructor(s){this.s=s;this.a=[]}bind(...a){this.a=a;return this}async run(){return{success:true,meta:this.s.run(...this.a)}}async first(){return this.s.get(...this.a)??null}async all(){return{results:this.s.all(...this.a)}}}
class D{constructor(x){this.x=x}prepare(q){return new S(this.x.prepare(q))}async batch(a){const out=[];this.x.exec('BEGIN IMMEDIATE');try{for(const s of a)out.push(await s.run());this.x.exec('COMMIT');return out}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:'); for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8')); const db=new D(raw);
const t='2026-09-15T00:00:00Z';
await enqueueAlertIntent(db,{intent_id:'shadow-deal',itinerary_id:'i1',alert_class:'DEAL',payload:{kind:'DEAL'}},t);
await enqueueAlertIntent(db,{intent_id:'shadow-admin',itinerary_id:'i1',alert_class:'ADMIN',payload:{kind:'ADMIN'}},t);
await projectAlertIntents(db,t,10,'SHADOW_ACCEPTANCE');
const states1=raw.prepare('select notification_id,state from notification_outbox order by notification_id').all();
const leasedShadow=await leaseNotifications(db,t,'w1',10);
for(const row of leasedShadow) await ackNotification(db,{notification_id:row.notification_id,worker_id:'w1',ok:true,retryable:false},'2026-09-15T00:00:01Z');
await enqueueAlertIntent(db,{intent_id:'prod-deal',itinerary_id:'i2',alert_class:'DEAL',payload:{kind:'DEAL'}},'2026-09-15T00:01:00Z');
await projectAlertIntents(db,'2026-09-15T00:01:00Z',10,'PRODUCTION');
const leasedProd=await leaseNotifications(db,'2026-09-15T00:01:00Z','w2',10);
const states2=raw.prepare('select notification_id,state from notification_outbox order by notification_id').all();
console.log(JSON.stringify({states1,leasedShadow:leasedShadow.map(x=>x.notification_id),leasedProd:leasedProd.map(x=>x.notification_id),states2}));
