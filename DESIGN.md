# vps-server — Design

**English** | [简体中文](translated_zh_cn/DESIGN_zh_cn.md) | [繁體中文](translated_zh_tw/DESIGN_zh_tw.md)

> Success criterion for this document: someone else, on a different machine,
> can rebuild this project from it. Assume the reader cannot see your machine.

## Goals & non-goals

**Goals**

- Install, on a fresh Debian/Ubuntu VPS, a single bundle that provides four
  things, each independently selectable at install time:
  1. **Public reachability page** — a deliberately minimal page served on TCP
     **80 and 443** with no authentication, so that anyone given only the IP can
     confirm in a browser whether this host's web ports are reachable from where
     they are.
  2. **Private console** — a password-protected dashboard on a persisted random
     high port, providing browser-based up/download speed testing and a log of
     recently observed inbound connections.
  3. **On-demand iperf3 window** — a bandwidth/latency test endpoint that is
     **off by default**; an operator opens a time-boxed window from the console,
     and it closes itself when the window expires.
  4. **anytls proxy** — a sing-box `anytls` inbound with a self-signed
     certificate, plus BBR.
- Be installable with no outbound network access beyond the distro package
  mirror. The sing-box binary ships in the repository.
- Coexist on the same host with `vps-webserver` and `Anytsl-Serve` without
  colliding on systemd unit names, install prefixes, environment variable
  prefixes, or persisted ports.

**Non-goals**

- **Not a replacement for `vps-webserver` or `Anytsl-Serve`.** Both remain
  independently maintained and independently released. vps-server vendors their
  code rather than importing or superseding it; see `DECISIONS.md` for the
  drift trade-off this accepts and the mitigation.
- **No ACME / Let's Encrypt / domain names.** TLS on 443 is a self-signed
  certificate. The public page's job is to answer "can you reach this IP at
  all", which a browser warning page already answers. Certificate renewal and
  a domain dependency buy nothing for that job.
- **No always-on iperf3.** An unauthenticated public `iperf3 -s` lets any
  stranger saturate the host's uplink for as long as they like.
- **The public page exposes nothing about the host.** No hostname, no kernel
  version, no uptime, no service inventory, no port list, no anytls parameters.
  It reports only: you reached it, the source IP it saw, the server clock, and
  which of the two ports/protocols you arrived on.
- **No reverse proxy, no nginx, no containers.** The Python process terminates
  TLS itself, as `vps-webserver` already does.
- **No multi-server speedtest selector.** One host, this host.

## Architecture

Two processes plus one transient child. Nothing talks to anything else over the
network; the console and the public page are two listeners inside one Python
process, sharing state in memory.

```
                       ┌──────────────────────── vps-server-web.service ───────┐
  anyone, no auth      │                                                       │
  :80  ──────────────► │  public listener (HTTP)  ──┐                          │
  :443 ──────────────► │  public listener (HTTPS) ──┤                          │
                       │                            ├─► ProbeHandler           │
                       │                            │   (reachability page)    │
                       │                            │                          │
  operator, password   │                            │                          │
  :<random> ─────────► │  console listener  ───────►│   ConsoleHandler         │
                       │                            │   ├─ LibreSpeed endpoints│
                       │                            │   ├─ visitor log         │
                       │                            │   └─ iperf3 window ctl ──┼──┐
                       │                            │                          │  │
                       │  connection poller ◄───────┴── /proc/net/tcp[6]       │  │
                       │  (all ports, not just HTTP)                           │  │
                       └───────────────────────────────────────────────────────┘  │
                                                                                   │
  tester with iperf3      :5201 ◄────────────── iperf3 -s  (child process, ────────┘
  client                                         killed when window expires)

                       ┌─── vps-server-anytls.service ───┐
  proxy client ──────► │  sing-box, anytls inbound, TLS  │
  :<random>            │  self-signed cert               │
                       └─────────────────────────────────┘
```

The two systemd units are independent: either can be installed without the
other, and neither restarts the other.

### Why the public page and the console are separate listeners

