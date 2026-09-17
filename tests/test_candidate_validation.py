import copy, subprocess, json, pathlib
from tests.fixtures import plan
ROOT=pathlib.Path(__file__).resolve().parents[1]

def test_valid_plan(run_cli): assert run_cli("validate-plan",plan()) is True

def test_missing_readiness_blocked(run_cli):
    p=plan(); p["readiness"].pop()
    proc=subprocess.run(["node","dist/cli.js","validate-plan",json.dumps(p)],cwd=ROOT,text=True,capture_output=True)
    assert proc.returncode != 0 and "READINESS_INCOMPLETE" in proc.stderr

def test_unknown_transfer_ticket_blocked():
    p=plan(); p["transfers"][0]["to_ticket_id"]="missing"
    proc=subprocess.run(["node","dist/cli.js","validate-plan",json.dumps(p)],cwd=ROOT,text=True,capture_output=True)
    assert proc.returncode != 0 and "TRANSFER_TICKET_UNKNOWN" in proc.stderr

def test_duplicate_cost_key_blocked():
    p=plan(); d=copy.deepcopy(p["costs"][0]); d["cost_id"]="c3"; p["costs"].append(d)
    proc=subprocess.run(["node","dist/cli.js","validate-plan",json.dumps(p)],cwd=ROOT,text=True,capture_output=True)
    assert proc.returncode != 0 and "COST_DEDUPE_DUPLICATE" in proc.stderr

def test_scenario_order_blocked():
    p=plan(); p["itinerary"]["scenario_cost_twd"]={"low":9000,"base":8000,"high":7000}
    proc=subprocess.run(["node","dist/cli.js","validate-plan",json.dumps(p)],cwd=ROOT,text=True,capture_output=True)
    assert proc.returncode != 0 and "SCENARIO_COST_ORDER_INVALID" in proc.stderr
