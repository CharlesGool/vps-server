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

After language selection, the installer starts background job `vps-server-install` and follows its `summary.log` in the foreground, showing only key steps, the address and password, or the failure reason. Before stopping any service, the installer checks minimum host component versions (the `core` check: Bash, systemd, SQLite, the OpenSSL library used by Python, basic commands). Module host requirements (nft able to list tables, `/dev/net/tun`, an existing tailscaled, iptables and `ss`/`ip`) come from `src/web/host_checks.py`; the installer, console module jobs and uninstalled module cards share its result codes. Console module installs use `VPSSRV_MODULE_ONLY=1` to install only the selected module while Web and other modules keep running. FRPC save/rename returns a waiting page before background validation and application, followed by a delayed instance restart. Status polling retries after tunnel interruption; success or failure comes from the actual job result.

| Directory | Responsibility |
| --- | --- |
| `.local/` | Git-ignored maintenance files, historical snapshots and private notes; excluded from deployment. |
| `.github/` | Continuous checks and Actions dependency maintenance. |
| `src/` | Web source, feature handlers and static resources. |
| `web/` | Vue shared components, tokens, feature styles and frontend build configuration. |
| `deploy/` | Install/uninstall scripts, module setup and systemd templates. |
| `config/` | Version, pinned artifact hashes and import provenance. |
| `lang/` | UI/installer translations; config value `zh_cn` selects Simplified Chinese. |
| `third_party/` | Upstream executables, archives, licenses and provenance. |
| `tools/` | Style build, dependency verification and offline packaging tools. |
| `doc/` | Design, status, history, changes, notices and translations. |

Frontend source is in `web/`, using Vue 3, Vite, TypeScript, Tailwind CSS and shadcn-vue template components to enhance server pages. Python retains business forms, authentication and authorization. Shared components provide the header, footer, page heading, card grid, section navigation, theme listbox and mode control. Navigation uses full same-origin links.

`web/src/styles/tokens.css` is the only visual-value source; `web/src/styles/legacy/` bridges existing forms through semantic tokens. Run `npm ci && npm run check` in `web/` for design/type checks and the production build. Output is `web/dist/ui.js` and `ui.css`, copied into installed static resources and included in offline packages; the VPS needs no Node.js. Original dependency texts and identities accompany the build in `web/dist/licenses/`. Build output and dependencies are Git-ignored.

`.github/` runs the same checks; `.claude/settings.json` runs the template design check after edits. `tools/check-project/check_project.py` also checks Python/Bash/JavaScript, translations, documents and pinned artifacts. `tools/build-offline/build_offline.py` builds two packages: the offline one (default) bundles every third-party program and the Debian 13 runtime (nft, iptables, `ip`, `ss`); the online one (`--variant online`) omits the large binaries, and `src/web/online_assets.py` downloads and SHA-256-verifies them at install time from `config/online-assets.json`. These upstream binaries are not committed to Git; the offline build uses the same module to download them into `third_party/` (ignored by Git) before packaging. `fetch_assets.py` downloads and verifies the nftables runtime and its corresponding sources. Installing and unpacking either package needs only python3, not curl, tar, gzip or Git. Components receive the actual backend build version; formal changelogs still come from translated CHANGELOG files.

## Design Constraints

