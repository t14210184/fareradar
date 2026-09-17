# 超值低價機票研究追蹤系統
## 生產級施工規格計劃書 v1.3

- 版本：1.3
- 研究／稽核重基準日：2026-09-14
- 狀態：**Construction Baseline / NOT_PRODUCTION_READY**
- 工作代稱：Fare Radar
- 前版：`超值低價機票研究追蹤系統_生產級施工規格計劃書_v1.2`
- 研究輸入：v1.2 + 兩份外部來源研究 + 2026-09-14 追加查核
- 本版定位：保留 v1.2 安全與成本基線，新增可自我擴張、可驗證、可合法降級的 Source Intelligence Mesh，作為正式施工基線。

---

# 0. v1.3 來源情報網重基準裁決

v1.3 不改變 v1.2 的產品 Mission、20 個 active strategy 或「完整旅程成本優先」原則；本版把施工基線從「有幾個來源 adapter」升級成可長期擴張、可治理、可驗證的 **Source Intelligence Mesh**。

本版輸入：

```text
v1.2 Construction Baseline
+ CO「必須納入的各種高品質有效相關特價低價資訊即時資源有效來源」
+「台日低價機票_施工必須納入即時資源有效來源清單_v1.0」
+ 2026-09-14 追加網路查核與來源衝突裁決
```

v1.2 已完成的核心安全基線全部保留：

1. 比完整旅程總成本，不比裸票價；
2. 社群只負責發現，不是票價或政策真值；
3. `cheap broad discovery → narrow live verification`；
4. 外站四腿票可研究，跳段／棄程預設 BLOCK；
5. verification lifecycle 與 readiness facets 分離；
6. `CostComponent` 有 inclusion/dedupe，禁止重複計價；
7. Cloudflare-first、Win11 optional accelerator；
8. 沒有歷史資料時不捏造失接機率或風險小數點。

v1.3 新增以下施工不變條件：

```text
M. Source Intelligence Mesh：官方、旅行社、Email、社群、價格警報、機場/地方補貼、會員/信用卡、全球 deal source 分層治理
N. Push-first：能用 Email/webhook/官方 notification 就不以高頻 browser polling 取代
O. Source-of-sources：RouteUniverse + SourceDiscoveryGraph，自動發現新航線、新市場頁、新旅行社/社群來源
P. AgencyInventoryOffer：臨期清艙、團體位、包機位、神秘票獨立建模，不塞進一般 LIVE_FARE
Q. Source provenance：每筆情報都有 canonical URL / observed_at / hash / parser / access basis / retention
R. Source quality 四軸：DiscoveryTrust / VerificationAuthority / LeadScore / YieldScore
S. 自適應調度：高 first-win、高驗證率、低成本來源升頻；duplicate/ghost/高成本來源降頻或 quarantine
T. 官方取得階梯：API/RSS/sitemap/JSON-LD/conditional HTTP > static diff > browser > OCR
U. Email Authenticity：Message-ID、From domain、DKIM/SPF/DMARC 結果與 link safety 為證據的一部分
V. Event-to-offer trace：DISCOVERED_PROMOTION、SOCIAL_CLAIM、AGENCY_CLAIM 不得直接等同 BOOKABLE_OFFER
W. 社群隱私與刪除治理：封閉群不硬爬；通知轉發最小保存；刪除/更正事件可追溯
X. Market identity：同一家航空公司不同 market/language/currency 是不同 SourceKey
Y. Airline alias continuity：品牌/公司更名不得切斷歷史來源，例如 T'way Air → Trinity Airways，IATA TW 保持 alias continuity
```

三條來源真值硬規則：

```text
DISCOVERED_PROMOTION != BOOKABLE_OFFER
SOCIAL_CLAIM != VERIFIED_FARE
LOW_BASE_FARE != LOW_TRIP_COST
```

v1.3 對兩份外部研究的衝突裁決：

- Threads：Meta 官方 Threads API 現有 `keyword_search`，支援 `TOP/RECENT`、`KEYWORD/TAG`、時間窗與 `threads_keyword_search` scope；因此可列正式 adapter，但必須受 OAuth、平台條款、額度、刪除與保存 policy 控制，不採第三方 scraper 作 Production 預設。
- LINE OpenChat：LIFF 目前不正式支援 OpenChat；因此不設計「OpenChat 全網 API 爬蟲」。高價值 OpenChat 採使用者正常加入後的 Android notification sensor／人工轉貼；公開 cover/recommendation 頁只做 source discovery。
- Travelpayouts/Aviasales Data API：官方明示資料源自使用者搜尋快取，並可保存 7 天；`get_special_offers` 可做異常低價 discovery，但不得升為 live fare authority，任何候選仍需 reprice。
- T'way Air／Trinity Airways：航空公司官方公告確認 2026-09-10 起以 Trinity Airways 名稱營運，IATA `TW` 與航班號碼維持；Source Registry 必須做 alias migration，不建立一份失去歷史的「新航空公司」。

證據優先序維持：

```text
政府／航空公司／平台官方現行文件
> 已驗證合作/產品/API文件
> 多來源一致且可重現之研究
> 社群與媒體線索
```

任何來源若 access basis、條款、政策、登入需求或資料保存權限無法確認：

```text
EXPERIMENTAL or RECHECK_REQUIRED
```

不得為了覆蓋率自動繞過 CAPTCHA、登入限制、私人群組權限或平台存取控制。

# 1. Mission

建立一套可長期 24/7 運作的「台灣↔日本超值機票研究與追蹤系統」。

系統同時具備：

- 社群／官方促銷第一時間發現；
- 航線與日期彈性搜尋；
- 多種票型策略自動生成；
- 多來源獨立驗價；
- 完整現金總成本計算；
- 自助轉機、文件、行李、時間與失接風險判斷；
- 外站四段／四腿票全週期成本計算；
- 方案 Pareto 排序；
- Telegram／其他渠道即時通知；
- 長期累積歷史低價、促銷規律與來源可信度；
- 自動發現新航線、新促銷入口、新旅行社清艙入口與新高品質社群來源；
- 以來源 first-win、驗證成功率、ghost/duplicate/成本等指標自動升降頻；
- 對旅行社臨期／團體／包機庫存建立可追溯的獨立資料模型；
- 零增量月費優先、Cloud-first、Win11 非單點故障。

## 1.1 不做事項

v1.3 明確不做：

- 自動付款；
- 自動下單；
- 自動填信用卡；
- 自動繞過 CAPTCHA；
- 未授權大量爬取；
- 對第三方網站進行違反條款的高頻搜尋；
- 把 OTA／社群顯示價直接當成可購買真值；
- 自動推薦「故意跳段、棄程、隱藏城市」等可能違反航空公司票券使用順序的玩法；
- 把中國大陸的「外國人 24／240 小時過境免簽」直接套用到台灣旅客；
- 對沒有真實歷史數據的失接機率、延誤機率假裝有精準統計答案；
- 建立「全網通用登入爬蟲」或硬爬封閉 LINE／Facebook／私人群組；
- 用 browser/OCR 取代已有 RSS、Email、API、sitemap、JSON-LD 或 conditional HTTP 的來源；
- 因來源成員數、轉貼量或流量大就提高 VerificationAuthority；
- 把快取型 deal API、EDM、社群截圖、旅行社貼文直接標成可購買票價。

---

# 2. 2026-09 台日機票市場研究摘要

## 2.1 低價已高度「方向不對稱」

2026 年台灣旅遊社群持續出現同一航空公司在不同方向、不同航班、不同星期具有完全不同促銷條件的案例。

例如 2026 年 8 月的 Peach 台灣出發活動，東京、名古屋部分促銷要求從台灣搜尋來回，且特價只落在指定回程／指定星期；日本出發活動又可能是另一組價格與日期。

工程含義：

```text
禁止：RT price = outbound lowest + inbound lowest 的簡單假設
必須：分方向、分 flight number、分 weekday、分 sale window 建模
```

新增：

```text
DIRECTION_ASYMMETRY_DETECTOR
PROMO_CONSTRAINT_PARSER
```

## 2.2 「廉航票價」不能等於「廉航總價」

2026 年 PTT Japan_Travel 對台灣虎航訂閱／促銷的討論，反覆出現「加託運後與傳統航空差距縮小」的比較；也有旅客指出自己不託運、只買回程託運，結果又不同。

因此 baggage 必須是使用者 Profile 的必要維度：

```text
NO_CHECKED_BAG
CHECKED_BAG_OUTBOUND_ONLY
CHECKED_BAG_RETURN_ONLY
CHECKED_BAG_BOTH
SHOPPING_HEAVY_RETURN
```

系統不得只存一個 `baggage=yes/no`。

## 2.3 韓國轉機不是理論方案，已有近期台灣旅客實際使用

2026 年 Japan_Travel 有台灣旅客因北海道直飛價格偏高，改用真航空經仁川轉新千歲，並回報約 3 小時轉機與安檢耗時。

這類方案的價值不是「韓國一定比較便宜」，而是：

> 台韓供給密集 + 韓國↔日本供給密集，使 ICN／PUS／TAE／CJJ 等節點值得成為自動策略生成器的候選轉運節點。

## 2.4 自助轉機的低價，必須加上失接尾部風險

KAYAK 對 Hacker Fare 的官方說明指出：兩張單程票是兩份分開預訂；一張票取消不會讓另一家航空負有退款／改票義務。

Kiwi 也明確說明 self-transfer 並非承運航空的正式聯程；若第一段中斷，承運人通常沒有義務處理後續獨立訂位。Kiwi 的 Guarantee 是額外保護層，不是把兩張分票變成航空公司的 protected connection。

2026 年 Reddit 的熱門討論也有旅客分享因第一段延誤而錯過獨立第二張票，臨時重買價格高於原本整趟票價的案例。社群案例只作風險證據，不作統計機率。

因此：

```text
SELF_TRANSFER != PROTECTED_CONNECTION
```

## 2.5 日本離境固定成本已變高

日本國際觀光旅客稅自 2026-07-01 起原則上為每次離境 JPY 3,000。現行官方規則另包含重要例外與過渡：未滿 2 歲、符合條件的入境後 24 小時內轉機等情形可免徵；2026-07-01 前成立且符合條件的運送契約可能沿用舊稅率，之後改變出境日期則必須重新依規則判斷。

因此模型不能只用：

```text
departure_from_japan = true → +JPY3000
```

而必須由 `PolicyRegistry` 依：

```text
transport_contract_at / ticket_issue_at
departure_at
change_at
traveler_age
transit_context
single_ticket_context
```

評估。

## 2.6 外站四段票有價值，但票券後果不能只用一個 BLOCK

外站四段票本身是可研究的 multi-city／stopover／foreign-origin 票型。不同航空公司對 coupon 未依序使用的後果可能包含：拒絕承運、後續 coupon 失效、重新計價或其他依票規處理。

v1.3 因此使用：

```text
FOREIGN_ORIGIN_4SEG_SEQUENTIAL   可評估
NESTED_TICKETS_FULLY_FLOWN       可評估
HIDDEN_CITY_OR_SKIP_SEGMENT      不自動推薦
BACK_TO_BACK_RESTRICTION_RISK    NEEDS_HUMAN / provider policy check
```

並把結果拆成：

```text
COUPON_SEQUENCE_VOID_RISK
COUPON_RECALCULATION_LIABILITY
CARRIER_REFUSAL_RISK
POLICY_UNKNOWN
```

不再把所有航空公司硬編碼成同一種後果。

# 3. 台日低價票完整策略分類

v1.3 定義 **20 個 active strategies（S00–S19）**。`S20` 哩程／點數機會成本移到 Future，不計入目前 Strategy Generator 的 active catalog。

| ID | 策略 | 典型例 | 預設風險 | v1.3 |
|---|---|---|---|---|
| S00 | 台灣直飛來回 | TPE↔NRT | 低 | Active |
| S01 | 兩張單程拼來回 | IT 去 + MM 回 | 低至中 | Active |
| S02 | 方向不對稱促銷配對 | 台灣出發促銷 + 日本出發促銷 | 低 | Active |
| S03 | Open-jaw 開口票 | TPE→KIX、NRT→TPE | 低 | Active |
| S04 | 台灣多機場 | TPE/TSA/KHH/RMQ/TNN | 低 | Active |
| S05 | 日本替代機場 | NRT/HND、KIX/UKB、FUK/KMJ/HSG/OIT 等 | 低至中 | Active |
| S06 | 日本國內接駁 | TPE→OKA + 日本國內線 | 中 | Active |
| S07 | 受保護轉機 | TPE→HKG→NRT | 中 | Active |
| S08 | 韓國單一票轉機 | TPE→ICN→CTS | 中 | Active |
| S09 | 韓國自助轉機 | TPE→ICN + ICN→CTS | 中高 | Active |
| S10 | 中國大陸單一票轉機 | TPE→PVG→NRT | 中 | Feature flag |
| S11 | 中國大陸自助轉機 | TPE→PVG + PVG→NRT | 高 | Feature flag + Document Gate |
| S12 | 香港／澳門自助轉機 | TPE→HKG/MFM + →日本 | 中高 | Active |
| S13 | 外站單程／反向票 | NRT→TPE 單程促銷 | 低 | Active |
| S14 | 外站四段完整飛 | ICN→TPE→JP→TPE→ICN | 中 | Active |
| S15 | Nested tickets | 外站票內再嵌另一完整來回 | 高 | Advanced flag |
| S16 | 會員／訂閱制 | Team Tiger | 低 | Active |
| S17 | 折扣碼／會員價 | Peach promo code | 低 | Active |
| S18 | Price Beat | Jetstar Price Beat | 低 | Active candidate |
| S19 | OTA／支付優惠 | Trip.com coupon、卡回饋 | 中 | Peripheral active |

Future：

```text
S20_MILES_POINTS_OPPORTUNITY_COST
```

CI 必須執行：

```text
assert active_strategy_count == 20
assert unique_strategy_ids == 20
assert S20 not in active_strategy_catalog
```

# 4. 「四腿票」正式工程定義

## 4.1 合法研究型態

以台灣居民為例：

```text
外站 A → TPE
TPE → 日本 B
日本 B → TPE
TPE → 外站 A
```

或：

```text
外站 A → TPE
TPE → 日本 B
日本 C → TPE
TPE → 外站 A
```

第二種同時包含日本 open-jaw。

## 4.2 真實成本不能只算四段主票

```text
FourLegCashCost =
    FourLegTicketAllIn
  + Positioning(Taiwan → ExternalOriginBeforeLeg1)
  + TailReturn(ExternalOriginAfterLeg4 → Taiwan)
  + RequiredHotel
  + GroundTransport
  + CheckedBagAllRelevantTickets
  + PaymentAndFX
  + DocumentCost
  + MandatoryTaxes
```

若第一段外站是日本：

```text
TPE → OKA positioning
OKA → TPE → Destination → TPE → OKA main ticket
OKA → TPE tail return
```

系統必須把頭尾兩張定位票納入；否則「四腿票省很多」可能只是會計幻覺。

## 4.3 `cycle_completion_state`

```text
NOT_STARTED
POSITIONING_BOOKED
AT_EXTERNAL_ORIGIN
LEG1_FLOWN
HOME_STOPOVER
MAIN_TRIP_ACTIVE
LEG3_FLOWN
TAIL_PENDING
CYCLE_COMPLETED
BROKEN
```

任何還沒完成第四段與返台補位的方案，研究報表須顯示：

```text
UNREALIZED_POSITIONING_LIABILITY
```

## 4.4 Coupon Sequence / Back-to-back Guard

對同一 ticket document：

