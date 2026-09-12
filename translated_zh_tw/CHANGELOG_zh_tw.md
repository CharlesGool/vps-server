# 更新日誌

[English](../CHANGELOG.md) | [简体中文](../translated_zh_cn/CHANGELOG_zh_cn.md) | **繁體中文**

最新版本在最上面。只記使用者能感知到的變化——內部重構不需要條目。

## Unreleased

尚未發布任何版本。文件骨架和已確認的設計已經就位，`app.py` 的公開頁與 iperf3 視窗
已經實作並通過端到端驗證；`install.sh`、`uninstall.sh` 與 vendored 的 anytls 模組
還沒寫完。工作順序見 `BACKLOG.md`。

第一個版本將打 tag `v0.1.0`；到那時把本節標題改成 `## v0.1.0 — <日期>`，不要另起一節。

<!--
版本小節的標題（## v0.1.0 — YYYY-MM-DD）和 Added / Changed / Fixed 三個分類名
逐字照抄英文版，不要翻譯：scripts/release-preflight.sh 靠 ^## vX.Y.Z 定位本版本
小節，gh release create 的描述也取自英文版的同一節。只翻譯條目正文。
-->
