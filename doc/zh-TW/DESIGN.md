---
name: project-design-zh-tw
description: 專案架構與設計限制
metadata:
  version: "1.0.0"
  lang: "zh-TW"
---

# vps-server — 設計

## 多語言

[English](../DESIGN.md) | [简体中文](../zh-CN/DESIGN.md) | **繁體中文(台灣)** | [繁體中文(香港)](../zh-HK/DESIGN.md) | [हिन्दी](../hi/DESIGN.md) | [Español](../es/DESIGN.md) | [العربية](../ar/DESIGN.md) | [Français](../fr/DESIGN.md)

## 文件

- 專案概覽:[README](README.md)

- 設計考量:[DESIGN](DESIGN.md)

- 發行歷史:[LOG](LOG.md)

- 第三方聲明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 設計目標

**v2.0.0 已實作的目標(見[驗收限制][local-link-001]):**

v2.0.0 亦包含實驗性的 frps 與 Lucky 安裝路徑.其行為尚未通過實機驗收;以下目標描述先前已記錄的四個模組.

- 在全新的 Debian/Ubuntu VPS 上安裝一套可選四個模組,提供五項功能的套件(web 模組同時包含公開頁面與私人主控台):
  1. **公開可達性頁面**——一個刻意精簡,不需要驗證的頁面,服務於 TCP
     **80 和 443**,讓任何只拿到 IP 的人都能在瀏覽器裡確認,從自己所在的位置能不能連到這台主機的
     web 連接埠.
  2. **私人主控台**——一個受密碼保護的儀表板,跑在一個持久化的隨機高位連接埠上,
     提供瀏覽器端的上/下載速度測試,以及近期觀察到的入站連線紀錄.
  3. **按需開啟的 iperf3 視窗**——一個頻寬/延遲測試端點,
     **預設關閉**;
     操作者從主控台開啟一個有時限的視窗,時限到了會自動關閉.
  4. **anytls 代理**——一個帶自簽憑證的 sing-box `anytls` inbound,外加 BBR.
  5. **proxy**——可任選 sing-box 的 `vmess`/`vless`/`trojan`/`shadowsocks` 入站,
     共用一個 systemd unit,一份設定及 anytls 模組使用的隨附 sing-box 執行檔.見下文"代理模組".
- 除了發行版套件鏡像之外不需要對外網路存取即可安裝.sing-box 二進位檔已內含在儲存庫中.
- 能與 `vps-webserver` 及 `Anytsl-Serve` 共存於同一台主機,不會在 systemd unit
  名稱,安裝前綴,環境變數前綴或持久化連接埠上發生衝突.

**持續追蹤的目標與目前狀態:**

- [x] 2026-09-19 各節點流量統計,流量上限與到期日:五種代理協定分別追蹤各節點的上傳與下載;達上限或到期後,分別將上傳與下載限速至 1 Mbps.每月或指定時間開始新週期時,清除週期流量並解除限速.實作已於 2026-09-27 通過實機測試.
- [x] 2026-09-19 瀏覽器首次執行設定:目前簽出版本透過 `tools/setup_wizard/setup_wizard.py` 提供短暫有效的設定精靈,觸發條件是互動式安裝程式沒有設定 `VPSSRV_MODULES`.精靈收集語言,模組,連接埠及驗證選項;Shell 安裝程式驗證結果後才執行所選操作.目前簽出版本尚未通過實機驗收.
- [ ] 2026-09-22 完成在主控台顯示 token 及連線資訊的 frps 支援.目前簽出版本已有 frps 安裝選項,但主控台需求仍未界定:須確定 token 資訊是指驗證 token,用戶端設定片段,還是已連線代理清單.
- [ ] 界定 2026-09-22 狀態快照所記更廣泛的 `gdy666/lucky` 功能需求.目前簽出版本已有 Lucky 安裝路徑,但當時未記錄更廣泛的功能清單或驗收準則.
- [x] 完成節點控制的實機驗收:節點有穩定編號,可修改名稱與隱藏的 UUID;可修改連接埠,憑證及 TLS 節點的 SNI;Shadowsocks 的 SNI 顯示為不適用;隨機重設連接埠與憑證時保留 SNI.控制功能已於 2026-09-27 通過實機測試.
- [x] 整個 Web UI 已採用一致的淺色設計系統,涵蓋控制台,公開連通頁面及安裝精靈.2026-09-27 的實作統一了間距與控制項樣式,提供四種可記憶的主題色,隨附字型與圖示,清楚的焦點狀態及響應式版面.

共用 SQLite 鎖的疑慮屬於[尚未解決的測量問題][local-link-002],不是變更架構的指令.歷史已完成工作及驗證記錄見 [LOG][local-link-003].

**非目標**

- **不是 `vps-webserver` 或 `Anytsl-Serve` 的替代品.** 兩者都繼續獨立維護,獨立發行.
  vps-server 是把它們的程式碼廠商化(vendor)進來,而不是匯入或取代它們;
  這麼做在上游變更不同步方面的取捨與緩解方式,見 [決策][local-link-004].
- **沒有 ACME / Let's Encrypt / 網域名稱.** 443 上的 TLS 是自簽憑證.公開頁面的任務
  是回答"你能不能連到這個 IP",而瀏覽器的警告頁面本身就已經回答了這個問題.
  憑證續期和網域依賴對這項任務沒有任何幫助.
- **沒有常駐開啟的 iperf3.** 一個未經驗證,公開的 `iperf3 -s` 會讓任何陌生人
  任意長時間占滿這台主機的上傳頻寬.
- **公開頁面不揭露任何主機資訊.** 沒有主機名稱,沒有核心版本,沒有開機時長,
  沒有服務清單,沒有連接埠清單,沒有 anytls 參數.它只回報:你連到了它,
  它看到的來源 IP,伺服器時鐘,以及你是透過哪一組連接埠/協定連進來的.
- **沒有反向代理,沒有 nginx,沒有容器.** Python 行程自己終結 TLS,
  與 `vps-webserver` 相同.
- **沒有多伺服器測速選單.** 一台主機,就是這台主機.

## 架構

