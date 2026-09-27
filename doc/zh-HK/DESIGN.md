---
name: project-design-zh-hk
description: 項目架構與設計限制
metadata:
  version: "1.0.0"
  lang: "zh-HK"
---

# vps-server — 設計

## 多語言

[English](../DESIGN.md) | [简体中文](../zh-CN/DESIGN.md) | [繁體中文(台灣)](../zh-TW/DESIGN.md) | **繁體中文(香港)** | [हिन्दी](../hi/DESIGN.md) | [Español](../es/DESIGN.md) | [العربية](../ar/DESIGN.md) | [Français](../fr/DESIGN.md)

## 文件

- 項目概覽:[README](README.md)

- 設計理據:[DESIGN](DESIGN.md)

- 發佈歷史:[LOG](LOG.md)

- 第三方聲明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 設計目標

**v2.0.0 已實作的目標(見[驗收限制][local-link-001]):**

v2.0.0 亦包含實驗性的 frps 和 Lucky 安裝路徑.其行為尚未通過真實主機驗收;以下目標描述先前已記錄的四個模組.

- 在全新 Debian/Ubuntu VPS 安裝一套工具,以四個可選模組提供五項功能(web 模組包括公開頁面與私人控制台):
  1. **公開連通性頁面** — 在 TCP
     **80 和 443** 提供刻意保持簡潔,毋須驗證的頁面;任何人只要取得 IP,便可用瀏覽器確認所在位置能否連到主機的網頁連接埠.
  2. **私人控制台** — 使用密碼保護,持久保存的隨機高位連接埠上的儀表板,提供瀏覽器上下載速度測試和近期觀察到的入站連線紀錄.
  3. **按需開啟 iperf3 時段** — 頻寬/延遲測試端點,
     **預設關閉**;操作員從控制台開啟限時時段,到期自行關閉.
  4. **anytls 代理** — sing-box `anytls` 入站連線,使用自簽憑證和 BBR.
  5. **proxy** — sing-box `vmess`/`vless`/`trojan`/`shadowsocks` 入站連線的任何子集,共用一個 systemd 服務單位,一份設定,以及 anytls 模組所用的同一個隨附 sing-box 執行檔.見下文"The proxy module".
- 除發行版套件鏡像站外,不需對外網絡連線即可安裝;sing-box 執行檔隨儲存庫提供.
- 與 `vps-webserver`,`Anytsl-Serve` 共存於同一主機,不會在 systemd 服務名稱,安裝前綴,環境變數前綴或持久保存的連接埠上衝突.

**持續追蹤的目標及目前狀態:**

- [x] 2026-09-19 每節點流量統計,數據上限和有效期:五種代理協定分別追蹤每個節點的上載及下載;達上限或到期後,分別把上載及下載限速至 1 Mbps.每月或指定時間開始新週期時,清除週期流量並解除限速.實作已於 2026-09-27 通過真實主機測試.
- [x] 2026-09-19 瀏覽器初次設定:目前檢出版本透過 `tools/setup_wizard/setup_wizard.py` 提供短時間有效的設定精靈,觸發條件是互動安裝程式沒有設定 `VPSSRV_MODULES`.精靈收集語言,模組,連接埠及驗證選項;Shell 安裝程式驗證結果後才執行所選操作.目前檢出版本尚未通過真實主機驗收.
- [ ] 2026-09-22 完成在控制台顯示令牌及連線資訊的 frps 支援.目前檢出版本已提供 frps 安裝選項,但控制台要求仍未界定:須確定令牌資訊是指驗證令牌,用戶端設定片段還是已連線代理清單.
- [ ] 界定 2026-09-22 狀態快照內更廣泛的 `gdy666/lucky` 功能要求範圍.目前檢出版本已提供 Lucky 安裝路徑,但當時沒有記錄更廣泛的功能清單或驗收準則.
- [x] 完成節點控制的主機驗收:節點有穩定編號,可修改名稱及隱藏的 UUID;可修改連接埠,憑證及 TLS 節點的 SNI;Shadowsocks 的 SNI 顯示為不適用;隨機重設連接埠及憑證時保留 SNI.控制功能已於 2026-09-27 通過真實主機測試.
- [x] 整個 Web UI 已採用一致的淺色設計系統,涵蓋控制台,公開連通頁面及安裝精靈.2026-09-27 的實作統一間距和控制項樣式,提供四種可記憶的主題色,隨附字型及圖示,清晰的焦點狀態和響應式版面.

共用 SQLite 鎖的顧慮屬[已知但未解決的量度問題][local-link-002],並非必須更改架構.已完成工作的歷史及驗證紀錄見 [LOG][local-link-003].

**不屬於目標**

- **不取代 `vps-webserver` 或 `Anytsl-Serve`.** 兩者仍獨立維護和發佈.vps-server 隨附其程式碼,而非匯入或取代;此舉接受的版本分歧權衡及緩解措施見[決策][local-link-004].
- **不提供 ACME/Let's Encrypt/網域名稱.** 443 使用自簽憑證.公開頁面只要回答"這個 IP 能否連通";瀏覽器警告頁已能證明連通,網域相依及憑證續期對此無益.
- **不持續執行 iperf3.** 未經驗證的公開 `iperf3 -s` 會讓陌生人任意長時間耗盡主機上傳頻寬.
- **公開頁面不披露主機資料.** 不顯示主機名稱,核心版本,運行時間,服務清單,連接埠清單或 anytls 參數.只顯示是否連通,觀察到的來源 IP,伺服器時鐘及所用的兩個連接埠/協定之一.
- **沒有反向代理,nginx 或容器.** Python 程序自行終止 TLS,與 `vps-webserver` 一樣.
- **沒有多伺服器網速測試選擇器.** 只用本主機一部.

