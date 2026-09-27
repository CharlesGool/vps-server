---
name: project-log-zh-hk
description: 項目決策,限制,錯誤與變更
metadata:
  version: "1.0.0"
  lang: "zh-HK"
---

# vps-server — 紀錄

本文彙集已知問題,決策,歷史工作,當前驗收限制和已發佈變更.過往測試的敍述並非本次文件遷移重新執行的測試.

## 多語言

[English](../LOG.md) | [简体中文](../zh-CN/LOG.md) | [繁體中文(台灣)](../zh-TW/LOG.md) | **繁體中文(香港)** | [हिन्दी](../hi/LOG.md) | [Español](../es/LOG.md) | [العربية](../ar/LOG.md) | [Français](../fr/LOG.md)

## 文件

- 項目概覽:[README](README.md)

- 設計理據:[DESIGN](DESIGN.md)

- 發佈歷史:[LOG](LOG.md)

- 第三方聲明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 錯誤

- [ ] 2026-09-12 決定是否需要拆分共用的 `_db_lock`:每次公開頁面存取都會取得整個程序共用的鎖,並同步寫入 SQLite;控制台亦共用此鎖,理論上匿名灌流可能令經驗證的頁面變慢.**已量度但未重現**:60 個同時灌流用戶端下控制台延遲為 0.4–0.6 毫秒,與閒置時相同.記錄此機制以免日後當作新問題重新發現;未有顯示損害的量度前,不應重構架構.

舊狀態快照沒有記錄其他阻礙運作的問題;啟動/停止時的訊號邊界,只有 iperf3 的安裝組合和登入速率限制已在 `feat/hardening-batch` 修正,但該分支仍待合併/審查.這並非聲稱已在真實主機重新驗證當前分支.

## 限制

- 自動檢查已核對文案鍵名,佔位符及文件結構,但新增譯文尚未經獨立的母語審閱.
- 正在使用的源碼檢出目錄根部可能包含被 Git 忽略的運行狀態(`admin_password.txt`,`console_port.txt`,`data/`)及 Python 快取(`__pycache__/`).結構檢查程式會報告這些本機檔案;只包含版本控制項目檔案的乾淨匯出可通過檢查.遷移時應保留運行狀態.
- 目前分支的真實主機驗收限制見下文.

## 決策

下列按日期記錄的決策保留了遭否決方案及其成本.歷史決策不等於新的法律或發佈批准.

| 決策 | 理由,遭否決方案及成本 |
| --- | --- |
| 2026-09-22 — `proxy` 採用一個 sing-box 程序,最多四個入站連線,而非複製四套 anytls | - **已解決,而非否決:**隨附 sing-box 是否支援 vmess/vless/trojan/shadowsocks?已實際在同一程序中同時執行四者(不只是 `sing-box check`),無須第二後端;曾測試 hysteria2/tuic,但因欄位/TLS 要求不同而不納入. - **否決:**仿照 anytls,為各協定各設 systemd 服務單位及設定;須監察四個服務,產生三份多餘的自簽憑證,亦不利於未來每節點流量統計(以單程序 `inbounds` 清單作節點清單). - **成本:**兩個獨立模組共用隨附執行檔;各模組 `uninstall()` 刪除前**必須**檢查另一模組是否仍有設定(anytls 隨附腳本因此有本地更改,見 `anytls/.upstream-version`). |
| 2026-09-21 — `prompt_new_settings()` 明確以 `return 0` 結束,不能只讓迴圈結束 | - **否決:**讓最後一個 `for` 迴圈決定退出狀態,仿照 `install.sh` 其他函式.先前最後語句為 `[ -n "$value" ] && export ...`,接受*最後一項*設定的預設值會令測試為 false,亦成為函式的退出狀態.直接呼叫 `prompt_new_settings` 的函式雖在 `if` 區塊內,本身不獲 `set -e` 豁免;安裝程式會在最後一次提問後默默終止:無錯誤,無複製檔案,無 `VERSION` 標記,無重啟服務.在 v1.0.4 → v1.1.1 真實重現;改以 `if`/`fi` 包住 export 並於結尾明確 `return 0`,避免退出狀態取決於最後詢問哪項設定. - **不得把結尾 `return 0` 當死碼移除.** 那是修正,而非樣板程式碼. |
| 2026-09-19 — 轉發採用 iptables DNAT,每次啟動從 JSON 重套;程序外不寫入規則 | - **否決:**每規則使用 `socat` 使用者空間中繼;雖較安全(不改 NAT 表或 `ip_forward`),但用戶明確選擇核心層面的 DNAT+MASQUERADE. - **否決:**用 `iptables-persistent` 令核心規則跨重啟保留;這會令控制台及系統套件成為相同規則的兩個權威來源.改由 `app.py` 每次啟動從自有 JSON 重套(DESIGN.md"Port forwarding lifecycle"),只有一個來源. - **否決:**移除最後一條轉發時把 `net.ipv4.ip_forward` 自動還原為 `0`;此屬主機全域設定,其他軟件(本項目測試主機的 Docker)可能依賴它. - **成本:**停止 `vps-server-web`(不是重啟)會撤銷每條轉發的核心狀態,包括已啟用規則;故障方向與 iperf3 時段相同.不要為"修正"此行為而搬到另一個常駐服務單位;此前已考慮並否決. |
| 2026-09-12 — 公開頁面和控制台使用不同監聽器及處理器類別 | - **否決:**同一監聽器下,以路徑前綴和驗證控制台路由;驗證可能因錯誤而放行,不存在的路由則不能. - **否決:**把控制台放在 80/443 上用密碼保護,取消隨機埠;會捨棄 `vps-webserver` 刻意採用的隱蔽層. - **成本:**一個程序內有三個監聽器,兩個處理器類別須分別接上訪客記錄掛鉤. - **不要重新列作改進.** |
| 2026-09-12 — iperf3 只在操作員開啟的限時時段運行 | - **否決:**持續公開運行 `iperf3 -s`;陌生人可無限時耗盡上傳頻寬,亦不會提示正發生此事. - **否決:**常駐執行並用 `--authorized-users-path` RSA 驗證;測試前便須另外交付憑證,有違"把 IP 交給別人自行測試"的目的. - **成本:**遠端測試者不能無人值守測試,得有人先開啟時段;公開頁面提示時段已開,供測試者安排連線. |
| 2026-09-12 — 443 使用自簽憑證;不使用 ACME,網域 | - **否決:**為真實網域使用 certbot/acme.sh;頁面只問"這 IP 能否連通",瀏覽器警告已能證明.網域相依及續期計時器無助於回答. - **否決:**只提供 80;無法分辨"主機無法連通"和"只有 443 被封鎖",後者正是需要檢查的常見情況. - **成本:**每次 HTTPS 存取都會顯示憑證警告;屬預期,毋須以 HSTS 或固定例外"修正". |
| 2026-09-12 — sing-box 執行檔隨儲存庫提供,故整個項目使用 GPL-3.0 | - **否決:**安裝時下載 sing-box,以縮小儲存庫並保留 Apache-2.0 授權;`Anytsl-Serve` 已否決同一方案,以便無法連線 GitHub 時仍能安裝.再次選用會默默推翻此目標. - **否決:**為保留 `vps-webserver` 的 Apache-2.0 而捨棄 anytls;任務是結合兩項目,並非二選一. - **成本:**Git 增加約 57 MB,往後每次升級 sing-box 都會增加;`vps-webserver` 的 Apache-2.0 程式碼在此以 GPL-3.0 再分發. |
| 2026-09-12 — 隨附上游項目,而不取代或採用子模組 | - **否決:**用 vps-server 取代並封存 `vps-webserver`,`Anytsl-Serve`;三者須獨立維護和發佈. - **否決:**以 Git 子模組指向兩個上游儲存庫;子模組無法包含本項目需要的改名(服務名稱,執行檔名稱,`VPSWS_` → `VPSSRV_`),clone 時亦須向另外兩個儲存庫連線. - **成本:**三個儲存庫有同一份程式碼,將會分歧.緩解措施:`.upstream-version` 記錄各隨附目錄所源自的準確上游標籤,每次更新**必須**在同一 commit 更新. |

