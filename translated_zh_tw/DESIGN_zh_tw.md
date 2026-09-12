# vps-server — Design

[English](../DESIGN.md) | [简体中文](../translated_zh_cn/DESIGN_zh_cn.md) | **繁體中文**

> 譯自 `DESIGN.md`（v1.0.1）。如有衝突，以英文版為準。

> 這份文件的成功標準：另一個人，在另一台機器上，能照著它把這個專案重建出來。
> 假設讀者看不到你的機器。

## 目標與非目標

**目標**

- 在全新的 Debian/Ubuntu VPS 上安裝一個套件，提供四項功能，每項在安裝時都能獨立選擇：
  1. **公開可達性頁面**——一個刻意精簡、不需要驗證的頁面，服務於 TCP
     **80 和 443**，讓任何只拿到 IP 的人都能在瀏覽器裡確認，從自己所在的位置能不能連到這台主機的
     web 連接埠。
  2. **私人主控台**——一個受密碼保護的儀表板，跑在一個持久化的隨機高位連接埠上，
     提供瀏覽器端的上/下載速度測試，以及近期觀察到的入站連線紀錄。
  3. **按需開啟的 iperf3 視窗**——一個頻寬/延遲測試端點，**預設關閉**；
     操作者從主控台開啟一個有時限的視窗，時限到了會自動關閉。
  4. **anytls 代理**——一個帶自簽憑證的 sing-box `anytls` inbound，外加 BBR。
- 除了發行版套件鏡像之外不需要對外網路存取即可安裝。sing-box 二進位檔已內含在儲存庫中。
- 能與 `vps-webserver` 及 `Anytsl-Serve` 共存於同一台主機，不會在 systemd unit
  名稱、安裝前綴、環境變數前綴或持久化連接埠上發生衝突。

**非目標**

- **不是 `vps-webserver` 或 `Anytsl-Serve` 的替代品。** 兩者都繼續獨立維護、獨立發行。
  vps-server 是把它們的程式碼廠商化（vendor）進來，而不是匯入或取代它們；
  這麼做在漂移（drift）上要付出的取捨與緩解方式，見 `DECISIONS.md`。
- **沒有 ACME / Let's Encrypt / 網域名稱。** 443 上的 TLS 是自簽憑證。公開頁面的任務
  是回答「你能不能連到這個 IP」，而瀏覽器的警告頁面本身就已經回答了這個問題。
  憑證續期和網域依賴對這項任務沒有任何幫助。
- **沒有常駐開啟的 iperf3。** 一個未經驗證、公開的 `iperf3 -s` 會讓任何陌生人
  想跑多久就跑多久地佔滿這台主機的上行頻寬。
- **公開頁面不揭露任何主機資訊。** 沒有主機名稱、沒有核心版本、沒有開機時長、
  沒有服務清單、沒有連接埠清單、沒有 anytls 參數。它只回報：你連到了它、
  它看到的來源 IP、伺服器時鐘，以及你是透過哪一組連接埠/協定連進來的。
- **沒有反向代理、沒有 nginx、沒有容器。** Python 行程自己終結 TLS，
  就跟 `vps-webserver` 現在做的一樣。
- **沒有多伺服器測速選單。** 一台主機，就是這台主機。

## 架構

兩個行程外加一個暫時性的子行程。彼此之間沒有任何網路通訊；主控台和公開頁面
是同一個 Python 行程裡的兩個監聽器，在記憶體中共享狀態。

```
                       ┌──────────────────────── vps-server-web.service ───────┐
  anyone, no auth      │                                                       │
  :80  ──────────────► │  public listener (HTTP)  ──┐                          │
  :443 ──────────────► │  public listener (HTTPS) ──┤                          │
                       │                            ├─► ProbeHandler           │
                       │                            │   (reachability page)    │
                       │                            │                          │
  operator, password   │                            │                          │
  :<random> ─────────► │  console listener  ───────►│   ConsoleHandler         │
                       │                            │   ├─ LibreSpeed endpoints│
                       │                            │   ├─ visitor log         │
                       │                            │   └─ iperf3 window ctl ──┼──┐
                       │                            │                          │  │
                       │  connection poller ◄───────┴── /proc/net/tcp[6]       │  │
                       │  (all ports, not just HTTP)                           │  │
                       └───────────────────────────────────────────────────────┘  │
                                                                                   │
  tester with iperf3      :5201 ◄────────────── iperf3 -s  (child process, ────────┘
  client                                         killed when window expires)

                       ┌─── vps-server-anytls.service ───┐
  proxy client ──────► │  sing-box, anytls inbound, TLS  │
  :<random>            │  self-signed cert               │
                       └─────────────────────────────────┘
```