## 架構

web,anytls 和可選 proxy 服務分別以獨立程序運行;web 服務另外啟動短暫運行的 iperf3 子程序.控制台及公開頁面在同一 Python 程序中使用不同監聽器,並共用記憶體內狀態.只有已設定的用戶端流量會到達這些服務.

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

圖中列出 web 和 anytls 服務;可選的 `vps-server-proxy.service` 在第三個程序中執行多個獨立入站連線,共用隨附 sing-box 執行檔但不共用其他服務的狀態.模組可分別選用;見[代理模組][local-link-005].

### 公開頁面與控制台為何使用獨立監聽器

兩者的保安定位相反,合併會迫使其中之一妥協.控制台經驗證並使用難以猜測的連接埠,避免被輕易發現;公開頁面則**必須**容易發現,
而且**不得**要求密碼.因此採用不同連接埠,請求處理器及路由表.到達 80/443 的請求永遠無法到達控制台路由,因為 `ProbeHandler` 沒有這些路由,而非因為檢查拒絕了請求.授權檢查可能有錯誤,不存在的路由則不會.

公開頁面只接受 `GET` 和 `HEAD`,且限於兩個路徑(`/`,`/favicon.ico`),其餘一律回應 404;不讀取查詢字串,不剖析請求內容,也不設定 cookie.

### 在現有安裝上升級

`install.sh` 偵測現有安裝,提供保留設定的選項.選"是"會重播先前安裝所記錄的設定;選"否"則重新詢問.兩者均保留控制台密碼,持久保存的連接埠,憑證和訪客紀錄,因安裝程式不會觸碰這些檔案.

有兩份紀錄,各自回答不同問題:

- **systemd 服務單位的 `Environment=` 行**記錄*設定了甚麼*.重播可防止曾選擇的設定(例如自訂公開連接埠,控制台 TLS)於下次升級時默默回復預設值.
- **`$PREFIX/.install-state`**記錄已安裝版本*認識甚麼*:版本,模組清單及其理解的所有設定名稱.服務單位只記錄賦值過的設定,無法回答有哪些設定存在.

以當前版本認識的設定減去標記列出的設定,即得出"此版本有甚麼新增項目".每項都附上 `.env.example` 的預設值;按 Enter 即可接受.

早於標記檔的安裝沒有此清單.安裝程式不會把猜測當作差異:會說明無法判斷,保留服務單位記錄的所有設定,並指出重新提問的做法.沒有標記時,模組偵測亦會從磁碟推斷:web 服務單位,anytls 服務單位及 `iperf3` 是否已安裝.

升級時讀取 `config.json` 內 anytls 節點的連接埠和密碼,再傳入安裝程式,以保留節點.否則 `setup-anytls.sh` 預設產生新的隨機值,例行升級會令所有已設定用戶端失效;見下文直接*刻意*重新安裝時仍適用的注意事項.

### 控制台的 anytls 區塊

**現時位於 `/proxy`,不再獨立成頁**(2026-09-22);anytls 和代理協定合併頁面的原因見下節.`/anytls` 仍會重新導向 `/proxy`,`POST /anytls/reset` 不變;只移除了獨立的 `GET /anytls` 頁面及其導覽連結/儀表板方格.以下仍描述合併頁面中的 anytls 區塊.

控制台從 `VPSSRV_ANYTLS_CONFIG` 讀取已安裝節點,顯示其狀態,可直接貼上的 Clash 設定及 `anytls://` 連結.

它只進行一項寫入操作:"重設連接埠和密碼"按鈕,而且會交由其他程式處理.控制台不會自行改動 `config.json`,而是執行 `setup-anytls.sh reset`:必須先撤銷舊連接埠的防火牆規則,*然後*才開啟新連接埠,否則每次重設都會留下無人監聽連接埠的 `ACCEPT` 規則.邏輯應屬節點管理腳本,不能分散兩處.重設前必須勾選經伺服器驗證的確認方格:標記內的 `required` 只防誤按,無法阻止非瀏覽器用戶端.更換憑證後所有已設定用戶端須取得新憑證才能使用.

它亦透過 `systemd-run --pipe --wait --collect` 建立暫時服務單位,**在本服務的沙盒之外**執行.web 服務單位使用 `ProtectSystem=strict`,只有 `ReadWritePaths=$PREFIX`;其 `/etc` 為唯讀,而重設須寫入 `/etc/vps-server-anytls` 及服務單位檔案.首次真實嘗試正因如此在中途失敗,而且當時已撤銷舊連接埠的防火牆規則.若改為把 `/etc/systemd/system` 加入 `ReadWritePaths`,只為一個按鈕永久擴大長期運行服務的寫入權限,得不償失.在缺少 `systemd-run` 的環境會直接呼叫;該等環境亦是 `install.sh` 不啟用加固措施的環境,因此做法正確.

`setup-anytls.sh reset` 在接觸防火牆前先確認可寫入.撤銷舊規則後才失敗,會使仍運行的節點無法連入,比重設根本未開始更差.