```text
if segment[i] intentionally_skipped:
    recommendation = BLOCK_AUTOMATIC_RECOMMENDATION
    readiness.coupon_sequence = BLOCKED
```

但風險原因必須由 carrier policy snapshot 決定，不可一律寫成「票券必然作廢」：

```text
COUPON_SEQUENCE_VOID_RISK
COUPON_RECALCULATION_LIABILITY
CARRIER_REFUSAL_RISK
UNKNOWN_POLICY_CONSEQUENCE
```

另新增：

```text
BACK_TO_BACK_GUARD
```

對互相嵌套／重疊日期的往返票，只要 provider 條款可能禁止 back-to-back，就改為 `NEEDS_HUMAN`，不得自動宣稱可行。

政策來源須保存：

```text
carrier
terms_url
article_or_clause
observed_at
source_snapshot_hash
```

# 5. 韓國轉機策略

## 5.1 為什麼值得搜尋

台灣↔韓國與韓國↔日本供給密度高，因此 ICN/GMP/PUS/TAE/CJJ/CJU 是高價值轉運節點；但只有完整成本與 readiness 通過時才保留。

## 5.2 2026 文件基線：K-ETA 與入境申報分開建模

K-ETA 官方目前將臨時豁免延長至 **2026-12-31（KST）**。v1.3 不把「K-ETA 豁免」等同「免做所有入境文件」。

拆成兩條 Requirement：

```text
KR_KETA
KR_E_ARRIVAL_DECLARATION
```

目前官方 e-Arrival Card 網站顯示：K-ETA 豁免者屬於可能需申報對象，而持有效 K-ETA 者屬於免申報類別之一；電子申報可於抵韓前 3 日內提交，提交後 72 小時失效。

Policy：

```text
KR_KETA.effective_to = 2026-12-31T23:59:59+09:00
KR_POLICY_WATCH_WINDOW = 60d
refresh_margin = 30d
```

到期前進 Watch Window，或官方來源過舊：

```text
RECHECK_REQUIRED
```

**不得預設 2027-01-01 一定恢復、延長或取消 K-ETA。**

## 5.3 韓國 self-transfer 安全門檻

```text
RequiredConnectionBuffer =
    airport_base_buffer
  + immigration_margin
  + baggage_reclaim_margin
  + terminal_transfer_margin
  + checkin_cutoff_margin
  + security_margin
  + delay_margin
```

沒有本地歷史資料時：

```text
buffer_confidence = LOW
BUFFER_MODEL_UNCALIBRATED = true
```

只允許以官方最低轉機／報到條件 + 保守 policy margin 產生候選，不得把估計值假裝成 p95。

還必須逐案確認：

- 是否實際入境；
- 行李是否直掛；
- ICN/GMP 是否跨機場；
- 航廈變更；
- 承運人文件要求；
- 最晚報到時間；
- 夜間住宿與地面成本。

# 6. 中國大陸轉機策略

## 6.1 台灣居民不得套用外國人 24／240 小時規則

外國人過境規則與台灣居民來往大陸的文件制度是不同法制路徑。對 `TAIWAN_RESIDENT`：

```text
CN_24H_AIRSIDE_DIRECT = DO_NOT_INFER_ELIGIBILITY
CN_240H_ENTRY = DO_NOT_INFER_ELIGIBILITY
```

2025-11-20 起，國家移民管理局已公告可簽發一次有效台灣居民來往大陸通行證的口岸由 58 個增加至 100 個；這是**可能的入境文件取得路徑**，不是 self-transfer 自動可行證明。

## 6.2 預設 Gate

中國大陸策略一律先跑：

```text
traveler_document_class
→ carrier_boarding_document_check
→ airside_or_entry_required
→ bag_reclaim_requirement
→ terminal_or_airport_change
→ local_permit_path_if_needed
```

只要任何一項未知：

```text
DOCUMENT_CHECK_REQUIRED
ACTIONABLE = false
```

尤其：

```text
self-transfer → DOCUMENT_CHECK_REQUIRED by default
```

「不入境」也不能直接推導「一定能登機」；必須保存實際承運人的文件接受證據或人工核驗結果。

## 6.3 候選 Hub

```text
PVG / SHA
PEK / PKX
XMN / FOC
CAN / SZX
NKG / TAO / HGH ...
```

只作圖搜尋節點。中國大陸策略預設 feature flag，直到 `PG22_POLICY_TTL_PASS` 與文件 corpus 足夠才可在正式通知中標 `ACTIONABLE`。

# 7. 香港／澳門與其他區域轉機

v1.3 不把系統鎖死在中韓兩地。

候選：

```text
HKG
MFM
MNL
BKK/DMK
SGN/HAN
```

但越遠的 detour 預設受到：

```text
DETOUR_DISTANCE_PENALTY
EXTRA_DEPARTURE_TAX
OVERNIGHT_PENALTY
SELF_TRANSFER_RISK
```

約束。

近期 KAYAK 台北→東京頁面曾顯示 HKG 是常見的單次轉機點；這只用來證明「轉機路徑市場存在」，不把其即時平均價硬編碼為長期規則。

---

# 8. 日本替代機場與地面交通

系統要搜尋「目的城市」，不是只搜尋一個 IATA。

## 8.1 城市機場群

```text
TOKYO = [HND, NRT, IBR候選]
OSAKA_KANSAI = [KIX, UKB, ITM(國內接駁)]
FUKUOKA_N_KYUSHU = [FUK, HSG, KMJ, OIT, KKJ候選]
NAGOYA = [NGO, NKM(國內候選)]
SAPPORO = [CTS, OKD(國內候選)]
```

是否納入須由 route registry 與實際航班資料決定，不因地理接近就自動視為等價。

## 8.2 地面成本

```text
GroundConnectorCost =
    airport_to_target_city_fare
  + reservations
  + luggage_surcharge
  + last_train_risk
  + overnight_if_missed
```

社群已有「機票很便宜，但日本境內交通把節省吃掉」的實例，因此地面交通是正式成本，不是備註欄位。

## 8.3 `SavingsPerExtraHour`

```text
SavingsPerExtraHour =
    (BestDirectCashCost - CandidateCashCost)
    / ExtraJourneyHours
```

例如：

```text
直飛多花 NT$2,000，但替代機場多 6 小時
→ 每額外 1 小時只省 NT$333
```

由 Profile 設定是否值得。

---

# 9. 2026 台日票價必要稅費模型

## 9.1 日本國際觀光旅客稅

現行基線：2026-07-01 起原則上每次自日本出境 JPY 3,000。

必建模的非課稅／過渡條件至少包括：

```text
TRANSIT_DEPART_WITHIN_24H_AFTER_ENTRY
AGE_LT_2
OFFICIAL/OTHER_STATUTORY_EXEMPTION
PRE_2026_07_01_ELIGIBLE_TRANSPORT_CONTRACT
DEPARTURE_DATE_CHANGED_AFTER_EFFECTIVE_DATE
```

PolicyRecord 不得只有 `effective_from`：

```json
{
  "policy_code": "JP_INTERNATIONAL_TOURIST_TAX",
  "amount": 3000,
  "currency": "JPY",
  "announced_at": "...",
  "observed_at": "...",
  "effective_from": "2026-07-01T00:00:00+09:00",
  "travel_event": "DEPARTURE_FROM_JAPAN",
  "ticket_issue_rule": "EVALUATE_TRANSITION_RULE",
  "exemption_rules": ["TRANSIT_LT_24H", "AGE_LT_2", "OTHER_STATUTORY"],
  "authority": "NTA"
}
```

日本作外站的四腿票每一次實際離境都要獨立判定；例如日本外站週期可能出現兩次日本離境，不能只加一次稅。

## 9.2 台灣出境航空旅客機場服務費

這是台灣法定機場服務費，不是 Peach 專屬費率。

現行官方基線：

```text
through 2026-08-31: TWD 500
2026-09-01 through 2028-08-31: TWD 750
from 2028-09-01: TWD 1,000
```

由航空公司隨機票代收；法規另有未滿 2 歲等免繳條件。

建立：

```text
TW_AIRPORT_SERVICE_FEE
```

key 至少含：

```text
jurisdiction
origin_airport
traveler_class
travel_event_at
policy_version
```

航空公司公告只能作輔助 evidence；source of truth 優先使用交通部法規／公告。

## 9.3 稅費／票價 inclusion 與去重

live/checkout offer 很可能已包含部分稅費。任何稅費都不得「看到政策就再加一次」。

`CostComponent` 強制：

```text
inclusion_state = INCLUDED_IN_OFFER | ADD_ON | UNKNOWN
source_offer_id
tax_code
dedupe_key
```

規則：

```text
INCLUDED_IN_OFFER → 不再次加總
ADD_ON             → 加總
UNKNOWN            → cost_complete = false
```

`dedupe_key` 建議：

```text
(provider_offer_id, passenger_scope, tax_or_fee_code, segment_scope, currency, amount)
```

若 offer 無法辨識稅費內含狀態，只能顯示 `COST_INCOMPLETE`，不得宣稱完整總成本。

# 10. 低價搜尋工具／平台採用矩陣

| 工具／來源 | Access basis | 強項 | 主要限制 | v1.3 定位 |
|---|---|---|---|---|
| Google Flights | manual/browser consumer | 日期、價格追蹤、替代機場 | 無一般公開消費者查價 API | 人工／Browser oracle |
| ITA Matrix | consumer research | routing、multi-city、calendar | 不售票 | 研究 oracle |
| Skyscanner Indicative API | partner gated | 廣域探索 | partner access、indicative/cached | discovery only |
| Skyscanner Live API | partner gated | live pricing | 必須 user-generated、精確日期、Look-to-Book/deeplink 約束 | 不作背景掃描 |
| KAYAK | consumer/manual | Hacker Fare、彈性搜尋 | 分票規則獨立 | 策略 oracle |
| Kiwi.com | consumer/partner terms | virtual interlining | self-transfer、Guarantee 另計 | 候選 + protection class |
| Trip.com | consumer/partner | 多城市、Price Alert | PNR/checkout 必須重驗 | 使用者工具／交叉來源 |
| Airline direct | first party | 第一方可售價 | DOM/anti-bot/各家差異 | LCC 強驗證首選 |
| `gfly` / `fast-flights` | unsupported/undocumented wrapper | 快速 discovery | fragile、ToS/封鎖/schema drift | Weak verifier only |
| Amadeus Self-Service | official API | 結構化 published fare | **不回傳 low-cost carriers，另缺 AA/DL/BA** | non-LCC targeted cross-check only |
| Duffel | official commercial API | bookable offer | 費用、search-to-book 限制、FX | P0/P1 targeted strong verifier |

## 10.1 Provider AccessBasis Matrix

每個 adapter 必填：

```text
access_basis = OFFICIAL_API | PARTNER_CONTRACT | AIRLINE_DIRECT | MANUAL_ORACLE | PUBLIC_PAGE_MONITOR | UNSUPPORTED_WRAPPER
owner
terms_url
terms_snapshot_at
rate_policy
look_to_book_budget
storage_policy
kill_switch_state
```

沒有合法／可接受的 access basis：

```text
adapter_enabled = false
```

GitHub 套件授權與第三方資料抓取權限是兩件事；permissive license 不構成爬取授權。

## 10.2 Amadeus LCC exclusion

Amadeus Self-Service 官方 FAQ 明示不回傳 low-cost carriers，因此：

```text
if itinerary.contains_lcc and only_verifier == AMADEUS_SELF_SERVICE:
    verification = INSUFFICIENT
    PG21 = FAIL
```

不得把 Amadeus 空回解讀成「Peach／虎航／Jetstar ghost fare」。

## 10.3 Duffel cost guard

目前公開定價包含每張 confirmed order 固定費、Managed Content 百分比、paid ancillary 費、超過 1500:1 後的 excess search、以及需要換匯時的 FX fee。所有費率都放 `ProviderPricingRegistry`，施工／部署前重抓，不永久 hard-code。

政策：

```text
Duffel = P0/P1 targeted only
broad_discovery = forbidden
search_to_book_budget exceeded → CIRCUIT_OPEN / airline direct fallback
```

# 11. 各家「省錢方法」如何轉成系統功能

## Google Flights / ITA Matrix

保留 flexible dates、multi-city、routing constraint、Best/Cheapest trade-off 與人工研究 oracle；不設計成官方 API 依賴。任何 `gfly` 類工具一律隔離在 undocumented adapter。

## KAYAK Hacker Fare

合法的 Hacker Fare 是兩張獨立單程拼成往返：

```text
RoundTripCandidate = BestOW(outbound) + BestOW(inbound)
```

另加：

```text
independent_booking_risk
refund_rule_mismatch
baggage_rule_mismatch
currency/payment_mismatch
```

不得把 Hacker Fare 與 hidden-city／skip-segment／back-to-back 混為同一類；後者依平台／航空條款進 `COUPON_SEQUENCE_GUARD` 或 `BACK_TO_BACK_GUARD`。

## Kiwi self-transfer

`connection_protection_type` 必須區分：

```text
THROUGH_TICKET_CARRIER_PROTECTED
INTERLINE_PROTECTED
OTA_GUARANTEE
SEPARATE_UNPROTECTED
UNKNOWN
```

Kiwi Guarantee 若存在，另存：

```text
kiwi_guarantee_tier
benefit_form = CREDIT_OR_OTHER
exclusions
observed_terms_at
```

使用者要求託運、但該 self-transfer itinerary 明示不可託運時：

```text
BAGGAGE_INFEASIBLE
```

## Skyscanner

採：

```text
Indicative → discovery
Live → user-generated exact-date query only
```

兩者皆以合作 access 為前提。Live 結果 UI 若使用 Skyscanner 資料，必須遵循其 deeplink／展示要求；background user-less Live query 禁止。

## Trip.com

`multi-city` 不等於自動受保護。每張 TicketComponent 都保存 `pnr_group`；跨 PNR 預設進 separate-ticket risk。checkout 新增費用、優惠券、卡回饋都不得在未確認前當成 guaranteed cash reduction。

## Jetstar Price Beat Guarantee

Eligibility Engine 至少驗：

```text
Jetstar fare brand == Economy Starter
competitor source == operating airline official website
competitor fare == direct one-way
identical origin/destination airports
scheduled_departure >= application_time + 7d
Asia international time difference <= 90 minutes
mandatory fees/taxes included
promo/member fare excluded
optional add-ons excluded from comparison
```

Jetstar Japan (GK) 的差額與 10% reduction 目前以 voucher 處理；Alert 固定寫：

```text
可能符合 Price Beat，需官方核驗；GK benefit may be voucher, not cash.
```

不通過任何一項：

```text
PRICE_BEAT_INELIGIBLE
```

# 12. Strategy Generator

## 12.1 Input

沿用 v1.1，另新增：

```json
{
  "positioning_cost_attribution": "FULL",
  "risk_tolerance": "CONSERVATIVE",
  "alert_profile_id": "default"
}
```

`positioning_cost_attribution`：

```text
FULL     # 預設，100% 歸入本次台日旅程
PARTIAL  # 使用者明確表示定位地本身有獨立旅遊價值
ZERO     # 只允許使用者明確設定，研究報表仍保留 full-cost view
```

## 12.2 Bounded Expansion

```text
Level 0 direct RT / split OW / open-jaw
Level 1 alternate TW / JP airports
Level 2 protected one-stop
Level 3 KR/HKG/MFM self-transfer
Level 4 foreign-origin / four-leg
Level 5 nested advanced
```

Expansion baseline 不再含糊：

```text
BaselineEstimator priority:
1. fresh verified direct quote <= baseline_quote_ttl
2. recent indicative direct quote
3. route × direction × month historical median with sample_count guard
4. country-pair/distance-band fallback
```

