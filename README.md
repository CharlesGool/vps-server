---
name: project-readme
description: Project overview and usage
metadata:
  version: "1.0.0"
  lang: "en"
---

# vps-server

## Multi-language

**English** | [简体中文](doc/zh-CN/README.md) | [繁體中文 (台灣)](doc/zh-TW/README.md) | [繁體中文 (香港)](doc/zh-HK/README.md) | [हिन्दी](doc/hi/README.md) | [Español](doc/es/README.md) | [العربية](doc/ar/README.md) | [Français](doc/fr/README.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](doc/DESIGN.md)

- Release history: [LOG](doc/LOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](doc/THIRD_PARTY_NOTICES.md)

## Introduction

A module-selecting bundle for a Debian/Ubuntu VPS: a public page to check web-port
reachability, an operator console for speed tests and connection logging, an
on-demand iperf3 window, and sing-box proxy nodes. Version 3.0.0 adds managed
nodes, traffic policies, private-IP access, and light/dark appearance choices.
The bundle also includes experimental frps and Lucky installers.
See [current state and acceptance limits][local-link-001].

## What it does

- **Proves reachability to anyone.** A deliberately minimal page on ports **80**
  and **443**, no login. Hand someone the IP; if the page renders, your web
  ports are reachable from where they are. It reports their source IP, the
  server clock, and which port and protocol they arrived on — and nothing else
  about the host.
- **Measures throughput from a browser.** A console on a persisted random high
  port runs up/download tests using the LibreSpeed engine. It accepts an admin
  password or an explicitly allowed private LAN IP. The login page always shows
  the IP access button; an unlisted visitor is guided to password login and
  access settings. Security Settings requires a recent administrator-password
  verification before showing its IP list or accepting changes. The allowlist
  accepts individual private IPv4 and unique-local IPv6 addresses, with a
  separate switch to disable IP access without deleting entries. Appearance
  and language choices are available on the ordinary Settings page; its Security
  section asks for the administrator password when verification has expired. Password
  changes invalidate existing sessions.
- **Measures throughput and latency with iperf3, on demand.** The console opens
  a time-boxed window; `iperf3 -s` runs only inside it and shuts itself down
  when the window expires. Its status and port are shown separately; the port
  can be changed while the window is closed and survives a service restart.
  The tester gets bandwidth from iperf3, and on a
  Linux client also round-trip time from `mean_rtt` in its `--json` output —
  that field comes from the kernel's `TCP_INFO` and is absent on clients that
  cannot read it, notably iperf3 under Cygwin on Windows. UDP mode (`-u`) adds
  jitter and loss on every platform.
- **Logs who connected.** Every inbound TCP connection, on any port, not just
  HTTP — read from `/proc/net/tcp[6]`, stored in SQLite, most recent 1000 kept.
- **Serves an anytls proxy.** sing-box with a self-signed certificate, plus BBR.
  The authenticated `/proxy` page shows the node status, traffic, editable
  connection settings, and a one-tap Clash Meta for Android import link with a
  copyable subscription URL and QR code when a private LAN address is available.
- **Serves vmess/vless/trojan/shadowsocks proxies, any subset.** One more
  sing-box process shares the vendored binary with anytls. Each installed
  protocol starts with a numbered node. The console can create more nodes of
  any installed protocol and delete individual nodes. New nodes accept a manual
  password or protocol-specific key/UUID, or generate one when the field is blank; TLS nodes default to
  `www.bing.com` for SNI. The node page lists interface and Tailscale addresses.
  Each node can have a traffic cap in GiB, separate upload and download speed limits
  in Mbps, and a choice to throttle both directions to 1 Mbps or block traffic
  after the cap. A configurable cycle of days, months, or years clears period
  usage; an optional validity duration blocks traffic when it ends. Connection
  and limit editors remain separate, alongside random-reset controls,
  plus the same LAN-only Clash Meta import and subscription-link copy options.
  The import URL contains an opaque token and changes after the node's connection settings
  or name changes. The public ports do not serve proxy configurations.

