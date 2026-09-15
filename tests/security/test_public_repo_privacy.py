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
