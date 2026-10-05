---
name: project-changelog-en
description: Changelog
metadata:
  version: "2.0.0"
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

#### Changed

- Installation runs as an independent systemd job after language selection, retaining logs/exit status and continuing after disconnection.

#### Fixed

- Unify typography/control sizing across Settings, iperf3, Singbox, FRPC and Tailscale; fix selects, narrow layouts and log-filter alignment. Add a detailed-log entry beside the home changelog.

- Editors load existing values; proxy edit/delete actions share a row and delete buttons use red backgrounds with clear hover feedback. FRPC lists server IPs and forwarding targets, synchronizing public-address visibility; FRPS addresses are hidden by default.

- FRPC save/rename returns a job waiting page and retries result queries after tunnel restart, preventing empty responses after successful saves. Invalid changes retain/restore prior configuration; request credentials are removed before execution.

- Tailscale logout uses a confirmation dialog and routes/exit nodes use single-select controls; fix long version/account text, the logged-out form and key visibility controls.

### v5.2.1 — 2026-10-05

#### Fixed

- Include and verify Tailscale 1.102.4 in source installs, retain resources for Web-only installs and give a clear missing-archive message.

- Complete uninstall clears Lucky settings/tasks and project FRPS/unified-proxy leftovers; keep-data mode is retained. Firewall cleanup failure stops deletion and preserves ownership records.

### v5.2.0 — 2026-10-05

#### Added

- Add a password-rechecked browser root terminal, offline Tailscale module, detailed logs and visitor-history clearing; include nftables runtime and corresponding Debian sources in complete offline packages.

#### Changed

- Move state to the separate `/var/lib/vps-server` layout and preserve it on same-layout reinstall; v5.1.0 and earlier have no automatic migration. Unify AnyTLS in Singbox, move module cards to top-level Settings, and count traffic as `(upload + download) × 2`.

#### Fixed

- Fix FRPS edits without port records, node editing, native Lucky port synchronization, terminal size/scrolling and recheck redirects. Prefer working system nft and register port changes through privileged helpers.

### v5.1.0 — 2026-10-04

#### Added

- Bundle checksum-pinned FRPC, FRPS and iperf3 x86-64 Linux artifacts in source.

#### Changed

- Limit languages to Simplified Chinese, English and Spanish, remove COMMITS.md, target x86-64 Linux and edit only managed proxy nodes. Complete uninstall clears FRPC instances/templates/ports; keep-data mode retains instance configuration.

#### Fixed

- Support non-ASCII passwords, rebuild kernel quota on cycle reset, roll back partial forwarding failures, unify port records/version synchronization, and fix FRPC module state and test-build changelog recognition.

### v5.0.0 — 2026-10-03

#### Added

- Add timed iperf3 client TCP/UDP tests, independent public-page controls and a persistent server label.

#### Changed

- Complete first install in the terminal with Web only by default; split source/styles by feature and retain unexpired sessions on ordinary restarts.

#### Fixed

- Support Unicode FRPC names, retain nodes/state on reinstall and fix complete-uninstall completion messages and exit status.

### v4.0.0 — 2026-09-29

#### Added

- Add a temporary HTTPS first-install wizard, module jobs and local FRPC CRUD/testing/simple proxy editing; separate FRPS/FRPC home entries.

#### Changed

- Give home feature cards independent switches, move modules to ordinary Settings, refine responsive forms/themes, remove page-transition animations and toggle forwarding without restarting Web.

#### Fixed

- Stop requiring an edit index for new FRPC proxies, stop visitor collection when disabled and retain saved node fields on reopening.

### v3.0.0 — 2026-09-28

#### Added

- Add managed nodes for five protocols, sharing/QR codes, quotas/rate limits/cycle resets/expiry and a private-IP passwordless allowlist.

#### Changed

- Unify console layouts, themes/accent colors and sensitive-value hiding; separate iperf3 status from port editing and retain runtime entry/modules on upgrade.

### v2.0.0 — 2026-09-27

#### Added

- Add four-protocol proxy, first-install wizard and experimental FRPS/Lucky modules with original licenses and artifact hashes.

#### Changed

- Move install entry points to `deploy/`, Web to `src/web/`, dependencies to `third_party/` and release metadata to `config/`; organize documents/translations by standard directories.

### v1.1.2 — 2026-09-21

#### Fixed

- Fix old-version upgrades silently ending after a new prompt, before copying files or updating services.

### v1.1.1 — 2026-09-20

#### Fixed

- Fix README commands checking out v1.0.4 instead of v1.1.0.

### v1.1.0 — 2026-09-19

#### Added

- Add TCP/UDP forwarding, iptables DNAT/MASQUERADE, startup replay and managed-port conflict checks.

### v1.0.4 — 2026-09-12

#### Changed

- Show real egress/interface addresses in installation output; retain a placeholder without aborting if detection fails.

### v1.0.3 — 2026-09-12

#### Fixed

- Retry the full update/install flow for stale package indexes and replace README repository/version placeholders.

### v1.0.2 — 2026-09-12

#### Fixed

- Attempt iperf3 installation even after repository-update failure, retry updates and retain installation errors.

### v1.0.1 — 2026-09-12

#### Fixed

- Stop rendering maintainer HTML comments in changelog pages.

### v1.0.0 — 2026-09-12

#### Added

- First release combining password-protected Web speed tests, visitor logs, AnyTLS, public reachability on 80/443 and timed iperf3 windows; add namespaced configuration and data-preserving uninstall.
