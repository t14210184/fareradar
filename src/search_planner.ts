import type { D1Database } from "./types.js";
import { validateExactFlightQuery, enqueueProviderSearch, type ExactFlightQuery } from "./provider_jobs.js";
import { profileBaggageQuery, promotionEntitlementAccess } from "./profile.js";

function isoDate(v:string){return /^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(`${v}T00:00:00Z`));}
function iata(v:string){return /^[A-Z]{3}$/.test(v);}
function uniq<T>(a:T[]){return [...new Set(a)];}
function addDays(d:string,n:number){const x=new Date(`${d}T00:00:00Z`);x.setUTCDate(x.getUTCDate()+n);return x.toISOString().slice(0,10);}
async function sha256Hex(text:string){const d=new TextEncoder().encode(text);const h=await crypto.subtle.digest("SHA-256",d);return [...new Uint8Array(h)].map(x=>x.toString(16).padStart(2,"0")).join("");}
function stable(v:any):string{if(v===null||typeof v!=="object")return JSON.stringify(v);if(Array.isArray(v))return `[${v.map(stable).join(",")}]`;return `{${Object.keys(v).sort().map(k=>JSON.stringify(k)+":"+stable(v[k])).join(",")}}`;}
function parse<T>(s:string):T{return JSON.parse(s) as T;}
function routePair(v:unknown):[string,string]|null{if(typeof v!=="string")return null;const m=v.toUpperCase().match(/^([A-Z]{3})-([A-Z]{3})$/);return m?[m[1],m[2]]:null;}
function travelWindow(raw:string|null|undefined){try{const x=raw?JSON.parse(raw):{};const start=typeof x.start==="string"?x.start.slice(0,10):null;const end=typeof x.end==="string"?x.end.slice(0,10):null;return {start:start&&isoDate(start)?start:null,end:end&&isoDate(end)?end:null};}catch{return {start:null,end:null};}}

export interface SearchCampaignInput {
  campaign_id:string; profile_id:string; provider_id:string;
  origin_airports:string[]; destination_airports:string[]; departure_dates:string[]; trip_lengths_nights:number[];
  passengers:{type?:string;age?:number}[]; cabin_class?:"economy"|"premium_economy"|"business"|"first";
  max_connections?:number; market?:string; locale?:string; max_queries_per_signal?:number; enabled?:boolean; expires_at:string;
}
export function validateSearchCampaign(c:SearchCampaignInput){
  if(!c.campaign_id||!c.profile_id||!c.provider_id)throw new Error("SEARCH_CAMPAIGN_IDENTITY_REQUIRED");
  const origins=uniq(c.origin_airports??[]),destinations=uniq(c.destination_airports??[]),dates=uniq(c.departure_dates??[]),lengths=uniq(c.trip_lengths_nights??[]);
  if(origins.length<1||origins.length>8||origins.some(x=>!iata(x)))throw new Error("SEARCH_CAMPAIGN_ORIGINS_INVALID");
  if(destinations.length<1||destinations.length>16||destinations.some(x=>!iata(x)))throw new Error("SEARCH_CAMPAIGN_DESTINATIONS_INVALID");
  if(dates.length<1||dates.length>32||dates.some(x=>!isoDate(x)))throw new Error("SEARCH_CAMPAIGN_DATES_INVALID");
  if(lengths.length<1||lengths.length>8||lengths.some(x=>!Number.isInteger(x)||x<0||x>30))throw new Error("SEARCH_CAMPAIGN_LENGTHS_INVALID");
  validateExactFlightQuery({slices:[{origin:origins[0],destination:destinations[0],departure_date:dates[0]}],passengers:c.passengers,cabin_class:c.cabin_class,max_connections:c.max_connections});
  const max=c.max_queries_per_signal??6;if(!Number.isInteger(max)||max<1||max>8)throw new Error("SEARCH_CAMPAIGN_QUERY_BUDGET_INVALID");
  if(!Number.isFinite(Date.parse(c.expires_at)))throw new Error("SEARCH_CAMPAIGN_EXPIRY_INVALID");
  return {...c,origin_airports:origins,destination_airports:destinations,departure_dates:dates.sort(),trip_lengths_nights:lengths.sort((a,b)=>a-b),max_queries_per_signal:max,enabled:c.enabled!==false};
}
export async function upsertSearchCampaign(db:D1Database,input:SearchCampaignInput,nowIso:string){
  const c=validateSearchCampaign(input);
  const provider=await db.prepare("SELECT provider_id FROM provider_access_registry WHERE provider_id=?").bind(c.provider_id).first();if(!provider)throw new Error("SEARCH_CAMPAIGN_PROVIDER_UNKNOWN");
  const profile=await db.prepare("SELECT profile_id FROM runtime_profiles WHERE profile_id=?").bind(c.profile_id).first();if(!profile)throw new Error("RUNTIME_PROFILE_NOT_FOUND");
  await db.prepare(`INSERT INTO search_campaigns(campaign_id,profile_id,provider_id,origin_airports_json,destination_airports_json,departure_dates_json,trip_lengths_json,passengers_json,cabin_class,max_connections,market,locale,max_queries_per_signal,enabled,expires_at,created_at,updated_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(campaign_id) DO UPDATE SET profile_id=excluded.profile_id,provider_id=excluded.provider_id,origin_airports_json=excluded.origin_airports_json,destination_airports_json=excluded.destination_airports_json,departure_dates_json=excluded.departure_dates_json,trip_lengths_json=excluded.trip_lengths_json,passengers_json=excluded.passengers_json,cabin_class=excluded.cabin_class,max_connections=excluded.max_connections,market=excluded.market,locale=excluded.locale,max_queries_per_signal=excluded.max_queries_per_signal,enabled=excluded.enabled,expires_at=excluded.expires_at,updated_at=excluded.updated_at`)
    .bind(c.campaign_id,c.profile_id,c.provider_id,JSON.stringify(c.origin_airports),JSON.stringify(c.destination_airports),JSON.stringify(c.departure_dates),JSON.stringify(c.trip_lengths_nights),JSON.stringify(c.passengers),c.cabin_class??null,c.max_connections??null,c.market??null,c.locale??null,c.max_queries_per_signal,c.enabled?1:0,c.expires_at,nowIso,nowIso).run();
  return {campaign_id:c.campaign_id,enabled:c.enabled};
}

