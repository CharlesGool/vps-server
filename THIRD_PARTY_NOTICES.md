# Third-party notices

**English** | [简体中文](translated_zh_cn/THIRD_PARTY_NOTICES_zh_cn.md) | [繁體中文](translated_zh_tw/THIRD_PARTY_NOTICES_zh_tw.md)

This project itself is licensed under GPL-3.0 (see [`LICENSE`](LICENSE)). It is
GPL-3.0 rather than something more permissive because it redistributes the
sing-box executable, which is GPL-3.0; the combined work must be too. Code
vendored from `vps-webserver`, which is Apache-2.0 upstream, is redistributed
here under GPL-3.0 — Apache-2.0 permits this, and the reverse would not have
been permitted.

There are no third-party Python packages. `app.py` uses only the standard
library, so there is no lockfile to audit and nothing to keep patched.

---

## sing-box

This repository redistributes an unmodified official sing-box executable as
`sing-box` in the repository root. It is installed as
`/usr/local/bin/sing-box-vps-server`.

- Component: `sing-box`
- Upstream project: https://github.com/SagerNet/sing-box
- Upstream copyright: Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- Version: `v1.13.14`
- Source revision: `25a600db24f7680ad9806ce5427bd0ab8afe1114`
- Distributed artifact: `sing-box-1.13.14-linux-amd64.tar.gz`
- Repository binary SHA-256: `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- License: GNU GPL version 3 or any later version, plus the upstream
  name/association condition; see [`LICENSES/sing-box-LICENSE`](LICENSES/sing-box-LICENSE)

The executable in this repository was compared byte-for-byte with the
executable in the official upstream Release archive and is unmodified.

### Corresponding source

The complete corresponding source for this exact binary is available without
charge at:

- Tagged source tree: https://github.com/SagerNet/sing-box/tree/v1.13.14
- Exact source revision: https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- Source archive: https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

The official binary Release used here is:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

This project is independent and is not affiliated with or endorsed by the
sing-box or SagerNet authors.

---

## LibreSpeed

The browser speed test uses LibreSpeed's own client engine, vendored unmodified.

- Component: LibreSpeed client engine — `static/speedtest.js`, `static/speedtest_worker.js`
- Upstream project: https://github.com/librespeed/speedtest
- Version: `v6.2.1`
- License: GNU LGPL version 3; full text at [`static/licenses/LGPL-3.0.txt`](static/licenses/LGPL-3.0.txt)
- Modified: no. Both files are byte-identical to the upstream release.

`static/speedtest-ui.js` is this project's own glue code and is not part of
LibreSpeed. The server-side endpoints in `app.py` (`/speedtest/garbage`,
`/speedtest/empty`, `/speedtest/getip`) reimplement LibreSpeed's documented
client/server contract; they are original code, not derived from the upstream
PHP backend.

LGPL-3.0 permits combination with this GPL-3.0 work.

---

## iperf3

- Component: `iperf3`
- Upstream project: https://github.com/esnet/iperf
- License: BSD 3-Clause
- Modified: no
- **Not redistributed.** `iperf3` is installed from the operating system's
  package repository by `install.sh` and is invoked as a separate program over
  a process boundary. No iperf3 code or binary ships in this repository, so the
  BSD attribution requirement, which attaches to redistribution, is not
  triggered here. It is listed anyway because the project depends on it at
  runtime and a reader should know where it comes from.

---

## Vendored from this author's own projects

Not third-party, but recorded here because the code did not originate in this
repository and its provenance matters for updates:

- `app.py`, `static/speedtest-ui.js`, `static/style.css`, `static/visitors.js`,
  `tests/`, `install.sh`, `uninstall.sh`, `systemd/` — from `vps-webserver`
  v0.4.1 (Apache-2.0 upstream, relicensed GPL-3.0 here). See `.upstream-version`.
- `anytls/setup-anytls.sh`, `sing-box`, `anytls/sing-box.version` — from
  `Anytsl-Serve` v1.2.0 (GPL-3.0 upstream). See `anytls/.upstream-version`.

---

No third-party fonts, icons, images, datasets, or model weights are included.
At runtime the service makes no outbound request; the only optional outbound
call is a public-IP lookup during installation, which degrades to a warning
if it fails.
