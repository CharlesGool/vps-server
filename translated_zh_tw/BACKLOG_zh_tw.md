# 待辦清單

[English](../BACKLOG.md) | **繁體中文**

> 譯自 `BACKLOG.md`（v1.0.4）。如有衝突，以英文版為準。

需求清單。所有被提出過的要求，依重要程度排序，完成後打勾。這份檔案回答的是「兩週沒動這個專案之後，接下來該做什麼？」，也是一個 session 結束時還沒做完的需求該寫進去的地方。

**`STATUS.md` 的 `Next:` 欄位，就是這裡最上面那個還沒打勾的項目，原文照抄。** 那一步做完後，在這裡打勾，並把下一個未勾選的項目提升上去。兩邊絕不能對不上：`Next` 是跨專案總表顯示的那一行，這份檔案才是續接工作時真正會被讀的內容。

每個項目都帶著新增日期，這樣一個放了一年的未完成項目會明顯過期，而不是悄悄變成永久項：

```
- [ ] YYYY-MM-DD <要做什麼> — <從哪裡開始：檔案、指令，或懸而未決的問題>
- [x] YYYY-MM-DD <一個已完成的項目>
```

寫項目時要讓人可以直接冷啟動去做。「改善錯誤處理」是一則筆記，不是一個待辦項目；「把 mount 呼叫包進重試機制 — `src/mount.py`，最下面那個裸 `except`」才是。

---

## 項目

- [x] 2026-09-12 阻止更新日誌頁面把維護者留言也一起渲染出來 — `render_changelog()` 完全沒有處理留言，導致 `<!--` 和 `-->` 之間的每一行都在三種語言的頁面上都變成了一個段落。v1.0.0 中可見此問題，已在 v1.0.1 修復

