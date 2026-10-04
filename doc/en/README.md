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

vps-server provides a Web-port reachability page and a console for speed tests
and connection logs on Debian/Ubuntu VPS hosts. Proxy, FRP, Lucky, and
Tailscale modules can be installed as needed. This branch is preparing a
v6.0.0 test candidate; v5.1.0 remains the latest formal release. See
[project status](LOG.md) for progress.

## Features

- **Public reachability page:** When enabled, ports 80 and 443 show the visitor IP, server time, connection port, and protocol. Port 443 uses a self-signed certificate. The page requires no login and does not show host configuration.
- **Private console:** On a separate persistent port, LibreSpeed measures upload and download speed and shows the most recent 1000 inbound TCP connections. An administrator password or approved private IP grants access.
- **iperf3:** Open a time-limited window from the console; it closes automatically. A Linux client's `--json` output may include `mean_rtt`. Clients unable to read `TCP_INFO` will not show that field. UDP tests report jitter and packet loss.
- **Proxy nodes:** One sing-box service hosts AnyTLS, VMess, VLESS, Trojan, and Shadowsocks. The console manages node connections, traffic caps, rate limits, periodic resets, and validity periods. Clash Meta configurations can be imported over the LAN.
- **FRP:** The console manages the local FRPS port, token, and service state, as well as local FRPC instances and simple token-authenticated TCP/UDP proxies. It validates edits and restores the previous configuration on failure. It does not monitor clients on other devices. FRPC installs from bundled resources.
- **Lucky:** Install or remove it with other modules and open Lucky's native management page from the console. This project does not recreate its DDNS or reverse-proxy features.
- **Tailscale:** Install or remove the Linux client included in the offline package. The console shows status, connectivity, devices, and service logs, with Linux settings for DNS, subnet routes, exit nodes, shields-up, and SSH. Joining a Tailnet still requires access to the selected control server.

The first installation enables only the Web console; other modules are installed
as needed. See the [design document](DESIGN.md) for feature boundaries, login
rules, and FRP editor limits.

## Requirements

- OS: Debian 11+ or Ubuntu 20.04+, systemd, run as root.
- Runtime: Python 3.9+ (the distribution's `python3` suffices; no Python dependencies to install).
- Architecture: the entire project supports only x86-64 Linux; the installer rejects other platforms before changing system state.
- When the Web module uses its default public ports, 80 and 443 **MUST** be free. The installer refuses to compete with nginx, Apache, Caddy, or `vps-webserver`.
- Other dependencies: the target needs its OS-provided Bash, systemd, Python, and common base tools. The complete offline package includes FRP, Lucky, Tailscale, sing-box, iperf3, and a private nftables runtime; the target needs neither Git nor a package mirror. Control-server authentication, service updates, and communication between devices still need network access.
- Minimum: the OS, runtime, and architecture above. Public-page ports must be free if enabled. Allow at least 1 GiB of disk space for the full offline package, extracted source, and installed program together.

## Install

### Quick Install

Run as root on the target host. The installer enables only the Web console by
default. The first interactive install presents language choices 1/2/3, then
prints the generated management port and password. Unattended installation
can select a language with `VPSSRV_DEFAULT_LANG=en|zh_cn|es`. Formal v6.0.0
has not been released. The source commands below are for this test branch;
use the archive procedure below for the complete offline modules.

```bash
git clone --branch release/v6.0.0-test.1 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

### Normal Install

```bash
git clone --branch release/v6.0.0-test.1 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
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

The v6.0.0 test package will contain the full source and checked offline
resources, including Tailscale and nftables. Building the package and
installing it on the target do not require Git on that target. Once the test
package is available, check its supplied SHA-256 and extract it into a
separate directory; do not overwrite the installed `$PREFIX` directly. The
test package has not yet been published. Replace `<测试包>` below with
the actual filename:

```bash
mkdir -p /root/vps-server-v6-test
tar -xzf /root/<测试包>.tar.gz -C /root/vps-server-v6-test --strip-components=1
cd /root/vps-server-v6-test
bash deploy/install.sh
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

A proxy node's traffic cap counts (upload + download) × 2. The console shows
the counted amount; an accounting gap alone does not trigger early throttling.
Monthly resets occur at 00:00 UTC on the first day of the selected month;
daily and yearly cycles retain their existing calculations. Node interface
addresses are masked by default and can be shown or copied. Recent Visitors
can clear history after confirmation; later visits and devices still connected
are recorded again. Module install/removal progress collapses 30 seconds after
its last output. A completion notice appears briefly only on the page that
started the operation and does not reappear after reload or return. Detailed
Logs, to the right of Changelog in the top bar, shows module-operation history
and service logs; retention depends on the host's systemd journal. Lucky uses
its own management page. If the current network cannot reach it directly, the
operator can forward its management port over SSH.

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

The v6.0.0 candidate establishes persistent state layout `1`. **Automatic migration is not supported** from v5.1.0 or earlier. Back
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
FRPS configuration, FRPC instance configurations, and Tailscale device identity.
A complete uninstall removes these project-named configurations and recovery
copies. Confirm instance ownership first on a host with shared FRPC. Data paths
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
