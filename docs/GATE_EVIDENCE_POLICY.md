# Gate Evidence Policy

Fare Radar 嚴格區分兩種結果：

- `LOCAL_TEST_PASS`：指定 commit 的 deterministic implementation test 通過。
- `Production Gate PASS`：除測試外，Gate Evidence Contract 要求的部署、provider same-source readback、terms/access snapshot、rollback/degrade rehearsal、Shadow 或人工驗收亦完整。

本機 commit 不是 durable remote checkpoint。沒有 public GitHub repo、remote CI、Cloudflare/D1 readback、實際 provider evidence 或必要 Shadow 時間窗時，禁止把任何本機測試結果包裝成 `PRODUCTION_READY`。

`tools/generate_gate_evidence.py` 直接解析 `docs/SPEC_v1.3.md` 的 PG00–PG36 mapping，驗證每個 exact test target 存在，逐一執行每個 Gate 的 exact test command，各自保存 stdout/stderr、report hash、時間、commit SHA、dependency hash 與未解條件；最後再額外執行一次完整 deterministic suite 作交叉驗收。禁止用單一次 full-suite PASS 冒充 37 個 exact command 都已執行。

任何 Gate 測試 mapping 增刪造成 PG00–PG36 不連續時，generator 必須 fail closed。
