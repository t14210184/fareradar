from tests.fixtures import plan

def test_actionable_requires_all_fresh_pass(run_cli):
    p=plan(); got=run_cli("actionable",{"verification_state":"CONFIRMED","facets":p["readiness"],"at":"2026-09-15T00:30:00Z"}); assert got is True

def test_probable_never_actionable(run_cli):
    p=plan(); got=run_cli("actionable",{"verification_state":"PROBABLE","facets":p["readiness"],"at":"2026-09-15T00:30:00Z"}); assert got is False

def test_stale_facet_blocks_actionable(run_cli):
    p=plan(); p["readiness"][0]["expires_at"]="2026-09-14T00:00:00Z"; assert run_cli("actionable",{"verification_state":"CONFIRMED","facets":p["readiness"],"at":"2026-09-15T00:30:00Z"}) is False

def test_cost_dedupe_and_unknown(run_cli):
    p=plan(); comps=p["costs"]+[dict(p["costs"][1])]; got=run_cli("cash",{"offer_total_twd":5000,"components":comps}); assert got=={"cash_trip_cost_twd":5900,"cost_complete":True}
    p["costs"][1]["inclusion_state"]="UNKNOWN"; got=run_cli("cash",{"offer_total_twd":5000,"components":p["costs"]}); assert got["cost_complete"] is False