- Sensitive values **MUST** require authentication and any required password recheck; initial HTML **MUST NOT** embed hidden real credentials. Editors **MUST** load existing values rather than overwrite unchanged values with blanks.
- Ports **MUST** be locked and recorded before activation; failures release new reservations. Other projects' reservations **MUST NOT** be taken.
- FRP changes **MUST** validate first and retain or restore old settings on failure. Structured editing **MUST NOT** discard unsupported advanced configuration.
- Quotas count `(upload + download) × 2`; missing meter readings **MUST NOT** count as quota exhaustion. Cycle resets **MUST** rebuild kernel quota state.
- FRPS uses the same accounting and nft rules as nodes, metered on its bindPort (`src/web/frps_meter.py`, separate table `vps_server_frps`); the FRPS service requires the meter, and a meter failure **MUST** stop FRPS.
- Client certificates **MUST** be signed with the bundled openssl and the project's own minimal configuration; a new certificate authority **MUST** first pass a mutual-TLS self test on the host TLS library.
- New CAs and device certificates carry the host name in their CN (ASCII letters, digits, dots and dashes only); existing CAs keep their name, since renaming would invalidate issued certificates. `cert_setup.py` generates the setup files; the versions that carry the certificate are offered only on the issuing page. Windows: a .cmd with embedded PowerShell that writes only the current user's certificate store and HKCU policies (no administrator rights), importing the key as non-exportable. macOS: a user-scope configuration profile (a PKCS#12 payload without the password, which the system asks for while installing, plus Chrome and Edge policy payloads). Linux: a bash script that imports with pk12util into `~/.pki/nssdb` and uses sudo to merge `vps-server.json` in each browser's policy directory, keeping other entries.
- iperf3 servers **MUST** be time-limited; Web shutdown closes temporary processes and project forwarding rules. Code **MUST NOT** reset host-wide `ip_forward` or remove unrelated firewall rules.
- TLS handshakes **MUST** finish in each connection's worker thread with a timeout; a handshake on the accepting thread lets one idle connection block the whole listener.
- Web restarts **MUST NOT** hold `.ports.lock`; the new Web process releases stale registrations through the same lock at startup.
- A single-module install **MUST NOT** stop, reinstall or disable another module's services.
- Public listener and console route boundaries **MUST** remain separate. Trusted proxy headers **MUST NOT** authorize passwordless IP login.
- When proxy address headers are trusted, the client address **MUST** be the last `X-Forwarded-For` entry the proxy appended; the entries to its left can be forged by the client and **MUST NOT** be used for bans or the access limit.
- Console pages **MUST NOT** use inline scripts or inline event attributes; responses carry a Content-Security-Policy with `script-src 'self'` and headers that forbid embedding by default. Inline styles stay allowed because xterm.js and the UI set styles at run time.
- The console access limit drops connections by source address before the TLS handshake, and loopback is always allowed; changes to the settings file apply immediately, and a damaged file counts as off so it cannot shut everyone out.
- The console **MUST** be served over HTTPS only. Client certificates are signed by the console's own CA (`certs/client-ca.*`), and the server **MUST NOT** keep device private keys; TLS only requests a certificate without enforcing it (`CERT_OPTIONAL`), and "require certificate" is checked per request at the HTTP layer against unrevoked serial numbers, so Clash subscriptions still work and revocation needs no TLS rebuild. Before the requirement is turned on, the current connection **MUST** present a valid certificate; while it is on, the certificate used by the current connection **MUST NOT** be revoked.
- Same-layout installs **MUST** retain state. Old layouts or missing locators **MUST NOT** be silently overwritten as fresh installs.
- Third-party artifacts **MUST** match pinned hashes and retain original licenses and corresponding source access. Artifact verification is not a complete OS dependency lock.

## Design Tokens

Use the latest starter tokens for typography, spacing, radii, shadows, containers, eight themes and motion. Shared components come directly from the starter; header/page-heading links preserve Python navigation. Additional `compat-*` tokens retain module-specific table/dialog dimensions and status variants. Typography, weights, radii and themes use template values. `--toast-lifetime-error` sets how long a failure toast stays (8 seconds). When a failed save redirects back with a `msg` parameter, the frontend shows the page's error as a toast and removes the inline copy. New components and pages only reference tokens. Check with `cd web && npm run check`.

## Data Design

| Location | Data |
| --- | --- |
| `/var/lib/vps-server` | Default layout-1 state root, located through `/etc/vps-server/state-dir`. |
| `admin_password.txt`, `console_port.txt`, `.env`, `paths.json`, `.layout-version` | Authentication, persisted port, configuration and path/layout metadata. |
| `certs/` | TLS certificates and private keys; the client-certificate CA (`client-ca.pem`, `client-ca.key`) and issuance record `client-auth.json` (requirement switch, serial numbers, device names, revocation state). |
| `data/` | SQLite visitor database, sessions/signing secret, feature state, node manifest and jobs; login security settings (`login-ban.json`, `console-access.json`, `alerts.json`), the security log (`security-audit.jsonl`) and known login addresses (`known-logins.json`). |
| `/etc/vps-server-proxy/config.json` | Singbox runtime configuration coordinated with the managed node manifest. |
| `/etc/vps-server-frps/frps.toml` | FRPS server configuration. |
| `/etc/vps-server-frps/traffic.json`, `traffic-meter.json` | FRPS traffic entry (cap, speed limits, validity, usage) and meter ledger. |
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
