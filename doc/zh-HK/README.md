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

這套可按模組選用的工具供 Debian/Ubuntu VPS 使用:公開頁面檢查網頁連接埠能否連通,操作員控制台提供網速測試及連線紀錄,按需開啟的 iperf3 測試時段,以及 sing-box 代理節點.v3.0.0 新增受管理節點,流量政策,私人 IP 免密存取和明暗外觀選項.套件亦包含實驗性的 frps 和 Lucky 安裝程式.參閱[現況及驗收限制][local-link-001].

## 功能

- **讓任何人確認連通性.** 在 **80** 和
  **443** 連接埠提供刻意保持簡潔,毋須登入的頁面.把 IP 交給對方;若頁面能顯示,就代表對方所在位置能連到你的網頁連接埠.頁面只顯示對方的來源 IP,伺服器時鐘,以及所用的連接埠和協定,不透露其他主機資料.
- **透過瀏覽器量度吞吐量.** 控制台在持久保存的隨機高位連接埠上,以 LibreSpeed 引擎測試上載及下載速度.可使用管理員密碼,或已明確列入名單的私人區域網絡 IP 存取.登入頁一直顯示 IP 免密按鈕;未獲准的訪客會被引導以密碼登入,再到存取設定新增私人 IP.安全設定須經近期管理員密碼驗證才顯示 IP 名單或接受修改.名單只接受單一私人 IPv4 或唯一本地 IPv6 位址,並可單獨停用 IP 免密而保留名單.修改密碼會使現有工作階段失效. 一般設定頁可直接調整外觀及語言;安全設定的管理員密碼驗證過期後須重新驗證.
- **按需用 iperf3 量度吞吐量及延遲.** 控制台開啟限時時段;`iperf3 -s` 只在期間執行,到期自動關閉.測試者可取得頻寬;Linux 用戶端亦可從 `mean_rtt` 在 `--json` 輸出中取得往返時間.此欄位來自核心的 `TCP_INFO`;不能讀取該資訊的用戶端(尤其是 Windows 上 Cygwin 的 iperf3)不會有此欄位.UDP 模式(`-u`)在各平台均提供抖動及封包遺失數據. 控制台分別顯示運行狀態及連接埠;測試時段關閉時可修改連接埠,新設定在服務重啟後仍有效.
- **記錄連線來源.** 透過 `/proc/net/tcp[6]` 讀取所有連接埠的每條入站 TCP 連線(不限 HTTP),存入 SQLite,保留最近 1000 條.
- **提供 anytls 代理.** sing-box 使用自簽憑證及 BBR.經驗證的 `/proxy` 頁面顯示節點狀態,流量及可編輯的連線設定;有私人局域網絡位址時,亦提供 Clash Meta for Android 一鍵匯入連結及 QR 碼. 訂閱 URL 亦可複製.
- **提供 vmess/vless/trojan/shadowsocks 代理,可選任何組合.** 另一個 sing-box 程序與 anytls 共用隨附的執行檔.每種已安裝協定起初各有一個編號節點;控制台可為任何已安裝協定新增更多節點,也可逐個刪除.每個節點都有以 GiB 為單位的流量上限,分開的連線與限制編輯功能,隨機重設控件,以及相同的局域網絡 Clash Meta 匯入選項.匯入 URL 含有不透明權杖;節點連線設定或名稱改變後,舊連結即失效.公開連接埠不提供代理設定. 新增節點可手動填寫密碼或協定所需的金鑰/UUID,留空則隨機產生;TLS 節點的 SNI 預設為 `www.bing.com`.節點頁面列出主機網卡及 Tailscale 位址. 每個節點亦可分別設定上載及下載的 Mbps 限速.達到 GiB 數據上限後,可選擇雙向限速 1 Mbps 或停止使用;按自訂日數,月數或年數重設週期數據.亦可設定可選有效期,到期後停止使用. 亦可複製局域網絡訂閱連結.

