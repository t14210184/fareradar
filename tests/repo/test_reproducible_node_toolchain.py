import json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_typescript_is_pinned_and_ci_uses_npm_ci():
    pkg=json.loads((ROOT/'package.json').read_text()); lock=json.loads((ROOT/'package-lock.json').read_text()); ci=(ROOT/'.github/workflows/ci.yml').read_text()
    assert pkg['devDependencies']['typescript']=='5.8.3'
    assert lock['lockfileVersion']==3 and lock['packages']['node_modules/typescript']['version']=='5.8.3'
    assert lock['packages']['node_modules/typescript']['integrity'].startswith('sha512-')
    assert 'npm ci --ignore-scripts' in ci and ci.index('npm ci --ignore-scripts') < ci.index('npm run check:ts')
