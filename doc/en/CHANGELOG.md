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

### v5.7.0 — 2026-11-08

Stronger console login security. The upgrade command is unchanged and configuration and data are kept; the installer mentions 4 new optional variables, and leaving them unset keeps the defaults. The new settings are under Settings > Security.

#### Added

- **Failed-login ban switch.** On by default. When off, nothing is banned, but failures per IP are still counted and an IP that reaches the threshold is marked "threshold reached, not banned", so you can test that detection works. Records can be cleared.
- **Escalating bans.** Each repeat ban of the same IP within a day lasts ten times longer: 30 seconds, 5 minutes, 50 minutes, about 8 hours, at most 24 hours (`VPSSRV_LOGIN_LOCKOUT_MAX_SECONDS`). A successful login resets it.
- **IPv6 /64 grouping and a global limit.** Addresses in the same /64 count together. When all sources together fail 20 times within 60 seconds, addresses that never logged in successfully cannot use the password for 5 minutes (`VPSSRV_LOGIN_GLOBAL_MAX_ATTEMPTS`, `VPSSRV_LOGIN_GLOBAL_LOCKOUT_SECONDS`); known addresses, certificate login and IP access are not affected.
- **Console access limit.** Off by default. When on, only listed IPs or networks can connect to the console; other addresses are dropped before the TLS handshake. It cannot be turned on, nor an entry removed, in a way that shuts out the current connection. If you are locked out, run `python3 /root/apps/vps-server/src/web/console_access.py disable` as root; no restart is needed.
- **Signed-in devices.** Lists signed-in devices (browser, system, IP, sign-in and last activity) and can sign out one device or all others. Logins end after 2 hours without activity (`VPSSRV_SESSION_IDLE_SECONDS`); terminal input counts as activity.
- **Security log and Bark login alerts.** Records logins, bans, root terminal sessions and security setting changes, and shows the latest 50. With a Bark key, logins from a new address and bans are pushed to your phone; the key is never shown on the page.

#### Improved

- Console responses carry a Content-Security-Policy that allows only the console's own scripts, and forbid embedding by other sites. The former inline script moved to its own file.

#### Fixed

- Behind a reverse proxy (`VPSSRV_TRUST_PROXY=1`), the client address is now the last `X-Forwarded-For` entry the proxy appended, so a forged header no longer affects rate limiting, logs or the access limit.
- The login page leaves space between the certificate login button and the password label.
- The README extraction commands and the installer's own extraction name the `tar` filter explicitly, removing the `DeprecationWarning` on Python 3.12 and 3.13.

#### Verification

Local runtime tests cover bans, the switch, IPv6 grouping, the global pause, the access limit, signed-in devices, the security log and Bark alerts against a mock server; 15 pages show no CSP violations in a headless browser. The operator installed `v5.7.0-test.1` and `v5.7.0-test.2` online on a LAN test machine and confirmed failure counting, marking while off, banning while on and the new layout. Not yet tested with a real Bark account or behind a real reverse proxy.

### v5.6.3 — 2026-11-06

**Upgrading is recommended for everyone, especially hosts installed from the offline package.** The upgrade command is unchanged and configuration and data are kept. Run the upgrade over SSH, not in the console's own terminal.

#### Fixed

- pcre2 in the system runtime bundled with the offline package (nft, iptables, `ip`, `ss`) is updated to the Debian security release 10.46-1~deb13u3, which fixes an oversized JIT stack allocation (GHSA-r9hj-j2rw-4q3m). Packages were previously taken only from the Debian main archive, which missed the security archive; the other 31 packages were checked one by one and match current Debian 13. Upgrades replace the installed runtime.
- Upgrading from the console's own terminal showed only a bare `Terminated`, with no sign whether the installation was still running. It now warns up front that the terminal disconnects when the console restarts while the installation continues in the background, and gives the command to check the result; an interrupted progress view also says the installation continues.
- Console restarts no longer stall for 90 seconds: open terminals are now hung up properly on shutdown.