兩點尤其重要:**節點密碼會以明文顯示在控制台區塊**,只有因為該頁屬登入後的 `ConsoleHandler` 才可接受;`ProbeHandler` 沒有該路由,並有測試確認公開監聽器對 `/anytls` 回傳 404,內容不含密碼.
**伺服器位址取自請求的
`Host` 標頭**而非查詢:能連到控制台的位址也能連到節點;繪製頁面時對外查詢 IP 違反不向外發送請求的規則;如需其他位址,可在複製後自行編輯.

SNI 不儲存在 sing-box 設定內;`setup-anytls.sh` 只把它寫入自簽憑證的 CN,故控制台從憑證讀回,而非維護可能分歧的第二份資料.

### proxy 模組

舊待辦事項問:隨附 sing-box 執行檔是否支援 anytls 以外的協定,抑或需要第二個後端?答案是支援:`vmess`,`vless`,`trojan`,`shadowsocks`(2022-blake3-aes-128-gcm)均通過 `sing-box check`;而且透過實際執行,非僅檢查設定,證實四者可在同一 `sing-box run` 程序中同時綁定連接埠及接受連線.沒有新增第二個後端.

與 anytls 不同,此模組採用**一個 systemd 服務單位(`vps-server-proxy.service`),一份 `config.json`
可有多個同時運行的入站連線**,而非複製四套 anytls.理由:只須監察一個服務單位,初次安裝時三個 TLS 協定共用一份自簽憑證，後續新增 TLS 節點各有憑證(shadowsocks 不需要),而日後的每節點流量統計亦需要一個已以 `inbounds` 陣列表示節點清單的程序.`deploy/proxy/setup-proxy.sh` 是 vps-server 原創,並非隨附上游程式碼;這四種協定均非來自 Anytsl-Serve.

模組**與 anytls 共用隨附 sing-box 執行檔**(`/usr/local/bin/sing-box-vps-server`),不另複製約 57 MB.兩模組的 `uninstall()` 在刪除此檔前均檢查*另一個*模組的設定是否仍存在;anytls 的隨附 `setup-anytls.sh` 因而加入了有紀錄的本地偏差(見 `deploy/anytls/.upstream-version`),因執行檔不再只屬 anytls 可刪除.

`PROXY_PROTOCOLS`(以逗號分隔,預設四種全部)會驗證並放入全域陣列,而非經 `$(...)` 命令替代輸出.早期版本在 `read -ra x <<< "$(fn)"` 呼叫的函式內驗證,當中 `exit 1` 只殺掉替代命令的子 shell;父腳本仍默默繼續,結果協定清單為空,啟動零入站連線的服務.此錯誤與[決策][local-link-006]內的 `prompt_new_settings()` 同類.各協定的連接埠來自 60000 以下互不重疊,寬度 5000 的區間,而非從 60000 開始的 10000 寬區間;後者產生較高埠時會超過 sing-box 的 uint16 `uint16 listen_port` 上限 65535.錯誤是在重複五次全新安裝後發現,非首次安裝.升級保留憑證的方式與 anytls 的 `preserve_anytls()` 一樣:`preserve_proxy()` 從 `config.json` 讀回每種已安裝協定的連接埠,憑證及*協定集合*;重新執行 `VPSSRV_MODULES=proxy` 不會默默加入或刪除協定.

控制台的 `/proxy` 頁面為各已安裝節點顯示連接埠,UUID 或密碼,從各自憑證讀回的 SNI,以及每個偵測到位址對應的 Clash 設定和分享連結(`vmess://`,`vless://`,`trojan://`,`ss://`).**各協定都有自己的重設按鈕**,而非共用"全部重設";操作員指出若只洩漏 vmess UUID,不應強迫所有 trojan/vless/shadowsocks 用戶端重新設定.`setup-proxy.sh reset <protocol>` 只更換該協定的連接埠和憑證;`load_installed_vars()` 先從磁碟讀取所有*其他*協定的現值,以保持不變.不加參數的 `reset` 仍會更換所有已安裝協定,供終端機/腳本使用,不在控制台顯示.兩種方式均經沙盒外的 `systemd-run` 執行,仿照 `anytls_reset()` 以避開 `ProtectSystem=strict`.共用 systemd 服務有一項實際成本:重設單一協定仍會重新啟動整個服務,其他協定的*連線*會短暫中斷,雖然憑證不變.

安裝程式起初為每種選定協定建立一個入站。之後，受管理的控制台可為任何已安裝協定建立多個編號節點、逐個刪除節點，亦容許模組保留但沒有監聽器。節點 ID 保持穩定，在可見介面中隱藏；每張表單及 Clash 訂閱均以 ID 指定節點，令同協定節點互不混淆。連線編輯欄位在卡片原有資訊的位置展開；流量上限、到期時間及重設週期使用另一張表單。新增或刪除節點時，在同一把鎖下更新 sing-box 設定、節點清單、防火牆及 nft 計量狀態，失敗時回復。新建的 TLS 節點各自取得自簽憑證。控制台的內建字型使用 `font-display: optional`，避免首次顯示後才切換字型。

`PortForwardManager.reserved_ports()` 把所有已安裝代理協定的連接埠列為保留,與既有 anytls 節點及控制台連接埠相同;轉發規則不能指向已由代理協定佔用的連接埠.

