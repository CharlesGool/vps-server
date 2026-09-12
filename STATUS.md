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
**Next:** Inject `VERSION` from the real tag rather than the literal in
`app.py`. It is the one open item that would contaminate the first tag:
`references/webui.md` §1 forbids the hard-coded constant precisely because
forgetting it at release time leaves the UI claiming the previous version with
nothing to report it. After that, the rest of the release checklist —
translate the six governance documents, run `release-preflight.sh`, cut
`v0.1.0`, export the snapshot.
**Known issues:** None that break anything. Five items in `BACKLOG.md` are
open by choice rather than by fault: the `VERSION` literal, a shared SQLite
lock whose reported impact could not be reproduced under load, two startup and
shutdown signal edges, `VPSSRV_MODULES=iperf3` on its own installing nothing,
and the absence of login rate limiting. The six governance documents are still
untranslated template placeholders; they are translated at tag time.
**Blocked on:** nothing.