只在：

```text
estimated_saving_vs_baseline >= expansion_threshold
```

才進下一層。

## 12.3 Graph State

```text
State = (
    airport,
    local_datetime,
    ticket_group_id,
    baggage_state,
    immigration_state,
    document_state,
    protection_type,
    overnight_state,
    cycle_state
)
```

Edge 仍包括 protected/separate flight、ground、airport change、positioning、hotel、immigration、bag reclaim。

## 12.4 Search Algorithm 與 Pareto 限縮

搜尋：

```text
bounded best-first search
+ dominance pruning
+ route prior
```

**Hard filters / readiness filters**：

```text
baggage feasibility
document freshness
coupon sequence
connection safety
cost completeness
max tickets / self-transfer / overnight profile limits
```

Pareto 僅保留三個主要維度，避免 9 維幾乎全部 non-dominated：

```text
CashTripCost
TotalElapsedTime
RiskClass
```

其他欄位作解釋與 hard filter，不再全部當 Pareto 軸。

# 13. 完整成本模型

## 13.1 CostComponent 去重不變條件

每個 CostComponent：

```text
inclusion_state
source_offer_id
dedupe_key
certainty
effective_event_at
paid_state
refundable
fx_snapshot_id
```

只有 `ADD_ON` 可在 offer total 之外再加；`INCLUDED_IN_OFFER` 只作拆解顯示；`UNKNOWN` 使 `cost_complete=false`。

## 13.2 `CashTripCost`

```text
CashTripCost =
    OfferTotalAlreadyIncluded
  + Σ AdditionalMandatoryCostComponent[ADD_ON]
  + CheckedBaggageNotIncluded
  + CabinBaggageNotIncluded
  + SeatIfRequired
  + BookingServiceFeeNotIncluded
  + PaymentFeeNotIncluded
  + FXSpreadOrFee
  + PositioningFlights
  + TailReturnFlights
  + GroundTransport
  + MandatoryHotel
  + DocumentFee
  + MandatoryInsurance
  - GuaranteedDiscount
```

信用卡回饋、里程、未確定 voucher 不直接扣除。

## 13.3 FX Snapshot

所有跨幣別成本保存：

```text
base_currency
quote_currency
rate
rate_source
rate_observed_at
provider_spread
card_fx_fee
settlement_currency
```

FX 來源失效：

```text
use_last_known_with_ttl → FX_STALE
FX_STALE → cost_complete=false for actionable comparison
```

## 13.4 `RiskAdjustedTripCost` 與 Scenario fallback

有足夠校準歷史資料時：

```text
RiskAdjustedTripCost = CashTripCost + Σ ExpectedLoss
```

沒有足夠歷史時，不捏造機率，改輸出：

```text
ScenarioAdjustedTripCost = {
  low,
  base,
  high
}
RiskAdjustedTripCost = null
```

`RiskClass` 全序：

```text
LOW < MEDIUM < HIGH < UNKNOWN
BLOCKED = excluded, not ranked
```

`UNKNOWN` 在保守模式下排在 HIGH 後面；不等於「一定更危險」，代表證據不足。

## 13.5 `GeneralizedTripCost`

若 RiskAdjusted 有單值：

```text
GeneralizedTripCost =
    RiskAdjustedTripCost
  + ExtraHours * UserValueOfTime
  + OvernightPenalty
  + AirportChangePenalty
  + BookingComplexityPenalty
```

若只有 scenario：輸出 `GeneralizedScenarioCost{low,base,high}`，不得把 `null` 偷填成 0。

## 13.6 必顯示 KPI

```text
SavingsVsBestDirect
SavingsPerExtraHour
RiskClass
CostCompleteness
```

除零護欄：

```text
if ExtraJourneyHours <= 0:
    SavingsPerExtraHour = null
```

# 14. Profile Engine

同一行程對不同人不是同一價值。Profile 至少包含：

```json
{
  "profile_id": "solo_tw_light",
  "home_city": "Taipei",
  "home_airports": ["TPE", "TSA"],
  "checked_bag_pattern": "RETURN_ONLY",
  "baggage_kg": 20,
  "seat_required": false,
  "red_eye_ok": true,
  "self_transfer_ok": true,
  "overnight_transfer_ok": false,
  "airport_change_ok": false,
  "mainland_permit_status": "UNKNOWN",
  "korea_entry_profile": "CHECK_AT_QUERY_TIME",
  "foreign_origin_ok": true,
  "positioning_cost_attribution": "FULL",
  "max_positioning_cost_twd": 2500,
  "value_of_time_twd_per_hour": 300,
  "min_savings_for_self_transfer_twd": 2500,
  "currency": "TWD"
}
```

Alert preference 另存私有 runtime profile，不進 public repo：

```text
quiet_hours = optional
p0_daily_budget = optional
quiet_hours_override_for_p0 = user-configurable
```

預設不擅自替使用者設定 23:00–08:00 等靜音規則。

公開 Repo 的 `profiles.example.json` 只能放 synthetic data；不得提交真實 home city 組合、私人群組／chat ID、旅行窗口或其他可識別偏好。

# 15. Fare / Promo Parser v1.3

除了 v1.0 的 route、price、tax、bag、sale time，新增：

```text
sale_direction
required_roundtrip
eligible_flight_numbers
eligible_weekdays
blackout_dates
origin_market
sales_currency
member_only
subscription_only
coupon_required
promo_code
fare_brand
baggage_bundle
minimum_stay
maximum_stay
stopover_allowed
open_jaw_allowed
change_rule
refund_rule
```

`PromoConstraint`：

```json
{
  "promo_id": "...",
  "origin_market": "TW",
  "direction": "OUTBOUND_OR_RT",
  "flight_numbers": ["MM627"],
  "weekdays": [2,3,4],
  "sale_start_at": "...",
  "sale_end_at": "...",
  "travel_start": "...",
  "travel_end": "...",
  "blackout_dates": [],
  "price_amount": 2380,
  "currency": "TWD",
  "tax_status": "EXCLUDED",
  "member_requirement": null,
  "source_authority": "AIRLINE_OR_SOCIAL_TRANSCRIPTION"
}
```

社群轉抄永遠不能升成 official constraint，除非重新對航空官方來源驗證。

---

# 16. Provider 驗價層級 v1.3

## Tier 0 — Intelligence Integrity

確認貼文／促銷頁存在且抽取無誤。

## Tier 1 — Broad Discovery

```text
historical baseline
official sale pages
Skyscanner Indicative (partner access only)
gfly/fast-flights or other replaceable weak sources
```

用途只回答「值不值得再查」。

## Tier 2 — Live Cross-check

```text
Google Flights manual/browser oracle
OTA live query
Skyscanner Live only on user-generated exact-date request and valid partner access
airline search
Amadeus Self-Service for non-LCC only
```

## Tier 3 — Bookable Strong Verification

```text
airline direct reproduction
bookable official/partner offer with known coverage
Duffel targeted offer when commercial guard allows
```

LCC：

```text
Amadeus Self-Service alone can never satisfy strong verification.
```

## Tier 4 — Human Checkout

核對姓名、行李、退改、票券順序、文件、最終總價與付款。

## 16.1 Verification policy

`CONFIRMED_FARE` 需符合其一：

1. airline direct 重現；
2. bookable provider offer 且已知覆蓋該 carrier；
3. 兩個獨立 live source 一致，且沒有 carrier-coverage exclusion。

weak wrapper + 社群轉貼不能升 `CONFIRMED_FARE`。

# 17. Verification Lifecycle + Readiness Facets v1.3

## 17.1 Verification lifecycle

只描述票價／offer 生命週期：

```text
DETECTED
→ PARSED
→ STRATEGY_EXPANDED
→ COST_ESTIMATED
→ VERIFYING
→ PROBABLE | CONFIRMED | GHOST | EXPIRED | NEEDS_HUMAN
```

不再把文件、行李、轉機安全硬塞進同一 state machine。

## 17.2 Readiness Facets

```text
FARE_VERIFIED
DOCUMENT_CLEAR
CONNECTION_ACCEPTABLE
BAGGAGE_FEASIBLE
COST_COMPLETE
COUPON_SEQUENCE_CLEAR
POLICY_FRESH
```

每個 facet：

```text
status = PASS | FAIL | UNKNOWN | STALE
reason_code
observed_at
expires_at
authority
source_snapshot_id
```

`ACTIONABLE` **不是持久狀態**，是即時計算：

```text
ACTIONABLE =
    verification_state == CONFIRMED
    AND every_required_facet == PASS
    AND no_required_facet expired
```

任何 facet 變 stale，下一次讀取即不再 ACTIONABLE，不需要寫「回退狀態」。

## 17.3 Connection protection classification

禁止：

```text
protected_connection: true/false
```

改用：

```text
THROUGH_TICKET_CARRIER_PROTECTED
INTERLINE_PROTECTED
OTA_GUARANTEE
SEPARATE_UNPROTECTED
UNKNOWN
```

並保存：

```text
validating_carrier
ticket_stock
pnr_group
mct_status
through_bag_status
reaccommodation_basis
evidence_id
```

# 18. DealScore、NetValueScore 與 P0 分工

四套指標不再互相搶角色。

## 18.1 `DealScore`

用途：**發現優先級／異常程度**。可在成本尚未完全驗證時觸發 provisional alert，但不能決定 ACTIONABLE。

## 18.2 P0 provisional trigger

可由 deterministic hard trigger 觸發，例如：

```text
fresh_price / fresh_direct_baseline <= anomaly_threshold
AND route_relevant
AND source_trust >= threshold
```

或大量獨立情報 burst。第一通通知必須標 `UNVERIFIED`。

## 18.3 `NetValueScore`

只用於 `ACTIONABLE` 或接近 ACTIONABLE 的候選做 scalar tie-breaker：

```text
CashSaving
TimeEfficiency
VerificationConfidence
ItineraryQuality
BaggageFit
DocumentConfidence
Flexibility
RiskPenalty
```

權重仍只是初始 policy，不宣稱統計最佳。

## 18.4 Pareto

Pareto 是呈現多種 trade-off，不是 P0 觸發器；只使用 cash × elapsed × risk-class 三軸。

因此：

```text
DealScore      = discovery urgency
Readiness      = can act safely?
NetValueScore  = scalar tie-breaker
Pareto         = user-facing trade-off
```

# 19. Pareto 排名

輸出：

```text
A. 最低現金價
B. 最低風險類別下的最低價
C. 最省時間
D. 最佳綜合值（NetValueScore）
```

Pareto frontier 只用：

```text
CashTripCost
TotalElapsedTime
RiskClass
```

`document certainty`、`baggage feasibility`、`cost complete` 等不是第四到第九個 Pareto 軸，而是 readiness/hard filter。

若 `RiskAdjustedTripCost` 尚不能計算，B 用 `RiskClass` 全序 + `ScenarioAdjustedTripCost.base` + `CashTripCost` 排序，畫面必須標明風險尚未統計校準。

# 20. 會員／訂閱制 Optimizer

## 20.1 Team Tiger

訂閱費與兌換券不能簡化成「免費機票」。`CouponRegistry` 必須保存：

```text
plan_type
booking_window
travel_window
cycle
roundtrip_required
same_point_roundtrip_required
name_change_forbidden
date_change_policy
subscriber_only
app_or_channel_requirement
fare_cap
taxes_and_booking_fee_excluded
baggage_excluded
observed_terms_at
```

過期或不在 travel window：

```text
EXPIRED / INELIGIBLE
```

RiskAdjusted/Scenario 增：

```text
voucher_expiry_risk
unused_subscription_allocation
```

決策畫面同時顯示：

```text
annualized_full_cost
sunk_marginal_cost
```

## 20.2 折扣碼

`CouponRegistry`：

```text
stackability
eligibility
booking_window
travel_window
new_booking_only
channel_requirement
account_login_required
expiry
```

未確認可疊加，不得疊算多個折扣。

# 21. Source Intelligence Mesh v1.3

本章取代 v1.2 的「即時偵測來源」清單。Production 目標不是抓最多資料，而是：

```text
最低取得成本
+ 最早 lead time
+ 足夠 route coverage
+ 可追溯 evidence
+ 合法 access basis
+ 少量高價值候選再做 live verification
```

## 21.1 來源事件 taxonomy

來源必須先分類，避免把不同性質訊號混成「低價票」。

```text
PROMOTION_ANNOUNCEMENT      # 官方促銷/折扣碼/會員日
FARE_INDICATIVE_SNAPSHOT   # 快取或近期他人搜尋價
BOOKABLE_OFFER             # 可重新定價的 offer
CHECKOUT_TOTAL             # 最接近實付的 checkout readback
AGENCY_CLEARANCE           # 旅行社臨期/團體/包機/計畫位
SOCIAL_DISCOVERY           # 社群發現
ROUTE_SUPPLY_SIGNAL        # 新航線/增班/復航/季節/包機
PACKAGE_VALUE_DEAL         # 機加酒/旅行產品
ELIGIBLE_DISCOUNT          # 信用卡/會員/支付優惠
SOURCE_DISCOVERY_SIGNAL    # 用來長出新 source，不是 fare
```

所有 downstream policy 固定：

```text
PROMOTION_ANNOUNCEMENT != BOOKABLE_OFFER
FARE_INDICATIVE_SNAPSHOT != BOOKABLE_OFFER
AGENCY_CLEARANCE != SELLER_CONFIRMED until seller/readback passes
SOCIAL_DISCOVERY != VERIFIED_FARE
ELIGIBLE_DISCOUNT != CASH_DISCOUNT until checkout applied
```

## 21.2 P0 第一方官方來源

P0 官方骨幹至少涵蓋：

```text
台灣：Tigerair Taiwan / China Airlines / EVA Air / STARLUX / Mandarin
日本：Peach / Jetstar Japan / JAL / ANA / ZIPAIR
韓國轉機：Trinity Airways(TW, former T'way) / Jeju Air / Jin Air / Air Busan / Air Seoul / Aero K / Eastar
港澳：Cathay Pacific / HK Express / Hong Kong Airlines / Air Macau / Greater Bay
中國大陸：Air China / China Eastern / Shanghai Airlines / China Southern / XiamenAir
其他區域低價候選：Scoot / AirAsia family / VietJet / Cebu Pacific
```

每家公司至少拆成：

```text
promotion/news/campaign
fare landing / low-fare map
new route / schedule opening
member-only / subscription
promo code
fee/baggage/payment changes
newsletter
app notification where lawfully accessible
official social account
```

同一家航空公司必須依 `market + language + currency + origin_market` 拆 SourceKey。台灣站、日本站、韓國站不得合併成同一來源，因促銷、幣別與可售條件常不同。

## 21.3 官方取得階梯：最輕的方法優先

每個 source adapter 必須從最便宜、最穩定、最少風險的方法開始：

```text
official API / webhook
→ RSS / Atom
→ sitemap / sitemap lastmod
→ structured JSON / JSON-LD / public endpoint
→ Email / app push / official notification
→ conditional HTTP (ETag / Last-Modified)
→ static HTML hash / DOM targeted diff
→ browser rendering
→ OCR / vision as last resort
```

禁止預設用 Playwright 掃所有頁。Browser 只有以下情況才啟動：

```text
JS-only content
login-authorized content owned by user
fare form must be rendered for targeted verification
image-only promotion where OCR is unavoidable
```

## 21.4 Push-first Email Intake

建立專用 promo inbox；可使用 Gmail connector／正式 mail ingestion。訂閱：

```text
airline newsletters
travel agency newsletters
airport/local-government campaigns
Google Flights price tracking
Skyscanner price alerts
bank/card/member promotions
mistake-fare/deal alerts where terms permit
```

