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

vps-server provides Web port-reachability pages, speed tests, and a connection-log console for Debian/Ubuntu VPS hosts, with optional proxy, FRP, Lucky, and Tailscale modules. The current formal release is v5.2.2. See [project status](LOG.md) for progress.

## Features

- **Public reachability page:** When enabled, ports 80 and 443 show the visitor IP, server time, connection port, and protocol. Port 443 uses a self-signed certificate. The page requires no login and does not show host configuration.
- **Private console:** On a separate persistent port, LibreSpeed measures upload and download speed and shows the most recent 1000 inbound TCP connections. An administrator password or approved private IP grants access.
- **iperf3:** Open a time-limited window from the console; it closes automatically. A Linux client's `--json` output may include `mean_rtt`. Clients unable to read `TCP_INFO` will not show that field. UDP tests report jitter and packet loss.
- **Proxy nodes:** One sing-box service hosts AnyTLS, VMess, VLESS, Trojan, and Shadowsocks. The console manages node connections, traffic caps, rate limits, periodic resets, and validity periods. Clash Meta configurations can be imported over the LAN.
- **FRP:** The console manages the local FRPS port, token, and service state, as well as local FRPC instances and simple token-authenticated TCP/UDP proxies. It validates edits and restores the previous configuration on failure. It does not monitor clients on other devices. FRPC installs from bundled resources.
- **Lucky:** Install or remove it with other modules. The console shows only its management address and running state, with a link to its native management page. When Lucky changes its own management port, the console periodically refreshes the address and `PORTS.md` registration. Full feature recreation is deferred to a later version.
- **Tailscale:** Install or remove the Linux client included in the offline package. The console shows status, connectivity, devices, and service logs, and saves several Linux settings for DNS, routes, exit nodes, shields-up, and SSH together. Device IPv4 and IPv6 addresses can be shown or copied separately as needed. Joining a Tailnet still requires access to the selected control server.
- **Terminal:** The Home entry opens a browser-based root terminal after administrator-password verification. Disconnecting, leaving the page, or expiration of the login session terminates its PTY process. Terminal rendering resources are included in the offline package.

The first installation enables only the Web console; other modules are installed
as needed. See the [design document](DESIGN.md) for feature boundaries, login
rules, and FRP editor limits.

## Requirements

