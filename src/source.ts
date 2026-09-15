export interface SourceProvenance { source_id:string; canonical_url?:string|null; observed_at:string; content_sha256:string; parser_version?:string|null; access_basis:string; }
export function provenanceValid(p:SourceProvenance){ return !!p.source_id && /^https:\/\//.test(p.canonical_url??"") && !Number.isNaN(Date.parse(p.observed_at)) && /^[a-f0-9]{64}$/.test(p.content_sha256) && !!p.access_basis; }
export function promotionFingerprint(p:{market:string;airline?:string;routes:string[];sale_start?:string;travel_start?:string;promo_code?:string}){return [p.market,p.airline??"",[...p.routes].sort().join(","),p.sale_start??"",p.travel_start??"",p.promo_code??""].join("|").toLowerCase();}
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