每封 `EmailEvidence` 保存：

```text
message_id
from_address
from_registrable_domain
received_at
subject
body_sha256
attachment_sha256[]
dkim_result
spf_result
dmarc_result
canonical_links[]
expanded_links[]
link_risk_class
parser_version
retention_until
```

安全政策：

```text
DMARC/DKIM failure + unfamiliar domain → UNTRUSTED_EMAIL
shortlink → expand safely, never auto-pay
tracking URL → resolve to registrable domain before trust decision
EDM price → promotion/indicative only until official seller reprice
```

Google Flights `Any dates` 等 Email 只生成 discovery candidate；不能因 Google 寄信而直接 `CONFIRMED`。

## 21.5 旅行社／批發商／臨期清艙

旅行社不是一般 OTA adapter 的附註，建立獨立 `AgencyPartnerRegistry` 與 `AgencyInventoryOffer`。

公開監控至少包括：

```text
雄獅 / 可樂 / 東南 / 五福 / 山富 / 易遊網 / 易飛網
燦星 / 百威 / 喜鴻 / 大興 / 旅天下
航空票務型旅行社 / 日本專門旅行社 / 包機團體位業者
Trip.com 等 OTA promotion/coupon pages
```

合作型 intake 優先於高頻爬網站：

```text
partner webhook
Offer Submission API
Email intake
CSV / JSON
Google Sheet read-only feed
Telegram bot submission
approved LINE Official Account webhook
manual seller portal
consolidator / GDS / NDC feed when contract exists
```

旅行社 offer 最低欄位：

```text
seller_identity
seller_verification_state
product_id
allotment_type
origin / destination
flight_number if known
departure_at / return_at
price / currency
tax_inclusion
baggage
seats_total / seats_available / inventory_hint
minimum_group_size
booking_deadline / ticketing_deadline
refund_change_terms
official_booking_or_contact_channel
observed_at
source_evidence_id
```

`allotment_type`：

```text
PLANNED_SEAT
GROUP_FARE
CHARTER
CLEARANCE
MYSTERY_TICKET
PACKAGE_BREAKOUT
UNKNOWN
```

狀態：

```text
AGENCY_CLAIMED
→ INVENTORY_UNVERIFIED
→ AGENCY_RECONFIRM_REQUIRED
→ SELLER_CONFIRMED
→ CHECKOUT_REPRODUCED
→ SOLD_OUT / WITHDRAWN / EXPIRED
```

只有截圖、私人匯款、無正式賣方、無可驗證 booking/contact channel：

```text
SCAM_RISK or AGENCY_CLAIMED
```

不得升 `SELLER_CONFIRMED`。

## 21.6 臨期清艙專用偵測器

新增：

```text
LAST_MINUTE_CLEARANCE_DETECTOR
AGENCY_DISTRESSED_INVENTORY_DETECTOR
DEPARTURE_PROXIMITY_SCORER
```

訊號：

```text
departure_at 距 now 很近
清艙 / 清倉 / 尾單 / 即期 / 最後席次 / 最後機位 / 候補轉正
限時 / 限量 / 售完為止
只剩特定日期/航班
團體位 / 包機位 / 計畫票 / 神秘機票
不可退改 / 需立即開票
貼文快速編輯/刪除
price anomaly 高且庫存線索強
```

`DepartureProximityScore` 只能提高查核優先級，不得提高 VerificationAuthority。

## 21.7 社群與論壇

Production 可用來源：

```text
Threads official keyword_search
PTT Japan_Travel / Aviation / Korea_Travel
公開 Telegram 頻道（bot/client 權限合法時）
Dcard 公開可取得內容／高命中作者
FlyerTalk
Reddit approved API / Developer Platform
旅行社官方社群
高價值部落格 / RSS 聚合站
使用者主動轉貼 /report
```

Threads adapter：

```text
access_basis = META_THREADS_API
required_scope includes threads_keyword_search
search_type = RECENT for hot discovery
search_mode = KEYWORD | TAG
query pack = zh-TW / ja / ko / en + route/airport/carrier tokens
```

第三方 Threads scraper：

```text
production_default = DISABLED
```

除非另做 access-basis、ToS、刪除、保存與商業使用稽核。

LINE OpenChat：

```text
LIFF/OpenChat direct app integration = NOT_PRODUCTION_ASSUMED
public cover/recommendation page = SOURCE_DISCOVERY only
user-joined OpenChat → Android notification sensor = allowed personal sensor path
manual forward = allowed
closed/private group hard scraping = forbidden
```

社群熱度只提高 `verification_priority`，不提高票價權威。

## 21.8 Source-of-sources：RouteUniverse

以 JNTO 台日直飛定期航班頁、航空公司／機場班表、民航局資料建立 `RouteUniverse`。

RouteUniverse 不是 fare source，而是 source generator：

```text
route discovered/changed
→ airline market pages
→ airline promo/news/newsletter
→ destination airport news/campaign
→ prefecture/city tourism campaign
→ agency products
→ community query packs
→ price-alert subscriptions
```

每條 RouteUniverseEntry 保存：

```text
origin_airport
destination_airport
carrier_alias_id
service_type = SCHEDULED | SEASONAL | CHARTER | UNKNOWN
first_seen_at
last_seen_at
official_evidence_id
status
```

新航線／增班／復航／季節／包機訊號：

```text
NEW_ROUTE_SIGNAL
CAPACITY_INCREASE_SIGNAL
SERVICE_RESUMPTION_SIGNAL
SEASONAL_ROUTE_SIGNAL
CHARTER_RELEASE_SIGNAL
SCHEDULE_OPENING_SIGNAL
```

只提高相對 route/date 的 discovery priority，不直接形成 P0 fare alert。

## 21.9 SourceDiscoveryGraph

系統每日／每週從 evidence 中抽取：

```text
linked_domain
linked_account
mentioned_agency
mentioned_airline
recommended_group
canonical_redirect
first_discovered_by
reposted_by
```

形成：

```text
SourceDiscoveryEdge(from_source, to_candidate_source, relation, evidence, observed_at)
```

Google Alerts、Talkwalker Alerts、公開搜尋警報、OpenChat recommendation graph 等只能產生 `SOURCE_DISCOVERY_SIGNAL`，不得直接建立 fare truth。

候選新 source 必須先進 onboarding：

```text
DISCOVERED
→ ACCESS_BASIS_REVIEW
→ TERMS_AND_PRIVACY_REVIEW
→ SHADOW
→ ENABLED
```

不能因為被大量來源推薦就直接進 Production。

## 21.10 結構化 Broad Discovery

可用於大面積候選生成，但 authority 明確分級：

```text
Skyscanner Indicative        = partner-gated indicative
Google Flights tracking      = user-configured email discovery
Aviasales/Travelpayouts Data = cached indicative
Secret Flying / deal sites   = discovery only
OTA trend/calendar           = indicative until live search
```

Travelpayouts Data API 官方資料來自 Aviasales 搜尋快取，資料可保存 7 天；`get_special_offers` 可回異常低價。Production 規則：

```text
fare_freshness = CACHED
requires_repricing = true
verification_authority = LOW_TO_MEDIUM
never_confirm_alone = true
```

## 21.11 信用卡／會員／支付／套裝來源

監控：

```text
airline co-brand cards
bank travel offers
Visa/Mastercard/JCB/Amex campaigns
OTA card discount
promo codes
member day
subscription vouchers
flight + hotel bundles
airport/local-government cashback
```

只生成：

```text
ELIGIBLE_DISCOUNT
EXPECTED_REBATE
CARDHOLDER_ONLY
REGISTRATION_REQUIRED
QUOTA_LIMITED
PACKAGE_VALUE_DEAL
```

除非 checkout 已確認折扣實際套用，否則不得從 `CashTripCost` 扣除。

## 21.12 多語 Query Pack

最少：

```text
zh-TW: 清艙 清倉 即期 尾單 計畫票 神秘機票 最後機位 限量 售完 開搶 快閃 會員日 破盤 錯價 bug票 含稅 行李
ja: タイムセール セール 特別運賃 限定運賃 キャンペーン 先着 残席 空席 チャーター 台湾 台北 高雄
ko: 특가 초특가 프로모션 할인 항공권 대만 타이베이 가오슝
zh-CN: 清仓 尾单 临期 特价 错价 BUG票 台湾 日本
English: flash sale seat sale promo fare special fare mistake fare error fare limited seats last minute
```

與 IATA、city alias、carrier alias、market tokens 組合，不建立一條無限長 query。

## 21.13 自適應監控頻率

來源初始 poll interval 依類型設定，之後按效益調節：

```text
高 confirmation/yield
+ 高 first_source_win
+ lead time 明顯領先
+ 低 request/cpu cost
→ 提高頻率

高 duplicate
+ 高 ghost
+ 很晚才發現
+ 高反爬/成本/錯誤率
→ 降低頻率 / OPEN_CIRCUIT / QUARANTINE
```

Push source 不因「高價值」而額外輪詢。

## 21.14 Source Intelligence execution path

```text
Official API/RSS/Email/Website/Agency Webhook/Social Sensor/RouteUniverse
                              |
                              v
                       Source Adapter
                              |
                              v
                    Immutable Evidence
                              |
                              v
                 Normalize + Provenance
                              |
                              v
                Exact/Content/Event Cluster
                              |
              +---------------+----------------+
              |                                |
              v                                v
       Promo/Clearance Parser            Source Discovery Graph
              |                                |
              v                                v
      Candidate Priority Queue          New Source Onboarding
              |
              v
        Broad Discovery
              |
              v
    Targeted Live / Seller Verification
              |
              v
     Full Trip Cost + Readiness Facets
              |
              v
       Alert + Research Corpus
```

任何 adapter 壞掉只能讓系統 `DEGRADED`，不得拖垮 canonical ingest/outbox。

# 22. 來源品質、熱門程度與自適應調度 v1.3

不再使用單一 `source_score`。

## 22.1 四軸來源評估

```text
DiscoveryTrust          # 這個來源的情報值不值得立刻查
VerificationAuthority   # 它能對哪一種 claim 作真值證據
LeadScore               # 平均比其他來源早多少
YieldScore              # 單位抓取成本帶來多少已驗證有效候選
```

`VerificationAuthority` 由來源性質與 access basis 決定，不能靠熱門度「學高」。例如：

| 來源 | DiscoveryTrust | VerificationAuthority |
|---|---|---|
| 航空官方促銷頁 | 高 | 自身促銷條款高；即時庫存仍需 reprice |
| 航空可購買/checkout readback | 中 | 最高可取得 |
| 旅行社正式清艙頁 | 高 | 對自身庫存中高，視 seller readback |
| Google/Skyscanner/OTA 快取價 | 高 | 中或以下，需 live refresh |
| 長期高命中 PTT/Threads 作者 | 高 | 低 |
| LINE/Telegram 轉貼 | 中 | 低 |
| 匿名截圖 | 可高 discovery | 極低 |

## 22.2 長期統計

每個 source 追蹤：

```text
event_count
verified_candidate_count
confirmed_count
ghost_count
expired_before_verify
duplicate_count
first_source_win_count
median_lead_seconds
field_completeness
parse_failure_rate
fetch_error_rate
schema_drift_count
mean_request_cost
mean_cpu_ms
terms_stale_count
last_unique_deal_at
```

小樣本採 Bayesian prior，禁止一次命中就給滿分。

## 22.3 SocialHeat 仍只決定查核優先級

```text
SocialHeat =
    repost_velocity
  + independent_source_count
  + reply_velocity
  + first_source_reputation
```

允許：

```text
SocialHeat ↑ → verify sooner
```

禁止：

```text
SocialHeat ↑ → VerificationAuthority ↑
SocialHeat ↑ → CONFIRMED
```

## 22.4 SchedulerUtility

Shadow 初始可用：

```text
SchedulerUtility =
    0.30 * normalized_verified_yield
  + 0.25 * normalized_first_win_rate
  + 0.20 * normalized_lead_advantage
  + 0.10 * field_completeness
  + 0.10 * freshness_reliability
  - 0.05 * normalized_acquisition_cost
```

權重只是初始 policy，不宣稱統計最佳。

調度輸出：

```text
BOOST
KEEP
DOWNSHIFT
QUARANTINE
DISABLE
```

任何 `terms_snapshot_at` 過期或 access basis 失效，直接 `DISABLE/RECHECK_REQUIRED`，不允許分數抵銷合規 Gate。

# 23. 競品／現成方案研究裁決

## 可直接借用的成熟產品思路

1. Google Flights：追蹤、Cheapest/Best trade-off。
2. Skyscanner：broad indicative discovery → live check。
3. ITA Matrix：routing DSL 與 multi-city 研究。
4. KAYAK：two-one-way Hacker Fare。
5. Kiwi：virtual interlining。
6. Trip.com：OTA price alert／multi-city／下單資訊整合。
7. Jetstar：Price Beat eligibility。

## 不應複製的錯誤

- 把 cached price 當 live；
- 用一個「最低價」欄位掩蓋 baggage／tax；
- self-transfer 不標風險；
- 外站票不算 positioning；
- 四腿票鼓勵跳段；
- 以單一 scraper 作權威；
- 每分鐘暴力查全球日期；
- API 有 permissive GitHub license 就推論可任意爬第三方網站。

---

# 24. 生產架構 v1.3：Cloudflare-first LEAN

## 24.0 Source Mesh overlay

```text
Push: Email / Webhook / Android notification / Telegram report
Poll: official pages / RSS / sitemap / PTT / source discovery
Partner: Agency API / CSV / Sheet / NDC/GDS/affiliate
                              |
                              v
                    Cloudflare ingress
                              |
          +-------------------+--------------------+
          |                   |                    |
          v                   v                    v
   SourceRegistry        Evidence metadata     Durable jobs/outbox
          |                   |                    |
          +-------------------+--------------------+
                              |
                              v
                   bounded parser / cluster
                              |
                   heavy-only work lease
                              |
                              v
                 Win11 verifier (optional)
```

Cloudflare 保存 canonical metadata、來源註冊、hash、candidate、outbox；大型 HTML／圖片／附件若需要長期保存，使用 R2 或其他允許的物件儲存 profile，不能把大 payload 塞進 D1。

Email、Threads、旅行社、LINE notification 等任何來源均只進同一 evidence/provenance contract，不允許各自建立旁路真值。

```text
                    Public GitHub Repository
                   source / docs / CI / release
                             |
                             v
                 Cloudflare Worker ingress
          webhook / idempotency / tiny rules / outbox
                             |
                             v
                       Cloudflare D1
                   canonical lightweight state
                             ^
                             |
                    1-minute Cron dispatcher
                 lease small bounded work only
                             |
             +---------------+----------------+
             |                                |
             v                                v
     lightweight cloud batch            Win11 Optional Worker
                                      Playwright / OCR / heavy parse
                                      provider readback / Python
```

**Cron 不再負責一次做完 parse + scoring + verification。** Cron 只 dispatch due work、寫 checkpoint/cursor、維護小批次。

## 24.1 2026-09-14 Free-tier hard limits

Workers Free：

```text
requests: 100,000/day
CPU: 10 ms/invocation
memory: 128 MB
subrequests: 50/request
simultaneous outgoing connections: 6
Cron triggers: 5/account
```

D1 Free：

```text
rows read: 5,000,000/day
rows written: 100,000/day
storage total: 5 GB
storage per DB: 500 MB
databases per account: 10
D1 queries per Worker invocation: 50
single DB: single-threaded query processing
```

D1 `rows_read` 按實際掃描列計；未索引條件可能回傳少量結果卻掃大量 rows。自 2026-09-01 起 Free daily row limit 超額會拒絕 query 到 00:00 UTC reset。

