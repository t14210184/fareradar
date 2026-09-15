import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import worker from '../dist/worker.js';

class Stmt { constructor(s){this.s=s;this.args=[]} bind(...v){this.args=v;return this} async run(){return {success:true,meta:this.s.run(...this.args)}} async first(){return this.s.get(...this.args)??null} async all(){return {results:this.s.all(...this.args)}} }
class DB { constructor(db){this.db=db} prepare(sql){return new Stmt(this.db.prepare(sql))} async batch(stmts){this.db.exec('BEGIN IMMEDIATE');try{const o=[];for(const s of stmts)o.push(await s.run());this.db.exec('COMMIT');return o}catch(e){this.db.exec('ROLLBACK');throw e}} }
const migration=fs.readFileSync(new URL('../migrations/0001_core.sql',import.meta.url),'utf8');
const raw=new DatabaseSync(':memory:'); raw.exec(migration); const db=new DB(raw);
const body=fs.readFileSync(process.argv[2],'utf8'); const secret='test-secret';
const ts=String(Date.now()); const enc=new TextEncoder(); const key=await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']); const sigBuf=await crypto.subtle.sign('HMAC',key,enc.encode(`${ts}.${body}`)); const sig=[...new Uint8Array(sigBuf)].map(x=>x.toString(16).padStart(2,'0')).join('');
const env={DB:db,INGEST_HMAC_SECRET:secret};
const req=new Request('https://fare.example/candidate-plan/intake',{method:'POST',headers:{'x-fare-timestamp':ts,'x-fare-signature':sig,'content-type':'application/json'},body});
const res=await worker.fetch(req,env); const payload=await res.json();
const bad=new Request('https://fare.example/candidate-plan/intake',{method:'POST',headers:{'x-fare-timestamp':ts,'x-fare-signature':'00'},body}); const badRes=await worker.fetch(bad,env);
const staleTs=String(Date.now()-600000); const staleSigBuf=await crypto.subtle.sign('HMAC',key,enc.encode(`${staleTs}.${body}`)); const staleSig=[...new Uint8Array(staleSigBuf)].map(x=>x.toString(16).padStart(2,'0')).join('');
const staleReq=new Request('https://fare.example/candidate-plan/intake',{method:'POST',headers:{'x-fare-timestamp':staleTs,'x-fare-signature':staleSig},body}); const staleRes=await worker.fetch(staleReq,env);
console.log(JSON.stringify({status:res.status,payload,bad_status:badRes.status,stale_status:staleRes.status,count:raw.prepare('select count(*) n from itinerary_candidates').get().n}));
