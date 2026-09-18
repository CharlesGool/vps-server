# vps-server

[English](../../README.md) | [简体中文](../zh_cn/README.md) | **繁體中文** | [繁體中文（香港）](../zh_hk/README.md) | [हिन्दी](../hi/README.md) | [Español](../es/README.md) | [العربية](../ar/README.md) | [Français](../fr/README.md)

## 文件說明

- 設計理念：[DESIGN](DESIGN.md)
- 版本歷史：[CHANGELOG](CHANGELOG.md)
- 目前狀態：[STATUS](STATUS.md)
- 需求清單：[BACKLOG](BACKLOG.md)
- 被否決的方案：[DECISIONS](DECISIONS.md)
- 第三方授權聲明：[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

> 譯自 `README.md`（v1.0.4）。如有衝突，以英文版為準。

在 Debian/Ubuntu VPS 上一鍵部署的整合套件：一個任何人都能連上、用來證明你這台 IP 的 web 埠可連通的公開頁面，一個受密碼保護、可測速並記錄連線的主控台，一個隨開隨用的 iperf3 視窗，以及一個 anytls 代理。

## 這個專案做什麼

- **向任何人證明可連通。** 在 **80** 和 **443** 埠上有一個刻意做得極簡、無需登入的頁面。把 IP 給對方,只要頁面能顯示出來,就代表你的 web 埠從對方那個位置是可連通的。它會回報對方的來源 IP、伺服器時鐘,以及對方是透過哪個埠、哪種協定連進來的——除此之外不透露主機的任何其他資訊。
- **從瀏覽器量測吞吐量。** 一個受密碼保護、位於固定隨機高位埠的主控台,使用 LibreSpeed 引擎執行上傳／下載測試。
- **用 iperf3 隨需量測吞吐量與延遲。** 主控台會開啟一個限時視窗；`iperf3 -s` 只在視窗期間內執行,視窗到期就自動關閉。測試者可從 iperf3 取得頻寬數據,若是 Linux 客戶端,還能從其 `--json` 輸出裡的 `mean_rtt` 取得往返時間——這個欄位來自核心的 `TCP_INFO`,在讀不到它的客戶端上會缺失,特別是 Windows 上 Cygwin 版的 iperf3。UDP 模式(`-u`)在任何平台上都會額外提供抖動與丟包數據。
- **記錄誰連上了。** 任何埠上的每一筆進站 TCP 連線都會被記錄,不只是 HTTP——資料讀自 `/proc/net/tcp[6]`,儲存在 SQLite 裡,只保留最近 1000 筆。
- **提供 anytls 代理服務。** sing-box 搭配自簽憑證,並啟用 BBR。安裝此模組後,主控台會多出一頁,顯示節點是否在線,並提供其 Clash 設定條目與附一鍵複製按鈕的 `anytls://` 連結,把節點交給客戶端時不必再回到終端機操作。

web、iperf3、anytls 這三個模組各自可在安裝時選擇是否啟用。

**非目標:** 不提供 ACME 或網域名稱(443 刻意採用自簽憑證);不提供常駐運作的 iperf3;不提供反向代理或容器化;公開頁面絕不透露主機名稱、核心版本、開機時間、服務清單或代理參數。本專案不會取代 `vps-webserver` 或 `Anytsl-Serve`——這兩者仍各自獨立維護,其程式碼是以引入(vendored)方式收錄於此,而非被整併吸收。

## 系統需求

- 作業系統:Debian 11 以上或 Ubuntu 20.04 以上,systemd,以 root 身分執行
- 執行環境:Python 3.9 以上(發行版內建的 `python3` 即可——不需另外安裝任何 Python 依賴套件)
- 架構:web 與 iperf3 模組支援任意架構;anytls **僅限 x86-64**,因為收錄的 sing-box 執行檔是 amd64 版本
- 80 與 443 埠必須是空閒的——安裝程式會拒絕安裝,而不會與既有的 nginx、Apache、Caddy 或 `vps-webserver` 搶埠
- 外部服務:無。安裝只需要你的發行版套件鏡像來源。

## 安裝

一行指令快速安裝(最新發行版標籤,不使用任何設定變數):

```bash
git clone --branch v1.0.4 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash install.sh
```

逐步安裝,並可自訂設定:

```bash
# Always clone a tag, not the default branch — the branch tip may be mid-work.
# Latest release tag: git ls-remote --tags https://github.com/CharlesGool/vps-server.git
git clone --branch v1.0.4 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # optional — every variable has a working default
bash install.sh
```

`install.sh` 會詢問要安裝哪些模組、介面語言、是否為主控台加上密碼保護,以及要使用哪些埠。

**重新執行會就地升級。** 它會偵測既有的安裝,提議保留現有設定,並只詢問已安裝版本沒有的設定項——每一項都附有預設值,直接按 Enter 也是合法答案。主控台密碼、固定的埠號、憑證、訪客記錄以及 anytls 節點的憑證都會保留下來。若對升級提示回答 `n`,則會改為重新詢問所有設定。

## 快速開始

```bash
bash install.sh                              # interactive: modules, language, password, port
sudo VPSSRV_MODULES=web,iperf3 bash install.sh   # unattended, no prompts
systemctl status vps-server-web              # is it up
bash anytls/setup-anytls.sh status           # anytls node details, if that module is installed
```

接著在另一台機器上執行:

```bash
curl -sS  http://<ip>/                     # reachability over plain HTTP
curl -sSk https://<ip>/                    # ... and over TLS (self-signed)
iperf3 -c <ip> -p 5201 --json              # only while a window is open
```

## 驗證是否正常運作

執行 `bash install.sh` 後,你應該會看到一個摘要區塊,列出每個已安裝的模組及其埠號。接著:

- `systemctl status vps-server-web` 回報 `active (running)`。
- 從**另一台機器**開啟 `http://<ip>/`,會顯示一個標題為「Reachable」的頁面,並顯示你自己的公開 IP。開啟 `https://<ip>/`,在你接受憑證警告之後,會顯示同樣的頁面,且協定欄位顯示為 HTTPS。
- 登入 `http://<ip>:<console port>/` 會顯示儀表板,其中 iperf3 控制項可見,且視窗處於關閉狀態。
- 開啟一個 5 分鐘的視窗之後,從另一台機器執行 `iperf3 -c <ip> -p 5201 --json` 會回報一個吞吐量數值,並包含 `mean_rtt`。五分鐘後,同一條指令會連線失敗——這是視窗自行關閉的結果,不是故障。
- 若你安裝了 anytls:`systemctl status vps-server-anytls` 會回報 `active (running)`。

## 設定

每個變數都有可直接運作的預設值;`.env` 是可選的。以下是最關鍵的幾項:

| 變數 | 意義 | 預設值 | 是否必填 |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | 公開可連通性頁面,明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公開可連通性頁面,TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 是否提供公開頁面 | `1` | 否 |
| `VPSSRV_CONSOLE_PORT` | 主控台埠號;`0` 表示自動產生並記住 | `0` | 否 |
| `VPSSRV_AUTH` | 主控台是否需要密碼 | `1` | 否 |
| `VPSSRV_IPERF_PORT` | 已開啟的 iperf3 視窗所監聽的埠 | `5201` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 主控台不可超過的上限 | `60` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` | `en` | 否 |

完整參考:見 `DESIGN.md` → Configuration reference。

## 解除安裝

```bash
bash uninstall.sh              # removes whichever modules are installed, and the data
KEEP_DATA=1 bash uninstall.sh  # keeps the visitor database and the console password
```

## 授權

GPL-3.0。本專案重新散布了 sing-box 執行檔(GPL-3.0 授權),因此整體合併作品也採用 GPL-3.0——詳見 `LICENSE`。收錄的第三方元件、其版本,以及 GPL 要求提供的對應原始碼連結,記錄於 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

本專案與 sing-box/SagerNet 或 LibreSpeed 均無隸屬或背書關係。