## 目前狀態與驗收限制

目前檢出版本亦有實驗性的 frps 和 Lucky 安裝路徑;本次文件遷移尚未完成其真實主機測試或發佈驗收.

原始碼快照所述的 `feat/proxy-protocols` 疊加在尚未合併的 `feat/hardening-batch` 之上;尚未合併,加標籤或發佈.proxy 模組仍待操作員審查及真實主機測試.分支審查時須協調分別套用的地址去重及公開 IP 修正.本次遷移不聲稱對代理功能進行真實主機驗證;舊容器因 systemd 並非 PID 1,使用了替代的 `systemctl`.下文 147/147,150/150,153/153,156/156 測試結果及早前真實主機測試均為歷史紀錄,並非新驗證.舊狀態稱沒有當前阻礙事項,但不能免除待辦驗收.

### 分支記錄 (2026-09-22 狀態快照)

原狀態紀錄稱功能已實作及自行測試,待操作員審查,疊加於 `feat/hardening-batch`,以使用其獨立 y/n 模組選擇器.首輪一次性 Docker 驗證中,systemd 無法以 PID 1 運行,故以替代的 `systemctl` 驗證;真實 sing-box 設定檢查,iptables 規則,憑證更換,辨識共用執行檔的解除安裝,以及無人值守安裝及升級重跑均已執行.測試發現並修正兩個問題:無效 `PROXY_PROTOCOLS` 驗證被吞掉(零個入站),以及產生的連接埠超出 sing-box uint16 限制.當時報告新增 19 項測試,147/147 通過;**不構成**代理功能的 systemd 或真實主機驗證.

其後操作員測試發現 `/anytls` 與 `/proxy` 被人為拆開,且多張頂層卡片在 flex 佈局中並排.分支現時把所有已安裝節點區塊放在 `/proxy` 上同一張卡片,重新導向 `/anytls`,並只用一個導覽項目.地址去重及移除 `get_ip()` 自動公開 IP 偵測,是由 `main` 重新套用到此分支,而非合併,原因是同時進行的代理頁面重寫;分支審查**必須**協調兩邊獨立套用的更改.歷史紀錄報告合併 anytls+proxy 回歸測試裝置及重新導向測試為 150/150 通過;其後由 `main` 重新套用 iperf3 倒數/指令例子修正,153/153 通過.

