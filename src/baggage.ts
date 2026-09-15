export type BaggageFacetStatus="PASS"|"UNKNOWN";
export interface BaggageEvaluation {status:BaggageFacetStatus;reason:string;required_slices:number[];}
function parseObject(v:unknown):any{if(v==null)return null;if(typeof v==='string'){try{return JSON.parse(v)}catch{return null}}return typeof v==='object'?v:null;}
function knownWeightKg(b:any):number|null{for(const k of ['weight_kg','maximum_weight_kg','max_weight_kg']){const n=Number(b?.[k]);if(Number.isFinite(n)&&n>0)return n}const meta=b?.metadata;for(const k of ['weight_kg','maximum_weight_kg','max_weight_kg']){const n=Number(meta?.[k]);if(Number.isFinite(n)&&n>0)return n}return null;}
export function evaluateBaggageEvidence(structureRaw:unknown,baggageQueryRaw:unknown):BaggageEvaluation{
  const q=parseObject(baggageQueryRaw); const s=parseObject(structureRaw); const req=Array.isArray(q?.checked_bags_by_slice)?q.checked_bags_by_slice.map((x:any)=>Number(x)||0):null; const requiredKg=Number(q?.checked_bag_kg)||0;
  if(!req)return {status:"UNKNOWN",reason:"BAGGAGE_PROFILE_MISSING",required_slices:[]};
  const needed=req.map((n:number,i:number)=>n>0?i:-1).filter((i:number)=>i>=0);
  if(!needed.length)return {status:"PASS",reason:"NO_CHECKED_BAG_REQUIRED",required_slices:[]};
  if(!Array.isArray(s?.slices))return {status:"UNKNOWN",reason:"OFFER_BAGGAGE_EVIDENCE_MISSING",required_slices:needed};
  for(const idx of needed){const slice=s.slices[idx];if(!slice||!Array.isArray(slice.segments)||!slice.segments.length)return {status:"UNKNOWN",reason:"OFFER_BAGGAGE_EVIDENCE_MISSING",required_slices:needed};const required=req[idx];
    for(const seg of slice.segments){if(!Array.isArray(seg.passengers)||!seg.passengers.length)return {status:"UNKNOWN",reason:"INCLUDED_BAGGAGE_UNKNOWN",required_slices:needed};
      for(const p of seg.passengers){const checked=(p.baggages??[]).filter((b:any)=>b?.type==='checked');const qty=checked.reduce((sum:number,b:any)=>sum+(Number(b.quantity)||0),0);if(qty<required)return {status:"UNKNOWN",reason:Array.isArray(s.available_services)&&s.available_services.some((x:any)=>x?.type==='baggage')?"BAGGAGE_ADDON_AVAILABLE_NEEDS_PRICING":"REQUIRED_CHECKED_BAG_NOT_PROVEN",required_slices:needed};
        if(requiredKg>0&&checked.filter((b:any)=>knownWeightKg(b)!==null&&knownWeightKg(b)!>=requiredKg).reduce((sum:number,b:any)=>sum+(Number(b.quantity)||0),0)<required)return {status:"UNKNOWN",reason:"INCLUDED_BAG_WEIGHT_UNKNOWN",required_slices:needed};
      }
    }
  }
  return {status:"PASS",reason:"REQUIRED_CHECKED_BAG_INCLUDED",required_slices:needed};
}
