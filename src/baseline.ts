import type { D1Database } from "./types.js";

function stable(v:any):string{if(v===null||typeof v!=="object")return JSON.stringify(v);if(Array.isArray(v))return `[${v.map(stable).join(",")}]`;return `{${Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+stable(v[k])).join(",")}}`;}
async function sha256Hex(text:string){const h=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text));return [...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,"0")).join("");}
function parse(raw:string|null|undefined){try{return raw?JSON.parse(raw):null}catch{return null}}
function metro(a:string){const m:Record<string,string>={TPE:"TPE_METRO",TSA:"TPE_METRO",NRT:"TYO_METRO",HND:"TYO_METRO",KIX:"OSA_METRO",ITM:"OSA_METRO",KOB:"OSA_METRO"};return m[a]??a;}
function advanceBucket(days:number){if(days<0)return "PAST";if(days<=6)return "D0_6";if(days<=13)return "D7_13";if(days<=29)return "D14_29";if(days<=59)return "D30_59";if(days<=89)return "D60_89";return "D90_PLUS";}
function bagProfile(raw:string|null|undefined){const x=parse(raw);if(!x||typeof x!=="object")return "UNKNOWN";const bags=Array.isArray(x.checked_bags_by_slice)?x.checked_bags_by_slice.map((v:any)=>Number(v)||0):[];const kg=Number(x.checked_bag_kg??0);const seat=!!x.seat_required;return `bags:${bags.join("-")||"unknown"}|kg:${Number.isFinite(kg)?kg:0}|seat:${seat?1:0}`;}
function deriveStructure(structure:any){
  const slices=Array.isArray(structure?.slices)?structure.slices:[];if(!slices.length)return null;
  const firstSegs=Array.isArray(slices[0]?.segments)?slices[0].segments:[];if(!firstSegs.length)return null;
  const origin=String(firstSegs[0]?.origin??"").toUpperCase();const destination=String(firstSegs[firstSegs.length-1]?.destination??"").toUpperCase();
  const departing=String(firstSegs[0]?.departing_at??"");if(!/^[A-Z]{3}$/.test(origin)||!/^[A-Z]{3}$/.test(destination)||!Number.isFinite(Date.parse(departing)))return null;
  const returnSegs=slices.length===2&&Array.isArray(slices[1]?.segments)?slices[1].segments:[];
  const roundtrip=returnSegs.length>0&&String(returnSegs[returnSegs.length-1]?.destination??"").toUpperCase()===origin;
  const tripType=slices.length===1?"ONEWAY":roundtrip?"ROUNDTRIP":"MULTICITY";
  const stop=slices.some((s:any)=>!Array.isArray(s?.segments)||s.segments.length!==1)?"STOP":"NONSTOP";
  return {origin,destination,departure_date:departing.slice(0,10),trip_type:tripType,nonstop_or_stop:stop,fare_brand:String(structure?.fare_brand??"UNKNOWN")};
}
export async function projectFareBaselineFromOffer(db:D1Database,providerOfferId:string,nowIso:string){
  const o=await db.prepare("SELECT provider_offer_id,provider,currency,offer_total,observed_at,cached_or_live,fare_freshness,baggage_query,offer_structure_json FROM offer_snapshots WHERE provider_offer_id=?").bind(providerOfferId).first<any>();
  if(!o)return {projected:false,reason:"OFFER_NOT_FOUND"};
  if(o.cached_or_live!=="LIVE")return {projected:false,reason:"NOT_LIVE"};
  if(o.currency!=="TWD")return {projected:false,reason:"NON_TWD_REQUIRES_FX"};
  const d=deriveStructure(parse(o.offer_structure_json));if(!d)return {projected:false,reason:"STRUCTURE_INCOMPLETE"};
  const observed=Date.parse(o.observed_at),depart=Date.parse(`${d.departure_date}T00:00:00Z`);if(!Number.isFinite(observed)||!Number.isFinite(depart))return {projected:false,reason:"TIME_INVALID"};
  const days=Math.floor((depart-observed)/86400000);if(days<0)return {projected:false,reason:"DEPARTURE_IN_PAST"};
  const dims={route_key:`${d.origin}-${d.destination}`,metro_pair:`${metro(d.origin)}-${metro(d.destination)}`,direction:`${d.origin}-${d.destination}`,trip_type:d.trip_type,nonstop_or_stop:d.nonstop_or_stop,protected_or_self_transfer:"PROVIDER_OFFER",fare_brand:d.fare_brand,baggage_profile:bagProfile(o.baggage_query),weekday:new Date(`${d.departure_date}T00:00:00Z`).getUTCDay(),season:`MONTH_${d.departure_date.slice(5,7)}`,holiday_bucket:"UNKNOWN",advance_purchase_bucket:advanceBucket(days),provider:o.provider,currency:o.currency};
  const key=await sha256Hex(stable(dims));const id=`baseline:${o.provider_offer_id}`;
  await db.prepare(`INSERT INTO fare_baseline_observations(baseline_id,provider_offer_id,baseline_key,route_key,metro_pair,direction,trip_type,nonstop_or_stop,protected_or_self_transfer,fare_brand,baggage_profile,weekday,season,holiday_bucket,advance_purchase_bucket,provider,currency,amount,departure_date,observed_at,created_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(provider_offer_id) DO NOTHING`)
    .bind(id,o.provider_offer_id,key,dims.route_key,dims.metro_pair,dims.direction,dims.trip_type,dims.nonstop_or_stop,dims.protected_or_self_transfer,dims.fare_brand,dims.baggage_profile,dims.weekday,dims.season,dims.holiday_bucket,dims.advance_purchase_bucket,dims.provider,dims.currency,Number(o.offer_total),d.departure_date,o.observed_at,nowIso).run();
  return {projected:true,baseline_id:id,baseline_key:key,dimensions:dims};
}
function median(xs:number[]){const a=[...xs].sort((x,y)=>x-y);if(!a.length)return null;const m=Math.floor(a.length/2);return a.length%2?a[m]:(a[m-1]+a[m])/2;}
export async function baselineForOffer(db:D1Database,providerOfferId:string,nowIso:string,lookbackDays=180,minSamples=5){
  const self=await db.prepare("SELECT baseline_key,observed_at FROM fare_baseline_observations WHERE provider_offer_id=?").bind(providerOfferId).first<any>();if(!self)return {ready:false,reason:"BASELINE_OBSERVATION_MISSING",sample_count:0};
  const evaluatedAt=Date.parse(nowIso),offerObservedAt=Date.parse(self.observed_at);if(!Number.isFinite(evaluatedAt)||!Number.isFinite(offerObservedAt))return {ready:false,reason:"BASELINE_TIME_INVALID",sample_count:0};
  const cutoff=new Date(Math.min(evaluatedAt,offerObservedAt)).toISOString();
  const since=new Date(Date.parse(cutoff)-lookbackDays*86400000).toISOString();
  const rows=(await db.prepare("SELECT provider_offer_id,amount FROM fare_baseline_observations WHERE baseline_key=? AND observed_at>=? AND observed_at<? AND provider_offer_id<>? ORDER BY observed_at DESC LIMIT 512").bind(self.baseline_key,since,cutoff,providerOfferId).all<any>()).results;
  const amounts=rows.map(r=>Number(r.amount)).filter(Number.isFinite);if(amounts.length<minSamples)return {ready:false,reason:"BASELINE_SAMPLE_INSUFFICIENT",sample_count:amounts.length};
  const sorted=[...amounts].sort((a,b)=>a-b);const p10=sorted[Math.floor((sorted.length-1)*0.10)];return {ready:true,reason:"READY",sample_count:amounts.length,median:median(amounts),p10,baseline_key:self.baseline_key};
}
