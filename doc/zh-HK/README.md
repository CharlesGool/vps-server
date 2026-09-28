---
name: project-readme-zh-hk
description: 項目概覽與使用說明
metadata:
  version: "1.0.0"
  lang: "zh-HK"
---

# vps-server

## 多語言

[English](../../README.md) | [简体中文](../zh-CN/README.md) | [繁體中文(台灣)](../zh-TW/README.md) | **繁體中文(香港)** | [हिन्दी](../hi/README.md) | [Español](../es/README.md) | [العربية](../ar/README.md) | [Français](../fr/README.md)

## 文件

- 項目概覽:[README](README.md)

- 設計理據:[DESIGN](DESIGN.md)

- 發佈歷史:[LOG](LOG.md)

- 第三方聲明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 簡介

這套可按模組選用的工具供 Debian/Ubuntu VPS 使用:公開頁面檢查網頁連接埠能否連通,操作員控制台提供網速測試及連線紀錄,按需開啟的 iperf3 測試時段,以及 sing-box 代理節點.v2.0.0 亦包含四協定 `proxy` 模組,以及實驗性的 frps 和 Lucky 安裝程式.參閱[現況及驗收限制][local-link-001].

## 功能

- **讓任何人確認連通性.** 在 **80** 和
  **443** 連接埠提供刻意保持簡潔,毋須登入的頁面.把 IP 交給對方;若頁面能顯示,就代表對方所在位置能連到你的網頁連接埠.頁面只顯示對方的來源 IP,伺服器時鐘,以及所用的連接埠和協定,不透露其他主機資料.
- **透過瀏覽器量度吞吐量.** 控制台在持久保存的隨機高位連接埠上，以 LibreSpeed 引擎測試上載及下載速度。可使用管理員密碼，或已明確列入名單的私人區域網絡 IP 存取。只有以密碼登入的管理員可修改密碼與 IP 名單；公網 IP 不可加入。
- **按需用 iperf3 量度吞吐量及延遲.** 控制台開啟限時時段;`iperf3 -s` 只在期間執行,到期自動關閉.測試者可取得頻寬;Linux 用戶端亦可從 `mean_rtt` 在 `--json` 輸出中取得往返時間.此欄位來自核心的 `TCP_INFO`;不能讀取該資訊的用戶端(尤其是 Windows 上 Cygwin 的 iperf3)不會有此欄位.UDP 模式(`-u`)在各平台均提供抖動及封包遺失數據. 控制台分別顯示運行狀態及連接埠；測試時段關閉時可修改連接埠，新設定在服務重啟後仍有效。
- **記錄連線來源.** 透過 `/proc/net/tcp[6]` 讀取所有連接埠的每條入站 TCP 連線(不限 HTTP),存入 SQLite,保留最近 1000 條.
- **提供 anytls 代理。** sing-box 使用自簽憑證及 BBR。經驗證的 `/proxy` 頁面顯示節點狀態、流量及可編輯的連線設定；有私人局域網絡位址時，亦提供 Clash Meta for Android 一鍵匯入連結及 QR 碼。
- **提供 vmess/vless/trojan/shadowsocks 代理，可選任何組合。** 另一個 sing-box 程序與 anytls 共用隨附的執行檔。每種已安裝協定起初各有一個編號節點；控制台可為任何已安裝協定新增更多節點，也可逐個刪除。每個節點都有以 GiB 為單位的流量上限、分開的連線與限制編輯功能、隨機重設控件，以及相同的局域網絡 Clash Meta 匯入選項。匯入 URL 含有不透明權杖；節點連線設定或名稱改變後，舊連結即失效。公開連接埠不提供代理設定。 新增節點可手動填寫憑據，留空則隨機產生；TLS 節點的 SNI 預設為 `www.bing.com`。節點頁面列出主機網卡及 Tailscale 位址。

web,iperf3,anytls,proxy,frps 和 Lucky 六個模組均可於安裝時選用.frps 和 Lucky 仍屬實驗性模組;本版本尚未在真實主機完成其行為驗收.

**不屬於目標:**不提供 ACME 或網域名稱(443 刻意使用自簽憑證);不持續執行 iperf3;不提供反向代理或容器;公開頁面絕不披露主機名稱,核心,運行時間,服務清單或代理參數.本項目不取代 `vps-webserver` 或 `Anytsl-Serve`;兩者維持獨立維護,其程式碼在此以隨附副本形式提供,並非納入取代.

## 要求

- 作業系統:Debian 11+ 或 Ubuntu 20.04+,systemd;以 root 身份執行
- 執行環境:Python 3.9+(發行版的 `python3` 已足夠,無須安裝 Python 相依套件)
- 架構:web 和 iperf3 模組支援任何架構;anytls,proxy,frps 和 Lucky **只支援 x86-64**,因為隨附的執行檔適用於 amd64
- web 模組如使用預設公開連接埠,80 和 443 **必須**空閒;安裝程式會拒絕安裝,而不會與 nginx,Apache,Caddy 或 `vps-webserver` 爭用
- 外部服務:執行時無須使用.安裝需要發行版套件鏡像站;可選的公開 IP 查詢可能會連線至外部服務.
- 最低要求為上述系統,執行環境,架構和空閒連接埠.沒有另行記錄建議硬件要求;約 150 MB 磁碟空間可容納隨附執行檔.

## 安裝

一行快速安裝(最新發佈標籤,不設定變數):

