import type { D1Database } from "./types.js";

export interface AuthEnv {
  DB:D1Database;
  INGEST_HMAC_SECRETS?:string;
  INGEST_HMAC_SECRET?:string;
  ALLOW_LEGACY_INGEST_TOKEN?:string;
}
export interface AuthPrincipal {key_id:string;role:string;source_id:string|null;agency_id:string|null;legacy:boolean;}
const enc=new TextEncoder();
function hex(a:ArrayBuffer){return [...new Uint8Array(a)].map(x=>x.toString(16).padStart(2,"0")).join("");}
function safeEq(a:string,b:string){if(a.length!==b.length)return false;let x=0;for(let i=0;i<a.length;i++)x|=a.charCodeAt(i)^b.charCodeAt(i);return x===0;}
async function sha256(text:string){return hex(await crypto.subtle.digest("SHA-256",enc.encode(text)));}
async function sign(secret:string,msg:string){const k=await crypto.subtle.importKey("raw",enc.encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);return hex(await crypto.subtle.sign("HMAC",k,enc.encode(msg)));}
function validNonce(n:string){return /^[A-Za-z0-9_-]{16,128}$/.test(n);}
function parseSecrets(raw:string|undefined){if(!raw)return {} as Record<string,string>;try{const x=JSON.parse(raw);if(!x||typeof x!=="object"||Array.isArray(x))return {};return Object.fromEntries(Object.entries(x).filter(([,v])=>typeof v==="string"&&v.length>=16)) as Record<string,string>;}catch{return {};}}
function timeValid(value:string|null|undefined,now:number,before:boolean){if(!value)return true;const t=Date.parse(value);if(!Number.isFinite(t))return false;return before?t<=now:t>now;}
function pathAllowed(raw:string,path:string){try{const xs=JSON.parse(raw);return Array.isArray(xs)&&xs.some(x=>typeof x==="string"&&x.startsWith("/")&&(x.endsWith("/")?path.startsWith(x):path===x));}catch{return false;}}

export async function authorizeRequest(req:Request,body:string,env:AuthEnv):Promise<AuthPrincipal|null>{
  const ts=req.headers.get("x-fare-timestamp")??"";const n=Number(ts);const now=Date.now();if(!Number.isFinite(n)||Math.abs(now-n)>300000)return null;
  const keyId=req.headers.get("x-fare-key-id")??"";const nonce=req.headers.get("x-fare-nonce")??"";const sig=req.headers.get("x-fare-signature")??"";
  if(keyId&&nonce&&sig){
    if(!validNonce(nonce))return null;
    const row=await env.DB.prepare("SELECT key_id,role,source_id,agency_id,secret_slot,allowed_paths_json,enabled,not_before,expires_at FROM ingest_auth_keys WHERE key_id=?").bind(keyId).first<any>();
    if(!row||Number(row.enabled)!==1||!timeValid(row.not_before,now,true)||!timeValid(row.expires_at,now,false))return null;
    const path=new URL(req.url).pathname;if(!pathAllowed(row.allowed_paths_json,path))return null;
    const secret=parseSecrets(env.INGEST_HMAC_SECRETS)[row.secret_slot];if(!secret)return null;
    const bodyHash=await sha256(body);const canonical=[keyId,ts,nonce,req.method.toUpperCase(),path,bodyHash].join("\n");if(!safeEq(sig,await sign(secret,canonical)))return null;
    const requestHash=await sha256(canonical);const usedAt=new Date(now).toISOString();const expiresAt=new Date(now+10*60_000).toISOString();
    try{await env.DB.prepare("INSERT INTO used_request_nonces(key_id,nonce,request_sha256,used_at,expires_at) VALUES(?,?,?,?,?)").bind(keyId,nonce,requestHash,usedAt,expiresAt).run();}catch{return null;}
    return {key_id:keyId,role:row.role,source_id:row.source_id??null,agency_id:row.agency_id??null,legacy:false};
  }
  if(env.ALLOW_LEGACY_INGEST_TOKEN==="1"&&env.INGEST_HMAC_SECRET&&sig){const expected=await sign(env.INGEST_HMAC_SECRET,`${ts}.${body}`);if(safeEq(sig,expected))return {key_id:"legacy",role:"LEGACY_TEST_ONLY",source_id:null,agency_id:null,legacy:true};}
  return null;
}

export function principalAllowsPayload(p:AuthPrincipal,payload:any,path:string){
  if(p.legacy)return true;
  if(path==="/ingest/agency"&&p.agency_id&&payload?.agency_id!==p.agency_id)return false;
  if((path==="/ingest/email"||path==="/ingest")&&p.source_id&&payload?.source_id!==p.source_id)return false;
  return true;
}
export async function cleanupExpiredNonces(db:D1Database,nowIso:string){await db.prepare("DELETE FROM used_request_nonces WHERE expires_at<=?").bind(nowIso).run();}