操作員之後要求把共用代理重設按鈕改為每協定一個.`setup-proxy.sh reset <protocol>` 保留其他協定的憑證及連接埠;終端機直接執行不加參數的 `reset` 仍會更換所有協定,控制台則不會.一個一次性容器測試更換四個已安裝協定之一,保留其他及完整協定集合,並確認未知名稱遭拒而不改設定.歷史紀錄報告新增/改寫六項測試,156/156 通過;此處不作新測試或發佈聲稱.

早前已發佈工作的狀態記錄:v1.1.0 連接埠轉發曾經在一次性三容器測試裝置及 119/119 單元測試後,由操作員在真實主機檢查.v1.0.0 前,操作員曾在真實主機檢查公開頁面兩個連接埠,控制台及瀏覽器測試,iperf3 在 LAN 達 2.8 Gbit/s 並在時段結束後拒絕連線,anytls 安裝/重設/清理,升級保留設定和三種介面語言.這些是歷史觀察,不是當前分支驗收.舊快照以 SQLite 鎖量度為下一項調查,報告沒有阻礙事項;未界定流量統計,初次設定精靈,frps,`gdy666/lucky` 功能或高度自訂節點.現時分別列於[問題][local-link-001]和[設計目標][local-link-002].

## 尚未發佈的儲存庫結構調整(無發佈標籤)

今次檢出版本將 Web 實作放在 `src/web/app.py`.安裝與移除指令位於 `deploy/install.sh` 和 `deploy/uninstall.sh`;儲存庫根目錄不再保留同名相容入口.`deploy/systemd/`,`deploy/anytls/` 和 `deploy/proxy/` 存放運作管理程式碼.amd64 執行檔,版本資料及上游聲明位於 `third_party/sing-box/{sing-box,sing-box.version,LICENSE}`.直接供瀏覽器使用的第三方資源位於 `static/third_party/`;相依套件核實工具位於 `tools/verify_dependencies/`.目前檢出版本另有實驗性的 frps,Lucky 安裝目錄與設定精靈工具目錄.

已安裝檔案仍採用 `$PREFIX/app.py`,`$PREFIX/static/`,`$PREFIX/anytls/`,`$PREFIX/proxy/` 和 `$PREFIX/sing-box` 的平鋪結構;模組設定仍使用 `/etc/vps-server-anytls/` 和 `/etc/vps-server-proxy/`.下文按日期記錄的決策及已完成工作所用舊路徑,描述當時的檢出版本,不是目前的使用指引.今次離線遷移檢查不等於真實主機或 systemd 驗證;仍待操作員驗收.

## 已完成工作歷史

以下已完成項目是舊待辦清單的按日期實作及驗證紀錄,並非新執行的測試報告.餘下目標見[設計目標][local-link-003],未解決的 `_db_lock` 項目見[問題][local-link-004].

