# Runbook

## 1. Local acceptance

Use the repository-managed toolchain and pre-push contract before any shared mutation:

```bash
npm ci --ignore-scripts
npm run hooks:install
npm run check:prepush
```

`check:prepush` requires a clean worktree, rejects bare executable/config `PLACEHOLDER` sentinels, and runs TypeScript, pinned Wrangler dry-run, the complete pytest suite, schema invariants, and `git diff --check`.

Local green tests are never Production PASS.

## 2. Reproducible Gate evidence

The canonical one-shot command is:

```bash
npm run gates:all
```

It parses all 37 PG commands and thresholds from `docs/SPEC_v1.3.md`, runs five PG stages plus five full-suite stages, and finalizes `gate-evidence-latest.json` for the exact Git HEAD, spec hash, dependency-lock hash, and test-corpus hash.

By default evidence is written below `evidence/`. To isolate evidence, set `FARE_EVIDENCE_ROOT` to an absolute path. Relative paths fail closed.

The required GitHub `test` workflow also runs `gates:all` and uploads `gate-evidence-<commit>` as an artifact. CI evidence does not replace provider evidence or Shadow acceptance.

## 3. GitHub protection and readback

The repository must be public, default branch `main`, exact expected HEAD, exact-head CI successful, and protected with:
- required `test` status context;
- strict status checks;
- admin enforcement;
- force-push disabled;
- branch deletion disabled.

Read-only verification:

```bash
npm run readback:github
```

One-time bounded protection bootstrap:

```bash
npm run protect:github
```

`protect:github` requires an Administration-write GitHub token. Missing admin permission is a hard provider Gate. If protection is absent it creates a safe minimum baseline once; if protection already exists it only strengthens scoped status/admin subresources and does not overwrite unrelated pull-request review or restriction rules. Unknown mutation outcomes are reconciled by same-source readback before any retry.

## 4. Shadow release provisioning

Before Worker deployment, create or reuse the canonical D1 database and prepare an exact release commit:

```bash
npm run provision:shadow
```

Required provider target variables include `FARE_GITHUB_REPOSITORY`, `FARE_PROVISION_EXPECTED_HEAD`, GitHub write credentials, `CLOUDFLARE_ACCOUNT_ID`, and `CLOUDFLARE_API_TOKEN`.

The provisioner:
1. verifies the clean exact local HEAD and current exact-head GitHub CI;
2. runs local pre-push acceptance before provider mutation;
3. creates or reuses exactly one `fare-radar-production` D1 database;
4. verifies migration history is a valid prefix, rejects destructive same-release migrations, captures a D1 Time Travel bookmark, writes the before/pending recovery manifest, then applies missing migrations once and reconciles the provider migration table by readback;
5. applies baseline source/provider seeds with readback;
6. replaces the public-repo D1 placeholder only in the release commit;
7. regenerates exact-head Gate evidence;
8. pushes a bounded `shadow-release-<head>` branch and waits for exact-head CI.

The public baseline may keep `REPLACE_WITH_D1_DATABASE_ID`; the release commit is the authoritative bridge to the real D1 identity.

### D1 recovery boundary

A Production migration must be expand-only. The provisioning path fails closed on `DROP TABLE`, `DROP COLUMN`, and table/column rename operations. Destructive cleanup belongs to a separate post-cutover release after the old Worker no longer depends on the old schema.

Before a pending migration is dispatched, the provisioner reads the current D1 Time Travel bookmark and writes `d1-migration-recovery.json` with the target database, before-state, pending list, and bookmark. If the migration command response is lost, it reads `d1_migrations` and provider state before deciding whether the migration applied; it never blindly reapplies an uncertain migration.

Worker rollback never restores D1. Emergency D1 restore is a separate human-reserved operation. Read-only planning is the default:

```bash
npm run d1:restore -- --bookmark <BOOKMARK>
```

Execution additionally requires `--execute` and an exact `FARE_D1_RESTORE_HUMAN_APPROVED_BOOKMARK` matching the requested bookmark. The tool re-reads the target D1 identity and current bookmark before dispatch. Automation must not create or infer this approval.

## 5. Shadow Worker deployment

```bash
npm run deploy:shadow
```

The driver requires a clean exact `FARE_SHADOW_EXPECTED_HEAD`, current exact-head local Gate evidence, non-placeholder D1 binding, Cloudflare credentials, Worker token, and separate Shadow/Access reviewer credentials.

Deployment behavior is state-dependent:

