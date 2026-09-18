---
project: vps-server
version: v1.0.4
status: active
branch: main
updated: 2026-09-12
---

# Status

**English** | [简体中文](zh_cn/STATUS.md) | [繁體中文](zh_tw/STATUS.md) | [繁體中文（香港）](zh_hk/STATUS.md) | [हिन्दी](hi/STATUS.md) | [Español](es/STATUS.md) | [العربية](ar/STATUS.md) | [Français](fr/STATUS.md)

## Documentation

- Project overview: [README](../README.md)
- Design rationale: [DESIGN](DESIGN.md)
- Release history: [CHANGELOG](CHANGELOG.md)
- Requirement list: [BACKLOG](BACKLOG.md)
- Rejected ideas: [DECISIONS](DECISIONS.md)
- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

**Notion:** private mirror (not published)
**Repo:** public
**Snapshots:** maintained privately (not published)
**In progress:** v1.0.4 released; the repository is public. The installer's
closing summary printed a literal `<this-server>` placeholder in place of an
address, so every URL in it had to be hand-edited before it could be used. It
now reads the real addresses: the source address the kernel would use to leave
the box goes on the public-page and console lines, and on a multi-homed
machine the remaining addresses are listed below, each labelled with its
interface. Detection failure falls back to the old placeholder rather than
failing the install. Verified end-to-end in a disposable systemd container
with a second interface attached: all three languages aligned, every printed
address answered HTTP 200, and a stubbed-out `ip` command still exited 0.
Earlier patches, newest first: v1.0.3 made `install_iperf3()` retry the whole
update-then-install pair (a stale `security.debian.org` index can 404 the
install even when `apt-get update` reports success) and filled in the README's
unfilled `<repo-url>`/`v0.1.0` install placeholders; v1.0.2 fixed
`install_iperf3()` skipping the install entirely when an unrelated apt repo
broke `apt-get update`; v1.0.1
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