**控制台的 `/proxy` 頁面亦顯示 anytls 節點**(如有安裝).操作員認為,從其角度兩者都是"代理節點",即使分屬不同獨立後端,分拆頁面也不合理.`/anytls` 會轉到這裏;`POST /anytls/reset` 不變,完成後只改為返回 `/proxy`.兩模組仍保持獨立狀態(anytls 自己的 `public-ip.txt`/`SERVER_IP` 並非代理模組的設定,兩者可不同),重設按鈕亦各自獨立;只共用顯示頁面.

節點頁面列出主機網卡位址及可選的 Tailscale 位址，不再顯示安裝時記錄的公開 IP。

### iperf3 時段生命週期

1. 操作員登入控制台,選擇時長(預設 10 分鐘,受 `VPSSRV_IPERF_MAX_MINUTES` 限制),按開啟.
2. 控制台啟動 `iperf3 -s -p <port>` 子程序,在目前啟用的防火牆開放連接埠,於記憶體記錄截止時間.
3. 時段開啟期間,**公開頁面**顯示 iperf3 正接受連線,連接埠和剩餘時間;遠端測試者需要知道,且刻意公開的時段不屬敏感資訊.
4. 到期,操作員要求關閉或服務停止時,終止子程序並撤銷防火牆規則.

時段儲於記憶體而非磁碟;服務故障時即失效,屬安全的故障方向.重新啟動絕不恢復開啟的時段.

延遲從測試者一方 iperf3 的 `--json` 輸出 TCP 資訊區塊 `mean_rtt` 讀取,伺服器無須加程式碼.欄位來自核心 `TCP_INFO`,Linux 用戶端可提供;不能讀取的用戶端則沒有,例如 Windows 上 Cygwin 的 iperf3 只報吞吐量,不報 `mean_rtt`.UDP 模式(`-u`)在各平台均報抖動及遺失率,適合非 Linux 測試者.

所選連接埠另外儲存在應用程式資料目錄。只可在時段關閉時從控制台修改；儲存前會檢查有否與已安裝服務、連接埠轉發或現有監聽連接埠衝突。

### 連接埠轉發生命週期

轉發把本主機公開的 TCP/UDP 連接埠轉送至透過 Tailscale 或 LAN 連接的裝置,使有公開 IP 的主機代替沒有公開 IP 的裝置.與 iperf3 時段不同,這是設定,不是限時借出上傳頻寬:預期重新啟動服務或主機後繼續存在,故實作方式不同.

1. 操作員從控制台加入規則:協定(tcp/udp/兩者),公開連接埠及目標 `host:port`.`PortForwardManager.add()` 在接觸 iptables 前拒絕此安裝已使用的公開連接埠(控制台,公開頁面,iperf3,anytls 節點或其他轉發).
2. 每個協定產生四條 `iptables` 規則,全部標上 `-m comment --comment vps-server-portfwd-<id>`,以區分表內其他規則:
   - `nat`/`PREROUTING`:DNAT 公開連接埠至 `target_host:target_port`.
   - `nat`/`POSTROUTING`:對目標流量使用 MASQUERADE,使回應經此主機返回,而非走目標自己的預設閘道;目標會把本主機視為用戶端.
   - `filter`/`FORWARD`:雙向各加一條 ACCEPT,否則此鏈預設為 `DROP` 時(例如 Docker 主機)會默默丟棄轉發流量.
3. 首次有規則需要時開啟 `net.ipv4.ip_forward`(`_ensure_ip_forward()`),之後不自動關閉;原因見[決策][local-link-007] (2026-09-19).
4. 規則集合存於 `PORTFWD_STATE_FILE`(JSON),不只存記憶體.每次程序啟動均呼叫 `PortForwardManager.load()`,無條件撤銷並重新加入每條已啟用規則的 iptables 狀態:重新開機後核心的表不保留規則,單純重啟服務時表又可能保留舊規則;此路徑兩種情況都須正確.
5. 正常停止(`SIGTERM`,與 iperf3 時段使用相同訊號處理器)呼叫 `PortForwardManager.shutdown()`,撤銷所有已啟用規則的 iptables 狀態,但不改 JSON 的 `enabled` 旗標;服務或主機重啟時**必須**經 `load()` 立即恢復.安全故障方向與 iperf3 時段一致:
管理程序未運行時,狀態**不得**默默留存.

`target_host` **必須**是 IPv4 字面位址,而非主機名稱:`iptables --to-destination` 接受位址,本項目在請求時不會向外查詢 DNS(見"Zero third-party runtime dependencies"決策).Tailscale 裝置的 IP 固定,可在裝置上以 `tailscale status` 或 `tailscale ip` 查看.

## 設計限制

- 控制台路由不可加入 `ProbeHandler`;驗證不能取代獨立的公開路由表.
- iperf3 須限時運行,在關閉或停止時移除防火牆規則.
- 程序啟動時從 JSON 重套持久保存的轉發;正常停止時撤銷執行期規則,但不重設主機層面的 `ip_forward` 開關.
- 升級時保留節點憑證及已選設定;在 web 服務單位檔案系統沙盒外透過所屬安裝腳本更換憑證.
- 沒有證明延遲有害的證據,不可拆開共用 `_db_lock`:歷史上 60 個灌流用戶端的量度未重現變慢;見[問題][local-link-008].

## 外部介面