export async function planSearchesForQueue(db:D1Database,campaignId:string,queueId:string,nowIso:string){
  const c=await db.prepare("SELECT * FROM search_campaigns WHERE campaign_id=?").bind(campaignId).first<any>();if(!c||!c.enabled||Date.parse(c.expires_at)<=Date.parse(nowIso))throw new Error("SEARCH_CAMPAIGN_INACTIVE");
  const q=await db.prepare("SELECT queue_id,signal_type,signal_id,required_verification,route_scope_json FROM candidate_priority_queue WHERE queue_id=?").bind(queueId).first<any>();if(!q)throw new Error("CANDIDATE_QUEUE_NOT_FOUND");
  if(q.required_verification!=="LIVE_REPRICE")throw new Error("SEARCH_PLANNER_VERIFICATION_UNSUPPORTED");
  const origins=new Set(parse<string[]>(c.origin_airports_json)),dests=new Set(parse<string[]>(c.destination_airports_json));
  const routes=(parse<unknown[]>(q.route_scope_json)??[]).map(routePair).filter((x):x is [string,string]=>!!x).filter(([o,d])=>origins.has(o)&&dests.has(d));
  if(!routes.length)return {created:0,reason:"ROUTE_OUTSIDE_CAMPAIGN"};
  let tw={start:null as string|null,end:null as string|null};
  if(q.signal_type==="PROMOTION"){
    const p=await db.prepare("SELECT travel_window,member_requirement,channel_requirement FROM promotion_events WHERE event_id=?").bind(q.signal_id).first<any>();
    tw=travelWindow(p?.travel_window);
    const access=await promotionEntitlementAccess(db,c.profile_id,{member_requirement:p?.member_requirement??null,channel_requirement:p?.channel_requirement??null},nowIso);
    if(!access.allowed)return {created:0,reason:"PROMOTION_ENTITLEMENT_MISSING",missing:access.missing};
  }
  const dates=parse<string[]>(c.departure_dates_json).filter(d=>(!tw.start||d>=tw.start)&&(!tw.end||d<=tw.end));
  const lengths=parse<number[]>(c.trip_lengths_json); const passengers=parse<any[]>(c.passengers_json); const max=Number(c.max_queries_per_signal)||6;
  const queries:ExactFlightQuery[]=[];
  outer: for(const [origin,destination] of routes.sort((a,b)=>(a[0]+a[1]).localeCompare(b[0]+b[1]))) for(const date of dates.sort()) for(const nights of lengths.sort((a,b)=>a-b)){
    const slices=[{origin,destination,departure_date:date}];
    if(nights>0){const back=addDays(date,nights);if(tw.end&&back>tw.end)continue;slices.push({origin:destination,destination:origin,departure_date:back});}
    const baggage_query=await profileBaggageQuery(db,c.profile_id,slices.length);
    const query:ExactFlightQuery={slices,passengers,cabin_class:c.cabin_class??undefined,max_connections:c.max_connections??undefined,market:c.market??undefined,locale:c.locale??undefined,baggage_query};validateExactFlightQuery(query);queries.push(query);if(queries.length>=max)break outer;
  }
  let created=0;
  for(const query of queries){const fp=await sha256Hex(stable(query));const planId=`plan:${campaignId}:${queueId}:${fp}`;const r=await db.prepare("INSERT OR IGNORE INTO provider_search_plans(plan_id,campaign_id,queue_id,provider_id,query_fingerprint,query_json,state,attempts,next_attempt_at,created_at,updated_at) VALUES(?,?,?,?,?,?,'READY',0,?,?,?)")
      .bind(planId,campaignId,queueId,c.provider_id,fp,JSON.stringify(query),nowIso,nowIso,nowIso).run();created+=Number((r.meta as any)?.changes??0);}
  return {created,planned:queries.length,reason:queries.length?"PLANNED":"NO_EXACT_DATES"};
}