- [x] 2026-09-12 議定架構並寫出 `DESIGN.md` — 在動任何程式碼之前完成
- [x] 2026-09-12 引入 `vps-webserver` v0.4.1 — 從上游 tag 複製 `app.py`、`static/`、`tests/`、`install.sh`、`uninstall.sh`、`systemd/`；在 `.upstream-version` 中記錄該 tag；同一個 commit 中把 `VPSWS_` 環境變數前綴改名為 `VPSSRV_`
- [x] 2026-09-12 把 `app.py` 拆成兩個 handler — `ConsoleHandler` 保留所有現有路由；新增 `ProbeHandler`，只服務 `/` 和 `/favicon.ico`；在 console 監聽器之外，另外於 80 和 443 啟動公開監聽器
- [x] 2026-09-12 寫出公開可達性頁面 — 顯示來源 IP、伺服器時鐘、抵達的協定/連接埠，不透露任何主機資訊；不使用 JavaScript。樣式表最終以 `PROBE_CSS` 內嵌方式呈現，而非獨立的 `static/probe.css` 檔案，所以公開監聽器完全沒有提供檔案服務的路由
- [x] 2026-09-12 實作 iperf3 視窗 — console 路由負責開啟/關閉、`subprocess.Popen("iperf3 -s -p …")`、記憶體內的截止時間、過期執行緒、防火牆開啟/撤除、`SIGTERM` 時的收尾清理
- [x] 2026-09-12 在公開頁面上顯示目前開啟的視窗 — 連接埠與剩餘分鐘數，讓遠端測試者知道何時可以連線
- [x] 2026-09-12 引入 `Anytsl-Serve` v1.2.0 — `anytls/setup-anytls.sh` 加上 sing-box 執行檔與 `sing-box.version`；把 unit 改名為 `vps-server-anytls.service`，執行檔改名為 `sing-box-vps-server`；在 `anytls/.upstream-version` 中記錄該 tag
- [x] 2026-09-12 把 `install.sh` 改成模組式選單 — web / anytls / iperf3 可獨立選擇；80 或 443 已被佔用時拒絕安裝；上游 `sing-box-anytls.service` 正在執行時拒絕安裝；非 amd64 時跳過 anytls。**已寫完但從未實際執行過** — 見下方的驗證項目
- [x] 2026-09-12 擴充 `uninstall.sh`，讓它能拆除偵測到的任何模組 — 預設完整移除，`KEEP_DATA=1` 可保留訪客資料庫；anytls 會先在 `$PREFIX` 被刪除前拆除，因為它的拆除腳本就放在 `$PREFIX` 裡面。**已寫完但從未實際執行過**
- [x] 2026-09-12 真正把 `install.sh` 從頭到尾跑一遍 — 由操作者在一台真實 systemd 主機上、使用獨立 prefix 完成。服務成功啟動，摘要區塊正確，部署後的實例在 18080 和 18443 上都正確服務了公開頁面，抵達連接埠也正確，公開連接埠上的 console 路由回應 404，console 連接埠則正常回應。發現並修復了兩個 bug：結尾的「移除方式」那行忽略了 `PREFIX`/`SERVICE_NAME`（導致拆除腳本悄悄掃描預設值而什麼都沒移除），以及每個使用範例都寫成 `./script.sh`，這在 CIFS 工作副本上無法執行
- [x] 2026-09-12 驗證 iperf3 視窗在 systemd 沙盒下的行為 — 在一台真實已安裝的實例上完成。`NoNewPrivileges` 與 `ProtectSystem=strict` 並不會擋住 `firewall_port()`：開啟視窗會加入 `-A INPUT -p tcp -m tcp --dport 5201 -j ACCEPT`，關閉時會撤除該規則。之後的拆除沒有留下任何 unit、目錄、規則、行程或監聽器
- [x] 2026-09-12 用 anytls 模組跑一次 `install.sh` — 已完成。第一次嘗試在 sing-box 安裝前就失敗了（執行檔因為 CIFS 在引入時吃掉了執行位元，被記錄成 `100644`，而 `install_singbox` 測試的是 `-x`）；修正兩側問題後，模組安裝成功，三個改名後的常數落在預期的位置，服務啟動，`uninstall.sh` 也成功移除了該 unit、執行檔、設定目錄與防火牆規則
- [x] 2026-09-12 在 console 中顯示已安裝的 anytls 節點 — `/anytls` 回報服務是否在執行，並提供可複製的 Clash 設定項與 `anytls://` 連結。唯讀；節點狀態仍由 `setup-anytls.sh` 掌管
- [x] 2026-09-12 驗證 `refuse_if_upstream_running` — 三個分支都測試過：上游 unit 執行中時以 exit 1 拒絕，不存在時繼續，`VPSSRV_ALLOW_DUAL_ANYTLS=1` 則發出警告後繼續。驗證方式是把該防護機制的服務名稱指向一個確實在執行的 unit，而不是實際安裝 `Anytsl-Serve`，所以分支邏輯已獲證實，但真正的字面衝突至今從未在任何主機上發生過
- [x] 2026-09-12 依 WCAG AA 標準審查 console 在兩種配色模式下的顏色 — 修復了五個真實的失敗案例，最嚴重的是淺色模式下 iperf「視窗已開啟」那行文字對比度只有 1.77:1，在白底上幾乎看不見。現在每個元件顏色都是一個帶有淺色模式數值的語意化 token；`StylesheetTest` 負責守護這個結構
- [x] 2026-09-12 從真實 tag 注入 `VERSION`，而非寫死 — `app.py` 把 `VERSION = "0.1.0"` 寫成字面值，這正是 `project-management` 的 `references/webui.md` §1 所禁止、並列為常見錯誤的做法：發版時忘了改，UI 就會一直宣稱是上一個版本，而且不會有任何提示。應在安裝時讀取 `git describe --tags --exact-match`（或在 `install.sh` 的複製步驟中直接烘焙進去），且回退值應是 `dev-<short sha>`，而不是一個過期的 tag。此問題繼承自 `vps-webserver`；是在為顏色工作閱讀 webui.md 時發現的，但當時因不在範圍內而未修
- [x] 2026-09-12 讓 `install.sh` 具備升級意識 — 它能偵測既有安裝，提議保留其設定，重新套用記錄在該 unit `Environment=` 行中的設定值，保留 anytls 節點的憑證，並只針對已安裝版本尚不存在的設定項提問。對於在 `$PREFIX/.install-state` 出現之前建立的安裝，則從磁碟推斷模組清單，並明確告知無法計算新設定的差異
- [x] 2026-09-12 在 console 中新增一個按鈕來輪替 anytls 的連接埠與密碼 — `/anytls/reset`，附伺服器端驗證的確認流程；它呼叫的是 `setup-anytls.sh reset`，而不是自行寫入節點資料
- [x] 2026-09-12 在一個較舊的安裝上實際執行一次升級 — 由操作者完成。升級路徑運作正常：設定值被正確重新套用，anytls 節點保留了原本的連接埠與密碼。發現並修復了兩個 bug：摘要印出的是預設公開連接埠而不是重新套用後的值，因為 `PUBLIC_HTTP_PORT` 是在重新套用之前就已推算完成（連接埠衝突檢查也用了同一個過期的值，因此檢查的是錯誤的連接埠）；以及 console 的重設按鈕完全失敗，因為 web 服務的 `ProtectSystem=strict` 讓 `/etc` 對它而言是唯讀的
- [x] 2026-09-12 重新安裝後點一次 anytls 重設按鈕 — 已完成，並在事後於主機上驗證：連接埠已輪替，節點監聽新的連接埠，新的防火牆規則存在，**舊連接埠的規則已被撤除**（沒有殘留的 ACCEPT），暫時性的 unit 也已被回收。連續四次重新安裝都沒有留下重複的規則
- [x] 2026-09-12 針對安全性、Python 並行處理、shell 正確性以及文件/程式碼落差進行完整審查 — 發現並修復了十一個真實缺陷；詳見審查 commit。其中最大的幾個是：`.env.example` 裡的 `VPSSRV_CONSOLE_PORT=0` 會把連接埠綁定在 0（導致 console 每次重啟都換一個連接埠）、`install.sh` 在檢查連接埠之前就先停掉服務（於是遇到無關的衝突時服務就這樣停在那裡不動）、以及每當 anytls 連接埠在 `reset` 之外的情況下變更時，都會留下一條孤兒防火牆規則
- [ ] 2026-09-12 決定共用的 `_db_lock` 是否需要解耦 — 每一次公開頁面的存取都會取得一個行程層級的鎖並同步寫入 SQLite，而 console 也共用這個鎖，因此理論上匿名端的洪水攻擊可能拖慢已驗證使用者的頁面。**已實測，但未能重現**：60 個並行洪水來源下，console 延遲維持在 0.4–0.6 ms，與閒置時相同。記錄下來是為了避免這個機制日後被重新「發現」一次；在沒有測量結果證明有害之前，不要重新設計架構
- [ ] 2026-09-12 加固 `app.py` 中 `main()` 的啟動/關閉邊界情況 — 目前 `try/finally` 只包住了 `console.serve_forever()`，所以在監聽器設定期間收到訊號會跳過清理，而在 `IPERF_WINDOW.close()` 執行期間收到第二個 `SIGTERM` 可能會在防火牆規則被撤除之前就逃逸。另外，兩個使用執行緒的公開監聽器應在 `server_close()` 之前呼叫 `shutdown()`，目前每次重啟都會記錄一筆 `OSError` traceback
- [ ] 2026-09-12 單獨設定 `VPSSRV_MODULES=iperf3` 時會悄悄地什麼都不安裝 — 它沒有通過 `web` 檢查，走進只有 anytls 才會走的提早退出分支，該分支不處理 iperf3，然後就以 exit 0 結束。應該拒絕這種組合，或是讓那個分支也安裝 iperf3
- [ ] 2026-09-12 考慮為 `/login` 加上速率限制 — 目前並非漏洞（產生的密碼是 `secrets.token_urlsafe(15)`），但完全沒有任何退避機制。屬於縱深防禦，不是修 bug
- [x] 2026-09-12 清除維護者主機上，在 `close_firewall` 能被 `reset` 呼叫到之前，某次安裝/移除循環遺留下來的過期 `--dport 31515` ACCEPT 規則 — `iptables -D INPUT -p tcp --dport 31515 -j ACCEPT`。這不是目前程式碼中的 bug；記錄下來是為了避免日後被誤認成一個
- [x] 2026-09-12 審查 console 版面配置 — iperf 表單的輸入框比按鈕高出了一個 rem，原因是 `.inline-form label` 繼承了 `margin-bottom: 1rem`，而 flex 的 `align-items: flex-end` 對齊的是 margin box；儀表板網格被固定寫死為兩欄，但磚塊數量已經成長到四個；鍵值網格、行內表單與複製列完全沒有窄螢幕規則。整個頁面沒有任何寫死的像素寬度，每個觸控目標都符合 WCAG 2.2 最小 24 CSS px 的要求
- [x] 2026-09-12 在瀏覽器上以純 HTTP 檢查複製按鈕 — 已由操作者確認可正常運作，因此 `document.execCommand` 的後備方案確實會在非安全情境下執行 — 在非安全情境（也就是預設情境）下，`navigator.clipboard` 是 undefined，所以 `static/copy.js` 裡的 `document.execCommand` 後備方案才是實際會執行的路徑。單元測試只涵蓋頁面標記，不涵蓋瀏覽器實際行為
- [x] 2026-09-12 為新增的功能面補上測試 — `ProbeHandler` 對每一個 console 路由都回應 404；iperf3 視窗會過期並終止其子行程；視窗不會在重啟後存活。測試已涵蓋這些情況；`firewall_port` 在視窗相關測試中被 stub 掉，所以整個測試套件永遠不會碰到主機的防火牆
- [x] 2026-09-12 撰寫 `LICENSE`（GPL-3.0）、`LICENSES/`，以及 `THIRD_PARTY_NOTICES.md` — sing-box（GPL-3.0，附 SHA-256 與對應原始碼連結）、LibreSpeed（LGPL-3.0）、iperf3（BSD-3-Clause，由發行版安裝、因此未隨附散布）
- [x] 2026-09-12 把六份治理文件翻譯進 `translated_zh_cn/` 與 `translated_zh_tw/` — 目前都還是未翻譯的範本佔位文字；派發 `doc-translator`，每份文件每種語言各一個實例
- [x] 2026-09-12 在真實的第二台機器上做端到端驗證 — 從主機外分別經由 80 與 443 抵達公開頁面，開啟一個視窗並執行 `iperf3 -c <ip> --json`，確認 `mean_rtt` 存在

