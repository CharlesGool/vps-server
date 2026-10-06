---
name: project-design-en
description: Project architecture and design constraints
metadata:
  version: "2.0.0"
  lang: "en"
---

# vps-server — Design

## Multi-language

[简体中文](../DESIGN.md) | **English** | [Español](../es/DESIGN.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Design Goals

- [x] Manage optional network tools and independent services through one authenticated console.
- [x] Separate replaceable code from persistent state and retain settings within one data layout.
- [x] Use constrained privileged helpers for services, ports and network rules, with queryable background results.
- [x] Support Simplified Chinese, English and Spanish with checksum-pinned client resources.

Non-goals: a general container platform, arbitrary FRP configuration editing, automatic public-IP discovery, or a complete host OS package lock.

## Architecture

The browser uses pages and authenticated endpoints served by a Python standard-library HTTP service. Handlers are divided by feature in `src/web/features/`. Independent systemd services run Singbox, FRPS, FRPC, Lucky and Tailscale. Web uses system protection options and delegates limited privileged actions to root helpers; a separately password-verified browser terminal runs a root PTY.

After language selection, the installer starts background job `vps-server-install`. FRPC save/rename returns a waiting page before background validation and application, followed by a delayed instance restart. Status polling retries after tunnel interruption; success or failure comes from the actual job result.

| Directory | Responsibility |
| --- | --- |
| `.local/` | Git-ignored maintenance files, historical snapshots and private notes; excluded from deployment. |
| `.github/` | Continuous checks and Actions dependency maintenance. |
| `src/` | Web source, feature handlers and static resources. |
| `deploy/` | Install/uninstall scripts, module setup and systemd templates. |
| `config/` | Version, pinned artifact hashes and import provenance. |
| `lang/` | UI/installer translations; config value `zh_cn` selects Simplified Chinese. |
| `third_party/` | Upstream executables, archives, licenses and provenance. |
| `tools/` | Style build, dependency verification and offline packaging tools. |
| `doc/` | Design, status, history, changes, notices and translations. |

Style sources live in `src/web/static/styles/`, with output at `src/web/static/style.css`. `tools/build-offline/build_offline.py` writes packages to a selected output directory, containing code, installer, pinned artifacts and notices; private state, `.git` and local debugging files are excluded. `tools/build-offline/fetch_assets.py` verifies nftables downloads on the build host.

The maintenance entry point is `python3 tools/check-project/check_project.py`, requiring Python 3.9+, Git, Bash and Node.js. It checks first-party Python/Bash/JavaScript syntax, duplicate JSON keys, three-language keys and format placeholders, local documentation links, environment-variable coverage, stylesheet output and pinned artifact hashes. `.github/` runs the same check in CI, while `.editorconfig` and `.gitattributes` define text encoding and line endings; original third-party bytes remain unchanged. Tool directories use lowercase words and hyphens; Python filenames retain underscores.

## Design Constraints

- Sensitive values **MUST** require authentication and any required password recheck; initial HTML **MUST NOT** embed hidden real credentials. Editors **MUST** load existing values rather than overwrite unchanged values with blanks.
- Ports **MUST** be locked and recorded before activation; failures release new reservations. Other projects' reservations **MUST NOT** be taken.
- FRP changes **MUST** validate first and retain or restore old settings on failure. Structured editing **MUST NOT** discard unsupported advanced configuration.
- Quotas count `(upload + download) × 2`; missing meter readings **MUST NOT** count as quota exhaustion. Cycle resets **MUST** rebuild kernel quota state.
- iperf3 servers **MUST** be time-limited; Web shutdown closes temporary processes and project forwarding rules. Code **MUST NOT** reset host-wide `ip_forward` or remove unrelated firewall rules.
- Public listener and console route boundaries **MUST** remain separate. Trusted proxy headers **MUST NOT** authorize passwordless IP login.
- Same-layout installs **MUST** retain state. Old layouts or missing locators **MUST NOT** be silently overwritten as fresh installs.
- Third-party artifacts **MUST** match pinned hashes and retain original licenses and corresponding source access. Artifact verification is not a complete OS dependency lock.

## Design Tokens

The existing Python service retains its design system. Color tokens live in `src/web/static/styles/foundation.css`, themes and dark variants in `shell.css`, and fonts in `components.css`; it does not migrate to the Vue starter. Check stylesheet consistency with `python3 tools/build-styles/build_styles.py --check`. This verifies that the combined asset matches its sources, not visual acceptance.

## Data Design

| Location | Data |
| --- | --- |
| `/var/lib/vps-server` | Default layout-1 state root, located through `/etc/vps-server/state-dir`. |
| `admin_password.txt`, `console_port.txt`, `.env`, `paths.json`, `.layout-version` | Authentication, persisted port, configuration and path/layout metadata. |
| `certs/` | TLS certificates and private keys. |
| `data/` | SQLite visitor database, sessions/signing secret, feature state, node manifest and jobs. |
| `/etc/vps-server-proxy/config.json` | Singbox runtime configuration coordinated with the managed node manifest. |
| `/etc/vps-server-frps/frps.toml` | FRPS server configuration. |
| `/etc/frp/frpc-<name>.toml` | FRPC instance configuration; non-ASCII names map to stable unit aliases. |
| `/etc/vps-server-lucky` | Native Lucky settings and tasks. |
| `~/apps/PORTS.md`, `~/apps/.ports.lock` | Host port ownership registry and mutex. |

State permissions reflect sensitivity; backups and configuration are not public static assets. FRPC job files `data/frp-jobs/*.json` use mode `0600`, remove request credentials before execution and retain job results. Forwarding rules are stored as project JSON and replayed on startup, without saving the host-wide ruleset. See README for backup and manual recovery.

## External Interfaces

- Web pages/forms serve project management actions; authenticated reveal/copy endpoints return sensitive values. `/frp/client/structured` and `/frp/client/rename` are POST actions, not standalone display pages.
- LibreSpeed uses `/speedtest/garbage`, `/speedtest/empty` and `/speedtest/getip` with an original Python backend; measurements describe the current client-to-server path.
- Privileged helpers use allowlisted actions for systemd, FRP validation, nft/iptables and installation; they expose no arbitrary-command API. Root PTY access is limited to password-rechecked terminal sessions.
- FRPC connects to a configured server; structured editing supports simple token-authenticated TCP/UDP proxies.
- Tailscale CLI talks to the local daemon; authentication and route approval belong to the control server/Tailnet. Lucky uses its independent native management port.
- Addresses come from local interfaces and configured FRPC server values; the installer does not query public-IP services.