這兩個 systemd unit 是各自獨立的：任何一個都能單獨安裝而不需要另一個，
也沒有誰會重啟誰。

### 為什麼公開頁面和主控台是分開的監聽器

它們的安全姿態是相反的，合併起來會迫使其中一方放棄自己的立場。主控台需要驗證，
放在一個猜不到的連接埠上，就是為了不被隨便發現；公開頁面則必須容易被發現，
也不能要求密碼。所以：不同的連接埠、不同的請求處理器、不同的路由表。
一個打到 80/443 的請求永遠碰不到主控台的路由，因為 `ProbeHandler` 根本沒有那些路由——
不是因為某個檢查拒絕了它。這正是重點所在：授權檢查可能會有 bug，
但不存在的路由不會。

公開頁面只在恰好兩個路徑（`/` 和 `/favicon.ico`）上接受 `GET` 和 `HEAD`，
其他一律回應 404。它不讀取查詢字串、不解析請求主體、也不設定任何 cookie。

### 在既有安裝上升級

`install.sh` 會偵測既有安裝，並詢問是否要沿用它的設定。回答「是」會重放
上一次安裝記錄下來的內容；回答「否」則重新詢問所有問題。不論哪種方式，
主控台密碼、持久化的連接埠、憑證以及訪客紀錄都會保留下來——
這些是安裝程式從不觸碰的檔案。

有兩份紀錄，因為它們回答的問題不一樣：

- **systemd unit 的 `Environment=` 那幾行**記錄的是「曾經被設定過什麼」。
  重放它們是為了阻止某個曾經選定的設定——例如自訂的公開連接埠、主控台上的 TLS——
  在下次升級時悄悄回退到預設值。
- **`$PREFIX/.install-state`** 記錄的是「已安裝的版本知道些什麼」：
  它的版本號、它的模組清單，以及它理解的每一個設定項的名稱。
  unit 無法回答這個問題，因為它只記錄被賦過值的設定，
  完全說明不了哪些設定曾經存在過。

「這個版本新增了什麼」就是靠第二份檔案算出來的：拿這個版本知道的設定
減去戳記清單上有的設定。每一項都會附上它在 `.env.example` 裡的預設值，
按 Enter 就是接受這個預設值。

早於這份戳記存在的安裝，沒有這份清單。安裝程式不會把猜測當成差異呈現，
而是直接說它無法判斷，把 unit 記錄的內容全部沿用下來，並指向重新詢問的路徑。
模組偵測也是同樣降級：沒有戳記時，它就從磁碟上有什麼來推斷模組清單——
web unit、anytls unit、有沒有裝 `iperf3`。

anytls 節點在升級時的保留方式，是把它的連接埠和密碼從 `config.json`
裡讀回來再傳進去。少了這一步，`setup-anytls.sh` 會把兩者都預設成全新的隨機值，
每一個已設定好的用戶端都會在一次例行升級中壞掉——見下方的「已知限制與陷阱」，
這一點在*刻意*重新安裝時依然成立。

### 主控台的 anytls 頁面

主控台從 `VPSSRV_ANYTLS_CONFIG` 讀取已安裝的節點，並呈現它的狀態，
外加一份可以直接貼上使用的 Clash 設定與 `anytls://` 連結。

它會寫入的東西只有一項：「重設連接埠與密碼」按鈕，而且連這一項也是委派出去的。
主控台自己不會碰 `config.json`——它會執行 `setup-anytls.sh reset`，
因為這裡的順序很容易搞錯：舊連接埠的防火牆規則必須在新連接埠開啟*之前*
先撤銷，否則每次重設都會留下一條沒有任何行程在監聽的 `ACCEPT` 規則。
這段邏輯歸擁有這個節點的腳本管，而不是分散在兩個地方各寫一份。
重設需要伺服器端驗證的確認核取方塊——標記語言裡的 `required` 阻止的是誤點，
不是非瀏覽器的用戶端——因為輪替憑證會讓每一個已設定好的用戶端在拿到新資訊之前
全部斷線。