web,anytls 及可選的 proxy 服務以獨立行程執行;web 服務也會建立暫時性的 iperf3 子行程.主控台和公開頁面在同一個 Python 行程內使用不同的監聽器並共用記憶體狀態.只有設定的用戶端流量會抵達這些服務.

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

圖示顯示 web 和 anytls unit;可選的 `vps-server-proxy.service` 在第三個行程中執行多個獨立入站,共用隨附的 sing-box 執行檔,但不共用任何 unit 的狀態.各模組均可獨立選擇;見[代理模組][local-link-005].

### 公開頁面與主控台為何使用不同監聽器

它們的安全姿態是相反的,合併起來會迫使其中一方放棄自己的立場.主控台需要驗證,
放在一個猜不到的連接埠上,就是為了不被隨便發現;公開頁面則**必須**容易被發現,
也**不得**要求密碼.所以:不同的連接埠,不同的請求處理器,不同的路由表.
一個打到 80/443 的請求永遠碰不到主控台的路由,因為 `ProbeHandler` 根本沒有那些路由——
不是因為某個檢查拒絕了它.這正是重點所在:授權檢查可能會有 bug,
但不存在的路由不會.

公開頁面只接受 `GET` 和 `HEAD`,且限於恰好兩個路徑(`/` 和 `/favicon.ico`),
其他一律回應 404.它不讀取查詢字串,不解析請求主體,也不設定任何 cookie.

### 在既有安裝上升級

`install.sh` 會偵測既有安裝,並詢問是否要沿用它的設定.回答"是"會重放
上一次安裝記錄下來的內容;回答"否"則重新詢問所有問題.不論哪種方式,
主控台密碼,持久化的連接埠,憑證以及訪客紀錄都會保留下來——
這些是安裝程式從不觸碰的檔案.

有兩份紀錄,因為它們回答的問題不一樣:

- **systemd unit 的 `Environment=` 那幾行**記錄的是"曾經被設定過什麼".
  重放它們是為了阻止某個曾經選定的設定——例如自訂的公開連接埠,主控台上的 TLS——
  在下次升級時悄悄回退到預設值.
- **`$PREFIX/.install-state`** 記錄的是"已安裝的版本知道些什麼":
  它的版本號,它的模組清單,以及它理解的每一個設定項的名稱.
  unit 無法回答這個問題,因為它只記錄被賦過值的設定,
  完全說明不了哪些設定曾經存在過.

"這個版本新增了什麼"就是靠第二份檔案算出來的:拿這個版本知道的設定
減去戳記清單上有的設定.每一項都會附上它在 `.env.example` 裡的預設值,
按 Enter 就是接受這個預設值.

早於這份戳記存在的安裝,沒有這份清單.安裝程式不會把猜測當成差異呈現,
而是直接說它無法判斷,把 unit 記錄的內容全部沿用下來,並指向重新詢問的路徑.
模組偵測也是同樣降級:沒有戳記時,它就從磁碟上有什麼來推斷模組清單——
web unit,anytls unit,有沒有裝 `iperf3`.

anytls 節點在升級時的保留方式,是把它的連接埠和密碼從 `config.json`
裡讀回來再傳進去.少了這一步,`setup-anytls.sh` 會把兩者都預設成全新的隨機值,
每一個已設定好的用戶端都會在一次例行升級中壞掉——見下方的"已知限制與陷阱",
這一點在*刻意*重新安裝時依然成立.

### 主控台的 anytls 區塊

**目前位於 `/proxy`,不是獨立頁面**(2026-09-22)——anytls 與 proxy 模組的協定合併到同一頁面的原因,見下文"代理模組".`/anytls` 仍存在,但會重新導向至 `/proxy`;`POST /anytls/reset` 不變.移除的只有獨立的 `GET /anytls` 頁面,以及其導覽連結和儀表板圖磚.下文仍描述合併頁面中的 anytls 區塊如何運作.

主控台從 `VPSSRV_ANYTLS_CONFIG` 讀取已安裝的節點,並呈現它的狀態,
外加一份可以直接貼上使用的 Clash 設定與 `anytls://` 連結.

它會寫入的東西只有一項:"重設連接埠與密碼"按鈕,而且連這一項也是委派出去的.
主控台自己不會碰 `config.json`——它會執行 `setup-anytls.sh reset`,
因為這裡的順序很容易搞錯:舊連接埠的防火牆規則必須在新連接埠開啟*之前*
先撤銷,否則每次重設都會留下一條沒有任何行程在監聽的 `ACCEPT` 規則.
這段邏輯歸擁有這個節點的腳本管,而不是分散在兩個地方各寫一份.
重設需要伺服器端驗證的確認核取方塊——標記語言裡的 `required` 阻止的是誤點,
不是非瀏覽器的用戶端——因為輪替憑證會讓每一個已設定好的用戶端在拿到新資訊之前
全部斷線.

它還跑在**這個服務的沙盒之外**,以 `systemd-run --pipe --wait --collect`
啟動的暫時性 unit 形式執行.web unit 設了 `ProtectSystem=strict`,
只有 `ReadWritePaths=$PREFIX`,所以 `/etc` 對它而言是唯讀的,
而重設需要寫入 `/etc/vps-server-anytls` 和一份 unit 檔案.
第一次實際嘗試就是因為這個原因半途死掉——而且是在已經撤銷了舊連接埠的
防火牆規則之後.另一個做法,把 `/etc/systemd/system` 加進
`ReadWritePaths`,會為了讓一個按鈕能用而永久放寬這個長駐服務的寫入權限;
沙盒的價值比這個更高.沒有 systemd-run 的環境下,呼叫會直接進行,
這是對的,因為缺少 `systemd-run` 的環境,正好也是 `install.sh` 省略了
安全強化措施的那些環境.

`setup-anytls.sh reset` 在動防火牆之前也會先檢查自己有沒有寫入權限.
一個在撤銷舊規則之後才失敗的重設,會留下一個正在運作卻進不去的節點,
這比從未啟動過還要糟.

