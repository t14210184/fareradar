import type { CandidatePlanInput, D1Database } from "./types.js";
import { persistCandidatePlan } from "./intake.js";

export interface Env { DB:D1Database; INGEST_HMAC_SECRET:string; }
const enc=new TextEncoder();
function hex(a:ArrayBuffer){return [...new Uint8Array(a)].map(x=>x.toString(16).padStart(2,"0")).join("");}
async function sign(secret:string,msg:string){const k=await crypto.subtle.importKey("raw",enc.encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);return hex(await crypto.subtle.sign("HMAC",k,enc.encode(msg)));}
function safeEq(a:string,b:string){if(a.length!==b.length)return false;let x=0;for(let i=0;i<a.length;i++)x|=a.charCodeAt(i)^b.charCodeAt(i);return x===0;}
async function authorized(req:Request,body:string,secret:string){const ts=req.headers.get("x-fare-timestamp")??"";const sig=req.headers.get("x-fare-signature")??"";const n=Number(ts);if(!Number.isFinite(n)||Math.abs(Date.now()-n)>300000)return false;return safeEq(sig,await sign(secret,`${ts}.${body}`));}
function json(data:unknown,status=200){return new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json"}});}

const worker={
  async fetch(req:Request,env:Env):Promise<Response>{
    const u=new URL(req.url);
    if(req.method==="GET"&&u.pathname==="/health")return json({ok:true,spec:"1.3"});
    if(req.method==="POST"&&u.pathname==="/candidate-plan/intake"){
      const body=await req.text(); if(!await authorized(req,body,env.INGEST_HMAC_SECRET))return json({error:"UNAUTHORIZED"},401);
      try{const payload=JSON.parse(body) as CandidatePlanInput;const r=await persistCandidatePlan(env.DB,payload);return json({ok:true,...r},202);}catch(e){const m=e instanceof Error?e.message:String(e);return json({error:m},m==="IDEMPOTENCY_CONFLICT"?409:400);}
    }
    return json({error:"NOT_FOUND"},404);
  }
};
export default worker;
