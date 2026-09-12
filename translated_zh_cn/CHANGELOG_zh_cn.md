# 更新日志

[English](../CHANGELOG.md) | **简体中文** | [繁體中文](../translated_zh_tw/CHANGELOG_zh_tw.md)

最新版本在最上面。只记用户能感知到的变化——内部重构不需要条目。

## Unreleased

尚未发布任何版本。文档骨架和已确认的设计已经就位，`app.py` 的公开页与 iperf3 窗口
已经实现并通过端到端验证；`install.sh`、`uninstall.sh` 与 vendored 的 anytls 模块
还没写完。工作顺序见 `BACKLOG.md`。

第一个版本将打 tag `v0.1.0`；到那时把本节标题改成 `## v0.1.0 — <日期>`，不要另起一节。

<!--
版本小节的标题（## v0.1.0 — YYYY-MM-DD）和 Added / Changed / Fixed 三个分类名
逐字照抄英文版，不要翻译：scripts/release-preflight.sh 靠 ^## vX.Y.Z 定位本版本
小节，gh release create 的描述也取自英文版的同一节。只翻译条目正文。
-->