They have opposite security postures, and merging them would force one of the
two to give up its own. The console is authenticated and on an unguessable port
precisely so that it is not casually discoverable; the public page must be
trivially discoverable and must not ask for a password. So: different ports,
different request handlers, different route tables. A request arriving on 80/443
can never reach a console route, because `ProbeHandler` has no such routes — not
because a check rejected it. That is the point; an authorization check can be
bugged, an absent route cannot.

The public page accepts `GET` and `HEAD` on exactly two paths (`/` and
`/favicon.ico`) and answers everything else with 404. It reads no query string,
parses no request body, and sets no cookie.

### iperf3 window lifecycle

1. Operator authenticates to the console, picks a duration (default 10 min,
   capped by `VPSSRV_IPERF_MAX_MINUTES`), clicks open.
2. The console spawns `iperf3 -s -p <port>` as a child process, opens the port in
   whichever firewall is active, and records the deadline in memory.
3. While the window is open, the **public page** shows that iperf3 is accepting
   connections, on which port, and how much time is left — the remote tester
   needs to know this, and it is not sensitive: the window is deliberately open.
4. At the deadline (or on operator request, or on service stop) the child is
   terminated and the firewall rule withdrawn.

The window is held in memory, not on disk: if the service dies, the window is
gone, which is the safe direction to fail. A restart never resurrects an open
window.

Latency is read from iperf3's own `--json` output (`mean_rtt` in the TCP info
block) on the tester's side; UDP mode (`-u`) additionally reports jitter and
loss. The server side needs no extra code for this.

## Tech stack

| Layer | Choice | Version | Why |
|---|---|---|---|
| Runtime | Python, standard library only | 3.9+ | Inherited from `vps-webserver`: no third-party packages means no dependency resolution on a fresh VPS and nothing to keep patched |
| HTTP server | `http.server.ThreadingHTTPServer` | stdlib | Three listeners of a few requests each; a framework would be dead weight |
| TLS | `ssl` + `openssl`-generated self-signed cert | stdlib / distro | No domain, no ACME (see non-goals) |
| Store | `sqlite3` | stdlib | Visitor log must survive restarts |
| Speedtest engine | LibreSpeed, vendored unmodified | v6.2.1 | LGPL-3.0; already vendored and working in `vps-webserver` |
| Bandwidth probe | `iperf3` from the distro | distro-pinned | The de-facto tool testers already have on the client side |
| Proxy core | sing-box, vendored binary (amd64) | v1.13.14 | GPL-3.0; shipping the binary keeps install offline-capable |
| Init | systemd | — | Target OS default |
| Installer | Bash | — | Inherited from both upstreams |

Rejected alternatives and the reasoning behind each choice live in
`DECISIONS.md` — do not restate them here.

## Reproduction requirements

### Environment

- OS: Debian 11+ / Ubuntu 20.04+, systemd, run as root
- Runtime: Python 3.9+ (distro python3 is sufficient)
- Architecture: **x86-64 only** for the anytls module — the vendored sing-box
  binary is amd64. The web and iperf3 modules are architecture-independent.
- Hardware: no GPU; ~150 MB disk (of which ~57 MB is the sing-box binary), any
  amount of RAM a VPS normally has
- Dependency restore command: none. There is no Python lockfile because there
  are no Python dependencies; see `THIRD_PARTY_NOTICES.md`.

### External dependencies

| Item | Source | Placed at |
|---|---|---|
| `iperf3` | distro package manager (`apt-get install iperf3`) | system path |
| `openssl`, `curl`, `jq`, `iproute2` | distro package manager | system path |
| sing-box binary | ships in this repository | `/usr/local/bin/sing-box-vps-server` |
| LibreSpeed engine | ships in this repository | `$VPSSRV_PREFIX/static/` |
| TLS certificates | generated on first run by the installer | `$VPSSRV_CERT_DIR` |

No API keys. The service makes no outbound request at runtime except the
optional public-IP lookup during install, which degrades to a warning if it
fails.

### Paths & mounts

| Path | Provided by | Purpose |
|---|---|---|
| `$VPSSRV_PREFIX` | installer, default `/opt/vps-server` | Code, static assets, persisted port files |
| `$VPSSRV_DATA_DIR` | installer, default `$VPSSRV_PREFIX/data` | `visitors.db`, `session_secret.txt` |
| `$VPSSRV_CERT_DIR` | installer, default `$VPSSRV_PREFIX/certs` | Self-signed cert and key for 443 |
| `/etc/vps-server-anytls/` | installer | sing-box `config.json` and its own self-signed cert |

