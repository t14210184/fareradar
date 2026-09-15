import type { D1Database } from "./types.js";

function isoAfter(nowIso:string, seconds:number){ return new Date(Date.parse(nowIso)+seconds*1000).toISOString(); }
export async function enqueueAlertIntent(db:D1Database,input:{intent_id:string;itinerary_id:string;alert_class:"DEAL"|"ADMIN";payload:unknown},nowIso:string){
  await db.prepare("INSERT INTO candidate_alert_intents(intent_id,itinerary_id,alert_class,payload_json,created_at) VALUES(?,?,?,?,?) ON CONFLICT(intent_id) DO NOTHING")
    .bind(input.intent_id,input.itinerary_id,input.alert_class,JSON.stringify(input.payload),nowIso).run();
}
export async function projectAlertIntents(db:D1Database,nowIso:string,limit=10){
  const rows=(await db.prepare("SELECT intent_id,alert_class,payload_json FROM candidate_alert_intents WHERE projected_at IS NULL ORDER BY created_at LIMIT ?").bind(limit).all<{intent_id:string;alert_class:string;payload_json:string}>()).results;
  for(const row of rows){
    await db.batch([
      db.prepare("INSERT INTO notification_outbox(notification_id,channel_class,payload_json,state,attempts,created_at) VALUES(?,?,?,'PENDING',0,?) ON CONFLICT(notification_id) DO NOTHING").bind(row.intent_id,row.alert_class,row.payload_json,nowIso),
      db.prepare("UPDATE candidate_alert_intents SET projected_at=? WHERE intent_id=? AND projected_at IS NULL").bind(nowIso,row.intent_id)
    ]);
  }
  return rows.length;
}
export async function leaseNotifications(db:D1Database,nowIso:string,workerId:string,limit=10,leaseSeconds=60){
  await db.prepare("UPDATE notification_outbox SET state='PENDING',claimed_by=NULL,lease_until=NULL WHERE state='SENDING' AND lease_until IS NOT NULL AND lease_until<=?").bind(nowIso).run();
  const leaseUntil=isoAfter(nowIso,leaseSeconds);
  const rows=(await db.prepare(`UPDATE notification_outbox SET state='SENDING',claimed_by=?,lease_until=?,attempts=attempts+1 WHERE notification_id IN (SELECT notification_id FROM notification_outbox WHERE state='PENDING' AND (next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY created_at LIMIT ?) AND state='PENDING' RETURNING notification_id,channel_class,payload_json,attempts,lease_until`).bind(workerId,leaseUntil,nowIso,limit).all()).results;
  return rows;
}
export async function ackNotification(db:D1Database,input:{notification_id:string;worker_id:string;ok:boolean;retryable:boolean;error?:string|null},nowIso:string){
  const row=await db.prepare("SELECT channel_class,attempts,state,claimed_by,lease_until FROM notification_outbox WHERE notification_id=?").bind(input.notification_id).first<{channel_class:string;attempts:number;state:string;claimed_by:string|null;lease_until:string|null}>();
  if(!row) throw new Error("NOTIFICATION_NOT_FOUND");
  if((row.state==="DELIVERED"||row.state==="DEAD")&&row.claimed_by===input.worker_id)return row.state;
  if(row.state!=="SENDING"||row.claimed_by!==input.worker_id||!row.lease_until||Date.parse(row.lease_until)<=Date.parse(nowIso))throw new Error("NOTIFICATION_LEASE_REQUIRED");
  if(input.ok){ await db.prepare("UPDATE notification_outbox SET state='DELIVERED',lease_until=NULL,last_error=NULL WHERE notification_id=? AND state='SENDING' AND claimed_by=?").bind(input.notification_id,input.worker_id).run(); return "DELIVERED"; }
  const maxAttempts=5;
  if(input.retryable && row.attempts<maxAttempts){ const delay=Math.min(3600,30*Math.pow(2,Math.max(0,row.attempts-1))); const next=isoAfter(nowIso,delay); await db.prepare("UPDATE notification_outbox SET state='PENDING',claimed_by=NULL,lease_until=NULL,next_attempt_at=?,last_error=? WHERE notification_id=? AND state='SENDING' AND claimed_by=?").bind(next,input.error??"RETRYABLE",input.notification_id,input.worker_id).run(); return "RETRY"; }
  await db.prepare("UPDATE notification_outbox SET state='DEAD',lease_until=NULL,last_error=? WHERE notification_id=? AND state='SENDING' AND claimed_by=?").bind(input.error??"TERMINAL",input.notification_id,input.worker_id).run();
  if(row.channel_class==="DEAL"){
    const adminId=`admin-delivery-${input.notification_id}`;
    await enqueueAlertIntent(db,{intent_id:adminId,itinerary_id:input.notification_id,alert_class:"ADMIN",payload:{type:"NOTIFICATION_DELIVERY_FAILED",notification_id:input.notification_id,error:input.error??"TERMINAL"}},nowIso);
  }
  return "DEAD";
}

