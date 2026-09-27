---
name: project-third-party-notices-zh-tw
description: 第三方署名與合規聲明
metadata:
  version: "1.0.0"
  lang: "zh-TW"
---

# 第三方聲明

本文記錄隨附及由作業系統提供的第三方元件,原始碼相關記錄,以及發行審查的限制.

## 多語言

[English](../THIRD_PARTY_NOTICES.md) | [简体中文](../zh-CN/THIRD_PARTY_NOTICES.md) | **繁體中文(台灣)** | [繁體中文(香港)](../zh-HK/THIRD_PARTY_NOTICES.md) | [हिन्दी](../hi/THIRD_PARTY_NOTICES.md) | [Español](../es/THIRD_PARTY_NOTICES.md) | [العربية](../ar/THIRD_PARTY_NOTICES.md) | [Français](../fr/THIRD_PARTY_NOTICES.md)

## 文件

- 專案概覽:[README](README.md)

- 設計考量:[DESIGN](DESIGN.md)

- 發行歷史:[LOG](LOG.md)

- 第三方聲明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 第三方聲明

下表列出本文既有記錄中的元件及原始碼相關主張.[dependencies.lock.json][local-link-001] 記錄了七項隨附的第三方可散布產物在本機計算的 SHA-256;從儲存庫根目錄執行 `python3 tools/verify_dependencies/verify_dependencies.py`,可離線比對工作目錄中的位元組.這項檢查無法確認上游身分,原始授權條款或發行合規性.本文不主張曾在新的日期完成上游授權或散布審查.散布前須依實際發行產物核實所記版本,原始授權文本,版權,適用的原始碼提供義務,以及任何分離分析.此表不代表發行已獲核准.