- 已完成:2026-09-12 修正更新紀錄頁面顯示維護者註解:`render_changelog()` 未處理註解,`<!--` 與 `-->` 之間每行均在三種語言頁面變成段落;v1.0.0 可見,v1.0.1 修正.
- 已完成:2026-09-12 同意架構並撰寫 `DESIGN.md`;先於任何程式碼.
- 已完成:2026-09-12 隨附 `vps-webserver` v0.4.1:由上游標籤複製 `app.py`,`static/`,`tests/`,`install.sh`,`uninstall.sh`,`systemd/`;記錄標籤於 `.upstream-version`;同一 commit 將 `VPSWS_` 環境變數前綴改為 `VPSSRV_`.
- 已完成:2026-09-12 將 `app.py` 拆為兩類處理器:`ConsoleHandler` 保留所有現有路由;新增 `ProbeHandler`,只提供 `/`,`/favicon.ico`;除控制台監聽器外,在 80,443 啟動公開監聽器.
- 已完成:2026-09-12 撰寫公開連通性頁面:只有來源 IP,伺服器時鐘,到達時所用協定/連接埠,不提供主機資料,也沒有 JavaScript.樣式表最後內嵌為 `PROBE_CSS`,並非 `static/probe.css`,故公開監聽器完全沒有檔案服務路由.
- 已完成:2026-09-12 實作 iperf3 時段:控制台開關路由,`subprocess.Popen("iperf3 -s -p …")`,記憶體截止時間,到期線程,防火牆開啟/撤銷,`SIGTERM` 清理.
- 已完成:2026-09-12 在公開頁面顯示開啟時段的連接埠和剩餘分鐘,供遠端測試者決定連線時間.
- 已完成:2026-09-12 隨附 `Anytsl-Serve` v1.2.0:`anytls/setup-anytls.sh`,sing-box 執行檔及 `sing-box.version`;服務單位改名為 `vps-server-anytls.service`,執行檔改名為 `sing-box-vps-server`;標籤記於 `anytls/.upstream-version`.
- 已完成:2026-09-12 `install.sh` 增設模組選單:web/anytls/iperf3 可各自選用;80 或 443 已被佔用時拒絕;上游 `sing-box-anytls.service` 運行時拒絕;非 amd64 略過 anytls.**已撰寫但當時尚未執行**;見下文驗證項目.
- 已完成:2026-09-12 擴展 `uninstall.sh` 清理偵測到的模組:預設完整移除,`KEEP_DATA=1` 保留訪客資料庫;先清理 anytls 才刪除 `$PREFIX`(安裝根目錄 `$PREFIX`),因清理腳本位於其中.**當時已撰寫但尚未執行**.
- 已完成:2026-09-12 在獨立前綴的真實 systemd 主機由操作員完整執行 `install.sh`:服務成功啟動,摘要正確,已部署實例在 18080,18443 提供公開頁面及正確到達連接埠,公開埠的控制台路由回應 404,控制台埠正常.發現並修正兩問題:摘要中的移除指令忽略 `PREFIX`/`SERVICE_NAME`(清理只掃描預設值,甚麼都不移除);所有例子使用 `./script.sh`,在 CIFS 工作副本無法運作.
- 已完成:2026-09-12 在真實安裝實例下驗證 systemd 沙盒內 iperf3 時段:`NoNewPrivileges`,`ProtectSystem=strict` 不阻礙 `firewall_port()`;開啟時加入 `-A INPUT -p tcp -m tcp --dport 5201 -j ACCEPT`,關閉時撤銷.清理後沒有遺留服務單位,目錄,規則,程序或監聽器.
- 已完成:2026-09-12 執行 `install.sh` 安裝 anytls 模組.首次嘗試在安裝 sing-box 前失敗:CIFS 在隨附過程吞掉執行權限,執行檔記為 `100644`,`install_singbox` 以 `-x` 測試.兩邊修正後,模組完成安裝,三個已改名常量正確,服務啟動,`uninstall.sh` 移除單位,執行檔,設定目錄及防火牆規則.
- 已完成:2026-09-12 控制台顯示已安裝 anytls 節點:`/anytls` 報告服務狀態,提供可複製 Clash 設定及 `anytls://` 連結;此處只讀,`setup-anytls.sh` 仍管理節點狀態.
- 已完成:2026-09-12 驗證 `refuse_if_upstream_running` 的三條分支:上游服務運行時以狀態 1 拒絕,不存在則繼續,`VPSSRV_ALLOW_DUAL_ANYTLS=1` 警告後繼續.藉把守衛的服務名稱指向確實運行的服務,而非安裝 `Anytsl-Serve` 驗證;分支邏輯獲證實,但主機上仍未發生字面上的服務衝突.
- 已完成:2026-09-12 按 WCAG AA 審核兩種模式的控制台顏色,修正五個真實問題;最差為淺色模式下 iperf"window open"行的 1.77:1,在白背景幾乎看不見.所有組件顏色均使用具淺色模式值的語義變數;`StylesheetTest` 保護結構.
- 已完成:2026-09-12 不再硬編碼版本,改從真實標籤注入 `VERSION`.`app.py` 原寫 `VERSION = "0.1.0"`,違反 `project-management` 的 `references/webui.md` §1;若發佈時忘記更新,介面會繼續顯示舊版,亦無錯誤提示.安裝時讀取 `git describe --tags --exact-match`(或在 `install.sh` 複製時寫入),否則使用 `dev-<short sha>`,不可回退至過期標籤.此問題繼承自 `vps-webserver`,於顏色工作期間閱讀 webui.md 發現,當時因超出範圍並未修正.
- 已完成:2026-09-12 令 `install.sh` 支援升級:偵測安裝並提供保留設定選項,重播單位 `Environment=`,保留 anytls 憑證,只詢問舊版未有的設定;早於 `$PREFIX/.install-state` 的安裝由磁碟推斷模組,並明言不能計算新設定差異.
- 已完成:2026-09-12 增加更換 anytls 連接埠及密碼的控制台按鈕:`/anytls/reset` 須經伺服器驗證確認;呼叫 `setup-anytls.sh reset`,不自行寫入節點.
- 已完成:2026-09-12 操作員對舊安裝實際升級:設定重播,anytls 保留埠及密碼.發現並修正兩問題:`PUBLIC_HTTP_PORT` 在重播前計算,摘要印出預設而非重播的公開埠,埠衝突檢查亦守錯埠;web 服務的 `ProtectSystem=strict` 令 `/etc` 唯讀,控制台重設按鈕直接失敗.
- 已完成:2026-09-12 重新安裝後按一次 anytls 重設,並在主機核實:連接埠更換,節點監聽新埠,有新防火牆規則,**舊埠規則已撤銷**(沒有洩漏的 ACCEPT),暫時服務單位亦已回收.重複安裝四次沒有重複規則.
- 已完成:2026-09-12 跨保安,Python 並行,shell 正確性,文件/程式碼分歧進行全面審核,發現並修正十一個真實缺陷;見審核 commit.較重大者包括 `VPSSRV_CONSOLE_PORT=0` 在 `.env.example` 中導致綁定埠 0(每次重啟都換埠),`install.sh` 檢查連接埠前先停止服務(無關衝突後服務保持停止),以及 anytls 連接埠變更時未透過 `reset`時留下孤兒防火牆規則.
- 已完成:2026-09-12 加固 `main()` 在 `app.py` 的啟停邊界:`try/finally` 現包住整段啟動而非僅 `console.serve_forever()`,在 `start_public_listeners()`/`PORTFWD.load()` 期間收到訊號仍會清理;清理開始後忽略之後的 `SIGTERM`/`SIGINT`,避免在 `IPERF_WINDOW.close()` 中第二個訊號令防火牆規則未撤銷;各監聽器先 `shutdown()` 再 `server_close()`,修正重啟時 `OSError` traceback.新的子程序層測試實際啟動 `app.py`,確認連線,送出真實 `SIGTERM`,斷言迅速乾淨退出;這是首個測試 `main()` 本身,而非直接測試處理器類別的測試.
- 已完成:2026-09-12 只有 `VPSSRV_MODULES=iperf3` 曾默默甚麼都不安裝;現在以清楚訊息拒絕,因 iperf3 是控制台按鈕,沒有 web 就無控制台可開啟.一次性容器內驗證無人值守路徑現在顯示新訊息並失敗,而非默默退出 0.
- 已完成:2026-09-12 限制 `/login` 速率:`LoginRateLimiter` 在某 IP 於時段內錯誤過多時鎖定固定時間,登入成功或等候期限後解除.僅作縱深防禦,產生的密碼已難以暴力破解.單元測試直接測限速器,HTTP 層測試確認實際 `/login` 路由鎖定時回傳 429.
- 已完成:2026-09-12 清除維護者主機殘留的 `--dport 31515` ACCEPT;此規則來自 `close_firewall` 尚不能由 `reset` 呼叫時的安裝/卸載週期:`iptables -D INPUT -p tcp --dport 31515 -j ACCEPT`.不是當前工作樹的程式錯誤,記錄以免日後誤認.
- 已完成:2026-09-12 審核控制台佈局:iperf 表單輸入欄較按鈕高一 rem,因 `.inline-form label` 繼承 `margin-bottom: 1rem`,且 flex `align-items: flex-end` 對齊包含外距的盒子;儀表板格線仍固定兩欄,方格已增至四個;鍵值格線,同行表單及複製行完全沒有窄螢幕規則.沒有固定像素寬度,所有觸控目標符合 WCAG 2.2 最小 24 CSS px.
- 已完成:2026-09-12 操作員在普通 HTTP 的瀏覽器確認複製按鈕正常,因此 `document.execCommand` 後備方案確在非安全環境運行;預設設定非安全環境下 `navigator.clipboard` 不存在,故 `document.execCommand` 後備方案才是實際路徑,其程式碼位於 `static/copy.js`.單元測試涵蓋頁面標記,不涵蓋瀏覽器行為.
- 已完成:2026-09-12 新功能測試:`ProbeHandler` 對所有控制台路由回應 404;iperf3 時段到期並終止子程序;重啟後時段不保留.時段測試會替換 `firewall_port`,測試組合不會碰主機防火牆.
- 已完成:2026-09-12 撰寫 `LICENSE`(GPL-3.0),`LICENSES/` 和 `THIRD_PARTY_NOTICES.md`:sing-box(GPL-3.0,附 SHA-256 和對應原始碼連結),LibreSpeed(LGPL-3.0),iperf3(BSD-3-Clause,發行版安裝,故不在此再分發).
- 已完成:2026-09-12 把六份治理文件譯至 `translated_zh_cn/`,`translated_zh_tw/`;當時仍是未翻譯的樣板佔位頁,須為每文件,每語言分別委派 `doc-translator`.
- 已完成:2026-09-12 在另一部真實機器端對端驗證:在主機外連通公開頁面的 80,443;開啟時段並執行 `iperf3 -c <ip> --json`,確認 `mean_rtt` 存在.
- 已完成:2026-09-12 修正 `install_iperf3()` 默默未能安裝 iperf3:原以 `apt-get update -qq && apt-get install -y -qq iperf3` 作一條 `&&` 鏈,並丟棄所有輸出;只要無關的套件庫令 `apt-get update` 失敗(真實 VPS 曾有過期第三方 `.list`),便完全略過安裝且無診斷資訊.現重試 `apt-get update` 最多三次;即使更新未完全成功仍嘗試安裝;設定 `DEBIAN_FRONTEND=noninteractive`,不再吞掉 apt 輸出.以一次性啟用 systemd 的 Debian 12 容器作完整端對端 `install.sh` 驗證(不用當前主機,以免綁定 80/443 及啟動真實服務),預先加入同一壞套件庫場景;iperf3 成功安裝,`vps-server-web.service` 啟動,控制台及公開監聽器均回應 HTTP 200.於 v1.0.2 發佈.
- 已完成:2026-09-12 修正 v1.0.2 的 iperf3 安裝修正不完整:操作員在真實主機由 v1.0.1 升級至 v1.0.2 時,`apt-get update` 報成功,但 `security.debian.org` 的 CDN 提供過期套件索引,緊接的 `apt-get install` 取回索引剛列出的 `.deb` 時回應 404.單獨重試 `update`(v1.0.2 的修正)未必有效,因重試可能碰上同一過期邊緣節點.`install_iperf3()` 現最多三次重試整套更新後安裝流程;已以首試失敗,次試成功的假 apt 測試裝置,及 v1.0.2 使用的同一壞套件庫 Docker/容器場景,全新完整 `install.sh` 容器運行確認.另修正 README `## Install` 自 v1.0.0 起仍未填入的 `templates/README.md` 佔位值(`<repo-url>`,從未發佈的 `v0.1.0` 範例標籤),改為真實 GitHub 網址及當前發佈標籤.於 v1.0.3 發佈.
- 已完成:2026-09-12 安裝摘要印出機器真實位址:原只印 `<this-server>`/`<本机地址>` 佔位值,公開頁面及控制台網址須手動改寫;只經 ZeroTier 或 Tailscale 可連的主機更缺乏建議位址.`primary_ip()` 從 `ip -4 route get` 取得核心真正會用於出站的來源位址;`other_ips()` 列出其餘位址及介面,沿用 `setup-anytls.sh` 的容器/橋接介面過濾,但刻意保留常用於存取控制台的 VPN 介面.所有失敗路徑均回退舊佔位值而不令安裝失敗.在附加第二介面的一次性 systemd 容器內驗證:三種語言輸出及欄位對齊正確,列印的每個位址均回應 HTTP 200,即使完全替換 `ip` 指令仍退出 0.於 v1.0.4 發佈.
- 已完成:2026-09-19 控制台管理連接埠轉發:把此主機公開 TCP/UDP 連接埠轉發至 Tailscale 或 LAN 裝置(本機有公開 IP,目標裝置沒有).實作:每規則用 iptables DNAT + MASQUERADE,加註解以辨識,JSON 持久保存並在每次服務啟動時冪等重套(一般重啟及重新開機都從檔案重播,核心表本身不會保留).首次需要時開啟 `net.ipv4.ip_forward`,刻意不自動關閉,因主機其他軟件也可能依賴它.新增 `/portfwd` 控制台頁:新增/啟用/停用/刪除,tcp/udp/兩者,檢查公開埠與此安裝所有其他監聽器有否衝突.在一次性三容器 Docker 測試裝置驗證(而非本身已有 Docker iptables/NAT 狀態的真實主機,理由與本文其他完整端對端測試相同):雙網絡"vps"容器代替公開/私人邊界,"target"代替 Tailscale/LAN 裝置,"client"代替公開訪客.實際確認 TCP 和 UDP 端對端轉發;首次啟用規則時 `net.ipv4.ip_forward` 自動由 `0` 變 `1`;停用/啟用即時切換連通性;連續兩次終止及重啟程序,均由 `portfwd.json` 重套且無重複 iptables 規則;正常 `SIGTERM` 撤銷核心規則,但磁碟保留 `enabled: true`,重啟即恢復;控制台埠衝突及無效目標 IP 都被正確拒絕.119/119 單元測試通過,包括新增的 `PortForwardManagerTest`(替換 iptables)和 `PortForwardConsoleTest`(對路由發真實 HTTP)類別.該工作紀錄當時建於 `feat/portfwd`,尚未合併,發佈並待操作員手動測試;之後的狀態快照記錄了測試及 [v1.1.0 發佈][local-link-005].
- 已完成:2026-09-21 修正 `install.sh` 在真實升級中默默終止:操作員從 v1.0.4 升至 v1.1.1 時發現(`v1.1.0` 新增的兩項 `VPSSRV_PORTFWD_*` 設定,是首次升級時確有新設定要問).`prompt_new_settings()` 最後的 `for` 迴圈以 `[ -n "$value" ] && export "$var=$value"` 結束;接受*最後一項*預設值使測試為 false,成為函式退出狀態;函式在 `if` 內直接呼叫,本身不豁免 `set -e`,導致安裝程式於最後提問後無聲終止:沒錯誤輸出,未複製檔案,未標記 `VERSION`,未重啟服務;主機保持舊版,表面卻似完成.操作員真實主機重現兩次(症狀及過期 `ActiveEnterTimestamp` 相同);用 `bash -x` 追蹤並單獨重現確切 `set -e`/`&&`/迴圈作用;改以 `if`/`fi` 包住 export,並在末尾明確 `return 0`.以獨立 Bash 片段驗證失敗及修正機制;並在一次性 systemd 容器安裝真實 v1.0.4,以真實 pty 執行互動的 `bash install.sh`,經 `expect` 驅動 升至 v1.1.1(不用會遮蓋問題的管道/非互動 stdin):未修補腳本與操作員一樣在該行終止,修補後完成,更新 `VERSION` 及重啟服務.於 v1.1.2 發佈.
- 已完成:2026-09-19 參考 vaxilu/x-ui 支援更多代理協定:原先只有 anytls;使用者認為增加 vmess/vless/trojan/shadowsocks 不會有顯著額外開銷.原須決定現有 sing-box 是否支援,或需第二後端.**已解決:支援**;在同一 `sing-box run` 程序中真實同時執行四者(shadowsocks 使用 2022-blake3-aes-128-gcm),不只通過 `check`;hysteria2/tuic 因欄位/TLS 要求不同,試用後排除於本輪範圍.新增 `proxy/setup-proxy.sh` 模組(本項目原創,並非隨附上游):任意四協定子集共用一個 systemd 單位和 config.json,與 anytls 共用 sing-box 執行檔;`install.sh` 新增 `proxy` 及各協定 y/n 子問題,升級安全的憑證/連接埠保留(`preserve_proxy()`),與 anytls 共用 amd64 架構限制.初版 `/proxy` 為每協定列出連接埠,UUID/密碼,共用 SNI,Clash 設定,分享連結,QR 碼,設一個"全部重設"按鈕;[較後分支紀錄][local-link-006]描述取代它的逐協定按鈕.`PortForwardManager.reserved_ports()` 亦保留全部代理埠.實測而非僅檢查發現並修正兩錯誤:協定驗證的 `exit 1` 被命令替代子 shell 吞掉(無效 `PROXY_PROTOCOLS` 可產生零入站設定);trojan 隨機埠區間超出 sing-box uint16 `listen_port` 的 65535 上限.一次性 Docker 容器驗證(本次 Docker 設定無法以 PID 1 啟動 systemd,故 `systemctl` 為不執行動作的替代程式;其餘程式路徑,如產生設定,真實 iptables 規則,更換憑證,認識共用執行檔的卸載,均實際運行):重複五次全新安裝,縮小/擴大協定子集,重設,卸載,並完整無人值守 `install.sh` 安裝及升級重跑,確認 `preserve_proxy()` 保留相同連接埠/UUID/密碼/協定集合.`tests/test_app.py` 新增 19 項單元測試(147/147 通過).建於 `feat/proxy-protocols`,疊加未合併的 `feat/hardening-batch`(其 y/n 模組選擇器當時在 `main` 尚不存在),尚未合併,發佈或加標籤;操作員審查及真實主機測試仍待進行.
- 已完成:2026-09-19 用 QR 碼加入節點:anytls 頁面每個地址區塊除可複製分享連結,還有可展開的"Scan to add"QR 碼.實作:隨附 kazuhikoarase/qrcode-generator(MIT,`static/qrcode.js` + 處理多位元組標籤的 `static/qrcode-utf8.js`),由本項目自有 `static/qrcode-render.js` 在用戶端繪製內嵌 SVG;該檔掃描 `[data-qr-text]`,可供日後新增的節點類型重用.驗證:HTTP 層測試確認分享連結在屬性內經 HTML 正確跳脫(未跳脫 `&` 會截斷),亦確認引用三份腳本;另以 Node 執行隨附檔案原文,對真實 anytls 分享連結(含 Unicode 標籤)產生結構正確的 41×41 模組 QR SVG,並非空白/損壞圖案;此無頭環境沒有供真實瀏覽器使用的 X server,該測試是最接近的驗證.
- 已完成:2026-09-19 模組化安裝程式:把 `install.sh` 編號 1/2/3/4 模組選單,改為三個各自獨立的 y/n 問題(web,iperf3,anytls),不再從固定組合中選擇;`VPSSRV_MODULES` 保持為無人值守/可供腳本使用的方式.若 web 回答否,會完全略過 iperf3 問題,因無控制台可操控它.在一次性容器驗證四種回答組合(預設,只有 web,全部,只有 anytls),以及兩項無人值守回歸.

