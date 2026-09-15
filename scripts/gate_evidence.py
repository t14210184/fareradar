from __future__ import annotations
import hashlib,json,pathlib,subprocess,time,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence'; OUT.mkdir(exist_ok=True)
MAP={
'PG00':'pytest -q tests/repo/test_repo_ci_contract.py','PG01':'pytest -q tests/durability/','PG02':'pytest -q tests/sources/test_adapter_isolation.py','PG03':'pytest -q tests/golden/test_promo_constraints.py','PG04':'pytest -q tests/cost/test_all_in_cost.py','PG05':'pytest -q tests/strategy/test_basic_search.py','PG06':'pytest -q tests/transfer/test_self_transfer_risk.py','PG07':'pytest -q tests/policy/test_staleness.py','PG08':'pytest -q tests/foreign_origin/test_cycle_cost.py','PG09':'pytest -q tests/verification/test_multi_provider.py','PG10':'pytest -q tests/ticketing/test_coupon_sequence.py','PG11':'pytest -q tests/alerts/test_complex_card_schema.py','PG12':'pytest -q tests/capacity/test_d1_quota_degrade.py','PG13':'pytest -q tests/resilience/test_win11_offline.py','PG14':'pytest -q tests/security/test_public_repo_privacy.py','PG15':'pytest -q tests/shadow/test_acceptance.py','PG16':'pytest -q tests/shadow/test_complex_review.py','PG17':'pytest -q tests/cost/test_offer_component_dedup.py','PG18':'pytest -q tests/transfer/test_protection_classification.py','PG19':'pytest -q tests/capacity/test_worker_cpu_budget.py','PG20':'pytest -q tests/contracts/test_provider_access_basis.py','PG21':'pytest -q tests/contracts/test_amadeus_lcc_exclusion.py','PG22':'pytest -q tests/policy/test_policy_ttl_event_time.py','PG23':'pytest -q tests/capacity/test_d1_scan_budget.py','PG24':'pytest -q tests/golden/test_jetstar_price_beat.py','PG25':'pytest -q tests/sources/test_source_registry_contract.py','PG26':'pytest -q tests/sources/test_provenance_hash.py','PG27':'pytest -q tests/sources/test_promotion_cluster_dedup.py','PG28':'pytest -q tests/agency/test_clearance_intake.py','PG29':'pytest -q tests/email/test_auth_and_link_safety.py','PG30':'pytest -q tests/sources/test_social_retention_privacy.py','PG31':'pytest -q tests/sources/test_rate_terms_guard.py','PG32':'pytest -q tests/verification/test_event_to_offer_trace.py','PG33':'pytest -q tests/sources/test_correction_deletion.py','PG34':'pytest -q tests/capacity/test_source_burst_degrade.py','PG35':'pytest -q tests/source_discovery/test_route_universe.py','PG36':'pytest -q tests/sources/test_adaptive_schedule.py'}

def target_exists(cmd):
    target=cmd.split()[-1]
    return (ROOT/target.rstrip('/')).exists()

def run_one(item, head):
    import os
    gate,cmd=item; start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not target_exists(cmd):
        return {'gate_id':gate,'status':'EVIDENCE_INCOMPLETE','exact_command':cmd,'reason':'TEST_TARGET_MISSING','commit_sha':head,'start':start,'end':start}
    env=os.environ.copy(); env['FARE_SKIP_BUILD']='1'
    p=subprocess.run(cmd,shell=True,cwd=ROOT,text=True,capture_output=True,env=env); end=datetime.datetime.now(datetime.timezone.utc).isoformat(); blob=(p.stdout+p.stderr).encode()
    return {'gate_id':gate,'status':'LOCAL_TEST_PASS' if p.returncode==0 else 'LOCAL_TEST_FAIL','exact_command':cmd,'commit_sha':head,'start':start,'end':end,'returncode':p.returncode,'report_sha256':hashlib.sha256(blob).hexdigest(),'output_tail':(p.stdout+p.stderr)[-1200:]}

def main():
    from concurrent.futures import ThreadPoolExecutor
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    subprocess.run(['tsc','-p','tsconfig.json'],cwd=ROOT,check=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows=list(ex.map(lambda item: run_one(item,head), MAP.items()))
    doc={'spec_version':'1.3','commit_sha':head,'production_pass':0,'gates':rows,'summary':{s:sum(1 for r in rows if r['status']==s) for s in ['LOCAL_TEST_PASS','LOCAL_TEST_FAIL','EVIDENCE_INCOMPLETE']}}
    path=OUT/'gate-evidence-latest.json'; path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)); print(json.dumps(doc['summary']))
    if any(r['status']=='LOCAL_TEST_FAIL' for r in rows): raise SystemExit(1)
if __name__=='__main__':main()