有兩個細節是承重的.**節點密碼會以明文顯示在那個頁面上**,
這之所以可以接受,只是因為那個頁面掛在 `ConsoleHandler` 之下,
在登入之後;`ProbeHandler` 沒有到它的路由,而且有一份測試斷言
公開監聽器對 `/anytls` 回應 404,且絕不含有密碼.以及**伺服器位址
是取自請求的 `Host` 標頭**,而不是查出來的:不管什麼位址連得到主控台,
就能連得到節點,在渲染時做一次對外的 IP 查詢會違反"不對外發起請求"的規則,
而任何需要不同位址的人,複製之後自己改那一行就好.

SNI 完全沒有存在 sing-box 的設定裡——`setup-anytls.sh` 只把它烤進
自簽憑證的 CN 欄位——所以主控台是從憑證裡把它讀回來,
而不是另外保留一份可能會漂移的副本.

### 代理模組

原先待辦清單詢問隨附的 sing-box 是否支援 anytls 之外的協定,或是否需要第二個後端.答案是支援:`vmess`,`vless`,`trojan` 和 `shadowsocks`(2022-blake3-aes-128-gcm)各自通過 `sing-box check`,而且實際執行(不只是驗證設定)確認四者可在單一 `sing-box run` 行程中同時監聽連接埠並接受連線.沒有加入第二個後端.

與 anytls 不同,此模組是**一個 systemd unit(`vps-server-proxy.service`)及一份 `config.json`,
多個同時運作的入站**,而非四份 anytls 模組副本.如此只需監控一個 unit,初次安裝時共用一張自簽憑證，後續新增 TLS 節點各有憑證(shadowsocks 無需憑證),且單一行程中的 `inbounds` 清單適合日後逐節點流量統計.`deploy/proxy/setup-proxy.sh` 是本專案自行編寫的,不是從 Anytsl-Serve 隨附的程式碼.

它與 anytls **共用隨附的 sing-box 執行檔**(`/usr/local/bin/sing-box-vps-server`),不用重複收錄約 57 MB 的執行檔.兩個模組的 `uninstall()` 刪除該檔前,都會檢查*另一個*模組的設定是否仍存在;隨附的 anytls `setup-anytls.sh` 因而新增本機修改,記錄於 `deploy/anytls/.upstream-version`.

`PROXY_PROTOCOLS`(逗號分隔,預設全選)會驗證後存入全域陣列,而不透過 `$(...)` 指令替換輸出:早期版本在 `read -ra x <<< "$(fn)"` 呼叫的函式內驗證,子 shell 的 `exit 1` 只終止子 shell,主腳本卻繼續使用空協定清單,啟動零個入站的服務;類似[決策][local-link-006]記載的 `prompt_new_settings()` 錯誤.各協定連接埠分別來自低於 60000,寬度 5000 的範圍;舊設計從 60000 開始取寬度 10000 的範圍,會使 sing-box 的 `uint16 listen_port` 溢出 65535.這是在五次全新安裝中發現,而不是第一次就發現.與 anytls 的 `preserve_anytls()` 類似,`preserve_proxy()` 會從 `config.json` 讀回每個已安裝協定的連接埠,憑證及*協定集合*,避免重跑 `VPSSRV_MODULES=proxy` 時悄悄增減協定.

主控台 `/proxy` 頁面依已安裝節點顯示一節:連接埠,UUID 或密碼,從各自憑證讀回的 SNI,以及每個偵測到位址的 Clash 條目與分享連結(`vmess://`,`vless://`,`trojan://`,`ss://`).**每個協定都有自己的重設按鈕**:一個 vmess UUID 洩漏不應迫使所有 trojan/vless/shadowsocks 用戶端也重新設定.`setup-proxy.sh reset <protocol>` 只輪替指定協定的連接埠與憑證;`load_installed_vars()` 會先從磁碟讀回*其他*協定的現有值,確保不變.無參數的 `reset` 仍會輪替所有已安裝協定,但只供終端機/腳本使用,主控台不提供.兩種重設都透過沙盒外的 `systemd-run` 執行,與 `anytls_reset()` 一樣,以避開 `ProtectSystem=strict` 限制.共用 unit 的代價是:重設單一協定仍需重新啟動整個服務,其他協定的*連線*也會短暫中斷,儘管憑證不變.

安裝程式起初為每種選定協定建立一個入站。之後，受管理的主控台可為任何已安裝協定建立多個編號節點、個別刪除節點，也容許模組保留但沒有監聽器。節點 ID 保持穩定，並在可見介面中隱藏；每張表單與 Clash 訂閱都以 ID 指定節點，使相同協定的節點互不混淆。連線編輯欄位在卡片原本資訊的位置展開；流量上限、到期時間和重設週期使用另一張表單。新增或刪除節點時，在同一把鎖下更新 sing-box 設定、節點清單、防火牆和 nft 計量狀態，失敗時回復。新建的 TLS 節點各自取得自簽憑證。主控台的內建字型使用 `font-display: optional`，避免首次呈現後才切換字型。

`PortForwardManager.reserved_ports()` 將所有已安裝代理協定的連接埠視為保留埠,與既有的 anytls 及主控台連接埠相同,不允許轉發規則占用.

若已安裝 anytls,主控台的 **/proxy 也顯示 anytls 節點**.操作者認為將兩種代理節點分成 /anytls 和 `/proxy` 是人為區隔.`/anytls` 會重新導向至此;`POST /anytls/reset` 不變,只是完成後導回 `/proxy`.兩個模組的狀態(包括 anytls 的 `public-ip.txt`/`SERVER_IP`)仍互相獨立,各自有重設按鈕,僅共用頁面.兩處位址去重邏輯則集中為一個 `address_entries()` 輔助函式.

### iperf3 視窗生命週期

1. 操作者登入主控台,選擇一個時長(預設 10 分鐘,上限由
   `VPSSRV_IPERF_MAX_MINUTES` 決定),點擊開啟.
2. 主控台以子行程形式產生 `iperf3 -s -p <port>`,在當前生效的防火牆上
   開啟該連接埠,並把截止時間記在記憶體裡.
3. 在視窗開啟期間,**公開頁面**會顯示 iperf3 正在接受連線,在哪個連接埠上,
   還剩多少時間——遠端的測試者需要知道這些資訊,而且它並不敏感:
   這個視窗本來就是刻意打開的.
