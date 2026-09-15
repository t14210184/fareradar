import type { D1Database } from "./types.js";
import { enqueueAlertIntent } from "./outbox.js";

type ExpiryReason="BOOKING_DEADLINE_PASSED"|"PAYMENT_DEADLINE_PASSED"|"TICKETING_DEADLINE_PASSED"|"SEATS_EXHAUSTED";
function parsed(v:string|null|undefined){const n=v?Date.parse(v):NaN;return Number.isFinite(n)?n:null;}
export function agencyOfferExpiryReason(row:{seats_available?:number|null;booking_deadline?:string|null;payment_deadline?:string|null;ticketing_deadline?:string|null},nowIso:string):{reason:ExpiryReason;effective_at:string;new_state:"EXPIRED"|"SOLD_OUT"}|null{
  const now=Date.parse(nowIso); if(!Number.isFinite(now))throw new Error("AGENCY_EXPIRY_TIME_INVALID");
  if(row.seats_available===0)return {reason:"SEATS_EXHAUSTED",effective_at:nowIso,new_state:"SOLD_OUT"};
  const candidates:[number,ExpiryReason,string][]=[];
  for(const [value,reason] of [[row.booking_deadline,"BOOKING_DEADLINE_PASSED"],[row.payment_deadline,"PAYMENT_DEADLINE_PASSED"],[row.ticketing_deadline,"TICKETING_DEADLINE_PASSED"]] as [string|null|undefined,ExpiryReason][]){const t=parsed(value);if(t!==null&&t<=now)candidates.push([t,reason,value!]);}
  if(!candidates.length)return null;candidates.sort((a,b)=>a[0]-b[0]);return {reason:candidates[0][1],effective_at:candidates[0][2],new_state:"EXPIRED"};
}
export async function expireAgencyOffers(db:D1Database,nowIso:string,limit=1){
  const rows=(await db.prepare(`SELECT agency_offer_id,agency_id,product_id,state,seats_available,booking_deadline,payment_deadline,ticketing_deadline,price,currency,booking_or_contact_channel
    FROM agency_inventory_offers WHERE state NOT IN ('EXPIRED','SOLD_OUT') AND (
      seats_available=0 OR (booking_deadline IS NOT NULL AND datetime(booking_deadline)<=datetime(?)) OR (payment_deadline IS NOT NULL AND datetime(payment_deadline)<=datetime(?)) OR (ticketing_deadline IS NOT NULL AND datetime(ticketing_deadline)<=datetime(?))
    ) ORDER BY COALESCE(booking_deadline,payment_deadline,ticketing_deadline,observed_at) ASC LIMIT ?`).bind(nowIso,nowIso,nowIso,Math.min(Math.max(limit,1),2)).all<any>()).results;
  let expired=0;
  for(const row of rows){
    const x=agencyOfferExpiryReason(row,nowIso); if(!x)continue;
    const eventId=`agency-life:${row.agency_offer_id}:${x.new_state}:${x.reason}`;
    await db.batch([
      db.prepare("UPDATE agency_inventory_offers SET seller_verification_state='REVOKED',state=?,expired_at=?,expiry_reason=? WHERE agency_offer_id=? AND state NOT IN ('EXPIRED','SOLD_OUT')").bind(x.new_state,x.effective_at,x.reason,row.agency_offer_id),
      db.prepare("INSERT OR IGNORE INTO agency_offer_lifecycle_events(event_id,agency_offer_id,previous_state,new_state,reason,effective_at,created_at) VALUES(?,?,?,?,?,?,?)").bind(eventId,row.agency_offer_id,row.state,x.new_state,x.reason,x.effective_at,nowIso),
      db.prepare("UPDATE candidate_priority_queue SET state='DEAD',claimed_by=NULL,lease_until=NULL,last_error=?,updated_at=? WHERE signal_type='AGENCY_CLEARANCE' AND signal_id=? AND state IN ('PENDING','LEASED')").bind(x.reason,nowIso,row.agency_offer_id),
      db.prepare("UPDATE agency_checkout_jobs SET state='DEAD',claimed_by=NULL,lease_until=NULL,last_error=?,updated_at=? WHERE agency_offer_id=? AND state IN ('PENDING','LEASED')").bind(x.reason,nowIso,row.agency_offer_id),
      db.prepare("UPDATE candidate_alert_intents SET projected_at=? WHERE itinerary_id=? AND projected_at IS NULL").bind(nowIso,`agency:${row.agency_offer_id}`),
      db.prepare("UPDATE notification_outbox SET state='CANCELLED',lease_until=NULL,last_error=? WHERE notification_id IN (SELECT intent_id FROM candidate_alert_intents WHERE itinerary_id=?) AND state='PENDING'").bind(x.reason,`agency:${row.agency_offer_id}`)
    ]);
    await enqueueAlertIntent(db,{intent_id:`agency-expiry:${row.agency_offer_id}:${x.reason}`,itinerary_id:`agency:${row.agency_offer_id}`,alert_class:"DEAL",payload:{kind:"DEAL-UPDATE",verification_state:x.new_state,actionable:false,bookable:false,subject_type:"AGENCY_CLEARANCE",agency_offer_id:row.agency_offer_id,agency_id:row.agency_id,product_id:row.product_id,price:row.price,currency:row.currency,booking_channel:row.booking_or_contact_channel,reason:x.reason,effective_at:x.effective_at}},nowIso);
    expired++;
  }
  return {expired};
}
