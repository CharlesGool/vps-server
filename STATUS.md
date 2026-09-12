---
project: vps-server
version: unreleased
status: active
branch: main
updated: 2026-09-12
---

# Status

**English** | [简体中文](translated_zh_cn/STATUS_zh_cn.md) | [繁體中文](translated_zh_tw/STATUS_zh_tw.md)

**Notion:** private mirror (not published)
**Repo:** private, pushed
**Snapshots:** maintained privately (not published)
**In progress:** Everything is verified on a real host by the operator: the
public page answers on both public ports, the console and browser speed test
work, the iperf3 window measures 2.8 Gbit/s over LAN and refuses connections
once it closes itself, the anytls node installs and tears down cleanly, the
console's anytls page shows the node and copies its client configuration, the
reset button rotates the port and password without leaking the old port's
firewall rule, an upgrade replays recorded settings and keeps the node's
credentials, and all three UI languages render. 98 tests pass. Nothing known
is broken; what is left before a tag is the release checklist.
**Next:** Decide whether to cut `v0.1.0`. Every feature is now verified on a
real host and the tree has no known defects, so the remaining work before a
tag is the release checklist rather than the code: translate the six
governance documents, run `release-preflight.sh`, and decide the repository's
public/private status given it redistributes a GPL-3.0 binary.
**Known issues:** The copy buttons on `/anytls` have not been clicked in a
browser. `navigator.clipboard` does not exist outside a secure context and
the console is plain HTTP by default, so the `document.execCommand` fallback
is the path that really runs; the tests cover the markup, not the browser.
The six governance documents are still untranslated template placeholders in
`translated_zh_cn/` and `translated_zh_tw/`; they get translated as part of
the v0.1.0 release checklist.
**Blocked on:** nothing.