function delayIso(nowIso:string,seconds:number){return new Date(Date.parse(nowIso)+seconds*1000).toISOString();}
export async function dispatchProviderSearchPlans(db:D1Database,nowIso:string,limit=2){
  const rows=(await db.prepare("SELECT plan_id,campaign_id,queue_id,provider_id,query_json,attempts FROM provider_search_plans WHERE state='READY' AND next_attempt_at<=? ORDER BY created_at LIMIT ?").bind(nowIso,Math.min(limit,2)).all<any>()).results;
  let dispatched=0,deferred=0,dead=0;
  for(const r of rows){try{
      const out=await enqueueProviderSearch(db,{provider_id:r.provider_id,mode:"BACKGROUND",query:JSON.parse(r.query_json)},nowIso);
      await db.batch([
        db.prepare("UPDATE provider_search_plans SET state='DISPATCHED',provider_job_id=?,attempts=attempts+1,last_error=NULL,updated_at=? WHERE plan_id=? AND state='READY'").bind(out.job_id,nowIso,r.plan_id),
        db.prepare("INSERT OR IGNORE INTO provider_job_consumers(job_id,plan_id,queue_id,created_at) VALUES(?,?,?,?)").bind(out.job_id,r.plan_id,r.queue_id,nowIso)
      ]); dispatched++;
    }catch(e){const m=e instanceof Error?e.message:String(e);const retryable=m.includes("PROVIDER_ACCESS_NOT_READY")||m.includes("PROVIDER_BACKGROUND_NOT_ALLOWED");if(retryable){await db.prepare("UPDATE provider_search_plans SET attempts=attempts+1,next_attempt_at=?,last_error=?,updated_at=? WHERE plan_id=?").bind(delayIso(nowIso,3600),m,nowIso,r.plan_id).run();deferred++;}else{await db.prepare("UPDATE provider_search_plans SET state='DEAD',attempts=attempts+1,last_error=?,updated_at=? WHERE plan_id=?").bind(m,nowIso,r.plan_id).run();dead++;}}
  }
  return {considered:rows.length,dispatched,deferred,dead};
}

export async function planDueCandidateSearches(db:D1Database,nowIso:string,signalLimit=8,campaignLimit=4){
  const signals=(await db.prepare(`SELECT q.queue_id,q.route_scope_json FROM candidate_priority_queue q
    WHERE q.state='PENDING' AND q.required_verification='LIVE_REPRICE'
    ORDER BY q.priority_score DESC,q.first_observed_at ASC LIMIT ?`).bind(Math.min(signalLimit,8)).all<any>()).results;
  const campaigns=(await db.prepare("SELECT campaign_id,origin_airports_json,destination_airports_json FROM search_campaigns WHERE enabled=1 AND expires_at>? ORDER BY updated_at ASC LIMIT ?").bind(nowIso,Math.min(campaignLimit,4)).all<any>()).results;
  const queueIds=signals.map((x:any)=>x.queue_id); const used=new Set<string>();
  if(queueIds.length){const marks=queueIds.map(()=>'?').join(',');const prior=(await db.prepare(`SELECT queue_id,campaign_id FROM provider_search_plans WHERE queue_id IN (${marks})`).bind(...queueIds).all<any>()).results;for(const x of prior)used.add(`${x.queue_id}|${x.campaign_id}`);}
  for(const q of signals){
    const routes=(parse<unknown[]>(q.route_scope_json)??[]).map(routePair).filter((x):x is [string,string]=>!!x);
    for(const c of campaigns){if(used.has(`${q.queue_id}|${c.campaign_id}`))continue;const origins=new Set(parse<string[]>(c.origin_airports_json)),dests=new Set(parse<string[]>(c.destination_airports_json));if(routes.some(([o,d])=>origins.has(o)&&dests.has(d))){const result=await planSearchesForQueue(db,c.campaign_id,q.queue_id,nowIso);return {queue_id:q.queue_id,campaign_id:c.campaign_id,...result};}}
  }
  return {created:0,reason:"NO_MATCHING_CAMPAIGN"};
}
