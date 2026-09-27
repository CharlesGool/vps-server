---
name: project-third-party-notices-zh-hk
description: 第三方署名與合規聲明
metadata:
  version: "1.0.0"
  lang: "zh-HK"
---

# 第三方聲明

本文記錄隨附及作業系統提供的第三方組件,原始碼相關聲稱和發佈審查限制.

## 多語言

[English](../THIRD_PARTY_NOTICES.md) | [简体中文](../zh-CN/THIRD_PARTY_NOTICES.md) | [繁體中文(台灣)](../zh-TW/THIRD_PARTY_NOTICES.md) | **繁體中文(香港)** | [हिन्दी](../hi/THIRD_PARTY_NOTICES.md) | [Español](../es/THIRD_PARTY_NOTICES.md) | [العربية](../ar/THIRD_PARTY_NOTICES.md) | [Français](../fr/THIRD_PARTY_NOTICES.md)

## 文件

- 項目概覽:[README](README.md)

- 設計理據:[DESIGN](DESIGN.md)

- 發佈歷史:[LOG](LOG.md)

- 第三方聲明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 第三方聲明

下表列出隨附組件及由作業系統提供的組件.七個隨附檔案在 [dependencies.lock.json][local-link-001] 記有檢出目錄中的 SHA-256;從儲存庫根目錄執行 `python3 tools/verify_dependencies/verify_dependencies.py`,可離線比較其位元組.2026-09-27,儲存庫中全部七個檔案均與所記上游發佈壓縮檔成員或標籤檔案位元組完全相同.隨附授權文件亦與下文核實的上游檔案相同.這些檢查確認檔案身份,不構成法律意見,亦無法建立完全可重現的系統依賴集合.

