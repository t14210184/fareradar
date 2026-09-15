import type { D1Database } from "./types.js";
import { REQUIRED_FACETS } from "./types.js";

function fresh(v:string|null|undefined,nowIso:string){return !!v&&Number.isFinite(Date.parse(v))&&Date.parse(v)>Date.parse(nowIso);}

export async function evaluateActionableFromDb(db:D1Database,itineraryId:string,nowIso:string){
  const itin=await db.prepare("SELECT verification_state,cost_complete FROM itinerary_candidates WHERE itinerary_id=?").bind(itineraryId).first<any>();
  if(!itin)return {actionable:false,reason:"ITINERARY_NOT_FOUND",failed_facets:[] as string[]};
  if(itin.verification_state!=="CONFIRMED")return {actionable:false,reason:"FARE_NOT_CONFIRMED",failed_facets:["FARE_VERIFIED"]};
  if(Number(itin.cost_complete)!==1)return {actionable:false,reason:"COST_NOT_COMPLETE",failed_facets:["COST_COMPLETE"]};
  const rows=(await db.prepare("SELECT facet_type,status,expires_at FROM readiness_facets WHERE itinerary_id=?").bind(itineraryId).all<any>()).results;
  const by=new Map(rows.map(r=>[String(r.facet_type),r])); const failed:string[]=[];
  for(const type of REQUIRED_FACETS){const r=by.get(type);if(!r||r.status!=="PASS"||!fresh(r.expires_at,nowIso))failed.push(type);}
  if(failed.length)return {actionable:false,reason:"READINESS_NOT_PASS",failed_facets:failed};
  return {actionable:true,reason:"ALL_READINESS_PASS",failed_facets:[] as string[]};
}
