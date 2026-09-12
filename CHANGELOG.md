# Changelog

**English** | [简体中文](translated_zh_cn/CHANGELOG_zh_cn.md) | [繁體中文](translated_zh_tw/CHANGELOG_zh_tw.md)

Newest version first. Only changes a user can perceive — internal refactors do
not need an entry. Draft from `git log <previous-tag>..HEAD --oneline`, then
rewrite in user-facing terms.

## v1.0.0 — 2026-09-12

First release. It combines two existing projects — a password-protected VPS
speed-test console and a sing-box `anytls` installer — and adds two
capabilities neither had: an on-demand iperf3 window and a public page that
lets anyone check whether your IP answers on the web.

### Added

- **Public reachability page on ports 80 and 443, with no login.** Hand
  someone the IP; if the page renders, your web ports are reachable from where
  they are. It reports their source address, the server clock, and which port
  and protocol they arrived on — and nothing else about the host. Serving both
  ports is deliberate: it distinguishes "the host is unreachable" from "443
  specifically is blocked".
- **On-demand iperf3 window.** The console opens a time-boxed window; `iperf3`
  runs only inside it, opens its port in whichever firewall is active, and
  shuts both down when the window expires — on request, or when the service
  stops. There is no "leave it running" option, because an open iperf3 server
  lets any stranger saturate the uplink. While a window is open the public
  page advertises it, so the tester knows when to connect.
- **Browser speed test and visitor log**, from the console: up/download
  measurement using the LibreSpeed engine, and a record of every inbound TCP
  connection on any port — not just HTTP — read from the kernel's connection
  table.
- **anytls proxy module.** sing-box with a self-signed certificate, plus BBR.
  The console shows the node's port, password and SNI, offers its Clash entry
  and `anytls://` link with copy buttons, and can rotate the credentials.
- **Module-selecting installer.** web, iperf3 and anytls are chosen
  independently, interactively or through `VPSSRV_MODULES` for unattended
  runs. It refuses rather than fighting for a port another process holds, and
  skips anytls on non-x86-64 rather than installing a binary that cannot run.
- **Upgrade-aware re-install.** Re-running the installer detects the existing
  install, offers to keep its configuration, replays the settings recorded in
  the service unit, preserves the anytls node's credentials, and asks only
  about settings the installed version did not have. Installs predating that
  bookkeeping are handled by reading the module list off the disk.
- **Three interface languages** — English, Simplified Chinese, Traditional
  Chinese — chosen at install time, switchable per visit, and remembered.
- **Offline installation.** The sing-box binary ships in the repository, so
  installing needs nothing beyond your distribution's package mirror.

### Notes

- The whole project is GPL-3.0, because it redistributes the GPL-3.0 sing-box
  binary. Component licences and the corresponding-source links the GPL
  requires are in `THIRD_PARTY_NOTICES.md`.
- TLS on 443 is a self-signed certificate: no domain, no ACME. A browser
  warning still proves the port answers, which is the question that page
  exists to settle.
- `mean_rtt` in iperf3's JSON output comes from the kernel's `TCP_INFO`, so a
  Linux client reports round-trip time and one that cannot read it — iperf3
  under Cygwin on Windows, for instance — reports throughput only. UDP mode
  (`-u`) gives jitter and loss everywhere.
- x86-64 only for the anytls module. The web and iperf3 modules are
  architecture-independent.

<!--
The version heading (## v1.0.0 — YYYY-MM-DD) and the Added / Changed / Fixed
category names are copied verbatim into the translations, not translated:
scripts/release-preflight.sh locates the current section by ^## vX.Y.Z, and
the GitHub release notes are taken from the English file's same section. Only
the entry text is translated.
-->
