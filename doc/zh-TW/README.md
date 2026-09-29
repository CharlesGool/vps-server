---
name: project-readme-zh-tw
description: 專案概覽與使用說明
metadata:
  version: "1.0.0"
  lang: "zh-TW"
---

# vps-server

## 多語言

[English](../../README.md) | [简体中文](../zh-CN/README.md) | **繁體中文(台灣)** | [繁體中文(香港)](../zh-HK/README.md) | [हिन्दी](../hi/README.md) | [Español](../es/README.md) | [العربية](../ar/README.md) | [Français](../fr/README.md)

## 文件

- 專案概覽:[README](README.md)

- 設計考量:[DESIGN](DESIGN.md)

- 發行歷史:[LOG](LOG.md)

- 第三方聲明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 簡介

這是一套可選擇模組的 Debian/Ubuntu VPS 套件:提供檢查 Web 連接埠可達性的公開頁面,測速和連線記錄的操作者主控台,隨需開啟的 iperf3 視窗,以及 sing-box 代理節點.v3.0.0 新增受管理節點,流量政策,私人 IP 免密存取及明暗外觀選項.套件也包含實驗性的 frps 與 Lucky 安裝程式.參閱[目前狀態及驗收限制][local-link-001].

## 功能

- **供任何人確認可達性.** **80** 和
  **443** 連接埠上刻意精簡,無需登入的頁面.將 IP 交給對方;若頁面顯示,表示對方所在位置可以連上你的 Web 連接埠.頁面只顯示來源 IP,伺服器時間,抵達時使用的連接埠與協定,不透露其他主機資訊.
- **從瀏覽器測量吞吐量.** 控制台在持久化的隨機高位連接埠上,透過 LibreSpeed 引擎測試上傳及下載速度.可用管理員密碼,或已明確列入清單的私人區域網路 IP 存取.登入頁始終顯示 IP 免密按鈕;未獲准的訪客會被引導以密碼登入,再到存取設定新增私人 IP.安全設定須經近期管理員密碼驗證才顯示 IP 清單或接受修改.清單只接受單一私人 IPv4 或唯一本地 IPv6 位址,並可單獨停用 IP 免密而保留清單.修改密碼會使現有工作階段失效. 一般設定頁可直接調整外觀和語言;安全設定的管理員密碼驗證過期後須重新驗證.
- **隨需用 iperf3 測量吞吐量與延遲.** 主控台開啟限時視窗;`iperf3 -s` 僅在視窗期間執行,到期後自行關閉.測試者可取得頻寬;Linux 用戶端還可從 `mean_rtt` 在 `--json` 輸出中取得往返時間.該欄位來自核心的 `TCP_INFO`,無法讀取它的用戶端(尤其 Windows 上 Cygwin 的 iperf3)不會提供此欄位.UDP 模式(`-u`)在各平台額外提供抖動及封包遺失率. 主控台分別顯示執行狀態與連接埠;測試視窗關閉時可修改連接埠,新設定在服務重啟後仍有效.
- **記錄連線者.** 讀取 `/proc/net/tcp[6]`,將所有連接埠的每筆入站 TCP 連線(不只 HTTP)記入 SQLite,保留最新 1000 筆.
- **提供 anytls 代理.** sing-box 使用自簽憑證及 BBR.通過驗證的 `/proxy` 頁面顯示節點狀態,流量與可編輯的連線設定;有私人區域網路位址時,亦提供 Clash Meta for Android 一鍵匯入連結及 QR 碼. 訂閱 URL 亦可複製.
- **提供 vmess/vless/trojan/shadowsocks 代理,可選任意組合.** 另一個 sing-box 行程與 anytls 共用隨附的執行檔.每種已安裝協定起初各有一個編號節點;主控台可為任何已安裝協定新增更多節點,也可個別刪除節點.每個節點都有以 GiB 為單位的流量上限,分開的連線與限制編輯功能,隨機重設控件,以及相同的區域網路 Clash Meta 匯入選項.匯入 URL 含有不透明權杖;節點連線設定或名稱改變後,舊連結即失效.公開連接埠不提供代理設定. 新增節點可手動填寫密碼或協定所需的金鑰/UUID,留空則隨機產生;TLS 節點的 SNI 預設為 `www.bing.com`.節點頁面列出主機網卡及 Tailscale 位址. 每個節點亦可分別設定上傳與下載的 Mbps 限速.達到 GiB 流量上限後,可選擇雙向限速 1 Mbps 或停止使用;依自訂天數,月數或年數重設週期流量.亦可設定選用有效期,到期後停止使用. 亦可複製區域網路訂閱連結.