| 元件/資源 | 版本/雜湊 | 來源 | 記錄的授權 | 用途 | 出處標示/原始授權路徑 | 待審查的發行義務 | 驗證日期 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0, per bundled license | 隨附的 frps 可執行檔 | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | 保留隨附的 Apache-2.0 授權並檢查發佈時的 NOTICE 義務 | Repository artifact hash verified; upstream identity pending |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT, per bundled license | 隨附的 Lucky 可執行檔 | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | 保留隨附的 MIT 版權與授權聲明 | Repository artifact hash verified; upstream identity pending |
| sing-box | `v1.13.14`;修訂版 `25a600db24f7680ad9806ce5427bd0ab8afe1114`;執行檔 SHA-256 `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL 第 3 版或更新版本,另有上游名稱條件(依聲明所載) | 由 anytls 和 proxy 共用的隨附執行檔 | [上游聲明][local-link-002];[GPL 完整文本][local-link-003] | 對應原始碼及名稱條件;審查[已記錄的原始碼連結][local-link-004]及[決策][local-link-005] | 未記錄;散布前重新驗證 |
| LibreSpeed | 先前記錄為 `v6.2.1` | [LibreSpeed](https://github.com/librespeed/speedtest) | 先前記錄為 LGPL-3.0 | 隨附的瀏覽器引擎 | 此處未記錄版權;[原始 LGPL 文本][local-link-006]及[GPL 文本][local-link-007] | 審查程式庫組合及原始碼可取得性 | 未記錄;散布前重新驗證 |
| qrcode-generator | `js2.0.4`;修訂版 `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | 先前記錄為 MIT | 隨附的用戶端 QR 程式庫 | [原始 MIT 文本][local-link-008] | 保留必要的版權與授權聲明 | 未記錄;散布前重新驗證 |
| iperf3 | 發行版套件;未鎖定版本 | [ESnet/iperf](https://github.com/esnet/iperf) | 先前記錄為 BSD-3-Clause | 作為獨立的作業系統程式呼叫;此處不重新散布 | 未記錄版權;原始授權由作業系統套件提供 | 若日後隨附或重新散布,重新評估 | 未記錄;散布前重新驗證 |

既有專案記錄將本專案標為 GPL-3.0([LICENSE][local-link-009]),理由是重新散布採用 GPL 的 sing-box 執行檔;[決策][local-link-010]保留其理由及否決的替代方案.先前記錄稱 `vps-webserver` 上游為 Apache-2.0,在此以 GPL-3.0 重新散布.這些是歷史專案主張,不是新的法律認定;發行前仍須審查義務與相容性.

沒有第三方 Python 套件.`src/web/app.py` 使用標準函式庫,因此沒有 Python 套件鎖定檔.上述隨附產物鎖定檔不鎖定由作業系統提供的 Python,iperf3 或其他系統套件:其版本和安全更新由目標 Debian/Ubuntu 發行版的套件渠道管理.安裝程式不選擇精確的套件版本或儲存庫快照;完整可重現的系統相依套件集合仍未解決(見[重建需求][local-link-011]).

---

## sing-box

本儲存庫以 `third_party/sing-box/sing-box` 路徑重新散布 sing-box 執行檔.先前專案記錄曾主張其上游發行身分,本次本機雜湊稽核並未獨立重新查證.安裝路徑為 `/usr/local/bin/sing-box-vps-server`.

- 元件:`sing-box`
- 上游專案:https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- 版本:`v1.13.14`
- 原始碼修訂版:`25a600db24f7680ad9806ce5427bd0ab8afe1114`
- 散布產物:`sing-box-1.13.14-linux-amd64.tar.gz`
- 儲存庫執行檔 SHA-256:`68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- 授權:GNU GPL 第 3 版或其後續版本,另加上游的名稱/關聯條件;見 [`third_party/sing-box/LICENSE`][local-link-012]

先前專案記錄稱已與上游 Release 壓縮檔逐位元組比對.本次稽核只驗證儲存庫執行檔的 SHA-256;是否等同發行產物仍需獨立比對上游.

### 對應原始碼

先前專案記錄為所聲稱的發行版本列出下列對應原始碼連結;本次稽核未核實其內容是否對應儲存庫執行檔.重新散布前須確認對應關係和原始碼提供義務:

- 標籤原始碼樹:https://github.com/SagerNet/sing-box/tree/v1.13.14
- 精確原始碼修訂版:https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- 原始碼壓縮檔:https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

先前專案記錄引用的上游 Release 壓縮檔:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

本專案為獨立專案,與 sing-box 或 SagerNet 作者並無隸屬關係,亦未獲其背書.

---

## LibreSpeed

瀏覽器測速使用隨附的 LibreSpeed 用戶端引擎.本次稽核並未獨立驗證所記版本及其與上游的等同性.

- 元件:LibreSpeed 用戶端引擎 — `static/third_party/librespeed/speedtest.js`,`static/third_party/librespeed/speedtest_worker.js`
- 上游專案:https://github.com/librespeed/speedtest
- 版本:`v6.2.1`
- 授權:GNU LGPL 第 3 版;完整文本見 [`static/licenses/LGPL-3.0.txt`][local-link-013]
- 先前專案記錄:兩個檔案曾被描述為與上游發行版逐位元組相同;本次稽核只核實本機工作目錄中的雜湊.尚未記錄精確的上游原始碼修訂版.

`static/speedtest-ui.js` 是本專案自行編寫的銜接程式碼,不屬於 LibreSpeed.`src/web/app.py` 的伺服器端端點(`/speedtest/garbage`,`/speedtest/empty`,`/speedtest/getip`)重新實作 LibreSpeed 文件中的用戶端/伺服器協定;屬原創程式碼,並非衍生自上游 PHP 後端.

先前記錄評估過 LGPL-3.0 與此 GPL-3.0 作品的組合;散布前須確認發行義務.

---

## qrcode-generator

主控台的 `/proxy` 頁面使用此隨附的用戶端程式庫,將各 anytls 位址的分享連結顯示成可掃描的 QR 圖碼.本次稽核並未獨立驗證所記版本及其與上游的等同性.

- 元件:`static/third_party/qrcode/qrcode.js`,`static/third_party/qrcode/qrcode-utf8.js`
- 上游專案:https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- 版本:`js2.0.4`
- 原始碼修訂版:`83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- 授權:MIT;完整文本見 [`static/licenses/MIT.txt`][local-link-014]
- 先前專案記錄:兩個檔案曾被描述為與上游 `js/dist/qrcode.js` 和 `js/dist/qrcode_UTF8.js` 逐位元組相同;本次稽核只核實本機工作目錄中的雜湊.

`static/qrcode-render.js` 是本專案自行編寫的銜接程式碼(尋找 `[data-qr-text]` 元素並填入繪製的 SVG),不屬於隨附程式庫.

先前記錄評估過 MIT 與此 GPL-3.0 作品的組合;散布前須確認聲明義務.

---

## iperf3

- 元件:`iperf3`
- 上游專案:https://github.com/esnet/iperf
- 授權:BSD 3-Clause
- 修改:否
- **未重新散布.** `iperf3` 由 `install.sh` 從作業系統套件庫安裝,並跨行程邊界將其作為獨立程式呼叫.本儲存庫沒有提供 iperf3 程式碼或執行檔;依先前記錄,與重新散布相關的 BSD 出處標示義務在此未觸發.若散布方式變更須重新評估.由於本專案執行時依賴它,故仍列於此.

---

## 隨附本作者其他專案的程式碼

並非第三方,但程式碼並非起源於本儲存庫,其來源對更新很重要,因此記錄如下:

- `src/web/app.py`, `static/speedtest-ui.js`,`static/style.css`,`static/visitors.js`,`tests/`,`deploy/install.sh`,`deploy/uninstall.sh`,`deploy/systemd/` — 來自 `vps-webserver` v0.4.1(上游為 Apache-2.0,在此以 GPL-3.0 重新授權).見 `config/upstream-version`.
- `deploy/anytls/setup-anytls.sh`,`third_party/sing-box/sing-box`,`third_party/sing-box/sing-box.version` — 來自 `Anytsl-Serve` v1.2.0(上游為 GPL-3.0).見 `deploy/anytls/.upstream-version`.

---

不包含第三方字型,圖示,影像,資料集或模型權重.服務執行時不發出對外請求;唯一可選的對外呼叫是安裝時查詢公開 IP,若失敗則僅顯示警告.

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
[local-link-011]: DESIGN.md#重建需求
[local-link-012]: ../../third_party/sing-box/LICENSE
[local-link-013]: ../../static/licenses/LGPL-3.0.txt
[local-link-014]: ../../static/licenses/MIT.txt
