# Security

The public repository contains only synthetic profiles/fixtures and public source seeds. Real chat/group IDs, private notification bodies, traveler preferences, credentials, HMAC secrets, cookies, and OAuth refresh tokens are prohibited from Git history.

## Ingest authentication

Production ingest does not rely on one shared bearer token.

- External heavy workers authenticate `/lease` with `WORKER_TOKEN`; `/ingest` is accepted only while the same worker owns a live lease whose source matches the observation.
- Agency and Email push intake use scoped HMAC keys registered in `ingest_auth_keys`. D1 stores key metadata and `secret_slot` only; plaintext secrets live in the Cloudflare secret `INGEST_HMAC_SECRETS`.
- Signed requests include key ID, timestamp, nonce, method, path, and SHA-256 of the exact request body. Nonces are persisted to reject replay.
- `ALLOW_LEGACY_INGEST_TOKEN=1` exists only for local migration tests. Deployment preflight treats it as a Production blocker.

Key rotation creates a new key ID/secret slot, changes the sender, then disables the old key after the overlap window. Do not reuse nonces across retries; retries must be re-signed with a new nonce.


## Cloudflare credential separation

V1.4 separates provider credentials by purpose. Secret token values are never stored in repository evidence.

- **Bootstrap credential:** temporary elevated credential for first-time resource creation only. After `fare-radar` Worker and `fare-radar-production` D1 exist, Production preflight requires bootstrap to be inactive/revoked.
- **Steady-state Worker deploy credential:** account-owned API token, scope `INDIVIDUAL_WORKER`, resource `fare-radar`, role `EDITOR`. It may update/deploy the Worker but must not have delete capability.
- **D1 administration credential:** account-owned API token limited to D1 operations required by migration/readback/recovery. The evidence contract identifies `fare-radar-production` and requires an Editor/Read-Write role rather than unrelated product write access.

Credential evidence stores only provider identity, normalized role/scope, status, same-session readback ID, and SHA-256 fingerprint of the provider token ID. It must set `secret_material_present=false`; plaintext token values are prohibited.

Local environment variables cannot satisfy this Gate. Production preflight requires fresh provider-backed `cloudflare-credential-policy.json` in the same readback session as Cloudflare auth, D1, Worker deploy, and secret evidence.
