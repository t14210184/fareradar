import type { D1Database } from "./types.js";

function day(iso:string){return iso.slice(0,10);}
function safeId(v:string){return v.replace(/[^A-Za-z0-9._:-]/g,"_");}

export async function attributeConfirmedCandidate(db:D1Database,input:{itinerary_id:string;evidence_ids:string[]},confirmedAt:string){
  const ids=[...new Set((input.evidence_ids??[]).filter(Boolean))];
  if(!input.itinerary_id||ids.length===0)return {inserted:0,winner_source_id:null};
  if(ids.length>16)throw new Error("ATTRIBUTION_EVIDENCE_LIMIT");
  const marks=ids.map(()=>"?").join(",");
  const rows=(await db.prepare(`SELECT observation_id,source_id,observed_at FROM source_observations WHERE observation_id IN (${marks})`).bind(...ids).all<any>()).results;
  if(rows.length!==ids.length){const have=new Set(rows.map(r=>r.observation_id));const missing=ids.filter(x=>!have.has(x));throw new Error(`ATTRIBUTION_EVIDENCE_NOT_FOUND:${missing.join(",")}`);}
  const earliestBySource=new Map<string,any>();
  for(const r of rows){const prior=earliestBySource.get(r.source_id);if(!prior||r.observed_at<prior.observed_at||(r.observed_at===prior.observed_at&&r.observation_id<prior.observation_id))earliestBySource.set(r.source_id,r);}
  const ranked=[...earliestBySource.values()].sort((a,b)=>a.observed_at.localeCompare(b.observed_at)||a.source_id.localeCompare(b.source_id)||a.observation_id.localeCompare(b.observation_id));
  const winner=ranked[0]?.source_id??null;
  let inserted=0;
  for(const r of ranked){
    const id=`confirmed:${safeId(input.itinerary_id)}:${safeId(r.source_id)}`;
    const res=await db.prepare("INSERT OR IGNORE INTO source_outcome_attributions(attribution_id,itinerary_id,source_id,observation_id,outcome_type,first_win,window_date,observed_at,confirmed_at) VALUES(?,?,?,?,'CONFIRMED',?,?,?,?)")
      .bind(id,input.itinerary_id,r.source_id,r.observation_id,r.source_id===winner?1:0,day(r.observed_at),r.observed_at,confirmedAt).run();
    inserted+=Number((res.meta as any)?.changes??0);
  }
  return {inserted,winner_source_id:winner};
}