[local-link-001]: #錯誤
[local-link-002]: DESIGN.md#設計目標
[local-link-003]: DESIGN.md#設計目標
[local-link-004]: #錯誤
[local-link-005]: #v110--2026-09-19
[local-link-006]: #分支記錄-2026-09-22-狀態快照
[local-link-007]: THIRD_PARTY_NOTICES.md

## 交接

- 分支:`standardize/project-structure`,以 `origin/main` 為基礎.一項本機快照提交包含已審閱的項目檔案樹;不含私人測試分支歷史.
- 已完成:項目目錄標準化,英文及七種譯文的文件遷移,介面語言目錄,以及 frps 和 Lucky 的第三方聲明.
- 檢查:271 項單元測試通過(8 項略過);依賴項目雜湊檢查通過;文件檢查 0 個錯誤,4 個導覽語言警告;多語言檢查 0 個錯誤.
- 待辦:真實主機/systemd 驗收,獨立母語審閱,以及完整的上游與發佈授權覆核.
- 發佈:正式儲存庫 `origin` 的工作分支已發佈;遠端檔案樹與本機已審閱的檔案樹一致.此分支沒有本機阻礙.
- 下一步:對 `standardize/project-structure` 進行真實主機/systemd 驗收,再完成獨立譯文審閱及上游授權覆核,之後才能考慮發佈版本.
## 變更記錄

