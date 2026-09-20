# 第三方聲明

[English](../THIRD_PARTY_NOTICES.md) | [简体中文](../zh_cn/THIRD_PARTY_NOTICES.md) | **繁體中文** | [繁體中文（香港）](../zh_hk/THIRD_PARTY_NOTICES.md) | [हिन्दी](../hi/THIRD_PARTY_NOTICES.md) | [Español](../es/THIRD_PARTY_NOTICES.md) | [العربية](../ar/THIRD_PARTY_NOTICES.md) | [Français](../fr/THIRD_PARTY_NOTICES.md)

## 文件說明

- 專案概覽：[README](README.md)
- 設計理念：[DESIGN](DESIGN.md)
- 版本歷史：[CHANGELOG](CHANGELOG.md)
- 目前狀態：[STATUS](STATUS.md)
- 需求清單：[BACKLOG](BACKLOG.md)
- 被否決的方案：[DECISIONS](DECISIONS.md)

> 譯自 `THIRD_PARTY_NOTICES.md`（v1.1.1）。如有衝突，以英文版為準；以英文版和各授權條款原始文本為準。

本專案本身採用 GPL-3.0 授權（見 [`LICENSE`](../LICENSE)）。之所以是 GPL-3.0 而不是更寬鬆的授權，是因為本專案重新散布了 sing-box 執行檔，而 sing-box 本身是 GPL-3.0，合併作品也必須跟著採用 GPL-3.0。從 `vps-webserver` 引入的程式碼，其上游是 Apache-2.0，在此以 GPL-3.0 重新散布——Apache-2.0 允許這樣做，反過來則不允許。

本專案沒有第三方 Python 套件。`app.py` 只使用標準函式庫，因此沒有需要稽核的鎖定檔（lockfile），也沒有需要持續修補的相依項目。

---

## sing-box

本儲存庫在儲存庫根目錄以 `sing-box` 之名重新散布未經修改的官方 sing-box 執行檔。它被安裝為 `/usr/local/bin/sing-box-vps-server`。

- 元件：`sing-box`
- 上游專案：https://github.com/SagerNet/sing-box
- 上游版權聲明：Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- 版本：`v1.13.14`
- 來源修訂版本：`25a600db24f7680ad9806ce5427bd0ab8afe1114`
- 發行的產物：`sing-box-1.13.14-linux-amd64.tar.gz`
- 儲存庫內執行檔的 SHA-256：`68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- 授權條款：GNU GPL 第 3 版或其後續任何版本，另加上游的名稱／關聯條件；見 [`LICENSES/sing-box-LICENSE`](../LICENSES/sing-box-LICENSE)

本儲存庫中的執行檔已與官方上游 Release 壓縮檔中的執行檔逐位元組比對，確認未經修改。

### 對應原始碼

這個確切二進位檔案的完整對應原始碼可免費取得，位於：

- 標籤原始碼樹：https://github.com/SagerNet/sing-box/tree/v1.13.14
- 確切來源修訂版本：https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- 原始碼壓縮檔：https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

此處使用的官方二進位 Release 為：

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

本專案為獨立專案，與 sing-box 或 SagerNet 作者無隸屬關係，亦未獲其背書。

---

## LibreSpeed

瀏覽器測速功能使用 LibreSpeed 自身的客戶端引擎，未經修改直接引入。

- 元件：LibreSpeed 客戶端引擎 — `static/speedtest.js`、`static/speedtest_worker.js`
- 上游專案：https://github.com/librespeed/speedtest
- 版本：`v6.2.1`
- 授權條款：GNU LGPL 第 3 版；完整文本見 [`static/licenses/LGPL-3.0.txt`](../static/licenses/LGPL-3.0.txt)
- 是否修改：否。這兩個檔案與上游發行版逐位元組相同。

`static/speedtest-ui.js` 是本專案自行編寫的膠合程式碼，不屬於 LibreSpeed 的一部分。`app.py` 中的伺服器端端點（`/speedtest/garbage`、`/speedtest/empty`、`/speedtest/getip`）重新實作了 LibreSpeed 記載的客戶端／伺服器介面約定；這些是原創程式碼，並非衍生自上游的 PHP 後端。

LGPL-3.0 允許與本 GPL-3.0 作品合併使用。

---

## iperf3

- 元件：`iperf3`
- 上游專案：https://github.com/esnet/iperf
- 授權條款：BSD 3-Clause
- 是否修改：否
- **未重新散布。** `iperf3` 是由 `install.sh` 從作業系統的套件庫安裝，並以跨處理程序邊界的獨立程式方式呼叫。本儲存庫並未內附任何 iperf3 程式碼或二進位檔案，因此附屬於「重新散布」行為的 BSD 標示義務在此並未被觸發。之所以仍將其列出，是因為本專案在執行期相依於它，讀者應當知道它的來源。

---

## 引自本作者自己其他專案的程式碼

不算第三方，但在此記錄，因為這些程式碼並非源自本儲存庫，其來源對於後續更新而言很重要：

- `app.py`、`static/speedtest-ui.js`、`static/style.css`、`static/visitors.js`、`tests/`、`install.sh`、`uninstall.sh`、`systemd/` — 來自 `vps-webserver` v0.4.1（上游為 Apache-2.0，在此重新授權為 GPL-3.0）。見 `.upstream-version`。
- `anytls/setup-anytls.sh`、`sing-box`、`anytls/sing-box.version` — 來自 `Anytsl-Serve` v1.2.0（上游為 GPL-3.0）。見 `anytls/.upstream-version`。

---

本專案不包含任何第三方字型、圖示、影像、資料集或模型權重。服務在執行期不會發出任何對外請求；唯一的可選對外呼叫是安裝過程中的公網 IP 查詢，若失敗則降級為警告，不影響安裝。
