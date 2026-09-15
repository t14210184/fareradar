# Security

The public repository contains only synthetic profiles/fixtures and public source seeds. Real chat/group IDs, private notification bodies, traveler preferences, credentials, HMAC secrets, cookies, and OAuth refresh tokens are prohibited from Git history.

## Ingest authentication

Production ingest does not rely on one shared bearer token.

- External heavy workers authenticate `/lease` with `WORKER_TOKEN`; `/ingest` is accepted only while the same worker owns a live lease whose source matches the observation.
- Agency and Email push intake use scoped HMAC keys registered in `ingest_auth_keys`. D1 stores key metadata and `secret_slot` only; plaintext secrets live in the Cloudflare secret `INGEST_HMAC_SECRETS`.
- Signed requests include key ID, timestamp, nonce, method, path, and SHA-256 of the exact request body. Nonces are persisted to reject replay.
- `ALLOW_LEGACY_INGEST_TOKEN=1` exists only for local migration tests. Deployment preflight treats it as a Production blocker.

Key rotation creates a new key ID/secret slot, changes the sender, then disables the old key after the overlap window. Do not reuse nonces across retries; retries must be re-signed with a new nonce.