## 24.2 Cron / Worker execution contract

只使用 1 個 `* * * * *` multiplexor 作主 dispatcher；其餘 trigger 保留，不做每策略一 cron。

每個工作：

```text
cpu_budget_ms
max_d1_queries
batch_size
continuation_cursor
priority
criticality
```

ZERO-INCREMENT-COST 初始 policy：

```text
cpu_budget_ms <= 7       # internal safety target, not provider guarantee
max_d1_queries <= 40     # keep margin under hard 50
large HTML parse = offload/defer
browser work = Win11 only
```

如果測試持續碰 CPU limit、D1 queueing 或 50-query margin：進 `SCALE_UP_EVALUATION`，不得靠縮短測試或關閉檢查硬撐。

## 24.3 Platform Budget Worksheet

Phase 1 必須產生實測 worksheet，至少列：

| Workload | freq/day | Worker invocations | D1 queries/invocation | rows_read | rows_written | CPU p95 | critical? |
|---|---:|---:|---:|---:|---:|---:|---|
| cron dispatcher | 1,440 | measured | measured | measured | measured | measured | yes |
| webhook ingest | event-driven | measured | measured | measured | measured | measured | yes |
| alert outbox | event-driven | measured | measured | measured | measured | measured | yes |
| policy refresh | low-frequency | measured | measured | measured | measured | measured | no |
| research/backfill | bounded | measured | measured | measured | measured | measured | no |

正常模式只允許非關鍵工作消耗至 daily read/write budget 的 70%；至少 30% 保留給 P0 ingest、outbox、heartbeat、policy readback。

Quota guard：

```text
70% → stop optional backfill
80% → degrade research
90% → critical-only
95% → emergency reserve + admin alert
```

所有 D1 query log `meta.rows_read` / `meta.rows_written`，PG23 以真實數據驗收。

# 25. 為什麼 Win11 只能當 Optional Accelerator

Win11 任務：

```text
15–30 秒高速 sensor
Playwright/Chromium airline verifier
圖片 OCR / vision 前處理
Python flight libraries
非 Worker 能完成的重計算
```

禁止：

```text
Win11 唯一 DB
Win11 唯一 alert router
Win11 唯一 scheduler
Docker Desktop 常駐大堆疊
Browser 24/7 常駐
```

Win11 離線：

```text
SYSTEM = DEGRADED
not DOWN
```

Cloudflare 仍可：

- 收 webhook；
- 每分鐘排程；
- ingest；
- D1；
- provisional alert；
- cloud verifier。

---

# 26. Win11 Worker 資源 Gate

設計驗收值，不是尚未實測的事實：

| 指標 | Gate |
|---|---:|
| idle resident RAM | `<150 MB` 目標 |
| 15 min avg CPU | `<1%` 目標 |
| Browser 常駐 | 禁止 |
| Chromium concurrency | 1 |
| local durable queue | SQLite |
| outbound-only control | 是 |
| open inbound Internet port | 0 |
| crash restart | 自動 |

Worker 以 outbound lease：

```text
GET /verification-jobs/lease
POST /verification-jobs/{id}/result
POST /worker-heartbeat
```

無需住宅 router port forwarding。

---

# 27. Repo 結構 v1.3

```text
fare-radar/
├── apps/
│   ├── worker-core/
│   ├── web-dashboard/
│   ├── email-intake/
│   └── win11-verifier/
├── packages/
│   ├── domain/
│   ├── schemas/
│   ├── source-registry/
│   ├── source-discovery/
│   ├── route-universe/
│   ├── evidence/
│   ├── email-intake/
│   ├── agency-intake/
│   ├── promo-parser/
│   ├── clearance-detector/
│   ├── strategy-generator/
│   ├── cost-engine/
│   ├── scoring/
│   ├── verification/
│   ├── alerts/
│   └── policy-registry/
├── data/
│   ├── airports.public.json
│   ├── airlines.public.json
│   ├── airline-aliases.public.json
│   ├── metro-airport-groups.json
│   ├── route-universe.seed.json
│   ├── source-seeds.public.json
│   └── synthetic-fixtures/
├── migrations/
├── tests/
│   ├── golden/
│   ├── sources/
│   ├── source_discovery/
│   ├── email/
│   ├── agency/
│   ├── strategy/
│   ├── cost/
│   ├── transfer/
│   ├── contracts/
│   ├── chaos/
│   ├── capacity/
│   └── policy/
├── config/
│   ├── sources.example.json
│   ├── provider_access.example.json
│   ├── promotion_channels.example.json
│   ├── agency_partners.example.json
│   ├── source_queries.example.json
│   ├── policy.example.json
│   └── profiles.example.json
├── docs/
│   ├── SPEC_v1.3.md
│   ├── ARCHITECTURE.md
│   ├── SOURCE_INTELLIGENCE.md
│   ├── SOURCE_ACCESS_POLICY.md
│   ├── AGENCY_CLEARANCE.md
│   ├── STRATEGY_CATALOG.md
│   ├── FARE_VERIFICATION.md
│   ├── TRANSIT_DOCUMENT_POLICY.md
│   ├── RUNBOOK.md
│   ├── SECURITY.md
│   ├── PLATFORM_BUDGET.md
│   └── THIRD_PARTY_NOTICES.md
├── .github/workflows/
├── wrangler.jsonc
└── README.md
```

每個 source config 強制：

```text
source_id
source_class
market
language
currency
access_basis
fetch_method
push_capable
min_interval_ms
max_burst
timeout_ms
backoff_multiplier
robots_or_terms_policy
storage_policy
retention_policy
parser
terms_snapshot_at
owner
kill_switch
```

Public repo 只放 synthetic profile/fixture 與公開來源 seed。CI 除 secret scan 外，再跑 git history privacy scan，禁止 token、chat/group ID、私人通知、真實個人旅行偏好、未授權原始社群內容進歷史 commit。

# 28. 核心資料模型 v1.3

## 28.1 `ItineraryCandidate`

```json
{
  "itinerary_id": "uuid",
  "strategy_type": "KR_SELF_TRANSFER",
  "cash_trip_cost_twd": 5900,
  "cost_complete": true,
  "risk_adjusted_cost_twd": null,
  "scenario_cost_twd": {"low": 5900, "base": 7600, "high": 14500},
  "generalized_cost_twd": null,
  "risk_class": "HIGH",
  "verification_state": "PROBABLE"
}
```

## 28.2 `OfferSnapshot`

```text
provider_offer_id
query_fingerprint
provider
market
locale
currency
passenger_mix
baggage_query
observed_at
expires_at
raw_sha256
source_snapshot_id
offer_total
fare_freshness
cached_or_live
```

任何 `CostComponent` 必須能追到 OfferSnapshot 或明確 policy evidence。

## 28.3 `TicketComponent`

```text
ticket_id
pnr_group
provider
ticket_type
connection_protection_type
validating_carrier
ticket_stock
segments
fare_brand
refund_rule
change_rule
```

## 28.4 `TransferBoundary`

```text
from_ticket_id
to_ticket_id
airport
self_transfer
protection_type
validating_carrier
mct_status
requires_entry
requires_bag_reclaim
through_bag_status
terminal_change
airport_change
scheduled_buffer_minutes
required_buffer_minutes
buffer_confidence
reaccommodation_basis
evidence_id
```

## 28.5 `CostComponent`

```text
type
amount
currency
twd_amount
inclusion_state
source_offer_id
dedupe_key
certainty
effective_event_at
paid_state
refundable
fx_snapshot_id
observed_at
```

## 28.6 `ReadinessFacet`

```text
itinerary_id
facet_type
status
reason_code
observed_at
expires_at
authority
evidence_id
```

## 28.7 `DocumentRequirement`

```text
jurisdiction
travel_event
traveler_document_class
status
announced_at
observed_at
effective_from
effective_to
valid_for_event_at
jurisdiction_timezone
authority_source
source_snapshot_id
```

## 28.8 `ProviderAdapter`

```text
provider_id
access_basis
terms_snapshot_at
rate_policy
look_to_book_budget
kill_switch_state
owner
```

## 28.9 `FourLegLiability`

```text
cycle_id
component_type = POSITIONING | MAIN_TICKET | TAIL_RETURN | HOTEL | DOCUMENT
amount
paid_state
refundable
booking_deadline
travel_deadline
remaining_exposure
recoverable_amount
```

## 28.10 `AuditEvidence`

```text
gate_id
spec_version
commit_sha
dependency_lock_hash
build_run_id
deployed_version
test_report_hash
provider_readback
unresolved_items
created_at
```

## 28.11 `SourceRegistry`

```text
source_id
owner_type
source_class
canonical_domain_or_account
market
language
currency
route_scope
access_basis
fetch_method
push_capable
discovery_trust
verification_authority
lead_score
yield_score
fare_freshness
requires_repricing
parser
terms_snapshot_at
privacy_class
retention_policy
min_interval_ms
max_burst
backoff_policy
kill_switch_state
last_success_at
last_unique_deal_at
status
```

## 28.12 `SourceObservation`

```text
observation_id
source_id
canonical_url
published_at
observed_at
content_sha256
content_version
raw_ref
parser_version
access_basis_snapshot
retention_until
deleted_at_source
correction_of_observation_id
```

所有 PromotionEvent、AgencyInventoryOffer、Social claim 都必須回溯至少一個 SourceObservation。

## 28.13 `PromotionEvent`

```text
promotion_id
promotion_type
carrier_or_seller
market
route_scope
sale_window
travel_window
price_claim
currency
promo_code
member_requirement
channel_requirement
status
first_observed_at
last_observed_at
cluster_fingerprint
primary_evidence_id
```

同一活動 Email、官網、Threads、PTT 轉貼只形成一個 PromotionEvent，多份 evidence 保留。

## 28.14 `AgencyInventoryOffer`

```text
agency_offer_id
agency_id
seller_verification_state
product_id
allotment_type
origin
destination
flight_number
departure_at
return_at
price
currency
tax_inclusion
baggage
seats_total
seats_available
inventory_hint
minimum_group_size
booking_deadline
ticketing_deadline
refund_change_terms
booking_or_contact_channel
observed_at
source_evidence_id
state
```

## 28.15 `RouteUniverseEntry`

```text
route_id
origin_airport
destination_airport
carrier_alias_id
service_type
first_seen_at
last_seen_at
status
official_evidence_id
```

## 28.16 `SourceDiscoveryEdge`

```text
from_source_id
to_candidate_source_key
relation_type
observed_at
evidence_id
confidence
onboarding_state
```

## 28.17 `EmailEvidence`

```text
message_id
from_address
from_domain
received_at
subject
body_sha256
attachment_sha256
dkim_result
spf_result
dmarc_result
canonical_links
expanded_links
link_risk_class
retention_until
```

## 28.18 `SourceHealthWindow`

```text
source_id
window_start
window_end
fetch_count
success_count
unique_event_count
confirmed_count
ghost_count
duplicate_count
first_win_count
median_lead_seconds
fetch_error_rate
mean_request_cost
mean_cpu_ms
schema_drift_count
recommended_schedule_action
```

## 28.19 Registry separation

四個 registry 不混為一表語意：

```text
SourceRegistry            # 哪裡取得情報
ProviderAccessRegistry    # 哪個 fare/provider 能怎麼查、額度、合約與 authority
PromotionChannelRegistry  # newsletter/app/social/member channel 與身份/市場
AgencyPartnerRegistry     # 旅行社身份、合作方式、submission/readback 契約
```

可共用底層 storage，但 schema/contract 必須分離，避免「旅行社有 webhook」被誤解為「票價 provider 有 bookable authority」。

# 29. Document / Tax / Provider Policy Registry

所有時效性規則採 event-time evaluation，而不是只看 `now`。

`PolicyRecord`：

```text
policy_code
jurisdiction
traveler_document_class
announced_at
observed_at
effective_from
effective_to
jurisdiction_timezone
travel_event
ticket_issue_rule
valid_for_event_at
source_url
source_authority
source_snapshot_hash
refresh_margin
status
```

Policy evaluation：

```text
policy applicable? = evaluate(travel_event_at, ticket_issue_at, traveler_class, exceptions)
policy fresh?      = observed_at within refresh policy AND source still retrievable
```

到期／來源失效／適用事件落在未覆蓋期間：

```text
POLICY_STALE or RECHECK_REQUIRED
→ readiness.POLICY_FRESH != PASS
→ complex itinerary not ACTIONABLE
```

優先 Watch：

```text
KR K-ETA / e-Arrival
JP tourist tax
TW airport service fee
CN Taiwan-resident document policy
carrier coupon sequence terms
Jetstar Price Beat
Team Tiger
provider API terms/pricing
```

# 30. Source Intelligence Score v1.3

v1.2 的 `DiscoveryTrust + VerificationAuthority` 保留，v1.3 增加 lead/yield 維度。

```text
DiscoveryTrust
VerificationAuthority
LeadScore
YieldScore
```

## 30.1 DiscoveryTrust

回答：這個來源一出現情報，值不值得立即花配額查？

初始 prior 依 source class；累積資料後用 Bayesian shrinkage 更新，至少考慮：

```text
historical_confirmation_rate
parse_quality
field_completeness
correction_rate
ghost_rate
```

## 30.2 VerificationAuthority

回答：來源可以證明什麼？

這是 policy classification，不由社群 popularity 訓練得到。

```text
OFFICIAL_PROMO_TERMS
OFFICIAL_SELLER_INVENTORY
BOOKABLE_OFFER
CHECKOUT_TOTAL
INDICATIVE_FARE
SOCIAL_DISCOVERY_ONLY
POLICY_AUTHORITY
```

## 30.3 LeadScore

```text
lead_seconds = verified_event_first_time_elsewhere - source_first_observed_at
```

以 percentile/robust median 評估，不因單一爆料極早就永久升級。

## 30.4 YieldScore

衡量每單位取得成本產生的有效候選：

```text
verified_unique_candidates
/ (requests + cpu_cost_weight + monetary_api_cost_weight + human_review_weight)
```

Push source 取得成本很低時會自然獲得調度優勢。

## 30.5 自適應 schedule

只有 `ENABLED + terms fresh + access basis valid` source 可進 schedule optimizer。

```text
BOOST      = high yield + high first-win + low acquisition cost
KEEP       = stable
DOWNSHIFT  = high duplicate / low unique yield
QUARANTINE = schema drift / policy ambiguity / repeated parser corruption
DISABLE    = terms/access/privacy gate fail
```

`DISABLE` 不能被分數覆蓋。

## 30.6 航空品牌 alias

品牌或公司更名以 alias graph 維持同一歷史 entity，例如：

```text
T'way Air --effective 2026-09-10--> Trinity Airways
IATA code TW remains alias key
```

來源統計、route history、舊 URL evidence 不因更名歸零。

# 31. Alert Policy v1.3

每張候選卡至少顯示：

```text
price_observed_at
fare verification tier
cash total
missing cost components
cost completeness
risk class / scenario range
connection protection type
document/policy expiry
baggage feasibility
```

## P0 provisional

允許先快報，但固定標：

```text
UNVERIFIED / VERIFYING
```

## P0 complex

只有 `ACTIONABLE=true` 才能使用「可執行候選」字樣；否則必須顯示卡住的 facet。

## Foreign-Origin

同時顯示主票、頭定位、尾補位、已付／未付 liability 與完整週期成本。

## Notification budget

```text
quiet_hours = per-user optional
p0_daily_budget = per-user optional
admin_alert_channel = separate from user deal channel
```

沒有使用者設定時不擅自啟用 DND。系統內部故障告警固定走 admin channel，不與促銷通知混用。

# 32. Historical Baseline v1.3