web,iperf3,anytls,proxy,frps 和 Lucky 六個模組均可於安裝時選用.frps 和 Lucky 仍屬實驗性模組;本版本尚未在真實主機完成其行為驗收.

經過身份驗證的 FRPS 頁面顯示本機服務狀態,網卡地址和連接設置;令牌及端口在用户要求顯示前保持遮蔽.FRPS 端口和令牌可直接編輯,服務可開啓或關閉.獨立的 FRPC 頁面以卡片列出本機客户端實例,遮蔽目標 IP,並根據已建立的 TCP 套接字顯示連接狀態.“測試連接”會使用保存的服務器地址,端口和令牌另行執行一次 FRPC 登錄.實例頁面按需顯示 IP 或令牌,編輯前也會列出每條 TCP/UDP 代理的類型,本地 IP,本地端口和遠程端口.保存後留在同一實例頁面,驗證配置文件,失敗時恢復原配置.這些 FRP 操作使用已登錄會話;修改密碼,IP 免密等安全設置操作才要求最近一次管理員密碼驗證.字段編輯器只處理簡單的令牌認證 TCP/UDP 配置,不會修改其無法表示的 FRPC TOML.此控制枱不監測其他設備上的 FRPC 實例.模塊頁面分別檢查本機 FRPC 可執行文件和 `frpc@.service` 模板,而不是用是否存在實例配置判斷安裝狀態.缺少其中任一文件時提供“安裝”;FRPC 已安裝但沒有實例時提供“創建實例”鏈接.安裝使用經過校驗和驗證的 FRPC v0.71.0 發行資源,不會自行建立連接或監聽端口.模塊日誌記錄下載和驗證結果.離線安裝時,先下載 [frpc-0.71.0-linux-amd64](https://github.com/CharlesGool/vps-server/releases/download/v4.0.0/frpc-0.71.0-linux-amd64) (16,593,080 字節;SHA-256:`f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`),放到 `~/apps/vps-server/vendor/frp/frpc`,再選擇“安裝”.安裝任務對下載或手動放入的文件執行相同的摘要校驗.卸載時會停止本機 FRPC 實例,在 `data/` 下備份其配置,並保留配置文件供日後重新安裝.

**不屬於目標:**不提供 ACME 或網域名稱(443 刻意使用自簽憑證);不持續執行 iperf3;不提供反向代理或容器;公開頁面絕不披露主機名稱,核心,運行時間,服務清單或代理參數.本項目不取代 `vps-webserver` 或 `Anytsl-Serve`;兩者維持獨立維護,其程式碼在此以隨附副本形式提供,並非納入取代.

## 要求

- 作業系統:Debian 11+ 或 Ubuntu 20.04+,systemd;以 root 身份執行
- 執行環境:Python 3.9+(發行版的 `python3` 已足夠,無須安裝 Python 相依套件)
- 架構:web 和 iperf3 模組支援任何架構;anytls,proxy,frps 和 Lucky **只支援 x86-64**,因為隨附的執行檔適用於 amd64
- web 模組如使用預設公開連接埠,80 和 443 **必須**空閒;安裝程式會拒絕安裝,而不會與 nginx,Apache,Caddy 或 `vps-webserver` 爭用
- 外部服務:運行期間不需要.安裝需要發行版套件鏡像;節點摘要只使用網絡介面位址及可用的 Tailscale 位址,不對外查詢公網 IP.
- 最低要求為上述系統,執行環境,架構和空閒連接埠.沒有另行記錄建議硬件要求;約 150 MB 磁碟空間可容納隨附執行檔.

## 安裝

一行快速安裝(最新發佈標籤,不設定變數):

```bash
git clone --branch v4.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

逐步安裝及設定:

```bash
# 複製發佈標籤;預設分支可能包含尚未發佈的變更.
# 列出發佈標籤: `git ls-remote --tags https://github.com/CharlesGool/vps-server.git`
git clone --branch v4.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # 可選;每個變數都有可用預設值
bash deploy/install.sh
```

`deploy/install.sh` 會詢問要安裝的模組,介面語言,是否以密碼保護控制台,以及使用哪些連接埠.v4.0.0 標籤包含六個可選模組;frps 和 Lucky 屬實驗性模組.

### 首次設置

以下設置流程包含在 v4.0.0 中.在全新 Debian 或 Ubuntu 系統上,從終端以 root 身份克隆發行標籤並運行 `bash deploy/install.sh`.應用默認安裝在 root 賬户的 `~/apps/vps-server`;可通過 `PREFIX` 選擇其他目錄.

安裝程序會在隨機可用端口上打開臨時 HTTPS 設置頁,並在終端打印其 URL,證書指紋和一次性隨機設置密碼.若五分鐘內未作選擇,頁面便會過期.登錄設置頁選擇要安裝的模塊;通過瀏覽器設置時必須選擇 Web 控制枱.僅在選擇代理節點後才詢問代理協議.提交後刷新設置頁可查看進度.安裝完成且主機有可用的網卡地址時,頁面會鏈接到控制枱;否則使用終端打印的地址.終端還會打印持久有效的控制枱密碼和地址;一次性設置密碼不能用於登錄控制枱.完成後的寬限期結束時,臨時監聽器會關閉並釋放端口.

在控制枱打開 **Settings → Modules**.普通已登錄會話可管理這些運行功能;Security Settings 仍要求密碼驗證.模塊列表包括 Speed test,iperf3,Proxy nodes,FRPS,FRPC,Port forward,Recent visitors,Changelog 和 Settings.僅可獨立安裝的功能顯示“安裝”或“卸載”.卸載前,輔助程序會將私有配置歸檔到 `$PREFIX/data`;模塊頁面可查看最近任務的輸出.可選模塊從 `$PREFIX/installer-source` 下與版本匹配的文件安裝.除 Settings 外,Home 的每張卡片都有獨立開關.Proxy nodes 開關同時控制 AnyTLS 和其他代理協議,保留節點記錄;沒有已啓用節點時不會啓動服務.FRPC 開關重新開啓時只恢復關閉前運行的實例.關閉端口轉發會保留規則,重新開啓時再次應用已啓用規則.安裝以獨立的 systemd 任務運行,可能短暫重啓 Web 服務.若無法訪問設置端口,可使用 `VPSSRV_SETUP_PUBLIC=0` 配合本地 SSH 隧道,或通過 `VPSSRV_SETUP_PORT` 選擇允許使用的端口.

主機安裝 FRPC 後,可從 Home 打開 **FRPS** 或 **FRPC** 卡片.
**Edit FRPS** 可修改綁定端口和令牌;字段留空則保留當前值.修改後還須更新連接此 FRPS 服務器的 FRPC 實例.本機 FRPC 卡片有獨立的“測試連接”“編輯”和需確認的“刪除”控件;點擊卡片空白處不會觸發操作.啓動開關位於實例名旁.打開“編輯”可重命名實例,或就地修改服務器和代理映射.點擊遮蔽的 IP,端口或令牌可顯示其值;打開“編輯服務器”會載入已保存的值.“測試連接”使用已保存的值執行一次臨時登錄,不會啓動或更改受管實例.保存時使用 `frpc verify` 驗證,重啓正在運行的實例,然後返回同一實例頁面.新實例首次有效保存後會啓用.頁面也可在不刪除配置的情況下啓動或停止已有實例.修改本機 FRPC 實例不會影響其他設備上的客户端.TCP 代理的 `remotePort` 必須在當前啓用的主機防火牆和雲安全組中放行;編輯器會登記同一主機上的端口分配,但不會修改雲防火牆規則.

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

[local-link-001]: LOG.md#目前狀態與驗收限制
[local-link-002]: DESIGN.md#設定參考
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#決策
[local-link-006]: THIRD_PARTY_NOTICES.md