- **No Worker exists:** one pinned `wrangler@4.131.2 deploy` performs the initial bootstrap.
- **A valid Shadow Worker exists:** upload a new Worker Version without traffic, expose a deterministic preview alias, run all live credential probes against the preview, then activate that exact version at 100%.
- **Existing Production or partial/ambiguous Worker state:** fail closed; Shadow deployment will not overwrite it.

A failed or lost version/deployment response is never blindly resent. Same-source readback classifies applied, not-applied, or ambiguous state. If activation or post-deploy validation fails, the driver restores the exact previous Shadow Worker version and re-runs Shadow readback/live probes.

## 6. Human access review

Source/provider access and terms/privacy decisions remain human-authored evidence. Automation must not invent or approve them.

Dry-run and submit the identical private JSONL:

```bash
npm run access:review -- --input /private/access-reviews.jsonl --dry-run
npm run access:review -- --input /private/access-reviews.jsonl
```

Every audit/review mutation is pre-readback fenced, bounded to one write, and post-readback verified. A lost response is reconciled before any subsequent attempt.

## 7. Cloudflare full same-session readback

After Shadow bootstrap and required human access reviews:

```bash
npm run readback:cloudflare
npm run probe:live
```

A valid full readback must prove one same-source session across account identity, D1 identity/binding, Worker settings, active deployment, secrets, cron schedules, migrations, baseline seeds, and dispatchable source/provider human-review evidence.

The Worker must have:
- exactly one active version at 100%;
- exact `FARE_COMMIT_SHA`;
- deployment mode `SHADOW_ACCEPTANCE` or `PRODUCTION` as expected;
- the exact D1 binding;
- exactly one `* * * * *` cron;
- required `WORKER_TOKEN` and `INGEST_HMAC_SECRETS`;
- legacy ingest auth disabled and legacy secret absent;
- workers.dev origin enabled.

Evidence from different readback sessions cannot be spliced into a Production PASS.

## 8. Shadow review and 14-day acceptance

Submit human-authored Shadow labels with:

```bash
npm run shadow:review -- --input /private/shadow-reviews.jsonl --dry-run
npm run shadow:review -- --input /private/shadow-reviews.jsonl
```

The client requires exact runtime identity and uses readback-first mutation safety. After submission it persists the canonical `/shadow/acceptance/readback` schema.

Production preflight requires, for the exact commit:
- at least 14 distinct Shadow runtime days;
- at least 150 labeled itinerary candidates;
- at least 30 complex candidates;
- at least 30 source-discovery events;
- at least 10 agency-clearance events;
- complex strategy coverage for S09, S11, S12, S14, and S15;
- zero false-actionable complex cases;
- zero safety-critical errors.

## 9. Read-only deployment planning and preflight

```bash
npm run preflight
npm run deploy:plan
```

`deploy:plan` never performs provider mutation. It reports current blockers and the ordered shared-mutation sequence.

`production_ready=true` is impossible until exact-head GitHub/provider evidence, real D1 identity, Cloudflare same-session readback, human access reviews, and exact-head Shadow acceptance all pass.

## 10. Human-gated Production activation

Production activation cannot create its own approval. The human-approved exact commit must already be supplied as `FARE_PRODUCTION_HUMAN_APPROVED_HEAD`, equal the clean local HEAD, and `npm run preflight` must report exactly one blocker: `PRODUCTION_ACTIVATION_REQUIRED`.

Then:

```bash
npm run deploy:production
```

Production uses a preview-first Worker Version flow:
1. require the exact same HEAD still active in `SHADOW_ACCEPTANCE`;
2. upload a `PRODUCTION` candidate Worker Version with zero traffic;
3. run all live credential probes against its preview alias;
4. activate only that exact candidate at 100%;
5. perform full provider readback and live probes again;
6. replace provider evidence only after exact Production validation succeeds.

If activation or post-deploy validation fails, the driver restores the exact previous Shadow Worker version and validates the restored Shadow runtime. The rollback boundary is **Worker Version only**: D1 state is not rolled back by Worker-version rollback.

## 11. Live offer expiry lifecycle

The five-minute cron re-evaluates exact LIVE offers supporting current `CONFIRMED` results. When support expires it first rotates to redundant fresh evidence if possible; otherwise it downgrades to `PROBABLE`, marks fare verification stale, cancels/suppresses unsent DEAL notifications, emits `DEAL-UPDATE` for already-visible deals, and schedules bounded repricing.

The normal five-minute path must remain under the internal 40-query target and below the hard 50-query budget.