此處只列出已加標籤的發佈版本.上文尚未合併的分支工作不屬新發佈.以下保留原更新紀錄完整歷史.

### v1.1.2 — 2026-09-21

#### Fixed

- 用 `install.sh` 從不認識新增設定的版本升級時(例如 v1.0.4 升級,遇到 v1.1.0 的連接埠轉發設定),過去可在最後一項新設定提問後無聲中止——當時尚未複製檔案,更新 `VERSION` 或重啟服務,也沒有錯誤訊息.表面安裝正常結束,主機卻留在舊版.

### v1.1.1 — 2026-09-20

#### Fixed

- README 的 Install 節中,一行快速安裝及逐步安裝指令仍使用 `--branch v1.0.4`;在 v1.1.0 發佈後照做會裝到沒有連接埠轉發功能的舊版本.

### v1.1.0 — 2026-09-19

#### Added

- **控制台管理連接埠轉發.** 新增"Port forward"頁面,把本主機公開 TCP/UDP 埠轉發至 Tailscale 或 LAN 裝置,適用於本機有公開 IP,目標沒有的情況.控制台可新增,啟用,停用,刪除規則;套用前檢查此安裝已使用的每個埠(控制台,公開頁面,iperf3,anytls).規則使用 `iptables` DNAT + MASQUERADE,並在每次服務啟動時自動重套;重新啟動或重新開機後所有已啟用轉發立即恢復,而不會遺失.首次需要時自動開啟 `net.ipv4.ip_forward`.設定 `VPSSRV_PORTFWD_ENABLE=0` 可完全移除該安裝的功能.

