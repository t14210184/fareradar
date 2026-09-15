import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import worker from '../dist/worker.js';
import { installKey, authEnv, signedRequest } from './scoped_auth_helper.mjs';
class S{constructor(s){this.s=s;this.a=[]}bind(...a){this.a=a;return this}async run(){return{success:true,meta:this.s.run(...this.a)}}async first(){return this.s.get(...this.a)??null}async all(){return{results:this.s.all(...this.a)}}}
class D{constructor(x){this.x=x}prepare(q){return new S(this.x.prepare(q))}async batch(a){const out=[];this.x.exec('BEGIN IMMEDIATE');try{for(const s of a)out.push(await s.run());this.x.exec('COMMIT');return out}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const db=new D(raw);
raw.prepare("insert into source_registry(source_id,source_class,canonical_domain_or_account,access_basis,verification_authority,lifecycle_state,min_interval_ms,kill_switch,entrypoint_url,fetch_method,terms_snapshot_at) values('src-1','AIRLINE','https://example.com','PUBLIC_WEB','DISCOVERY_ONLY','SHADOW',60000,0,'https://example.com/deals','STATIC_HTML_DIFF','2026-09-01T00:00:00Z')").run();
raw.prepare("insert into agency_partner_registry(agency_id,source_id,status,verified_business,terms_snapshot_at) values('agency-1','src-1','ENABLED',1,'2026-09-01T00:00:00Z')").run();
for(const p of ['duffel','other'])raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner,connector_state,supported_verification_json,background_allowed) values(?,'OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test','IMPLEMENTED','[\"LIVE_REPRICE\",\"CHECKOUT_REPRICE\"]',0)").run(p);
const secret='role-boundary-secret-0123456789';const env=authEnv(db,secret);
installKey(raw,{keyId:'agency-broad',role:'AGENCY_PARTNER',agencyId:'agency-1',allowedPaths:['/']});
installKey(raw,{keyId:'email-broad',role:'EMAIL_PUSH',sourceId:'src-1',allowedPaths:['/']});
installKey(raw,{keyId:'provider-broad',role:'PROVIDER_WORKER',providerId:'duffel',allowedPaths:['/']});
installKey(raw,{keyId:'agency-unbound',role:'AGENCY_PARTNER',agencyId:null,allowedPaths:['/agency-rechecks/lease']});
installKey(raw,{keyId:'email-unbound',role:'EMAIL_PUSH',sourceId:null,allowedPaths:['/ingest/email']});
installKey(raw,{keyId:'provider-unbound',role:'PROVIDER_WORKER',providerId:null,allowedPaths:['/providers/runtime/readback']});
async function post(keyId,path,payload){const body=JSON.stringify(payload);return worker.fetch(await signedRequest(`https://fare.example${path}`,body,{keyId,secret}),env)}
const agencyOperational=await post('agency-broad','/notifications/lease',{worker_id:'wrong-role'});
const emailOperational=await post('email-broad','/sources/disable',{source_id:'src-1',reason:'wrong-role'});
const providerOperational=await post('provider-broad','/notifications/lease',{worker_id:'wrong-role'});
const agencyUnbound=await post('agency-unbound','/agency-rechecks/lease',{agency_id:'agency-1',worker_id:'w',limit:1});
const emailUnbound=await post('email-unbound','/ingest/email',{source_id:'src-1'});
const providerUnbound=await post('provider-unbound','/providers/runtime/readback',{provider_id:'duffel',worker_id:'w',connector_version:'1',credentials_present:true,capabilities:['LIVE_REPRICE']});
const crossPricing=await post('provider-broad','/provider-pricing/ingest',{pricing_snapshot_id:'cross-price',provider_id:'other',usage_window_kind:'CALENDAR_MONTH',search_to_book_threshold:10,hard_search_cap:100,currency:'TWD',rate_json:{},source_url:'https://other.example/rates',raw_sha256:'a'.repeat(64),observed_at:'2026-09-15T00:00:00Z',effective_from:'2026-09-15T00:00:00Z',expires_at:'2099-01-01T00:00:00Z'});
const crossPayment=await post('provider-broad','/payment-profiles/upsert',{payment_profile_id:'cross-payment',provider_id:'other',payment_method_class:'CARD',credential_binding:'OTHER_CARD_ID',enabled:true,expires_at:'2099-01-01T00:00:00Z'});
console.log(JSON.stringify({agency_operational:agencyOperational.status,email_operational:emailOperational.status,provider_operational:providerOperational.status,agency_unbound:agencyUnbound.status,email_unbound:emailUnbound.status,provider_unbound:providerUnbound.status,cross_pricing:crossPricing.status,cross_payment:crossPayment.status,other_pricing:raw.prepare("select count(*) n from provider_pricing_snapshots where provider_id='other'").get().n,other_payment:raw.prepare("select count(*) n from runtime_payment_profiles where provider_id='other'").get().n,source_state:raw.prepare("select lifecycle_state from source_registry where source_id='src-1'").get().lifecycle_state}));
