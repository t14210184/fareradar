import type { D1Database } from "./types.js";
import { enqueueAlertIntent } from "./outbox.js";

function after(nowIso:string,seconds:number){return new Date(Date.parse(nowIso)+seconds*1000).toISOString();}
function qid(type:"PROMOTION"|"AGENCY_CLEARANCE",id:string){return `${type.toLowerCase()}:${id}`;}

export async function enqueueCandidateSignal(db:D1Database,input:{
  signal_type:"PROMOTION"|"AGENCY_CLEARANCE";
  signal_id:string;
  required_verification:"LIVE_REPRICE"|"SELLER_RECHECK";
  priority_score:number;
  route_scope:unknown;
  price_claim?:unknown;
  source_evidence_id:string;
  observed_at:string;
},nowIso:string){
  if(!input.signal_id||!input.source_evidence_id)throw new Error("CANDIDATE_SIGNAL_INVALID");
  if(!Number.isFinite(input.priority_score)||input.priority_score<0||input.priority_score>100)throw new Error("PRIORITY_SCORE_INVALID");
  const queueId=qid(input.signal_type,input.signal_id);
  await db.prepare(`INSERT INTO candidate_priority_queue(
      queue_id,signal_type,signal_id,required_verification,priority_score,route_scope_json,price_claim_json,source_evidence_id,
      state,attempts,available_at,first_observed_at,last_observed_at,created_at,updated_at)
    VALUES(?,?,?,?,?,?,?,?,'PENDING',0,?,?,?,?,?)
    ON CONFLICT(signal_type,signal_id) DO UPDATE SET
      priority_score=MAX(candidate_priority_queue.priority_score,excluded.priority_score),
      route_scope_json=excluded.route_scope_json,
      price_claim_json=COALESCE(excluded.price_claim_json,candidate_priority_queue.price_claim_json),
      source_evidence_id=excluded.source_evidence_id,
      last_observed_at=excluded.last_observed_at,
      updated_at=excluded.updated_at,
      state=CASE WHEN candidate_priority_queue.state='DEAD' THEN candidate_priority_queue.state ELSE candidate_priority_queue.state END`)
    .bind(queueId,input.signal_type,input.signal_id,input.required_verification,input.priority_score,JSON.stringify(input.route_scope),input.price_claim===undefined?null:JSON.stringify(input.price_claim),input.source_evidence_id,nowIso,input.observed_at,input.observed_at,nowIso,nowIso).run();
  return {queue_id:queueId};
}

export async function leaseCandidateSignals(db:D1Database,nowIso:string,workerId:string,limit=5,leaseSeconds=90,verificationType?:"LIVE_REPRICE"|"SELLER_RECHECK"){
  await db.prepare("UPDATE candidate_priority_queue SET state='PENDING',claimed_by=NULL,lease_until=NULL WHERE state='LEASED' AND lease_until IS NOT NULL AND lease_until<=?").bind(nowIso).run();
  const until=after(nowIso,leaseSeconds);
  return (await db.prepare(`UPDATE candidate_priority_queue SET state='LEASED',claimed_by=?,lease_until=?,attempts=attempts+1
    WHERE queue_id IN (SELECT queue_id FROM candidate_priority_queue WHERE state='PENDING' AND available_at<=? AND (? IS NULL OR required_verification=?) ORDER BY priority_score DESC,first_observed_at ASC LIMIT ?)
    AND state='PENDING'
    RETURNING queue_id,signal_type,signal_id,required_verification,priority_score,route_scope_json,price_claim_json,source_evidence_id,attempts,lease_until`)
    .bind(workerId,until,nowIso,verificationType??null,verificationType??null,limit).all()).results;
}

export async function ackCandidateSignal(db:D1Database,input:{queue_id:string;worker_id?:string;ok:boolean;retryable?:boolean;error?:string|null},nowIso:string){
  const row=await db.prepare("SELECT attempts,signal_id,state,claimed_by,lease_until FROM candidate_priority_queue WHERE queue_id=?").bind(input.queue_id).first<{attempts:number;signal_id:string;state:string;claimed_by:string|null;lease_until:string|null}>();
  if(!row)throw new Error("CANDIDATE_SIGNAL_NOT_FOUND");
  const external=!!input.worker_id;
  if(external){
    if((row.state==="DONE"||row.state==="DEAD")&&row.claimed_by===input.worker_id)return row.state;
    if(row.state!=="LEASED"||row.claimed_by!==input.worker_id||!row.lease_until||Date.parse(row.lease_until)<=Date.parse(nowIso))throw new Error("CANDIDATE_SIGNAL_LEASE_REQUIRED");
  }
  if(input.ok){await db.prepare("UPDATE candidate_priority_queue SET state='DONE',lease_until=NULL,last_error=NULL,updated_at=? WHERE queue_id=?").bind(nowIso,input.queue_id).run();return "DONE";}
  if(input.retryable!==false&&row.attempts<5){const delay=Math.min(3600,30*Math.pow(2,Math.max(0,row.attempts-1)));await db.prepare("UPDATE candidate_priority_queue SET state='PENDING',claimed_by=NULL,lease_until=NULL,available_at=?,last_error=?,updated_at=? WHERE queue_id=?").bind(after(nowIso,delay),input.error??"RETRYABLE",nowIso,input.queue_id).run();return "RETRY";}
  await db.prepare("UPDATE candidate_priority_queue SET state='DEAD',lease_until=NULL,last_error=?,updated_at=? WHERE queue_id=?").bind(input.error??"TERMINAL",nowIso,input.queue_id).run();
  await enqueueAlertIntent(db,{intent_id:`admin-candidate-${input.queue_id}`,itinerary_id:row.signal_id,alert_class:"ADMIN",payload:{type:"CANDIDATE_PRIORITY_DEAD",queue_id:input.queue_id,signal_id:row.signal_id,error:input.error??"TERMINAL"}},nowIso);
  return "DEAD";
}
