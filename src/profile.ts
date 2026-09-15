import type { D1Database } from "./types.js";

export type CheckedBagPattern="NONE"|"OUTBOUND_ONLY"|"RETURN_ONLY"|"BOTH";
export interface RuntimeProfileInput {
  profile_id:string; home_city?:string|null; home_airports:string[]; checked_bag_pattern:CheckedBagPattern; baggage_kg:number;
  seat_required:boolean; red_eye_ok:boolean; self_transfer_ok:boolean; overnight_transfer_ok:boolean; airport_change_ok:boolean;
  mainland_permit_status:string; korea_entry_profile:string; foreign_origin_ok:boolean; positioning_cost_attribution:"FULL"|"MARGINAL"|"NONE";
  max_positioning_cost_twd:number; value_of_time_twd_per_hour:number; min_savings_for_self_transfer_twd:number; currency:string;
}
function assert(c:boolean,m:string):asserts c{if(!c)throw new Error(m);}
function iata(v:string){return /^[A-Z]{3}$/.test(v);}
export function validateRuntimeProfile(p:RuntimeProfileInput){
  assert(!!p.profile_id,"PROFILE_ID_REQUIRED"); const airports=[...new Set(p.home_airports??[])];
  assert(airports.length>=1&&airports.length<=8&&airports.every(iata),"PROFILE_HOME_AIRPORTS_INVALID");
  assert(["NONE","OUTBOUND_ONLY","RETURN_ONLY","BOTH"].includes(p.checked_bag_pattern),"PROFILE_BAG_PATTERN_INVALID");
  assert(Number.isInteger(p.baggage_kg)&&p.baggage_kg>=0&&p.baggage_kg<=50,"PROFILE_BAGGAGE_KG_INVALID");
  assert(/^[A-Z]{3}$/.test(p.currency),"PROFILE_CURRENCY_INVALID");
  for(const [v,n] of [[p.max_positioning_cost_twd,"MAX_POSITIONING_COST"],[p.value_of_time_twd_per_hour,"VALUE_OF_TIME"],[p.min_savings_for_self_transfer_twd,"MIN_SELF_TRANSFER_SAVING"]] as const)assert(Number.isFinite(v)&&v>=0,`PROFILE_${n}_INVALID`);
  assert(!!p.mainland_permit_status&&!!p.korea_entry_profile,"PROFILE_DOCUMENT_CONTEXT_REQUIRED");
  return {...p,home_airports:airports};
}
export async function upsertRuntimeProfile(db:D1Database,input:RuntimeProfileInput,nowIso:string){
  const p=validateRuntimeProfile(input);
  await db.prepare(`INSERT INTO runtime_profiles(profile_id,home_city,home_airports_json,checked_bag_pattern,baggage_kg,seat_required,red_eye_ok,self_transfer_ok,overnight_transfer_ok,airport_change_ok,mainland_permit_status,korea_entry_profile,foreign_origin_ok,positioning_cost_attribution,max_positioning_cost_twd,value_of_time_twd_per_hour,min_savings_for_self_transfer_twd,currency,created_at,updated_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(profile_id) DO UPDATE SET home_city=excluded.home_city,home_airports_json=excluded.home_airports_json,checked_bag_pattern=excluded.checked_bag_pattern,baggage_kg=excluded.baggage_kg,seat_required=excluded.seat_required,red_eye_ok=excluded.red_eye_ok,self_transfer_ok=excluded.self_transfer_ok,overnight_transfer_ok=excluded.overnight_transfer_ok,airport_change_ok=excluded.airport_change_ok,mainland_permit_status=excluded.mainland_permit_status,korea_entry_profile=excluded.korea_entry_profile,foreign_origin_ok=excluded.foreign_origin_ok,positioning_cost_attribution=excluded.positioning_cost_attribution,max_positioning_cost_twd=excluded.max_positioning_cost_twd,value_of_time_twd_per_hour=excluded.value_of_time_twd_per_hour,min_savings_for_self_transfer_twd=excluded.min_savings_for_self_transfer_twd,currency=excluded.currency,updated_at=excluded.updated_at`)
    .bind(p.profile_id,p.home_city??null,JSON.stringify(p.home_airports),p.checked_bag_pattern,p.baggage_kg,p.seat_required?1:0,p.red_eye_ok?1:0,p.self_transfer_ok?1:0,p.overnight_transfer_ok?1:0,p.airport_change_ok?1:0,p.mainland_permit_status,p.korea_entry_profile,p.foreign_origin_ok?1:0,p.positioning_cost_attribution,p.max_positioning_cost_twd,p.value_of_time_twd_per_hour,p.min_savings_for_self_transfer_twd,p.currency,nowIso,nowIso).run();
  return {profile_id:p.profile_id};
}
export function baggageQueryFromProfile(p:{checked_bag_pattern:CheckedBagPattern;baggage_kg:number;seat_required?:number|boolean},sliceCount:number){
  assert(Number.isInteger(sliceCount)&&sliceCount>=1&&sliceCount<=4,"PROFILE_SLICE_COUNT_INVALID");
  const bags=Array(sliceCount).fill(0); if(p.checked_bag_pattern==="BOTH")bags.fill(1); else if(p.checked_bag_pattern==="OUTBOUND_ONLY")bags[0]=1; else if(p.checked_bag_pattern==="RETURN_ONLY"&&sliceCount>1)bags[sliceCount-1]=1;
  return {checked_bags_by_slice:bags,checked_bag_kg:p.baggage_kg,seat_required:!!p.seat_required};
}
export async function profileBaggageQuery(db:D1Database,profileId:string,sliceCount:number){
  const p=await db.prepare("SELECT checked_bag_pattern,baggage_kg,seat_required FROM runtime_profiles WHERE profile_id=?").bind(profileId).first<any>();
  if(!p)throw new Error("RUNTIME_PROFILE_NOT_FOUND"); return baggageQueryFromProfile(p,sliceCount);
}