4. 到了截止時間(或操作者要求,或服務停止)時,子行程會被終止,
   防火牆規則也會被撤銷.

這個視窗只保存在記憶體裡,不落地到磁碟:如果服務掛掉,視窗就沒了,
這是失敗時比較安全的方向.重啟絕不會讓一個開著的視窗死而復生.

延遲是在測試者那一側,從 iperf3 自己的 `--json` 輸出(TCP info 區塊裡的
`mean_rtt`)讀出來的;伺服器端不需要為此寫任何額外程式碼.這個欄位來自核心的
`TCP_INFO`,所以在 Linux 用戶端上會有,在讀不到它的用戶端上就沒有——
Windows 上 Cygwin 版本的 iperf3 會回報輸送量,但沒有 `mean_rtt`.
UDP 模式(`-u`)在任何地方都會回報 jitter 和封包遺失,
是測試者不在 Linux 上時比較通用的答案.

### 連接埠轉發生命週期

一個轉發(forward)會把這台主機上的一個公開 TCP/UDP 連接埠,轉送到透過
Tailscale 或區域網路才能連到的裝置——這是一台有公開 IP 的主機,
能替一台沒有公開 IP 的裝置頂替上場的方式.跟 iperf3 視窗不同,
這是一份設定,不是一次限時借出的上行頻寬:它應該在重啟或重開機之後
依然存在,所以建置方式也不一樣.

1. 操作者從主控台新增一條規則:協定(tcp/udp/both),一個公開連接埠,
   以及目標 `host:port`.`PortForwardManager.add()` 會在動 iptables 之前,
   先拒絕一個這次安裝已經在用的公開連接埠(主控台,公開頁面,iperf3,
   anytls 節點,或另一條轉發規則).
2. 規則裡的每個協定都會變成四條 `iptables` 規則,全部標記
   `-m comment --comment vps-server-portfwd-<id>`,這樣才能跟表格裡
   原本就有的其他規則區分開來:
   - `nat`/`PREROUTING`:把公開連接埠 DNAT 到 `target_host:target_port`.
   - `nat`/`POSTROUTING`:對送往目標的流量做 MASQUERADE,讓回應
     經由這台主機路由回去,而不是走目標自己的預設閘道——目標看到的
     用戶端就是這台主機.
   - `filter`/`FORWARD`:兩個方向各一條 ACCEPT 規則,因為那條鏈上
     的預設 `DROP` policy(例如在 Docker 主機上很常見)否則會悄悄
     吃掉轉發的流量.
3. `net.ipv4.ip_forward` 會在第一條規則需要它的時候被開啟
   (`_ensure_ip_forward()`),而且再也不會被關掉——原因見
   [決策][local-link-007] (2026-09-19).
4. 規則集存在 `PORTFWD_STATE_FILE`(JSON)裡,不只是記在記憶體中.
   每次行程啟動都會呼叫 `PortForwardManager.load()`,它會無條件地
   先撤銷,再重新加入每一條已啟用規則的 iptables 狀態——核心的表格
   在重開機之後什麼都不會記得,但如果這只是服務重啟,可能還留著
   上一次執行的規則,所以不管是哪一種情況,這都是唯一一條必須做對
   的路徑.
5. 乾淨的停止(`SIGTERM`,跟 iperf3 視窗用的是同一個訊號處理器)
   會呼叫 `PortForwardManager.shutdown()`,它會撤銷每一條已啟用
   規則的 iptables 狀態,但不會動 JSON 裡的 `enabled` 旗標——
   重啟服務或重開機時,**必須**靠 `load()` 把它們全部直接帶回來.
   這跟 iperf3 視窗是同一個容錯方向:如果管理這個狀態的行程沒有在跑,
   這個狀態就**不得**悄悄活得比它久.

`target_host` **必須**是一個字面上的 IPv4 位址,不能是主機名稱:
`iptables --to-destination` 接受的是位址,而且這個專案在請求當下
不會對外做 DNS 查詢(見"零第三方執行期依賴"的決策).Tailscale
裝置的 IP 是穩定的,可以在該裝置上用 `tailscale status` 或
`tailscale ip` 查到.

## 設計限制

- 主控台路由必須留在 `ProbeHandler` 之外;驗證不能取代獨立的公開路由表.
- iperf3 必須有時限,關閉視窗或停止服務時必須撤銷防火牆規則.
- 行程啟動時從 JSON 重新套用持久化的轉發規則;正常停止時撤銷執行期規則,但不重設全主機的 `ip_forward` 開關.
- 升級時保留節點憑證與選定設定;輪替時使用擁有節點的設定腳本,並在 web unit 的檔案系統沙盒之外執行.
- 沒有有害延遲的證據,就不要拆開共用的 `_db_lock`:過往以 60 個流量來源進行的測量未重現速度下降.見[錯誤][local-link-008].

## 外部介面

- HTTP/HTTPS:80/443 公開監聽器僅提供可達性頁面;操作者主控台使用另一個持久化連接埠.iperf3 只在經驗證後開啟的限時視窗內監聽.
- 主控台讀取 `/proc/net/tcp[6]` 以記錄入站 TCP 連線;不在公開路由輸出代理密鑰.
- `install.sh` 使用發行版套件管理員,並可選擇在安裝時查詢公開 IP;服務本身在執行期間不發出對外請求.`setup-anytls.sh` 和 `setup-proxy.sh` 管理 sing-box unit 與憑證.iptables 管理暫時開放的 iperf3 與已啟用的轉發;systemd 監督服務,並在 web 沙盒外執行憑證重設.

## 技術組合