web,iperf3,anytls,proxy,frps 與 Lucky 六個模組均可在安裝時選擇.frps 與 Lucky 仍屬實驗性模組;本版本尚未在實機完成其行為驗收.

經過身份驗證的 FRPS 頁面顯示本機服務狀態,網絡卡地址和連線設定;令牌及埠在使用者要求顯示前保持遮蔽.FRPS 埠和令牌可直接編輯,服務可開啟或關閉.獨立的 FRPC 頁面以卡片列出本機客戶端例項,遮蔽目標 IP,並根據已建立的 TCP 套接字顯示連線狀態.“測試連線”會使用儲存的伺服器地址,埠和令牌另行執行一次 FRPC 登入.例項頁面按需顯示 IP 或令牌,編輯前也會列出每條 TCP/UDP 代理的型別,本地 IP,本地埠和遠端埠.儲存後留在同一例項頁面,驗證配置檔案,失敗時恢復原配置.這些 FRP 操作使用已登入會話;修改密碼,IP 免密等安全設定操作才要求最近一次管理員密碼驗證.欄位編輯器只處理簡單的令牌認證 TCP/UDP 配置,不會修改其無法表示的 FRPC TOML.此控制檯不監測其他裝置上的 FRPC 例項.模組頁面分別檢查本機 FRPC 可執行檔案和 `frpc@.service` 模板,而不是用是否存在例項配置判斷安裝狀態.缺少其中任一檔案時提供“安裝”;FRPC 已安裝但沒有例項時提供“建立例項”連結.安裝使用經過校驗和驗證的 FRPC v0.71.0 發行資源,不會自行建立連線或監聽埠.模組日誌記錄下載和驗證結果.離線安裝時,先下載 [frpc-0.71.0-linux-amd64](https://github.com/CharlesGool/vps-server/releases/download/v4.0.0/frpc-0.71.0-linux-amd64) (16,593,080 位元組;SHA-256:`f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`),放到 `~/apps/vps-server/vendor/frp/frpc`,再選擇“安裝”.安裝任務對下載或手動放入的檔案執行相同的摘要校驗.解除安裝時會停止本機 FRPC 例項,在 `data/` 下備份其配置,並保留配置檔案供日後重新安裝.

**非目標:**不提供 ACME 或網域名稱(443 刻意使用自簽憑證);不常駐執行 iperf3;不使用反向代理或容器;公開頁面絕不揭露主機名稱,核心版本,運行時間,服務清單或代理參數.本專案不取代 `vps-webserver` 或 `Anytsl-Serve`;兩者仍獨立維護,其程式碼在此以隨附方式收錄,而非被合併取代.

## 需求

- 作業系統:Debian 11+ 或 Ubuntu 20.04+,systemd,以 root 執行
- 執行環境:Python 3.9+(發行版提供的 `python3` 即可;不需安裝額外 Python 套件)
- 架構:web 與 iperf3 模組支援各種架構;anytls,proxy,frps 及 Lucky **僅限 x86-64**,因為隨附的執行檔適用於 amd64
- web 模組使用預設公開連接埠時,80 和 443 **必須**未被佔用;安裝程式會拒絕與 nginx,Apache,Caddy 或 `vps-webserver` 搶佔連接埠
- 外部服務:執行期間不需要.安裝需要發行版套件鏡像;節點摘要只使用網路介面位址及可用的 Tailscale 位址,不對外查詢公開 IP.
- 最低需求:上述作業系統,執行環境,架構與閒置連接埠.尚未記錄其他建議的硬體需求;約 150 MB 的 VPS 磁碟空間可容納隨附執行檔.

## 安裝

單行快速安裝(最新發行標籤,無設定變數):

```bash
git clone --branch v4.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

逐步安裝並設定:

```bash
# 複製發行標籤;預設分支可能包含尚未發行的變更.
# 列出發行標籤: `git ls-remote --tags https://github.com/CharlesGool/vps-server.git`
git clone --branch v4.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # 可選;每個變數都有可用的預設值
bash deploy/install.sh
```

`deploy/install.sh` 會詢問要安裝哪些模組,介面語言,是否以密碼保護主控台,以及使用哪些連接埠.v4.0.0 標籤包含六個可選模組;frps 與 Lucky 屬實驗性模組.

### 首次設定

以下設定流程包含在 v4.0.0 中.在全新 Debian 或 Ubuntu 系統上,從終端以 root 身份克隆發行標籤並執行 `bash deploy/install.sh`.應用預設安裝在 root 賬戶的 `~/apps/vps-server`;可透過 `PREFIX` 選擇其他目錄.

安裝程式會在隨機可用埠上開啟臨時 HTTPS 設定頁,並在終端列印其 URL,證書指紋和一次性隨機設定密碼.若五分鐘內未作選擇,頁面便會過期.登入設定頁選擇要安裝的模組;透過瀏覽器設定時必須選擇 Web 控制檯.僅在選擇代理節點後才詢問代理協議.提交後重新整理設定頁可檢視進度.安裝完成且主機有可用的網絡卡地址時,頁面會連結到控制檯;否則使用終端列印的地址.終端還會列印持久有效的控制檯密碼和地址;一次性設定密碼不能用於登入控制檯.完成後的寬限期結束時,臨時監聽器會關閉並釋放埠.

在控制檯開啟 **Settings → Modules**.普通已登入會話可管理這些執行功能;Security Settings 仍要求密碼驗證.模組列表包括 Speed test,iperf3,Proxy nodes,FRPS,FRPC,Port forward,Recent visitors,Changelog 和 Settings.僅可獨立安裝的功能顯示“安裝”或“解除安裝”.解除安裝前,輔助程式會將私有配置歸檔到 `$PREFIX/data`;模組頁面可檢視最近任務的輸出.可選模組從 `$PREFIX/installer-source` 下與版本匹配的檔案安裝.除 Settings 外,Home 的每張卡片都有獨立開關.Proxy nodes 開關同時控制 AnyTLS 和其他代理協議,保留節點記錄;沒有已啟用節點時不會啟動服務.FRPC 開關重新開啟時只恢復關閉前執行的例項.關閉埠轉發會保留規則,重新開啟時再次應用已啟用規則.安裝以獨立的 systemd 任務執行,可能短暫重啟 Web 服務.若無法訪問設定埠,可使用 `VPSSRV_SETUP_PUBLIC=0` 配合本地 SSH 隧道,或透過 `VPSSRV_SETUP_PORT` 選擇允許使用的埠.

主機安裝 FRPC 後,可從 Home 開啟 **FRPS** 或 **FRPC** 卡片.
**Edit FRPS** 可修改繫結埠和令牌;欄位留空則保留當前值.修改後還須更新連線此 FRPS 伺服器的 FRPC 例項.本機 FRPC 卡片有獨立的“測試連線”“編輯”和需確認的“刪除”控制元件;點選卡片空白處不會觸發操作.啟動開關位於例項名旁.開啟“編輯”可重新命名例項,或就地修改伺服器和代理對映.點選遮蔽的 IP,埠或令牌可顯示其值;開啟“編輯伺服器”會載入已儲存的值.“測試連線”使用已儲存的值執行一次臨時登入,不會啟動或更改受管例項.儲存時使用 `frpc verify` 驗證,重啟正在執行的例項,然後返回同一例項頁面.新例項首次有效儲存後會啟用.頁面也可在不刪除配置的情況下啟動或停止已有例項.修改本機 FRPC 例項不會影響其他裝置上的客戶端.TCP 代理的 `remotePort` 必須在當前啟用的主機防火牆和雲安全組中放行;編輯器會登記同一主機上的埠分配,但不會修改雲防火牆規則.

**再次執行會就地升級.** 程式偵測現有安裝,讓你選擇保留設定,只詢問已安裝版本尚未提供的設定;每項都有預設值,直接按 Enter 即可.主控台密碼,已保存的連接埠,憑證,訪客記錄,anytls 節點憑證,以及各已安裝代理協定的連接埠和憑證都會保留.升級提示回答 `n` 則會重新詢問設定.

## 指南

### 快速開始

v2.0.0 將 Web 實作放在 `src/web/app.py`,安裝程式從 `deploy/` 執行.隨附的執行檔及授權聲明位於 `third_party/`;發行中繼資料位於 `config/`.已安裝檔案仍平鋪於 `$PREFIX` 下;簽出目錄的結構調整不會遷移運行資料.新路徑已通過本地測試,但本版本尚未通過實機驗收.

```bash
bash deploy/install.sh                       # 互動式設定:使用瀏覽器中的臨時安裝精靈
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # 無人值守,不顯示提示
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
| `VPSSRV_PUBLIC_ENABLE` | 是否提供公開頁面 | `1` | 否 |
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

[local-link-001]: LOG.md#目前狀態與驗收限制
[local-link-002]: DESIGN.md#設定參考
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#決策
[local-link-006]: THIRD_PARTY_NOTICES.md