- HTTP/HTTPS:80/443 公開監聽器只提供連通性頁面;操作員控制台使用持久保存的獨立連接埠;iperf3 只在經驗證後開啟的限時時段監聽.
- 控制台讀取 `/proc/net/tcp[6]` 記錄入站 TCP 連線;不透過公開路由輸出代理機密.
- `install.sh` 使用發行版套件管理器,並可於安裝時選擇查詢公開 IP;服務本身執行時不向外發送請求.`setup-anytls.sh` 和 `setup-proxy.sh` 管理 sing-box 服務單位及憑證.iptables 管理暫時開放的 iperf3 埠及已啟用的轉發;systemd 監督服務,並於 web 沙盒之外執行憑證重設.

## 技術組合

| 層面 | 選擇 | 版本 | 原因 |
|---|---|---|---|
| 執行環境 | Python,僅使用標準函式庫 | 3.9+ | 繼承自 `vps-webserver`:沒有第三方 Python 套件;發行版管理的直譯器及函式庫仍須安裝安全更新 |
| HTTP 伺服器 | `http.server.ThreadingHTTPServer` | stdlib | 三個監聽器,各自請求量少;框架純屬額外負擔 |
| TLS | `ssl` 加 `openssl` 產生的自簽憑證 | stdlib/發行版 | 沒有網域或 ACME(見不屬於目標) |
| 儲存 | `sqlite3` | stdlib | 訪客紀錄**必須**在重啟後保留 |
| 網速測試引擎 | LibreSpeed,隨附且不修改 | v6.2.1 | LGPL-3.0;已在 `vps-webserver` 隨附並正常運作 |
| QR 碼繪製 | kazuhikoarase/qrcode-generator,隨附且不修改 | js2.0.4 | MIT;體積小,無建構步驟,與 LibreSpeed 一樣使用普通 `<script>` 標籤 |
| 頻寬探測 | 發行版提供的 `iperf3` | 本項目未鎖定 | 測試者用戶端已有的事實標準工具 |
| 代理核心 | sing-box,隨附執行檔(amd64) | v1.13.14 | GPL-3.0;隨附執行檔令安裝可離線完成 |
| 初始化 | systemd | — | 目標作業系統預設 |
| 安裝程式 | Bash | — | 繼承自兩個上游項目 |

遭否決的方案及各選擇的原因見[決策][local-link-009],毋須在此重述.

## 重現要求

### 環境

- 作業系統:Debian 11+/Ubuntu 20.04+,systemd,以 root 身份執行
- 執行環境:Python 3.9+(發行版 python3 足夠)
- 架構:anytls 和 proxy **只支援 x86-64**,兩者均使用同一個隨附 amd64 sing-box 執行檔;web 和 iperf3 不受架構限制.
- 硬件:無須 GPU;約 150 MB 磁碟(其中約 57 MB 為 sing-box 執行檔);一般 VPS 的記憶體容量均可.
- 隨附檔案完整性檢查:從儲存庫根目錄執行 `python3 tools/verify_dependencies/verify_dependencies.py`.該指令不執行檔案,而是以 SHA-256 比較五個受追蹤的第三方發佈檔案與 [dependencies.lock.json][local-link-010].版本及上游修訂欄位來自先前項目紀錄,不是獨立核實的上游身份;LibreSpeed 的準確上游修訂未記錄.
- `app.py` 使用標準函式庫,故沒有第三方 Python 套件鎖定檔.檔案鎖定檔不是還原相依套件的指令,也不是完整系統套件鎖定檔;見 [THIRD_PARTY_NOTICES.md][local-link-011].

### 外部依賴

| 項目 | 來源 | 放置位置 |
|---|---|---|
| `iperf3` | 發行版套件管理器(`apt-get install iperf3`) | 系統路徑 |
| `openssl`,`curl`,`jq`,`iproute2`,`procps`,`iptables`,`ca-certificates` | 發行版套件管理器或主機現有安裝 | 系統路徑 |
| sing-box 執行檔 | 隨本儲存庫提供 | `/usr/local/bin/sing-box-vps-server` |
| LibreSpeed 引擎及 qrcode-generator 函式庫 | 隨本儲存庫提供 | `$PREFIX/static/` |
| TLS 憑證 | 安裝程式在首次運行時產生 | `$VPSSRV_CERT_DIR` |

安裝程式從目標 Debian/Ubuntu 套件庫安裝缺少的系統套件(包括可選 `iperf3`),但不選定準確版本或儲存庫快照.Python,OpenSSL,shell/系統工具和 systemd 亦由目標作業系統提供.主機操作員依賴所選發行版持續維護安全性的套件渠道取得更新.這避免隨附執行檔,但套件版本,雜湊及遞迴相依套件的解析可因主機及時間而異;**尚未達成嚴格,完全可重現的相依套件
還原**.如要達成,須另外批准更改安裝程式,並選定發行版/儲存庫快照.鎖定檔內機器可讀的 `exclusions` 記錄這項界限,而非虛構的版本鎖定.

沒有 API 金鑰.web 服務執行時不會向外查詢公開 IP.安裝程式可選擇對外查詢,失敗只作警告.

### 路徑與掛載