它還跑在**這個服務的沙盒之外**，以 `systemd-run --pipe --wait --collect`
啟動的暫時性 unit 形式執行。web unit 設了 `ProtectSystem=strict`，
只有 `ReadWritePaths=$PREFIX`，所以 `/etc` 對它而言是唯讀的，
而重設需要寫入 `/etc/vps-server-anytls` 和一份 unit 檔案。
第一次實際嘗試就是因為這個原因半途死掉——而且是在已經撤銷了舊連接埠的
防火牆規則之後。另一個做法，把 `/etc/systemd/system` 加進
`ReadWritePaths`，會為了讓一個按鈕能用而永久放寬這個長駐服務的寫入權限；
沙盒的價值比這個更高。沒有 `systemd-run` 的環境下，呼叫會直接進行，
這是對的，因為缺少 `systemd-run` 的環境，正好也是 `install.sh` 省略了
安全強化措施的那些環境。

`setup-anytls.sh reset` 在動防火牆之前也會先檢查自己有沒有寫入權限。
一個在撤銷舊規則之後才失敗的重設，會留下一個正在運作卻進不去的節點，
這比從未啟動過還要糟。

有兩個細節是承重的。**節點密碼會以明文顯示在那個頁面上**，
這之所以可以接受，只是因為那個頁面掛在 `ConsoleHandler` 之下，
在登入之後；`ProbeHandler` 沒有到它的路由，而且有一份測試斷言
公開監聽器對 `/anytls` 回應 404、且絕不含有密碼。以及**伺服器位址
是取自請求的 `Host` 標頭**，而不是查出來的：不管什麼位址連得到主控台，
就能連得到節點，在渲染時做一次對外的 IP 查詢會違反「不對外發起請求」的規則，
而任何需要不同位址的人，複製之後自己改那一行就好。

SNI 完全沒有存在 sing-box 的設定裡——`setup-anytls.sh` 只把它烤進
自簽憑證的 CN 欄位——所以主控台是從憑證裡把它讀回來，
而不是另外保留一份可能會漂移的副本。

### iperf3 視窗的生命週期

1. 操作者登入主控台，選擇一個時長（預設 10 分鐘，上限由
   `VPSSRV_IPERF_MAX_MINUTES` 決定），點擊開啟。
2. 主控台以子行程形式產生 `iperf3 -s -p <port>`，在當前生效的防火牆上
   開啟該連接埠，並把截止時間記在記憶體裡。
3. 在視窗開啟期間，**公開頁面**會顯示 iperf3 正在接受連線、在哪個連接埠上、
   還剩多少時間——遠端的測試者需要知道這些資訊，而且它並不敏感：
   這個視窗本來就是刻意打開的。
4. 到了截止時間（或操作者要求、或服務停止）時，子行程會被終止，
   防火牆規則也會被撤銷。

這個視窗只保存在記憶體裡，不落地到磁碟：如果服務掛掉，視窗就沒了，
這是失敗時比較安全的方向。重啟絕不會讓一個開著的視窗死而復生。

延遲是在測試者那一側，從 iperf3 自己的 `--json` 輸出（TCP info 區塊裡的
`mean_rtt`）讀出來的；伺服器端不需要為此寫任何額外程式碼。這個欄位來自核心的
`TCP_INFO`，所以在 Linux 用戶端上會有，在讀不到它的用戶端上就沒有——
Windows 上 Cygwin 版本的 iperf3 會回報輸送量，但沒有 `mean_rtt`。
UDP 模式（`-u`）在任何地方都會回報 jitter 和封包遺失，
是測試者不在 Linux 上時比較通用的答案。

## 技術選型

