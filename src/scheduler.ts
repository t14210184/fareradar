import type { D1Database } from "./types.js";
import { adaptiveSchedule } from "./source.js";

function day(iso:string){return iso.slice(0,10)}
function bucket(ms:number,interval:number){return Math.floor(ms/interval)}
function dueInterval(base:number,action:string){if(action==="BOOST")return Math.max(60000,Math.floor(base/2));if(action==="DOWNSHIFT")return Math.max(base,base*4);return base}
function termsCurrent(v:string|null|undefined){return !!v && v!=="RECHECK_REQUIRED" && Number.isFinite(Date.parse(v))}

export async function scheduleDueSources(db:D1Database,nowIso:string,limit=10){
  const now=Date.parse(nowIso);
  const rows=(await db.prepare(`SELECT s.source_id,s.entrypoint_url,s.fetch_method,s.min_interval_ms,s.lifecycle_state,s.terms_snapshot_at,
    f.last_attempt_at,COALESCE(h.schedule_action,'KEEP') schedule_action
    FROM source_registry s LEFT JOIN source_fetch_state f ON f.source_id=s.source_id
    LEFT JOIN source_health_windows h ON h.source_id=s.source_id AND h.window_date=?
    WHERE s.lifecycle_state IN ('ENABLED','SHADOW') AND s.kill_switch=0 AND s.entrypoint_url IS NOT NULL
    ORDER BY COALESCE(f.last_attempt_at,'') ASC LIMIT ?`).bind(day(nowIso),limit).all<any>()).results;
  let inserted=0;
  for(const r of rows){
    if(!termsCurrent(r.terms_snapshot_at)||r.schedule_action==="QUARANTINE")continue;
    const interval=dueInterval(Number(r.min_interval_ms)||300000,String(r.schedule_action));
    if(r.last_attempt_at && now-Date.parse(r.last_attempt_at)<interval)continue;
    const jobId=`source:${r.source_id}:${bucket(now,interval)}`;
    const payload={source_id:r.source_id,url:r.entrypoint_url,fetch_method:r.fetch_method};
    const res=await db.prepare("INSERT OR IGNORE INTO verification_jobs(job_id,job_type,target_class,source_id,payload_json,state,available_at,created_at) VALUES(?, 'SOURCE_FETCH','EXTERNAL_HEAVY',?,?,'PENDING',?,?)")
      .bind(jobId,r.source_id,JSON.stringify(payload),nowIso,nowIso).run();
    await db.prepare("INSERT INTO source_fetch_state(source_id,last_attempt_at,consecutive_failures,updated_at) VALUES(?,?,0,?) ON CONFLICT(source_id) DO UPDATE SET last_attempt_at=excluded.last_attempt_at,updated_at=excluded.updated_at")
      .bind(r.source_id,nowIso,nowIso).run();
    inserted += Number((res.meta as any)?.changes??1)>0?1:0;
  }
  return {considered:rows.length,inserted};
}

export async function completeSourceFetch(db:D1Database,input:{source_id:string;success:boolean;duplicate?:boolean;schema_drift?:boolean;etag?:string|null;last_modified?:string|null;content_sha256?:string|null},nowIso:string){
  const d=day(nowIso);
  const current=await db.prepare("SELECT fetch_count,success_count,duplicate_count,confirmed_count,first_win_count,ghost_count,schema_drift_count FROM source_health_windows WHERE source_id=? AND window_date=?").bind(input.source_id,d).first<any>();
  const x={fetch_count:(current?.fetch_count??0)+1,success_count:(current?.success_count??0)+(input.success?1:0),duplicate_count:(current?.duplicate_count??0)+(input.duplicate?1:0),confirmed_count:current?.confirmed_count??0,first_win_count:current?.first_win_count??0,ghost_count:current?.ghost_count??0,schema_drift_count:(current?.schema_drift_count??0)+(input.schema_drift?1:0)};
  let action="KEEP"; if(x.fetch_count<5){if(!input.success||input.schema_drift)action="DOWNSHIFT";}else action=adaptiveSchedule({confirmed_rate:x.confirmed_count/x.fetch_count,first_win_rate:x.first_win_count/x.fetch_count,duplicate_rate:x.duplicate_count/x.fetch_count,ghost_rate:x.ghost_count/x.fetch_count,schema_drift_rate:x.schema_drift_count/x.fetch_count});
  await db.batch([
    db.prepare("INSERT INTO source_health_windows(source_id,window_date,fetch_count,success_count,duplicate_count,confirmed_count,first_win_count,ghost_count,schema_drift_count,schedule_action,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id,window_date) DO UPDATE SET fetch_count=excluded.fetch_count,success_count=excluded.success_count,duplicate_count=excluded.duplicate_count,confirmed_count=excluded.confirmed_count,first_win_count=excluded.first_win_count,ghost_count=excluded.ghost_count,schema_drift_count=excluded.schema_drift_count,schedule_action=excluded.schedule_action,updated_at=excluded.updated_at")
      .bind(input.source_id,d,x.fetch_count,x.success_count,x.duplicate_count,x.confirmed_count,x.first_win_count,x.ghost_count,x.schema_drift_count,action,nowIso),
    db.prepare("INSERT INTO source_fetch_state(source_id,last_attempt_at,last_success_at,etag,last_modified,content_sha256,consecutive_failures,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET last_attempt_at=excluded.last_attempt_at,last_success_at=CASE WHEN ? THEN excluded.last_success_at ELSE source_fetch_state.last_success_at END,etag=COALESCE(excluded.etag,source_fetch_state.etag),last_modified=COALESCE(excluded.last_modified,source_fetch_state.last_modified),content_sha256=COALESCE(excluded.content_sha256,source_fetch_state.content_sha256),consecutive_failures=CASE WHEN ? THEN 0 ELSE source_fetch_state.consecutive_failures+1 END,updated_at=excluded.updated_at")
      .bind(input.source_id,nowIso,input.success?nowIso:null,input.etag??null,input.last_modified??null,input.content_sha256??null,input.success?0:1,nowIso,input.success?1:0,input.success?1:0)
  ]);
  return {action,...x};
}

export async function leaseVerificationJobs(db:D1Database,nowIso:string,workerId:string,limit=5,leaseSeconds=90){
  await db.prepare("UPDATE verification_jobs SET state='PENDING',claimed_by=NULL,lease_until=NULL WHERE state='LEASED' AND lease_until IS NOT NULL AND lease_until<=?").bind(nowIso).run();
  const until=new Date(Date.parse(nowIso)+leaseSeconds*1000).toISOString();
  return (await db.prepare(`UPDATE verification_jobs SET state='LEASED',claimed_by=?,lease_until=?,attempts=attempts+1 WHERE job_id IN (SELECT job_id FROM verification_jobs WHERE state='PENDING' AND available_at<=? ORDER BY created_at LIMIT ?) AND state='PENDING' RETURNING job_id,job_type,source_id,payload_json,attempts,lease_until`).bind(workerId,until,nowIso,limit).all()).results;
}
