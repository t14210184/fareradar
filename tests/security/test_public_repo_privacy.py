import pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_no_obvious_secret_material_in_tracked_text():
    bad=[]; patterns=[re.compile(r'(?i)(api[_-]?token|secret|password)\s*[:=]\s*[A-Za-z0-9_\-]{20,}')]
    for p in ROOT.rglob('*'):
        if not p.is_file() or '.git' in p.parts or 'dist' in p.parts or p.suffix in {'.bundle'}: continue
        try:s=p.read_text(errors='ignore')
        except:continue
        if any(x.search(s) for x in patterns): bad.append(str(p))
    assert bad==[]


def test_public_profile_example_is_synthetic_only():
    import json
    rows=json.loads((ROOT/'config'/'profiles.example.json').read_text())
    assert rows and all(str(r.get('profile_id','')).startswith('synthetic_') for r in rows)
    assert all(str(r.get('home_city','')).lower().startswith('example') for r in rows)