### v1.0.4 — 2026-09-12

#### Changed

- 安裝程式最終摘要現在列印機器真實 IP,而非必須手動替換才能使用網址的 `<this-server>` 佔位值.公開頁面及控制台行採用核心實際出站時使用的地址;多網卡機器會在下方列出其他位址及各自介面,毋須猜測只經 ZeroTier 或 Tailscale 可連的節點.若讀不到任何地址,仍如以往印出佔位值,避免無關緊要的顯示問題使正常安裝失敗.

### v1.0.3 — 2026-09-12

#### Fixed

- v1.0.2 修正後 `install_iperf3()` 仍可能失敗:`apt-get update` 可報成功,但 `security.debian.org` CDN 提供過期索引,下一次 `apt-get install` 取回索引聲稱存在的 `.deb` 時卻回應 404;真實主機由 v1.0.1 升至 v1.0.2 曾遇到.單獨重試 `update` 未必有效,可能再次遇上同一過期節點.現在最多三次重試整套更新後安裝程序,後續嘗試碰上同步的鏡像站即可恢復.
- README 的 `## Install` 仍有未填的樣板佔位值:字面的 `<repo-url>`,以及本項目從未發佈過的 `v0.1.0` 範例標籤.現已改為真正的 GitHub 網址及當前發佈標籤.

