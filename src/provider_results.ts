import type { D1Database } from "./types.js";
import { verifyMultiProvider } from "./verification.js";
import { ackCandidateSignal } from "./priority.js";

function safe(v:string){return v.replace(/[^A-Za-z0-9._:-]/g,"_");}
export async function projectProviderJobResults(db:D1Database,jobId:string,nowIso:string){
  const consumers=(await db.prepare("SELECT c.plan_id,c.queue_id,p.query_fingerprint FROM provider_job_consumers c JOIN provider_search_plans p ON p.plan_id=c.plan_id WHERE c.job_id=?").bind(jobId).all<any>()).results;
  let projected=0;
  for(const c of consumers){
    const offers=(await db.prepare("SELECT provider_offer_id,query_fingerprint,provider,offer_total,currency,observed_at,expires_at,cached_or_live FROM offer_snapshots WHERE source_snapshot_id=? AND query_fingerprint=? AND cached_or_live='LIVE'").bind(jobId,c.query_fingerprint).all<any>()).results;
    for(const o of offers)await db.prepare("INSERT OR IGNORE INTO candidate_offer_links(queue_id,plan_id,job_id,provider_offer_id,query_fingerprint,created_at) VALUES(?,?,?,?,?,?)").bind(c.queue_id,c.plan_id,jobId,o.provider_offer_id,c.query_fingerprint,nowIso).run();
    const linked=(await db.prepare(`SELECT o.provider_offer_id,o.query_fingerprint,o.provider,o.offer_total,o.currency,o.observed_at,o.expires_at
      FROM candidate_offer_links l JOIN offer_snapshots o ON o.provider_offer_id=l.provider_offer_id
      WHERE l.queue_id=? AND l.query_fingerprint=? AND o.cached_or_live='LIVE'`).bind(c.queue_id,c.query_fingerprint).all<any>()).results;
    if(!linked.length)continue;
    const verdict=verifyMultiProvider(linked.map(o=>({provider:o.provider,kind:"LIVE_OFFER" as const,price:Number(o.offer_total),query_fingerprint:o.query_fingerprint,observed_at:o.observed_at,expires_at:o.expires_at,coverage_allowed:true})),nowIso);
    const best=[...linked].sort((a,b)=>Number(a.offer_total)-Number(b.offer_total)||String(a.provider_offer_id).localeCompare(String(b.provider_offer_id)))[0];
    const providers=new Set(linked.map(o=>o.provider)); const resultId=`verify:${safe(c.queue_id)}:${c.query_fingerprint}`;
    await db.prepare(`INSERT INTO candidate_verification_results(result_id,queue_id,query_fingerprint,verification_state,reason,best_offer_id,best_offer_total,currency,live_offer_count,provider_count,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(queue_id,query_fingerprint) DO UPDATE SET verification_state=excluded.verification_state,reason=excluded.reason,best_offer_id=excluded.best_offer_id,best_offer_total=excluded.best_offer_total,currency=excluded.currency,live_offer_count=excluded.live_offer_count,provider_count=excluded.provider_count,updated_at=excluded.updated_at`)
      .bind(resultId,c.queue_id,c.query_fingerprint,verdict.state,verdict.reason,best.provider_offer_id,Number(best.offer_total),best.currency,linked.length,providers.size,nowIso).run();
    if(verdict.state==="CONFIRMED") await ackCandidateSignal(db,{queue_id:c.queue_id,ok:true},nowIso); projected++;
  }
  return {consumers:consumers.length,projected};
}
