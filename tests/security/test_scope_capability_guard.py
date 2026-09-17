import json
import pathlib
import subprocess

ROOT=pathlib.Path(__file__).resolve().parents[2]


def test_entity_scoped_keys_cannot_escape_route_family_even_with_broad_allowlist():
    process=subprocess.run(['node','tests/node_scope_capability_guard.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    got=json.loads(process.stdout)
    assert got['source_allowed'] is True
    assert got['agency_allowed'] is True
    assert got['provider_allowed'] is True
    assert got['source_cross'] is False
    assert got['agency_cross'] is False
    assert got['provider_cross'] is False
    assert got['multi_scope'] is False
    assert got['internal_allowed'] is True
