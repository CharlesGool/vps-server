# vps-server

[简体中文](../../README.md) | **English** | [Español](../es/README.md)

Manage VPS speed tests, proxies, FRP and Tailscale from one Web console.

[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue)](../../LICENSE) [![Release](https://img.shields.io/badge/release-v5.2.2-blue)](https://github.com/CharlesGool/vps-server/releases/tag/v5.2.2)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Introduction

- Browser upload/download tests, visitor records, timed iperf3 server windows and client tests.
- Managed Singbox nodes for AnyTLS, VMess, VLESS, Trojan and Shadowsocks, with sharing, quotas, rate limits and expiry.
- FRPS server, FRPC instances and TCP/UDP proxies, a native Lucky management entry, and Tailscale status and devices.
- Optional modules, port forwarding, detailed logs, a password-protected browser root terminal, three languages and themes.
- Fresh installs include only Web; public reachability pages are disabled. See [LOG](LOG.md#bugs) for issues and verification boundaries.

## Requirements

Minimum: x86-64 Linux, systemd, root access, Python 3.9+, Bash and writable installation/state directories. The installer targets Debian 11+ and Ubuntu 20.04+; other architectures are unsupported.

Use a maintained Debian/Ubuntu release, reserve backup space and allow ports for enabled features. Debian 13 x86-64 was tested on a host; Python 3.9 and other distributions have not been independently accepted. Complete Release packages contain offline artifacts, but missing base OS packages still require a working package repository. Building the complete offline package from source requires network access.

## Install

Run as root.

### Quick Install

Install Web, iperf3, Singbox, FRPS, Lucky and Tailscale with one command. Add the FRPC client from Settings/Modules.

```bash
curl -fL https://github.com/CharlesGool/vps-server/releases/download/v5.2.2/vps-server-v5.2.2-linux-amd64.tar.gz | tar -xz -C /root && VPSSRV_MODULES=web,iperf3,proxy,frps,lucky,tailscale bash /root/vps-server/deploy/install.sh
```

### Normal Install

Source installs include the Tailscale archive; the private nftables runtime is supplied only in the complete offline package. Copying `.env` is optional; edit it before installing when customization is needed.

```bash
git clone --depth 1 --branch v5.2.2 https://github.com/CharlesGool/vps-server.git /root/vps-server-source
cd /root/vps-server-source
cp .env.example .env
bash deploy/install.sh
```

#### Offline Install

Download the [complete package](https://github.com/CharlesGool/vps-server/releases/download/v5.2.2/vps-server-v5.2.2-linux-amd64.tar.gz) and [SHA256SUMS](https://github.com/CharlesGool/vps-server/releases/download/v5.2.2/SHA256SUMS) on a networked machine, transfer them to `/root/vps-server-download/` on the target and run the commands below. The target must already have the base OS dependencies listed above.

```bash
cd /root/vps-server-download
sha256sum -c SHA256SUMS
mkdir -p /root/vps-server-v5.2.2
tar -xzf vps-server-v5.2.2-linux-amd64.tar.gz -C /root/vps-server-v5.2.2 --strip-components=1
cd /root/vps-server-v5.2.2
VPSSRV_MODULES=web,iperf3,proxy,frps,lucky,tailscale bash deploy/install.sh
```

After language selection, systemd runs the installation in the background. You **MUST** keep the source directory until completion. For the default prefix, inspect the log and result:

```bash
tail -f /root/apps/vps-server/.local/install-job/install.log
cat /root/apps/vps-server/.local/install-job/exit-code
```

A missing `exit-code` means the job has not finished; `0` means success and any other value failure. Adjust the path for a custom `PREFIX`. On completion, the log contains console addresses, initial password and module results. Terminal disconnection does not mean installation failure.

## Usage

Log in using the address and password in the installation log. Install components in Settings/Modules, then manage nodes, FRPC instances or timed tests. Addresses and credentials are hidden by default; editors load existing values. The browser root terminal and security settings require admin password verification. Connect and authenticate Tailscale before use; advertised subnet routes still require Tailnet approval.

Configuration template: [.env.example](../../.env.example). All variables have defaults; credentials need not be supplied. Use absolute paths, `0/1` switches, ports `1-65535` (console `0` is an exception), and integer counts/durations. Except for `PREFIX` and the initial `VPSSRV_STATE_DIR`, these settings are stored in the state-root `.env`; restart Web after changes. Initial module values apply when installing the module.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `PREFIX` | `/root/apps/vps-server` | Code prefix, passed to the installer/uninstaller environment; setting it in `.env` has no effect. |
| `VPSSRV_STATE_DIR` | `/var/lib/vps-server` | State root environment parameter for first install; editing `.env` does not migrate data. |
| `VPSSRV_DATA_DIR` | empty | Data directory; empty uses `data/` under the state root. |
| `VPSSRV_CERT_DIR` | empty | Certificate directory; empty uses `certs/` under the state root. |
| `VPSSRV_PUBLIC_ENABLE` | `0` | Public reachability pages; 1 enables them. |
| `VPSSRV_PUBLIC_HTTP_PORT` | `80` | Public HTTP port. |
| `VPSSRV_PUBLIC_HTTPS_PORT` | `443` | Public HTTPS port. |
| `VPSSRV_HOST` | `0.0.0.0` | Web bind address. |
| `VPSSRV_CONSOLE_PORT` | `0` | Console port; 0 selects and persists a port in 20000-59999. |
| `VPSSRV_CONSOLE_PORT_FILE` | empty | Port file; empty uses `console_port.txt` under the state root. |
| `VPSSRV_CONSOLE_TLS` | `0` | Console TLS switch. |
| `VPSSRV_AUTH` | `1` | Console authentication; 0 permits unauthenticated management access. |
| `VPSSRV_PASSWORD_FILE` | empty | Admin password file; empty uses `admin_password.txt` under the state root. |
| `VPSSRV_IP_ALLOWLIST_FILE` | empty | Passwordless IP allowlist file; empty uses the default state-root list. |
| `VPSSRV_LOGIN_MAX_ATTEMPTS` | `5` | Maximum failed attempts per login window. |
| `VPSSRV_LOGIN_WINDOW_SECONDS` | `60` | Failed-login tracking window in seconds. |
| `VPSSRV_LOGIN_LOCKOUT_SECONDS` | `30` | Lockout duration after the limit, in seconds. |
| `VPSSRV_TLS_CERT` | empty | Custom TLS certificate path; supply together with its key. |
| `VPSSRV_TLS_KEY` | empty | Custom TLS key path; an unspecified pair uses a generated self-signed certificate. |
| `VPSSRV_IPERF_ENABLE` | `1` | iperf3 feature switch. |
| `VPSSRV_IPERF_PORT` | `5201` | Timed server port. |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | `10` | Default server window duration in minutes. |
| `VPSSRV_IPERF_MAX_MINUTES` | `60` | Maximum server window duration in minutes. |
| `VPSSRV_PORTFWD_ENABLE` | `1` | Port-forwarding feature switch. |
| `VPSSRV_PORTFWD_MAX_RULES` | `20` | Maximum configured forwarding rules. |
| `VPSSRV_TRACK_CONNECTIONS` | `1` | Collect kernel TCP connection records. |
| `VPSSRV_CONN_POLL_SECONDS` | `5` | Connection polling interval in seconds. |
| `VPSSRV_TRUST_PROXY` | `0` | Trust proxy address headers; only for a controlled reverse proxy, and disables passwordless IP login. |
| `VPSSRV_MAX_TEST_MB` | `200` | Single browser test transfer ceiling in MB. |
| `VPSSRV_TEST_SECONDS` | `10` | Speed-test measurement duration in seconds. |
| `VPSSRV_WARMUP_SECONDS` | `2` | Warmup seconds excluded from results. |
| `VPSSRV_DOWNLOAD_STREAMS` | `6` | Parallel download streams. |
| `VPSSRV_UPLOAD_STREAMS` | `3` | Parallel upload streams. |
| `VPSSRV_PING_SAMPLES` | `20` | Latency sample count. |
| `VPSSRV_DEFAULT_LANG` | `en` | Default language: `en`, `zh_cn`, `es`. |
| `VPSSRV_PROXY_CONFIG` | `/etc/vps-server-proxy/config.json` | Unified proxy configuration path. |
| `VPSSRV_PROXY_SERVICE` | `vps-server-proxy.service` | Unified proxy service name. |
| `PROXY_PROTOCOLS` | empty | Comma-separated protocol subset; empty installs all five protocols. |
| `PROXY_SNI` | `www.bing.com` | Initial TLS SNI for VMess, VLESS and Trojan. |
| `PROXY_ANYTLS_PORT` | empty | Initial protocol port; empty selects one automatically. |
| `PROXY_ANYTLS_PASSWORD` | empty | Initial protocol credential; empty generates one. |
| `PROXY_VMESS_PORT` | empty | Initial protocol port; empty selects one automatically. |
| `PROXY_VMESS_UUID` | empty | Initial protocol credential; empty generates one. |
| `PROXY_VLESS_PORT` | empty | Initial protocol port; empty selects one automatically. |
| `PROXY_VLESS_UUID` | empty | Initial protocol credential; empty generates one. |
| `PROXY_TROJAN_PORT` | empty | Initial protocol port; empty selects one automatically. |
| `PROXY_TROJAN_PASSWORD` | empty | Initial protocol credential; empty generates one. |
| `PROXY_SS_PORT` | empty | Initial protocol port; empty selects one automatically. |
| `PROXY_SS_PASSWORD` | empty | Initial protocol credential; empty generates one. |

The installer also accepts environment arguments `VPSSRV_MODULES` (comma-separated `web,iperf3,proxy,frps,lucky,tailscale`; fresh default `web`, existing modules retained on reinstall) and `SERVICE_NAME` (default `vps-server-web`). Uninstall argument `KEEP_DATA=1` preserves data. These are not Web settings.

## Upgrade

Layout-1 v5.1.1 test builds, v5.2.0 and v5.2.1 can be upgraded using the installation steps above. Back up the state root, `/etc/vps-server-proxy`, `/etc/vps-server-frps`, FRPC instance configuration and native Lucky configuration. Extract outside the installed prefix and install with the same `PREFIX` and state root. Passwords, ports, certificates, sessions and module settings are retained within this layout; source directories no longer store persistent data.

v5.1.0 and earlier use the old layout and have no automatic migration. You **MUST** back up the old prefix and module configuration, then install fresh and manually restore required settings. A missing state locator or detected old layout blocks in-place upgrade; do not delete the old directory first.

Check background exit code `0`, `systemctl is-active vps-server-web` returning `active`, console version v5.2.2, login with the original password, retained node/FRPC configuration, and required modules and ports. Adjust the service name if customized. Preserve logs and backups on failure; partial completion is not success.

## Uninstall

The first command block removes services while retaining program files, configuration and data; the second performs complete removal. Pass the same custom `PREFIX`, or run from a retained source directory.

```bash
cd /root/apps/vps-server/installer-source
KEEP_DATA=1 bash deploy/uninstall.sh
```

```bash
cd /root/apps/vps-server/installer-source
bash deploy/uninstall.sh
```

Both stop managed services and release project ports. Complete removal also deletes the default state root, project FRPS/unified-proxy/FRPC configuration, Lucky settings/tasks and Tailscale identity. Custom data paths outside the state root are not automatically removed. Check instance ownership on hosts sharing FRPC. Firewall cleanup failure stops complete removal and preserves ownership records.

## Acknowledgements

This project uses or draws on: [LibreSpeed](https://github.com/librespeed/speedtest), [sing-box](https://github.com/SagerNet/sing-box), [frp](https://github.com/fatedier/frp), [Lucky](https://github.com/gdy666/lucky), [Tailscale](https://github.com/tailscale/tailscale), [iperf3](https://github.com/esnet/iperf), [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator), [xterm.js](https://github.com/xtermjs/xterm.js), [Fontsource](https://github.com/fontsource/font-files), [Lucide](https://github.com/lucide-icons/lucide).

See [Third-Party Notices](THIRD_PARTY_NOTICES.md) for original attribution and terms.

## License

GNU General Public License v3.0, SPDX: `GPL-3.0-only`. Full text: [LICENSE](../../LICENSE). Third-party components retain their original licenses. This project is not affiliated with or endorsed by sing-box/SagerNet or LibreSpeed.
