export interface PolicyRecord { observed_at:string; effective_from?:string|null; effective_to?:string|null; ttl_hours:number; watch_window_hours?:number; status?:string; }
export function policyUsable(p:PolicyRecord,eventAt:string,nowIso:string){
  if(p.status==="RECHECK_REQUIRED"||p.status==="STALE") return false;
  const event=Date.parse(eventAt), now=Date.parse(nowIso), observed=Date.parse(p.observed_at);
  if(![event,now,observed].every(Number.isFinite)) return false;
  if(p.effective_from && event<Date.parse(p.effective_from)) return false;
  if(p.effective_to && event>=Date.parse(p.effective_to)) return false;
  if(now-observed>p.ttl_hours*3600000) return false;
  if(p.watch_window_hours && event-now <= p.watch_window_hours*3600000 && now-observed > Math.min(p.ttl_hours,p.watch_window_hours)*3600000) return false;
  return true;
}