- OS: Debian 11+ or Ubuntu 20.04+, systemd, run as root.
- Runtime: Python 3.9+ (the distribution's `python3` suffices; no Python dependencies to install).
- Architecture: the entire project supports only x86-64 Linux; the installer rejects other platforms before changing system state.
- When the Web module uses its default public ports, 80 and 443 **MUST** be free. The installer refuses to compete with nginx, Apache, Caddy, or `vps-webserver`.
- Other dependencies: the target needs its OS-provided Bash, systemd, Python, and common base tools. The complete offline package includes FRP, Lucky, Tailscale, sing-box, iperf3, and a private nftables runtime. Node accounting prefers the host nft command if it can read the ruleset, otherwise it uses the bundled version; the target needs neither Git nor a package mirror. Control-server authentication, service updates, and communication between devices still need network access.
- Minimum: the OS, runtime, and architecture above. Public-page ports must be free if enabled. Allow at least 1 GiB of disk space for the full offline package, extracted source, and installed program together.

## Install

### Quick Install

Run as root on the target host. The installer enables only the Web console by default. The first interactive install offers language choices 1/2/3 and prints a random management port and password. Use `VPSSRV_DEFAULT_LANG=en|zh_cn|es` for unattended installation. The source commands below use the formal v5.2.2 tag; use the archive procedure below for complete offline modules.

```bash
git clone --branch v5.2.2 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

From v5.2.2 onward, the source includes the Tailscale 1.102.4 installation archive. Even when the initial installation selects only Web, the console can install Tailscale offline later. The v5.2.0 source tag still lacks this archive; use the complete Release package for that version. The private nftables archive and its corresponding source remain available through the complete offline package.

### Normal Install

```bash
git clone --branch v5.2.2 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env  # Optional: set overrides described in the file
bash deploy/install.sh
```

`PREFIX` defaults to `/root/apps/vps-server` and holds
replaceable program files. Passwords, the console port, certificates, runtime
data, installation records, and `.env` default to `/var/lib/vps-server`. Set
`VPSSRV_STATE_DIR` in the command environment before the first install to use
another external directory. There is no browser-based first-run wizard. Set
`VPSSRV_MODULES=web,iperf3,proxy,frps,lucky,tailscale` to select server modules;
when omitted, only Web is installed. Install or remove optional modules from
Settings → Modules. AnyTLS is a protocol within `proxy`, with no separate
module or service. Enable public HTTP and HTTPS pages separately from Home;
the console uses a separate port. Install FRPC separately when a local client
is needed.

### Offline installation package

The v5.2.2 offline package contains the full source and verified offline resources, including Tailscale and nftables. Target installation does not require Git. Verify SHA-256 before extracting into a separate directory; do not overwrite the installed `$PREFIX` directly. Download `vps-server-v5.2.2-linux-amd64.tar.gz` and `SHA256SUMS` from GitHub Release, verify the digest, and install:

```bash
mkdir -p /root/vps-server-v5.2.2
tar -xzf /root/vps-server-v5.2.2-linux-amd64.tar.gz -C /root/vps-server-v5.2.2 --strip-components=1
cd /root/vps-server-v5.2.2
bash deploy/install.sh
```

A connected build host can create the formal offline package from a **clean, committed** worktree; the target receives only the final `.tar.gz`. The build host requires Python 3, Git, `dpkg-deb`, and GNU tar. The asset-fetch script checks fixed digests. The package includes the nftables runtime, its corresponding source, and the Tailscale archive:

```bash
python3 tools/build_offline/fetch_assets.py --output-dir .local/offline-assets
python3 tools/build_offline/build_offline.py \
  --tailscale-archive .local/offline-assets/tailscale_1.102.4_amd64.tgz \
  --nft-runtime .local/offline-assets/nft-runtime-bullseye.tar.gz \
  --nft-sources .local/offline-assets/nft-sources-bullseye.tar.gz \
  --version 5.2.2 \
  --output .local/vps-server-v5.2.2-linux-amd64.tar.gz
```

## Guidance

The installation summary shows the console address, administrator password,
and installed modules. Public pages are off by default. After enabling them
from Home, visit `http://<ip>/` and `https://<ip>/` from another machine to
check ports 80 and 443. HTTPS uses a self-signed certificate. Check the service
with `systemctl status vps-server-web`, then sign in to manage modules, proxy
nodes, and FRP.

For iperf3, open a time-limited window in the console, then run
`iperf3 -c <ip> -p 5201 --json` from another machine. The port stops listening
when the window closes. The source has no automated test suite; manually
accept the enabled modules. See the [design document](DESIGN.md) for service
paths, limitations, and state files.

Proxy-node traffic caps count (upload + download) × 2. The interface shows counted usage; incomplete accounting alone does not trigger early throttling. Monthly resets start on day 1 of the selected month at 00:00 UTC; daily and yearly cycles retain their existing calculation. Node interface addresses are masked by default and can be shown or copied as needed. Recent Visitors can clear history after confirmation; later visits and still-connected devices are recorded again. Settings directly shows module installation cards; progress collapses 30 seconds after the last output, and completion notices appear briefly only on the current operation page. Reloading or returning does not reproduce them. Detailed Logs, to the right of Changelog in the header, combines module operation history and service logs, with severity filtering for service logs. Clearing module history truncates its file; clearing one service log only hides earlier entries and does not delete the host journal. Lucky retains its native management page; use SSH port forwarding if the current network cannot reach it directly.

### Configuration

Every variable has a working default. A first install can import `.env` from
the source directory; afterward it is stored as `.env` in the state root. Key
variables:

| Variable | Meaning | Default | Required |
|---|---|---|---|
| `VPSSRV_STATE_DIR` | Persistent state root, set in the command environment before first install; `.env` cannot move it | `/var/lib/vps-server` | no |
| `VPSSRV_PUBLIC_HTTP_PORT` | Public reachability page, plaintext | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Public reachability page, TLS | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Whether to serve public pages at first install; Home controls HTTP and HTTPS separately afterward | `0` | no |
| `VPSSRV_CONSOLE_PORT` | Console port; `0` generates and remembers it | `0` | no |
| `VPSSRV_AUTH` | Require a password on the console | `1` | no |
| `VPSSRV_IPERF_PORT` | Port an open iperf3 window listens on | `5201` | no |
| `VPSSRV_IPERF_MAX_MINUTES` | Maximum duration allowed by the console | `60` | no |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `es` | `en` | no |

Full reference: [Configuration reference][local-link-002].

## Upgrade

v5.2.0 establishes persistent state layout `1`. **Automatic migration is not supported** from v5.1.0 or earlier. Back
up remaining old data outside the installation directory, then perform a fresh
installation. Deleted data without a backup cannot be recovered. If the
installer finds an old service but missing state, it stops before changing
services.

For later upgrades from layout `1`, check out new source in a separate
directory and run the installer with the same `PREFIX` and `VPSSRV_STATE_DIR`.
Preserve the state root and module configurations under `/etc`; the installer
retains the password, port, certificates, runtime data, and recorded modules
without printing the old password again. Keep code and data backups, then
check service state, console port, login, and enabled modules after upgrading.
Use the same customized state paths on later installations; moving them
requires manual transfer and verification.

## Uninstall

Run as root from the installation source directory with the same `PREFIX` and
`SERVICE_NAME` used at installation (the exact command is in the install
summary):

```bash
KEEP_DATA=1 bash deploy/uninstall.sh  # Stop services; keep program and persistent state
bash deploy/uninstall.sh              # Complete uninstall; delete default state root
```

Both modes stop project-managed services and release port registrations.
Retained-data mode keeps the program, state root, unified proxy configuration,
FRPS configuration, FRPC instance configurations, Lucky native settings and tasks, and Tailscale device identity.
A complete uninstall removes these project-named configurations and recovery
copies, including native settings, DDNS and reverse-proxy tasks in `/etc/vps-server-lucky`, and the Tailscale login identity in the state root. Confirm instance ownership first on a host with shared FRPC. Data paths
customized outside the state root are not deleted automatically. See the
[design document](DESIGN.md#complete-uninstall) for the full cleanup scope.

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
