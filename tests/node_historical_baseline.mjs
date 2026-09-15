import { DatabaseSync } from 'node:sqlite'; import fs from 'node:fs';
import { ingestOfferSnapshot } from '../dist/offers.js';
import { projectDomainEvents } from '../dist/ingest.js';
import { baselineForOffer } from '../dist/baseline.js';
class S{constructor(s){this.s=s;this.a=[]}bind(...a){this.a=a;return this}async run(){return{success:true,meta:this.s.run(...this.a)}}async first(){return this.s.get(...this.a)??null}async all(){return{results:this.s.all(...this.a)}}}
class D{constructor(x){this.x=x}prepare(q){return new S(this.x.prepare(q))}async batch(a){this.x.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of a)o.push(await s.run());this.x.exec('COMMIT');return o}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:');for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort())raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));const db=new D(raw);
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner) values('p1','OFFICIAL_API','2026-09-15T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test')").run();
const oneWay={slices:[{segments:[{origin:'TPE',destination:'KIX',departing_at:'2026-11-03T01:00:00Z',arriving_at:'2026-11-03T03:30:00Z'}]}]};
const roundTrip={slices:[{segments:[{origin:'TPE',destination:'KIX',departing_at:'2026-11-03T01:00:00Z',arriving_at:'2026-11-03T03:30:00Z'}]},{segments:[{origin:'KIX',destination:'TPE',departing_at:'2026-11-06T04:00:00Z',arriving_at:'2026-11-06T07:00:00Z'}]}]};
const bag='{"checked_bags_by_slice":[0],"checked_bag_kg":0,"seat_required":false}';
async function add(id,amount,day,{structure=oneWay,currency='TWD',live='LIVE',baggage=bag}={}){return ingestOfferSnapshot(db,{provider_offer_id:id,query_fingerprint:`q-${id}`,provider:'p1',currency,baggage_query:baggage,observed_at:`2026-09-${String(day).padStart(2,'0')}T00:00:00Z`,expires_at:'2026-10-01T00:00:00Z',raw_sha256:String(id.charCodeAt(0)%10).repeat(64),offer_total:amount,fare_freshness:'REFRESHED_LIVE',cached_or_live:live,offer_structure:structure});}
for(const [i,a] of [7000,6800,7200,6900,7100].entries())await add(`hist-${i}`,a,15+i);
await add('current',4000,20);
await add('round',3500,20,{structure:roundTrip});
await add('bagged',3600,20,{baggage:'{"checked_bags_by_slice":[1],"checked_bag_kg":20,"seat_required":false}'});
await add('cached',3000,20,{live:'CACHED'});
await add('usd',100,20,{currency:'USD'});
const projected=await projectDomainEvents(db,'2026-09-21T00:00:00Z','baseline-test',20);
const current=await baselineForOffer(db,'current','2026-09-21T00:00:00Z',180,5);
const round=await baselineForOffer(db,'round','2026-09-21T00:00:00Z',180,5);
const cached=await baselineForOffer(db,'cached','2026-09-21T00:00:00Z',180,5);
const rows=raw.prepare('select provider_offer_id,trip_type,baggage_profile,currency from fare_baseline_observations order by provider_offer_id').all();
console.log(JSON.stringify({projected,current,round,cached,count:rows.length,rows}));
