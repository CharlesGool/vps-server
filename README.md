# vps-server

**English** | [简体中文](translated_zh_cn/README_zh_cn.md) | [繁體中文](translated_zh_tw/README_zh_tw.md)

A one-command bundle for a Debian/Ubuntu VPS: a public page anyone can hit to
prove your IP's web ports are reachable, a password-protected console for
speed testing and connection logging, an on-demand iperf3 window, and an
anytls proxy.

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
  when the window expires. The tester gets bandwidth from iperf3 and round-trip
  time from `mean_rtt` in its `--json` output; UDP mode adds jitter and loss.
- **Logs who connected.** Every inbound TCP connection, on any port, not just
  HTTP — read from `/proc/net/tcp[6]`, stored in SQLite, most recent 1000 kept.
- **Serves an anytls proxy.** sing-box with a self-signed certificate, plus BBR.
  When that module is installed, the console gains a page showing whether the
  node is up and offering its Clash entry and `anytls://` link with a copy
  button, so handing the node to a client does not mean going back to the
  terminal.

Each of the three modules — web, iperf3, anytls — is selectable at install time.

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
  because the vendored sing-box binary is amd64
- Ports 80 and 443 must be free — the installer refuses rather than competing
  with an existing nginx, Apache, Caddy, or `vps-webserver`
- External services: none. Installation needs only your distro's package mirror.

## Install

```bash
# Always clone a tag, not the default branch — the branch tip may be mid-work.
# Latest release tag: `git ls-remote --tags <repo-url>`
git clone --branch v0.1.0 --depth 1 <repo-url> vps-server
cd vps-server
cp .env.example .env   # optional — every variable has a working default
bash install.sh
```

`install.sh` asks which modules to install, the interface language, whether to
password-protect the console, and which ports to use. It is idempotent: values
already set are kept, so re-running it upgrades in place.

## Quick start

```bash
bash install.sh                              # interactive: modules, language, password, port
sudo VPSSRV_MODULES=web,iperf3 bash install.sh   # unattended, no prompts
systemctl status vps-server-web              # is it up
bash anytls/setup-anytls.sh status           # anytls node details, if that module is installed
```

Then, from a different machine:

```bash
curl -sS  http://<ip>/                     # reachability over plain HTTP
curl -sSk https://<ip>/                    # ... and over TLS (self-signed)
iperf3 -c <ip> -p 5201 --json              # only while a window is open
```

## Verify it works

After `bash install.sh` you should see a summary block naming each installed
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

## Configuration

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
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` | `en` | no |

Full reference: see `DESIGN.md` → Configuration reference.

## Uninstall

```bash
bash uninstall.sh              # removes whichever modules are installed, and the data
KEEP_DATA=1 bash uninstall.sh  # keeps the visitor database and the console password
```

## License

GPL-3.0. This project redistributes the sing-box binary, which is GPL-3.0, so
the combined work is GPL-3.0 — see `LICENSE`. Vendored third-party components,
their versions, and the corresponding-source links the GPL requires are recorded
in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

This project is not affiliated with or endorsed by sing-box/SagerNet or
LibreSpeed.
