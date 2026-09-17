# Contributing

Changes must preserve GC/PG ID uniqueness and may not weaken Gate acceptance rules to make tests pass.

For a local clone, install the repository-managed pre-push hook once:

```bash
npm run hooks:install
```

Every push must pass `npm run check:prepush`, which requires a clean worktree, rejects bare executable/config `PLACEHOLDER` sentinels, and runs TypeScript, pinned Wrangler dry-run, the full pytest suite, schema invariants, and `git diff --check`.

Runtime/provider evidence is local/private state and must not be committed under `evidence/`.
