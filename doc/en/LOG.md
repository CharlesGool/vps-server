---
name: project-log-en
description: Current project status, decisions, and handoff
metadata:
  version: "1.0.0"
  lang: "en"
---

# Log

## Multi-language

[简体中文](../LOG.md) | **English** | [繁體中文 (台灣)](../zh-TW/LOG.md) | [繁體中文 (香港)](../zh-HK/LOG.md) | [हिन्दी](../hi/LOG.md) | [Español](../es/LOG.md) | [العربية](../ar/LOG.md) | [Français](../fr/LOG.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)
- Commit history: [COMMITS](COMMITS.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)


## Records

- [Historical records](HISTORY.md)
- [Version changelog](CHANGELOG.md)
- [Commit history](COMMITS.md)

## Bugs

- [ ] 2026-09-12 Decide whether the shared `_db_lock` needs decoupling — every public-page hit takes a process-wide lock and does a synchronous SQLite write, and the console shares that lock, so in principle anonymous flooding can slow an authenticated page. **Measured and not reproduced**: 60 concurrent flooders left console latency at 0.4–0.6 ms, identical to idle. Recorded so the mechanism is not rediscovered as new; do not rearchitect without a measurement that shows harm

No other breaking issue is recorded in the prior status snapshot; the startup/shutdown signal edges, iperf3-only installer combination, and login rate limiting were fixed on `feat/hardening-batch`, which still requires merge/review. This is not a claim that the current branch was revalidated on a real host.

## Limitations

- Automated checks verify catalog keys, placeholders, and document structure, but the new translations have not had independent native-language review.
- Before migration, the Simplified Chinese originals and older translations of the four core documents were scattered across different paths, so a complete baseline from a single synchronization cannot be restored. This migration resynchronized all seven languages against the current Simplified Chinese source. The next update can use this commit as the incremental translation baseline. English-only test records from before migration remain in the historical archive; its boundary is described in [HISTORY](HISTORY.md).
- During standardization on 2026-10-03, ignored runtime state and caches at the source checkout root were moved intact to `private/local-runtime-prestandardization-20261003/`. The current worktree passes the structure check. On a CIFS working copy mounted with fixed 0644 file and 0755 directory modes, `chmod` does not change the displayed modes of local secrets; the mount's access control requires separate assessment.
- The current branch's real-host acceptance limits are recorded in the Simplified Chinese handoff below.

## Decisions

<a id="vps-decisions"></a>

The dated decisions below preserve both rejected alternatives and their costs. A historical decision is not a new legal or release approval.

