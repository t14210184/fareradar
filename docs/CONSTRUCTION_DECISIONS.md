# Construction Decisions

## ADR-001 — Source pull entrypoint

v1.3 的 `SourceRegistry` 有 `canonical_domain_or_account`，但實作 pull adapter 需要精確 URL，不能從 domain 猜 promotion path。

施工採 additive 欄位 `entrypoint_url`：

- `RSS / SITEMAP / CONDITIONAL_HTTP / STATIC_HTML_DIFF / BROWSER` 必須為 HTTPS URL。
- `API / WEBHOOK / EMAIL / FORWARD / OCR` 可為 `null`，endpoint 由 provider/channel adapter config 管理。
- `canonical_domain_or_account` 仍負責來源 identity；`entrypoint_url` 只負責 fetch routing，不改 Source authority。

此決策不改 Mission、策略集合或 Gate 門檻，屬資料模型落地必要補充。