- [x] 2026-09-12 修復 `install_iperf3()` 悄悄安裝 iperf3 失敗的問題 — 它把 `apt-get update -qq && apt-get install -y -qq iperf3` 寫成單一個 `&&` 鏈，且所有輸出都被捨棄，因此只要有一個無關的軟體來源讓 `apt-get update` 失敗（在一台真實 VPS 上遇到的是一個過期的第三方 `.list`），就會直接整個跳過安裝嘗試，也沒有任何診斷訊息。已修復為：`apt-get update` 最多重試 3 次，之後無論 update 是否完全成功都會嘗試安裝，設定 `DEBIAN_FRONTEND=noninteractive`，並且不再吞掉 apt 的輸出。已在一個可拋棄、啟用了 systemd 的 Debian 12 容器（而非這台正式主機，以避免在此綁定 80/443 並啟動真實服務）中，用完整的 `install.sh` 端到端執行，並種入完全相同的損壞軟體來源情境進行驗證：iperf3 成功安裝，`vps-server-web.service` 啟動並處於 active 狀態，console 與公開監聽器兩者都回應了 HTTP 200。已隨 v1.0.2 出貨

- [x] 2026-09-12 修復 v1.0.2 對 iperf3 安裝問題的修復並不完整 — 操作者在把一台真實主機從 v1.0.1 升級到 v1.0.2 時遇到了實際的失敗案例：`apt-get update` 回報成功，但 `security.debian.org` 的 CDN 回傳了一份過期的套件索引，導致 `apt-get install` 在抓取索引剛剛才宣稱存在的 `.deb` 時出現 404。單獨重試 `update`（v1.0.2 的修法）無法穩定解決這個問題，因為重試仍可能碰上同一個過期的邊界情況。現在 `install_iperf3()` 會把「update 接著 install」這一整組一起重試，最多重試 3 次 —— 已針對一個先失敗一次、再成功的假 apt 測試工具驗證過，也針對 v1.0.2 所使用的同一個損壞軟體來源 Docker/容器重現案例驗證過，並額外執行了一次全新的、完整的端到端 `install.sh` 容器測試。同時也修復了 README 的 `## Install` 區段，該區段自 v1.0.0 以來一直帶著未填寫的 `templates/README.md` 佔位文字（`<repo-url>`，以及一個從未真正發布過的範例 `v0.1.0` tag）—— 已替換成真實的 GitHub URL 與目前的發行 tag。已隨 v1.0.3 出貨

