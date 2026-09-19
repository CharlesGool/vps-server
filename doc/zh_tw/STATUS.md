# Status

[English](../STATUS.md) | [简体中文](../zh_cn/STATUS.md) | **繁體中文** | [繁體中文（香港）](../zh_hk/STATUS.md) | [हिन्दी](../hi/STATUS.md) | [Español](../es/STATUS.md) | [العربية](../ar/STATUS.md) | [Français](../fr/STATUS.md)

## 文件說明

- 專案概覽：[README](README.md)
- 設計理念：[DESIGN](DESIGN.md)
- 版本歷史：[CHANGELOG](CHANGELOG.md)
- 需求清單：[BACKLOG](BACKLOG.md)
- 被否決的方案：[DECISIONS](DECISIONS.md)
- 第三方授權聲明：[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

> 譯自 `STATUS.md`（v1.1.0）。如有衝突，以英文版為準。

**Notion:** 私人鏡像（未公開發布）
**Repo:** 公開
**Snapshots:** 私下維護（未公開發布）
**進行中:** v1.1.0 已發布。由主控台管理的通訊埠轉發（port forwarding）：讓主控台把這台主機上的一個公開 TCP/UDP 通訊埠，轉發到透過 Tailscale 或區域網路才能連到的裝置——也就是「這台主機有公開 IP、那台裝置沒有」的情境——做法是透過 iptables DNAT + MASQUERADE，規則以 JSON 形式持久化，並在每次服務啟動時冪等地重新套用。在交給操作者親自測試之前已先自我驗證：119/119 個單元測試通過（含新增的 `PortForwardManagerTest` 與 `PortForwardConsoleTest`），且一個一次性的三容器 Docker 測試環境端到端確認了真實的 TCP 與 UDP 流量轉發、`net.ipv4.ip_forward` 會自動開啟、停用/啟用能立即切換可達性、連續兩次行程重啟不會套用重複的 iptables 規則、乾淨停止會撤銷每一條規則的核心狀態，即使 `portfwd.json` 仍寫著 `enabled: true`，下次啟動也會立刻恢復。操作者接著已在真實主機上手動驗證過。目前沒有任何項目在進行中。

較早的修補，依新到舊排列：v1.0.4 讓安裝程式結尾的摘要印出主機的真實位址——先前它會原樣印出 `<this-server>` 這個佔位符取代實際位址，導致每一個 URL 在使用前都得手動修改；v1.0.3 讓 `install_iperf3()` 對「更新後安裝」這整組動作進行重試（即使 `apt-get update` 回報成功，過期的 `security.debian.org` 索引仍可能讓安裝出現 404），並補上 README 中尚未填寫的 `<repo-url>`/`v0.1.0` 安裝佔位符；v1.0.2 修正了 `install_iperf3()` 在某個無關的 apt 來源導致 `apt-get update` 失敗時，會整個跳過安裝的問題；v1.0.1 修正了 CHANGELOG 頁面上維護者註解的顯示問題——僅影響顯示，其餘皆未受影響。

在 v1.0.0 之前，操作者已在真實主機上驗證過每一項功能：公開頁面在兩個公開埠上皆能回應、主控台與瀏覽器測速功能正常運作、iperf3 測速視窗在區域網路內測得 2.8 Gbit/s、且該視窗關閉自身後會拒絕連線、anytls 節點能安裝、輪替其憑證並乾淨地拆除、升級能重放已記錄的設定且不影響節點運作、三種介面語言均能正確顯示。目前沒有任何項目在進行中。
**下一步:** 決定是否需要將共用的 `_db_lock` 解耦——每一次公開頁面的存取都會取得一個行程層級的鎖並同步寫入 SQLite，而主控台也共用同一把鎖，因此理論上匿名的洪水式請求可能拖慢已驗證使用者的頁面。**已實測但未能重現**：60 個並發洪水請求下，主控台延遲維持在 0.4–0.6 毫秒，與閒置時相同。記錄下來是為了不讓這個機制日後被重新發現為新問題；在沒有能證明其造成損害的測量結果之前，不要重新架構。
**已知問題:** 沒有會造成故障的問題。`BACKLOG.md` 中有四個項目是刻意保持開放，而非缺陷所致：一個共用的 SQLite 鎖，其回報的影響在負載下無法重現；兩個啟動與關閉時的訊號邊界情況；單獨設定 `VPSSRV_MODULES=iperf3` 時不會安裝任何東西；以及尚未實作登入速率限制。
**卡住的地方:** 沒有。