| 層 | 選擇 | 版本 | 理由 |
|---|---|---|---|
| Runtime | Python，只用標準函式庫 | 3.9+ | 繼承自 `vps-webserver`：不用第三方套件，代表在全新 VPS 上不需要解析依賴，也沒有東西需要持續打補丁 |
| HTTP 伺服器 | `http.server.ThreadingHTTPServer` | stdlib | 三個監聽器，每個都只有零星幾個請求；上框架只是死重量 |
| TLS | `ssl` + `openssl` 產生的自簽憑證 | stdlib / distro | 沒有網域、沒有 ACME（見「非目標」） |
| 儲存 | `sqlite3` | stdlib | 訪客紀錄必須撐過重啟 |
| 測速引擎 | LibreSpeed，原樣廠商化（vendor）進來 | v6.2.1 | LGPL-3.0；在 `vps-webserver` 裡已經廠商化且能正常運作 |
| 頻寬探測 | 發行版提供的 `iperf3` | distro-pinned | 測試者在用戶端那一側事實上早就有的工具 |
| Proxy core | sing-box，廠商化的二進位檔（amd64） | v1.13.14 | GPL-3.0；隨附二進位檔能讓安裝保持離線可用 |
| Init | systemd | — | 目標作業系統的預設值 |
| Installer | Bash | — | 繼承自兩個上游專案 |

被否決的替代方案以及每個選擇背後的理由都放在 `DECISIONS.md` 裡——這裡不重複。

## 重建需求

### 環境

- OS：Debian 11+ / Ubuntu 20.04+，systemd，以 root 執行
- Runtime：Python 3.9+（發行版自帶的 python3 就足夠）
- 架構：anytls 模組**僅限 x86-64**——內含的 sing-box 二進位檔是 amd64 的。
  web 和 iperf3 模組與架構無關。
- 硬體：不需要 GPU；約 150 MB 磁碟空間（其中約 57 MB 是 sing-box 二進位檔），
  VPS 一般具備的任何記憶體容量都夠用
- 依賴還原命令：無。沒有 Python 鎖檔，因為沒有任何 Python 依賴；
  見 `THIRD_PARTY_NOTICES.md`。

### 外部依賴

| 項目 | 來源 | 放置位置 |
|---|---|---|
| `iperf3` | 發行版套件管理員（`apt-get install iperf3`） | 系統路徑 |
| `openssl`、`curl`、`jq`、`iproute2` | 發行版套件管理員 | 系統路徑 |
| sing-box 二進位檔 | 隨此儲存庫附帶 | `/usr/local/bin/sing-box-vps-server` |
| LibreSpeed 引擎 | 隨此儲存庫附帶 | `$PREFIX/static/` |
| TLS 憑證 | 由安裝程式在首次執行時產生 | `$VPSSRV_CERT_DIR` |

不需要任何 API 金鑰。這個服務在執行期間不會發起任何對外請求，
唯一的例外是安裝時可選的公開 IP 查詢，失敗時會降級為一則警告。

### 路徑與掛載點

| 路徑 | 由誰提供 | 用途 |
|---|---|---|
| `$PREFIX` | 安裝程式，預設 `/opt/vps-server` | 程式碼、靜態資源、持久化連接埠檔案 |
| `$VPSSRV_DATA_DIR` | 安裝程式，預設 `$PREFIX/data` | `visitors.db`、`session_secret.txt` |
| `$VPSSRV_CERT_DIR` | 安裝程式，預設 `$PREFIX/certs` | 443 用的自簽憑證與金鑰 |
| `/etc/vps-server-anytls/` | 安裝程式 | sing-box 的 `config.json` 以及它自己的自簽憑證 |

### 設定參考

所有變數都使用 `VPSSRV_` 前綴。這不是美觀考量：`vps-webserver`
擁有 `VPSWS_` 前綴，`Anytsl-Serve` 擁有 `ANYTLS_` 前綴，
而這三者可能同時裝在同一台主機上，共用前綴會讓一個專案的 `.env`
悄悄重新設定另一個專案。

| 變數 | 意義 | 預設值 | 是否必要 |
|---|---|---|---|
| `PREFIX` | 安裝根目錄。傳給 `install.sh`/`uninstall.sh`，**不**從 `.env` 讀取——
  在有安裝可以讀取 `.env` 之前，就需要先知道這個路徑 | `/opt/vps-server` | 否 |