| 層 | 選擇 | 版本 | 原因 |
|---|---|---|---|
| 執行環境 | Python,僅使用標準函式庫 | 3.9+ | 繼承自 `vps-webserver`:沒有第三方 Python 套件;發行版管理的直譯器和函式庫仍須安裝安全性更新 |
| HTTP 伺服器 | `http.server.ThreadingHTTPServer` | stdlib | 三個監聽器各僅處理少量請求;框架只會增加負擔 |
| TLS | `ssl` + 由 `openssl` 產生的自簽憑證 | stdlib / distro | 不用網域與 ACME(見非目標) |
| 儲存 | `sqlite3` | stdlib | 訪客紀錄**必須**在重啟後保留 |
| 測速引擎 | LibreSpeed,原樣隨附 | v6.2.1 | LGPL-3.0;已在 `vps-webserver` 中隨附且正常運作 |
| QR 碼產生 | kazuhikoarase/qrcode-generator,原樣隨附 | js2.0.4 | MIT;體積小,無建置步驟,像 LibreSpeed 一樣使用一般 `<script>` 標籤 |
| 頻寬探測 | 發行版的 `iperf3` | 本專案未固定版本 | 測試者用戶端已有的常用工具 |
| 代理核心 | sing-box,隨附執行檔(amd64) | v1.13.14 | GPL-3.0;隨附執行檔可離線安裝 |
| 初始化系統 | systemd | — | 目標作業系統預設值 |
| 安裝程式 | Bash | — | 繼承自兩個上游專案 |

各項被否決的替代方案及選擇理由見[決策][local-link-009];此處不重複.

## 重建需求

### 環境

- 作業系統:Debian 11+ / Ubuntu 20.04+,systemd,以 root 執行.
- 執行環境:Python 3.9+(發行版的 python3 即可).
- 架構:anytls 和 proxy 模組**僅支援 x86-64**,兩者共用隨附的 amd64 sing-box 執行檔.web 和 iperf3 模組不受架構限制.
- 硬體:不需要 GPU;約 150 MB 磁碟空間(其中約 57 MB 為 sing-box 執行檔);一般 VPS 的記憶體容量即可.
- 隨附成品完整性檢查:在儲存庫根目錄執行 `python3 tools/verify_dependencies/verify_dependencies.py`.此指令以 SHA-256 比對五個受版本控制的第三方發行檔與 [dependencies.lock.json][local-link-010],不執行這些檔案.記錄的版本及上游修訂欄位是專案既有紀錄,並非經獨立驗證的上游身分.LibreSpeed 的確切上游修訂未記錄.
- `app.py` 僅使用標準函式庫,因此沒有第三方 Python 套件鎖檔.成品鎖檔不是依賴還原指令,也不是完整的系統套件鎖檔;見 [THIRD_PARTY_NOTICES.md][local-link-011].

### 外部依賴

| 項目 | 來源 | 放置位置 |
|---|---|---|
| `iperf3` | 發行版套件管理員(`apt-get install iperf3`) | 系統路徑 |
| `openssl`,`curl`,`jq`,`iproute2`,`procps`,`iptables`,`ca-certificates` | 發行版套件管理員或主機既有安裝 | 系統路徑 |
| sing-box 執行檔 | 隨本儲存庫提供 | `/usr/local/bin/sing-box-vps-server` |
| LibreSpeed 引擎與 qrcode-generator 函式庫 | 隨本儲存庫提供 | `$PREFIX/static/` |
| TLS 憑證 | 安裝程式首次執行時產生 | `$VPSSRV_CERT_DIR` |

安裝程式從目標 Debian/Ubuntu 的套件儲存庫安裝缺少的系統套件(包括選配的 `iperf3`),未指定確切版本或儲存庫快照.Python,OpenSSL,shell/系統工具及 systemd 也由目標作業系統提供.主機操作者須仰賴所選發行版持續提供安全性維護的套件管道取得更新.此方式避免隨附這些執行檔,但套件版本,雜湊與遞迴依賴的解析可能因主機和時間而異;**尚未實現嚴格且完全可重現的依賴
還原**.若要實現,須另行核准修改安裝程式,並選定發行版/儲存庫快照.鎖檔中的機器可讀 `exclusions` 記錄此邊界,而非虛構的版本固定資訊.

不需要 API 金鑰.web 服務在執行期間不對外查詢公開 IP.安裝程式可選擇對外查詢;失敗只會發出警告.

### 路徑與掛載

| 路徑 | 提供者 | 用途 |
|---|---|---|
| `$PREFIX` | 安裝程式,預設 `/opt/vps-server` | 程式碼,靜態資源,持久化連接埠檔案 |
| `$VPSSRV_DATA_DIR` | 安裝程式,預設 `$PREFIX/data` | `visitors.db`,`session_secret.txt`,`portfwd.json` |
| `$VPSSRV_CERT_DIR` | 安裝程式,預設 `$PREFIX/certs` | 443 使用的自簽憑證及金鑰 |
| `/etc/vps-server-anytls/` | 安裝程式 | sing-box `config.json` 及其自簽憑證 |
| `/etc/vps-server-proxy/` | 安裝程式 | sing-box `config.json`(多個入站)及初始自簽憑證；新節點憑證位於 `/etc/vps-server-nodes/certs/` |

### 設定參考

所有變數都使用 `VPSSRV_` 前綴.這不是美觀考量:`vps-webserver` 使用 `VPSWS_`,`Anytsl-Serve` 使用 `ANYTLS_`;三者可能同時安裝於一台主機,共用前綴會使一個專案的 `.env` 悄悄改變另一個專案的設定.