export async function claimDomainEvents(db:D1Database,nowIso:string,workerId:string,limit=2,leaseSeconds=60){
  await db.prepare("UPDATE domain_outbox SET state='PENDING',claimed_by=NULL,lease_until=NULL WHERE state='CLAIMED' AND lease_until IS NOT NULL AND lease_until<=?").bind(nowIso).run();
  const leaseUntil=isoAfter(nowIso,leaseSeconds);
  return (await db.prepare(`UPDATE domain_outbox SET state='CLAIMED',claimed_by=?,lease_until=?,attempts=attempts+1 WHERE id IN (SELECT id FROM domain_outbox WHERE state='PENDING' ORDER BY id LIMIT ?) AND state='PENDING' RETURNING id,event_type,entity_id,payload_json,attempts,lease_until`).bind(workerId,leaseUntil,limit).all()).results;
}
export async function ackDomainEvent(db:D1Database,input:{id:number;worker_id:string;ok:boolean;error?:string|null},nowIso:string){
  const row=await db.prepare("SELECT attempts,event_type,entity_id,state,claimed_by,lease_until FROM domain_outbox WHERE id=?").bind(input.id).first<{attempts:number;event_type:string;entity_id:string;state:string;claimed_by:string|null;lease_until:string|null}>(); if(!row) throw new Error("DOMAIN_EVENT_NOT_FOUND");
  if((row.state==="DONE"||row.state==="DEAD")&&row.claimed_by===input.worker_id)return row.state;
  if(row.state!=="CLAIMED"||row.claimed_by!==input.worker_id||!row.lease_until||Date.parse(row.lease_until)<=Date.parse(nowIso))throw new Error("DOMAIN_EVENT_LEASE_REQUIRED");
  if(input.ok){await db.prepare("UPDATE domain_outbox SET state='DONE',lease_until=NULL,last_error=NULL WHERE id=? AND state='CLAIMED' AND claimed_by=?").bind(input.id,input.worker_id).run();return "DONE";}
  if(row.attempts<5){await db.prepare("UPDATE domain_outbox SET state='PENDING',claimed_by=NULL,lease_until=NULL,last_error=? WHERE id=? AND state='CLAIMED' AND claimed_by=?").bind(input.error??"RETRYABLE",input.id,input.worker_id).run();return "RETRY";}
  await db.prepare("UPDATE domain_outbox SET state='DEAD',lease_until=NULL,last_error=? WHERE id=? AND state='CLAIMED' AND claimed_by=?").bind(input.error??"TERMINAL",input.id,input.worker_id).run();
  await enqueueAlertIntent(db,{intent_id:`admin-domain-${input.id}`,itinerary_id:row.entity_id,alert_class:"ADMIN",payload:{type:"DOMAIN_EVENT_DEAD",event_type:row.event_type,entity_id:row.entity_id}},nowIso); return "DEAD";
}