| `VPSSRV_DATA_DIR` | SQLite + session secret | `$PREFIX/data` | 否 |
| `VPSSRV_HOST` | 所有監聽器的綁定位址 | `0.0.0.0` | 否 |
| `VPSSRV_PUBLIC_HTTP_PORT` | 公開可達性頁面，明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公開可達性頁面，TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 是否要提供公開頁面 | `1` | 否 |
| `VPSSRV_CONSOLE_PORT` | 主控台連接埠；`0` = 產生一次並持久化 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT_FILE` | 產生出來的主控台連接埠記在哪裡 | `$PREFIX/console_port.txt` | 否 |
| `VPSSRV_CONSOLE_TLS` | 主控台是否走 HTTPS | `0` | 否 |
| `VPSSRV_AUTH` | 主控台是否要求登入 | `1` | 否 |
| `VPSSRV_PASSWORD_FILE` | 主控台密碼的明文檔，操作者可編輯 | `$PREFIX/admin_password.txt` | 否 |
| `VPSSRV_CERT_DIR` | 自簽憑證位置 | `$PREFIX/certs` | 否 |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | 改用操作者提供的憑證 | — | 否 |
| `VPSSRV_IPERF_PORT` | iperf3 視窗所監聽的連接埠 | `5201` | 否 |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | 預先填入的視窗時長 | `10` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 主控台不得超過的硬上限 | `60` | 否 |
| `VPSSRV_IPERF_ENABLE` | 是否允許開啟視窗 | `1` | 否 |
| `VPSSRV_TRUST_PROXY` | 記錄訪客時是否採信 `X-Forwarded-For` | `0` | 否 |
| `VPSSRV_TRACK_CONNECTIONS` | 輪詢 `/proc/net/tcp[6]` 以記錄所有連接埠的連線 | `1` | 否 |
| `VPSSRV_CONN_POLL_SECONDS` | 輪詢間隔 | `5` | 否 |
| `VPSSRV_MAX_TEST_MB` | 單次測速傳輸量上限（MB） | `200` | 否 |
| `VPSSRV_TEST_SECONDS` | 每個方向的測量時間窗 | `10` | 否 |
| `VPSSRV_WARMUP_SECONDS` | 每個方向開始時被捨棄的暖身時間 | `2` | 否 |
| `VPSSRV_DOWNLOAD_STREAMS` / `VPSSRV_UPLOAD_STREAMS` | 每個方向的並行串流數 | `6` / `3` | 否 |
| `VPSSRV_PING_SAMPLES` | 用於算出延遲數值的往返次數 | `20` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` | `en` | 否 |
| `ANYTLS_PORT`、`ANYTLS_PASSWORD`、`SNI`、`SERVER_IP` | anytls 模組沿用上游的變數名稱 | 見 `.env.example` | 否 |
| `VPSSRV_ANYTLS_CONFIG` | 主控台從哪裡讀取已安裝的節點 | `/etc/vps-server-anytls/config.json` | 否 |
| `VPSSRV_ANYTLS_SERVICE` | 主控台用來檢查節點存活狀態的 unit | `vps-server-anytls.service` | 否 |
| `VPSSRV_ANYTLS_SETUP` | 主控台用來輪替節點憑證的腳本 | `$PREFIX/anytls/setup-anytls.sh` | 否 |

anytls 模組刻意沿用 `Anytsl-Serve` 的變數名稱，而不是改名成
`VPSSRV_ANYTLS_*`：內含的設定產生器會讀取這些變數，改名就意味著
要去修改廠商化進來的程式碼，而這正是廠商化政策想要避免的事。

## 從零開始建置

1. `git clone <repo>` 並 `cd` 進去——驗證：`ls sing-box` 顯示一個約 57 MB 的檔案。
2. `bash install.sh`——安裝程式會詢問要安裝哪些模組、UI 語言、
   是否要對主控台做密碼保護，以及各連接埠。驗證：它會印出一個摘要區塊，
   列出每個已安裝的模組和它的連接埠。
3. `systemctl status vps-server-web`——驗證：`active (running)`。
4. 從另一台機器打開 `http://<ip>/`——驗證：可達性頁面正常渲染，
   並顯示你自己的來源 IP。
5. 從另一台機器打開 `https://<ip>/` 並接受憑證警告——驗證：
   同一個頁面，協定那一行顯示 HTTPS。
6. 打開 `http://<ip>:<console port>/`，登入——驗證：儀表板正常載入，
   顯示 iperf3 控制項且視窗處於關閉狀態。
