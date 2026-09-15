import type { D1Database } from "./types.js";

function normalizeHost(value:string|null|undefined){
  if(!value)return null;
  try{const u=value.includes("://")?new URL(value):new URL(`https://${value}`);if(u.protocol!=="https:")return null;return u.hostname.toLowerCase().replace(/\.$/,"");}catch{return null;}
}
function matches(host:string,allowed:string){return host===allowed||host.endsWith(`.${allowed}`);}
export async function agencyAllowedDomains(db:D1Database,agencyId:string,bookingChannel?:string|null){
  const row=await db.prepare(`SELECT p.source_id,s.canonical_domain_or_account FROM agency_partner_registry p JOIN source_registry s ON s.source_id=p.source_id WHERE p.agency_id=?`).bind(agencyId).first<any>();
  if(!row)throw new Error("AGENCY_PARTNER_NOT_FOUND");
  const domains=new Set<string>();const sourceHost=normalizeHost(row.canonical_domain_or_account);if(sourceHost)domains.add(sourceHost);const bookingHost=normalizeHost(bookingChannel);if(bookingHost)domains.add(bookingHost);return [...domains];
}
export async function assertAgencyUrlAllowed(db:D1Database,agencyId:string,url:string,bookingChannel?:string|null){
  const host=normalizeHost(url);if(!host)throw new Error("AGENCY_URL_INVALID");const domains=await agencyAllowedDomains(db,agencyId,bookingChannel);if(!domains.length||!domains.some(d=>matches(host,d)))throw new Error("AGENCY_URL_DOMAIN_MISMATCH");return host;
}