不能把所有價格混成 route median。

至少分層：

```text
route
metro_pair
direction
trip_type
nonstop_or_stop
protected_or_self_transfer
fare_brand
baggage_profile
weekday
season
holiday_bucket
advance_purchase_bucket
provider
```

例如：

```text
TPE-NRT one-way no-bag
```

不能直接與：

```text
TPE-NRT roundtrip return-bag legacy
```

比較。

---

# 33. Research Engine v1.3

每日／每週產生兩類研究輸出。

## 33.1 Fare / strategy research

- 台日各 route 最低 CashTripCost；
- direct vs split OW；
- direct vs KR/CN/HKG/MFM transfer；
- foreign-origin yield；
- baggage sensitivity；
- weekend/weekday spread；
- sale-direction asymmetry；
- promotion lead time；
- P0 survival time；
- ghost fare rate by provider；
- self-transfer theoretical saving；
- self-transfer risk events；
- positioning cost distribution；
- `SavingsPerExtraHour` distribution。

## 33.2 Source intelligence research

- event count / unique event count by source；
- source first-win rate；
- median lead advantage；
- confirmation / ghost / correction rate；
- duplicate ratio；
- parser completeness；
- request/API/CPU cost per verified unique event；
- source schedule action history；
- source onboarding conversion `DISCOVERED→ENABLED`；
- agency clearance sell-through survival curve；
- Email vs web vs social first-source comparison；
- official page vs community propagation lag；
- new-route signal → first promotion lag；
- cached discovery → live reprice hit rate；
- Travelpayouts/indicative provider freshness distribution；
- RouteUniverse missing/added route audit。

沒有完整市場 ground truth：

```text
禁止宣稱 95% recall
```

只能報 observed coverage、backfill misses 與 source-specific lag。

# 34. Shadow Mode v1.3

14 天仍只是最短時間條件，不等於自動 PASS。

初始工程驗收最低 corpus：

```text
shadow_days >= 14
labeled_candidates >= 150
labeled_complex_candidates >= 30
labeled_source_discovery_events >= 30
labeled_agency_clearance_events >= 10  # 若此期間實際觀察到足夠事件；不足則 NOT_ENOUGH_EVIDENCE
```

這些是施工 Gate 的最低工程樣本，不宣稱具統計代表性。

人工 label：

```text
TRUE_DEAL
NORMAL
GHOST
EXPIRED
BAG_ERASED_SAVINGS
GROUND_ERASED_SAVINGS
SELF_TRANSFER_NOT_WORTH_IT
DOCUMENT_BLOCKED
FOUR_LEG_WORTH_IT
FOUR_LEG_POSITIONING_ERASED_SAVINGS
AMADEUS_LCC_MISS
BEAT_WINDOW_MISS
TAX_EXEMPT_MISS
COST_DEDUP_MISS
POLICY_STALE_MISS
PROTECTION_CLASS_MISS
PROMO_NOT_BOOKABLE
AGENCY_CLEARANCE_TRUE
AGENCY_CLEARANCE_GHOST
AGENCY_SELLER_UNVERIFIED
EMAIL_AUTH_FAIL
EMAIL_LINK_RISK
SOURCE_DUPLICATE_HEAVY
SOURCE_FIRST_WIN
SOURCE_LATE_REPOST
SOURCE_ACCESS_STALE
SOURCE_DELETION_OBSERVED
CACHED_FARE_REPRICE_MISS
ROUTE_UNIVERSE_NEW_SIGNAL
```

`PG15_SHADOW_ACCEPTANCE_PASS` safety-critical 條件：

```text
ACTIONABLE with stale policy = 0
ACTIONABLE with missing mandatory cost = 0
ACTIONABLE with coupon-sequence BLOCK = 0
ACTIONABLE with document facet UNKNOWN/STALE = 0
critical alert lost after durable persist = 0
untrusted email causing CONFIRMED = 0
social/indicative source alone causing CONFIRMED = 0
agency anonymous/private-payment claim causing SELLER_CONFIRMED = 0
```

來源分數只在 Shadow 後調整 schedule；不得在未通 Gate 前自動擴大存取範圍。

# 35. Golden Corpus v1.3

Golden Case 一律用 `GCxx`，與 Production Gate `PGxx` 分離。

| Case | 情境 | 預期 |
|---|---|---|
| GC01 | TPE→NRT TWD 1,790 未稅 | 不得以 1,790 作總價 |
| GC02 | 去 IT、回 MM 比單一 RT 低 | `SPLIT_ONEWAY` |
| GC03 | 回程促銷限定星期三 | 只生成符合 weekday 候選 |
| GC04 | LCC + return 20kg 後仍最低 | 保留 |
| GC05 | LCC + 20kg both ways 後高於 legacy | 降級 |
| GC06 | TPE→ICN + ICN→CTS | KR self-transfer + separate risk |
| GC07 | ICN 需重領行李 | buffer 增加且 protection 非 carrier-protected |
| GC08 | 大陸 self-transfer、台胞證未知 | `DOCUMENT_CHECK_REQUIRED` |
| GC09 | 單票／interline protected PVG connection | protection class 正確 |
| GC10 | TPE→KIX、NRT→TPE | `OPEN_JAW` |
| GC11 | HSG 便宜但地面交通昂貴 | ground cost 納入 |
| GC12 | 日本出發新票未計 JPY 3,000 | FAIL |
| GC13 | 外站四段主票便宜、頭尾定位昂貴 | 不得標最省 |
| GC14 | 外站四段完整依序使用 | 可評估 |
| GC15 | 打算跳第一段 | coupon facet BLOCK |
| GC16 | Hacker Fare 第一張取消 | 不得顯示 carrier protection |
| GC17 | Kiwi no-checked-bag + user 20kg | `BAGGAGE_INFEASIBLE` |
| GC18 | Jetstar 台日 competitor ±90m、Starter、7d、官網 | eligible candidate |
| GC19 | Team Tiger 已付費 | 同顯 sunk marginal / annualized |
| GC20 | 同一神票 100 轉貼 | 1 candidate + 100 evidence |
| GC21 | Offer total 已含 JP tax，又建立 tax component | dedupe：不得二次加總 |
| GC22 | JP transit passenger 符合 24h 免稅 | JP tax = 0，policy evidence retained |
| GC23 | 旅客未滿 2 歲日本離境 | JP tax = 0 |
| GC24 | 日本作外站四腿、兩次實際應稅離境 | 分段判定，可能 2× tax |
| GC25 | KR K-ETA policy 進 watch window | `RECHECK_REQUIRED` |
| GC26 | LCC 只有 Amadeus 空回 | 不得標 GHOST/CONFIRMED |
| GC27 | D1 query unindexed full scan | PG23 fail |
| GC28 | 單 invocation 第 51 次 D1 query | batch 必須先切分，不得發出 |
| GC29 | CONFIRMED fare 但 DOCUMENT_STALE | ACTIONABLE=false |
| GC30 | same PNR 但 protection evidence 不足 | protection=`UNKNOWN` |
| GC31 | Price Beat 差 2 小時（Asia international） | INELIGIBLE |
| GC32 | ExtraJourneyHours <= 0 | SavingsPerExtraHour=null |
| GC33 | 航空官網宣布促銷但 live search 無席 | PROMOTION 保留；不得 CONFIRMED，標 `PROMO_NOT_BOOKABLE` |
| GC34 | 旅行社清艙頁有 2 席、正式 seller/booking channel 可重現 | `AgencyInventoryOffer→SELLER_CONFIRMED` |
| GC35 | 同一促銷由 Email、官網、Threads、PTT 四處出現 | 1 PromotionEvent + 4 SourceObservation |
| GC36 | 偽冒航空 EDM，DKIM/DMARC fail 且導未知 domain | `UNTRUSTED_EMAIL/SCAM_RISK`，不得查付款 |
| GC37 | Google Flights Any dates 寄低價通知 | 只生成 discovery candidate，需 live reprice |
| GC38 | Threads `keyword_search` 命中神票文字 | `SOCIAL_DISCOVERY`，不得單獨 CONFIRMED |
| GC39 | LINE OpenChat 原生通知轉入 | 最小保存；群內容不公開 commit；只能 discovery |
| GC40 | JNTO/官方 route 新增航線 | 建 RouteUniverse signal + 新 source onboarding，不直接 P0 fare |
| GC41 | Travelpayouts cached special offer 很低但 reprice 失敗 | `CACHED_FARE_REPRICE_MISS/GHOST-like discovery miss` |
| GC42 | source 原文後續刪除 | hash/evidence 保留依 retention policy；source status 更新 |
| GC43 | 旅行社只要求私訊匯款、無正式賣方頁 | `AGENCY_CLAIMED + SCAM_RISK`，不可 SELLER_CONFIRMED |
| GC44 | T'way 舊 URL/歷史資料與 Trinity Airways 新名稱 | alias continuity；TW route history 不歸零 |
| GC45 | 同航空台灣站與日本站促銷不同 | 兩個 SourceKey，不互相覆寫 market 條件 |
| GC46 | 信用卡回饋尚未在 checkout 套用 | 只 `EXPECTED_REBATE`，不得從 CashTripCost 扣除 |
| GC47 | source 90% 都是 duplicate late repost | `DOWNSHIFT`，但歷史 evidence 不刪除 |
| GC48 | source ToS/access snapshot 過期 | adapter `RECHECK_REQUIRED/DISABLED`，不再 dispatch |

# 36. Chaos / Failure Tests v1.3

沿用 429／5xx／DNS／schema drift，新增：

```text
Worker CPU budget exhausted mid-batch
D1 50-query boundary
D1 full-scan rows_read spike
D1 daily limit reached before UTC reset
D1 single-database overload/queue
FX source down / FX_STALE
Japan tax policy stale or exemption edge
K-ETA expiry/watch window
mainland document ambiguity
flight 1 schedule change breaks flight 2
same PNR but protection UNKNOWN
checked bag rule changes
promotion edited after ingestion
promo code revoked
subscription term/window changed
positioning ticket disappears
four-leg liability partially paid
one ticket confirmed, paired return ghost
OTA checkout adds fee already included elsewhere
fare currency/market changes
clock crosses JP/KR/TW date boundary
ACTIONABLE facet expires after initial display
provider terms kill switch activates
source ETag changes but content semantically identical
source content changes without Last-Modified
same promotion arrives via Email/web/PTT simultaneously
email forged From header with DKIM/DMARC failure
email tracking link redirects across unknown registrable domain
agency seats_available drops to zero between poll and recheck
agency withdraws/corrects price after alert
source page deleted after ingestion
LINE/Android notification sensor offline
Threads OAuth scope revoked / token expired
Threads search rate-limited
source discovery graph recommends malicious/phishing domain
RouteUniverse adds seasonal/charter route then removes it
Travelpayouts cached fare seven-day-old and reprice misses
carrier rename/alias migration during active promotion
source high-volume burst exceeds parser budget
```

批次工作 crash 後只允許由 durable cursor 重進，不得整批重跑造成 duplicate alert。

# 37. Security / Anti-scam

沿用 v1.0 原則：社群內容永遠是 untrusted data。

新增 complex-fare 防詐：

- 不跟社群短網址直接付款；
- domain normalize；
- 航空公司／核准 OTA allowlist；
- 未知付款頁 `SCAM_RISK`；
- Browser verifier 只查價，不填付款資料；
- 不把「代開四腿票、私訊匯款」升成 verified；
- 公開 Repo 不保存私人社群／通知原文；
- 所有外部 URL fetch 有 SSRF 防護；
- Email sender/domain 與 link destination 分開驗證，寄件者顯示名稱不是信任依據；
- 封閉社群 raw content 預設不進公開 repo，依 retention TTL 刪除；
- 來源刪除請求／平台刪除事件可標記並執行 retention policy；
- SourceDiscoveryGraph 新 domain 一律先 onboarding，不直接 fetch 高風險 URL；
- 旅行社 seller identity 與正式聯絡/購票渠道必須分離驗證。

---

# 38. Cloudflare/D1 資料保存與 Migration

```text
hot tables = small + indexed
raw payload = TTL
aggregates = precomputed
large media = not stored as D1 blob
```

Retention 仍以最小保存為原則。

所有 hot query 必須：

```text
EXPLAIN/plan review
index coverage
rows_read measured
rows_written measured including index amplification
```

Migration：

```text
pre-migration schema hash
backup/time-travel checkpoint where available
forward migration
smoke/readback
rollback rehearsal or compensating migration
```

不得只因 migration command exit 0 就宣稱完成。

Quota guard 使用 §24.3 的 critical reserve；`meta.rows_read/rows_written` 是 Gate 證據。

# 39. CI/CD

Public repository 的**標準 GitHub-hosted runner 運算分鐘**目前免費；artifact/cache/storage、larger runners 與未來政策分開監控，不再寫成「所有 Actions 無限制」。

PR Gate：

```text
format/lint
typecheck
unit
golden GC corpus
strategy catalog count/unique IDs
cost dedupe tests
readiness facet tests
protection classification tests
policy event-time tests
adapter contract/access-basis tests
capacity budget tests
secret scan
git-history privacy scan
license/third-party notice scan
wrangler dry-run
```

部署：

```text
feature branch
→ PR
→ CI PASS
→ preview/staging
→ smoke
→ production deploy
→ same-source health/readback
```

GitHub Actions 不作 hot-path fare monitor。

# 40. Observability / SLO v1.3

Metrics 延續前版並新增：

```text
d1_rows_read_total
d1_rows_written_total
d1_queries_per_invocation
worker_cpu_ms
worker_batch_size
cost_dedup_hit_total
readiness_facet_stale_total
protection_unknown_total
provider_kill_switch_total
policy_watch_window_total
```

設計 SLO（不是第三方 SLA）：

```text
webhook received → durable persist p95 <= 2s
received P0 candidate → provisional alert p95 <= 5s
cloud-only 1-minute source poll → detected target p95 <= 90s
Win11 fast sensor enabled → detected target p95 <= 30s
alert outbox due → delivered/failed-classified p95 <= 10s
persisted critical alert loss = 0
email/webhook source received → SourceObservation persisted p95 <= 3s
source observation → clustered candidate p95 <= 5s for hot-path parsable events
agency partner webhook → provisional agency candidate p95 <= 5s
terms/access marked STALE → new dispatches = 0
source correction/withdrawal received → candidate state update p95 <= 10s
```

所有 canonical timestamp 存 UTC ISO8601；顯示層預設 Asia/Taipei。政策適用時間用該 jurisdiction timezone 評估，不能先轉台北時間再判法規生效日。

重大內部警報走 admin channel：

```text
ALL_STRONG_VERIFIERS_DOWN
POLICY_REGISTRY_STALE_*
D1_QUOTA_CRITICAL
WORKER_CPU_BUDGET_EXCEEDED
WIN11_VERIFIER_OFFLINE
PROMO_PARSER_DRIFT
PROVIDER_TERMS_KILL_SWITCH
```

## 40.1 Source Intelligence metrics

```text
source_fetch_total
source_fetch_error_total
source_unique_event_total
source_duplicate_ratio
source_first_win_total
source_median_lead_seconds
source_confirmed_yield
source_ghost_total
source_schedule_action_total
source_terms_stale_total
source_quarantine_total
promotion_cluster_size
agency_clearance_total
agency_clearance_sellout_seconds
email_auth_fail_total
source_discovery_candidate_total
source_onboarding_enabled_total
route_universe_change_total
event_to_offer_reprice_hit_rate
```

管理警報：

```text
P0 source all down
email auth failure burst
agency seller correction after alert
source terms stale but dispatch attempted
source quarantine count spike
RouteUniverse stale beyond refresh policy
cached discovery reprice hit rate collapses
```

