export interface EvidenceVersion { entity_id:string; version:number; state:"ACTIVE"|"CORRECTED"|"DELETED"; payload:unknown; observed_at:string; supersedes_version?:number|null; }
export function applyCorrection(history:EvidenceVersion[], event:{entity_id:string;type:"CORRECT"|"DELETE";payload?:unknown;observed_at:string}){
  const own=history.filter(x=>x.entity_id===event.entity_id).sort((a,b)=>a.version-b.version);
  const prev=own.at(-1); const version=(prev?.version??0)+1;
  const next:EvidenceVersion={entity_id:event.entity_id,version,state:event.type==="DELETE"?"DELETED":"CORRECTED",payload:event.type==="DELETE"?null:event.payload??null,observed_at:event.observed_at,supersedes_version:prev?.version??null};
  return [...history,next];
}
