from __future__ import annotations
import ast,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_gate_finalize_uses_file_backed_full_suite_output_not_capture_pipe():
    src=(ROOT/'scripts/gate_evidence.py').read_text()
    tree=ast.parse(src)
    finalize=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='finalize')
    text=ast.get_source_segment(src,finalize) or ''
    assert 'tempfile.NamedTemporaryFile' in text
    assert "prefix='fare-gate-full-'" in text
    assert 'report_path.unlink(missing_ok=True)' in text
    assert 'stdout=report' in text and 'stderr=subprocess.STDOUT' in text
    assert 'timeout=180' in text
    assert 'capture_output=True' not in text
