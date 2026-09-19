# Decisions

**English** | [简体中文](zh_cn/DECISIONS.md) | [繁體中文](zh_tw/DECISIONS.md) | [繁體中文（香港）](zh_hk/DECISIONS.md) | [हिन्दी](hi/DECISIONS.md) | [Español](es/DECISIONS.md) | [العربية](ar/DECISIONS.md) | [Français](fr/DECISIONS.md)

## Documentation

- Project overview: [README](../README.md)
- Design rationale: [DESIGN](DESIGN.md)
- Release history: [CHANGELOG](CHANGELOG.md)
- Current state: [STATUS](STATUS.md)
- Requirement list: [BACKLOG](BACKLOG.md)
- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

Not a decision log — a guard against re-proposing. One question decides whether
something belongs here:

> In six months, would I or another agent propose this as a fresh idea?

Yes → one entry. No → leave it out; that is not an omission. "We use PostgreSQL"
belongs in DESIGN.md. "MongoDB was evaluated and rejected because X" belongs here.

**Five bullet lines per entry, and under ~1000 bytes of body.** Both limits, not
either: a line cap alone does not bind, because the biggest files measured were
mostly 5-line entries whose every bullet was one unwrapped paragraph. Over the
cap means it is DESIGN.md material — move it there.

The cap is what keeps the file working. At 2 KB per entry nobody opens it before
proposing, and a guard nobody reads guards nothing.

Newest first. Append only. To reverse a decision, add a new entry saying so —
never edit or delete the old one.

---

## 2026-09-19 — Port forwards are iptables DNAT, reapplied from JSON at every start; nothing is written outside the process

- **Rejected:** a per-rule `socat` userspace relay — no NAT table or
  `ip_forward` changes at all, which is safer on a shared host, but the user
  explicitly chose kernel-level DNAT+MASQUERADE for this project instead.
- **Rejected:** `iptables-persistent`/`netfilter-persistent` to survive a
  reboot at the kernel level — that would make the console and a system
  package two separate sources of truth for the same rules, which drift.
  `app.py` reapplies from its own JSON on every start instead (see DESIGN.md,
  "Port forwarding lifecycle"), so there is exactly one.
- **Rejected:** turning `net.ipv4.ip_forward` back to `0` automatically once
  the last forward is disabled or removed — it is a single host-wide toggle,
  and other software already on the box (this project's own test host runs
  Docker, which sets it independently) may depend on it staying on. Turning
  it off is left to the operator.
- **Cost:** stopping `vps-server-web` (not just restarting it) withdraws
  every forward's kernel state, even the enabled ones — the same fail-safe
  direction already chosen for the iperf3 window. Do not "fix" this by moving
  the rules into a separate always-on unit; that was considered and rejected
  above.

---

## 2026-09-12 — The public page and the console are separate listeners with separate handler classes

- **Rejected:** One listener serving both, with console routes gated behind a path prefix plus an auth check — an auth check can be bugged into allowing; a route that does not exist cannot.
- **Rejected:** Putting the console itself on 80/443 behind the password and dropping the random port — that discards the obscurity layer `vps-webserver` deliberately chose.
- **Cost:** Three listeners in one process, and two handler classes that each need the visitor-logging hook wired in separately.
- **Do not re-add this as an improvement.**

---

## 2026-09-12 — iperf3 runs only inside an operator-opened, time-boxed window

- **Rejected:** An always-on public `iperf3 -s` — any stranger can saturate the uplink indefinitely and nothing surfaces that it is happening.
- **Rejected:** Always-on with `--authorized-users-path` RSA authentication — credentials must be handed over out of band before anyone can test, which defeats the point of "give someone the IP and let them measure".
- **Cost:** A remote tester cannot test unattended; someone must open a window first. The public page advertises an open window so the tester knows when to connect.

---

## 2026-09-12 — Port 443 uses a self-signed certificate; no ACME, no domain

- **Rejected:** certbot / acme.sh against a real domain — the page exists to answer "can you reach this IP", and a browser warning page already proves reachability. A domain dependency and a renewal timer buy nothing for that question.
- **Rejected:** Serving only port 80 — that cannot distinguish "the host is unreachable" from "443 specifically is blocked", which is the common case worth detecting.
- **Cost:** Every HTTPS visit shows a certificate warning. Expected; do not "fix" it with HSTS or a pinned exception.

---

## 2026-09-12 — The sing-box binary ships in the repository, so the whole project is GPL-3.0

- **Rejected:** Downloading sing-box at install time to keep the repo small and the licence Apache-2.0 — `Anytsl-Serve` already rejected exactly this to keep installation working without GitHub access; re-deciding it here would silently undo that goal.
- **Rejected:** Dropping the anytls module to preserve `vps-webserver`'s Apache-2.0 — the brief was to combine the two projects, not to pick one.
- **Cost:** ~57 MB in git, growing with every sing-box bump; and `vps-webserver`'s Apache-2.0 code is redistributed here under GPL-3.0.

---

## 2026-09-12 — Upstream projects are vendored, not superseded and not submoduled

- **Rejected:** Letting vps-server replace `vps-webserver` and `Anytsl-Serve` and archiving both — all three are to stay independently maintained and independently released.
- **Rejected:** git submodules pointing at the two upstream repos — a submodule cannot carry the renames this project needs (unit names, binary name, `VPSWS_` → `VPSSRV_`), and a clone would then need network access to two more repos.
- **Cost:** The same code lives in three repositories and will drift. Mitigation: `.upstream-version` files record the exact upstream tag each vendored tree came from, and must be updated in the same commit as any refresh.

<!--
Compaction is the one permitted rewrite, and only once the file has grown past
30 KB or 20 entries. Do it while working on the project anyway, not as its own
errand: entries older than the most recent tag collapse to one line each --

  - YYYY-MM-DD <what was rejected> -- <one-line reason>

-- filed under a `## Compacted history` section at the foot of the file. Never
delete an entry, never change a conclusion, never turn "X was rejected" into
silence. The full text stays recoverable with `git log -p -- DECISIONS.md`, so
commit the compaction on its own as `docs(decisions): compact entries before
vX.Y.Z` rather than mixing it into a feature change.

What does NOT belong here, and where it goes instead:

  what the system is now, which stack, which architecture   DESIGN.md
  what shipped in each version                              CHANGELOG.md
  what to build, and whether it is done                     BACKLOG.md
-->
