let nonceSeq=0;
const enc=new TextEncoder();
function hex(buf){return [...new Uint8Array(buf)].map(x=>x.toString(16).padStart(2,'0')).join('');}
export function installKey(raw,{keyId='test-key',role='TEST',sourceId=null,agencyId=null,providerId=null,secretSlot='test-slot',allowedPaths=['/'],enabled=1,notBefore=null,expiresAt='2099-01-01T00:00:00Z'}={}){
  raw.prepare("insert into ingest_auth_keys(key_id,role,source_id,agency_id,provider_id,secret_slot,allowed_paths_json,enabled,not_before,expires_at,created_at) values(?,?,?,?,?,?,?,?,?,?,?)")
    .run(keyId,role,sourceId,agencyId,providerId,secretSlot,JSON.stringify(allowedPaths),enabled,notBefore,expiresAt,'2026-09-15T00:00:00Z');
  return {keyId,secretSlot};
}
export function authEnv(db,secret='test-secret-0123456789',secretSlot='test-slot'){return {DB:db,INGEST_HMAC_SECRETS:JSON.stringify({[secretSlot]:secret})};}
export async function signedRequest(url,body,{keyId='test-key',secret='test-secret-0123456789',method='POST',nonce,ts,headers={}}={}){
  ts=ts??String(Date.now()); nonce=nonce??`nonce-${Date.now()}-${++nonceSeq}-abcdef`;
  const path=new URL(url).pathname; const bodyHash=hex(await crypto.subtle.digest('SHA-256',enc.encode(body)));
  const key=await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  const canonical=[keyId,ts,nonce,method.toUpperCase(),path,bodyHash].join('\n');
  const sig=hex(await crypto.subtle.sign('HMAC',key,enc.encode(canonical)));
  return new Request(url,{method,headers:{'x-fare-key-id':keyId,'x-fare-timestamp':ts,'x-fare-nonce':nonce,'x-fare-signature':sig,'content-type':'application/json',...headers},body:method==='GET'?undefined:body});
}