| 路徑 | 提供者 | 用途 |
|---|---|---|
| `$PREFIX` | 安裝程式,預設 `/opt/vps-server` | 程式碼,靜態檔案,持久保存的連接埠檔案 |
| `$VPSSRV_DATA_DIR` | 安裝程式,預設 `$PREFIX/data` | `visitors.db`,`session_secret.txt`,`portfwd.json` |
| `$VPSSRV_CERT_DIR` | 安裝程式,預設 `$PREFIX/certs` | 443 的自簽憑證及私鑰 |
| `/etc/vps-server-anytls/` | 安裝程式 | sing-box `config.json` 及其自簽憑證 |
| `/etc/vps-server-proxy/` | 安裝程式 | sing-box `config.json`(多個入站)及初始自簽憑證；新節點憑證位於 `/etc/vps-server-nodes/certs/` |

### 設定參考

所有變數使用 `VPSSRV_` 前綴.這不是外觀修飾:`vps-webserver` 使用 `VPSWS_`,`Anytsl-Serve` 使用 `ANYTLS_`;三者可安裝於同一主機,若共用前綴,一個項目的 `.env` 可默默改動另一項目的設定.

| 變數 | 用途 | 預設值 | 必需 |
|---|---|---|---|
| `PREFIX` | 安裝根目錄.傳入 `install.sh`/`uninstall.sh`,**不**從 `.env` 讀取;尚未有 `.env` 的安裝前已需要此路徑 | `/opt/vps-server` | 否 |
| `VPSSRV_DATA_DIR` | SQLite 及工作階段機密 | `$PREFIX/data` | 否 |
| `VPSSRV_HOST` | 所有監聽器的綁定位址 | `0.0.0.0` | 否 |
| `VPSSRV_PUBLIC_HTTP_PORT` | 公開連通性頁面,明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公開連通性頁面,TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 是否提供公開頁面 | `1` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台連接埠;`0` 表示產生一次並持久保存 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT_FILE` | 記錄產生的控制台連接埠的位置 | `$PREFIX/console_port.txt` | 否 |
| `VPSSRV_CONSOLE_TLS` | 透過 HTTPS 提供控制台 | `0` | 否 |
| `VPSSRV_AUTH` | 控制台必須登入 | `1` | 否 |
| `VPSSRV_PASSWORD_FILE` | 可由操作員編輯的明文控制台密碼 | `$PREFIX/admin_password.txt` | 否 |
| `VPSSRV_CERT_DIR` | 自簽憑證位置 | `$PREFIX/certs` | 否 |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | 改用操作員提供的憑證 | — | 否 |
| `VPSSRV_IPERF_PORT` | iperf3 時段監聽的連接埠 | `5201` | 否 |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | 預填的時段長度 | `10` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台不能超過的硬性上限 | `60` | 否 |
| `VPSSRV_IPERF_ENABLE` | 是否容許開啟時段 | `1` | 否 |
| `VPSSRV_PORTFWD_ENABLE` | 顯示連接埠轉發頁面及容許新增轉發 | `1` | 否 |
| `VPSSRV_PORTFWD_MAX_RULES` | 可設定轉發數目上限 | `20` | 否 |
| `VPSSRV_TRUST_PROXY` | 記錄訪客時信任 `X-Forwarded-For` | `0` | 否 |
| `VPSSRV_TRACK_CONNECTIONS` | 輪詢 `/proc/net/tcp[6]` 記錄所有連接埠連線 | `1` | 否 |
| `VPSSRV_CONN_POLL_SECONDS` | 輪詢間距 | `5` | 否 |
| `VPSSRV_MAX_TEST_MB` | 單次速度測試傳輸的 MB 上限 | `200` | 否 |
| `VPSSRV_TEST_SECONDS` | 每個方向的量度時段 | `10` | 否 |
| `VPSSRV_WARMUP_SECONDS` | 每個方向開始時捨棄的預熱秒數 | `2` | 否 |
| `VPSSRV_DOWNLOAD_STREAMS` / `VPSSRV_UPLOAD_STREAMS` | 每方向並行串流數 | `6` / `3` | 否 |
| `VPSSRV_PING_SAMPLES` | 計算延遲所用的往返樣本 | `20` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | 否 |
| `ANYTLS_PORT`, `ANYTLS_PASSWORD`, `SNI`, `SERVER_IP` | anytls 模組保留上游變數名稱 | 見 `.env.example` | 否 |
| `VPSSRV_ANYTLS_CONFIG` | 控制台讀取已安裝節點的位置 | `/etc/vps-server-anytls/config.json` | 否 |
| `VPSSRV_ANYTLS_SERVICE` | 控制台檢查節點狀態的服務單位 | `vps-server-anytls.service` | 否 |
| `VPSSRV_ANYTLS_SETUP` | 控制台更換節點憑證所用腳本 | `$PREFIX/anytls/setup-anytls.sh` | 否 |
| `PROXY_PROTOCOLS`, `PROXY_SNI`, `SERVER_IP` | proxy 模組腳本層面的設定;雖為原創,不受隨附上游限制,仍維持無前綴,以符合 anytls 腳本與控制台的區分 | 見 `.env.example` | 否 |
| `VPSSRV_PROXY_CONFIG` | 控制台讀取已安裝節點集合的位置 | `/etc/vps-server-proxy/config.json` | 否 |
| `VPSSRV_PROXY_SERVICE` | 控制台檢查節點狀態的服務單位 | `vps-server-proxy.service` | 否 |
| `VPSSRV_PROXY_SETUP` | 控制台更換選定協定憑證所用腳本 | `$PREFIX/proxy/setup-proxy.sh` | 否 |

anytls 模組刻意保留 `Anytsl-Serve` 的變數名稱,而不改為 `VPSSRV_ANYTLS_*`:隨附的設定產生器使用這些名稱,重新命名便須修改隨附上游程式碼,與隨附政策的目的相反.

## 從零開始安裝

1. `git clone <repo>` 並 `cd` 進入;驗證:`ls -lh third_party/sing-box/sing-box` 顯示約 57 MB 檔案.
2. `bash deploy/install.sh`;互動執行會啟動暫時的瀏覽器設定精靈,收集模組,介面語言,控制台驗證及連接埠選項.開啟顯示的網址並輸入一次性權杖;套用經驗證的選項後,確認終端摘要列出各模組及連接埠.
3. `systemctl status vps-server-web`;驗證:`active (running)`.
4. 從另一部機器開啟 `http://<ip>/`;驗證:連通性頁面顯示自己的來源 IP.
5. 從另一部機器開啟 `https://<ip>/` 並接受憑證警告;驗證:同一頁面,協定顯示 HTTPS.
6. 開啟 `http://<ip>:<console port>/` 並登入;驗證:儀表板已載入,顯示關閉中的 iperf3 控制項.
7. 從控制台開啟五分鐘 iperf3 時段,再從另一部機器執行 `iperf3 -c <ip> -p 5201 --json`;驗證:報告吞吐量,輸出包含 `mean_rtt`.
8. 如安裝了 anytls:`systemctl status vps-server-anytls`;驗證:`active (running)`,安裝摘要列印用戶端設定行.

