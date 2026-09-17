# Construction Decisions

## ADR-001 — Source pull entrypoint

v1.3 的 `SourceRegistry` 有 `canonical_domain_or_account`，但實作 pull adapter 需要精確 URL，不能從 domain 猜 promotion path。

施工採 additive 欄位 `entrypoint_url`：

- `RSS / SITEMAP / CONDITIONAL_HTTP / STATIC_HTML_DIFF / BROWSER` 必須為 HTTPS URL。
- `API / WEBHOOK / EMAIL / FORWARD / OCR` 可為 `null`，endpoint 由 provider/channel adapter config 管理。
- `canonical_domain_or_account` 仍負責來源 identity；`entrypoint_url` 只負責 fetch routing，不改 Source authority。

此決策不改 Mission、策略集合或 Gate 門檻，屬資料模型落地必要補充。


## ADR-002 — Private bounded provider search campaigns

背景 provider 查價不得從促銷 route 自行暴力展開日期。Production runtime 只接受存放於私有 D1 的 `SearchCampaign`：

- departure dates 必須明確列舉，最多 32 日；
- trip lengths 最多 8 種；
- 單一 candidate signal 最多產生 8 個 exact provider queries；
- promotion travel window 只負責過濾明確日期，不會生成新的日期；
- Campaign 值不寫入 public repo，repo 只保存 schema／synthetic fixtures；
- provider terms／background permission 未通過時，plan 可保存但 dispatch fail-closed。

Provider planner 使用獨立低頻控制路徑，避免擠壓每分鐘 P0 ingest／alert／source dispatcher 的 D1 預算。
