import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { enqueueAlertIntent, projectAlertIntents, leaseNotifications, ackNotification, claimDomainEvents, ackDomainEvent } from '../dist/outbox.js';
class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:'); for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8')); const db=new DB(raw);
const t0='2026-09-15T00:00:00.000Z';
await enqueueAlertIntent(db,{intent_id:'deal-1',itinerary_id:'itin-1',alert_class:'DEAL',payload:{x:1}},t0);
await projectAlertIntents(db,t0); await projectAlertIntents(db,t0);
let jobs=await leaseNotifications(db,t0,'w1',10,60);
raw.prepare("update notification_outbox set lease_until='2026-09-14T23:59:59.000Z' where notification_id='deal-1'").run();
let reclaimed=await leaseNotifications(db,'2026-09-15T00:02:00.000Z','w2',10,60);
let retry=await ackNotification(db,{notification_id:'deal-1',ok:false,retryable:true,error:'500'},'2026-09-15T00:02:00.000Z');
raw.prepare("update notification_outbox set state='SENDING',attempts=5 where notification_id='deal-1'").run();
let dead=await ackNotification(db,{notification_id:'deal-1',ok:false,retryable:false,error:'400'},'2026-09-15T01:00:00.000Z');
await projectAlertIntents(db,'2026-09-15T01:00:01.000Z');
raw.prepare("insert into domain_outbox(event_type,entity_id,payload_json,state,attempts,created_at) values('OBS','o1','{}','PENDING',0,?)").run(t0);
let ev=await claimDomainEvents(db,t0,'dw1',2,60); raw.prepare("update domain_outbox set lease_until='2026-09-14T23:59:59.000Z' where entity_id='o1'").run(); let ev2=await claimDomainEvents(db,'2026-09-15T00:02:00.000Z','dw2',2,60); let dstate=await ackDomainEvent(db,{id:Number(ev2[0].id),ok:true},'2026-09-15T00:02:01.000Z');
const counts={intents:raw.prepare('select count(*) n from candidate_alert_intents').get().n,notifications:raw.prepare('select count(*) n from notification_outbox').get().n,domain_done:raw.prepare("select count(*) n from domain_outbox where state='DONE'").get().n};
console.log(JSON.stringify({jobs:jobs.length,reclaimed:reclaimed.length,retry,dead,ev:ev.length,ev2:ev2.length,dstate,counts,admin:raw.prepare("select count(*) n from candidate_alert_intents where alert_class='ADMIN'").get().n}));