| Decisions | Reasons, rejected alternatives, and costs |
| --- | --- |
| 2026-09-22 — `proxy` is one sing-box process with up to four inbounds, not four clones of anytls | - **Resolved, not rejected:** whether the vendored sing-box binary covers   vmess/vless/trojan/shadowsocks — confirmed by actually running all four   simultaneously in one process (not just `sing-box check`); no second   backend needed. hysteria2/tuic tried and left out (different field/TLS   requirements). - **Rejected:** one systemd unit + config per protocol, mirroring anytls's   own shape exactly — four units to monitor, three redundant self-signed   certs, and it fights the shape a future per-node traffic-accounting   feature would want (one process whose `inbounds` list is already the node   list). - **Cost:** the shared vendored binary is now used by two independent   modules; each module's `uninstall()` **MUST** check the other's config exists   before deleting it (anytls's vendored script gained this as a documented   local deviation — see `anytls/.upstream-version`). |
| 2026-09-21 — `prompt_new_settings()` ends with an explicit `return 0`, not just falling off the loop | - **Rejected:** letting the function's exit status fall out of its final `for`   loop, as most other functions in `install.sh` do — the loop's last   statement used to be a bare `[ -n "$value" ] && export ...`, so leaving the   *last* prompted setting at its default made that test false, which became   the function's own return status. Called bare (`prompt_new_settings` inside   an `if`-body, not itself exempt from `set -e`) that silently killed the   whole installer right after the last prompt — no error, no file copy, no   `VERSION` stamp, no service restart. Reproduced live on v1.0.4 → v1.1.1 and   fixed by wrapping the export in `if`/`fi` and adding an explicit trailing   `return 0`, so the function's exit status no longer depends on which   setting happened to be prompted last. - **Do not remove the trailing `return 0` as apparent dead code.** It is the   fix, not boilerplate. |
| 2026-09-19 — Port forwards are iptables DNAT, reapplied from JSON at every start; nothing written outside the process | - **Rejected:** a per-rule `socat` userspace relay — safer (no NAT table or   `ip_forward` changes), but the user explicitly chose kernel-level   DNAT+MASQUERADE for this project instead. - **Rejected:** `iptables-persistent` to survive a reboot at the kernel level   — that makes the console and a system package two sources of truth for the   same rules. `app.py` reapplies from its own JSON on every start instead   (DESIGN.md, "Port forwarding lifecycle"), so there is exactly one. - **Rejected:** auto-reverting `net.ipv4.ip_forward` to `0` once the last   forward is removed — it is host-wide, and other software (this project's   own test host runs Docker) may depend on it staying on. - **Cost:** stopping `vps-server-web` (not restarting it) withdraws every   forward's kernel state, even enabled ones — same fail-safe direction as the   iperf3 window. Do not move the rules into a separate always-on unit to   "fix" this; that was considered and rejected above. |
| 2026-09-12 — The public page and the console are separate listeners with separate handler classes | - **Rejected:** One listener serving both, with console routes gated behind a path prefix plus an auth check — an auth check can be bugged into allowing; a route that does not exist cannot. - **Rejected:** Putting the console itself on 80/443 behind the password and dropping the random port — that discards the obscurity layer `vps-webserver` deliberately chose. - **Cost:** Three listeners in one process, and two handler classes that each need the visitor-logging hook wired in separately. - **Do not re-add this as an improvement.** |
| 2026-09-12 — iperf3 runs only inside an operator-opened, time-boxed window | - **Rejected:** An always-on public `iperf3 -s` — any stranger can saturate the uplink indefinitely and nothing surfaces that it is happening. - **Rejected:** Always-on with `--authorized-users-path` RSA authentication — credentials would have to be handed over out of band before anyone can test, which defeats the point of "give someone the IP and let them measure". - **Cost:** A remote tester cannot test unattended; someone has to open a window first. The public page advertises an open window so the tester knows when to connect. |
| 2026-09-12 — Port 443 uses a self-signed certificate; no ACME, no domain | - **Rejected:** certbot / acme.sh against a real domain — the page exists to answer "can you reach this IP", and a browser warning page already proves reachability. A domain dependency and a renewal timer buy nothing for that question. - **Rejected:** Serving only port 80 — that cannot distinguish "the host is unreachable" from "443 specifically is blocked", which is the common case worth detecting. - **Cost:** Every HTTPS visit shows a certificate warning. Expected; do not "fix" it with HSTS or a pinned exception. |
| 2026-09-12 — The sing-box binary ships in the repository, so the whole project is GPL-3.0 | - **Rejected:** Downloading sing-box at install time to keep the repo small and the licence Apache-2.0 — `Anytsl-Serve` already rejected exactly this to keep installation working without GitHub access; re-deciding it here would silently undo that goal. - **Rejected:** Dropping the anytls module to preserve `vps-webserver`'s Apache-2.0 — the brief was to combine the two projects, not to pick one. - **Cost:** ~57 MB in git, growing with every sing-box bump; and `vps-webserver`'s Apache-2.0 code is redistributed here under GPL-3.0. |
| 2026-09-12 — Upstream projects are vendored, not superseded and not submoduled | - **Rejected:** Letting vps-server replace `vps-webserver` and `Anytsl-Serve` and archiving both — all three are to stay independently maintained and independently released. - **Rejected:** git submodules pointing at the two upstream repos — a submodule cannot carry the renames this project needs (unit names, binary name, `VPSWS_` → `VPSSRV_`), and a clone would then need network access to two more repos. - **Cost:** The same code lives in three repositories and will drift. Mitigation: `.upstream-version` files record the exact upstream tag each vendored tree came from, and **MUST** be updated in the same commit as any refresh. |

## Handoff

The current handoff, including completed checks, remaining release steps, blockers, and the next action, is maintained in the [Simplified Chinese LOG.md](../LOG.md#交接).