| 變數 | 意義 | 預設值 | 必要 |
|---|---|---|---|
| `PREFIX` | 安裝根目錄.傳給 `install.sh`/`uninstall.sh`,**不**從 `.env` 讀取;尚未安裝,無法讀取 `.env` 時就須知道此路徑 | `/opt/vps-server` | 否 |
| `VPSSRV_DATA_DIR` | SQLite 與工作階段密鑰 | `$PREFIX/data` | 否 |
| `VPSSRV_HOST` | 所有監聽器的綁定位址 | `0.0.0.0` | 否 |
| `VPSSRV_PUBLIC_HTTP_PORT` | 公開可達性頁面,明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公開可達性頁面,TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 是否提供公開頁面 | `1` | 否 |
| `VPSSRV_CONSOLE_PORT` | 主控台連接埠;`0` 表示產生一次並持久化 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT_FILE` | 記錄產生的主控台連接埠的位置 | `$PREFIX/console_port.txt` | 否 |
| `VPSSRV_CONSOLE_TLS` | 以 HTTPS 提供主控台 | `0` | 否 |
| `VPSSRV_AUTH` | 主控台須登入 | `1` | 否 |
| `VPSSRV_PASSWORD_FILE` | 可由操作者編輯的明文主控台密碼 | `$PREFIX/admin_password.txt` | 否 |
| `VPSSRV_CERT_DIR` | 自簽憑證位置 | `$PREFIX/certs` | 否 |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | 改用操作者提供的憑證 | — | 否 |
| `VPSSRV_IPERF_PORT` | iperf3 視窗的監聽連接埠 | `5201` | 否 |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | 預填視窗時長 | `10` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 主控台不能超過的硬性上限 | `60` | 否 |
| `VPSSRV_IPERF_ENABLE` | 是否允許開啟視窗 | `1` | 否 |
| `VPSSRV_PORTFWD_ENABLE` | 顯示連接埠轉發頁面並允許新增規則 | `1` | 否 |
| `VPSSRV_PORTFWD_MAX_RULES` | 已設定轉發規則的數量上限 | `20` | 否 |
| `VPSSRV_TRUST_PROXY` | 記錄訪客時採信 `X-Forwarded-For` | `0` | 否 |
| `VPSSRV_TRACK_CONNECTIONS` | 輪詢 `/proc/net/tcp[6]` 記錄所有連接埠的連線 | `1` | 否 |
| `VPSSRV_CONN_POLL_SECONDS` | 輪詢間隔 | `5` | 否 |
| `VPSSRV_MAX_TEST_MB` | 單次測速傳輸量上限(MB) | `200` | 否 |
| `VPSSRV_TEST_SECONDS` | 每個方向的測量時長 | `10` | 否 |
| `VPSSRV_WARMUP_SECONDS` | 每個方向起始時捨棄的暖身時長 | `2` | 否 |
| `VPSSRV_DOWNLOAD_STREAMS` / `VPSSRV_UPLOAD_STREAMS` | 各方向的並行串流數 | `6` / `3` | 否 |
| `VPSSRV_PING_SAMPLES` | 計算延遲數值的往返次數 | `20` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | 否 |
| `ANYTLS_PORT`,`ANYTLS_PASSWORD`,`SNI`,`SERVER_IP` | anytls 模組沿用上游名稱 | 見 `.env.example` | 否 |
| `VPSSRV_ANYTLS_CONFIG` | 主控台讀取已安裝節點的位置 | `/etc/vps-server-anytls/config.json` | 否 |
| `VPSSRV_ANYTLS_SERVICE` | 主控台檢查節點運作狀態的 unit | `vps-server-anytls.service` | 否 |
| `VPSSRV_ANYTLS_SETUP` | 主控台輪替節點憑證的腳本 | `$PREFIX/anytls/setup-anytls.sh` | 否 |
| `PROXY_PROTOCOLS`,`PROXY_SNI`,`SERVER_IP` | proxy 模組自己的腳本層級選項;為本專案程式碼,沒有隨附上游的限制,但仍不加前綴,以符合 anytls 腳本與主控台變數的區別 | 見 `.env.example` | 否 |
| `VPSSRV_PROXY_CONFIG` | 主控台讀取已安裝節點集合的位置 | `/etc/vps-server-proxy/config.json` | 否 |
| `VPSSRV_PROXY_SERVICE` | 主控台檢查節點運作狀態的 unit | `vps-server-proxy.service` | 否 |
| `VPSSRV_PROXY_SETUP` | 主控台輪替選定協定憑證的腳本 | `$PREFIX/proxy/setup-proxy.sh` | 否 |

anytls 模組刻意沿用 `Anytsl-Serve` 的變數名稱,而不改為 `VPSSRV_ANYTLS_*`:隨附的設定產生器會讀取這些變數;改名等於修改隨附的上游程式碼,而隨附政策正是為了避免這類修改.

## 從零開始安裝

1. 執行 `git clone <repo>` 並 `cd` 進入儲存庫;驗證:`ls -lh third_party/sing-box/sing-box` 顯示約 57 MB 的檔案.
2. 執行 `bash deploy/install.sh`;互動式執行會啟動暫時的瀏覽器設定精靈,收集模組,介面語言,主控台驗證及連接埠選項.開啟列印的網址並輸入一次性權杖;套用經驗證的選項後,確認終端摘要列出各模組及連接埠.
3. 執行 `systemctl status vps-server-web`;驗證:`active (running)`.
4. 從另一台機器開啟 `http://<ip>/`;驗證:可達性頁面正常顯示,並顯示你的來源 IP.
5. 從另一台機器開啟 `https://<ip>/` 並接受憑證警告;驗證:顯示相同頁面,協定列為 HTTPS.
6. 開啟 `http://<ip>:<console port>/` 並登入;驗證:儀表板載入,顯示已關閉的 iperf3 視窗控制項.
7. 從主控台開啟五分鐘的 iperf3 視窗,再從另一台機器執行 `iperf3 -c <ip> -p 5201 --json`;驗證:輸出包含傳輸速率及 `mean_rtt`.
8. 若已安裝 anytls:執行 `systemctl status vps-server-anytls`;驗證:`active (running)`,且安裝程式摘要曾列印用戶端設定.

## 資料設計

訪客資料庫與 `portfwd.json`(已啟用的轉發規則)持久化於 `$VPSSRV_DATA_DIR`.主控台密碼,選定的連接埠,web 憑證及 `.install-state` 位於 `$PREFIX`;sing-box 模組設定及憑證位於 `/etc/vps-server-anytls/` 與 `/etc/vps-server-proxy/`.見[路徑與掛載][local-link-012].iperf3 的截止時間僅存於記憶體,不會在重啟後保留.

### 資料模型與檔案配置

