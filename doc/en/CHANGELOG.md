---
name: project-changelog-en
description: Changelog
metadata:
  version: "1.0.0"
  lang: "en"
---

# Changelog

## Multi-language

[简体中文](../CHANGELOG.md) | **English** | [Español](../es/CHANGELOG.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)


## Changelog

### v5.2.2 — 2026-10-05

#### Fixed

- Align typography, buttons, dropdowns and narrow layouts across settings/modules, iperf3, Singbox, FRPC and Tailscale. Correct log filter alignment, settings navigation highlighting and the port forwarding form. Add detailed logs beside the changelog on Home.
- Load existing values before editing FRPS, FRPC and proxy nodes so blank inputs do not replace saved ports or tokens. Keep proxy edit and delete actions together, with red delete buttons and clear hover feedback.
- Show each FRPC proxy's server IP, remote port and local forwarding target. Reveal and hide the server IP together with the card control. Hide FRPS interface addresses by default and provide reveal and copy controls.
- FRPC saves and renames return a background task page before restarting the instance. Result polling retries through tunnel interruptions and reports the actual outcome after reconnection, avoiding empty responses after successful saves. Invalid changes retain or restore the previous configuration; credentials are removed from the task request before execution.
- Confirm Tailscale logout in a dialog and use single-choice dropdowns for advertised subnet routes and exit nodes. Fix version and long account text, disconnected connection forms, key reveal controls and runtime log layout.

#### Installation and upgrades

- After language selection, the installer runs as an independent systemd background task. Terminal or FRPC disconnections do not stop upgrades. Private logs and a completion exit code record the outcome; console module installs continue waiting for their existing background job before reporting results.

#### Verification and limits

- Checks passed on Debian 13 x86-64 for upgrades, service health and Web autostart, Unicode FRPC renames and server/proxy saves, save results across an actual FRPC tunnel restart, retention of invalid configurations, private address endpoints, and desktop/narrow layouts. The operator confirmed the reported issues were fixed and approved publication.
- The test host was not logged into a Tailnet, so logout from an authenticated account was not exercised. Real mobile devices, other distributions, Python 3.9 and a host reboot were not independently retested. Syntax, stylesheet builds, three languages, offline asset checksums and third-party notices passed. Documentation and release records are internal maintenance.

### v5.2.1 — 2026-10-05

#### Fixed

- Source distributions include and verify the official Tailscale 1.102.4 amd64 archive, allowing the console to add Tailscale after a Git installation. Web-only installs retain the archive; offline builds reuse the source copy.
- Missing Tailscale archives produce a specific resource-recovery message, separate from missing installer files.
- Complete uninstall removes Lucky native settings, DDNS and reverse-proxy tasks, and this project's FRPS and unified proxy directories, including leftovers after service units have been removed. Tailscale identity is deleted with the project state root; `KEEP_DATA=1` continues to retain data. Failed firewall cleanup stops complete uninstall and preserves ownership records.

#### Validation and limitations

- Three-language missing-resource responses, payload retention for separate-directory and in-place Web-only installation, source archive reuse and pinned digests passed. Five isolated uninstall scenarios passed: complete removal, missing units, retained data, firewall failure and directory symlinks. Source syntax, styles, language parity and in-app changelog checks passed.
- No installation or uninstall was performed on the operator's VPS for this release; the real-host retry remains unconfirmed. The v5.2.0 tag is unchanged. Earlier-layout migration restrictions and supported-environment limits remain those of v5.2.0. Publication records and documentation housekeeping are internal maintenance.

### v5.2.0 — 2026-10-05

#### Added

- Browser root terminal with administrator password verification, automatic closure on navigation, scrollback and narrow-screen support.
- Offline Tailscale module with status, device addresses, logs, batch Linux settings and an experimental low-memory option.
- Detailed module and service logs with severity filters and project-scoped clearing; recent visitor history can be cleared.
- Complete x86-64 Linux offline bundle with pinned Tailscale and nftables runtime archives and corresponding Debian sources.

#### Changed

- Persistent data uses a separate state root, `/var/lib/vps-server` by default; reinstalling the same layout preserves credentials, ports, certificates and configuration. **The v5.1.0 and earlier layout cannot be upgraded automatically; back up first and perform a fresh installation.**
- AnyTLS and other protocols share the Singbox service; module cards appear directly in Settings and Lucky uses its actual native administration address.
- Proxy accounting counts (upload + download) × 2; monthly resets begin on the first day of the selected month at 00:00 UTC. Logs and module progress notices follow the current operation.

#### Fixed

