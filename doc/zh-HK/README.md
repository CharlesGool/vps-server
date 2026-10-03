---
name: project-readme-zh-hk
description: 項目概覽與使用說明
metadata:
  version: "1.0.0"
  lang: "zh-HK"
---

# vps-server

## 多語言

[简体中文](../../README.md) | [English](../en/README.md) | [繁體中文(台灣)](../zh-TW/README.md) | **繁體中文(香港)** | [हिन्दी](../hi/README.md) | [Español](../es/README.md) | [العربية](../ar/README.md) | [Français](../fr/README.md)

## 文件

- 項目概覽:[README](README.md)

- 設計理據:[DESIGN](DESIGN.md)

- 項目狀態: [LOG](LOG.md)
- 歷史記錄: [HISTORY](HISTORY.md)
- 變更記錄: [CHANGELOG](CHANGELOG.md)
- 提交記錄: [COMMITS](COMMITS.md)

- 第三方聲明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 簡介

這套可按模組選用的工具供 Debian/Ubuntu VPS 使用:公開頁面檢查網頁連接埠能否連通,操作員控制台提供網速測試及連線紀錄,按需開啟的 iperf3 測試時段,以及 sing-box 代理節點.v5.0.0 包含受管理節點,流量政策,私人 IP 免密存取,獨立的 HTTP/HTTPS 開關,FRPS/本機 FRPC 管理,Lucky 安裝入口及直接執行的安裝程式.版本範圍及檢查結果見[變更記錄][local-link-001].

## 功能

- **讓任何人確認連通性.** 在 **80** 和
  **443** 連接埠提供刻意保持簡潔,毋須登入的頁面.把 IP 交給對方;若頁面能顯示,就代表對方所在位置能連到你的網頁連接埠.頁面只顯示對方的來源 IP,伺服器時鐘,以及所用的連接埠和協定,不透露其他主機資料.
- **透過瀏覽器量度吞吐量.** 控制台在持久保存的隨機高位連接埠上,以 LibreSpeed 引擎測試上載及下載速度.可使用管理員密碼,或已明確列入名單的私人區域網絡 IP 存取.登入頁一直顯示 IP 免密按鈕;未獲准的訪客會被引導以密碼登入,再到存取設定新增私人 IP.安全設定須經近期管理員密碼驗證才顯示 IP 名單或接受修改.名單只接受單一私人 IPv4 或唯一本地 IPv6 位址,並可單獨停用 IP 免密而保留名單.修改密碼會使現有工作階段失效. 一般設定頁可直接調整外觀及語言;安全設定的管理員密碼驗證過期後須重新驗證.
- **按需用 iperf3 量度吞吐量及延遲.** 控制台開啟限時時段;`iperf3 -s` 只在期間執行,到期自動關閉.測試者可取得頻寬;Linux 用戶端亦可從 `mean_rtt` 在 `--json` 輸出中取得往返時間.此欄位來自核心的 `TCP_INFO`;不能讀取該資訊的用戶端(尤其是 Windows 上 Cygwin 的 iperf3)不會有此欄位.UDP 模式(`-u`)在各平台均提供抖動及封包遺失數據. 控制台分別顯示運行狀態及連接埠;測試時段關閉時可修改連接埠,新設定在服務重啟後仍有效.
- **記錄連線來源.** 透過 `/proc/net/tcp[6]` 讀取所有連接埠的每條入站 TCP 連線(不限 HTTP),存入 SQLite,保留最近 1000 條.
- **提供 anytls 代理.** sing-box 使用自簽憑證及 BBR.經驗證的 `/proxy` 頁面顯示節點狀態,流量及可編輯的連線設定;有私人局域網絡位址時,亦提供 Clash Meta for Android 一鍵匯入連結及 QR 碼. 訂閱 URL 亦可複製.
- **提供 vmess/vless/trojan/shadowsocks 代理,可選任何組合.** 另一個 sing-box 程序與 anytls 共用隨附的執行檔.每種已安裝協定起初各有一個編號節點;控制台可為任何已安裝協定新增更多節點,也可逐個刪除.每個節點都有以 GiB 為單位的流量上限,分開的連線與限制編輯功能,隨機重設控件,以及相同的局域網絡 Clash Meta 匯入選項.匯入 URL 含有不透明權杖;節點連線設定或名稱改變後,舊連結即失效.公開連接埠不提供代理設定. 新增節點可手動填寫密碼或協定所需的金鑰/UUID,留空則隨機產生;TLS 節點的 SNI 預設為 `www.bing.com`.節點頁面列出主機網卡及 Tailscale 位址. 每個節點亦可分別設定上載及下載的 Mbps 限速.達到 GiB 數據上限後,可選擇雙向限速 1 Mbps 或停止使用;按自訂日數,月數或年數重設週期數據.亦可設定可選有效期,到期後停止使用. 亦可複製局域網絡訂閱連結.