- [x] 2026-09-12 在安裝程式結尾的摘要中印出機器的真實位址 — 之前印出的是一個字面上的 `<this-server>` / `<本机地址>` 佔位文字，導致公開頁面與 console 的網址在能用之前都得手動修改，而在一台只能透過 ZeroTier 或 Tailscale 連線的機器上，完全沒有東西能告訴操作者該嘗試哪個位址。`primary_ip()` 從 `ip -4 route get` 取得來源位址，也就是核心實際上會用來離開這台機器的那一個；`other_ips()` 則列出其餘位址，各自標上所屬介面，沿用了 `setup-anytls.sh` 的容器/橋接介面過濾器，但刻意保留了 VPN 介面，因為那往往就是 console 被連上的方式。所有失敗路徑都會回退到舊的佔位文字，而不會讓安裝失敗。已在一個接了第二張網卡的可拋棄 systemd 容器中驗證：三種語言的輸出內容與欄位對齊都正確，每一個印出的位址都回應了 HTTP 200，而且就算把 `ip` 整個 stub 掉也依然以 exit 0 結束。已隨 v1.0.4 出貨

<!--
打勾，不要刪除。打了勾的項目，就是這個需求曾被聽見並處理過的證據 —— 刪掉它會讓這份清單看起來一直都很短，
也會讓人無法分辨「從未被要求過」和「被要求過並已完成」的差別。

