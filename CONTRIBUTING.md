# Contributing

Changes must preserve GC/PG ID uniqueness and may not weaken Gate acceptance rules to make tests pass.

For a local clone, install the repository-managed pre-push hook once:

```bash
npm run hooks:install
```

Every push must first pass `npm run check:prepush`, which requires a clean worktree, rejects bare executable/config `PLACEHOLDER` sentinels, and runs TypeScript, pinned Wrangler dry-run, the full pytest suite, schema invariants, and `git diff --check`.

Before treating a commit as release-ready, run:

```bash
npm run gates:all
```

GitHub CI independently re-runs the same exact-head Gate evidence pipeline. Do not weaken, skip, or replace a failing Gate to obtain green CI.

Runtime/provider evidence is local/private state and must not be committed under `evidence/`. Shared GitHub or Cloudflare mutations must use bounded drivers and same-source readback; never substitute manually edited evidence for provider truth.