```
<project root>/
├── snapshots/                 # private snapshots; not part of the Git repository
└── repo/                      # Git working tree; paths below are relative to it
    ├── README.md              # entry point for users and documentation navigation
    ├── config/VERSION         # release version used in checkout
    ├── src/web/app.py         # web service implementation
    ├── deploy/
    │   ├── install.sh         # module-selecting installer
    │   ├── uninstall.sh       # module removal
    │   ├── systemd/vps-server-web.service
    │   ├── anytls/setup-anytls.sh
    │   ├── proxy/setup-proxy.sh
    │   ├── frps/setup-frps.sh
    │   └── lucky/setup-lucky.sh
    ├── static/                # first-party UI assets and vendored browser libraries
    │   └── third_party/
    │       ├── librespeed/    # speedtest.js, speedtest_worker.js
    │       └── qrcode/        # qrcode.js, qrcode-utf8.js
    ├── lang/                  # interface catalogs for web, installers, and tools
    ├── third_party/sing-box/
    │   ├── sing-box           # vendored amd64 binary
    │   ├── sing-box.version   # binary version metadata
    │   └── LICENSE            # original upstream notice
    ├── tools/verify_dependencies/verify_dependencies.py # checks config/dependencies.lock.json from repo root
    ├── config/dependencies.lock.json
    ├── config/upstream-version # records: vps-webserver v0.4.1
    ├── deploy/anytls/.upstream-version # records: Anytsl-Serve v1.2.0
    ├── tests/
    ├── LICENSE                # GPL-3.0
    └── doc/
        ├── DESIGN.md          # architecture, constraints, and tracked goals
        ├── LOG.md             # bugs, dated decisions, verification, release history
        ├── THIRD_PARTY_NOTICES.md
        └── <lang>/            # translated docs (seven language directories)
```

這些僅為簽出目錄路徑:安裝後,應用程式,代理執行檔及瀏覽器資源仍分別位於 `$PREFIX/app.py`,`$PREFIX/sing-box` 和 `$PREFIX/static/`,資源的 HTTP URL 不變.在簽出目錄中,安裝及移除腳本為 `deploy/install.sh` 和 `deploy/uninstall.sh`;已安裝的 Web 入口仍為 `$PREFIX/app.py`.

只有 `repo/` 由 Git 追蹤;`snapshots/` 獨立且為私有.從 [README][local-link-013] 開始,透過 [LOG][local-link-014] 查閱歷史驗證及發行歷史,並查閱[第三方聲明][local-link-015]了解上游資源.文件不會使快照或已安裝主機變成可重現的原始碼簽出版本.

SQLite 結構原樣繼承自 `vps-webserver`:一張 `visits` 資料表,僅保留最近 1000 筆.`portfwd.json` 是一份扁平的 JSON 規則物件清單(`id`,`label`,`protocol`,`public_port`,`target_host`,`target_port`,`enabled`,`created`);見 `PortForwardManager` 在 `src/web/app.py` 中的實作.

## 已知限制與注意事項

- **綁定 80 和 443 需要 root 權限,且這兩個連接埠本身要沒被佔用.**
  如果 nginx,Apache,Caddy,或另一個 `vps-webserver` 執行個體已經佔用了
  其中一個連接埠,安裝程式會直接拒絕,不會跟它搶.安裝前先用
  `ss -lntp '( sport = :80 or sport = :443 )'` 檢查一下.
- **公開頁面確實是公開的.** 任何猜到或掃到這個 IP 的人都看得到它,
  而每一次這樣的存取都會落進訪客紀錄.這是特意設計的功能,
  但也代表被掃描過的 IP,訪客紀錄會在幾小時內被網路背景雜訊塞滿.
- **Unit 名稱刻意跟上游不同.** `Anytsl-Serve` 安裝的是
  `sing-box-anytls.service`;這個專案安裝的是 `vps-server-anytls.service`,
  以及一個另外命名的二進位檔,因此兩者可以並存.安裝程式仍然會在
  偵測到上游的 unit 正在執行時拒絕繼續,因為同一台主機上有兩個
  anytls inbound,幾乎肯定是失誤而不是本意.
- **`iperf3` 沒有釘死版本.** 它來自發行版,所以版本會隨發行版而異.
  wire protocol 在 3.x 這條線上一直保持穩定,但如果用戶端版本比伺服器
  舊太多,版本交握可能會失敗.
- **anytls 和 proxy 僅限 amd64.** 內含的二進位檔不是多架構的;在 arm64 上,
  安裝程式會直接跳過這個模組並附上說明,而不是安裝一個跑不起來的二進位檔.
- **自簽 TLS 意味著 443 每次都會跳出瀏覽器警告.** 這是預期行為,
  不值得用例外規則或 HSTS 標頭去"修掉"它.
- **重啟會關閉任何開著的 iperf3 視窗.** 這是刻意設計;見生命週期那一節.
- **停止服務會撤銷每一條連接埠轉發,即使是已啟用的那些
  也一樣.**
  這是刻意設計,跟 iperf3 視窗對稱;見連接埠轉發生命週期那一節.
  `systemctl restart` 或重開機會把它們直接帶回來——但停在
  `systemctl stop` 狀態不會.
- **`net.ipv4.ip_forward` 會被自動開啟,而且再也不會被關掉.**
  這是一個整台主機共用的單一開關;主機上的其他軟體(例如 Docker)
  可能已經依賴它了,所以移除最後一條轉發不會去動它.如果主機上
  沒有其他東西需要它,就自己手動關掉.
- **一條轉發只涵蓋原生 `iptables` 看得到的範圍.** 如果 `ufw` 或
  `firewalld` 正在運作,且自己也有一個預設拒絕的 `FORWARD` policy,
  它們的鏈會比這個功能附加的規則更早被評估,可能還需要為同一個
  連接埠額外加一條自己的放行規則,流量才過得去.
- **sing-box 二進位檔已經超過 GitHub 建議的檔案大小.** 約 55 MB,
  超過了 50 MB 的軟性限制,所以每次 push 都會印出一則建議使用
  Git LFS 的"Large files detected"警告.push 仍然會成功;
  硬性上限是 100 MB.未來 sing-box 版本升級最終可能會跨過這個門檻,
  屆時該怎麼辦(改用 LFS,或不再隨附這個二進位檔)應該是一個
  刻意做出的決定,而不是發版當天才被嚇一跳.
- **執行腳本要用 `bash <script>`,不要用 `./<script>`.**
  可執行位元記在 git 索引裡,所以全新的 clone 會帶著它——
  但在 CIFS/SMB 掛載點上的工作副本不會,於是那裡的 `./install.sh`
  會以"Permission denied"失敗.