```bash
git clone --branch v2.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

逐步安裝及設定:

```bash
# 複製發佈標籤;預設分支可能包含尚未發佈的變更.
# 列出發佈標籤: `git ls-remote --tags https://github.com/CharlesGool/vps-server.git`
git clone --branch v2.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # 可選;每個變數都有可用預設值
bash deploy/install.sh
```

`deploy/install.sh` 會詢問要安裝的模組,介面語言,是否以密碼保護控制台,以及使用哪些連接埠.v2.0.0 標籤包含六個可選模組;frps 和 Lucky 屬實驗性模組.

**再次執行會原地升級.** 程式偵測既有安裝,讓操作員選擇保留設定,並只詢問舊版本未有的設定;每項附有預設值,按 Enter 即可接受.控制台密碼,持久保存的連接埠,憑證,訪客紀錄,anytls 節點憑證,以及所有已安裝代理協定的連接埠及憑證都會保留.如要重新回答設定問題,在升級提問時回答 `n`.

## 指引

### 快速開始

v2.0.0 將 Web 實作放在 `src/web/app.py`,安裝程式從 `deploy/` 執行.隨附的執行檔及授權聲明位於 `third_party/`;發佈中繼資料位於 `config/`.已安裝檔案仍平鋪於 `$PREFIX` 下;檢出目錄的結構調整不會遷移運行資料.新路徑已通過本機測試,但本版本尚未通過真實主機驗收.

```bash
bash deploy/install.sh                       # 互動式設定:使用瀏覽器內的臨時安裝精靈
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # 無人值守,不顯示提示
systemctl status vps-server-web              # 檢查服務是否運作
bash deploy/anytls/setup-anytls.sh status           # 如已安裝該模組,查看 anytls 節點詳情
bash deploy/proxy/setup-proxy.sh status             # 如已安裝該模組,查看代理節點詳情
```

然後從另一部機器執行:

```bash
curl -sS  http://<ip>/                     # 檢查明文 HTTP 連通性
curl -sSk https://<ip>/                    # 檢查 TLS 連通性(自簽憑證)
iperf3 -c <ip> -p 5201 --json              # 只在測試時段開啟時使用
```

### 驗證運作

執行 `bash deploy/install.sh` 後,應看到列出各已安裝模組及連接埠的摘要.然後:

- `systemctl status vps-server-web` 顯示 `active (running)`.
- 從**另一部機器**開啟 `http://<ip>/`,應見標題為"Reachable"的頁面及自己的公開 IP.接受憑證警告後開啟 `https://<ip>/`,應見相同頁面,協定一行顯示 HTTPS.
- 登入 `http://<ip>:<console port>/`,應見儀表板和 iperf3 控制項,時段處於關閉狀態.
- 開啟五分鐘時段後,從另一部機器執行 `iperf3 -c <ip> -p 5201 --json`,應取得吞吐量及 `mean_rtt`.五分鐘後同一指令無法連線,表示時段自動關閉,並非故障.
- 如安裝了 anytls:`systemctl status vps-server-anytls` 顯示 `active (running)`.
- 如安裝了 proxy:`systemctl status vps-server-proxy` 顯示 `active (running)`.

### 設定

每個變數都有可用預設值;`.env` 並非必要.主要設定:

| 變數 | 用途 | 預設值 | 必需 |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | 公開連通性頁面,明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公開連通性頁面,TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 是否提供公開頁面 | `1` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台連接埠;`0` 表示產生一次並保存 | `0` | 否 |
| `VPSSRV_AUTH` | 控制台必須以密碼登入 | `1` | 否 |
| `VPSSRV_IPERF_PORT` | 開啟 iperf3 時段時監聽的連接埠 | `5201` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台時段上限 | `60` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | 否 |

完整資料:[設定參考][local-link-002].

## 升級

升級時使用目前檢出版本，沿用原安裝目錄及模組選項重新執行安裝程式。在確認升級後的服務及控制台正常前，保留持久資料備份。

## 移除

以 root 身份從安裝程式的 checkout 執行,使用安裝時相同的 `PREFIX` 和 `SERVICE_NAME` 值(安裝摘要會列印準確移除指令).移除模組和服務單位,但**保留
資料**於 `$PREFIX` 內供日後重新安裝:

```bash
KEEP_DATA=1 bash deploy/uninstall.sh
```

移除模組並**連資料一併刪除**(包括 `$PREFIX` 內的訪客紀錄,控制台密碼,儲存的連接埠及憑證):

```bash
bash deploy/uninstall.sh
```

兩種模式都會在已安裝時移除 anytls/proxy 服務及其獨立模組設定.`KEEP_DATA=1` 只保留 `$PREFIX`,不保留這些模組設定.

## 致謝

瀏覽器測試使用 [LibreSpeed](https://github.com/librespeed/speedtest);QR 碼使用
[qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator);隨附代理核心為
[sing-box](https://github.com/SagerNet/sing-box). 實驗性模組隨附
[frp](https://github.com/fatedier/frp) 和
[Lucky](https://github.com/gdy666/lucky). 組件清單及原始授權文件路徑見[第三方聲明][local-link-003].

## 授權條款

項目授權:GPL-3.0(SPDX:`GPL-3.0-only`);完整條文見 [LICENSE][local-link-004].歷史上的組合理由見[決策][local-link-005].隨附組件,其原始授權,已核實的檔案來源及餘下法律審查限制見 [THIRD_PARTY_NOTICES.md][local-link-006].

本項目與 sing-box/SagerNet 或 LibreSpeed 並無從屬關係,也沒有獲其認可.

[local-link-001]: LOG.md#目前狀態與驗收限制
[local-link-002]: DESIGN.md#設定參考
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#決策
[local-link-006]: THIRD_PARTY_NOTICES.md
