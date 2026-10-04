---
name: project-readme-en
description: Project overview and usage
metadata:
  version: "1.0.0"
  lang: "en"
---

# vps-server

## Multi-language

[简体中文](../../README.md) | **English** | [Español](../es/README.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Introduction

A module-selecting bundle for a Debian/Ubuntu VPS: a public page to check web-port
reachability, an operator console for speed tests and connection logging, an
on-demand iperf3 window, and sing-box proxy nodes. The latest formal release is
v5.1.0. Current `main` is preparing the separate persistent state directory
and FRPS editor correction for v5.1.1; it has not been formally released. See
the [changelog][local-link-001] and [project status](../LOG.md) for release
scope and verification results.

## Features

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
  Ordinary Web service restarts preserve unexpired sessions, including when a
  public listener or iperf3 setting is switched.
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

A fresh installation includes only the Web console by default. `VPSSRV_MODULES`
selects web, iperf3, anytls, proxy, frps, and Lucky; optional modules can also be
installed from the console. FRPC is installed separately as a local client feature.
The authenticated FRPS page shows the local server service, interface
addresses, and connection settings, with its token and port masked until
requested. The FRPS port and token can be edited in place and its service can
be switched on or off. The separate FRPC page lists local client instances as cards with
a masked IP and a connection indicator based on its established TCP socket.
Its Test connection button makes a separate FRPC login using the saved server,
port, and token. The instance page reveals the IP or token on request and
shows each TCP/UDP proxy's type, local IP, local port, and remote port before
editing. Saves keep the operator on the instance page, verify the file, and
roll back on failure. FRPC instance names may use Unicode letters and numbers,
hyphens, and underscores, up to 32 characters. The name remains the suffix of
its the instance configuration file configuration file. These FRP actions use the
signed-in session; recent administrator-password verification is reserved for
Security Settings actions such as password and password-free IP changes. The
field editor accepts simple
token-authenticated TCP/UDP configurations only; it does not alter unsupported
FRPC TOML. FRPC instances on other devices remain outside this console's live
status. The Modules page checks the local FRPC executable and
`frpc@.service` template separately from server-instance configurations. It
offers Install if either executable or template is absent. Install uses the
checksum-verified FRPC v0.71.0 release asset and creates no connection or listener.
The module log records installation and verification. FRPC and FRPS v0.71.0
binaries ship with the repository. FRPC installation first checks the local
`vendor/frp/frpc` and can use the bundled copy retained by the installer,
without access to GitHub. Their sources and SHA-256 hashes are in the
[third-party notices](THIRD_PARTY_NOTICES.md).
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
- Architecture: the entire project supports x86-64 Linux only; the installer
  rejects other platforms before changing system state
- For the web module on its default public ports, 80 and 443 **MUST** be free — the
  installer refuses rather than competing with nginx, Apache, Caddy, or `vps-webserver`
- External services: none at runtime. FRPS, FRPC, and iperf3 install from bundled
  artifacts; other missing system packages may still require a distro mirror.
  Node summaries use interface and available Tailscale addresses without an outbound public-IP lookup.
- Minimum: the OS, runtime, architecture, and free ports above. No additional recommended hardware requirement is recorded; roughly 180 MB of VPS disk space accommodates the bundled binaries.

## Install

### Quick Install

Run as root on a fresh test host. By default, only the Web console is installed.
On first install, the installer prints the generated management port and
password. These commands check out the current `main` test source; the running
version displays `test-<SHA>`. v5.1.1 has not been formally released.
Installations of v5.1.0 or earlier cannot be migrated automatically; read
[Upgrade](#upgrade) first.

```bash
git clone --branch main --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

### Normal Install

```bash
git clone --branch main --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env  # Optional: set overrides described in the file
bash deploy/install.sh
```

In this test source, `PREFIX` defaults to `/root/apps/vps-server` and holds replaceable program files.
Passwords, the console port, certificates, runtime data, installation records,
and `.env` default to `/var/lib/vps-server`. Set `VPSSRV_STATE_DIR` in the command
environment before the first install to use another external directory. There
is no browser-based first-run wizard. Set
`VPSSRV_MODULES=web,iperf3,anytls,proxy,frps,lucky` to select server modules
explicitly; when omitted, only Web is installed. Install or remove optional
modules later from Settings → Modules. Enable the HTTP and HTTPS public pages
separately from Home. FRPC is installed separately when a local client is
needed, using the bundled binary.

## Guidance

### Quick start

The Web implementation is in `src/web/`, static assets in `src/web/static/`, and
installers in `deploy/`. Bundled FRPC, FRPS, and iperf3 binaries and license
records are in `third_party/`; release metadata is in `config/`. Installed
runtime code is in `$PREFIX/src/web/`, with only a compatibility entry point at
`$PREFIX/app.py`. Persistent state is in `$VPSSRV_STATE_DIR`; checking out or
replacing the program directory does not delete that state root.

There is no automated test suite in the source checkout. After changes, verify
installation, console, and service behavior for the enabled modules manually.
The current test source still bundles FRPC, FRPS, and iperf3. Formal tags retain
the behavior documented for their respective versions.

```bash
bash deploy/install.sh                       # install the Web console by default
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # select Web and iperf3 explicitly
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

After `bash deploy/install.sh`, check the printed management address, password, and module summary. Public ports are disabled by default; enable them in the console before checking them from another machine:

- `systemctl status vps-server-web` reports `active (running)`.
- Opening `http://<ip>/` from **another machine** renders a page headed
  "Reachable" that shows your own public IP. Opening `https://<ip>/` shows the
  same page after you accept the certificate warning, with the protocol line
  reading HTTPS.
- Logging in to `http://<ip>:<console port>/` shows the dashboard with the
  iperf3 control present and the window closed.
- After opening a 5-minute window, `iperf3 -c <ip> -p 5201 --json` from another
  machine reports throughput and, where the client exposes it, `mean_rtt`. Five minutes
  later the same command fails to connect — that is the window closing itself,
  not a fault.
- If you installed anytls: `systemctl status vps-server-anytls` reports
  `active (running)`.
- If you installed proxy: `systemctl status vps-server-proxy` reports
  `active (running)`.

### Configuration

Every variable has a working default. The first installation can import
`.env` from the source directory; afterward it is stored as `.env` in the state root.
Key variables:

| Variable | Meaning | Default | Required |
|---|---|---|---|
| `VPSSRV_STATE_DIR` | Persistent state root, set in the command environment before first install; `.env` cannot move it | `/var/lib/vps-server` | no |
| `VPSSRV_PUBLIC_HTTP_PORT` | Public reachability page, plaintext | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Public reachability page, TLS | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Whether to serve public pages at first install; Home controls HTTP and HTTPS separately afterward | `0` | no |
| `VPSSRV_CONSOLE_PORT` | Console port; `0` generates one and remembers it | `0` | no |
| `VPSSRV_AUTH` | Require a password on the console | `1` | no |
| `VPSSRV_IPERF_PORT` | Port an open iperf3 window listens on | `5201` | no |
| `VPSSRV_IPERF_MAX_MINUTES` | Cap the console cannot exceed | `60` | no |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `es` | `en` | no |

Full reference: [Configuration reference][local-link-002].

## Upgrade

The planned `v5.1.1` starts persistent state layout `1`. **Automatic migration is not supported**
from v5.1.0 or earlier. If old data remains, back it up outside
the installation directory and explicitly perform a fresh install. Data that
was deleted without a backup cannot be recovered. If the installer finds an
old service or missing state, it stops before changing services; it does not
generate a new password or port for the old installation.

To upgrade from v5.1.1 to a later version, check out the new version in a
separate source directory. Preserve `$VPSSRV_STATE_DIR` and installed module
configurations under `/etc`, then run the installer with the same `PREFIX`.
It retains the state root's password, port, certificates, runtime data, and
recorded modules. An upgrade does not print the old password again. Do not
delete old data inside `$PREFIX` to prepare an upgrade. If you customized
persistent paths, you **MUST** use the same paths in later installs; moving them requires
manual transfer and verification. Keep separate backups of the old code and
data until the new services have been checked.

## Uninstall

Run as root, from the installer checkout, with the same `PREFIX` and
`SERVICE_NAME` values used at install time (the installer's summary prints
the exact removal command). To remove services and units **while keeping**
the program directory and `$VPSSRV_STATE_DIR` for a later reinstall:

```bash
KEEP_DATA=1 bash deploy/uninstall.sh
```

To remove the installed modules and **delete data in the default state root**
(including the visitor log, console password, saved port, certificates, and
this project's FRPC instance configurations):

```bash
bash deploy/uninstall.sh
```

Both modes remove installed anytls/proxy services and their module
configurations, stop this project's FRPC instances, remove its FRPC service
template and matching binary, and atomically release vps-server entries from
the sibling `PORTS.md` while retaining other projects' entries.
`KEEP_DATA=1` retains `$PREFIX`, `$VPSSRV_STATE_DIR`, FRPC instance configurations such as
`/etc/frp/frpc-*.toml`, and recovery copies, but not anytls/proxy module
configurations. A complete uninstall also deletes project-named FRPC
configurations, aliases, and recovery copies, as well as the default state
root if it has layout marker `1`. Data paths customized outside that root
are not deleted automatically. Without `KEEP_DATA=1`, the project-named
`frpc-*.toml` files are removed. When it finds instances the
console can recognize, it stops them and removes their global FRPC files even
if an older service template differs; confirm ownership first on a shared
FRPC host. If no recognizable instance establishes ownership, global FRPC is
retained with an explanation. A binary checksum mismatch stops cleanup.

## Acknowledgements

The browser test uses [LibreSpeed](https://github.com/librespeed/speedtest);
QR rendering uses [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator);
the bundled proxy core is [sing-box](https://github.com/SagerNet/sing-box).
The optional modules bundle [frp](https://github.com/fatedier/frp) and
[Lucky](https://github.com/gdy666/lucky). See [third-party notices][local-link-003]
for the inventory and original license paths.

## License

Project license: GPL-3.0 (SPDX: `GPL-3.0-only`); read the full [LICENSE][local-link-004]. The historical combination rationale is in [Decisions][local-link-005]. Bundled components, their original licenses, verified artifact sources, and remaining legal-review limits are in [THIRD_PARTY_NOTICES.md][local-link-006].

This project is not affiliated with or endorsed by sing-box/SagerNet or
LibreSpeed.

[local-link-001]: ../CHANGELOG.md
[local-link-002]: DESIGN.md#configuration-reference
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#decisions
[local-link-006]: THIRD_PARTY_NOTICES.md
