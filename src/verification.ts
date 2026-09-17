export interface VerificationEvidence {
  evidence_id?:string;
  provider:string;
  kind:"LIVE_OFFER"|"CACHED_FARE"|"SOCIAL"|"PROMOTION"|"SELLER_READBACK";
  price?:number;
  query_fingerprint?:string;
  observed_at:string;
  expires_at?:string|null;
  coverage_allowed?:boolean;
}
export function verifyMultiProvider(evidence:VerificationEvidence[], nowIso:string, tolerance=0.03){
  const now=Date.parse(nowIso);
  const live=evidence.filter(e=>e.kind==="LIVE_OFFER" && e.coverage_allowed!==false && (!e.expires_at || Date.parse(e.expires_at)>now));
  const direct=live.find(e=>e.provider.startsWith("airline:"));
  if(direct) return {state:"CONFIRMED",reason:"AIRLINE_DIRECT",supporting_evidence_ids:direct.evidence_id?[direct.evidence_id]:[]};
  for(let i=0;i<live.length;i++) for(let j=i+1;j<live.length;j++){
    const a=live[i],b=live[j];
    if(a.provider===b.provider||!a.price||!b.price||a.query_fingerprint!==b.query_fingerprint) continue;
    if(Math.abs(a.price-b.price)/Math.max(a.price,b.price)<=tolerance){
      return {state:"CONFIRMED",reason:"INDEPENDENT_LIVE_MATCH",supporting_evidence_ids:[a.evidence_id,b.evidence_id].filter((x):x is string=>!!x)};
    }
  }
  if(live.length) return {state:"PROBABLE",reason:"SINGLE_LIVE_SOURCE",supporting_evidence_ids:[] as string[]};
  return {state:"PROBABLE",reason:"NO_LIVE_CONFIRMATION",supporting_evidence_ids:[] as string[]};
}

export function amadeusCanConfirm(carrierClass:"LCC"|"FULL_SERVICE") { return carrierClass !== "LCC"; }
