export interface ShadowSample { day:string; complex:boolean; source_discovery:boolean; agency_clearance:boolean; safety_errors:number; reviewed?:boolean; false_actionable?:boolean; }
export function evaluateShadow(samples:ShadowSample[]){
  const days=new Set(samples.map(x=>x.day)).size;
  const complex=samples.filter(x=>x.complex).length;
  const sourceDiscovery=samples.filter(x=>x.source_discovery).length;
  const agency=samples.filter(x=>x.agency_clearance).length;
  const safetyErrors=samples.reduce((a,b)=>a+b.safety_errors,0);
  const pass=days>=14&&samples.length>=150&&complex>=30&&sourceDiscovery>=30&&agency>=10&&safetyErrors===0;
  return {pass,days,labeled:samples.length,complex,source_discovery:sourceDiscovery,agency_clearance:agency,safety_errors:safetyErrors};
}
export function evaluateComplexReview(samples:ShadowSample[]){
  const complex=samples.filter(x=>x.complex);
  return {pass:complex.length>=30&&complex.every(x=>x.reviewed===true&&x.false_actionable===false),complex_reviewed:complex.filter(x=>x.reviewed).length,false_actionable:complex.filter(x=>x.false_actionable).length};
}