# 41. Operating Profiles

## Profile A — ZERO-INCREMENT-COST（預設）

這是**Operating Profile**，不是永久架構承諾。

```text
GitHub public repo
Cloudflare Workers Free
Cloudflare D1 Free
Telegram Bot
Win11 optional existing host
```

月固定新增基礎設施費目標 NT$0；不等於電費、網路、人力、partner API 永遠為 0。

## Profile B — SCALE-UP

任一條件持續成立即評估升級：

```text
Worker CPU limit recurring
D1 read/write reserve repeatedly compressed
single DB overload/queue
partner API requires controlled backend
strong verification demand exceeds Win11 availability
multi-user / larger retention required
```

升級是容量與可靠性決策，不是失敗。

# 42. 施工階段 v1.3

## Phase 0 — Repo / Schema / Invariants

交付：Public repo、`SPEC_v1.3.md`、domain schema、GC01–GC48、PG Evidence Contract、CI skeleton、四 Registry schema、source privacy fixtures。

驗收：`PG00 PG14 PG25`；active strategy count=20；Public repo secret/privacy/history scan 必須通過。

## Phase 1 — Durable Lean Core + Capacity Proof

交付：D1 schema、idempotent ingest、SourceObservation/evidence hash、outbox、cron dispatcher、cursor、quota guard、Platform Budget Worksheet。

驗收：`PG01 PG12 PG13 PG19 PG23 PG26`；Win11 offline 時 canonical ingest/outbox/alert path 仍可降級運作。

## Phase 2 — Source Intelligence Mesh Foundation

先接低風險、高權威、低成本來源：

```text
official airline sale/news pages
Peach/Tigerair 等 newsletter
Google Flights user-configured tracking Email
JNTO RouteUniverse
PTT/RSS
official airport/new-route feeds
```

建立 SourceRegistry、ProviderAccessRegistry、PromotionChannelRegistry、RouteUniverse、SourceDiscoveryGraph onboarding skeleton。

驗收：`PG02 PG20 PG25 PG26 PG29 PG31 PG35`。

## Phase 3 — Agency / Community / Promo & Clearance Parser

交付：旅行社公開 campaign、Agency Submission API/Webhook/Email、Threads official keyword search、Telegram/Android sensor、promo parser、clearance detector、promotion cluster。

封閉群不硬爬；Threads 第三方 scraper 預設 disabled。

驗收：`PG03 PG27 PG28 PG30 PG33`，對應 `GC33–GC45` 相關 source cases。

## Phase 4 — Direct/Split/Open-jaw + All-in Cost

先完成產品閉環：direct、split OW、open-jaw、bag、tax、FX、ground、cost dedupe、未套用 rebate 不扣 CashTripCost。

驗收：`PG04 PG17`，對應 `GC04 GC05 GC10 GC11 GC12 GC21–GC24 GC32 GC46`。

## Phase 5 — Strategy Generator Basic

台灣／日本機場群、方向促銷、bounded expansion、3D Pareto。

驗收：`PG05 PG36`；source scheduling 只調 acquisition priority，不改策略安全 Gate。

## Phase 6 — Transfer Engine

KR/HKG/MFM；保護類型、bag recheck、buffer。中國大陸仍 feature flag；Trinity Airways 使用 airline alias continuity。

驗收：`PG06 PG18`，對應 `GC06 GC07 GC09 GC16 GC17 GC30 GC44`。

## Phase 7 — Policy Registry

JP/TW/KR/CN、event-time、TTL/watch window、source snapshots、provider/source terms refresh。

驗收：`PG07 PG22 PG31`，對應 `GC08 GC22–GC25 GC48`。

## Phase 8 — Foreign-Origin / Four-Leg

positioning、tail liability ledger、cycle、coupon sequence、nested bounded mode。

驗收：`PG08 PG10`，對應 `GC13–GC15 GC24`。

## Phase 9 — Multi-provider Verification

airline direct、weak adapters、non-LCC Amadeus、targeted Duffel、cached discovery reprice、event-to-bookable trace。

驗收：`PG09 PG21 PG32`，對應 `GC26 GC33 GC37 GC38 GC41`。

## Phase 10 — Alert / UX + Adaptive Source Scheduling

simple/complex/foreign-origin/agency-clearance card、facet explanation、Price Beat eligibility、source provenance、schedule action explainability。

驗收：`PG11 PG24 PG34 PG36`。

## Phase 11 — Shadow Acceptance

至少 14 天且滿足 §34 corpus 與 safety-critical zero-error conditions；來源升降頻需留下可回放決策證據。

驗收：`PG15 PG16 PG34 PG36`。

## Phase 12 — Production Gate

所有 applicable `PG00–PG36` PASS + Evidence Contract 完整才可升 Production。

# 43. Production Gates v1.3

Production Gate 一律使用 `PGxx`：

```text
PG00_PUBLIC_REPO_AND_CI_PASS
PG01_CORE_DURABILITY_PASS
PG02_SOURCE_ISOLATION_PASS
PG03_PROMO_CONSTRAINT_GOLDEN_PASS
PG04_ALL_IN_COST_GOLDEN_PASS
PG05_BASIC_STRATEGY_SEARCH_PASS
PG06_SELF_TRANSFER_RISK_PASS
PG07_DOCUMENT_POLICY_STALENESS_PASS
PG08_FOREIGN_ORIGIN_CYCLE_PASS
PG09_MULTI_PROVIDER_VERIFY_PASS
PG10_COUPON_SEQUENCE_GUARD_PASS
PG11_COMPLEX_ALERT_EXPLAINS_TOTAL_COST_PASS
PG12_D1_QUOTA_DEGRADE_PASS
PG13_WIN11_OFFLINE_DEGRADE_PASS
PG14_SECRET_PRIVACY_PASS
PG15_SHADOW_ACCEPTANCE_PASS
PG16_COMPLEX_STRATEGY_REVIEW_PASS
PG17_OFFER_COST_DEDUP_PASS
PG18_CONNECTION_PROTECTION_CLASSIFICATION_PASS
PG19_WORKER_CPU_BUDGET_PASS
PG20_PROVIDER_ACCESS_BASIS_PASS
PG21_AMADEUS_LCC_EXCLUSION_PASS
PG22_POLICY_TTL_PASS
PG23_D1_SCAN_BUDGET_PASS
PG24_PRICE_BEAT_WINDOW_PASS
PG25_SOURCE_REGISTRY_CONTRACT_PASS
PG26_SOURCE_PROVENANCE_AND_HASH_PASS
PG27_PROMOTION_CLUSTER_DEDUP_PASS
PG28_AGENCY_CLEARANCE_INTAKE_PASS
PG29_EMAIL_AUTHENTICITY_AND_LINK_SAFETY_PASS
PG30_SOCIAL_RETENTION_PRIVACY_PASS
PG31_SOURCE_RATE_TERMS_GUARD_PASS
PG32_EVENT_TO_BOOKABLE_OFFER_TRACE_PASS
PG33_SOURCE_CORRECTION_DELETION_PASS
PG34_HIGH_VOLUME_SOURCE_DEGRADE_PASS
PG35_ROUTE_UNIVERSE_SOURCE_DISCOVERY_PASS
PG36_SOURCE_SCORING_ADAPTIVE_SCHEDULE_PASS
```

## 43.1 Gate Evidence Contract

每個 PG 必須輸出：

```text
gate_id + spec_version
source commit SHA
dependency lock hash
exact test command
test fixture/corpus version
start/end timestamp
machine-readable report + SHA-256
expected output / threshold
actual result
deployment environment/version/ID (if applicable)
same-source/provider readback (if applicable)
source/access/terms snapshot IDs (if applicable)
rollback/degrade rehearsal result
unresolved items
```

Gate PASS 必須可重現。`test says pass`、HTTP 200、deploy accepted、workflow green 都不能單獨當業務 PASS。

## 43.2 Gate-to-test executable mapping

| Gate | 最低測試／命令 | PASS 下限 |
|---|---|---|
| PG00 | `pytest -q tests/repo/test_repo_ci_contract.py` | clean checkout 可安裝；required CI 全綠；main protection 存在 |
| PG01 | `pytest -q tests/durability/` | duplicate ingest、crash/restart、outbox replay 不遺失、不重複業務效果 |
| PG02 | `pytest -q tests/sources/test_adapter_isolation.py` | 任一 source 429/5xx/schema drift 不拖垮其他 adapter |
| PG03 | `pytest -q tests/golden/test_promo_constraints.py` | GC01–GC03 全部符合方向／星期／sale window 約束 |
| PG04 | `pytest -q tests/cost/test_all_in_cost.py` | mandatory cost 完整；cost_complete=false 不得宣稱最低總價 |
| PG05 | `pytest -q tests/strategy/test_basic_search.py` | S00–S19 唯一；bounded expansion；3D Pareto deterministic |
| PG06 | `pytest -q tests/transfer/test_self_transfer_risk.py` | baggage/document/buffer 任一 BLOCK 時不得 ACTIONABLE |
| PG07 | `pytest -q tests/policy/test_staleness.py` | STALE/RECHECK_REQUIRED policy 不得支撐 ACTIONABLE |
| PG08 | `pytest -q tests/foreign_origin/test_cycle_cost.py` | positioning、tail、tax、liability 全週期可重算 |
| PG09 | `pytest -q tests/verification/test_multi_provider.py` | provider mismatch、timeout、expiry 有 evidence-backed 結果 |
| PG10 | `pytest -q tests/ticketing/test_coupon_sequence.py` | skipped coupon / forbidden pattern 永遠 BLOCK；carrier consequence 不混用 |
| PG11 | `pytest -q tests/alerts/test_complex_card_schema.py` | alert 必含 total cost、缺漏、protection、policy TTL、observed_at、source provenance |
| PG12 | `pytest -q tests/capacity/test_d1_quota_degrade.py` | 95% quota 仍保留 P0 ingest/outbox/heartbeat；非關鍵工作降級 |
| PG13 | `pytest -q tests/resilience/test_win11_offline.py` | Win11 offline 不影響 canonical DB/scheduler/router；狀態 DEGRADED |
| PG14 | `pytest -q tests/security/test_public_repo_privacy.py` | secret/history scan；真實 profile/chat/group ID 洩漏 = 0 |
| PG15 | `pytest -q tests/shadow/test_acceptance.py` | ≥14 日、≥150 labeled、≥30 complex，且 §34 safety-critical 全為 0 |
| PG16 | `pytest -q tests/shadow/test_complex_review.py` | 所有複雜策略均有人審樣本與 false-actionable audit |
| PG17 | `pytest -q tests/cost/test_offer_component_dedup.py` | INCLUDED_IN_OFFER 不二次加總；unknown 有保守結果 |
| PG18 | `pytest -q tests/transfer/test_protection_classification.py` | protection type 必有 evidence；同 PNR 不自動推定 protected |
| PG19 | `pytest -q tests/capacity/test_worker_cpu_budget.py` | bounded batch 在 Free CPU budget；超預算可續跑不丟 job |
| PG20 | `pytest -q tests/contracts/test_provider_access_basis.py` | enabled provider 皆有 access basis、ToS snapshot、rate policy、kill switch |
| PG21 | `pytest -q tests/contracts/test_amadeus_lcc_exclusion.py` | LCC 不得僅靠 Amadeus Self-Service 升 CONFIRMED |
| PG22 | `pytest -q tests/policy/test_policy_ttl_event_time.py` | JP/TW/KR/CN event-time、TTL/watch window fixtures 全通過 |
| PG23 | `pytest -q tests/capacity/test_d1_scan_budget.py` | 單 invocation ≤50 D1 queries；critical query 有 index/query-plan |
| PG24 | `pytest -q tests/golden/test_jetstar_price_beat.py` | 台日 eligibility 全條件同時成立才 eligible |
| PG25 | `pytest -q tests/sources/test_source_registry_contract.py` | enabled source 皆有 market/language/access/fetch/terms/retention/kill-switch；ID 唯一 |
| PG26 | `pytest -q tests/sources/test_provenance_hash.py` | 每個 promotion/social/agency event 可回溯 observation + SHA-256 + observed_at |
| PG27 | `pytest -q tests/sources/test_promotion_cluster_dedup.py` | GC35：跨 Email/web/social 同活動只產 1 PromotionEvent，evidence 不遺失 |
| PG28 | `pytest -q tests/agency/test_clearance_intake.py` | GC34/43：seller/readback 狀態正確；匿名匯款永不 SELLER_CONFIRMED |
| PG29 | `pytest -q tests/email/test_auth_and_link_safety.py` | DKIM/SPF/DMARC/link-risk fixtures；GC36 不產 trusted fare |
| PG30 | `pytest -q tests/sources/test_social_retention_privacy.py` | 私人通知最小保存；刪除政策可執行；公開 repo 無 raw private content |
| PG31 | `pytest -q tests/sources/test_rate_terms_guard.py` | terms stale/access invalid → no dispatch；politeness/backoff/kill-switch 生效 |
| PG32 | `pytest -q tests/verification/test_event_to_offer_trace.py` | promotion/social/cached claim 無 live/seller readback 不得 CONFIRMED |
| PG33 | `pytest -q tests/sources/test_correction_deletion.py` | source edit/delete/withdraw 形成新 version/correction，不覆寫歷史 evidence |
| PG34 | `pytest -q tests/capacity/test_source_burst_degrade.py` | 高量 burst 可去重/降頻/quarantine；critical intake/outbox 不失效 |
| PG35 | `pytest -q tests/source_discovery/test_route_universe.py` | RouteUniverse diff 產生 onboarding candidates；不直接產 confirmed fare；GC40 PASS |
| PG36 | `pytest -q tests/sources/test_adaptive_schedule.py` | 固定 fixture 下 BOOST/KEEP/DOWNSHIFT/QUARANTINE deterministic；authority 不被 popularity 改寫 |

## 43.3 Gate completeness invariant

CI 必須另執行：

```text
assert production_gate_ids == {PG00..PG36}
assert len(production_gate_ids) == 37
assert every_gate_has_test_mapping == true
assert every_gate_has_acceptance_rule == true
assert every_applicable_gate_has_evidence_contract_before_production == true
```

任何 Gate 缺 test mapping、PASS 閾值或 Evidence Contract，狀態只能 `UNDEFINED/NOT_RUN`，不得手動標 PASS。

# 44. 主要風險與緩解 v1.3

