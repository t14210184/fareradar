import importlib.util,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ge',ROOT/'scripts/gate_evidence.py'); ge=importlib.util.module_from_spec(spec); spec.loader.exec_module(ge)

def test_spec_is_single_source_for_all_37_gate_commands_and_thresholds():
    rows=ge.parse_gate_mapping()
    assert [r['gate_id'] for r in rows]==[f'PG{i:02d}' for i in range(37)]
    assert all(r['exact_command'].startswith('pytest -q tests/') for r in rows)
    assert all(r['expected_threshold'] for r in rows)

def test_evidence_context_binds_head_spec_dependencies_and_test_corpus():
    ctx=ge.context()
    assert len(ctx['commit_sha'])==40
    assert all(len(ctx[k])==64 for k in ['spec_sha256','dependency_lock_sha256','test_corpus_sha256'])
