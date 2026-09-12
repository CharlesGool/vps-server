# Changelog

[English](../CHANGELOG.md) | **繁體中文**

> 譯自 `CHANGELOG.md`（v<release-version>）。如有衝突，以英文版為準。

最新版本在最前。只寫使用者能感知到的變化——內部重構不用單列條目。先用
`git log <上一個tag>..HEAD --oneline` 起草，再按使用者視角改寫。

## v0.1.0 — YYYY-MM-DD

### Added
- <新增能力>

### Changed
- <行為變化；屬於破壞性變更時寫明遷移步驟>

### Fixed
- <修復的 bug>

<!--
版本小節的標題（## v0.1.0 — YYYY-MM-DD）和 Added / Changed / Fixed 三個分類名
逐字照抄英文版，不要翻譯：scripts/release-preflight.sh 靠 ^## vX.Y.Z 定位本版本
小節，gh release create 的描述也取自英文版的同一節。只翻譯條目正文。
-->