## 資料設計

訪客資料庫與 `portfwd.json`(已啟用的轉發規則)保存在 `$VPSSRV_DATA_DIR`.控制台密碼,選定連接埠,web 憑證及 `.install-state` 位於 `$PREFIX`;sing-box 模組設定與憑證位於 `/etc/vps-server-anytls/` 和 `/etc/vps-server-proxy/`.見[路徑及掛載][local-link-012].iperf3 截止時間只存記憶體,重啟後不保留.

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

這些只屬檢出目錄路徑:安裝後,應用程式,代理執行檔及瀏覽器資源仍分別位於 `$PREFIX/app.py`,`$PREFIX/sing-box` 及 `$PREFIX/static/`,資源的 HTTP URL 不變.在檢出目錄中,安裝及移除腳本為 `deploy/install.sh` 和 `deploy/uninstall.sh`;已安裝的 Web 入口仍為 `$PREFIX/app.py`.

只有 `repo/` 由 Git 追蹤;`snapshots/` 獨立且屬私人資料.從 [README][local-link-013] 開始;歷史驗證及版本歷史見 [LOG][local-link-014];上游檔案見[第三方聲明][local-link-015].文件不會把快照或已安裝主機變成可重現的原始碼 checkout.

SQLite 綱要原封不動繼承自 `vps-webserver`:一個 `visits` 表,僅保留最近 1000 行.`portfwd.json` 是平面 JSON 規則物件清單(`id`,`label`,`protocol`,`public_port`,`target_host`,`target_port`,`enabled`,`created`);見 `PortForwardManager` 在 `src/web/app.py` 內的實作.

## 已知限制與注意事項

- **綁定 80 和 443 須有 root 權限,且連接埠沒有被佔用.** 如 nginx,Apache,Caddy 或其他 `vps-webserver` 執行個體已使用其中一埠,安裝程式會拒絕,而非爭用.安裝前執行 `ss -lntp '( sport = :80 or sport = :443 )'` 檢查.
- **公開頁面確實公開.** 任何猜到或掃描 IP 的人都能看到頁面,其每次存取亦會進入訪客紀錄.這是設計功能,但被掃描的 IP 的訪客紀錄可在數小時內充滿互聯網背景雜訊.
- **服務單位名稱刻意與上游不同.** `Anytsl-Serve` 安裝 `sing-box-anytls.service`;本項目安裝 `vps-server-anytls.service` 及另一名稱的執行檔,兩者可共存.但若上游服務單位正在運行,安裝程式仍會拒絕:同一主機有兩個 anytls 入站連線幾乎肯定是失誤而非預期.
- **`iperf3` 沒有鎖定版本.** 它來自發行版,版本隨發行版而異.3.x 系列的線路協定一直穩定,但用戶端如遠比伺服器舊,版本協商仍可能失敗.
- **anytls 和 proxy 僅支援 amd64.** 隨附執行檔不支援多架構;arm64 上安裝程式會解釋並略過模組,而非安裝無法執行的檔案.
- **自簽 TLS 表示每次存取 443 都有瀏覽器警告.** 此屬預期,不值得以例外或 HSTS 標頭"修正".
- **重新啟動會關閉所有開啟中的 iperf3 時段.** 刻意如此;見生命週期一節.
- **停止服務會撤銷所有轉發,包括已啟用的
  規則.** 刻意與 iperf3 時段對稱;見連接埠轉發生命週期.`systemctl restart` 或重新開機會立即恢復;執行 `systemctl stop` 並保持停止則不會.