| 組件/資源 | 版本/雜湊 | 來源 | 已記錄授權 | 用途 | 署名/原始授權路徑 | 待審查發佈義務 | 核實日期 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0,依上游授權 | 隨附的 frps 可執行檔 | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | 保留隨附的 Apache-2.0 授權;官方二進制壓縮檔內沒有 NOTICE 文件 | 2026-09-27:壓縮檔,執行檔及授權文件相符 |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT,依上游授權 | 隨附的 Lucky 可執行檔 | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | 保留隨附的 MIT 版權與授權聲明 | 2026-09-27:壓縮檔,執行檔及授權文件相符 |
| sing-box | `v1.13.14`;修訂 `25a600db24f7680ad9806ce5427bd0ab8afe1114`;執行檔 SHA-256 `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL 第 3 版或更新版,加上上游命名條件(依聲明記錄) | anytls 和 proxy 共用的隨附執行檔 | [上游聲明][local-link-002];[GPL 全文][local-link-003] | 保留對應原始碼連結及上游名稱/關聯條件 | 2026-09-27:壓縮檔,執行檔,授權文件及標籤修訂相符 |
| LibreSpeed | `v6.2.1` | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0,依上游授權 | 隨附瀏覽器引擎 | [原始 LGPL 條文][local-link-006]及[GPL 條文][local-link-007] | 保留授權條文並確保上游原始碼可取得 | 2026-09-27:兩個標籤檔案及授權文件相符 |
| qrcode-generator | `js2.0.4`;修訂 `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT,依上游授權 | 隨附用戶端 QR 函式庫 | [原始 MIT 條文][local-link-008] | 保留規定的版權及授權聲明 | 2026-09-27:兩個標籤檔案及授權文件相符 |
| iperf3 | 發行版套件;未鎖定版本 | [ESnet/iperf](https://github.com/esnet/iperf) | 先前記錄為 BSD-3-Clause | 作為獨立的作業系統安裝程式呼叫;此處不再分發 | 版權未記錄;原始授權由作業系統套件提供 | 如日後隨附或再分發,須重新評估 | 未記錄;分發前須重新核實 |

現有項目紀錄指定本項目使用 GPL-3.0([LICENSE][local-link-009]),並將再分發 GPL 授權的 sing-box 執行檔列為原因;[決策][local-link-010]保留理由及遭否決的方案.舊紀錄稱 `vps-webserver` 上游使用 Apache-2.0,此處以 GPL-3.0 再分發.本清單記錄了為 v2.0.0 核實的檔案及條款;不提供獨立法律意見.

沒有第三方 Python 套件.`src/web/app.py` 使用標準函式庫,因此沒有 Python 套件鎖定檔.上述隨附檔案鎖定檔不鎖定作業系統提供的 Python,iperf3 或其他系統套件:其版本與安全更新由目標 Debian/Ubuntu 發行版的套件渠道管理.安裝程式不選定準確套件版本或儲存庫快照;完整可重現的系統相依套件封閉集合仍未解決(見[重現要求][local-link-011]).

---

## sing-box

本儲存庫以 `third_party/sing-box/sing-box` 再分發 sing-box 執行檔.2026-09-27,其位元組及隨附的上游授權文件與官方 v1.13.14 發佈壓縮檔相符.安裝位置為 `/usr/local/bin/sing-box-vps-server`.

- 組件:`sing-box`
- 上游項目:https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- 版本:`v1.13.14`
- 原始碼修訂:`25a600db24f7680ad9806ce5427bd0ab8afe1114`
- 分發檔案:`sing-box-1.13.14-linux-amd64.tar.gz`
- 儲存庫執行檔 SHA-256:`68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- 授權:GNU GPL 第 3 版或任何更新版本,另加上游名稱/關聯條件;見 [`third_party/sing-box/LICENSE`][local-link-012]

下載的發佈壓縮檔 SHA-256 為 `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697`.儲存庫內的執行檔及授權文件與解壓後對應檔案位元組完全相同.

### 對應原始碼

2026-09-27,v1.13.14 標籤指向原始碼修訂 `25a600db24f7680ad9806ce5427bd0ab8afe1114`.以下上游原始碼連結與隨附的執行檔一同提供:

- 標籤原始碼樹:https://github.com/SagerNet/sing-box/tree/v1.13.14
- 準確原始碼修訂:https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- 原始碼壓縮檔:https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

先前項目紀錄引用的上游 Release 壓縮檔:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

本項目為獨立項目,與 sing-box 或 SagerNet 作者並無從屬關係,也沒有獲其認可.

---

## LibreSpeed

瀏覽器網速測試使用隨附的 LibreSpeed 用戶端引擎.2026-09-27,兩個隨附的 JavaScript 檔案及授權文件與上游 v6.2.1 標籤檔案位元組完全相同.

- 組件:LibreSpeed 用戶端引擎 — `static/third_party/librespeed/speedtest.js`,`static/third_party/librespeed/speedtest_worker.js`
- 上游項目:https://github.com/librespeed/speedtest
- 版本:`v6.2.1`
- 授權:GNU LGPL 第 3 版;全文見 [`static/licenses/LGPL-3.0.txt`][local-link-013]
- 核實:兩個檔案及原始授權文件與 v6.2.1 標籤相符;本清單沒有記錄準確的標籤提交.

`static/speedtest-ui.js` 是本項目自有的銜接程式碼,並非 LibreSpeed 的一部分.`src/web/app.py` 內的伺服器端點(`/speedtest/garbage`,`/speedtest/empty`,`/speedtest/getip`)重新實作 LibreSpeed 文件所述用戶端/伺服器協定;屬原創程式碼,並非衍生自上游 PHP 後端.

LGPL-3.0 全文已隨附,並提供上游原始碼連結;本清單不提供關於組合使用的獨立法律意見.

---

## qrcode-generator

控制台的 `/proxy` 頁面使用這套隨附用戶端函式庫,把分享連結繪成可掃描 QR 碼.2026-09-27,兩個隨附的 JavaScript 檔案及原始授權文件與上游 js2.0.4 標籤檔案位元組完全相同.

- 組件:`static/third_party/qrcode/qrcode.js`,`static/third_party/qrcode/qrcode-utf8.js`
- 上游項目:https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- 版本:`js2.0.4`
- 原始碼修訂:`83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- 授權:MIT;全文見 [`static/licenses/MIT.txt`][local-link-014]
- 核實:兩個檔案與上游 `js/dist/qrcode.js` 和 `js/dist/qrcode_UTF8.js` 相符;原始 MIT 授權文件亦相符.

`static/qrcode-render.js` 是本項目自有的銜接程式碼(尋找 `[data-qr-text]` 元素,填入繪製的 SVG),並非隨附函式庫的一部分.

MIT 版權及授權聲明與用戶端函式庫一同隨附.

---

## iperf3

- 組件:`iperf3`
- 上游項目:https://github.com/esnet/iperf
- 授權:BSD 3-Clause
- 修改:沒有
- **不作再分發.** `iperf3` 由 `install.sh` 從作業系統套件庫安裝,並作為獨立程序呼叫.本儲存庫沒有提供 iperf3 程式碼或執行檔;先前紀錄因此認為再分發才適用的 BSD 署名要求在此不會觸發.分發方式如有變更須重新評估.由於本項目執行時依賴它,因此仍列於此.

---

## 隨附本作者其他項目的程式碼

並非第三方;但程式碼並非源自此儲存庫,其來源對更新甚為重要,故在此記錄:

- `src/web/app.py`, `static/speedtest-ui.js`,`static/style.css`,`static/visitors.js`,`tests/`,`deploy/install.sh`,`deploy/uninstall.sh`,`deploy/systemd/` — 來自 `vps-webserver` v0.4.1(上游 Apache-2.0,此處改以 GPL-3.0 授權).見 `config/upstream-version`.
- `deploy/anytls/setup-anytls.sh`,`third_party/sing-box/sing-box`,`third_party/sing-box/sing-box.version` — 來自 `Anytsl-Serve` v1.2.0(上游 GPL-3.0).見 `deploy/anytls/.upstream-version`.

---

不包含第三方字型,圖示,圖片,資料集或模型權重.服務執行時不會向外發送請求;唯一可選的對外呼叫是安裝期間查詢公開 IP,失敗時只顯示警告.

[local-link-001]: ../../config/dependencies.lock.json
[local-link-002]: ../../third_party/sing-box/LICENSE
[local-link-003]: ../../LICENSE
[local-link-004]: #對應原始碼
[local-link-005]: LOG.md#決策
[local-link-006]: ../../static/licenses/LGPL-3.0.txt
[local-link-007]: ../../LICENSE
[local-link-008]: ../../static/licenses/MIT.txt
[local-link-009]: ../../LICENSE
[local-link-010]: LOG.md#決策
[local-link-011]: DESIGN.md#重現要求
[local-link-012]: ../../third_party/sing-box/LICENSE
[local-link-013]: ../../static/licenses/LGPL-3.0.txt
[local-link-014]: ../../static/licenses/MIT.txt
