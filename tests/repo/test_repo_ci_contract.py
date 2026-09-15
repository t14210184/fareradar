import pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_ci_contract_present():
    assert (ROOT/'.github/workflows/ci.yml').exists()
    assert (ROOT/'package.json').exists()
