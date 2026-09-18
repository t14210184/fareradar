from __future__ import annotations

import json
import os
import pathlib
import stat
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import cloudflare_provider as cf
import runtime_credentials as mod

DB = "11111111-2222-3333-4444-555555555555"


def env():
    shadow_secret = "shadow-secret-0123456789"
    access_secret = "access-secret-0123456789"
    return {
        "FARE_WORKER_TOKEN": "worker-token-0123456789",
        "FARE_INGEST_HMAC_SECRETS": json.dumps({
            "shadow-slot": shadow_secret,
            "access-slot": access_secret,
            "source-slot": "source-secret-0123456789",
        }),
        "FARE_SHADOW_REVIEWER_KEY_ID": "shadow-key",
        "FARE_SHADOW_REVIEWER_SECRET_SLOT": "shadow-slot",
        "FARE_SHADOW_REVIEWER_SECRET": shadow_secret,
        "FARE_ACCESS_REVIEWER_KEY_ID": "access-key",
        "FARE_ACCESS_REVIEWER_SECRET_SLOT": "access-slot",
        "FARE_ACCESS_REVIEWER_SECRET": access_secret,
    }


def envelope(rows):
    return cf.Response(200, {
        "success": True,
        "errors": [],
        "messages": [],
        "result": [{"success": True, "results": rows}],
    })


class Api:
    def __init__(self, *, unknown_after_insert=False):
        self.rows = {}
        self.insert_calls = 0
        self.unknown_after_insert = unknown_after_insert

    def post(self, path, payload):
        assert path == f"/d1/database/{DB}/query"
        sql = payload["sql"]
        if sql.startswith("SELECT "):
            key = sql.split("WHERE key_id=", 1)[1].strip().strip("'").replace("''", "'")
            row = self.rows.get(key)
            return envelope([] if row is None else [row])
        if sql.startswith("INSERT INTO ingest_auth_keys"):
            self.insert_calls += 1
            values = sql.split("VALUES(", 1)[1][:-1]
            parts = []
            current = ""
            quoted = False
            index = 0
            while index < len(values):
                char = values[index]
                if char == "'":
                    if quoted and index + 1 < len(values) and values[index + 1] == "'":
                        current += "'"
                        index += 2
                        continue
                    quoted = not quoted
                    index += 1
                    continue
                if char == "," and not quoted:
                    parts.append(current)
                    current = ""
                else:
                    current += char
                index += 1
            parts.append(current)
            def value(item):
                return None if item == "NULL" else item
            row = {
                "key_id": value(parts[0]),
                "role": value(parts[1]),
                "source_id": value(parts[2]),
                "agency_id": value(parts[3]),
                "provider_id": value(parts[4]),
                "secret_slot": value(parts[5]),
                "allowed_paths_json": value(parts[6]),
                "enabled": int(parts[7]),
                "not_before": value(parts[8]),
                "expires_at": value(parts[9]),
            }
            self.rows[row["key_id"]] = row
            if self.unknown_after_insert:
                raise cf.CloudflareProviderError("CLOUDFLARE_TRANSPORT_UNKNOWN")
            return envelope([])
        raise AssertionError(sql)


def test_load_config_requires_full_secret_map_and_distinct_reviewers():
    config = mod.load_config(env())
    assert config.hmac_secrets["source-slot"] == "source-secret-0123456789"
    assert config.shadow.secret_slot == "shadow-slot"
    assert config.access.secret_slot == "access-slot"

    broken = env()
    broken["FARE_INGEST_HMAC_SECRETS"] = json.dumps({"shadow-slot": broken["FARE_SHADOW_REVIEWER_SECRET"]})
    with pytest.raises(mod.RuntimeCredentialError, match="ACCESS_REVIEWER_SECRET_SLOT_MISMATCH"):
        mod.load_config(broken)

    broken = env()
    broken["FARE_ACCESS_REVIEWER_SECRET_SLOT"] = "shadow-slot"
    with pytest.raises(mod.RuntimeCredentialError, match="REVIEWER_SECRET_SLOTS_MUST_DIFFER"):
        mod.load_config(broken)


def test_reviewer_auth_keys_create_once_then_readback_exact():
    config = mod.load_config(env())
    api = Api()
    first = mod.ensure_reviewer_auth_keys(api, DB, config)
    assert first == {"shadow-key": "EXACT_CREATED", "access-key": "EXACT_CREATED"}
    assert api.insert_calls == 2
    second = mod.ensure_reviewer_auth_keys(api, DB, config)
    assert second == {"shadow-key": "EXACT_EXISTING", "access-key": "EXACT_EXISTING"}
    assert api.insert_calls == 2
    assert json.loads(api.rows["shadow-key"]["allowed_paths_json"]) == mod.SHADOW_PATHS
    assert json.loads(api.rows["access-key"]["allowed_paths_json"]) == mod.ACCESS_PATHS


def test_unknown_insert_is_reconciled_without_resend():
    config = mod.load_config(env())
    api = Api(unknown_after_insert=True)
    result = mod.ensure_reviewer_auth_keys(api, DB, config)
    assert result == {"shadow-key": "EXACT_AFTER_UNKNOWN", "access-key": "EXACT_AFTER_UNKNOWN"}
    assert api.insert_calls == 2


def test_existing_reviewer_metadata_conflict_fails_without_mutation():
    config = mod.load_config(env())
    api = Api()
    mod.ensure_reviewer_auth_keys(api, DB, config)
    api.rows["shadow-key"]["role"] = "TEST"
    before = api.insert_calls
    with pytest.raises(mod.RuntimeCredentialError, match="REVIEWER_AUTH_KEY_CONFLICT:shadow-key"):
        mod.ensure_reviewer_auth_keys(api, DB, config)
    assert api.insert_calls == before


def test_secret_file_is_private_complete_and_deleted():
    config = mod.load_config(env())
    with mod.secret_file(config) as path:
        assert path.exists()
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600
        data = json.loads(path.read_text())
        assert data["WORKER_TOKEN"] == config.worker_token
        assert json.loads(data["INGEST_HMAC_SECRETS"]) == config.hmac_secrets
        assert "shadow-secret" not in path.name
    assert not path.exists()