#### Improved

- After a client certificate is generated, the page now shows four steps: download, import into the system certificate store (Windows, macOS, Android and iOS each explained, plus Firefox's separate store), fully quit and reopen the browser, and confirm the certificate is in use before turning on Require client certificate. Security settings explain the usual causes when certificates exist but the current connection presented none.

#### Internal maintenance

- Upstream binaries such as sing-box, frp, Lucky and Tailscale are no longer committed; the offline build downloads them from pinned URLs and verifies each SHA-256. Package contents are unchanged. Source installs download these programs at install time, like the online package.

#### Verification

Verified in a throwaway Debian 13 container: upgrades from v5.6.2 run both inside the console terminal's control group and from a normal shell; nft, iptables, `ip` and `ss` from the new runtime run; an offline package built from a fresh clone carries byte-identical programs and installed and ran the proxy module. The certificate import steps were checked as page content only and are not yet tested on macOS, Android or iOS.

### v5.6.2 — 2026-11-06

**Upgrading is strongly recommended, especially on hosts with the Tailscale module.** The upgrade command is unchanged and configuration and data are kept.

#### Changed

- Bundled components updated: Tailscale 1.102.4 → 1.104.5, sing-box 1.13.14 → 1.13.21, frp (FRPS, FRPC) 0.71.0 → 0.72.0. All three match the upstream published checksums.
  - Tailscale 1.104.4 fixes security bulletins TS-2026-014 to 017 (Tailscale SSH and serve). This project does not enable either feature, so default use is not affected; hosts where Tailscale SSH was turned on manually should upgrade promptly.
  - frp 0.72.0 fixes lost frpc configuration on reconnect, a CPU busy loop after session close and a data race that could crash the process.
- Upgrades now replace the older FRPC client this project installed (`/usr/local/bin/frpc`) and restart running instances; an frpc placed or changed by the user is left alone. Uninstall still recognizes the older client.

### v5.6.1 — 2026-11-06

**All users are strongly advised to upgrade.** This release only updates a security-relevant dependency; the upgrade steps are unchanged and configuration and data are not affected.

#### Fixed

- The console frontend's vue-i18n moves from 11.4.13 to 11.4.18, fixing two cross-site scripting (XSS) advisories (GHSA-8rc2-428q-7ww3, GHSA-83rm-6c8r-g728). Analysis of the current code found no exploitable path, since the console does not enable `escapeParameter` or render translations as HTML; the upgrade keeps a dependency with open advisories off installed systems.

### v5.6.0 — 2026-11-06

#### Added

- Client-certificate login. Settings > Security > Client certificates issues a `.p12` certificate per device (the import password is shown once); once imported into the system, the browser logs in with it instead of a password. Certificates can be revoked one by one, and the server never keeps a device's private key. With "Require client certificate" on, a device without a valid certificate sees only a block page (IP allowlist login also needs a certificate), the password is used only to re-verify the root terminal and security settings, and Clash subscriptions keep working. It cannot be turned on unless the current connection presents a certificate, and the certificate in use cannot be revoked while it is required; after losing a certificate, root runs `python3 /root/apps/vps-server/src/web/client_cert.py disable` to restore password login. Issuing, importing, certificate login and turning the requirement on were verified in Chrome on Windows.

- When the host lacks a working nftables, installing Singbox from the installer or from a console module job now installs it with apt first instead of asking for a manual command; it stops with a reason only when apt is missing or the install fails. Uninstalled module cards in the console say it will be installed automatically.

#### Changed

- The console is served over HTTPS only. `VPSSRV_CONSOLE_TLS=0` no longer has an effect, and an install that ran over HTTP moves to HTTPS on upgrade with the same port. The installer installs `openssl` with apt when it is missing, for issuing certificates.

### v5.5.1 — 2026-10-23

#### Fixed

- The offline package no longer announces a download during install: nothing is downloaded or announced when the components are already in the package, and the notice appears only when a download is actually needed.

### v5.5.0 — 2026-10-23

#### Added

- Releases now ship two packages. The offline package bundles every third-party program and system tool; the target needs no network, curl, Git, tar or gzip, only Python 3.9+. The online package is about 4 MB: the installer downloads Singbox, Lucky, FRP and Tailscale for the selected modules, verifies each by SHA-256, and installs any missing iptables, iproute2 and nftables with apt. Adding the FRPC or Tailscale module later from the console downloads them the same way.

- The offline package's bundled runtime now includes iproute2 (`ss`, `ip`) and its libraries. When the host lacks these commands the bundled ones are used, and the missing-`ss`/`ip` warning no longer appears.

- The language prompt at the start of an install continues with the default after 5 seconds without an answer, so unattended installs finish on their own. `VPSSRV_PROMPT_TIMEOUT` changes the seconds; `0` waits forever.

#### Changed

- Installation no longer depends on curl, tar or gzip: the one-line install command, unpacking the Tailscale and nftables runtimes, and host checks now use Python's own tarfile and urllib. Minimal images do not need these commands installed first.

- The offline package grew from about 98 MB to about 167 MB because it carries iproute2 and its source.

- The browser tab title separator changed from the long dash `—` to a short hyphen `-`.

- The build script retries when downloading Debian packages fails.

### v5.4.0 — 2026-10-21

#### Added

- The complete package bundles Debian 13 nftables 1.1.3 and iptables 1.8.11 together with glibc, started by the bundled loader. On Debian 11+ and Ubuntu 20.04+ hosts without nftables or iptables, or without network access, node traffic accounting, rate limits and port forwarding still work. A host copy that can read the rules is still preferred; Web-only installs also receive this runtime.

- Host requirements are checked before a module is installed: Singbox needs a working nftables, and Tailscale needs `/dev/net/tun` and no other running tailscaled. The installer, console install jobs and the cards and install pages of uninstalled modules share these checks; when one is unmet, the install stops before changing anything and shows the reason and fix instead of a bare "failed".

- On a first install the command stays in the foreground following the background job, showing only key steps and then the console address and initial password; on failure it shows the reason and a few related log lines. Ctrl-C or an SSH disconnect only stops the display; the install continues.

- Feature pages for a missing module can install it directly and show progress in place.

- A failed settings save shows an 8-second toast, and the page no longer repeats the same error inline.

#### Changed

- Fresh installs serve the console over HTTPS with a self-signed certificate, and session cookies carry `Secure`; upgrades keep the previous setting.

- Installing Singbox, Lucky or Tailscale from the console installs only that module; Web and other modules keep running.

- Before stopping any service, the installer checks the Python version (stopping below 3.9) and iptables, `ss` and `ip` (warning when missing and naming the affected features).

- Node meter errors now include nft's own error message.

#### Fixed

- On Debian 13 hosts without system nftables, the node meter restarted in a loop and stopped Singbox: the old bundled nft 0.9.8 cannot read rules written by newer iptables-nft, and the install preflight only ran `nft --version`, so it did not catch this. The preflight and runtime checks now actually read the ruleset.

- Port forwarding and iperf3 forms lacked CSRF tokens, so a page on another port of the same host could submit them.

- Idle connections pre-opened by browsers could make the HTTPS console and public page stop answering: TLS handshakes now run in each connection's worker thread with a 10-second timeout.

- Changing the console port restarted Web while holding a lock, so the new process timed out releasing a stale iperf3 port registration and crashed; a failed release of stale registrations also no longer stops Web from starting.

- Installing Lucky from the console stopped Singbox; after uninstalling Lucky its page no longer offered an install button.

- A failed first Tailscale install left its unit file and binaries behind, and the rollback could miss releasing port registrations.

- The install summary's public page status disagreed with the console switches; FRPS/Lucky installs failed and rolled back on a firewall rule that was already gone; the proxy configuration file is now 0600, and BBR uses its own sysctl file that a full uninstall removes.

- The terminal page and the FRPS and FRPC not-installed pages used the home tab icon.

### v5.3.1 — 2026-10-07

#### Fixed

- Installing with a shorter `VPSSRV_MODULES` (such as the README quick install) dropped installed modules from the record and stopped sing-box through the node-meter dependency: an explicit list now only adds modules, and modules still present on disk are counted again.

- A foreign process on a public page port aborted every install and module job of an existing install; it is now a warning. A missing frontend bundle now stops the install before anything is written, instead of leaving a partial state directory that blocked later installs.

- Uninstalling Singbox removed every node: it now keeps the sing-box configuration and node inventory and releases only the service, firewall rules and port registrations. Reinstalling registers the kept nodes' ports again (failing cleanly if one is in use) and reopens their firewall rules. The uninstall confirmation now says the configuration is kept.

- Reinstalling Lucky failed with "Address already in use" because connections the console had just closed were in TIME_WAIT: the Lucky and FRPS setup scripts and the node, FRP and iperf3 port checks now probe with `SO_REUSEADDR` like the servers do.

- Uninstalling FRPC stopped every instance and reinstalling did not bring them back: the uninstall now remembers which instances were enabled and the reinstall enables them again, unless the whole FRPC group is switched off.

### v5.3.0 — 2026-10-07

#### Added

- Shared interface components: the header and the new footer (GitHub profile, project repository) glide item by item when the window is resized; the settings section navigation eases along while scrolling and becomes a top bar on narrow screens; the tab icon follows the theme color and light/dark mode; Appearance gains "Follow system"; the server label badge links back to the dashboard.

- The Clash QR code opens from a button in a dialog; confirmations for uninstalling, clearing log history, deleting a proxy and clearing visitors use the console's own dialog instead of the browser prompt.

#### Changed

- The Web frontend now uses the shared template (Vue 3, Vite, TypeScript, Tailwind CSS): unified design tokens, eight theme colors and responsive layout, with page content as wide as the header. The frontend is built in `web/` and the complete package includes the build output; source installs must first run `npm ci && npm run check` in `web/` (Node.js 24).

- The top left of the header shows only the project name, without the logo (a project exception recorded in `doc/LOG.md`).

- The public page (80/443) returns a single plain-text line, "The server sees your IP address".

- On refresh the server-rendered fallback layout stays hidden until the shared header and the styled dropdowns are ready, so the old layout and native dropdowns no longer flash.

- iPerf 3, Singbox, FRPS, FRPC, Lucky, Tailscale and Terminal pages were re-laid out: iPerf 3 page title with Server and Client cards, left-aligned Singbox counters, FRPC instance heading and new-instance button on one row, a larger terminal with a smaller font. The Lucky admin page and the home HTTP and HTTPS tiles open in a new tab. The Tailscale connect button joins the same row, the version shows only the release number, and the route and exit node lists no longer have a "Clear" entry.

- Tool directories now use hyphenated names (for example `tools/build-offline`), a shared static check `tools/check-project` was added, and CI pins its Actions; installation commands are unchanged.

#### Fixed

- Installing or toggling iperf3 restarted Web while the status page was loading, leaving the page on the old state.

- The installer aborted during an upgrade because TIME_WAIT sockets left by just-closed connections were mistaken for ports 80/443 being in use.

- Repeated clicks on Tailscale "Connect" failed: only one connection runs at a time, the login address is awaited, and the button is disabled after a click (Tailscale works on the real host, confirmed by the operator).

- Black strip at the bottom of the terminal, empty card on closed-module pages, wrong target of the back control on the detailed log page, and duplicated page icons.

### v5.2.3 — 2026-10-05

#### Changed

- Rebuilt project documentation using the current standards, with Simplified Chinese, English, and Spanish versions.

- Simplified quick installation to one command that installs only Web by default, and added offline steps under regular installation.

- Added 16 real interface screenshots to README, grouped in collapsible sections with addresses and credentials hidden.

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