### Configuration reference

All variables use the `VPSSRV_` prefix. This is not cosmetic: `vps-webserver`
owns `VPSWS_` and `Anytsl-Serve` owns `ANYTLS_`, and all three may be installed
on one host, where a shared prefix would let one project's `.env` silently
reconfigure another.

| Variable | Meaning | Default | Required |
|---|---|---|---|
| `VPSSRV_PREFIX` | Install root | `/opt/vps-server` | no |
| `VPSSRV_DATA_DIR` | SQLite + session secret | `$VPSSRV_PREFIX/data` | no |
| `VPSSRV_HOST` | Bind address for all listeners | `0.0.0.0` | no |
| `VPSSRV_PUBLIC_HTTP_PORT` | Public reachability page, plaintext | `80` | no |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Public reachability page, TLS | `443` | no |
| `VPSSRV_PUBLIC_ENABLE` | Serve the public page at all | `1` | no |
| `VPSSRV_CONSOLE_PORT` | Console port; `0` = generate once and persist | `0` | no |
| `VPSSRV_CONSOLE_PORT_FILE` | Where the generated console port is remembered | `$VPSSRV_PREFIX/console_port.txt` | no |
| `VPSSRV_CONSOLE_TLS` | Serve the console over HTTPS | `0` | no |
| `VPSSRV_AUTH` | Require login on the console | `1` | no |
| `VPSSRV_PASSWORD_FILE` | Plaintext console password, editable by the operator | `$VPSSRV_PREFIX/admin_password.txt` | no |
| `VPSSRV_CERT_DIR` | Self-signed cert location | `$VPSSRV_PREFIX/certs` | no |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | Use an operator-supplied cert instead | — | no |
| `VPSSRV_IPERF_PORT` | Port the iperf3 window listens on | `5201` | no |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | Pre-filled window duration | `10` | no |
| `VPSSRV_IPERF_MAX_MINUTES` | Hard cap the console cannot exceed | `60` | no |
| `VPSSRV_IPERF_ENABLE` | Allow opening windows at all | `1` | no |
| `VPSSRV_TRUST_PROXY` | Honour `X-Forwarded-For` when recording visitors | `0` | no |
| `VPSSRV_TRACK_CONNECTIONS` | Poll `/proc/net/tcp[6]` for all-port connection logging | `1` | no |
| `VPSSRV_CONN_POLL_SECONDS` | Poll interval | `5` | no |
| `VPSSRV_MAX_TEST_MB` | Cap on a single speedtest transfer, in MB | `200` | no |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` | `en` | no |
| `ANYTLS_PORT`, `ANYTLS_PASSWORD`, `SNI`, `SERVER_IP` | The anytls module keeps the upstream names | see `.env.example` | no |

The anytls module deliberately keeps `Anytsl-Serve`'s variable names rather than
renaming them to `VPSSRV_ANYTLS_*`: the vendored config generator reads them, and
renaming would mean patching vendored code, which is what the vendoring policy
exists to avoid.

## Setup from scratch

1. `git clone <repo>` and `cd` into it — verify: `ls sing-box` shows a ~57 MB file.
2. `bash install.sh` — the installer asks which modules to install, the UI
   language, whether to password-protect the console, and the ports. Verify:
   it prints a summary block listing each installed module and its port.
3. `systemctl status vps-server-web` — verify: `active (running)`.
4. From another machine, open `http://<ip>/` — verify: the reachability page
   renders and shows your own source IP.
5. From another machine, open `https://<ip>/` and accept the certificate warning
   — verify: the same page, with the protocol line reading HTTPS.
6. Open `http://<ip>:<console port>/`, log in — verify: the dashboard loads and
   shows the iperf3 control with the window closed.
7. Open a 5-minute iperf3 window from the console, then from another machine run
   `iperf3 -c <ip> -p 5201 --json` — verify: throughput is reported and
   `mean_rtt` is present in the output.
8. If the anytls module was installed: `systemctl status vps-server-anytls` —
   verify: `active (running)`; the installer's summary printed a client config
   line.