首次安裝預設只安裝 Web 控制台.`VPSSRV_MODULES` 可選擇 web,iperf3,anytls,proxy,frps 和 Lucky;其他模組亦可稍後從控制台安裝.FRPC 作為獨立的本機客戶端功能安裝.

經過身份驗證的 FRPS 頁面顯示本機服務狀態,網卡地址和連接設置;令牌及端口在用户要求顯示前保持遮蔽.FRPS 端口和令牌可直接編輯,服務可開啓或關閉.獨立的 FRPC 頁面以卡片列出本機客户端實例,遮蔽目標 IP,並根據已建立的 TCP 套接字顯示連接狀態.“測試連接”會使用保存的服務器地址,端口和令牌另行執行一次 FRPC 登錄.實例頁面按需顯示 IP 或令牌,編輯前也會列出每條 TCP/UDP 代理的類型,本地 IP,本地端口和遠程端口.保存後留在同一實例頁面,驗證配置文件,失敗時恢復原配置.這些 FRP 操作使用已登錄會話;修改密碼,IP 免密等安全設置操作才要求最近一次管理員密碼驗證.字段編輯器只處理簡單的令牌認證 TCP/UDP 配置,不會修改其無法表示的 FRPC TOML.此控制枱不監測其他設備上的 FRPC 實例.模塊頁面分別檢查本機 FRPC 可執行文件和 `frpc@.service` 模板,而不是用是否存在實例配置判斷安裝狀態.缺少其中任一文件時提供“安裝”.安裝使用經過校驗和驗證的 FRPC v0.71.0 發行資源,不會自行建立連接或監聽端口.模塊日誌記錄下載和驗證結果.離線安裝時,先下載 [frpc-0.71.0-linux-amd64](https://github.com/CharlesGool/vps-server/releases/download/v4.0.0/frpc-0.71.0-linux-amd64) (16,593,080 字節;SHA-256:`f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`),放到 `~/apps/vps-server/vendor/frp/frpc`,再選擇“安裝”.安裝任務對下載或手動放入的文件執行相同的摘要校驗.卸載時會停止本機 FRPC 實例,在 `data/` 下備份其配置,並保留配置文件供日後重新安裝.

**不屬於目標:**不提供 ACME 或網域名稱(443 刻意使用自簽憑證);不持續執行 iperf3;不提供反向代理或容器;公開頁面絕不披露主機名稱,核心,運行時間,服務清單或代理參數.本項目不取代 `vps-webserver` 或 `Anytsl-Serve`;兩者維持獨立維護,其程式碼在此以隨附副本形式提供,並非納入取代.

## 要求

- 作業系統:Debian 11+ 或 Ubuntu 20.04+,systemd;以 root 身份執行
- 執行環境:Python 3.9+(發行版的 `python3` 已足夠,無須安裝 Python 相依套件)
- 架構:web 和 iperf3 模組支援任何架構;anytls,proxy,frps 和 Lucky **只支援 x86-64**,因為隨附的執行檔適用於 amd64
- web 模組如使用預設公開連接埠,80 和 443 **必須**空閒;安裝程式會拒絕安裝,而不會與 nginx,Apache,Caddy 或 `vps-webserver` 爭用
- 外部服務:運行期間不需要.安裝需要發行版套件鏡像;節點摘要只使用網絡介面位址及可用的 Tailscale 位址,不對外查詢公網 IP.
- 最低要求為上述系統,執行環境,架構和空閒連接埠.沒有另行記錄建議硬件要求;約 150 MB 磁碟空間可容納隨附執行檔.

## 安裝

### 快速安裝

以 root 身份執行;預設只安裝 Web 控制台,並在終端列印隨機管理連接埠及密碼.

```bash
git clone --branch v5.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

### 一般安裝

```bash
git clone --branch v5.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env  # 選用:按註解設定覆蓋值
bash deploy/install.sh
```

`PREFIX` 預設為 `/root/apps/vps-server`.首次安裝毋須瀏覽器設定精靈.可用 `VPSSRV_MODULES=web,iperf3,anytls,proxy,frps,lucky` 明確選擇服務端模組;省略時只安裝 Web.安裝後可在 Settings → Modules 安裝或移除選用模組.公開 HTTP 和 HTTPS 頁面分別從 Home 啟用;管理控制台使用獨立連接埠.FRPC 只在需要本機客戶端時另行安裝;其下載資源及離線放置路徑見上文.

## 指引

### 快速開始

Web 實作位於 `src/web/`,靜態資源位於 `src/web/static/`,安裝程式位於 `deploy/`.隨附執行檔及授權記錄位於 `third_party/`;發行中繼資料位於 `config/`.安裝目錄仍沿用既有平鋪佈局;更新原始碼佈局不會遷移其中的運行資料.

```bash
bash deploy/install.sh                       # 互動式設定:使用瀏覽器內的臨時安裝精靈
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # 明確選擇 Web 與 iperf3
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
| `VPSSRV_PUBLIC_ENABLE` | 首次安裝是否提供公開頁面;安裝後可在 Home 分別開關 HTTP/HTTPS | `0` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台連接埠;`0` 表示產生一次並保存 | `0` | 否 |
| `VPSSRV_AUTH` | 控制台必須以密碼登入 | `1` | 否 |
| `VPSSRV_IPERF_PORT` | 開啟 iperf3 時段時監聽的連接埠 | `5201` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台時段上限 | `60` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | 否 |

完整資料:[設定參考][local-link-002].

## 升級

升級時使用目前檢出版本,沿用原安裝目錄及模組選項重新執行安裝程式.在確認升級後的服務及控制台正常前,保留持久資料備份.

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

瀏覽器測試使用 [LibreSpeed](https://github.com/librespeed/speedtest) ;QR 碼使用
[qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) ;隨附代理核心為
[sing-box](https://github.com/SagerNet/sing-box). 實驗性模組隨附
[frp](https://github.com/fatedier/frp) 和
[Lucky](https://github.com/gdy666/lucky). 組件清單及原始授權文件路徑見[第三方聲明][local-link-003].

## 授權條款

項目授權:GPL-3.0(SPDX:`GPL-3.0-only`);完整條文見 [LICENSE][local-link-004].歷史上的組合理由見[決策][local-link-005].隨附組件,其原始授權,已核實的檔案來源及餘下法律審查限制見 [THIRD_PARTY_NOTICES.md][local-link-006].

本項目與 sing-box/SagerNet 或 LibreSpeed 並無從屬關係,也沒有獲其認可.

[local-link-001]: CHANGELOG.md
[local-link-002]: DESIGN.md#設定參考
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#決策
[local-link-006]: THIRD_PARTY_NOTICES.md
