import type { D1Database } from "./types.js";
import { verifyMultiProvider } from "./verification.js";
import { ackCandidateSignal } from "./priority.js";
import { projectDirectVerifiedCandidate } from "./direct_candidate.js";

function safe(v:string){return v.replace(/[^A-Za-z0-9._:-]/g,"_");}
function parseJson<T>(raw:string|null|undefined,fallback:T):T{try{return raw?JSON.parse(raw) as T:fallback;}catch{return fallback;}}
function flightToken(v:unknown){return String(v??"").toUpperCase().replace(/[^A-Z0-9]/g,"");}
function offerMatchesEligibleFlights(structureRaw:string|null|undefined,eligibleRaw:unknown):boolean{
  const eligible=Array.isArray(eligibleRaw)?eligibleRaw.map(flightToken).filter(Boolean):[];
  if(!eligible.length)return true;
  const allow=new Set(eligible);const structure=parseJson<any>(structureRaw,null);
  if(!structure||!Array.isArray(structure.slices)||!structure.slices.length)return false;
  let count=0;
  for(const slice of structure.slices){
    if(!Array.isArray(slice?.segments)||!slice.segments.length)return false;
    for(const segment of slice.segments){
      const number=flightToken(segment?.flight_number);
      if(!number)return false;
      const marketing=flightToken(segment?.marketing_carrier);
      const candidates=[number,marketing?`${marketing}${number}`:""];
      if(!candidates.some(x=>x&&allow.has(x)))return false;
      count++;
    }
  }
  return count>0;
}
async function promotionEligibleFlightNumbers(db:D1Database,queueId:string):Promise<string[]>{
  const q=await db.prepare("SELECT signal_type,signal_id FROM candidate_priority_queue WHERE queue_id=?").bind(queueId).first<any>();
  if(!q||q.signal_type!=="PROMOTION")return [];
  const p=await db.prepare("SELECT constraint_json FROM promotion_events WHERE event_id=?").bind(q.signal_id).first<any>();
  const c=parseJson<any>(p?.constraint_json,{});
  return Array.isArray(c?.eligible_flight_numbers)?c.eligible_flight_numbers.map(String).filter(Boolean):[];
}
export async function projectProviderJobResults(db:D1Database,jobId:string,nowIso:string){
  const consumers=(await db.prepare("SELECT c.plan_id,c.queue_id,p.query_fingerprint FROM provider_job_consumers c JOIN provider_search_plans p ON p.plan_id=c.plan_id WHERE c.job_id=?").bind(jobId).all<any>()).results;
  let projected=0;
  for(const c of consumers){
    const offers=(await db.prepare("SELECT provider_offer_id,query_fingerprint,provider,offer_total,currency,observed_at,expires_at,cached_or_live FROM offer_snapshots WHERE source_snapshot_id=? AND query_fingerprint=? AND cached_or_live='LIVE'").bind(jobId,c.query_fingerprint).all<any>()).results;
    for(const o of offers)await db.prepare("INSERT OR IGNORE INTO candidate_offer_links(queue_id,plan_id,job_id,provider_offer_id,query_fingerprint,created_at) VALUES(?,?,?,?,?,?)").bind(c.queue_id,c.plan_id,jobId,o.provider_offer_id,c.query_fingerprint,nowIso).run();
    const linkedRaw=(await db.prepare(`SELECT o.provider_offer_id,o.query_fingerprint,o.provider,o.offer_total,o.currency,o.observed_at,o.expires_at,o.offer_structure_json
      FROM candidate_offer_links l JOIN offer_snapshots o ON o.provider_offer_id=l.provider_offer_id
      WHERE l.queue_id=? AND l.query_fingerprint=? AND o.cached_or_live='LIVE'`).bind(c.queue_id,c.query_fingerprint).all<any>()).results;
    if(!linkedRaw.length)continue;
    const eligibleFlights=await promotionEligibleFlightNumbers(db,c.queue_id);
    const linked=eligibleFlights.length?linkedRaw.filter(o=>offerMatchesEligibleFlights(o.offer_structure_json,eligibleFlights)):linkedRaw;
    const resultId=`verify:${safe(c.queue_id)}:${c.query_fingerprint}`;
    if(!linked.length){
      await db.prepare(`INSERT INTO candidate_verification_results(result_id,queue_id,query_fingerprint,verification_state,reason,best_offer_id,best_offer_total,currency,live_offer_count,provider_count,updated_at)
        VALUES(?,?,?,?,?,NULL,NULL,NULL,0,0,?) ON CONFLICT(queue_id,query_fingerprint) DO UPDATE SET verification_state=excluded.verification_state,reason=excluded.reason,best_offer_id=NULL,best_offer_total=NULL,currency=NULL,live_offer_count=0,provider_count=0,updated_at=excluded.updated_at`)
        .bind(resultId,c.queue_id,c.query_fingerprint,"PROBABLE","PROMOTION_CONSTRAINT_MISMATCH",nowIso).run();
      projected++;continue;
    }
    const verdict=verifyMultiProvider(linked.map(o=>({provider:o.provider,kind:"LIVE_OFFER" as const,price:Number(o.offer_total),query_fingerprint:o.query_fingerprint,observed_at:o.observed_at,expires_at:o.expires_at,coverage_allowed:true})),nowIso); const verificationState:"PROBABLE"|"CONFIRMED"=verdict.state==="CONFIRMED"?"CONFIRMED":"PROBABLE";
    const best=[...linked].sort((a,b)=>Number(a.offer_total)-Number(b.offer_total)||String(a.provider_offer_id).localeCompare(String(b.provider_offer_id)))[0];
    const providers=new Set(linked.map(o=>o.provider));
    await db.prepare(`INSERT INTO candidate_verification_results(result_id,queue_id,query_fingerprint,verification_state,reason,best_offer_id,best_offer_total,currency,live_offer_count,provider_count,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(queue_id,query_fingerprint) DO UPDATE SET verification_state=excluded.verification_state,reason=excluded.reason,best_offer_id=excluded.best_offer_id,best_offer_total=excluded.best_offer_total,currency=excluded.currency,live_offer_count=excluded.live_offer_count,provider_count=excluded.provider_count,updated_at=excluded.updated_at`)
      .bind(resultId,c.queue_id,c.query_fingerprint,verificationState,verdict.reason,best.provider_offer_id,Number(best.offer_total),best.currency,linked.length,providers.size,nowIso).run();
    await projectDirectVerifiedCandidate(db,{queue_id:c.queue_id,query_fingerprint:c.query_fingerprint,verification_state:verificationState,best_offer_id:best.provider_offer_id},nowIso);
    if(verificationState==="CONFIRMED") await ackCandidateSignal(db,{queue_id:c.queue_id,ok:true},nowIso); projected++;
  }
  return {consumers:consumers.length,projected};
}
