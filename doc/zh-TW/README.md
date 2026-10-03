---
name: project-readme-zh-tw
description: 專案概覽與使用說明
metadata:
  version: "1.0.0"
  lang: "zh-TW"
---

# vps-server

## 多語言

[简体中文](../../README.md) | [English](../en/README.md) | **繁體中文(台灣)** | [繁體中文(香港)](../zh-HK/README.md) | [हिन्दी](../hi/README.md) | [Español](../es/README.md) | [العربية](../ar/README.md) | [Français](../fr/README.md)

## 文件

- 專案概覽:[README](README.md)

- 設計考量:[DESIGN](DESIGN.md)

- 專案狀態: [LOG](LOG.md)
- 歷史記錄: [HISTORY](HISTORY.md)
- 變更紀錄: [CHANGELOG](CHANGELOG.md)
- 提交歷史: [COMMITS](COMMITS.md)

- 第三方聲明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 簡介

這是一套可選擇模組的 Debian/Ubuntu VPS 套件:提供檢查 Web 連接埠可達性的公開頁面,測速和連線記錄的操作者主控台,隨需開啟的 iperf3 視窗,以及 sing-box 代理節點.v5.0.0 包含受管理節點,流量政策,私人 IP 免密存取,獨立的 HTTP/HTTPS 開關,FRPS/本機 FRPC 管理,Lucky 安裝入口及直接執行的安裝程式.版本範圍及檢查結果見[變更紀錄][local-link-001].

## 功能

- **供任何人確認可達性.** **80** 和
  **443** 連接埠上刻意精簡,無需登入的頁面.將 IP 交給對方;若頁面顯示,表示對方所在位置可以連上你的 Web 連接埠.頁面只顯示來源 IP,伺服器時間,抵達時使用的連接埠與協定,不透露其他主機資訊.
- **從瀏覽器測量吞吐量.** 控制台在持久化的隨機高位連接埠上,透過 LibreSpeed 引擎測試上傳及下載速度.可用管理員密碼,或已明確列入清單的私人區域網路 IP 存取.登入頁始終顯示 IP 免密按鈕;未獲准的訪客會被引導以密碼登入,再到存取設定新增私人 IP.安全設定須經近期管理員密碼驗證才顯示 IP 清單或接受修改.清單只接受單一私人 IPv4 或唯一本地 IPv6 位址,並可單獨停用 IP 免密而保留清單.修改密碼會使現有工作階段失效. 一般設定頁可直接調整外觀和語言;安全設定的管理員密碼驗證過期後須重新驗證.
- **隨需用 iperf3 測量吞吐量與延遲.** 主控台開啟限時視窗;`iperf3 -s` 僅在視窗期間執行,到期後自行關閉.測試者可取得頻寬;Linux 用戶端還可從 `mean_rtt` 在 `--json` 輸出中取得往返時間.該欄位來自核心的 `TCP_INFO`,無法讀取它的用戶端(尤其 Windows 上 Cygwin 的 iperf3)不會提供此欄位.UDP 模式(`-u`)在各平台額外提供抖動及封包遺失率. 主控台分別顯示執行狀態與連接埠;測試視窗關閉時可修改連接埠,新設定在服務重啟後仍有效.
- **記錄連線者.** 讀取 `/proc/net/tcp[6]`,將所有連接埠的每筆入站 TCP 連線(不只 HTTP)記入 SQLite,保留最新 1000 筆.
- **提供 anytls 代理.** sing-box 使用自簽憑證及 BBR.通過驗證的 `/proxy` 頁面顯示節點狀態,流量與可編輯的連線設定;有私人區域網路位址時,亦提供 Clash Meta for Android 一鍵匯入連結及 QR 碼. 訂閱 URL 亦可複製.
- **提供 vmess/vless/trojan/shadowsocks 代理,可選任意組合.** 另一個 sing-box 行程與 anytls 共用隨附的執行檔.每種已安裝協定起初各有一個編號節點;主控台可為任何已安裝協定新增更多節點,也可個別刪除節點.每個節點都有以 GiB 為單位的流量上限,分開的連線與限制編輯功能,隨機重設控件,以及相同的區域網路 Clash Meta 匯入選項.匯入 URL 含有不透明權杖;節點連線設定或名稱改變後,舊連結即失效.公開連接埠不提供代理設定. 新增節點可手動填寫密碼或協定所需的金鑰/UUID,留空則隨機產生;TLS 節點的 SNI 預設為 `www.bing.com`.節點頁面列出主機網卡及 Tailscale 位址. 每個節點亦可分別設定上傳與下載的 Mbps 限速.達到 GiB 流量上限後,可選擇雙向限速 1 Mbps 或停止使用;依自訂天數,月數或年數重設週期流量.亦可設定選用有效期,到期後停止使用. 亦可複製區域網路訂閱連結.

