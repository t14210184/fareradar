import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import worker from '../dist/worker.js';
import { installKey, authEnv, signedRequest } from './scoped_auth_helper.mjs';
class S{constructor(s){this.s=s;this.a=[]}bind(...a){this.a=a;return this}async run(){return{success:true,meta:this.s.run(...this.a)}}async first(){return this.s.get(...this.a)??null}async all(){return{results:this.s.all(...this.a)}}}
class D{constructor(x){this.x=x}prepare(q){return new S(this.x.prepare(q))}async batch(a){const out=[];this.x.exec('BEGIN IMMEDIATE');try{for(const s of a)out.push(await s.run());this.x.exec('COMMIT');return out}catch(e){this.x.exec('ROLLBACK');throw e}}}
const raw=new DatabaseSync(':memory:'); for(const f of fs.readdirSync(new URL('../migrations/',import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) raw.exec(fs.readFileSync(new URL(`../migrations/${f}`,import.meta.url),'utf8')); const db=new D(raw);
const secret='reviewer-secret-0123456789'; const env=authEnv(db,secret);
for(const role of ['ACCESS_REVIEWER','SHADOW_REVIEWER']){
  const keyId=role.toLowerCase(); installKey(raw,{keyId,role,allowedPaths:['/']});
  for(const [path,payload] of [['/notifications/lease',{worker_id:'w'}],['/sources/disable',{source_id:'s'}],['/provider-search/enqueue',{provider_id:'p'}]]){
    const r=await worker.fetch(await signedRequest(`https://fare.example${path}`,JSON.stringify(payload),{keyId,secret}),env);
    if(r.status!==401) throw new Error(`${role} unexpectedly authorized ${path}: ${r.status}`);
  }
}
console.log(JSON.stringify({ok:true}));