7. 從主控台開啟一個 5 分鐘的 iperf3 視窗，然後從另一台機器執行
   `iperf3 -c <ip> -p 5201 --json`——驗證：有回報輸送量，
   輸出中也有 `mean_rtt`。
8. 若安裝了 anytls 模組：`systemctl status vps-server-anytls`——
   驗證：`active (running)`；安裝程式的摘要有印出用戶端設定那一行。

## 資料模型 / 檔案配置

```
repo/
├── install.sh                 # module-selecting installer (web / anytls / iperf3)
├── uninstall.sh               # removes the modules it finds
├── app.py                     # the web service: console + public listeners
├── static/                    # LibreSpeed engine (vendored) + own UI assets
├── systemd/
│   └── vps-server-web.service # the anytls unit is not here: setup-anytls.sh
│                              # writes it at install time, so it is never
│                              # shipped and never stale
├── anytls/
│   ├── setup-anytls.sh        # vendored from Anytsl-Serve, renamed units/paths
│   ├── sing-box.version       # which sing-box release the binary below is
│   └── .upstream-version      # records: Anytsl-Serve v1.2.0
├── sing-box                   # vendored amd64 binary
├── .upstream-version          # records: vps-webserver v0.4.1
├── tests/
├── LICENSE                    # GPL-3.0
├── LICENSES/                  # upstream licence texts
└── <the six governance docs + two translated_* trees>
```

SQLite 的 schema 原封不動繼承自 `vps-webserver`：一張 `visits` 資料表，
只保留最近 1000 筆紀錄。

## 已知限制與陷阱

- **綁定 80 和 443 需要 root 權限，且這兩個連接埠本身要沒被佔用。**
  如果 nginx、Apache、Caddy，或另一個 `vps-webserver` 執行個體已經佔用了
  其中一個連接埠，安裝程式會直接拒絕，不會跟它搶。安裝前先用
  `ss -lntp '( sport = :80 or sport = :443 )'` 檢查一下。
- **公開頁面確實是公開的。** 任何猜到或掃到這個 IP 的人都看得到它，
  而每一次這樣的存取都會落進訪客紀錄。這是特意設計的功能，
  但也代表被掃描過的 IP，訪客紀錄會在幾小時內被網路背景雜訊塞滿。
- **Unit 名稱刻意跟上游不同。** `Anytsl-Serve` 安裝的是
  `sing-box-anytls.service`；這個專案安裝的是 `vps-server-anytls.service`，
  以及一個另外命名的二進位檔，因此兩者可以並存。安裝程式仍然會在
  偵測到上游的 unit 正在執行時拒絕繼續，因為同一台主機上有兩個
  anytls inbound，幾乎肯定是失誤而不是本意。
- **`iperf3` 沒有釘死版本。** 它來自發行版，所以版本會隨發行版而異。
  wire protocol 在 3.x 這條線上一直保持穩定，但如果用戶端版本比伺服器
  舊太多，版本交握可能會失敗。
- **anytls 僅限 amd64。** 內含的二進位檔不是多架構的；在 arm64 上，
  安裝程式會直接跳過這個模組並附上說明，而不是安裝一個跑不起來的二進位檔。
- **自簽 TLS 意味著 443 每次都會跳出瀏覽器警告。** 這是預期行為，
  不值得用例外規則或 HSTS 標頭去「修掉」它。
- **重啟會關閉任何開著的 iperf3 視窗。** 這是刻意設計；見生命週期那一節。
- **sing-box 二進位檔已經超過 GitHub 建議的檔案大小。** 約 55 MB，
  超過了 50 MB 的軟性限制，所以每次 push 都會印出一則建議使用
  Git LFS 的「Large files detected」警告。push 仍然會成功；
  硬性上限是 100 MB。未來 sing-box 版本升級最終可能會跨過這個門檻，
  屆時該怎麼辦（改用 LFS，或不再隨附這個二進位檔）應該是一個
  刻意做出的決定，而不是發版當天才被嚇一跳。
- **執行腳本要用 `bash <script>`，不要用 `./<script>`。**
  可執行位元記在 git 索引裡，所以全新的 clone 會帶著它——
  但在 CIFS/SMB 掛載點上的工作副本不會，於是那裡的 `./install.sh`
  會以「Permission denied」失敗。
