import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import { persistCandidatePlan } from '../dist/intake.js';
import { ingestOfferSnapshot } from '../dist/offers.js';
import { projectDomainEvents } from '../dist/ingest.js';
class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const raw=new DatabaseSync(':memory:');
for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8'));
raw.exec(fs.readFileSync(new URL('../generated/seed.generated.sql',import.meta.url),'utf8'));
const db=new DB(raw);
raw.prepare("insert into provider_access_registry(provider_id,access_basis,terms_snapshot_at,rate_policy,look_to_book_budget,kill_switch_state,owner) values('test-provider','OFFICIAL_API','2026-09-01T00:00:00Z','TARGETED_ONLY',1000,'CLEAR','test')").run();
await ingestOfferSnapshot(db,{provider_offer_id:'off1',query_fingerprint:'q1',provider:'test-provider',currency:'TWD',observed_at:'2026-09-15T00:10:00Z',expires_at:'2026-09-15T12:00:00Z',raw_sha256:'f'.repeat(64),offer_total:5000,fare_freshness:'LIVE',cached_or_live:'LIVE'});
for(const [id,source,at] of [['obs-tiger','tigerair_tw_official','2026-09-15T00:00:00Z'],['obs-peach','peach_tw_official','2026-09-15T00:02:00Z'],['obs-tiger-later','tigerair_tw_official','2026-09-15T00:03:00Z']]) raw.prepare("insert into source_observations(observation_id,source_id,observed_at,canonical_url,content_sha256,parser_version,access_basis,privacy_class,access_basis_snapshot,retention_until,content_version) values(?,?,?,?,?,'test','PUBLIC','PUBLIC','PUBLIC','2026-12-15T00:00:00Z',1)").run(id,source,at,`https://example.test/${id}`,'a'.repeat(64));
const payload=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
payload.discovery_evidence_ids=['obs-peach','obs-tiger-later','obs-tiger'];
await persistCandidatePlan(db,payload,'2026-09-15T00:15:00Z');
const first=await projectDomainEvents(db,'2026-09-15T00:16:00Z','cron',10);
await persistCandidatePlan(db,payload,'2026-09-15T00:17:00Z');
const second=await projectDomainEvents(db,'2026-09-15T00:18:00Z','cron',10);
const attrs=raw.prepare("select source_id,observation_id,first_win from source_outcome_attributions order by source_id").all();
const health=raw.prepare("select source_id,confirmed_count,first_win_count from source_health_windows where window_date='2026-09-15' and source_id in ('tigerair_tw_official','peach_tw_official') order by source_id").all();
console.log(JSON.stringify({first,second,attrs,health,outbox:raw.prepare("select state,count(*) n from domain_outbox group by state order by state").all()}));
