# Changelog

[English](../CHANGELOG.md) | **简体中文**

> 译自 `CHANGELOG.md`（v<release-version>）。如有冲突，以英文版为准。

最新版本在最前。只写用户能感知到的变化——内部重构不用单列条目。先用
`git log <上一个tag>..HEAD --oneline` 起草，再按用户视角改写。

## v0.1.0 — YYYY-MM-DD

### Added
- <新增能力>

### Changed
- <行为变化；属于破坏性变更时写明迁移步骤>

### Fixed
- <修复的 bug>

<!--
版本小节的标题（## v0.1.0 — YYYY-MM-DD）和 Added / Changed / Fixed 三个分类名
逐字照抄英文版，不要翻译：scripts/release-preflight.sh 靠 ^## vX.Y.Z 定位本版本
小节，gh release create 的描述也取自英文版的同一节。只翻译条目正文。
-->
