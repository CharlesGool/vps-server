---
name: project-changelog-en
description: Changelog
metadata:
  version: "2.0.0"
  lang: "en"
---

# Changelog

## Multi-language

[简体中文](../CHANGELOG.md) | **English** | [Español](../es/CHANGELOG.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Changelog

### v7.0.5 — 2026-11-17

Layout fixes for the traffic section of the FRPS page. The upgrade command is unchanged and settings and data are kept.

#### Fixed

- **The traffic section of the FRPS page did not fill the card.** The heading was centred and the four tiles were narrower than the card. It now uses the same traffic-card layout as the Tailscale and FRPC pages: left-aligned heading, tiles across the full card width.
- **The "Access" button touched the tiles above it.** There is now a gap between them.

#### Verification

Checked by logging in and rendering the FRPS page on the Macau server. The whole automated suite passes.

### v7.0.4 — 2026-11-17

Security hardening: three issues found in a code review are fixed. The upgrade command is unchanged and settings and data are kept.

#### Security

- **Connection read timeouts.** After the TLS handshake a silent or very slow client could hold a thread and a connection forever, and enough of them made the console unresponsive (no certificate needed). Connections now drop after 60 s (console) or 30 s (public 80/443 page) without data; the limit is per read or write, so long downloads and speed tests are unaffected.
- **"Fetch from URL" can no longer be aimed at this machine or a cloud metadata address.** Loopback (127.x, ::1), link-local (169.254.x, which includes cloud metadata), unspecified and multicast addresses are refused, also when a redirect leads there; LAN addresses still work. A new message explains: "This address points at this machine or a link-local address and is not allowed."
- **Restoring a backup no longer overwrites the pinned release key.** `release-key.pub` in a backup is skipped on restore, so an uploaded backup cannot swap the signing key this host trusts.

#### Verification

Six new tests and one backup test; the whole suite passes. On the home VM a connection that sent half a request and then stayed silent was closed after 60 s, and the console pages work. The address check is covered by unit tests only; the home VM has the Files page off, so it was not exercised on a real page.

#### Known issues

- The address check runs before the download starts; it does not defend against a name that resolves differently afterwards (DNS rebinding).
- Restoring a backup can still write systemd units inside the allowed set; this needs administrator access.

### v7.0.3 — 2026-11-17

The "Choose file" button in the Backup page's upload card follows the template. The upgrade command is unchanged and settings and data are kept.

#### Fixed

- **The "Choose file" button did not follow the design rules.** It was the browser's own file input (different in every browser, unlike the other buttons). It is now the same outlined, separate button as on the Files page, with the chosen file name beside it ("No file chosen" when empty) and the Upload button on the right.

#### Verification

The Backup page was rendered on the home VM and the layout checked; the design check passes. Showing the file name after choosing and the redirect after upload were not exercised in a real browser.

### v7.0.2 — 2026-11-17

Date and time controls follow the template, and a few cards that did not fill the width are fixed. The upgrade command is unchanged and settings and data are kept.

#### Improved

- **Date and time controls.** They used to be the browser's own controls (12-hour with AM/PM, looking different in every browser). The time is now a 24-hour "hour : minute : second" segmented input, and the date is a "year - month - day" segmented input with a calendar popover (past days are greyed out and cannot be picked). You can type (it moves to the next segment after two digits), step with the up and down arrow keys, and out-of-range values are clamped; it looks the same in every browser and in the same style as the select and other controls. Used for the schedule of scheduled tasks and the scheduled backup.

#### Fixed

- **Cards that did not fill the width.** The "traffic" card on pages such as Tailscale was limited to about 44rem and the Singbox node card to 42rem, leaving a wide empty area on the right of a wide screen; both now match the content width.
- **A gap among the small cards inside a node card.** The three small cards "Port / SNI / Reachable targets" sat in a two-column grid, so the last one took only half the row. They now share the whole row by count, an odd number included; on a phone they are still two to a row.

#### Verification

The new controls were operated in a real browser on a home virtual machine: typing hour, minute and second gives 12:30:10, arrow keys step and clamp, and an incomplete value is not submitted; the calendar opens, past days cannot be picked, picking a day fills year, month and day, an invalid date (30 February) is not submitted and a valid one is. Page measurements confirm the Singbox node card and the Tailscale traffic card are as wide as the content, and the node card was viewed at desktop and phone widths. 209 automated tests; the front-end controls have no automated test and were verified item by item with a browser script.

#### Known issues

- The node's "next reset time" setting still uses the browser's own date-time control; it was not changed this time.

### v7.0.1 — 2026-11-17

The backup restore flow is reworked, and the backup keys get copy buttons. The upgrade command is unchanged and settings and data are kept.

#### Improved

- **Restore previews first, then confirms.** "Restore" opens a preview showing the backup's source host, version, kind, creation time and file count. A backup from another host or a newer version counts as risky and must be ticked to confirm before it is restored; the server decides that again before acting.
- **The private key is needed only to restore.** Downloading and uploading an encrypted backup need no private key (the server holds none and cannot check it); you enter it on the preview page after clicking "Restore", a wrong key is reported at once and nothing is changed. Uploading a backup goes straight to this preview.
- **Encrypted backups record their target key.** A new encrypted backup carries which public key it is sealed to in its header; after the backup key is replaced, earlier encrypted backups are marked "Other key" in the list. Encrypted backups in the older format can still be restored.
- **The restore result is visible.** The outcome (how many files were restored, or why it failed and that "the current configuration was not changed") shows at the top of the Backup page.

#### New

- **Scheduled backups and scheduled tasks share one schedule.** The "When to run" part is the same on both pages: choose the kind first (repeating, or only once); for a repeating one choose the frequency (every so often, every day, every week, every month, custom cron), then which days, and finally the time, **exact to the second**, for example "every week, Wednesday, 12:30:10". The scheduled backup can now also run weekly, monthly, every few hours, or just once at a chosen moment.
- **One-time schedules.** Besides repeating tasks there are now tasks and backups that run only once: pick a date and a time (a time in the past is refused); afterwards the task is marked "Done" and switched off (it stays in the list, and the scheduled backup turns itself off); one missed by more than 2 minutes because the console was not running is recorded as "Missed" instead of being run after the fact.
- **Copy buttons beside the backup keys.** After generating a backup key, the private and public keys each get a copy button, using the copy feature other console pages already have.

#### Verification

Verified on a home virtual machine through the real console: previews of plain and encrypted backups; wrong and malformed private keys refused on the spot without changing data; the right key restoring with the result shown on the Backup page; after changing the host name inside a backup, the preview warns and asks for a tick, the server refuses to restore without it and changes nothing, and with it the restore succeeds; after replacing the backup key, an older encrypted backup is marked "Other key"; downloading plain or encrypted backups and uploading encrypted ones need no private key, and junk files are still refused. A real browser click on the copy button copies exactly the private key. The new schedule form of scheduled tasks and the scheduled backup was verified on the real console: weekly Wednesday 12:30:10, daily with seconds, monthly, interval and cron save and display correctly; a one-time task set 25 seconds ahead ran once at its time, was then marked done and switched off and did not run again; a time in the past, an invalid date and the old form were refused; a one-time scheduled backup made one backup at its time and turned its schedule off. 209 automated tests. The Macau host was not exercised before this release.

#### Known issues

- The console looks at the schedules every second; a daily, weekly, monthly or one-time schedule missed by no more than 2 minutes still runs, longer is not made up (a one-time one is recorded as missed).
- An uploaded encrypted backup cannot be checked for damage before it is restored, nor for which private key it needs (the older header does not record it).
- Restoring a backup from another host brings that host's data key, login method and certificates with it; the preview warns and the current state is backed up first.

### v7.0.0 — 2026-11-16

State data is stored encrypted, backups can be encrypted to a key of your own, and there are four login methods. This version migrates a data format: the upgrade command is unchanged and settings and data are kept, but going back to an older version needs a decrypt step first (see below).

#### New

- **Total traffic calibration.** The home page total gains "Calibrate": enter the usage the provider's panel shows for this period, and the console stores the difference as a "calibration", shows it on its own bar (with a sign), includes it in the total, and clears it when the next period begins. Leave it empty and save to clear.
- **Data encryption.** The installer creates the data key `/etc/vps-server/data.key`, and the console stores the admin password, sessions, the alert (Bark) key, audit records, addresses that have logged in, the console access list, allowed IPs, the Mini Drive index, scheduled tasks, backup settings, the TLS private key and the client CA private key encrypted. Plain files from an older version are read as they are and turned into encrypted ones at startup. The Backup page gains a "Data encryption" card showing the state. It protects against a copy of the state directory, a disk image or a backup without the key, not against someone who is already root on the host. Node, FRP, domain forwarding and Tailscale configuration must be read by those programs directly, and Mini Drive files and the visitor database are not encrypted.
- **Backup encryption.** Generate a key pair on the Backup page: the server keeps only the public key, and new backups are encrypted to it as `.sealed`, so it cannot open them itself; restoring asks for the private key you saved (shown once, never stored). Encrypted backups carry the data key and restore on any host; without a public key backups are plain and leave out the data key.
- **Four login methods.** Settings > Access > Client certificates: password only, certificate only, password or certificate, or password + certificate. The older "require client certificates" becomes "certificate only", and when it was off, "password or certificate". Before switching to a method that needs a certificate you must have opened the settings with an active certificate, so you cannot lock yourself out.

#### Changed

- **The total traffic's start and basis are corrected.** The total used to count from the moment the console first recorded it, so it did not match the period traffic the pages show (a node page showing tens of GiB against a total of a few hundred MiB). The period now runs from the reset day and includes what each source has already used in its current cycle; statistics left by older versions are rebuilt automatically after the upgrade (cap and reset day kept). Each row shows "raw traffic × multiplier = billed usage", which explains why it is double the page's figure. Changing the reset day recalculates the period from the new day. New installs default to the 1st of the month.
- **Before going back to a version older than v7.0.0**, run `python3 /root/apps/vps-server/src/web/secure_store.py decrypt-all`; `upgrade.py` refuses an older version while encrypted files exist. Keep the data key safe (`secure_store.py export-key`): without it the encrypted state files cannot be recovered.
- The configuration backup taken automatically before the upgrade to v7.0.0 is still plain (it is made before the data key exists); delete it once the upgrade looks fine.
- Password login, certificate login and "password + certificate" are now decided by the login method; the Backup and security settings pages are adjusted.

#### Verification

Verified on a home virtual machine through the real console: after the upgrade the installer created the data key and at startup 10 state files (including the TLS and CA private keys) became encrypted, with HTTPS, certificate login and issuing a new certificate with the encrypted CA key all working and state surviving a restart. Each of the four login methods was checked for what it allows and refuses (including a device without a certificate being unable to switch to a method that needs one, wrong passwords, and devices without a certificate being kept out), and the original setting was restored. A plain backup does not carry the data key; an encrypted backup is entirely unreadable, a missing, wrong or malformed private key is refused without changing anything, the right key restores with services running and the temporary key file removed; uploading an encrypted backup works. 191 automated tests, including the RFC vectors and cross-checks against a reference library. The Macau host was not exercised before this release.

#### Known issues

- A lost backup private key or data key cannot be recovered; keep a separate copy of each.
- Node, FRP, domain forwarding and Tailscale configuration, Mini Drive files and the visitor database are not encrypted (see above).
- The key sits on the same host as the data, so it does not protect against someone who already has root on it.

### v6.6.0 — 2026-11-16

Upgrades are now verified: a host that has pinned the maintainer's key upgrades only to releases signed with that key. The upgrade command changes, see below. Settings and data are kept.

#### New

- **Signed releases.** The release's `SHA256SUMS` carries an Ed25519 signature, `SHA256SUMS.sig`. The private key is kept encrypted on another host of the maintainer; the build machine gets back only the signature and never holds the key. Release key fingerprint: `e6d9:e0c2:55dc:3f8c:b673:defd:9043:d5a0`.
- **A verifying upgrade command.** `python3 /root/apps/vps-server/src/web/upgrade.py` verifies the signature first, then checks the package's SHA-256, unpacks it safely, checks that the version inside matches the tag, and only then runs the new package's installer; it trusts no script inside the new package. A bad signature, a checksum mismatch, an older version, or a package whose key differs from the pinned one is refused. It supports `--version`, `--variant online`, `--from DIR` (use downloaded files, no network) and `--dry-run`.
- **A pinned release key.** The first time the installer sees a package that ships a key, it pins `config/release-key.pub` as `<state root>/release-key.pub` and prints the fingerprint. From then on the installer also refuses, with the old command, a package from someone's fork or one without a key. A key change needs `--accept-key-change NEW-FINGERPRINT`. Anyone may publish their own builds with their own key; a host pinned to yours will not upgrade to theirs.

#### Changed

- **The first upgrade to v6.6.0 still uses the old upgrade command**; after that use `upgrade.py`. The first pin is trust on first use, so compare the fingerprint the installer prints with the one above.
- Verification is pure Python from the standard library (RFC 8032), so hosts need no extra dependency.

#### Verification

Rehearsed on a home virtual machine with the real signing key: installing v6.6.0 with the old command pinned the key (mode 0600, fingerprint matching); on the pinned host, installing a package without a key and one with another key with the old command were both refused and the pinned key and version stayed as they were; `upgrade.py` refused a list signed by someone else, a tampered package and an older version, verified the genuine package with `--dry-run`, then upgraded to v6.6.1 with services running and the temporary directory removed. 104 automated tests, including signatures cross-checked against OpenSSL. Downloading directly from GitHub (without `--from`) and the Macau host were not exercised before this release.

#### Known issues

- The pinned fingerprint can for now only be read with `python3 src/web/release_trust.py show --state-dir <state root>`; the console does not show it yet.
- If the private key is lost, hosts that pinned it can only accept a new key's releases through `--accept-key-change`.
- Going back to a version before v6.6.0 needs `<state root>/release-key.pub` deleted first.

### v6.5.0 — 2026-11-16

Configuration backup and scheduled tasks are new, and an upgrade now backs up only the configuration. The upgrade command is unchanged and settings and data are kept.

#### New

- **Configuration backup.** The home page gains "Backup": back up with one click, or automatically every day at a set time, keeping only the latest few scheduled backups (by default 03:00 daily, keeping 7). A backup holds all configuration and state: console settings, certificates and keys, nodes, FRP, domain forwarding, the Tailscale login and the service unit files; it does not hold program code or the files in Mini Drive. You can download it, upload an earlier backup, and restore from the page (a backup of the current state is taken first and the affected services restart afterwards). Backup files contain keys and are mode 0600.
- **Scheduled tasks.** The home page gains "Scheduled tasks": set when to run in everyday terms, no cron needed: every so many minutes, hours or days, every day at a set time, on chosen weekdays, or on one day of the month; a cron expression is still available. Commands run in the server's local time, each task has a timeout, can be enabled or disabled, run now, and notify through Bark on failure; a task is not started again while its previous run is still going; the latest 20 runs per task are kept (status, exit code, the end of the output). The configuration backup is listed too.

#### Improved

- **The per-source usage under the home page total now shows progress bars too**, so each source's share of the cap (or of the total when there is no cap) is clear at a glance. The Backup and Scheduled tasks pages are redesigned: status tags, grouped layout, tidy on a phone.
- **An upgrade backs up only the configuration.** Before an upgrade the installer saves the configuration to `<state root>/backups/` (the latest 3 are kept), so backing up whole directories by hand is no longer needed. The backup holds no program code (always available from GitHub) and no Mini Drive files. A failed backup only warns and does not stop the upgrade.

#### Verification

Verified on a home virtual machine through the real console: backup contents (including the Tailscale login, without Mini Drive files), download, upload (non-backup files and archives with paths outside the configuration are refused), the scheduled backup firing on time and pruning old ones by count, restore returning changed files to their backed-up content with services running, and scheduled tasks running as root on schedule with failures, timeouts and skipped overlaps recorded. Restore and the scheduled backup were verified on the home virtual machine, not on the Macau host. 72 automated tests.

#### Known issues

- A restore rolls the traffic counters back to their values at backup time.
- Scheduled tasks missed while the console restarts are not made up.

### v6.4.0 — 2026-11-16

FRP gains stcp mode, Singbox nodes can restrict where they may connect, the home page gets a total traffic bar, and a short nft failure no longer stops frps and the proxy. The upgrade command is unchanged and settings and data are kept.

#### New

- **FRP supports stcp.** A tcp proxy opens your home service directly on the public IP and port, reachable by anyone; an stcp proxy needs a secret key and is reached through a visitor on another machine. FRPC instances can add stcp proxies and visitors (listening on 127.0.0.1 only); the key must be at least 16 characters and is never shown again.
- **Singbox node access scope.** Each node can be unrestricted, internet-only (loopback, LAN and local addresses refused), or limited to specific IPs, IP:port, CIDR ranges or domains. The rules are written into the sing-box routes and removed with the node; other hand-written route rules are kept.
- **Total traffic bar on the home page.** The top of the home page shows the combined traffic of all metered items for the current period, with a settable total cap (GiB) and monthly reset day (1-28). The cap only shows a warning for now; it does not throttle or disconnect when exceeded.

#### Fixed

- **A short nft failure stopped frps and the proxy.** The meters exited on the first failed nft call, and frps and the proxy depend on them, so all stopped together and did not recover. The FRPS and node meters now retry for 60 seconds, during which the installed limits stay in force; only a failure longer than that stops them, as designed.

#### Verification

STCP and node access scope were verified end to end on a home virtual machine: the right key connects, a wrong key is refused, visitor ports listen on loopback only, and a restricted node really refuses loopback and LAN. The meter fix was verified with fault injection: a 20-second nft failure left node services running, a 76-second failure still stops them. The total bar was verified through the real console. There are 34 automated tests.

#### Known issues

- The total cap only warns; if nobody opens the home page when the month rolls over, the new period starts a little late.
- On Debian 11 (nftables 0.9.8), creating or deleting an FRPC instance can occasionally crash nft; the retry covers short failures.

### v6.3.3 — 2026-11-12

The online package now installs on servers in mainland China. The upgrade command is unchanged and settings and data are kept.

#### Improved

- **The online package switches to mirrors when downloads crawl.** The online package downloads sing-box, frp and Caddy from GitHub during install, which could stall on servers in mainland China (a known issue of v6.3.2). Now, when a GitHub download is still below 200 KB/s after 15 seconds, the install switches to the mirrors gh-proxy.com and then ghfast.top; wherever it comes from, the download is verified by the same SHA-256. Set `VPSSRV_GITHUB_MIRROR=https://your.mirror/` to try your own mirror first, or `none` to use no mirror. The README also explains how servers in mainland China can download the package through a mirror. Tailscale does not come from GitHub and is not affected.

#### Verification

An online in-place upgrade on an Alibaba Cloud server in Guangzhou switched to the mirror for all three components and finished in 87 seconds (it used to stall); on another server in mainland China every component was downloaded and verified. The source switching was also verified in a local simulation.

### v6.3.2 — 2026-11-12

Fixes two problems with the IP certificate. The upgrade command is unchanged and settings and data are kept.

#### Fixed

- **Installing from the IP certificate page turned on domain forwarding.** The IP certificate and domain forwarding both run on the Caddy module, and the install button on the IP certificate page installed Caddy directly, then went to the domain forwarding page with domain forwarding turned on. Now domain forwarding stays off: the install requests the IP certificate and returns to its page, and if the request fails Caddy stops and 80/443 go back to the public page. Installing from the domain forwarding page is unchanged. Domain forwarding that this already turned on is not turned off on upgrade; turn it off on the home page if it is not needed.
- **Cloud servers behind one-to-one NAT had no public IPv4.** Cloud servers such as Alibaba Cloud ECS only have a private address on their interface, so the IP certificate reported no public IPv4 and domain forwarding wrote no A record. Now, when the host's IPv4 address is private, the address its connections leave from is read from `www.cloudflare.com` over IPv4 and cached for 10 minutes.

#### Verification

Upgraded an Alibaba Cloud Debian server behind one-to-one NAT from v6.3.1: its public IPv4 was found, a Let's Encrypt IP certificate was issued, and the console port passed normal certificate verification. Installing from the IP certificate page was verified only in a local simulation, not by clicking it on a host without Caddy.

#### Known issues

- The online package downloads sing-box, frp and Caddy from GitHub during install, which can stall on servers in mainland China; use the offline package there.

### v6.3.1 — 2026-11-12

Fixes two problems with FRPC instances in traffic accounting, and the note shown when the Windows setup script runs from a network location. The upgrade command is unchanged and settings and data are kept.

#### Fixed

- **FRPC instances using the same server are counted together.** Traffic accounting counts FRPC by its connections to a server address and port, so instances using the same server cannot be told apart: in v6.3.0 each of their entries counted the same traffic, and limiting or cutting off one affected the other. These instances now share one entry for counting and limits; each instance card shows it and names the instances sharing it. On upgrade the per-instance entries of v6.3.0 merge into it, keeping totals and limits.
- **FRPC instances with non-English names (Chinese ones, for example) had no traffic accounting.** Every name FRPC management allows is now accepted.
- **Windows one-click setup script.** The script passes its own path to PowerShell in an environment variable instead of the command line, so a path with a single quote works; when run from a network location (such as a NAS share) it says CMD's "UNC paths are not supported" note can be ignored.

#### Verification

Verified with real traffic in a disposable Debian 13 container and on two LAN Debian 13 virtual machines: counting, slowing to about 1 Mbps at the cap, cutting off and recovery for port forwarding, Tailscale (local and forwarded), FRPC and iperf3, plus an in-place upgrade of both virtual machines from v6.1.0. FRPC grouping and the migration of old entries were verified in a local simulation and on one virtual machine; the setup script's launcher was verified on Windows from a UNC path (with Chinese letters and parentheses, with a UNC working directory), without a full certificate import on Windows.

### v6.3.0 — 2026-11-12

Mini Drive, the speed test, domain forwarding, iperf3, port forwarding, FRPC and Tailscale now have the same traffic accounting and limits as Singbox nodes. The upgrade command is unchanged and settings and data are kept; the install adds the service `vps-server-traffic-meter`.

#### Added

- **Traffic limits for every feature that carries traffic.** Each feature's page has a "Traffic" card with upload, download and counted totals; under "Traffic limits" you set a traffic cap (slow to 1 Mbps or cut off when reached), upload and download speed limits, a validity period and a reset schedule, the same as for Singbox nodes. Console pages, the web terminal and SSH are not counted.
  - Mini Drive (download links, uploads, server downloads) and the speed test share the console's port, so the console counts and limits them itself; when cut off, download links and the speed test answer 503 and uploads and server downloads are refused.
  - Domain forwarding: Caddy's 80/443 together. iperf3: its port. FRPC: each instance's connection to its server. Each byte counts once.
  - Port forwarding: each rule on its own; forwarded traffic enters and leaves the host, so it counts twice.
  - Tailscale: traffic on the `tailscale0` interface; what the host forwards (exit node, subnet routes) counts twice.
- The new service `vps-server-traffic-meter` (nft table `vps_server_traffic`) handles the last five. When it fails it logs and retries and never stops those features; node and FRPS metering is unchanged and still stops its service on failure.

#### Verification

On a public test host: domain forwarding slowed to about 1 Mbps (0.13 MiB/s) at the cap, could not connect when cut off, and recovered when the limit was removed; Mini Drive downloads ran at 1.01 MiB/s with an 8 Mbps download limit and answered 503 when cut off; a 20 MiB speed test counted 20 MiB; saving and clearing limits through the page worked; port forwarding and FRPC rules (with speed limits, a cap and cut-off) passed the kernel's check. Node and FRPS rules are byte-for-byte unchanged. Not verified: real port forwarding and FRPC traffic, Tailscale limits once reached, real iperf3 traffic. Known: Mini Drive downloads through a domain count toward both Mini Drive and domain forwarding.

### v6.2.1 — 2026-11-12

Fixes addresses such as Mini Drive download links pointing to `127.0.0.1` when the console is opened through a domain. The upgrade command is unchanged and settings and data are kept.

#### Fixed

- When the console was opened through domain forwarding (a site whose target is "This console"), Caddy passed the console its own connection address `127.0.0.1:port`, so every address the console built from it was wrong: Mini Drive download links and Clash subscription links pointed to `127.0.0.1`, and the web terminal failed its origin check. Caddy now passes the domain the visitor used; only the site's own domains reach the console this way. Reload the page after upgrading; existing download links do not need to be created again.
- While Caddy runs, the home "Public page" link pointed to the domain when the console was opened through one, but Caddy shows that page only for the host's IP. The link now uses the public IPv4.

#### Verification

On a public test host, a temporary client certificate signed in to the console through a domain: every Mini Drive download link used that domain, and "Public page" led to the host's IP; access through the IP and console port is unchanged. Not verified: the web terminal through a domain.

### v6.2.0 — 2026-11-12

Adds Mini Drive: keep files on the server for a while and create password-free download links, for example so a server that cannot reach GitHub can download from here. The IP certificate becomes a separate switch on the home page and no longer needs a domain to be configured first; the public reachability page also keeps working while Caddy runs; domain forwarding supports several Cloudflare tokens. The upgrade command is unchanged and settings and data are kept.

#### Added

- **Mini Drive (off by default).** Files can be uploaded from the browser, or you can enter an http/https URL for the server to download itself (in the background; the browser can be closed). Each file can have several download links with an expiry of 5, 10 or 30 minutes, 1, 2 or 5 hours, 1, 7 or 30 days, or never, an optional download limit, and each can be revoked at any time. Whoever has a link needs no password or client certificate, and `curl -O`, `wget` and resumed downloads all work. The limit defaults to 5 GiB, and at least 500 MiB always stays free on disk. A download speed limit can be set; all links together stay under it. An upload that is interrupted or gets no data for 2 minutes has its partial file discarded, and leftover files are cleaned every 10 minutes.
- **Separate switch for the IP certificate.** The home page gets an "IP certificate" tile that obtains a Let's Encrypt certificate for the host's public IPv4 on its own, so it also works on hosts that do not bind a certificate to a domain. It shares Caddy with domain forwarding (the domain forwarding module must be installed); each has its own switch, and Caddy runs when either is on.
- **Several Cloudflare tokens.** When domains belong to different Cloudflare accounts, several tokens can be added (up to 20, nameable). Each site automatically uses the token that can manage its main domain. A token Cloudflare rejects is not saved. The previous single token is converted automatically the first time a token is changed.

#### Changed

- **The public reachability page is no longer disabled while Caddy runs.** Caddy returns the page directly: port 80 shows it for the IP and for names that are not configured (no HTTPS redirect, so that port 80 itself can be tested), and port 443 shows it for `https://host-IP/` while the IP certificate is on. HTTP requests for domain sites still redirect to HTTPS.
- **One "Public page" switch on the home page.** The former "HTTP page" and "HTTPS page" tiles are merged; one switch turns both pages on or off, and the tile has separate buttons to open the HTTP and HTTPS pages.
- "Stop picking the certificate every time" is now shown expanded on the certificate issuing page and in the security settings; the layout of the Mini Drive and IP certificate pages is tidied.

#### Fixed

- When a dropdown menu was narrower than its options, option text was squeezed into one character per line: the menu width now follows the options.

#### Verification

Each test version was deployed by file copy to a public test host and verified: Mini Drive upload, server download (a GitHub Release asset), download links working without a certificate through both the IP port and a domain while client certificates are required, download limits, expiry, speed limit (both a single download and two simultaneous downloads match the setting); the four combinations of the IP certificate and domain forwarding switches; the public reachability page by IP over http/https (strictly validating the IP certificate) while domain requests still redirect; conversion of an old token with several tokens and DNS sync, and a Cloudflare-rejected token not being saved; the public page switch while Caddy runs. On the local machine, mocked interfaces and connections verified picking a token across accounts and that stalled and interrupted uploads leave no file. Not verified: a real token from a second Cloudflare account; the "Public page" switch changing both ports in one go when there is no Caddy; stalled uploads on a real network; IPv6 records.

### v6.1.0 — 2026-11-11

Client certificate login takes less effort: one-click setup files import the certificate and make the browser pick it on its own, so you no longer search the picker at every login; certificates now import on macOS. The upgrade command is unchanged and settings and data are kept.

#### Added

- **One-click setup files.** The first step on the page shown after issuing a certificate offers Windows (`.cmd`), macOS (`.mobileconfig`) and Linux (`.sh`) files. They import the certificate and, through the browser policy `AutoSelectCertificateForUrls`, make Chrome and Edge (plus Chromium on Linux) pick it on their own for each console address (the current address, and the domains and IP that point to the console). A device that already has the certificate can download a version without it from Settings > Security > Client certificates to turn on auto-select only. The manual `.p12` steps move into "Manual import" on the issued page.
- **Certificate names include the host name.** Newly issued CAs and device certificates carry the host name, so certificates from several hosts can be told apart in the picker. Existing CAs keep their names and issued certificates keep working.

#### Fixed

- macOS reported a wrong password when importing a certificate (both Keychain and profiles): the certificate bundle now uses encryption that macOS supports (SHA1/3DES). Certificates issued earlier must be reissued for use on a Mac.
- When the connection presents no certificate, the certificate card tells a new device to generate its own below.
- The edit, access log and delete buttons at the bottom of the domain forwarding site cards sit in one row with matching styles.

#### Verification

The operator verified the Windows setup on a real machine. Linux was verified end to end on Ubuntu 22.04 with Chrome 157 (import, policy write, and both the console's IP and domain addresses sending the certificate with no picker). The operator imported a certificate with the new encryption on macOS through the profile and signed in. Not verified: snap Chromium (separate certificate store, not supported by the script) and Firefox (does not read these policies). Known limitation: on one Mac, profiles from two hosts conflict over the browser policy.

### v6.0.0 — 2026-11-11

Adds a domain forwarding module (bundled Caddy) that replaces the removed Lucky module: HTTPS by subdomain to a local port or the console, with automatic certificates and DNS records kept on Cloudflare. The console can also get a trusted certificate for the host's IP. The upgrade command is unchanged and settings and data are kept; the Lucky module is removed during the upgrade.

#### Added

- **Domain forwarding (`caddy` module).** On the Domains page, add a subdomain (choosing from the main domains the Cloudflare token can manage) and forward it to a local port (such as an frps port) or to the console itself. The bundled Caddy 2.11.9 obtains and renews Let's Encrypt certificates, so it takes ports 80/443 and the public reachability page is off while it runs. A/AAAA records (DNS only) are created and removed through the Cloudflare API; the host's public IP is checked every 5 minutes and records follow it.
- **Site management.** Each site can be switched off and edited; the backend may speak HTTPS (its certificate is not checked, for self-signed NAS or router pages), and the backend can receive either the original name or its own address as Host. Up to 8 extra names per site, limits by source address or network, and a password prompt (only the hash is stored). Each site has an access log (last 200 requests).
- **History and alerts.** Site changes, switches, DNS records and public IP changes are recorded. A changed public IP, a failed DNS update or a certificate close to expiry and not renewed is pushed through the console's existing Bark settings, at most once a day per event.
- **Console on a domain.** A site can target "this console": Caddy hands the client certificate to the console, and "require client certificate" still applies.
- **HTTPS certificate for IP access.** Turned on from the Domains page, it gets a Let's Encrypt certificate for the host's public IPv4 (about 6 days, renewed by Caddy), and the console's existing `https://IP:port` uses it, so browsers stop warning. Ports 80/443 do not serve the console for the bare IP.

#### Removed

- **Lucky module (breaking).** The DDNS, reverse proxy and certificate features in use are covered by domain forwarding. The upgrade stops and removes Lucky after archiving its settings to `data/module-backup-lucky-*.tar.gz` in the state directory; `lucky` in `VPSSRV_MODULES` is ignored.

#### Fixed

- The online installer check reported hashed CA certificate directories as missing certificates.

#### Verification

Installed and upgraded from an older version in throwaway Ubuntu 24.04 system containers, testing site switches, edits, HTTPS backends, the Host choice, address limits, passwords, extra names, access logs and alert de-duplication. On a public test host with a real Cloudflare zone and Let's Encrypt: certificates for subdomains and extra names, passwords, address limits, switches, DNS cleanup on removal, the console on a domain, and the IP certificate being issued and picked up by the console (one forced reissue was picked up automatically). Not verified: the natural renewal of the 6-day IP certificate, real Bark delivery (only a mocked send), IPv6 records, opening 80/443 in ufw/firewalld. Wildcard certificates and certificate export are not supported; DNS is Cloudflare only.

### v5.8.0 — 2026-11-08

FRPS gets the same traffic accounting and limits as Singbox nodes; client certificates are now signed with a bundled OpenSSL, fixing invalid certificate authorities on hosts with an old openssl. The upgrade command is unchanged and configuration and data are kept.

#### Added

- **FRPS traffic accounting and limits.** The same as a Singbox node: upload/download usage, a traffic cap (throttle to 1 Mbps or block once exceeded), upload and download speed limits, a validity period and a reset schedule; the cap counts `(upload + download) × 2`. FRPS is metered on its bindPort, which every frpc tunnel crosses. Usage shows on the FRPS page and the "Limits" dialog edits it. A new service, `vps-server-frps-meter`, does the metering and stops FRPS if accounting fails. The FRPS module therefore needs nftables: the offline package bundles it, and the installer installs it with apt for the online package when missing.
- **Minimum dependency versions.** Before changing any service, the installer checks Bash 4.1, systemd 240, SQLite 3.24 and the OpenSSL library 1.1.1 as used by Python, `/usr/bin/python3` 3.9+ and basic commands (flock, sha256sum, base64, getent, install, mktemp, systemd-run); the online package also checks for CA certificates. Unmet requirements stop the install and name what is missing.
- `python3 /root/apps/vps-server/src/web/client_cert.py check` shows the openssl used to sign certificates and the certificate authority's self-test result.

#### Improved

- Client certificates are signed by the static OpenSSL 3.5.9 LTS shipped in the package, with the project's own minimal configuration, so the host's openssl version and openssl.cnf no longer matter; the installer no longer installs openssl with apt.
- A host `ip`/`ss` without JSON routes or `-H` gives way to the bundled copy; a host iperf3 is used only when no bundled copy exists, and must be 3.1+.

#### Fixed

- On hosts with OpenSSL 1.1.1k or similar old versions, the client certificate authority was written with Basic Constraints twice and failed even its own verification, so certificate login could not work. A new authority must now pass a mutual-TLS self test on the host TLS library; an existing invalid authority is replaced the next time a certificate is issued, the certificates it signed are marked revoked, and "Require client certificate" is turned off.
- FRPC connection status always read disconnected on hosts with only the bundled `ss`.
- The README offline install's `sha256sum -c SHA256SUMS` failed when only the offline package was downloaded; it now uses `--ignore-missing`.

#### Verification

OpenSSL 1.1.1k reproduced the original problem locally and the fix was confirmed; dependency checks and certificate issuing passed in a Debian 11 container (Python 3.9, libssl 1.1.1w). In a Debian 13 system container, the offline package installed web, proxy and frps: all services ran, the console was driven over HTTPS, FRPS limits took effect in the kernel rules, node limits worked as before, and a full uninstall left nothing behind. The operator upgraded a VPS in place with `v5.8.0-test.1` and confirmed certificate issuing and login and FRPS traffic and cap limits. Not verified on a real host whose TLS library is OpenSSL 1.1.1k, and the 1 Mbps throttle rate was not measured on a real host. After the FRPS bindPort changes, the new port goes unmetered for up to about 2 seconds.

### v5.7.0 — 2026-11-08

Stronger console login security. The upgrade command is unchanged and configuration and data are kept; the installer mentions 4 new optional variables, and leaving them unset keeps the defaults. The new settings are under Settings > Security.

#### Added

- **Failed-login ban switch.** On by default. When off, nothing is banned, but failures per IP are still counted and an IP that reaches the threshold is marked "threshold reached, not banned", so you can test that detection works. Records can be cleared.
- **Escalating bans.** Each repeat ban of the same IP within a day lasts ten times longer: 30 seconds, 5 minutes, 50 minutes, about 8 hours, at most 24 hours (`VPSSRV_LOGIN_LOCKOUT_MAX_SECONDS`). A successful login resets it.
- **IPv6 /64 grouping and a global limit.** Addresses in the same /64 count together. When all sources together fail 20 times within 60 seconds, addresses that never logged in successfully cannot use the password for 5 minutes (`VPSSRV_LOGIN_GLOBAL_MAX_ATTEMPTS`, `VPSSRV_LOGIN_GLOBAL_LOCKOUT_SECONDS`); known addresses, certificate login and IP access are not affected.
- **Console access limit.** Off by default. When on, only listed IPs or networks can connect to the console; other addresses are dropped before the TLS handshake. It cannot be turned on, nor an entry removed, in a way that shuts out the current connection. If you are locked out, run `python3 /root/apps/vps-server/src/web/console_access.py disable` as root; no restart is needed.
- **Signed-in devices.** Lists signed-in devices (browser, system, IP, sign-in and last activity) and can sign out one device or all others. Logins end after 2 hours without activity (`VPSSRV_SESSION_IDLE_SECONDS`); terminal input counts as activity.
- **Security log and Bark login alerts.** Records logins, bans, root terminal sessions and security setting changes, and shows the latest 50. With a Bark key, logins from a new address and bans are pushed to your phone; the key is never shown on the page.

#### Improved

- Console responses carry a Content-Security-Policy that allows only the console's own scripts, and forbid embedding by other sites. The former inline script moved to its own file.

#### Fixed

- Behind a reverse proxy (`VPSSRV_TRUST_PROXY=1`), the client address is now the last `X-Forwarded-For` entry the proxy appended, so a forged header no longer affects rate limiting, logs or the access limit.
- The login page leaves space between the certificate login button and the password label.
- The README extraction commands and the installer's own extraction name the `tar` filter explicitly, removing the `DeprecationWarning` on Python 3.12 and 3.13.

#### Verification

Local runtime tests cover bans, the switch, IPv6 grouping, the global pause, the access limit, signed-in devices, the security log and Bark alerts against a mock server; 15 pages show no CSP violations in a headless browser. The operator installed `v5.7.0-test.1` and `v5.7.0-test.2` online on a LAN test machine and confirmed failure counting, marking while off, banning while on and the new layout. Not yet tested with a real Bark account or behind a real reverse proxy.

### v5.6.3 — 2026-11-06

**Upgrading is recommended for everyone, especially hosts installed from the offline package.** The upgrade command is unchanged and configuration and data are kept. Run the upgrade over SSH, not in the console's own terminal.

#### Fixed

- pcre2 in the system runtime bundled with the offline package (nft, iptables, `ip`, `ss`) is updated to the Debian security release 10.46-1~deb13u3, which fixes an oversized JIT stack allocation (GHSA-r9hj-j2rw-4q3m). Packages were previously taken only from the Debian main archive, which missed the security archive; the other 31 packages were checked one by one and match current Debian 13. Upgrades replace the installed runtime.
- Upgrading from the console's own terminal showed only a bare `Terminated`, with no sign whether the installation was still running. It now warns up front that the terminal disconnects when the console restarts while the installation continues in the background, and gives the command to check the result; an interrupted progress view also says the installation continues.
- Console restarts no longer stall for 90 seconds: open terminals are now hung up properly on shutdown.

#### Improved

- After a client certificate is generated, the page now shows four steps: download, import into the system certificate store (Windows, macOS, Android and iOS each explained, plus Firefox's separate store), fully quit and reopen the browser, and confirm the certificate is in use before turning on Require client certificate. Security settings explain the usual causes when certificates exist but the current connection presented none.

#### Internal maintenance

- Upstream binaries such as sing-box, frp, Lucky and Tailscale are no longer committed; the offline build downloads them from pinned URLs and verifies each SHA-256. Package contents are unchanged. Source installs download these programs at install time, like the online package.

#### Verification

Verified in a throwaway Debian 13 container: upgrades from v5.6.2 run both inside the console terminal's control group and from a normal shell; nft, iptables, `ip` and `ss` from the new runtime run; an offline package built from a fresh clone carries byte-identical programs and installed and ran the proxy module. The certificate import steps were checked as page content only and are not yet tested on macOS, Android or iOS.

### v5.6.2 — 2026-11-06

**Upgrading is strongly recommended, especially on hosts with the Tailscale module.** The upgrade command is unchanged and configuration and data are kept.

#### Changed

- Bundled components updated: Tailscale 1.102.4 → 1.104.5, sing-box 1.13.14 → 1.13.21, frp (FRPS, FRPC) 0.71.0 → 0.72.0. All three match the upstream published checksums.
  - Tailscale 1.104.4 fixes security bulletins TS-2026-014 to 017 (Tailscale SSH and serve). This project does not enable either feature, so default use is not affected; hosts where Tailscale SSH was turned on manually should upgrade promptly.
  - frp 0.72.0 fixes lost frpc configuration on reconnect, a CPU busy loop after session close and a data race that could crash the process.
- Upgrades now replace the older FRPC client this project installed (`/usr/local/bin/frpc`) and restart running instances; an frpc placed or changed by the user is left alone. Uninstall still recognizes the older client.

### v5.6.1 — 2026-11-06

**All users are strongly advised to upgrade.** This release only updates a security-relevant dependency; the upgrade steps are unchanged and configuration and data are not affected.

#### Fixed

- The console frontend's vue-i18n moves from 11.4.13 to 11.4.18, fixing two cross-site scripting (XSS) advisories (GHSA-8rc2-428q-7ww3, GHSA-83rm-6c8r-g728). Analysis of the current code found no exploitable path, since the console does not enable `escapeParameter` or render translations as HTML; the upgrade keeps a dependency with open advisories off installed systems.

### v5.6.0 — 2026-11-06

#### Added

- Client-certificate login. Settings > Security > Client certificates issues a `.p12` certificate per device (the import password is shown once); once imported into the system, the browser logs in with it instead of a password. Certificates can be revoked one by one, and the server never keeps a device's private key. With "Require client certificate" on, a device without a valid certificate sees only a block page (IP allowlist login also needs a certificate), the password is used only to re-verify the root terminal and security settings, and Clash subscriptions keep working. It cannot be turned on unless the current connection presents a certificate, and the certificate in use cannot be revoked while it is required; after losing a certificate, root runs `python3 /root/apps/vps-server/src/web/client_cert.py disable` to restore password login. Issuing, importing, certificate login and turning the requirement on were verified in Chrome on Windows.

- When the host lacks a working nftables, installing Singbox from the installer or from a console module job now installs it with apt first instead of asking for a manual command; it stops with a reason only when apt is missing or the install fails. Uninstalled module cards in the console say it will be installed automatically.

#### Changed

- The console is served over HTTPS only. `VPSSRV_CONSOLE_TLS=0` no longer has an effect, and an install that ran over HTTP moves to HTTPS on upgrade with the same port. The installer installs `openssl` with apt when it is missing, for issuing certificates.

### v5.5.1 — 2026-10-23

#### Fixed

- The offline package no longer announces a download during install: nothing is downloaded or announced when the components are already in the package, and the notice appears only when a download is actually needed.

### v5.5.0 — 2026-10-23

#### Added

- Releases now ship two packages. The offline package bundles every third-party program and system tool; the target needs no network, curl, Git, tar or gzip, only Python 3.9+. The online package is about 4 MB: the installer downloads Singbox, Lucky, FRP and Tailscale for the selected modules, verifies each by SHA-256, and installs any missing iptables, iproute2 and nftables with apt. Adding the FRPC or Tailscale module later from the console downloads them the same way.

- The offline package's bundled runtime now includes iproute2 (`ss`, `ip`) and its libraries. When the host lacks these commands the bundled ones are used, and the missing-`ss`/`ip` warning no longer appears.

- The language prompt at the start of an install continues with the default after 5 seconds without an answer, so unattended installs finish on their own. `VPSSRV_PROMPT_TIMEOUT` changes the seconds; `0` waits forever.

#### Changed

- Installation no longer depends on curl, tar or gzip: the one-line install command, unpacking the Tailscale and nftables runtimes, and host checks now use Python's own tarfile and urllib. Minimal images do not need these commands installed first.

- The offline package grew from about 98 MB to about 167 MB because it carries iproute2 and its source.

- The browser tab title separator changed from the long dash `—` to a short hyphen `-`.

- The build script retries when downloading Debian packages fails.

### v5.4.0 — 2026-10-21

#### Added

- The complete package bundles Debian 13 nftables 1.1.3 and iptables 1.8.11 together with glibc, started by the bundled loader. On Debian 11+ and Ubuntu 20.04+ hosts without nftables or iptables, or without network access, node traffic accounting, rate limits and port forwarding still work. A host copy that can read the rules is still preferred; Web-only installs also receive this runtime.

- Host requirements are checked before a module is installed: Singbox needs a working nftables, and Tailscale needs `/dev/net/tun` and no other running tailscaled. The installer, console install jobs and the cards and install pages of uninstalled modules share these checks; when one is unmet, the install stops before changing anything and shows the reason and fix instead of a bare "failed".

- On a first install the command stays in the foreground following the background job, showing only key steps and then the console address and initial password; on failure it shows the reason and a few related log lines. Ctrl-C or an SSH disconnect only stops the display; the install continues.

- Feature pages for a missing module can install it directly and show progress in place.

- A failed settings save shows an 8-second toast, and the page no longer repeats the same error inline.

#### Changed

- Fresh installs serve the console over HTTPS with a self-signed certificate, and session cookies carry `Secure`; upgrades keep the previous setting.

- Installing Singbox, Lucky or Tailscale from the console installs only that module; Web and other modules keep running.

- Before stopping any service, the installer checks the Python version (stopping below 3.9) and iptables, `ss` and `ip` (warning when missing and naming the affected features).

- Node meter errors now include nft's own error message.

#### Fixed

- On Debian 13 hosts without system nftables, the node meter restarted in a loop and stopped Singbox: the old bundled nft 0.9.8 cannot read rules written by newer iptables-nft, and the install preflight only ran `nft --version`, so it did not catch this. The preflight and runtime checks now actually read the ruleset.

- Port forwarding and iperf3 forms lacked CSRF tokens, so a page on another port of the same host could submit them.

- Idle connections pre-opened by browsers could make the HTTPS console and public page stop answering: TLS handshakes now run in each connection's worker thread with a 10-second timeout.

- Changing the console port restarted Web while holding a lock, so the new process timed out releasing a stale iperf3 port registration and crashed; a failed release of stale registrations also no longer stops Web from starting.

- Installing Lucky from the console stopped Singbox; after uninstalling Lucky its page no longer offered an install button.

- A failed first Tailscale install left its unit file and binaries behind, and the rollback could miss releasing port registrations.

- The install summary's public page status disagreed with the console switches; FRPS/Lucky installs failed and rolled back on a firewall rule that was already gone; the proxy configuration file is now 0600, and BBR uses its own sysctl file that a full uninstall removes.

- The terminal page and the FRPS and FRPC not-installed pages used the home tab icon.

### v5.3.1 — 2026-10-07

#### Fixed

- Installing with a shorter `VPSSRV_MODULES` (such as the README quick install) dropped installed modules from the record and stopped sing-box through the node-meter dependency: an explicit list now only adds modules, and modules still present on disk are counted again.

- A foreign process on a public page port aborted every install and module job of an existing install; it is now a warning. A missing frontend bundle now stops the install before anything is written, instead of leaving a partial state directory that blocked later installs.

- Uninstalling Singbox removed every node: it now keeps the sing-box configuration and node inventory and releases only the service, firewall rules and port registrations. Reinstalling registers the kept nodes' ports again (failing cleanly if one is in use) and reopens their firewall rules. The uninstall confirmation now says the configuration is kept.

- Reinstalling Lucky failed with "Address already in use" because connections the console had just closed were in TIME_WAIT: the Lucky and FRPS setup scripts and the node, FRP and iperf3 port checks now probe with `SO_REUSEADDR` like the servers do.

- Uninstalling FRPC stopped every instance and reinstalling did not bring them back: the uninstall now remembers which instances were enabled and the reinstall enables them again, unless the whole FRPC group is switched off.

### v5.3.0 — 2026-10-07

#### Added

- Shared interface components: the header and the new footer (GitHub profile, project repository) glide item by item when the window is resized; the settings section navigation eases along while scrolling and becomes a top bar on narrow screens; the tab icon follows the theme color and light/dark mode; Appearance gains "Follow system"; the server label badge links back to the dashboard.

- The Clash QR code opens from a button in a dialog; confirmations for uninstalling, clearing log history, deleting a proxy and clearing visitors use the console's own dialog instead of the browser prompt.

#### Changed

- The Web frontend now uses the shared template (Vue 3, Vite, TypeScript, Tailwind CSS): unified design tokens, eight theme colors and responsive layout, with page content as wide as the header. The frontend is built in `web/` and the complete package includes the build output; source installs must first run `npm ci && npm run check` in `web/` (Node.js 24).

- The top left of the header shows only the project name, without the logo (a project exception recorded in `doc/LOG.md`).

- The public page (80/443) returns a single plain-text line, "The server sees your IP address".

- On refresh the server-rendered fallback layout stays hidden until the shared header and the styled dropdowns are ready, so the old layout and native dropdowns no longer flash.

- iPerf 3, Singbox, FRPS, FRPC, Lucky, Tailscale and Terminal pages were re-laid out: iPerf 3 page title with Server and Client cards, left-aligned Singbox counters, FRPC instance heading and new-instance button on one row, a larger terminal with a smaller font. The Lucky admin page and the home HTTP and HTTPS tiles open in a new tab. The Tailscale connect button joins the same row, the version shows only the release number, and the route and exit node lists no longer have a "Clear" entry.

- Tool directories now use hyphenated names (for example `tools/build-offline`), a shared static check `tools/check-project` was added, and CI pins its Actions; installation commands are unchanged.

#### Fixed

- Installing or toggling iperf3 restarted Web while the status page was loading, leaving the page on the old state.

- The installer aborted during an upgrade because TIME_WAIT sockets left by just-closed connections were mistaken for ports 80/443 being in use.

- Repeated clicks on Tailscale "Connect" failed: only one connection runs at a time, the login address is awaited, and the button is disabled after a click (Tailscale works on the real host, confirmed by the operator).

- Black strip at the bottom of the terminal, empty card on closed-module pages, wrong target of the back control on the detailed log page, and duplicated page icons.

### v5.2.3 — 2026-10-05

#### Changed

- Rebuilt project documentation using the current standards, with Simplified Chinese, English, and Spanish versions.

- Simplified quick installation to one command that installs only Web by default, and added offline steps under regular installation.

- Added 16 real interface screenshots to README, grouped in collapsible sections with addresses and credentials hidden.

### v5.2.2 — 2026-10-05

#### Changed

- Installation runs as an independent systemd job after language selection, retaining logs/exit status and continuing after disconnection.

#### Fixed

- Unify typography/control sizing across Settings, iperf3, Singbox, FRPC and Tailscale; fix selects, narrow layouts and log-filter alignment. Add a detailed-log entry beside the home changelog.

- Editors load existing values; proxy edit/delete actions share a row and delete buttons use red backgrounds with clear hover feedback. FRPC lists server IPs and forwarding targets, synchronizing public-address visibility; FRPS addresses are hidden by default.

- FRPC save/rename returns a job waiting page and retries result queries after tunnel restart, preventing empty responses after successful saves. Invalid changes retain/restore prior configuration; request credentials are removed before execution.

- Tailscale logout uses a confirmation dialog and routes/exit nodes use single-select controls; fix long version/account text, the logged-out form and key visibility controls.

### v5.2.1 — 2026-10-05

#### Fixed

- Include and verify Tailscale 1.102.4 in source installs, retain resources for Web-only installs and give a clear missing-archive message.

- Complete uninstall clears Lucky settings/tasks and project FRPS/unified-proxy leftovers; keep-data mode is retained. Firewall cleanup failure stops deletion and preserves ownership records.

### v5.2.0 — 2026-10-05

#### Added

- Add a password-rechecked browser root terminal, offline Tailscale module, detailed logs and visitor-history clearing; include nftables runtime and corresponding Debian sources in complete offline packages.

#### Changed

- Move state to the separate `/var/lib/vps-server` layout and preserve it on same-layout reinstall; v5.1.0 and earlier have no automatic migration. Unify AnyTLS in Singbox, move module cards to top-level Settings, and count traffic as `(upload + download) × 2`.

#### Fixed

- Fix FRPS edits without port records, node editing, native Lucky port synchronization, terminal size/scrolling and recheck redirects. Prefer working system nft and register port changes through privileged helpers.

### v5.1.0 — 2026-10-04

#### Added

- Bundle checksum-pinned FRPC, FRPS and iperf3 x86-64 Linux artifacts in source.

#### Changed

- Limit languages to Simplified Chinese, English and Spanish, remove COMMITS.md, target x86-64 Linux and edit only managed proxy nodes. Complete uninstall clears FRPC instances/templates/ports; keep-data mode retains instance configuration.

#### Fixed

- Support non-ASCII passwords, rebuild kernel quota on cycle reset, roll back partial forwarding failures, unify port records/version synchronization, and fix FRPC module state and test-build changelog recognition.

### v5.0.0 — 2026-10-03

#### Added

- Add timed iperf3 client TCP/UDP tests, independent public-page controls and a persistent server label.

#### Changed

- Complete first install in the terminal with Web only by default; split source/styles by feature and retain unexpired sessions on ordinary restarts.

#### Fixed

- Support Unicode FRPC names, retain nodes/state on reinstall and fix complete-uninstall completion messages and exit status.

### v4.0.0 — 2026-09-29

#### Added

- Add a temporary HTTPS first-install wizard, module jobs and local FRPC CRUD/testing/simple proxy editing; separate FRPS/FRPC home entries.

#### Changed

- Give home feature cards independent switches, move modules to ordinary Settings, refine responsive forms/themes, remove page-transition animations and toggle forwarding without restarting Web.

#### Fixed

- Stop requiring an edit index for new FRPC proxies, stop visitor collection when disabled and retain saved node fields on reopening.

### v3.0.0 — 2026-09-28

#### Added

- Add managed nodes for five protocols, sharing/QR codes, quotas/rate limits/cycle resets/expiry and a private-IP passwordless allowlist.

#### Changed

- Unify console layouts, themes/accent colors and sensitive-value hiding; separate iperf3 status from port editing and retain runtime entry/modules on upgrade.

### v2.0.0 — 2026-09-27

#### Added

- Add four-protocol proxy, first-install wizard and experimental FRPS/Lucky modules with original licenses and artifact hashes.

#### Changed

- Move install entry points to `deploy/`, Web to `src/web/`, dependencies to `third_party/` and release metadata to `config/`; organize documents/translations by standard directories.

### v1.1.2 — 2026-09-21

#### Fixed

- Fix old-version upgrades silently ending after a new prompt, before copying files or updating services.

### v1.1.1 — 2026-09-20

#### Fixed

- Fix README commands checking out v1.0.4 instead of v1.1.0.

### v1.1.0 — 2026-09-19

#### Added

- Add TCP/UDP forwarding, iptables DNAT/MASQUERADE, startup replay and managed-port conflict checks.

### v1.0.4 — 2026-09-12

#### Changed

- Show real egress/interface addresses in installation output; retain a placeholder without aborting if detection fails.

### v1.0.3 — 2026-09-12

#### Fixed

- Retry the full update/install flow for stale package indexes and replace README repository/version placeholders.

### v1.0.2 — 2026-09-12

#### Fixed

- Attempt iperf3 installation even after repository-update failure, retry updates and retain installation errors.

### v1.0.1 — 2026-09-12

#### Fixed

- Stop rendering maintainer HTML comments in changelog pages.

### v1.0.0 — 2026-09-12

#### Added

- First release combining password-protected Web speed tests, visitor logs, AnyTLS, public reachability on 80/443 and timed iperf3 windows; add namespaced configuration and data-preserving uninstall.