- FRPS editing without a port registry entry, masked value reveal/copy, unified proxy node creation/editing, and Lucky address synchronization after native port changes.
- Terminal disconnects caused by resize reports, password verification return navigation, content sizing, scrollbars and background. Metering prefers a working system nft and avoids early throttling when accounting data is missing.
- Web port updates use a privileged helper; FRPS reserves its port before installation and iperf3 reserves a port only while its window is open.

#### Validation and limitations

- On 2026-10-05 the operator confirmed current project tests were satisfactory and authorized release. Local release checks cover source syntax, style build, dependency digests and three-language structure; earlier Debian 13 x86-64 host checks are recorded in LOG and HISTORY.
- Python 3.9, other Debian/Ubuntu versions, physical mobile devices and a full host reboot were not independently retested for this release. Publication does not upgrade the test host. The operator requested minor version v5.2.0; the installation layout still requires the migration steps above. Other documentation and record housekeeping is internal maintenance.

### v5.1.0 — 2026-10-04

#### Added

- A complete source checkout bundles and checks x86-64 Linux FRPC, FRPS, and
  iperf3 artifacts. Installing the FRPC and iperf3 modules no longer requires
  separate GitHub downloads of executables.

#### Changed

- Documentation and interface languages now follow the current project
  standard: Simplified Chinese, English, and Spanish. During upgrade, prior
  selections of other languages fall back to English. Earlier translations
  remain available through old tags and Git history.
- The retired `COMMITS.md` listing was removed; Git history is the commit record.
- The entire project now targets x86-64 Linux. Installed Web runtime code
  remains at `$PREFIX/src/web/`, while the root compatibility entry point
  retains the existing service names and data directories.
- The proxy console reads only its managed-node registry and asks for migration
  or repair when older configurations cannot be matched. The old node editor
  and installation interaction paths that did not execute were retired.
- A complete uninstall cleans up recognizable FRPC instances, related global
  service files, and this project's `PORTS.md` entries. `KEEP_DATA=1` retains
  FRPC instance configurations.

#### Fixed

- The FRPC module card detects installation from the local executable and
  service template. Changelog recognizes numbered test candidate versions.
- Administrator passwords containing Chinese or other non-ASCII characters
  verify correctly. Periodic traffic resets also rebuild the kernel quota.
- Applying a port forward no longer reports success after failure, and
  partially applied rules are cleaned up. The console and node helper record
  sanitized error types.
- FRP, console, and iperf3 port registrations share one format. The installer
  synchronizes the runtime directory's `config/VERSION`.

#### Verification and limits

- Local syntax checks, style build, artifact checksums, project structure,
  multilingual structure, and isolated logic checks passed. The automated
  test suite had previously been removed at the operator's request.
- The operator reported passing the test host's complete FRPC uninstall and
  port registry cleanup, Web login, iperf3, proxy nodes and traffic, port
  forwarding, and upgrade from an older version. SSH was unavailable in this
  session, so these host results were not independently checked. Recovery
  after reboot, installation and Web startup on a Python 3.9 target, real
  mobile devices, and combinations outside the reported scope remain unverified.

### v5.0.0 — 2026-10-03

#### Added

- The console can start a time-limited TCP or UDP test against another iperf3 server and shows short server and client commands.
- Public HTTP and HTTPS pages have independent switches and Home entries. A persistent server label appears in navigation and browser titles.

#### Changed

- First installation runs directly in the terminal and installs only the Web console by default. Optional modules can be installed later from Settings → Modules. FRPC enablement is independent of the running state of its client instances.
- Web feature handlers and styles are split by feature; served assets now live in `src/web/static/`. Project documentation separates the Simplified Chinese source, historical records, release changes, and translations.
- Ordinary Web service restarts preserve unexpired login sessions. Password changes still invalidate existing sessions.

#### Fixed

- FRPC instance names accept Unicode letters and numbers. Module reinstall keeps installed nodes and service state, and module controls report their result before restart.
- Full uninstall prints its localized completion message and exits successfully after deleting the installation directory.

#### Verification and limits