The selectable modules are web, iperf3, anytls, proxy, frps, and Lucky. frps
and Lucky remain experimental; their behavior has not been accepted on a real
host for this version.
The authenticated FRPS page shows the local server service, interface
addresses, and connection settings, with its token and port masked until
requested. The FRPS port and token can be edited in place and its service can
be switched on or off. The separate FRPC page lists local client instances as cards with
a masked IP and a connection indicator based on its established TCP socket.
Its Test connection button makes a separate FRPC login using the saved server,
port, and token. The instance page reveals the IP or token on request and
shows each TCP/UDP proxy's type, local IP, local port, and remote port before
editing. Saves keep the operator on the instance page, verify the file, and
roll back on failure. These FRP actions use the signed-in session; recent
administrator-password verification is reserved for Security Settings actions
such as password and password-free IP changes. The field editor accepts simple
token-authenticated TCP/UDP configurations only; it does not alter unsupported
FRPC TOML. FRPC instances on other devices remain outside this console's live
status. The Modules page checks the local FRPC executable and
`frpc@.service` template separately from server-instance configurations. It
offers Install if either executable or template is absent, and shows a Create
instance link when FRPC is installed with no instances. Install uses the
checksum-verified FRPC v0.71.0 release asset and creates no connection or listener.
The module log records its download and verification. For an offline install,
download [frpc-0.71.0-linux-amd64](https://github.com/CharlesGool/vps-server/releases/download/v4.0.0/frpc-0.71.0-linux-amd64)
(16,593,080 bytes; SHA-256
`f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`)
and place it at `~/apps/vps-server/vendor/frp/frpc` before choosing Install.
The install job checks the same digest for a downloaded or manually placed file.
Uninstall stops local FRPC instances, backs up their configurations under
`data/`, and retains the configuration files for later reinstallation.

**Non-goals:** no ACME or domain names (443 is self-signed on purpose); no
always-on iperf3; no reverse proxy or containers; the public page never reveals
the hostname, kernel, uptime, service list, or proxy parameters. This project
does not replace `vps-webserver` or `Anytsl-Serve` — both remain independently
maintained, and their code is vendored here rather than absorbed.

## Requirements

- OS: Debian 11+ or Ubuntu 20.04+, systemd, run as root
- Runtime: Python 3.9+ (the distro's `python3` is enough — there are no Python
  dependencies to install)
- Architecture: any for the web and iperf3 modules; **x86-64 only** for anytls,
  proxy, frps, and Lucky, because the bundled executables target amd64
- For the web module on its default public ports, 80 and 443 **MUST** be free — the
  installer refuses rather than competing with nginx, Apache, Caddy, or `vps-webserver`
- External services: none at runtime. Installation needs your distro's package mirror; the node summaries use interface and optional Tailscale addresses without an outbound public-IP lookup.
- Minimum: the OS, runtime, architecture, and free ports above. No additional recommended hardware requirement is recorded; a VPS with roughly 150 MB disk accommodates the vendored binary.

## Install

One-line quick install (latest release tag, no configuration variables):

```bash
git clone --branch v4.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

Step by step, with configuration:

```bash
# Clone a release tag; the default branch can contain unpublished changes.
# List release tags: `git ls-remote --tags https://github.com/CharlesGool/vps-server.git`
git clone --branch v4.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # optional — every variable has a working default
bash deploy/install.sh
```

`deploy/install.sh` asks which modules to install, the interface language,
whether to password-protect the console, and which ports to use. The v4.0.0
tag includes all six selectable modules; frps and Lucky are experimental.

### First setup

The setup flow below is included in v4.0.0. On a new Debian or Ubuntu installation,
clone the release tag and run `bash deploy/install.sh` as root from a terminal. The
default application directory is the root account's `~/apps/vps-server`;
`PREFIX` can select another directory.

The installer opens a temporary HTTPS setup page on a random available port
and prints its URL, certificate fingerprint, and one-time random setup password
in the terminal. The page expires after five minutes if no selection is made.
Sign in there and choose the modules to install; the Web console is required
for browser setup. Proxy protocols are asked only when proxy nodes are selected.
After submission, refresh the setup page to see progress. When installation
finishes and the host has a usable interface address, it links to the control
panel; otherwise use the address printed in the terminal. The terminal prints
the persistent control-panel password and address; the one-time setup password
does not log in to the control panel. The temporary listener closes and
releases its port after the completion grace period.

From the control panel, open **Settings → Modules**. An ordinary signed-in
session can manage these operational functions; password verification remains
required for Security Settings. The module list contains Speed test, iperf3,
Proxy nodes, FRPS, FRPC, Port forward, Recent visitors, Changelog, and Settings.
Only separately installable functions show Install or Uninstall. Before
uninstalling one, the helper stores a private configuration archive under
`$PREFIX/data`; the latest job output is visible on the Modules page. Optional
modules install from version-matched files under `$PREFIX/installer-source`.
Every Home card except Settings has its own switch. The Proxy nodes switch
controls both AnyTLS and the other proxy protocols; it keeps node records and
does not start a service with zero enabled nodes. The FRPC switch restores
instances that were running before it was turned off. Port forwarding keeps
saved rules when switched off and reapplies enabled rules when switched on.
An installation runs as an independent systemd job and can briefly restart
the Web service. If the setup port is unreachable,
use `VPSSRV_SETUP_PUBLIC=0` with a local SSH tunnel or choose a permitted port
with `VPSSRV_SETUP_PORT`.

For a host with FRPC installed, open the **FRPS** or **FRPC** card from Home.
**Edit FRPS** changes its bind port and token; a blank field keeps its current
value. Updating these values requires updating FRPC instances that connect to
this FRPS server. A local FRPC card has separate Test connection, Edit, and
confirmed Delete controls; clicking its background does nothing. Its start
switch sits beside the instance name. Open Edit to rename the instance or
change its server and proxy mappings in place. Click a masked IP, port, or
token to reveal it; opening Edit server loads the saved values. Test
connection performs a temporary login with the saved values; it does not start
or change the managed instance. Save validates with `frpc verify` and restarts
an active instance, then returns to the same instance page. New instances are
enabled after their first valid save. The page can also start or stop an
existing instance without deleting its configuration. Changes to local FRPC
instances do not alter clients on other devices. For a TCP proxy,
allow its `remotePort` in any active host firewall and cloud security group;
the editor registers same-host port assignments but does not change cloud
firewall rules.

**Re-running it upgrades in place.** It detects an existing install, offers to
keep its configuration, and only asks about settings the installed version did
not have — each with its default, so pressing Enter is a valid answer. The
console password, the persisted port, the certificates, the visitor log, the
anytls node's credentials, and every installed
proxy protocol's port and credential all survive. Answer `n` to the upgrade
question to re-ask settings instead.

## Guidance

### Quick start

Version 2.0.0 puts web implementation in `src/web/app.py` and runs installers
from `deploy/`. Bundled binaries and license notices are under `third_party/`;
release metadata is under `config/`. Installed files remain flat under
`$PREFIX`; the checkout layout change does not migrate runtime data. The
new paths have passed local tests, but this version has not been accepted on a
real host.

```bash
bash deploy/install.sh                       # interactive setup in a temporary browser wizard
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # unattended, no prompts
systemctl status vps-server-web              # is it up
bash deploy/anytls/setup-anytls.sh status           # anytls node details, if that module is installed
bash deploy/proxy/setup-proxy.sh status             # proxy node details, if that module is installed
```

Then, from a different machine:

```bash
curl -sS  http://<ip>/                     # reachability over plain HTTP
curl -sSk https://<ip>/                    # ... and over TLS (self-signed)
iperf3 -c <ip> -p 5201 --json              # only while a window is open
```

### Verify it works

After `bash deploy/install.sh` you should see a summary block naming each installed
module and its port. Then:

- `systemctl status vps-server-web` reports `active (running)`.
- Opening `http://<ip>/` from **another machine** renders a page headed
  "Reachable" that shows your own public IP. Opening `https://<ip>/` shows the
  same page after you accept the certificate warning, with the protocol line
  reading HTTPS.
- Logging in to `http://<ip>:<console port>/` shows the dashboard with the
  iperf3 control present and the window closed.
- After opening a 5-minute window, `iperf3 -c <ip> -p 5201 --json` from another
  machine reports a throughput figure and contains `mean_rtt`. Five minutes
  later the same command fails to connect — that is the window closing itself,
  not a fault.
- If you installed anytls: `systemctl status vps-server-anytls` reports
  `active (running)`.
- If you installed proxy: `systemctl status vps-server-proxy` reports
  `active (running)`.

### Configuration

Every variable has a working default; `.env` is optional. The most load-bearing
ones:

| Variable | Meaning | Default | Required |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | Public reachability page, plaintext | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Public reachability page, TLS | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Serve the public page at all | `1` | no |
| `VPSSRV_CONSOLE_PORT` | Console port; `0` generates one and remembers it | `0` | no |
| `VPSSRV_AUTH` | Require a password on the console | `1` | no |
| `VPSSRV_IPERF_PORT` | Port an open iperf3 window listens on | `5201` | no |
| `VPSSRV_IPERF_MAX_MINUTES` | Cap the console cannot exceed | `60` | no |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | no |

Full reference: [Configuration reference][local-link-002].

## Upgrade

To upgrade, use a current checkout and rerun the installer with the same installation directory and module choices. Keep a backup of persistent data until the upgraded services and console have been verified.

## Uninstall

Run as root, from the installer checkout, with the same `PREFIX` and
`SERVICE_NAME` values used at install time (the installer's summary prints
the exact removal command). To remove the installed modules and units **while
keeping data** in `$PREFIX` for a later reinstall:

```bash
KEEP_DATA=1 bash deploy/uninstall.sh
```

To remove the installed modules and **delete data as well** (including the
visitor log, console password, saved port, and certificates in `$PREFIX`):

```bash
bash deploy/uninstall.sh
```

Both modes tear down the anytls/proxy services and their separate module
configs if installed. `KEEP_DATA=1` retains `$PREFIX`, not those module configs.

## Acknowledgements

The browser test uses [LibreSpeed](https://github.com/librespeed/speedtest);
QR rendering uses [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator);
the bundled proxy core is [sing-box](https://github.com/SagerNet/sing-box).
The experimental modules bundle [frp](https://github.com/fatedier/frp) and
[Lucky](https://github.com/gdy666/lucky). See [third-party notices][local-link-003]
for the inventory and original license paths.

## License

Project license: GPL-3.0 (SPDX: `GPL-3.0-only`); read the full [LICENSE][local-link-004]. The historical combination rationale is in [Decisions][local-link-005]. Bundled components, their original licenses, verified artifact sources, and remaining legal-review limits are in [THIRD_PARTY_NOTICES.md][local-link-006].

This project is not affiliated with or endorsed by sing-box/SagerNet or
LibreSpeed.

[local-link-001]: doc/LOG.md#current-state-and-acceptance-limits
[local-link-002]: doc/DESIGN.md#configuration-reference
[local-link-003]: doc/THIRD_PARTY_NOTICES.md
[local-link-004]: LICENSE
[local-link-005]: doc/LOG.md#decisions
[local-link-006]: doc/THIRD_PARTY_NOTICES.md