- **`net.ipv4.ip_forward` 會自動開啟且不自動關閉.** 此為主機共用開關,其他軟件(例如 Docker)可能依賴它;移除最後一條轉發也不觸碰.若主機沒有其他用途,須自行關閉.
- **轉發只涵蓋原始 `iptables` 看得到的流量.** 如 `ufw` 或 `firewalld` 啟用,並以自己的 `FORWARD` 鏈採用預設拒絕策略,該等鏈會在此功能附加的規則前執行;流量要通過,仍可能須為相同連接埠另加允許規則.
- **sing-box 執行檔超過 GitHub 建議檔案大小.** 約 55 MB 已超過 50 MB 軟上限,每次 push 都會顯示"Large files detected"及 Git LFS 建議,但仍能 push;硬上限為 100 MB.將來升級 sing-box 可能越過硬上限,屆時應刻意決定是否用 LFS 或不再隨附執行檔,而非到發佈日才驚覺.
- **以 `bash <script>` 而非 `./<script>` 執行腳本.** Git 索引記錄了可執行位元,新 clone 可用;但 CIFS/SMB 掛載的工作副本不會保留,當中的 `./install.sh` 會因"Permission denied"失敗.
- **重新隨附任何可執行檔會遺失其模式位元.** 維護者的工作副本位於 CIFS,解壓後以 `git add` 加入的檔案會記為 `100644`,即使上游為 `100755`.`sing-box` 執行檔曾因此令整個 anytls 模組故障.重新隨附後用 `git ls-files -s` 檢查,以 `git update-index --chmod=+x <path>` 恢復;該掛載上的 `chmod +x` 並無效用.
- **直接執行 `setup-anytls.sh` 會更換連接埠和密碼.** 它每次都為 `ANYTLS_PORT` 和 `ANYTLS_PASSWORD` 預設新的隨機值並重寫 `config.json`,令先前設定的所有用戶端失效.`install.sh` 升級時會從 `config.json` 讀回並傳入兩者,因此不再如此;直接呼叫仍然會.如要保留節點,傳入 `/proxy` 頁面的 anytls 區塊所列現值:`ANYTLS_PORT=<current> ANYTLS_PASSWORD='<current>' bash deploy/anytls/setup-anytls.sh`.此為刻意繼承的上游行為.`setup-anytls.sh reset` 是刻意更換,控制台重設按鈕是受支援的操作方式.
- **節點頁面列出網卡及 Tailscale 位址。** 舊的安裝時公開位址區塊已移除：它在 VPS 上重複顯示網卡位址，在 NAT 後亦可能誤導使用者。安裝程式仍可為設定腳本記錄 `public-ip.txt`；控制台不再讀取它。
- **`body` 傳給 `render_page()` 時** **必須**剛好只有一個頂層元素. `<main>` 是 `display: flex` 且沒有覆寫 `flex-direction`,多個頂層同層元素(例如每協定一個 `<div class="card wide">`)會並排而非垂直堆疊;早期 `/proxy` 頁面確曾發佈此錯誤,操作員報告"layout is messed up".各頁以單一外層卡片包裹所有內容,重複區塊放於其中的 `.node-addr` div.
- **移除時須使用安裝時相同的 `PREFIX` 和 `SERVICE_NAME`.** `uninstall.sh` 未設環境變數時使用預設值,如該等路徑無檔案,會報告成功但實際甚麼都沒移除.安裝摘要末行印出填好數值的準確指令,應使用該指令而非憑記憶輸入.

## 擴充

### 擴充方法

- **新增模組**(安裝程式可選擇設定的另一項功能):加入 `deploy/<name>/setup-<name>.sh`,其 systemd 服務單位(隨 `deploy/systemd/` 提供或由安裝腳本產生),`deploy/install.sh` 模組選單分支,以及 `deploy/uninstall.sh` 清理分支.模組互不呼叫.
- **新增控制台頁面**:在 `ConsoleHandler` 加入路由.不要在 `ProbeHandler` 加路由;其路由表幾乎為空是保安特性,而非疏忽.
- **新增語言**:在每個 `lang/<component>/` 目錄下加入對應的文案檔案,並在 Web 語言選擇器,變更記錄對應表,安裝程式,初次設定精靈及模組腳本的文案載入器中登記語言代碼,然後加入相應的 `doc/<BCP47>/` 文件目錄樹.
- **新增顏色**:在 `:root` 中(位於 `static/style.css`) *以及* `prefers-color-scheme: light` 區塊加入對應變數,然後使用該變數.不要在組件規則直接寫十六進制值;字面值不會跟隨佈景,因此只會在目測當時的模式正確,另一模式則錯誤,亦不會收到提示.作為填滿背景的顏色須配有 `--on-*` 前景色:適合文字的值很少適合作為白色文字背景.提交前對兩種模式檢查 WCAG AA(4.5:1);`tests/test_app.py::StylesheetTest` 只檢查結構,不能判斷對比度.
- **更新隨附上游程式碼**:從上游標籤重新複製,在同一 commit 更新相應 `.upstream-version`,並在 [LOG.md][local-link-016] 記錄版本更新.切勿原地手動修改隨附程式碼;未反映在上游的本地更改,會在下次更新時默默倒退.

[local-link-001]: LOG.md#目前狀態與驗收限制
[local-link-002]: LOG.md#錯誤
[local-link-003]: LOG.md#已完成工作歷史
[local-link-004]: LOG.md#決策
[local-link-005]: #proxy-模組
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
[local-link-016]: LOG.md#變更記錄
