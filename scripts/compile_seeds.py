from __future__ import annotations
import json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def q(v):
    if v is None:return 'NULL'
    if isinstance(v,bool):return '1' if v else '0'
    if isinstance(v,(int,float)):return str(v)
    return "'"+str(v).replace("'","''")+"'"
def main():
    out=['BEGIN;']
    for r in json.loads((ROOT/'config/sources.seed.json').read_text()):
        cols=['source_id','source_class','canonical_domain_or_account','entrypoint_url','access_basis','fetch_method','lifecycle_state','verification_authority','terms_snapshot_at','min_interval_ms','kill_switch','market','language','currency','storage_policy','retention_policy','parser','owner','owner_type','route_scope','push_capable','discovery_trust','lead_score','yield_score','fare_freshness','requires_repricing','privacy_class','max_burst','backoff_policy','kill_switch_state','last_success_at','last_unique_deal_at','status']
        vals=[r.get(c) for c in cols]
        out.append(f"INSERT INTO source_registry({','.join(cols)}) VALUES({','.join(q(v) for v in vals)}) ON CONFLICT(source_id) DO UPDATE SET lifecycle_state=excluded.lifecycle_state,terms_snapshot_at=excluded.terms_snapshot_at,min_interval_ms=excluded.min_interval_ms,kill_switch=excluded.kill_switch;")
    for r in json.loads((ROOT/'config/providers.seed.json').read_text()):
        rr=dict(r); rr['supported_verification_json']=json.dumps(r.get('supported_verification',[]),separators=(',',':'))
        cols=['provider_id','access_basis','terms_snapshot_at','rate_policy','look_to_book_budget','kill_switch_state','owner','connector_state','supported_verification_json','credential_binding','background_allowed']; vals=[rr.get(c) for c in cols]
        out.append(f"INSERT INTO provider_access_registry({','.join(cols)}) VALUES({','.join(q(v) for v in vals)}) ON CONFLICT(provider_id) DO UPDATE SET terms_snapshot_at=excluded.terms_snapshot_at,rate_policy=excluded.rate_policy,kill_switch_state=excluded.kill_switch_state,connector_state=excluded.connector_state,supported_verification_json=excluded.supported_verification_json,credential_binding=excluded.credential_binding,background_allowed=excluded.background_allowed;")
    out.append('COMMIT;')
    p=ROOT/'generated/seed.generated.sql'; p.write_text('\n'.join(out)+'\n'); print(p)
if __name__=='__main__':main()
