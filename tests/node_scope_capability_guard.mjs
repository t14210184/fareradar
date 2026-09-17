import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { authorizeRequest } from '../dist/auth.js';
import { installKey, authEnv, signedRequest } from './scoped_auth_helper.mjs';

class S{constructor(s){this.s=s;this.a=[]}bind(...a){this.a=a;return this}async run(){return{success:true,meta:this.s.run(...this.a)}}async first(){return this.s.get(...this.a)??null}async all(){return{results:this.s.all(...this.a)}}}
class D{constructor(x){this.x=x}prepare(q){return new S(this.x.prepare(q))}async batch(a){const out=[];this.x.exec('BEGIN IMMEDIATE');try{for(const s of a)out.push(await s.run());this.x.exec('COMMIT');return out}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');
for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));
const db=new D(raw);const secret='scope-capability-secret-0123456789';const env=authEnv(db,secret);
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner) values('duffel','OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test')").run();
installKey(raw,{keyId:'source-broad',role:'EMAIL_PUSH',sourceId:'source-1',allowedPaths:['/']});
installKey(raw,{keyId:'agency-broad',role:'AGENCY_PARTNER',agencyId:'agency-1',allowedPaths:['/']});
installKey(raw,{keyId:'provider-broad',role:'PROVIDER_WORKER',providerId:'duffel',allowedPaths:['/']});
installKey(raw,{keyId:'multi-broad',role:'TEST',sourceId:'source-1',providerId:'duffel',allowedPaths:['/']});
installKey(raw,{keyId:'internal-broad',role:'TEST',allowedPaths:['/']});

async function auth(keyId,path,body='{}'){
  const req=await signedRequest(`https://fare.example${path}`,body,{keyId,secret});
  return await authorizeRequest(req,body,env);
}
const sourceAllowed=await auth('source-broad','/ingest/email',JSON.stringify({source_id:'source-1'}));
const sourceCross=await auth('source-broad','/notifications/lease',JSON.stringify({worker_id:'n'}));
const agencyAllowed=await auth('agency-broad','/ingest/agency',JSON.stringify({agency_id:'agency-1'}));
const agencyCross=await auth('agency-broad','/profiles/upsert','{}');
const providerAllowed=await auth('provider-broad','/offers/ingest',JSON.stringify({provider:'duffel'}));
const providerCross=await auth('provider-broad','/sources/disable',JSON.stringify({source_id:'source-1'}));
const multiScope=await auth('multi-broad','/ingest',JSON.stringify({source_id:'source-1'}));
const internalAllowed=await auth('internal-broad','/profiles/upsert','{}');
console.log(JSON.stringify({
  source_allowed:!!sourceAllowed,
  source_cross:!!sourceCross,
  agency_allowed:!!agencyAllowed,
  agency_cross:!!agencyCross,
  provider_allowed:!!providerAllowed,
  provider_cross:!!providerCross,
  multi_scope:!!multiScope,
  internal_allowed:!!internalAllowed
}));
