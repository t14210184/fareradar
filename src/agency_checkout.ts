import type { D1Database } from "./types.js";
import { enqueueAlertIntent } from "./outbox.js";

function assert(c:boolean,m:string):asserts c{if(!c)throw new Error(m);}
function sha(v:string){return /^[a-f0-9]{64}$/i.test(v);}
function terms(v:string|null|undefined){return !!v&&v!=="RECHECK_REQUIRED"&&Number.isFinite(Date.parse(v));}
function after(nowIso:string,seconds:number){return new Date(Date.parse(nowIso)+seconds*1000).toISOString();}
async function partnerReady(db:D1Database,agencyId:string){const a=await db.prepare("SELECT agency_id,status,verified_business,terms_snapshot_at FROM agency_partner_registry WHERE agency_id=?").bind(agencyId).first<any>();return a&&a.status==="ENABLED"&&Number(a.verified_business)===1&&terms(a.terms_snapshot_at)?a:null;}

export async function enqueueAgencyCheckoutJob(db:D1Database,agencyOfferId:string,agencyId:string,nowIso:string){
  const jobId=`agency-checkout:${agencyOfferId}`;
  await db.prepare(`INSERT INTO agency_checkout_jobs(job_id,agency_offer_id,agency_id,state,attempts,available_at,created_at,updated_at)
    VALUES(?,?,?,'PENDING',0,?,?,?) ON CONFLICT(agency_offer_id) DO NOTHING`).bind(jobId,agencyOfferId,agencyId,nowIso,nowIso,nowIso).run();
  return {job_id:jobId};
}

export async function leaseAgencyCheckouts(db:D1Database,input:{agency_id:string;worker_id:string;limit?:number},nowIso:string){
  assert(!!input.agency_id&&!!input.worker_id,"AGENCY_CHECKOUT_IDENTITY_REQUIRED");assert(!!await partnerReady(db,input.agency_id),"AGENCY_PARTNER_NOT_ENABLED");
  await db.prepare("UPDATE agency_checkout_jobs SET state='PENDING',claimed_by=NULL,lease_until=NULL WHERE state='LEASED' AND lease_until IS NOT NULL AND lease_until<=? AND agency_id=?").bind(nowIso,input.agency_id).run();
  const limit=Math.min(Math.max(Number(input.limit??3),1),3),until=after(nowIso,120);
  return (await db.prepare(`UPDATE agency_checkout_jobs SET state='LEASED',claimed_by=?,lease_until=?,attempts=attempts+1,updated_at=?
    WHERE job_id IN (SELECT job_id FROM agency_checkout_jobs WHERE agency_id=? AND state='PENDING' AND available_at<=? ORDER BY created_at ASC LIMIT ?)
    AND state='PENDING' RETURNING job_id,agency_offer_id,agency_id,attempts,lease_until`)
    .bind(input.worker_id,until,nowIso,input.agency_id,nowIso,limit).all<any>()).results;
}

async function ackCheckoutJob(db:D1Database,row:any,input:{job_id:string;worker_id:string},nowIso:string,ok:boolean,retryable:boolean,error:string|null){
  if(ok){await db.prepare("UPDATE agency_checkout_jobs SET state='DONE',lease_until=NULL,last_error=NULL,updated_at=? WHERE job_id=?").bind(nowIso,input.job_id).run();return "DONE";}
  if(retryable&&Number(row.attempts)<5){const delay=Math.min(3600,30*Math.pow(2,Math.max(0,Number(row.attempts)-1)));await db.prepare("UPDATE agency_checkout_jobs SET state='PENDING',claimed_by=NULL,lease_until=NULL,available_at=?,last_error=?,updated_at=? WHERE job_id=?").bind(after(nowIso,delay),error??"RETRYABLE",nowIso,input.job_id).run();return "RETRY";}
  await db.prepare("UPDATE agency_checkout_jobs SET state='DEAD',lease_until=NULL,last_error=?,updated_at=? WHERE job_id=?").bind(error??"TERMINAL",nowIso,input.job_id).run();
  await enqueueAlertIntent(db,{intent_id:`admin-agency-checkout:${input.job_id}`,itinerary_id:row.agency_offer_id,alert_class:"ADMIN",payload:{type:"AGENCY_CHECKOUT_DEAD",job_id:input.job_id,agency_offer_id:row.agency_offer_id,error:error??"TERMINAL"}},nowIso);return "DEAD";
}