## Data model / file layout

```
repo/
├── install.sh                 # module-selecting installer (web / anytls / iperf3)
├── uninstall.sh               # removes the modules it finds
├── app.py                     # the web service: console + public listeners
├── static/                    # LibreSpeed engine (vendored) + own UI assets
├── systemd/
│   ├── vps-server-web.service
│   └── vps-server-anytls.service
├── anytls/
│   ├── setup-anytls.sh        # vendored from Anytsl-Serve, renamed units/paths
│   └── .upstream-version      # records: Anytsl-Serve v1.2.0
├── sing-box                   # vendored amd64 binary
├── sing-box.version
├── .upstream-version          # records: vps-webserver v0.4.1
├── tests/
├── LICENSE                    # GPL-3.0
├── LICENSES/                  # upstream licence texts
└── <the six governance docs + two translated_* trees>
```

SQLite schema is inherited unchanged from `vps-webserver`: one `visits` table,
trimmed to the most recent 1000 rows.

## Known limitations & gotchas

- **Binding 80 and 443 requires root and an otherwise-free port.** If nginx,
  Apache, Caddy, or another `vps-webserver` instance already holds either port,
  the installer refuses rather than fighting for it. Check with
  `ss -lntp '( sport = :80 or sport = :443 )'` before installing.
- **The public page is genuinely public.** Anyone who guesses or scans the IP
  sees it, and every such hit lands in the visitor log. That is the feature, but
  it also means the visitor log on a scanned IP fills with internet background
  noise within hours.
- **Unit names differ from upstream on purpose.** `Anytsl-Serve` installs
  `sing-box-anytls.service`; this project installs `vps-server-anytls.service`
  and a separately-named binary, so both can exist. The installer still refuses
  to proceed if the upstream unit is running, because two anytls inbounds on one
  host is almost certainly a mistake rather than an intent.
- **`iperf3` is not version-pinned.** It comes from the distro, so its version
  varies by release. The wire protocol has been stable across the 3.x line, but
  a client much older than the server can fail the version handshake.
- **amd64 only for anytls.** The vendored binary is not multi-arch; on arm64 the
  installer skips the module with an explanation rather than installing a binary
  that cannot execute.
- **Self-signed TLS means a browser warning on 443, every time.** This is
  expected and is not worth "fixing" with an exception or an HSTS header.
- **A restart closes any open iperf3 window.** Intentional; see the lifecycle
  section.
- **The sing-box binary is past GitHub's recommended file size.** At ~55 MB it
  is over the 50 MB soft limit, so every push prints a "Large files detected"
  warning suggesting Git LFS. Pushes still succeed; the hard limit is 100 MB.
  A future sing-box bump could eventually cross that, and the answer then is a
  decision to make deliberately (LFS, or stop shipping the binary), not a
  surprise on release day.
- **Run the scripts with `bash <script>`, not `./<script>`.** The executable
  bit is recorded in the git index, so a fresh clone has it — but a working
  copy on a CIFS/SMB mount does not, and `./install.sh` there fails with
  "Permission denied".
- **Teardown needs the same `PREFIX` and `SERVICE_NAME` the install used.**
  `uninstall.sh` with no environment reads the defaults, finds nothing at
  those paths, and reports success having removed nothing. The installer's
  closing line prints the exact command with the values filled in; use that
  rather than typing it from memory.

## How to extend

- **A new module** (something else the installer can optionally set up): add a
  `<name>/setup-<name>.sh`, a `systemd/vps-server-<name>.service`, a branch in
  `install.sh`'s module menu, and a teardown branch in `uninstall.sh`. Modules
  do not call each other.
- **A new console page**: add a route to `ConsoleHandler`. Do not add routes to
  `ProbeHandler` — its route table being nearly empty is a security property,
  not an oversight.
- **A new language**: extend the `STRINGS` table in `app.py` and the `msg()`
  table in `install.sh`, then add a `translated_<lang>/` tree.
- **Refreshing a vendored upstream**: re-copy from the upstream tag, update the
  matching `.upstream-version` file in the same commit, and note the bump in
  `CHANGELOG.md`. Never hand-edit vendored code in place — a local edit that is
  not reflected upstream makes the next refresh a silent regression.