首次安裝預設只安裝 Web 主控台.`VPSSRV_MODULES` 可選擇 web,iperf3,anytls,proxy,frps 及 Lucky;其他模組亦可稍後從主控台安裝.FRPC 作為獨立的本機用戶端功能安裝.

經過身份驗證的 FRPS 頁面顯示本機服務狀態,網絡卡地址和連線設定;令牌及埠在使用者要求顯示前保持遮蔽.FRPS 埠和令牌可直接編輯,服務可開啟或關閉.獨立的 FRPC 頁面以卡片列出本機客戶端例項,遮蔽目標 IP,並根據已建立的 TCP 套接字顯示連線狀態.“測試連線”會使用儲存的伺服器地址,埠和令牌另行執行一次 FRPC 登入.例項頁面按需顯示 IP 或令牌,編輯前也會列出每條 TCP/UDP 代理的型別,本地 IP,本地埠和遠端埠.儲存後留在同一例項頁面,驗證配置檔案,失敗時恢復原配置.這些 FRP 操作使用已登入會話;修改密碼,IP 免密等安全設定操作才要求最近一次管理員密碼驗證.欄位編輯器只處理簡單的令牌認證 TCP/UDP 配置,不會修改其無法表示的 FRPC TOML.此控制檯不監測其他裝置上的 FRPC 例項.模組頁面分別檢查本機 FRPC 可執行檔案和 `frpc@.service` 模板,而不是用是否存在例項配置判斷安裝狀態.缺少其中任一檔案時提供“安裝”.安裝使用經過校驗和驗證的 FRPC v0.71.0 發行資源,不會自行建立連線或監聽埠.模組日誌記錄下載和驗證結果.離線安裝時,先下載 [frpc-0.71.0-linux-amd64](https://github.com/CharlesGool/vps-server/releases/download/v4.0.0/frpc-0.71.0-linux-amd64) (16,593,080 位元組;SHA-256:`f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`),放到 `~/apps/vps-server/vendor/frp/frpc`,再選擇“安裝”.安裝任務對下載或手動放入的檔案執行相同的摘要校驗.解除安裝時會停止本機 FRPC 例項,在 `data/` 下備份其配置,並保留配置檔案供日後重新安裝.

**非目標:**不提供 ACME 或網域名稱(443 刻意使用自簽憑證);不常駐執行 iperf3;不使用反向代理或容器;公開頁面絕不揭露主機名稱,核心版本,運行時間,服務清單或代理參數.本專案不取代 `vps-webserver` 或 `Anytsl-Serve`;兩者仍獨立維護,其程式碼在此以隨附方式收錄,而非被合併取代.

## 需求

- 作業系統:Debian 11+ 或 Ubuntu 20.04+,systemd,以 root 執行
- 執行環境:Python 3.9+(發行版提供的 `python3` 即可;不需安裝額外 Python 套件)
- 架構:web 與 iperf3 模組支援各種架構;anytls,proxy,frps 及 Lucky **僅限 x86-64**,因為隨附的執行檔適用於 amd64
- web 模組使用預設公開連接埠時,80 和 443 **必須**未被佔用;安裝程式會拒絕與 nginx,Apache,Caddy 或 `vps-webserver` 搶佔連接埠
- 外部服務:執行期間不需要.安裝需要發行版套件鏡像;節點摘要只使用網路介面位址及可用的 Tailscale 位址,不對外查詢公開 IP.
- 最低需求:上述作業系統,執行環境,架構與閒置連接埠.尚未記錄其他建議的硬體需求;約 150 MB 的 VPS 磁碟空間可容納隨附執行檔.

## 安裝

### 快速安裝

以 root 身分執行;預設只安裝 Web 主控台,並在終端列印隨機管理連接埠及密碼.

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

`PREFIX` 預設為 `/root/apps/vps-server`.首次安裝無需瀏覽器設定精靈.可用 `VPSSRV_MODULES=web,iperf3,anytls,proxy,frps,lucky` 明確選擇服務端模組;省略時只安裝 Web.安裝後可在 Settings → Modules 安裝或移除選用模組.公開 HTTP 和 HTTPS 頁面分別從 Home 啟用;管理主控台使用獨立連接埠.FRPC 只在需要本機用戶端時另行安裝;其下載資源及離線放置路徑見上文.

## 指南

### 快速開始

Web 實作位於 `src/web/`,靜態資源位於 `src/web/static/`,安裝程式位於 `deploy/`.隨附執行檔及授權記錄位於 `third_party/`;發行中繼資料位於 `config/`.安裝目錄仍沿用既有平鋪布局;更新原始碼布局不會遷移其中的執行資料.

```bash
bash deploy/install.sh                       # 首次只安裝 Web 主控台
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # 明確選擇 Web 與 iperf3
systemctl status vps-server-web              # 檢查服務是否運作
bash deploy/anytls/setup-anytls.sh status           # 若已安裝該模組,查看 anytls 節點詳情
bash deploy/proxy/setup-proxy.sh status             # 若已安裝該模組,查看代理節點詳情
```

接著從另一台機器執行:

```bash
curl -sS  http://<ip>/                     # 檢查明文 HTTP 的可達性
curl -sSk https://<ip>/                    # 檢查 TLS 的可達性(自簽憑證)
iperf3 -c <ip> -p 5201 --json              # 僅在測試視窗開啟時使用
```

### 驗證運作

執行 `bash deploy/install.sh` 後應看到列出各已安裝模組和連接埠的摘要.然後:

- `systemctl status vps-server-web` 回報 `active (running)`.
- 從**另一台機器**開啟 `http://<ip>/`,應看到標題為"Reachable"的頁面及自己的公開 IP.接受憑證警告後開啟 `https://<ip>/`,應看到相同頁面,協定欄位顯示 HTTPS.
- 登入 `http://<ip>:<console port>/`,儀表板顯示 iperf3 控制項,視窗處於關閉狀態.
- 開啟 5 分鐘視窗後,從另一台機器執行 `iperf3 -c <ip> -p 5201 --json`,應取得吞吐量並包含 `mean_rtt`.五分鐘後相同指令應無法連線:這表示視窗自行關閉,不是故障.
- 若已安裝 anytls:`systemctl status vps-server-anytls` 回報 `active (running)`.
- 若已安裝 proxy:`systemctl status vps-server-proxy` 回報 `active (running)`.

### 設定

各變數均有可用的預設值;`.env` 可省略.最重要的項目:

| 變數 | 意義 | 預設值 | 必填 |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | 公開可達性頁面,明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公開可達性頁面,TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 首次安裝是否提供公開頁面;安裝後可在 Home 分別開關 HTTP/HTTPS | `0` | 否 |
| `VPSSRV_CONSOLE_PORT` | 主控台連接埠;`0` 表示產生並保存一個 | `0` | 否 |
| `VPSSRV_AUTH` | 主控台是否需要密碼 | `1` | 否 |
| `VPSSRV_IPERF_PORT` | 已開啟的 iperf3 視窗監聽連接埠 | `5201` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 主控台不可超過的上限 | `60` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | 否 |

完整參考:[設定參考][local-link-002].

## 升級

升級時使用目前的簽出版本,沿用原安裝目錄和模組選項重新執行安裝程式.在確認升級後的服務與主控台正常前,保留持久資料備份.

## 解除安裝

從安裝程式的工作目錄以 root 執行,並使用安裝時相同的 `PREFIX` 和 `SERVICE_NAME` 值(安裝程式的摘要會印出精確的移除指令).要移除已安裝的模組及 unit,**同時
保留** `$PREFIX` 中供日後重新安裝使用的資料:

```bash
KEEP_DATA=1 bash deploy/uninstall.sh
```

若要移除模組並**一併刪除資料**(包括 `$PREFIX` 中的訪客記錄,主控台密碼,已保存連接埠和憑證):

```bash
bash deploy/uninstall.sh
```

兩種模式都會拆除已安裝的 anytls/proxy 服務及各自的模組設定.`KEEP_DATA=1` 保留 `$PREFIX`,不保留這些模組設定.

## 致謝

瀏覽器測試使用 [LibreSpeed](https://github.com/librespeed/speedtest) ;QR 圖碼使用
[qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) ;隨附的代理核心為
[sing-box](https://github.com/SagerNet/sing-box). 實驗性模組隨附
[frp](https://github.com/fatedier/frp) 與
[Lucky](https://github.com/gdy666/lucky). 元件清單和原始授權檔路徑見[第三方聲明][local-link-003].

## 授權條款

專案授權為 GPL-3.0(SPDX:`GPL-3.0-only`);請閱讀完整的 [LICENSE][local-link-004].歷史上的組合理由見[決策][local-link-005].隨附元件,其原始授權,已驗證的產物來源及尚待處理的法律審查限制見 [THIRD_PARTY_NOTICES.md][local-link-006].

本專案與 sing-box/SagerNet 或 LibreSpeed 無隸屬關係,也未獲其背書.

[local-link-001]: CHANGELOG.md
[local-link-002]: DESIGN.md#設定參考
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#決策
[local-link-006]: THIRD_PARTY_NOTICES.md
