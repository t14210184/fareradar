export function complexAlertCard(i:{itinerary_id:string;total_cost:number|null;missing:string[];protection:string;policy_ttl:string;observed_at:string;source_provenance:string[]}){
  if(i.total_cost==null) throw new Error("TOTAL_COST_REQUIRED");
  if(!i.observed_at||!i.protection||!i.policy_ttl||!i.source_provenance.length)throw new Error("ALERT_EVIDENCE_INCOMPLETE");
  return {kind:"P0-COMPLEX",...i};
}
