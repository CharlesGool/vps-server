---
project: vps-server
version: v1.0.3
status: active
branch: main
updated: 2026-09-12
---

# Status

**English** | [简体中文](translated_zh_cn/STATUS_zh_cn.md) | [繁體中文](translated_zh_tw/STATUS_zh_tw.md)

**Notion:** private mirror (not published)
**Repo:** public
**Snapshots:** maintained privately (not published)
**In progress:** v1.0.3 released; the repository is public. v1.0.2's iperf3
install fix was incomplete: `apt-get update` can report success while
`security.debian.org`'s CDN hands back a stale index that 404s on the next
`apt-get install` — hit live on a real host upgrading v1.0.1 to v1.0.2.
`install_iperf3()` now retries the whole update-then-install pair, not just
update alone. Also fixed the README's `## Install` section, which still had
unfilled template placeholders (`<repo-url>`, an example `v0.1.0` tag this
project has never had) since v1.0.0. Verified with a full end-to-end
`install.sh` run in a disposable, systemd-enabled Debian 12 container (not
this live host) with the same broken-repo scenario seeded: iperf3 installed,
`vps-server-web.service` came up active, and both the console and the public
listener answered HTTP 200. v1.0.2 fixed `install_iperf3()` skipping the
install entirely when an unrelated apt repo broke `apt-get update`; v1.0.1
fixed the CHANGELOG's maintainer comment rendering on the changelog page —
display only, nothing else was affected.

Every feature was verified on a real host by the operator before v1.0.0: the
public page
answers on both public ports, the console and browser speed test work, the
iperf3 window measures 2.8 Gbit/s over LAN and refuses connections once it
closes itself, the anytls node installs, rotates its credentials and tears
down cleanly, an upgrade replays recorded settings without disturbing the
node, and all three interface languages render. Nothing is in flight.
**Next:** Decide whether the shared `_db_lock` needs decoupling — every
public-page hit takes a process-wide lock and does a synchronous SQLite write,
and the console shares that lock, so in principle anonymous flooding can slow
an authenticated page. **Measured and not reproduced**: 60 concurrent flooders
left console latency at 0.4–0.6 ms, identical to idle. Recorded so the
mechanism is not rediscovered as new; do not rearchitect without a measurement
that shows harm.
**Known issues:** None that break anything. Four items in `BACKLOG.md` are
open by choice rather than by fault: a shared SQLite lock whose reported
impact could not be reproduced under load, two startup and shutdown signal
edges, `VPSSRV_MODULES=iperf3` on its own installing nothing, and the absence
of login rate limiting.
**Blocked on:** nothing.
