# Changelog

**English** | [简体中文](translated_zh_cn/CHANGELOG_zh_cn.md) | [繁體中文](translated_zh_tw/CHANGELOG_zh_tw.md)

Newest version first. Only changes a user can perceive — internal refactors do
not need an entry. Draft from `git log <previous-tag>..HEAD --oneline`, then
rewrite in user-facing terms.

## v1.0.4 — 2026-09-12

### Changed

- The installer's closing summary now prints the machine's real IP addresses
  instead of a literal `<this-server>` placeholder that had to be substituted
  by hand before the URLs were usable. The address the kernel would actually
  use to leave the box goes on the public-page and console lines; on a
  multi-homed machine every other address is listed below them, each labelled
  with its interface, so a node reachable only over ZeroTier or Tailscale is
  visible rather than guessed at. If no address can be read the old
  placeholder is printed as before, which keeps an otherwise-good install
  from failing over cosmetics.

## v1.0.3 — 2026-09-12

### Fixed

- `install_iperf3()` could still fail even after v1.0.2's fix. `apt-get update`
  can report success while `security.debian.org`'s CDN hands back a stale
  package index, so the very next `apt-get install` 404s trying to fetch a
  `.deb` the index just claimed exists — seen live on a real host upgrading
  from v1.0.1 to v1.0.2. A single retry of `update` alone did not reliably
  fix this, since the retry could hit the same stale edge. The installer now
  retries the whole update-then-install pair together, up to 3 times, which
  recovers once a later attempt lands on a synced mirror.
- The README's `## Install` section still had unfilled template
  placeholders — a literal `<repo-url>` and a `v0.1.0` example tag that this
  project has never actually had a release named. Both now read the real
  values: the project's actual GitHub URL and its current release tag.

## v1.0.2 — 2026-09-12

### Fixed

- `install.sh` could silently fail to install iperf3: it chained the apt
  update and install steps together with all output discarded, so one
  unrelated broken repository — a stale third-party `.list` file, which is
  what happened on a real VPS — made the update step fail and skipped
  installing iperf3 entirely, with no way to see why. It now retries the
  update, attempts the install regardless of whether the update succeeded,
  and no longer hides apt's own error output when the install genuinely
  fails.

## v1.0.1 — 2026-09-12

### Fixed

- The changelog page showed the maintainer comment from the bottom of the
  CHANGELOG file — the one naming which headings stay in English — as ordinary
  paragraphs, escaped `<!--` and `-->` included, in all three languages. The
  renderer had no comment handling at all. Display only; nothing else was
  affected.

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
