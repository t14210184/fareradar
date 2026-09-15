import type { D1Database } from "./types.js";

export type FourLegCycleState = "NOT_STARTED"|"POSITIONING_BOOKED"|"AT_EXTERNAL_ORIGIN"|"LEG1_FLOWN"|"HOME_STOPOVER"|"MAIN_TRIP_ACTIVE"|"LEG3_FLOWN"|"TAIL_PENDING"|"CYCLE_COMPLETED"|"BROKEN";
const ORDER:FourLegCycleState[]=["NOT_STARTED","POSITIONING_BOOKED","AT_EXTERNAL_ORIGIN","LEG1_FLOWN","HOME_STOPOVER","MAIN_TRIP_ACTIVE","LEG3_FLOWN","TAIL_PENDING","CYCLE_COMPLETED"];
function assert(c:boolean,m:string):asserts c{if(!c)throw new Error(m);}
export function fourLegTransitionAllowed(from:FourLegCycleState,to:FourLegCycleState){
  if(from==="BROKEN"||from==="CYCLE_COMPLETED")return false;
  if(to==="BROKEN")return true;
  const i=ORDER.indexOf(from),j=ORDER.indexOf(to);return i>=0&&j===i+1;
}
export async function upsertFourLegCycle(db:D1Database,input:{cycle_id:string;itinerary_id:string},nowIso:string){
  assert(!!input.cycle_id&&!!input.itinerary_id,"FOUR_LEG_CYCLE_IDENTITY_REQUIRED");
  const itin=await db.prepare("SELECT strategy_type FROM itinerary_candidates WHERE itinerary_id=?").bind(input.itinerary_id).first<any>();assert(!!itin,"ITINERARY_NOT_FOUND");assert(["S14_FOREIGN_ORIGIN_FOUR_LEG","S14"].includes(itin.strategy_type),"FOUR_LEG_STRATEGY_REQUIRED");
  const prior=await db.prepare("SELECT cycle_id,itinerary_id,state FROM four_leg_cycles WHERE cycle_id=? OR itinerary_id=?").bind(input.cycle_id,input.itinerary_id).first<any>();
  if(prior){assert(prior.cycle_id===input.cycle_id&&prior.itinerary_id===input.itinerary_id,"FOUR_LEG_CYCLE_CONFLICT");return {cycle_id:prior.cycle_id,state:prior.state,idempotent:true};}
  await db.prepare("INSERT INTO four_leg_cycles(cycle_id,itinerary_id,state,created_at,updated_at) VALUES(?,?,'NOT_STARTED',?,?)").bind(input.cycle_id,input.itinerary_id,nowIso,nowIso).run();return {cycle_id:input.cycle_id,state:"NOT_STARTED",idempotent:false};
}
export async function transitionFourLegCycle(db:D1Database,input:{cycle_id:string;to_state:FourLegCycleState;reason?:string|null},nowIso:string){
  const c=await db.prepare("SELECT state FROM four_leg_cycles WHERE cycle_id=?").bind(input.cycle_id).first<any>();assert(!!c,"FOUR_LEG_CYCLE_NOT_FOUND");const from=c.state as FourLegCycleState;
  if(from===input.to_state)return {cycle_id:input.cycle_id,from,to:input.to_state,idempotent:true};
  assert(fourLegTransitionAllowed(from,input.to_state),"FOUR_LEG_ILLEGAL_TRANSITION");
  if(input.to_state==="BROKEN")assert(!!input.reason,"FOUR_LEG_BROKEN_REASON_REQUIRED");
  await db.prepare("UPDATE four_leg_cycles SET state=?,broken_reason=?,updated_at=? WHERE cycle_id=? AND state=?").bind(input.to_state,input.to_state==="BROKEN"?input.reason??null:null,nowIso,input.cycle_id,from).run();
  return {cycle_id:input.cycle_id,from,to:input.to_state,idempotent:false};
}
export async function fourLegLiabilitySummary(db:D1Database,cycleId:string){
  const c=await db.prepare("SELECT itinerary_id,state FROM four_leg_cycles WHERE cycle_id=?").bind(cycleId).first<any>();assert(!!c,"FOUR_LEG_CYCLE_NOT_FOUND");
  const rows=(await db.prepare("SELECT component_type,amount,paid_state,refundable,remaining_exposure,recoverable_amount FROM four_leg_liabilities WHERE cycle_id=? AND itinerary_id=?").bind(cycleId,c.itinerary_id).all<any>()).results;
  let remaining=0,recoverable=0,tail=0,positioning=0;for(const r of rows){const rem=Number(r.remaining_exposure);const rec=Number(r.recoverable_amount);assert(Number.isFinite(rem)&&rem>=0&&Number.isFinite(rec)&&rec>=0,"FOUR_LEG_LIABILITY_INVALID");remaining+=rem;recoverable+=rec;if(r.component_type==="TAIL_RETURN")tail+=rem;if(r.component_type==="POSITIONING")positioning+=rem;}
  const complete=c.state==="CYCLE_COMPLETED";return {cycle_id:cycleId,state:c.state,remaining_exposure:remaining,recoverable_amount:recoverable,positioning_exposure:positioning,tail_return_exposure:tail,unrealized_positioning_liability:!complete&&(positioning>0||tail>0),liability_count:rows.length};
}