- **重新廠商化任何可執行檔都會丟失它的權限模式位元.**
  維護者的工作副本掛在 CIFS 上,所以在那裡解壓出來再 `git add`
  的檔案,會被記成 `100644`,即使上游是 `100755`.這件事已經在
  `sing-box` 二進位檔上發生過一次,並弄壞了整個 anytls 模組.
  重新廠商化之後,用 `git ls-files -s` 檢查,再用
  `git update-index --chmod=+x <path>` 把權限位元找回來——
  單純 `chmod +x` 在那個掛載點上是無效的.
- **直接執行 `setup-anytls.sh` 會輪替它的連接埠與密碼.**
  它會把 `ANYTLS_PORT` 和 `ANYTLS_PASSWORD` 預設成全新的隨機值,
  並在每次執行時重寫 `config.json`,所以手動呼叫它會讓每一個
  照舊值設定好的用戶端都失效.`install.sh` 已經不會這樣做了——
  升級路徑會把兩個值從 `config.json` 讀回來再傳進去——但直接呼叫
  仍然會這樣.要保住節點,就傳入目前的值,兩者都能在主控台的
  `/proxy` 的 anytls 區塊中找到:
  `ANYTLS_PORT=<current> ANYTLS_PASSWORD='<current>' bash deploy/anytls/setup-anytls.sh`.
  這是刻意繼承下來的上游行為.`setup-anytls.sh reset` 就是故意
  要輪替它們,主控台上的重設按鈕就是要求這個效果的官方支援方式.
- **主控台的公開位址區塊只有明確設定 `SERVER_IP` 時才會
  出現.**
  `get_ip()` 過去會退回對外使用 curl 查詢(先 `api.ip.sb`,再 `ifconfig.me`);此行為已在 2026-09-22 完全移除.在沒有 NAT 的常見 VPS 上,查到的位址與 `get_lan_ips()` 已回報的完全相同,節點頁面會重複顯示同一 IP.若主機確實位於 NAT 後方且未覆寫位址,情況更糟:該節點須經本專案無法確認存在的連接埠轉發,才能以該位址連入.`public-ip.txt` 仍由 `setup-anytls.sh`/`setup-proxy.sh` 寫入,也仍是主控台在呈現時避免對外查詢的唯一方式;現在只有操作者明確傳入 `SERVER_IP`(或 `PROXY_PROTOCOLS` 同層的 `SERVER_IP`)時才會存在,亦即確知位址正確的情況,例如已實際設定連接埠轉發的 NAT.
- **`body` 由 `render_page()` 接收時** **必須**恰好只有一個最上層元素.
  `<main>` 使用 `display: flex`,未覆寫 `flex-direction`;若有多個最上層同級元素(例如每個協定各一個 `<div class="card wide">`),它們會並排而非上下排列.這是先前已發行的 `/proxy` 頁面中真實存在的錯誤,操作者曾回報"版面配置亂掉".每個頁面都以一個外層卡片包住所有內容,再於其中以 `.node-addr` div 放入重複區塊.
- **移除安裝需要使用與安裝時相同的 `PREFIX` 和 `SERVICE_NAME`.**
  沒有設定任何環境變數就執行 `uninstall.sh`,會讀到預設值,
  在那些路徑下找不到東西,並回報"成功"但其實什麼都沒移除.
  安裝程式的結尾那一行會印出填好實際值的完整命令;照著用,
  不要憑記憶自己打.

## 擴充

### 如何擴充

- **新增一個模組**(安裝程式可以選配設定的其他東西):新增一個
  `deploy/<name>/setup-<name>.sh`,其 systemd unit(置於 `deploy/systemd/` 或由設定腳本產生),
  `deploy/install.sh` 模組選單裡的一個分支,以及 `deploy/uninstall.sh` 裡對應的移除分支.
  各模組之間不互相呼叫.
- **新增一個主控台頁面**:在 `ConsoleHandler` 裡新增一個路由.
  不要在 `ProbeHandler` 裡加路由——它的路由表幾乎是空的,
  這是一項安全特性,不是疏漏.
- **新增一種語言**:在每個 `lang/<component>/` 目錄下加入對應的文案檔案,並在 Web 語言選擇器,變更日誌對應表,安裝程式,首次設定精靈及模組指令碼的文案載入程式中註冊語言代碼,再加入相應的 `doc/<BCP47>/` 文件目錄樹.
- **新增一種顏色**:在 `:root` 裡加一個 token(位於 `static/style.css`),
  *並且*在 `prefers-color-scheme: light` 區塊裡加對應的淺色模式值,
  然後使用這個 token.絕不要在元件規則裡直接寫死十六進位色碼——
  字面值沒辦法跟著主題走,所以它只在被目測校色的那個模式下是對的,
  換一個模式就錯了,而且沒有任何東西會回報這個問題.任何被當作
  填色背景使用的值,都需要一個配對的 `--on-*` 前景色:讀起來適合當文字的值,
  很少同時也適合放在白色文字後面.commit 之前,兩種模式都要對照
  WCAG AA(4.5:1)檢查一遍;`tests/test_app.py::StylesheetTest`
  會強制檢查這件事的結構性那一半,但沒辦法判斷對比度數值.
- **更新一份廠商化的上游程式碼**:從上游的 tag 重新複製過來,
  在同一次 commit 裡更新對應的 `.upstream-version` 檔案,
  並在 [LOG.md][local-link-016] 裡記下這次更新.絕不要就地手改廠商化進來的程式碼——
  沒有反映回上游的本地修改,會讓下一次更新變成一次無聲的回歸.

[local-link-001]: LOG.md#目前狀態與驗收限制
[local-link-002]: LOG.md#錯誤
[local-link-003]: LOG.md#已完成工作歷史
[local-link-004]: LOG.md#決策
[local-link-005]: #代理模組
[local-link-006]: LOG.md#決策
[local-link-007]: LOG.md#決策
[local-link-008]: LOG.md#錯誤
[local-link-009]: LOG.md#決策
[local-link-010]: ../../config/dependencies.lock.json
[local-link-011]: THIRD_PARTY_NOTICES.md
[local-link-012]: #路徑與掛載
[local-link-013]: README.md
[local-link-014]: LOG.md
[local-link-015]: THIRD_PARTY_NOTICES.md
[local-link-016]: LOG.md#變更紀錄
