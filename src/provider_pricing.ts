import type { D1Database } from "./types.js";

function assert(c:boolean,m:string):asserts c{if(!c)throw new Error(m);}
function validSha(v:string){return /^[a-f0-9]{64}$/i.test(v);}
function validIso(v:string){return Number.isFinite(Date.parse(v));}
function stable(v:any):string{if(v===null||typeof v!=="object")return JSON.stringify(v);if(Array.isArray(v))return `[${v.map(stable).join(",")}]`;return `{${Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+stable(v[k])).join(",")}}`;}

export interface ProviderPricingSnapshotInput {
  pricing_snapshot_id:string; provider_id:string; usage_window_kind:"CALENDAR_MONTH"|"LIFETIME";
  search_to_book_threshold:number; hard_search_cap?:number|null; currency?:string|null; rate_json:unknown;
  source_url:string; raw_sha256:string; observed_at:string; effective_from:string; expires_at:string;
}
export async function ingestProviderPricingSnapshot(db:D1Database,input:ProviderPricingSnapshotInput,nowIso:string){
  assert(!!input.pricing_snapshot_id&&!!input.provider_id,"PROVIDER_PRICING_IDENTITY_REQUIRED");
  assert(["CALENDAR_MONTH","LIFETIME"].includes(input.usage_window_kind),"PROVIDER_PRICING_WINDOW_INVALID");
  assert(Number.isInteger(input.search_to_book_threshold)&&input.search_to_book_threshold>0,"PROVIDER_PRICING_THRESHOLD_INVALID");
  if(input.hard_search_cap!=null)assert(Number.isInteger(input.hard_search_cap)&&input.hard_search_cap>0,"PROVIDER_PRICING_HARD_CAP_INVALID");
  if(input.currency!=null)assert(/^[A-Z]{3}$/.test(input.currency),"PROVIDER_PRICING_CURRENCY_INVALID");
  assert(input.source_url.startsWith("https://")&&validSha(input.raw_sha256),"PROVIDER_PRICING_EVIDENCE_INVALID");
  for(const v of [input.observed_at,input.effective_from,input.expires_at])assert(validIso(v),"PROVIDER_PRICING_TIME_INVALID");
  assert(Date.parse(input.expires_at)>Date.parse(input.effective_from)&&Date.parse(input.observed_at)<=Date.parse(nowIso),"PROVIDER_PRICING_TIME_INVALID");
  const provider=await db.prepare("SELECT provider_id FROM provider_access_registry WHERE provider_id=?").bind(input.provider_id).first();assert(!!provider,"PROVIDER_PRICING_PROVIDER_UNKNOWN");
  const rateJson=stable(input.rate_json??{});
  const existing=await db.prepare("SELECT provider_id,usage_window_kind,search_to_book_threshold,hard_search_cap,currency,rate_json,source_url,raw_sha256,observed_at,effective_from,expires_at FROM provider_pricing_snapshots WHERE pricing_snapshot_id=?").bind(input.pricing_snapshot_id).first<any>();
  if(existing){const same=existing.provider_id===input.provider_id&&existing.usage_window_kind===input.usage_window_kind&&Number(existing.search_to_book_threshold)===input.search_to_book_threshold&&Number(existing.hard_search_cap??0)===Number(input.hard_search_cap??0)&&(existing.currency??null)===(input.currency??null)&&existing.rate_json===rateJson&&existing.source_url===input.source_url&&existing.raw_sha256===input.raw_sha256&&existing.observed_at===input.observed_at&&existing.effective_from===input.effective_from&&existing.expires_at===input.expires_at;if(!same)throw new Error("PROVIDER_PRICING_IMMUTABLE_CONFLICT");return {pricing_snapshot_id:input.pricing_snapshot_id,idempotent:true};}
  await db.batch([
    db.prepare("UPDATE provider_pricing_snapshots SET state='SUPERSEDED' WHERE provider_id=? AND state='ACTIVE'").bind(input.provider_id),
    db.prepare("INSERT INTO provider_pricing_snapshots(pricing_snapshot_id,provider_id,usage_window_kind,search_to_book_threshold,hard_search_cap,currency,rate_json,source_url,raw_sha256,observed_at,effective_from,expires_at,state,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'ACTIVE',?)")
      .bind(input.pricing_snapshot_id,input.provider_id,input.usage_window_kind,input.search_to_book_threshold,input.hard_search_cap??null,input.currency??null,rateJson,input.source_url,input.raw_sha256,input.observed_at,input.effective_from,input.expires_at,nowIso)
  ]);
  return {pricing_snapshot_id:input.pricing_snapshot_id,idempotent:false};
}
function windowKey(kind:string,nowIso:string){if(kind==="LIFETIME")return "LIFETIME";return nowIso.slice(0,7);}
function effectiveLimit(accessBudget:number|null,snapshotThreshold:number,hardCap:number|null,orders:number){const ratioLimit=Math.max(1,orders)*snapshotThreshold;const budget=accessBudget&&accessBudget>0?accessBudget:ratioLimit;let limit=Math.min(ratioLimit,budget);if(hardCap&&hardCap>0)limit=Math.min(limit,hardCap);return Math.max(0,Math.floor(limit));}
export async function reserveProviderSearchBudget(db:D1Database,providerId:string,nowIso:string){
  if(providerId!=="duffel")return {guarded:false,allowed:true};
  const access=await db.prepare("SELECT look_to_book_budget FROM provider_access_registry WHERE provider_id=?").bind(providerId).first<any>();if(!access)throw new Error("PROVIDER_ACCESS_NOT_READY");
  const snap=await db.prepare("SELECT pricing_snapshot_id,usage_window_kind,search_to_book_threshold,hard_search_cap FROM provider_pricing_snapshots WHERE provider_id=? AND state='ACTIVE' AND effective_from<=? AND expires_at>? ORDER BY observed_at DESC LIMIT 1").bind(providerId,nowIso,nowIso).first<any>();
  if(!snap)throw new Error("PROVIDER_PRICING_POLICY_MISSING");
  const key=windowKey(snap.usage_window_kind,nowIso);await db.prepare("INSERT OR IGNORE INTO provider_usage_windows(provider_id,window_key,pricing_snapshot_id,search_count,confirmed_order_count,circuit_state,updated_at) VALUES(?,?,?,0,0,'CLEAR',?)").bind(providerId,key,snap.pricing_snapshot_id,nowIso).run();
  const usage=await db.prepare("SELECT search_count,confirmed_order_count,circuit_state FROM provider_usage_windows WHERE provider_id=? AND window_key=?").bind(providerId,key).first<any>();
  const limit=effectiveLimit(access.look_to_book_budget==null?null:Number(access.look_to_book_budget),Number(snap.search_to_book_threshold),snap.hard_search_cap==null?null:Number(snap.hard_search_cap),Number(usage?.confirmed_order_count??0));
  if(usage?.circuit_state==="OPEN"||Number(usage?.search_count??0)>=limit){await db.prepare("UPDATE provider_usage_windows SET circuit_state='OPEN',opened_reason='SEARCH_TO_BOOK_BUDGET',updated_at=? WHERE provider_id=? AND window_key=?").bind(nowIso,providerId,key).run();throw new Error("PROVIDER_SEARCH_CIRCUIT_OPEN");}
  const r=await db.prepare("UPDATE provider_usage_windows SET search_count=search_count+1,updated_at=? WHERE provider_id=? AND window_key=? AND circuit_state='CLEAR' AND search_count<?").bind(nowIso,providerId,key,limit).run();
  if(Number((r.meta as any)?.changes??0)!==1){await db.prepare("UPDATE provider_usage_windows SET circuit_state='OPEN',opened_reason='SEARCH_TO_BOOK_BUDGET',updated_at=? WHERE provider_id=? AND window_key=?").bind(nowIso,providerId,key).run();throw new Error("PROVIDER_SEARCH_CIRCUIT_OPEN");}
  return {guarded:true,allowed:true,window_key:key,limit,search_count:Number(usage?.search_count??0)+1,pricing_snapshot_id:snap.pricing_snapshot_id};
}
export async function recordProviderConfirmedOrder(db:D1Database,providerId:string,nowIso:string){
  if(providerId!=="duffel")return {guarded:false};
  const snap=await db.prepare("SELECT pricing_snapshot_id,usage_window_kind,search_to_book_threshold,hard_search_cap FROM provider_pricing_snapshots WHERE provider_id=? AND state='ACTIVE' AND effective_from<=? AND expires_at>? ORDER BY observed_at DESC LIMIT 1").bind(providerId,nowIso,nowIso).first<any>();if(!snap)throw new Error("PROVIDER_PRICING_POLICY_MISSING");
  const key=windowKey(snap.usage_window_kind,nowIso);await db.prepare("INSERT OR IGNORE INTO provider_usage_windows(provider_id,window_key,pricing_snapshot_id,search_count,confirmed_order_count,circuit_state,updated_at) VALUES(?,?,?,0,0,'CLEAR',?)").bind(providerId,key,snap.pricing_snapshot_id,nowIso).run();
  await db.prepare("UPDATE provider_usage_windows SET confirmed_order_count=confirmed_order_count+1,circuit_state='CLEAR',opened_reason=NULL,updated_at=? WHERE provider_id=? AND window_key=?").bind(nowIso,providerId,key).run();return {guarded:true,window_key:key};
}
