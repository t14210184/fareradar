export interface SourceProvenance { source_id:string; canonical_url?:string|null; observed_at:string; content_sha256:string; parser_version?:string|null; access_basis:string; }
export function provenanceValid(p:SourceProvenance){ return !!p.source_id && /^https:\/\//.test(p.canonical_url??"") && !Number.isNaN(Date.parse(p.observed_at)) && /^[a-f0-9]{64}$/.test(p.content_sha256) && !!p.access_basis; }
export interface PromotionFingerprintInput {market:string;airline?:string;routes:string[];sale_start?:string;sale_end?:string;travel_start?:string;travel_end?:string;promo_code?:string;member_requirement?:string|null;channel_requirement?:string|null;sale_direction?:string|null;required_roundtrip?:boolean;eligible_flight_numbers?:string[];eligible_weekdays?:number[];blackout_dates?:string[];origin_market?:string|null;sales_currency?:string|null;member_only?:boolean;subscription_only?:boolean;coupon_required?:boolean;fare_brand?:string|null;baggage_bundle?:string|null;minimum_stay?:number|null;maximum_stay?:number|null;stopover_allowed?:boolean|null;open_jaw_allowed?:boolean|null;change_rule?:string|null;refund_rule?:string|null;}
export function promotionFingerprint(p:PromotionFingerprintInput){const rules={sale_end:p.sale_end??"",travel_end:p.travel_end??"",sale_direction:p.sale_direction??"",required_roundtrip:!!p.required_roundtrip,eligible_flight_numbers:[...(p.eligible_flight_numbers??[])].sort(),eligible_weekdays:[...(p.eligible_weekdays??[])].sort((a,b)=>a-b),blackout_dates:[...(p.blackout_dates??[])].sort(),origin_market:p.origin_market??"",sales_currency:p.sales_currency??"",member_requirement:p.member_requirement??"",channel_requirement:p.channel_requirement??"",member_only:!!p.member_only,subscription_only:!!p.subscription_only,coupon_required:!!p.coupon_required,fare_brand:p.fare_brand??"",baggage_bundle:p.baggage_bundle??"",minimum_stay:p.minimum_stay??null,maximum_stay:p.maximum_stay??null,stopover_allowed:p.stopover_allowed??null,open_jaw_allowed:p.open_jaw_allowed??null,change_rule:p.change_rule??"",refund_rule:p.refund_rule??""};return [p.market,p.airline??"",[...p.routes].sort().join(","),p.sale_start??"",p.travel_start??"",p.promo_code??"",JSON.stringify(rules)].join("|").toLowerCase();}
export function promoEligible(p:{direction?:string;required_weekdays?:number[];sale_from?:string;sale_to?:string},q:{direction:string;weekday:number;at:string}){
  const t=Date.parse(q.at); if(p.direction&&p.direction!==q.direction)return false; if(p.required_weekdays&&!p.required_weekdays.includes(q.weekday))return false; if(p.sale_from&&t<Date.parse(p.sale_from))return false; if(p.sale_to&&t>Date.parse(p.sale_to))return false; return true;
}
export function clearanceState(i:{seller_verified:boolean;official_readback:boolean;anonymous_payment:boolean}){ if(i.anonymous_payment)return "AGENCY_RECONFIRM_REQUIRED"; if(i.seller_verified&&i.official_readback)return "SELLER_CONFIRMED"; if(i.seller_verified)return "AGENCY_CLAIMED"; return "INVENTORY_UNVERIFIED"; }
export function emailTrust(i:{dkim:"PASS"|"FAIL"|"UNKNOWN";spf:"PASS"|"FAIL"|"UNKNOWN";dmarc:"PASS"|"FAIL"|"UNKNOWN";links:string[]}){ const unsafe=i.links.some(x=>!x.startsWith("https://")); if(unsafe||i.dkim!=="PASS"||i.dmarc!=="PASS")return "UNTRUSTED"; return i.spf==="FAIL"?"REVIEW":"TRUSTED"; }
export function dispatchAllowed(i:{terms_state:string;access_valid:boolean;kill_switch:boolean;retry_after_until?:string|null},nowIso:string){ if(i.kill_switch||!i.access_valid||i.terms_state!=="CURRENT")return false; if(i.retry_after_until&&Date.parse(i.retry_after_until)>Date.parse(nowIso))return false; return true; }
export function adaptiveSchedule(m:{confirmed_rate:number;first_win_rate:number;duplicate_rate:number;ghost_rate:number;schema_drift_rate:number}){
  if(m.schema_drift_rate>=0.2||m.ghost_rate>=0.7)return "QUARANTINE";
  const u=0.35*m.confirmed_rate+0.30*m.first_win_rate-0.20*m.duplicate_rate-0.15*m.ghost_rate;
  if(u>=0.45)return "BOOST"; if(u>=0.12)return "KEEP"; return "DOWNSHIFT";
}
export function routeUniverseDiff(before:string[],after:string[]){const b=new Set(before);return after.filter(x=>!b.has(x)).sort();}
export function socialRetention(input:{privacy_class:"PUBLIC"|"PRIVATE_NOTIFICATION";raw_body?:string;content_sha256:string}){return input.privacy_class==="PRIVATE_NOTIFICATION"?{content_sha256:input.content_sha256,raw_body:null}:{content_sha256:input.content_sha256,raw_body:input.raw_body??null};}

export interface PromotionSignal { market:string; routes:string[]; prices:{currency:string;amount:number}[]; promo_code:string|null; keywords:string[]; member_requirement:string|null; channel_requirement:string|null; eligible_flight_numbers:string[]; required_roundtrip:boolean; coupon_required:boolean; sales_currency:string|null; }
export function extractPromotionText(text:string,market="TW"):PromotionSignal|null {
  const routes=[...text.matchAll(/\b(TPE|KHH|RMQ|TSA)\s*(?:-|–|→|to|至)\s*([A-Z]{3})\b/gi)].map(m=>`${m[1].toUpperCase()}-${m[2].toUpperCase()}`);
  const prices:{currency:string;amount:number}[]=[];
  for(const [currency,re] of [["TWD",/(?:NT\$|TWD\s*)([0-9][0-9,]{2,})/gi],["JPY",/(?:JPY\s*|¥\s*)([0-9][0-9,]{2,})/gi]] as const){ for(const m of text.matchAll(re))prices.push({currency,amount:Number(m[1].replaceAll(",",""))}); }
  const promo=text.match(/(?:優惠碼|折扣碼|promo\s*code)\s*[:：]?\s*([A-Z0-9_-]{3,20})/i);
  const keywords=["特價","促銷","清艙","清倉","限時","flash sale","sale"].filter(k=>text.toLowerCase().includes(k.toLowerCase()));
  const member_requirement=/team\s*tiger|尊榮虎/i.test(text)?"TEAM_TIGER":/(?:會員(?:限定|專屬)|member[-\s]?only)/i.test(text)?"MEMBER_ONLY":null;
  const channel_requirements:string[]=[];if(/樂虎卡/.test(text))channel_requirements.push("LOHO_CARD");if(/(?:app\s*(?:only|限定)|APP限定)/i.test(text))channel_requirements.push("APP_ONLY");if(/(?:line\s*(?:only|限定)|LINE限定)/i.test(text))channel_requirements.push("LINE_ONLY");const channel_requirement=channel_requirements.length?[...new Set(channel_requirements)].sort().join("+"):null;
  const flights:string[]=[];
  for(const m of text.matchAll(/(?:航班|班機|flight(?:s)?(?:\s*no\.?)?)\s*[:：#]?\s*((?:[A-Z0-9]{2}\s?\d{2,4})(?:\s*[\/、,，]\s*[A-Z0-9]{2}\s?\d{2,4})*)/gi))for(const f of m[1].matchAll(/[A-Z0-9]{2}\s?\d{2,4}/gi))flights.push(f[0].replace(/\s+/g,"").toUpperCase());
  for(const m of text.matchAll(/\b([A-Z0-9]{2}\d{2,4})\b\s*(?:航班|班機)/gi))flights.push(m[1].toUpperCase());
  const required_roundtrip=/(?:限|僅限|須|需).{0,6}(?:來回|round[\s-]?trip)|(?:來回|round[\s-]?trip).{0,6}(?:限定|only|must)/i.test(text);
  const coupon_required=!!promo||/(?:須|需|請).{0,5}(?:輸入|使用).{0,5}(?:優惠碼|折扣碼|promo\s*code)/i.test(text);
  const currencies=[...new Set(prices.map(x=>x.currency))];const sales_currency=currencies.length===1?currencies[0]:null;
  if(!routes.length&&!prices.length&&!keywords.length)return null;
  return {market,routes:[...new Set(routes)].sort(),prices,promo_code:promo?.[1]?.toUpperCase()??null,keywords,member_requirement,channel_requirement,eligible_flight_numbers:[...new Set(flights)].sort(),required_roundtrip,coupon_required,sales_currency};
}