### v1.0.2 — 2026-09-12

#### Fixed

- `install.sh` 曾可能默默未能安裝 iperf3:以 && 串連 apt 更新及安裝,並丟棄輸出;任何無關的損壞套件庫(例如真實 VPS 上的過期第三方 `.list`)均令更新失敗,並完全略過 iperf3 安裝,亦無法得知原因.現在會重試更新,不論更新是否成功都嘗試安裝;真正安裝失敗時不再隱藏 apt 錯誤輸出.

### v1.0.1 — 2026-09-12

#### Fixed

- 更新紀錄頁面把 CHANGELOG 底部的維護者註解(指定哪些標題維持英文)在三種語言中當普通段落顯示,連跳脫後的 `<!--` 和 `-->` 也顯示.繪製器完全沒有註解處理.只影響顯示,其他功能不受影響.

### v1.0.0 — 2026-09-12

首個發佈版本.結合兩個現有項目——以密碼保護的 VPS 網速測試控制台,以及 sing-box `anytls` 安裝程式——並新增兩者原本都沒有的功能:按需開啟的 iperf3 時段,以及讓任何人檢查 IP 的網頁連接埠能否回應的公開頁面.

#### Added

- **公開連通性頁面於 80 及 443 提供,毋須登入.** 把 IP 交給對方;如能顯示頁面,代表對方所在位置能連到你的網頁連接埠.只顯示來源位址,伺服器時鐘和所用埠/協定,不透露其他主機資料.提供兩埠是刻意安排,以區分"主機無法連通"和"僅 443 被封鎖".
- **按需開啟 iperf3 時段.** 控制台開啟限時時段;`iperf3` 只在期間執行,在當前防火牆開放連接埠,到期,操作員要求或服務停止時一併關閉.沒有"持續執行"選項,因公開 iperf3 伺服器可供陌生人耗盡上傳頻寬.時段開啟時公開頁面會顯示,讓測試者知道何時連線.
- **瀏覽器網速測試及訪客紀錄**,由控制台提供:以 LibreSpeed 引擎量度上下載,並從核心連線表讀取任何連接埠(不限 HTTP)的每條入站 TCP 連線紀錄.
- **anytls 代理模組.** sing-box 使用自簽憑證及 BBR.控制台顯示節點連接埠,密碼及 SNI,提供 Clash 設定,可複製的 `anytls://` 連結,亦可更換憑證.
- **可選模組安裝程式.** web,iperf3,anytls 可互相獨立地互動選擇,或於無人值守運行時透過 `VPSSRV_MODULES` 指定.若其他程序佔用連接埠會拒絕而非爭用;非 x86-64 略過 anytls,不會安裝無法運行的執行檔.
- **了解升級的重新安裝.** 重跑安裝程式時偵測現有安裝,提供保留設定選項,重播服務單位所記錄設定,保留 anytls 節點憑證,只詢問舊版本未有的設定.早於這項記錄方式的安裝會從磁碟讀取模組清單.
- **三種介面語言**:英文,簡體中文,繁體中文;安裝時選用,可每次瀏覽切換並記住.
- **離線安裝.** sing-box 執行檔隨儲存庫提供,因此除發行版套件鏡像站外無須其他連線.

**發佈備註(v1.0.0):**

- 整個項目使用 GPL-3.0,因其再分發 GPL-3.0 sing-box 執行檔.組件授權及 GPL 要求的對應原始碼連結見 [THIRD_PARTY_NOTICES.md][local-link-007].
- 443 使用自簽憑證:沒有網域,沒有 ACME.瀏覽器警告已能證明連接埠回應,這正是頁面的目的.
- iperf3 JSON 輸出的 `mean_rtt` 來自核心 `TCP_INFO`,故 Linux 用戶端會報往返時間;不能讀取它的用戶端(例如 Windows 上 Cygwin 的 iperf3)只報吞吐量.UDP 模式(`-u`)在各平台提供抖動及遺失率.
- anytls 模組只支援 x86-64;web 和 iperf3 不受架構限制.
