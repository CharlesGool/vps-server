---
project: vps-server
version: v1.1.1
status: active
branch: main
updated: 2026-09-20
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
**In progress:** v1.1.1 released. Fixed the README Install section, which
still cloned `--branch v1.0.4` in both the quick-install one-liner and the
step-by-step command — anyone following it right after v1.1.0 shipped would
have installed the previous release and missed port forwarding entirely.
Nothing is in flight.

Released history, newest first: v1.1.0 added console-managed port forwarding
— lets the console forward a public TCP/UDP port on this host to a device
reached over Tailscale or the LAN via iptables DNAT + MASQUERADE, with rules
persisted as JSON and reapplied idempotently on every service start.
Self-verified before the operator's own test: 119/119 unit tests pass, and a
live disposable three-container Docker harness confirmed real TCP and UDP
forwarding end to end, `net.ipv4.ip_forward` turning on automatically,
disable/enable toggling reachability immediately, two process restarts in a
row applying no duplicate iptables rules, and a clean stop withdrawing every
rule's kernel state while `portfwd.json` still says `enabled: true` so the
next start brings it straight back. The operator then verified it manually on
a real host. v1.0.4 printed the machine's real addresses in
the installer's closing summary — it used to emit a literal `<this-server>`
placeholder in place of an address, so every URL had to be hand-edited before
it could be used. v1.0.3 made `install_iperf3()` retry the whole
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