export interface AgencyCheckoutInput {
  checkout_id:string;job_id:string;agency_offer_id:string;agency_id:string;worker_id:string;
  readback_basis:"PARTNER_BOOKING_API"|"PARTNER_PORTAL_CHECKOUT"|"OFFICIAL_CHECKOUT_PAGE";
  checkout_url:string;content_sha256:string;observed_at:string;final_price:number;currency:string;
  seats_available?:number|null;booking_deadline?:string|null;total_includes_taxes:boolean;total_includes_mandatory_fees:boolean;
  payment_dispatched?:boolean;
}
export async function completeAgencyCheckout(db:D1Database,input:AgencyCheckoutInput,nowIso:string){
  assert(!!input.checkout_id&&!!input.job_id&&!!input.agency_offer_id&&!!input.agency_id&&!!input.worker_id,"AGENCY_CHECKOUT_IDENTITY_REQUIRED");
  assert(["PARTNER_BOOKING_API","PARTNER_PORTAL_CHECKOUT","OFFICIAL_CHECKOUT_PAGE"].includes(input.readback_basis),"AGENCY_CHECKOUT_BASIS_INVALID");
  assert(input.checkout_url.startsWith("https://")&&sha(input.content_sha256),"AGENCY_CHECKOUT_EVIDENCE_INVALID");
  assert(Number.isFinite(Date.parse(input.observed_at))&&Date.parse(input.observed_at)<=Date.parse(nowIso),"AGENCY_CHECKOUT_TIME_INVALID");
  assert(Number.isFinite(input.final_price)&&input.final_price>=0&&/^[A-Z]{3}$/.test(input.currency),"AGENCY_CHECKOUT_PRICE_INVALID");
  if(input.seats_available!=null)assert(Number.isInteger(input.seats_available)&&input.seats_available>=0,"AGENCY_CHECKOUT_SEATS_INVALID");
  assert(input.payment_dispatched!==true,"AGENCY_CHECKOUT_PAYMENT_FORBIDDEN");
  const existing=await db.prepare("SELECT job_id,agency_offer_id,agency_id,worker_id,content_sha256,result_state FROM agency_checkout_evidence WHERE checkout_id=?").bind(input.checkout_id).first<any>();
  if(existing){if(existing.job_id!==input.job_id||existing.agency_offer_id!==input.agency_offer_id||existing.agency_id!==input.agency_id||existing.worker_id!==input.worker_id||existing.content_sha256!==input.content_sha256)throw new Error("AGENCY_CHECKOUT_IMMUTABLE_CONFLICT");return {state:existing.result_state,idempotent:true};}
  assert(!!await partnerReady(db,input.agency_id),"AGENCY_PARTNER_NOT_ENABLED");
  const row=await db.prepare(`SELECT j.state,j.claimed_by,j.lease_until,j.attempts,j.agency_offer_id,j.agency_id,a.currency,a.product_id,a.tax_inclusion,a.baggage,a.booking_or_contact_channel,a.state offer_state
    FROM agency_checkout_jobs j JOIN agency_inventory_offers a ON a.agency_offer_id=j.agency_offer_id WHERE j.job_id=? AND j.agency_id=?`).bind(input.job_id,input.agency_id).first<any>();
  assert(!!row&&row.agency_offer_id===input.agency_offer_id&&row.state==="LEASED"&&row.claimed_by===input.worker_id&&row.lease_until&&Date.parse(row.lease_until)>Date.parse(nowIso),"AGENCY_CHECKOUT_LIVE_LEASE_REQUIRED");
  assert(row.offer_state==="SELLER_CONFIRMED"||row.offer_state==="CHECKOUT_REPRODUCED","AGENCY_SELLER_CONFIRMATION_REQUIRED");
  let result:"CHECKOUT_REPRODUCED"|"SOLD_OUT"|"RECHECK_REQUIRED"="CHECKOUT_REPRODUCED",retryable=false,error:string|null=null;
  if(input.currency!==row.currency){result="RECHECK_REQUIRED";retryable=true;error="AGENCY_CHECKOUT_CURRENCY_MISMATCH";}
  else if(!input.total_includes_taxes||!input.total_includes_mandatory_fees){result="RECHECK_REQUIRED";retryable=true;error="AGENCY_CHECKOUT_TOTAL_INCOMPLETE";}
  else if(input.seats_available===0){result="SOLD_OUT";}
  await db.prepare(`INSERT INTO agency_checkout_evidence(checkout_id,job_id,agency_offer_id,agency_id,worker_id,readback_basis,checkout_url,content_sha256,observed_at,final_price,currency,seats_available,booking_deadline,total_includes_taxes,total_includes_mandatory_fees,payment_dispatched,result_state,created_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).bind(input.checkout_id,input.job_id,input.agency_offer_id,input.agency_id,input.worker_id,input.readback_basis,input.checkout_url,input.content_sha256,input.observed_at,input.final_price,input.currency,input.seats_available??null,input.booking_deadline??null,input.total_includes_taxes?1:0,input.total_includes_mandatory_fees?1:0,0,result,nowIso).run();
  if(result==="RECHECK_REQUIRED"){const state=await ackCheckoutJob(db,row,input,nowIso,false,retryable,error);return {state,result,idempotent:false};}
  if(result==="SOLD_OUT"){await db.prepare("UPDATE agency_inventory_offers SET seats_available=0,observed_at=?,state='SOLD_OUT' WHERE agency_offer_id=?").bind(input.observed_at,input.agency_offer_id).run();const state=await ackCheckoutJob(db,row,input,nowIso,true,false,null);return {state,result,idempotent:false};}
  await db.prepare("UPDATE agency_inventory_offers SET seller_verification_state='CHECKOUT_REPRODUCED',price=?,seats_available=COALESCE(?,seats_available),booking_deadline=COALESCE(?,booking_deadline),observed_at=?,state='CHECKOUT_REPRODUCED' WHERE agency_offer_id=?")
    .bind(input.final_price,input.seats_available??null,input.booking_deadline??null,input.observed_at,input.agency_offer_id).run();
  const state=await ackCheckoutJob(db,row,input,nowIso,true,false,null);
  const payload={kind:"P0-PROVISIONAL",verification_state:"CHECKOUT_REPRODUCED",actionable:false,bookable:false,subject_type:"AGENCY_CLEARANCE",agency_offer_id:input.agency_offer_id,agency_id:input.agency_id,product_id:row.product_id,price:input.final_price,currency:input.currency,tax_inclusion:"CHECKOUT_TOTAL",baggage:row.baggage,seats_available:input.seats_available??null,booking_deadline:input.booking_deadline??null,booking_channel:row.booking_or_contact_channel,checkout_evidence_id:input.checkout_id,readback_basis:input.readback_basis};
  await enqueueAlertIntent(db,{intent_id:`agency-checkout:${input.agency_offer_id}:${input.checkout_id}`,itinerary_id:`agency:${input.agency_offer_id}`,alert_class:"DEAL",payload},nowIso);
  return {state,result,idempotent:false};
}