- The local unit suite ran 377 tests: 369 passed and 8 were skipped. The style build, dependency verification, project structure, multilingual, and document-link checks passed. The operator reports that the existing features had previously been tested without problems. This source layout migration has not been reinstalled on a real host; reboot persistence, every cross-host proxy and forwarding combination, and real mobile devices have not been fully verified.
- FRPC continues to use the [frpc-0.71.0-linux-amd64](https://github.com/CharlesGool/vps-server/releases/download/v4.0.0/frpc-0.71.0-linux-amd64) asset from the prior formal release. It is 16,593,080 bytes, with SHA-256 `f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`. For offline installation, place the file at `~/apps/vps-server/vendor/frp/frpc`, then install it from the Modules page; the installer verifies its digest before use. The three large executables retained in the repository have Git blobs identical to those in `v4.0.0`.

### v4.0.0 — 2026-09-29

#### Added

- A browser-based first-run setup selects modules, language, authentication, and ports through a temporary HTTPS listener with a one-time password. The installed console can install or remove optional modules from Settings and shows each job's status and log.
- Local FRPC instances can be created, renamed, edited, enabled, disabled, tested, and removed. The editor supports simple token-authenticated TCP and UDP proxies, verifies changes with `frpc`, and restores the previous configuration when applying a change fails. FRPC installation is independent of FRPS; its checksum-pinned client binary is distributed as the `frpc-0.71.0-linux-amd64` Release asset.
- Home has separate FRPS and FRPC entries and pages. Disabled feature pages lead to a localized closed page.

#### Changed

- Home presents the nine main functions as cards with individual switches. Module management moved to ordinary Settings; Security Settings remains protected by recent administrator-password verification.
- FRPC and proxy-node cards have clearer edit, test, reveal, and confirmation controls. Instance edits retain the current server address and token unless changed, and proxy fields distinguish local from server ports.
- Login and Settings navigation, page icons, password controls, theme choices, and responsive layout follow the current console design. The body uses system fonts to keep text metrics stable during refresh. Page-transition animation was removed after operator feedback; responsive resize motion remains.
- Port forwarding switches reconcile rules in the running Web process without restarting the console. Repeated module submissions return to the page, and rejected POST connections close cleanly instead of misparsing a later request.

#### Fixed

- Adding an FRPC proxy no longer requires the index used only for editing or deleting a proxy. Visitor collection stops while the feature is disabled, and proxy-node controls preserve saved values when reopened.

#### Verification and limits

- The local suite passed 341 tests with 8 skipped. On the designated test host, authenticated routes, FRPS and FRPC page separation, module switches, closed-page routing, FRPC configuration validation, and a user-requested TCP proxy mapping were checked. The operator accepted the current refresh behavior as adequate. The host currently remains on a patched test build; this formal source tag does not itself upgrade that installation.
- Real mobile hardware, reboot persistence, a complete clean-host install from this final tag, and every live proxy or forwarding policy combination remain unverified. The three previously published large executable blobs are unchanged from v3.0.0. The FRPC client is a new 16,593,080-byte Release asset with SHA-256 `f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`; the installer verifies that digest before use.

### v3.0.0 — 2026-09-28

#### Added

- Managed AnyTLS, VMess, VLESS, Trojan, and Shadowsocks nodes can be created, edited, disabled, reset, and deleted individually. Display numbers stay contiguous; hidden UUIDs preserve identity. Connection details can be copied or imported into Clash Meta for Android by link or QR code.
- Each node tracks upload and download traffic and supports a GiB cap, separate directional speed limits, recurring resets in days, months, or years, and an optional validity period. A reached cap can throttle both directions to 1 Mbps or block access; an expired validity period blocks access.
- Password-free access is available to an explicit private-IP allowlist. Security Settings requires a recent administrator-password check, including for IP-only sessions, before exposing or changing credentials and access rules.

#### Changed

- Unified the console and login layouts, responsive node cards, dashboard navigation, and settings. Ordinary Settings now offers eight persistent accent colors and independent light/dark modes. Stored credentials and configured ports are masked until an authorized reveal or use.
- The iperf3 view separates service state from its editable port. Installer upgrades preserve the runtime web entry point and staged modules. Proxy setup summaries list interface and optional Tailscale addresses without public-IP lookup. Translated document fragments and third-party source links were repaired.

#### Verification and limits

- The operator reports that functional testing passed. The local suite passed 311 tests (8 skipped); the designated test host served the new login and theme assets with Web, proxy, node-meter, and AnyTLS services active and enabled for boot. An actual reboot and every live policy transfer were not independently witnessed in this release preparation.
- No new or changed blob over 10 MB was added. The existing sing-box (57,995,520 bytes), frps (20,332,728 bytes), and Lucky (10,883,644 bytes) executables have the same Git blob IDs as in `v2.0.0`; provenance and license records remain in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md). frps and Lucky remain experimental.

### v2.0.0 — 2026-09-27

#### Changed

- Moved installer and removal entry points to `deploy/install.sh` and
  `deploy/uninstall.sh`, web source to `src/web/`, bundled dependencies to
  `third_party/`, and release metadata to `config/`. Scripts that called the
  old checkout paths need the new paths; installed runtime data stays in its
  existing locations.
- Consolidated the former backlog, status, decision, and changelog documents
  into `DESIGN.md` and `LOG.md`; migrated all eight language sets and local
  links to the standard document layout. Interface text now lives under
  `lang/` with BCP-47 file names.

#### Added