範圍界線，避免這份檔案變成另一份「什麼都記」的副本：

  這裡              每一個需求，不論是否完成
  DECISIONS.md      只記錄「被否決過、而且不記下來就會被當成新點子重新提出」的內容；
                    這是防止重複提案的守門記錄，不是決策日誌 —— 大多數決定都不屬於這裡
  CHANGELOG.md      每個版本實際出貨了什麼，寫給使用這個專案的人看；這份檔案是它背後的工作清單
  STATUS.md         最上面那個未完成項目，加上目前狀態
  todo 工具         今天這個 session 內部的步驟；那些東西明天就沒了，這正是它們不寫進這裡的原因

依事件更新，而不是「session 結束前」（一個 session 從不會宣布自己結束）：
  - 使用者要求了某件目前沒人在做的事 —— 當下就寫下來，不要等到最後
  - 一個項目完成了 —— 打勾，並把 STATUS.md 的 Next 移到下一個未完成項目
  - 一個項目不再需要了 —— 原地劃掉並註明原因（- [~] ... —— 已放棄，因為 X）；
    悄悄刪掉的話，兩週後它就會以「新提案」的樣貌捲土重來。只有當這個點子有可能自己再冒出來時，
    才需要額外在 DECISIONS.md 補一條

只記錄真正打算做的工作。一份沒人相信是真的待辦清單，只會被掃過一眼就被無視。

在公開倉庫中，適用與 STATUS.md 相同的隱去規則：不放 Notion 網址、不放本機/NAS 絕對路徑、
不放內部主機名。那些資訊放在 repo/ 之外的 ../.local-notes.md 裡。
-->