- **重新廠商化任何可執行檔都會丟失它的權限模式位元。**
  維護者的工作副本掛在 CIFS 上，所以在那裡解壓出來再 `git add`
  的檔案，即使上游是 `100755`，也會被記成 `100644`。這件事已經在
  `sing-box` 二進位檔上發生過一次，並弄壞了整個 anytls 模組。
  重新廠商化之後，用 `git ls-files -s` 檢查，再用
  `git update-index --chmod=+x <path>` 把權限位元找回來——
  單純 `chmod +x` 在那個掛載點上是無效的。
- **直接執行 `setup-anytls.sh` 會輪替它的連接埠與密碼。**
  它會把 `ANYTLS_PORT` 和 `ANYTLS_PASSWORD` 預設成全新的隨機值，
  並在每次執行時重寫 `config.json`，所以手動呼叫它會讓每一個
  照舊值設定好的用戶端都失效。`install.sh` 已經不會這樣做了——
  升級路徑會把兩個值從 `config.json` 讀回來再傳進去——但直接呼叫
  仍然會這樣。要保住節點，就傳入目前的值，兩者都能在主控台的
  anytls 頁面上找到：
  `ANYTLS_PORT=<current> ANYTLS_PASSWORD='<current>' bash anytls/setup-anytls.sh`。
  這是刻意繼承下來的上游行為。`setup-anytls.sh reset` 就是故意
  要輪替它們，主控台上的重設按鈕就是要求這個效果的官方支援方式。
- **主控台的公開位址區塊只有在安裝過 anytls 之後才會出現。**
  `public-ip.txt` 是由 `setup-anytls.sh` 寫入的，所以早於這份檔案存在的
  安裝，在該模組重新安裝之前只會顯示介面位址。這是拒絕在渲染時
  做對外查詢所付出的代價。
- **拆除（teardown）需要用跟安裝時相同的 `PREFIX` 和 `SERVICE_NAME`。**
  沒有設定任何環境變數就執行 `uninstall.sh`，會讀到預設值、
  在那些路徑下找不到東西，並回報「成功」但其實什麼都沒移除。
  安裝程式的結尾那一行會印出填好實際值的完整命令；照著用，
  不要憑記憶自己打。

## 如何擴充

- **新增一個模組**（安裝程式可以選配設定的其他東西）：新增一個
  `<name>/setup-<name>.sh`、一個 `systemd/vps-server-<name>.service`、
  `install.sh` 模組選單裡的一個分支，以及 `uninstall.sh` 裡對應的拆除分支。
  各模組之間不互相呼叫。
- **新增一個主控台頁面**：在 `ConsoleHandler` 裡新增一個路由。
  不要在 `ProbeHandler` 裡加路由——它的路由表幾乎是空的，
  這是一項安全特性，不是疏漏。
- **新增一種語言**：擴充 `app.py` 裡的 `STRINGS` 表和 `install.sh` 裡的
  `msg()` 表，再新增一個 `translated_<lang>/` 目錄樹。
- **新增一種顏色**：在 `static/style.css` 的 `:root` 裡加一個 token，
  *並且*在 `prefers-color-scheme: light` 區塊裡加對應的淺色模式值，
  然後使用這個 token。絕不要在元件規則裡直接寫死十六進位色碼——
  字面值沒辦法跟著主題走，所以它只在被目測校色的那個模式下是對的，
  換一個模式就錯了，而且沒有任何東西會回報這個問題。任何被當作
  填色背景使用的值，都需要一個配對的 `--on-*` 前景色：讀起來適合當文字的值，
  很少同時也適合放在白色文字後面。commit 之前，兩種模式都要對照
  WCAG AA（4.5:1）檢查一遍；`tests/test_app.py::StylesheetTest`
  會強制檢查這件事的結構性那一半，但沒辦法判斷對比度數值。
- **更新一份廠商化的上游程式碼**：從上游的 tag 重新複製過來，
  在同一次 commit 裡更新對應的 `.upstream-version` 檔案，
  並在 `CHANGELOG.md` 裡記下這次更新。絕不要就地手改廠商化進來的程式碼——
  沒有反映回上游的本地修改，會讓下一次更新變成一次無聲的回歸。