| 風險 | 緩解 |
|---|---|
| 已含稅 offer 再加稅 | inclusion_state + dedupe key + PG17 |
| ACTIONABLE 狀態爆炸 | verification lifecycle + readiness facets |
| same PNR 被誤認全程保護 | typed protection + evidence + PG18 |
| Amadeus 空回誤判 LCC ghost | LCC exclusion + PG21 |
| Duffel 廣掃燒錢 | targeted only + pricing/search-to-book breaker |
| Cloudflare CPU 超限 | Cron dispatcher + bounded batch + PG19 |
| D1 全表掃描耗盡 | index + rows_read evidence + PG23 |
| D1 quota 讓 critical alert 失效 | critical reserve + PG12 |
| 日本稅重複／漏豁免 | event-time policy + dedupe + GC21–24 |
| 台灣機場費誤當 carrier fee | TW policy source-of-truth |
| KR 政策跨 2026-12-31 | watch window + RECHECK_REQUIRED |
| CN 文件誤套外國人規則 | Taiwan-resident gate + carrier document check |
| Jetstar Price Beat 誤報 | exact eligibility + PG24 |
| Team Tiger 過期券仍推薦 | booking/travel window + expiry facet |
| 外站漏 positioning/tail | liability ledger + cycle cost |
| 跳段後果過度簡化 | carrier-specific consequence classification |
| provider ToS/access 改變 | AccessBasis + terms snapshot + kill switch |
| 公開 Repo 洩密 | synthetic only + secret/history privacy scan |
| 社群連結腐爛 | observation snapshot/hash；不得支撐 policy gate |
| 官方促銷被誤當可買票 | event taxonomy + PG32 |
| 快取 deal API 被誤當 live | fare_freshness + requires_repricing + GC41 |
| Email 冒名/釣魚 | DKIM/SPF/DMARC + registrable-domain/link gate + PG29 |
| 旅行社匿名清艙詐騙 | seller verification + formal channel + PG28 |
| OpenChat/封閉群硬爬 | Android notification/manual forward only + PG30 |
| 新來源自動擴張成惡意網域 | onboarding review + access/terms gate + PG35 |
| source 轉貼量大污染排程 | Yield/Lead/duplicate metrics + PG36 |
| 同一促銷 100 來源重複 | PromotionEvent cluster + PG27 |
| source 刪文/改價後歷史被覆蓋 | immutable SourceObservation + correction chain + PG33 |
| 航空更名造成歷史斷裂 | airline alias graph；IATA/route continuity + GC44 |
| RouteUniverse 過期 | official route diff + status/last_seen + PG35 |
| 高量 burst 壓垮 parser/D1 | source admission control + batch + PG34 |
| Push source 又被高頻 polling | push_capable policy；scheduler 禁止重複 acquisition path |

# 45. 研究來源與證據分級 v1.3

```text
A = 政府／航空公司／機場／平台官方政策、條款、API、正式產品頁
B = 合作型 API/旅行社正式頁/官方產品文件/可重現之二級整理
C = PTT／Threads／Dcard／Reddit／FlyerTalk／部落格等 discovery 線索
```

C 類不得單獨決定文件資格、政策、票券順序、seller legitimacy 或 CONFIRMED fare。C 類進長期 corpus 前依 privacy policy 保存 `fetched_at + sha256 + redacted transcript`；來源刪除後按 retention policy 處理，不以失連補猜。

## 45.1 v1.3 新增／重基準之 A/B 來源

### RouteUniverse / source discovery

- JNTO — 台灣與日本直飛定期航班「航空情報」，2026-07-07 更新；官方頁並提醒另有包機與期間限定航班。  
  https://www.japan.travel/tw/tw/airline/
- 各航空公司 News/Press/Schedule opening、台灣民航局、台灣與日本機場公告：作 route supply signal；實際啟用 adapter 前逐站建立 SourceRegistry。

### Push-first / Email

- Google Flights — Track flights & prices；支援特定日期與 `Any dates` Email。  
  https://support.google.com/travel/answer/6235879
- Peach Newsletter — special offers / advance notice of sales。  
  https://www.flypeach.com/sg/lm/newsletter
- Peach FAQ — sale/campaign/schedule announcements 可由 newsletter 等渠道取得。  
  https://cs.flypeach.com/hc/en-us/articles/4659141519774
- Tigerair Taiwan — 官網與 newsletter，第一手促銷與動態。  
  https://www.tigerairtw.com/

### 社群正式介面

- Meta Threads API official Postman collection — `keyword_search`, `TOP/RECENT`, `KEYWORD/TAG`, `since/until`, OAuth scope `threads_keyword_search`。  
  https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api
- LINE Developers — LIFF apps currently not officially supported in OpenChat；OpenChat 不建立 LIFF 全網監聽假設。  
  https://developers.line.biz/en/docs/liff/overview/
- LINE Messaging API group chats — 只適用 OA 實際參與之一般 group/multi-person chat；不等於可讀任意 OpenChat。  
  https://developers.line.biz/en/docs/messaging-api/group-chats

### Cached broad discovery

- Aviasales / Travelpayouts Data API — 官方說明資料源自 Aviasales 使用者搜尋快取，Data API cache 保存 7 天，含 `get_special_offers`。  
  https://support.travelpayouts.com/hc/en-us/articles/203956163-Aviasales-Data-API
- Travelpayouts API rate limits — `v3/get_special_offers` 等有正式 RPM 限制；adapter 必須自我節流。  
  https://support.travelpayouts.com/hc/en-us/articles/4402565416594-API-rate-limits

### Airline identity migration

- Trinity Airways / T'way Air official notice — 2026-09-10 起以 Trinity Airways 名稱營運，IATA `TW` 與航班編號不變，舊訂位維持。  
  https://www.twayair.com/app/customerCenter/notice/retrieve/12584?langCode=zh-TW&regionCode=TW

## 45.2 v1.2 持續有效的 A/B 來源

- Taiwan MOTC — Airport Service Fee / 出境航空旅客機場服務費  
  https://www.motc.gov.tw/  
  https://motclaw.motc.gov.tw/
- Japan NTA — International Tourist Tax  
  https://www.nta.go.jp/english/taxes/indirect/tourist_tax.htm
- K-ETA temporary exemption notices  
  https://www.k-eta.go.kr/
- Korea e-Arrival Card  
  https://www.e-arrivalcard.go.kr/
- China NIA — Taiwan-resident document/transit official information  
  https://en.nia.gov.cn/
- ANA / JAL / China Airlines Conditions of Carriage  
  https://www.ana.co.jp/en/jp/guide/terms/int-conditions-of-carriage/  
  https://www.jal.co.jp/jp/en/inter/carriage/251128/index.html  
  https://www.china-airlines.com/us/en/terms-and-conditions/transportation-clauses
- Skyscanner developer Usage Guidelines / Live / Indicative  
  https://developers.skyscanner.net/docs/getting-started/usage-guidelines  
  https://developers.skyscanner.net/docs/flights-live-prices/overview  
  https://developers.skyscanner.net/docs/flights-indicative-prices/overview
- KAYAK Terms / Hacker Fare  
  https://www.kayak.com/terms-of-use  
  https://www.kayak.com/news/hacker-fare/
- Kiwi Fees / Guarantee  
  https://www.kiwi.com/en/pages/content/fees  
  https://www.kiwi.com/en/pages/guarantee
- Jetstar Price Beat  
  https://www.jetstar.com/us/en/price-beat-guarantee
- Team Tiger Terms  
  https://subscriptions.tigerairtw.com/documents/TermsAndConditions_zh.pdf
- Amadeus Self-Service / developer FAQ：LCC coverage restriction 持續作 PG21 依據，施工前 recheck 官方現況。  
  https://developers.amadeus.com/  
  https://amadeus4dev.github.io/developer-guides/faq/
- Duffel pricing  
  https://duffel.com/pricing
- Cloudflare Workers / D1 limits  
  https://developers.cloudflare.com/workers/platform/limits/  
  https://developers.cloudflare.com/d1/platform/limits/  
  https://developers.cloudflare.com/d1/platform/pricing/
- GitHub Actions billing  
  https://docs.github.com/en/billing/concepts/product-billing/github-actions

## 45.3 Agency / OTA SourceRegistry seed

兩份外部研究均指出旅行社臨期、獨家航空庫存與折扣碼是 v1.2 的實質缺口。v1.3 首批 seed 至少包含：

```text
Lion Travel
Colatour
Settour
LifeTour
ezTravel
ezfly
FunTime/other comparison only if access basis reviewed
Trip.com promotion/coupon pages
specialized ticket/charter agencies via partner intake
```

正式啟用前逐項重查 canonical domain、robots/terms、market、登入需求、抓取方法與 retention；外部研究中的一次性 campaign URL 只作 fixture/seed，不保證永久有效。

## 45.4 P0 SourceRegistry seed by airline/market

```text
TW origin: Tigerair / CI / BR / JX / AE
JP carriers/markets: Peach / Jetstar Japan / JAL / ANA / ZIPAIR
KR hubs: Trinity Airways(TW) / Jeju / Jin Air / Air Busan / Air Seoul / Aero K / Eastar
HK/MFM: Cathay / HK Express / Hong Kong Airlines / Air Macau / Greater Bay
CN hubs: Air China / China Eastern / Shanghai Airlines / China Southern / XiamenAir
regional: Scoot / AirAsia family / VietJet / Cebu Pacific
```

這是 source coverage seed，不代表全部都能以 API 或背景爬取。每一 source 必須先過 `PG25/PG31`。

## 45.5 C 類與二級 discovery seed

```text
PTT Japan_Travel / Aviation / Korea_Travel
Threads keyword search / high-value accounts
Dcard airfare/deal authors
FlyerTalk
Reddit approved API communities
TRAICY / Secret Flying / Japan fare blogs
LINE OpenChat public discovery + user notification sensor
Telegram authorized public channels
local route/news aggregators
```

任何第三方 source 的自述「即時、全網、官方資料」都不能提升 authority；需要自己的 reprice/readback。

## 45.6 外部研究快照之初始 adapter seed

下列為兩份外部研究在 2026-09-14 已實際開啟檢查的施工 seed；它們適合直接轉為 `sources.seed.json` 候選，但每個 adapter 在真正 `ENABLED` 前仍須由 `PG25/PG31` 重新確認 canonical URL、access basis 與條款。

| Source seed | 代表入口 | v1.3 定位 |
|---|---|---|
| Tigerair Taiwan Low-Fare / Special Offers | https://www.tigerairtw.com/ | P0 official promo / indicative |
| China Airlines Japan fare pages | https://flights.china-airlines.com/zh-tw/flights-to-japan | P0 official indicative |
| EVA Japan fare pages | https://flights.evaair.com/zh-tw/航班-飛往-日本 | P0 official indicative |
| STARLUX promotions | https://www.starlux-airlines.com/flights/en-us/promotions | P0 official promo |
| Peach | https://www.flypeach.com/en | P0 sale/news/newsletter |
| JAL Taiwan | https://www.jal.co.jp/flights/zh-tw/ | P0 official fare/news |
| ANA Taiwan deals | https://www.ana.co.jp/en/tw/plan-book/promotions/ana-deals-2026/ | P0 official promo |
| Trinity Airways | https://www.trinityairways.com | P0 KR hub / alias migrated from T'way |
| Jeju Air | https://www.jejuair.net/en/event/event.do | P0 KR hub promo |
| Cathay Pacific TW | https://www.cathaypacific.com/cx/en_TW.html | P1 protected-transfer baseline/promo |
| HK Express | https://www.hkexpress.com/ | P1 HKG hub promo |
| Lion Travel | https://event.liontravel.com/zh-tw/campaign/hotsale/earlybird | agency campaign seed |
| Colatour | https://www.colatour.com.tw/ | agency campaign/email seed |
| Settour | https://flight.settour.com.tw/ | agency campaign/search seed |
| LifeTour | https://www.lifetour.com.tw/ | agency campaign/clearance seed |
| Trip.com TW | https://tw.trip.com/flights | OTA discovery/checkout cross-check |
| PTT Japan_Travel | https://www.ptt.cc/bbs/Japan_Travel/ | C discovery |
| FlyerTalk | https://www.flyertalk.com/forum/index.php | external-origin/error-fare research |
| TRAICY | https://en.traicy.com/posts/category/airline/sale | JP sale discovery |
| AeroRoutes | https://www.aeroroutes.com/ | route supply signal |
| Secret Flying | https://www.secretflying.com/ | mistake-fare discovery only |

一次性 campaign URL 不寫死為永久 source identity；Registry 的 canonical source 與 observation URL 分開保存。

# 46. 控制 AI 施工命令 v1.3

施工基準改為 **v1.3**。v1.2、兩份外部來源研究與本輪網路查核均只作歷史／證據輸入；不得繞過 v1.3 的 Source Registry、AccessBasis、Evidence Contract 與 readiness policy。

最短 critical path：

```text
Phase 0 schema/invariants/GC/PG contract
→ Phase 1 durable core + evidence/provenance
→ Phase 2 official/email/RouteUniverse source mesh
→ Phase 3 agency/community/clearance + clustering
→ Phase 4 direct/split/open-jaw all-in cost
→ Phase 5 bounded strategy + adaptive source scheduling
→ Phase 6 KR/HKG/MFM transfer
→ Phase 7 event-time policy + source terms TTL
→ Phase 8 foreign-origin/four-leg
→ Phase 9 targeted multi-provider verification + event-to-offer trace
→ Phase 10 explainable alerts + source provenance
→ Phase 11 shadow acceptance
→ Phase 12 production gate
```

硬規則：

```text
CHAT/CONTROLLER 能直接完成 → 直接完成
不要先做 UI 漂亮化
不要先做 AI scoring
不要做全網通用登入爬蟲
Push-first source 不重複高頻 poll
能 conditional HTTP / RSS / Email 就不要 Playwright
不要把 Win11 變 canonical DB/scheduler/router
不要把社群/EDM/快取 fare 當 bookable truth
不要把 Travelpayouts/Google email/Skyscanner indicative 單獨升 CONFIRMED
不要把 OpenChat 當可任意 API 監聽
不要把 Amadeus 當 LCC 真值
不要讓 Cron 做重 parse/browser work
不要在 cost_complete=false 時排「最便宜」
不要持久化 ACTIONABLE 狀態
不要讓 source popularity 改寫 VerificationAuthority
不要讓 access/terms stale 的 adapter 繼續 dispatch
不要讓無 evidence contract 的 Gate PASS
```

每個來源 adapter 上線流程：

```text
source discovery/seed
→ access basis + terms + privacy review
→ SourceRegistry entry
→ parser/adapter contract test
→ Shadow
→ provenance/hash test
→ rate/budget test
→ ENABLED
```

每 Phase：

```text
implementation
→ deterministic tests
→ relevant GC
→ capacity/source/provider readback where applicable
→ PG Evidence Contract
→ PASS
→ next phase
```

# 47. 最終工程裁決 v1.3

v1.3 保留 v1.2 的完整旅程成本、文件、轉機保護與驗價治理，新增的是「如何持續、合法、低成本地找到好情報」這個 Production 缺口。

系統現在必須同時回答十二個問題：

```text
1. 現在哪個台日方案真的便宜？
2. 這個情報最早在哪個 source、什麼時間被發現？
3. Source access basis 是否合法、條款與 retention 是否仍新鮮？
4. 這是促銷、快取價、社群 claim、旅行社庫存，還是可購買 offer？
5. 同一活動是否已跨 Email/官網/社群正確聚類，而不是重複洗版？
6. 旅行社賣方與庫存能否回讀，還是只有匿名截圖/私訊匯款？
7. Offer 已含哪些稅費，還缺哪些，會不會重複算？
8. 分票／轉機實際受到哪一種保護？
9. 文件與政策在實際旅行事件當天仍有效嗎？
10. 外站／四腿票把定位、尾段與 liability 算完還划算嗎？
11. 這個價由什麼 authority 在什麼時間重現？
12. 現在是否 ACTIONABLE；若不是，卡在哪個 readiness facet？
```

來源網的長期成功指標不是抓取量，而是：

```text
verified unique deal yield
first-source-win rate
median lead advantage
low ghost rate
low duplicate acquisition cost
high provenance completeness
zero unauthorized access paths
zero social/cached-only false CONFIRMED
```

截至本版：

```text
SPEC = CONSTRUCTION_BASELINE_V1.3
SOURCE_MESH = SPECIFIED_NOT_YET_PROVEN
IMPLEMENTATION = NOT_YET_PROVEN
PRODUCTION_READY = NO
PROJECT_CONTROL_PLANE = UNREGISTERED_FOR_THIS_HUMAN_NAME
```

只有所有 applicable `PG00–PG36` 以 Evidence Contract 可重現 PASS，Shadow Acceptance 通過，且 source/provider access/terms 在部署時重新讀回有效，才能改成 Production Ready。
