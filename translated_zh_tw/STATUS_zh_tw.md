# Status

[English](../STATUS.md) | **繁體中文**

> 譯自 `STATUS.md`（v1.0.2）。如有衝突，以英文版為準。

**Notion:** private mirror（未公開）
**Repo:** public
**Snapshots:** 私下維護（未公開）
**In progress:** v1.0.2 已發布；此儲存庫為 public。`install.sh` 的
`install_iperf3()` 原本把 `apt-get update && apt-get install iperf3` 串在一起，
並將所有輸出丟棄，因此只要有一個與此無關、已損壞的 apt repository（在真實 VPS
上曾出現過），就會讓整個安裝步驟悄悄被跳過。現已修正為：重試 update、
不論 update 本身的結果如何都嘗試安裝，並且不再隱藏 apt 的錯誤輸出。已在一個
可拋棄、啟用 systemd 的 Debian 12 容器中（並非此正式主機）以完整的
`install.sh` 端對端執行做過驗證，並刻意重現了那個已損壞 repository 的情境：
iperf3 成功安裝、`vps-server-web.service` 進入 active 狀態，主控台與對外的
public listener 也都回應 HTTP 200。v1.0.1 修的是 changelog 頁面上 CHANGELOG
維護者註解的顯示問題——只影響顯示，其餘一律未受影響。

v1.0.0 之前，操作者已在真實主機上驗證過每一項功能：public page
在兩個 public port 上都能回應，主控台與瀏覽器測速都正常運作，
iperf3 視窗在區網內量到 2.8 Gbit/s，並在自行關閉後拒絕連線，
anytls 節點能安裝、輪替憑證並乾淨拆除，升級能重放已記錄的設定而不影響
節點，三種介面語言也都能正常渲染。目前沒有任何項目在進行中。
**Next:** 決定共用的 `_db_lock` 是否需要解耦——每一次 public-page 的
存取都會拿下一把全域行程鎖並執行同步的 SQLite 寫入，主控台也共用同一把鎖，
理論上匿名的洪水式請求可能拖慢已登入頁面的速度。**已實測、未能重現**：
60 個並行洪水請求下，主控台延遲維持在 0.4–0.6 ms，與閒置時相同。記錄下來
是為了不讓這個機制之後被當成新問題重新發現一次；在沒有測量數據證明有害
之前，不要重新架構它。
**Known issues:** 沒有會壞事的問題。`BACKLOG.md` 裡有四項是刻意保留
未處理，而非有缺陷：一把共用的 SQLite 鎖，其回報的影響在負載下無法重現；
兩個啟動與關閉時的訊號邊界情況；單獨設定 `VPSSRV_MODULES=iperf3` 不會
安裝任何東西；以及尚未提供登入速率限制。
**Blocked on:** 無。