- Included the four-protocol proxy module, its shared console page and
  per-protocol credential reset controls, plus the browser setup wizard.
- Included experimental frps and Lucky installers and their bundled
  executables. Their original license files and artifact hashes are recorded
  in the third-party inventory.

#### Verification and limits

- Local unit suite: 271 tests passed, 8 skipped. Dependency hashes,
  document checks, and multilingual structure checks passed. The document
  checker reported four navigation-label warnings in English documents.
- Repository copies of all seven bundled artifacts matched the corresponding
  upstream release files on 2026-09-27; the original license files for the
  bundled executables matched those release archives. Independent legal
  interpretation was not obtained.
- Real-host/systemd acceptance and independent native-language review remain
  outstanding. frps and Lucky are experimental in this version.

### v1.1.2 — 2026-09-21

#### Fixed

- Upgrading with `install.sh` from a version that predates a newly-added
  setting (as v1.1.0's port-forwarding settings did to anyone on v1.0.4)
  could silently abort right after the last new-setting prompt — before
  copying any files, updating `VERSION`, or restarting the service — with
  no error message, leaving the host on the old version while the install
  appeared to finish normally.

### v1.1.1 — 2026-09-20

#### Fixed

- README's Install section still cloned `--branch v1.0.4` in both the
  one-line quick install and the step-by-step command — anyone following it
  right after v1.1.0 shipped would have installed the previous release,
  missing port forwarding entirely.

### v1.1.0 — 2026-09-19

<a id="vps-release-v1-1-0"></a>

#### Added

- **Console-managed port forwarding.** A new "Port forward" page lets you
  forward a public TCP/UDP port on this host to a device reached over
  Tailscale or the LAN — useful when this box has a public IP and the target
  device does not. Add, enable, disable and delete rules from the console;
  each one is checked against every port this install already uses (console,
  public page, iperf3, anytls) before it is applied. Rules are backed by
  `iptables` DNAT + MASQUERADE and are reapplied automatically every time the
  service starts, so a restart or a reboot brings every enabled forward
  straight back rather than losing it. `net.ipv4.ip_forward` is turned on
  automatically the first time it is needed. Set `VPSSRV_PORTFWD_ENABLE=0` to
  remove the feature from an install entirely.

### v1.0.4 — 2026-09-12

#### Changed

- The installer's closing summary now prints the machine's real IP addresses
  instead of a literal `<this-server>` placeholder that had to be substituted
  by hand before the URLs were usable. The address the kernel would actually
  use to leave the box goes on the public-page and console lines; on a
  multi-homed machine every other address is listed below them, each labelled
  with its interface, so a node reachable only over ZeroTier or Tailscale is
  visible rather than guessed at. If no address can be read the old
  placeholder is printed as before, which keeps an otherwise-good install
  from failing over cosmetics.

### v1.0.3 — 2026-09-12

#### Fixed

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

### v1.0.2 — 2026-09-12

#### Fixed

- `install.sh` could silently fail to install iperf3: it chained the apt
  update and install steps together with all output discarded, so one
  unrelated broken repository — a stale third-party `.list` file, which is
  what happened on a real VPS — made the update step fail and skipped
  installing iperf3 entirely, with no way to see why. It now retries the
  update, attempts the install regardless of whether the update succeeded,
  and no longer hides apt's own error output when the install genuinely
  fails.

### v1.0.1 — 2026-09-12

#### Fixed

- The changelog page showed the maintainer comment from the bottom of the
  CHANGELOG file — the one naming which headings stay in English — as ordinary
  paragraphs, escaped `<!--` and `-->` included, in all three languages. The
  renderer had no comment handling at all. Display only; nothing else was
  affected.

### v1.0.0 — 2026-09-12

First release. It combines two existing projects — a password-protected VPS
speed-test console and a sing-box `anytls` installer — and adds two
capabilities neither had: an on-demand iperf3 window and a public page that
lets anyone check whether your IP answers on the web.

#### Added

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

**Release notes (v1.0.0):**

- The whole project is GPL-3.0, because it redistributes the GPL-3.0 sing-box
  binary. Component licences and the corresponding-source links the GPL
  requires are in [THIRD_PARTY_NOTICES.md][local-link-007].
- TLS on 443 is a self-signed certificate: no domain, no ACME. A browser
  warning still proves the port answers, which is the question that page
  exists to settle.
- `mean_rtt` in iperf3's JSON output comes from the kernel's `TCP_INFO`, so a
  Linux client reports round-trip time and one that cannot read it — iperf3
  under Cygwin on Windows, for instance — reports throughput only. UDP mode
  (`-u`) gives jitter and loss everywhere.
- x86-64 only for the anytls module. The web and iperf3 modules are
  architecture-independent.
