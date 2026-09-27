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
on-demand iperf3 window, and sing-box proxy nodes. Version 2.0.0 also includes
the four-protocol `proxy` module and experimental frps and Lucky installers.
See [current state and acceptance limits][local-link-001].

## What it does

- **Proves reachability to anyone.** A deliberately minimal page on ports **80**
  and **443**, no login. Hand someone the IP; if the page renders, your web
  ports are reachable from where they are. It reports their source IP, the
  server clock, and which port and protocol they arrived on — and nothing else
  about the host.
- **Measures throughput from a browser.** A password-protected console on a
  persisted random high port runs up/download tests using the LibreSpeed engine.
- **Measures throughput and latency with iperf3, on demand.** The console opens
  a time-boxed window; `iperf3 -s` runs only inside it and shuts itself down
  when the window expires. The tester gets bandwidth from iperf3, and on a
  Linux client also round-trip time from `mean_rtt` in its `--json` output —
  that field comes from the kernel's `TCP_INFO` and is absent on clients that
  cannot read it, notably iperf3 under Cygwin on Windows. UDP mode (`-u`) adds
  jitter and loss on every platform.
- **Logs who connected.** Every inbound TCP connection, on any port, not just
  HTTP — read from `/proc/net/tcp[6]`, stored in SQLite, most recent 1000 kept.
- **Serves an anytls proxy.** sing-box with a self-signed certificate, plus BBR.
  The authenticated `/proxy` page shows the node status, traffic, editable
  connection settings, and a one-tap Clash Meta for Android import link with QR
  code when a private LAN address is available.
- **Serves vmess/vless/trojan/shadowsocks proxies, any subset.** One more
  sing-box process shares the vendored binary with anytls. Each installed
  protocol has its own numbered node, traffic cap in GiB, edit and random-reset
  controls, and the same LAN-only Clash Meta import option. The import URL
  contains an opaque token and changes after the node's connection settings
  or name changes. The public ports do not serve proxy configurations.

The selectable modules are web, iperf3, anytls, proxy, frps, and Lucky. frps
and Lucky remain experimental; their behavior has not been accepted on a real
host for this version.

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
- External services: none at runtime. Installation needs your distro's package mirror; optional public-IP lookup may contact an external service.
- Minimum: the OS, runtime, architecture, and free ports above. No additional recommended hardware requirement is recorded; a VPS with roughly 150 MB disk accommodates the vendored binary.

## Install

One-line quick install (latest release tag, no configuration variables):

```bash
git clone --branch v2.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

Step by step, with configuration:

```bash
# Clone a release tag; the default branch can contain unpublished changes.
# List release tags: `git ls-remote --tags https://github.com/CharlesGool/vps-server.git`
git clone --branch v2.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # optional — every variable has a working default
bash deploy/install.sh
```

`deploy/install.sh` asks which modules to install, the interface language,
whether to password-protect the console, and which ports to use. The v2.0.0
tag includes all six selectable modules; frps and Lucky are experimental.

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
