---
name: project-third-party-notices-en
description: Third-party attribution and compliance notices
metadata:
  version: "2.0.0"
  lang: "en"
---

# Third-Party Notices

## Multi-language

[简体中文](../THIRD_PARTY_NOTICES.md) | **English** | [Español](../es/THIRD_PARTY_NOTICES.md)

## Documentation

- Project overview: [README](README.md)

- Design rationale: [DESIGN](DESIGN.md)

- Project status: [LOG](LOG.md)
- Historical records: [HISTORY](HISTORY.md)
- Version changelog: [CHANGELOG](CHANGELOG.md)

- Third-party notices: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Third-Party Notices

This inventory records distributed component identity and obligations, preserves upstream texts and does not describe OS packages as pinned dependencies. [Pinned hashes](../../config/dependencies.lock.json) cover 15 artifacts.

### Components

| Component | Version or hash | Upstream | License | Usage | Copyright holder | Distribution obligations | Verification date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | 0.71.0 | [frps](https://github.com/fatedier/frp) | Apache-2.0 | Independent server binary. | fatedier/frp contributors | Retain license; official archive has no NOTICE. | 2026-09-27 |
| frpc | 0.71.0 | [frpc](https://github.com/fatedier/frp) | Apache-2.0 | Instance client binary. | fatedier/frp contributors | Retain attribution and full license. | 2026-10-04 |
| Lucky | 2.27.2 | [Lucky](https://github.com/gdy666/lucky) | MIT | Independent management service. | gdy (2022) | Retain attribution and full license. | 2026-09-27 |
| sing-box | 1.13.14 / `25a600db24f7680ad9806ce5427bd0ab8afe1114` | [sing-box](https://github.com/SagerNet/sing-box) | GPL-3.0-or-later | Independent proxy core. | nekohasekai (2022) | Retain source access and upstream naming/affiliation conditions. | 2026-09-27 |
| LibreSpeed | 6.2.1 | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0 | Browser speed-test engine. | LibreSpeed contributors | Retain LGPL/GPL texts, provide corresponding source and replaceable client files. | 2026-09-27 |
| qrcode-generator | js2.0.4 / `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT | Client QR library. | Kazuhiko Arase (2009) | Retain attribution and full license. | 2026-09-27 |
| Inter | Fontsource 5.3.0 | [Inter](https://github.com/fontsource/font-files/tree/main/fonts/google/inter) | OFL-1.1 | Bundled font, 400/600/700. | The Inter Project Authors (2016) | Retain OFL/attribution and reserved font-name conditions. | 2026-09-27 |
| Noto Sans SC | Fontsource 5.3.0 | [Noto Sans SC](https://github.com/fontsource/font-files/tree/main/fonts/google/noto-sans-sc) | OFL-1.1 | Bundled font, 400/700. | Google Inc. | Retain OFL and attribution. | 2026-09-27 |
| Lucide | main, 2026-09-27 | [Lucide](https://github.com/lucide-icons/lucide) | ISC | Bundled SVG icons. | Lucide Icons and Contributors; Cole Bemis | Retain attribution and full license. | 2026-09-27 |
| xterm.js / Fit Addon | 6.0.0 / 0.11.0 | [xterm.js / Fit Addon](https://github.com/xtermjs/xterm.js) | MIT | Terminal rendering and fitting. | The xterm.js authors; SourceLair; Christopher Jeffrey | Retain both original license/attribution texts. | 2026-10-05 |
| iperf3 | 3.22 | [iperf3](https://github.com/esnet/iperf) | BSD-3-Clause | Static build from unchanged source for TCP/UDP tests. | The Regents of the University of California / Lawrence Berkeley National Laboratory | Retain attribution and full license. | 2026-10-04 |
| Tailscale | 1.102.4 | [Tailscale](https://pkgs.tailscale.com/stable/tailscale_1.102.4_amd64.tgz) | BSD-3-Clause | Official static client/daemon archive. | Tailscale Inc & contributors (2020) | Retain LICENSE, PATENTS and original dependency notices/licenses. | 2026-10-04 |
| nftables + 10 libraries | Debian 11 amd64, nftables 0.9.8-3.1+deb11u2 | [nftables + 10 libraries](https://deb.debian.org/debian/) | Per-package copyright: GPL/LGPL/BSD and others. | Private runtime, supplied only in complete offline packages. | Upstream package authors; see original archive notices. | Distribute complete corresponding sources, patches and package notices together. | 2026-10-04 |

Verification dates are the original provenance-check dates; publication on 2026-10-05 rechecked artifact hashes, not every upstream provenance claim. Upstream frp, Lucky, Singbox, LibreSpeed and QR artifacts are unchanged. Inter/Noto versions identify Fontsource packages, not internal font versions. No third-party Python packages, image datasets or model weights are included. Python, systemd, OpenSSL, iptables and similar OS components are not pinned by this lock; their licenses/security updates follow distribution channels.

### License Texts

- [frp](../../third_party/frp/LICENSE)
- [Lucky](../../third_party/lucky/LICENSE)
- [sing-box](../../third_party/sing-box/LICENSE)
- [GPL-3.0](../../LICENSE)
- [LibreSpeed LGPL-3.0](../../src/web/static/licenses/LGPL-3.0.txt)
- [qrcode-generator MIT](../../src/web/static/licenses/MIT.txt)
- [Inter OFL](../../src/web/static/licenses/OFL-Inter.txt)
- [Noto Sans SC OFL](../../src/web/static/licenses/OFL-Noto-Sans-SC.txt)
- [Lucide ISC](../../src/web/static/licenses/Lucide-ISC.txt)
- [xterm.js MIT](../../src/web/static/third_party/xterm/LICENSE-xterm)
- [Fit Addon MIT](../../src/web/static/third_party/xterm/LICENSE-addon-fit)
- [iperf3](../../third_party/iperf3/LICENSE)
- [Tailscale LICENSE](../../third_party/tailscale/LICENSE)
- [Tailscale PATENTS](../../third_party/tailscale/PATENTS)
- [Tailscale dependencies](../../third_party/tailscale/DEPENDENCY_NOTICES.md)
- [Tailscale license manifest](../../third_party/tailscale/license-manifest.json)

Tailscale's 80 dependency licenses, freetype license and 3 NOTICE files total 84 original files in `third_party/tailscale/licenses/`; the manifest pins origins and hashes. The upstream dependency list still calls freetype Unknown; this project supplements the original BSD-style text at a fixed revision without altering that list. The nftables runtime retains each package's `usr/share/doc/<package>/copyright`; package names/hashes are in [component.txt](../../third_party/nft/component.txt).

### Source Code Offer

- sing-box: [v1.13.14 source](https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114), [source archive](https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz).
- LibreSpeed: [v6.2.1 source](https://github.com/librespeed/speedtest/tree/v6.2.1).
- iperf3: [3.22 source archive](https://downloads.es.net/pub/iperf/iperf-3.22.tar.gz), SHA-256 `1c0d0fb02c52626111d6e132db80edfbf27bbaff8bd9245df2a371dcb0b35a92`.
- Tailscale: [v1.102.4 source](https://github.com/tailscale/tailscale/tree/v1.102.4).

The complete Release includes `third_party/nft/nft-runtime-bullseye.tar.gz` and `third_party/nft/nft-sources-bullseye.tar.gz`, pinned to SHA-256 `42eeb9496a173777df2e46d67b32b631e5eb31bbc1a74d2a0fa335f32a46c9eb` and `fce6ca6c5050ff7715c5bd9fedb0160c942e3e5ede7d2702c02f01d920ac6e83`. The source archive supplies 10 upstream source groups, Debian patches and source descriptors corresponding to 11 binary packages; files are pinned in [source-manifest.json](../../third_party/nft/source-manifest.json). The build script downloads and verifies them from Debian; a source checkout alone does not include these two nft archives. Source descriptors/patches restore the corresponding Debian tree with packaging build files. Hosts use the private runtime without replacing system nft.

Unchanged iperf3 source was built on Ubuntu 22.04 x86-64 with `./configure --enable-static-bin --disable-shared --without-sctp && make -j2` and stripped, without SCTP/OpenSSL authentication; static name-resolution compatibility on older hosts still needs acceptance.

### Compliance Review

Publication review on 2026-10-05: hashes for 15 pinned artifacts and 84 Tailscale notices/licenses passed, nft corresponding sources accompanied the runtime and original licenses were unchanged. The [license decision](LOG.md#decisions) records GPL-3.0-only. Distribution analysis:

- sing-box is distributed as a separate executable/process, not statically linked into Python; separation does not waive GPL source/notice obligations. Upstream naming conditions remain, without affiliation or endorsement.
- LibreSpeed JavaScript remains independently replaceable, with LGPL/GPL texts. `speedtest-ui.js` is project glue; Python endpoints implement the protocol independently rather than copying the PHP backend.
- nft repackages unchanged Debian artifacts with original notices and complete corresponding source packages; separate paths do not waive package obligations.
- Tailscale retains original dependency notices, patent grant and supplemental original texts; license identity checks do not prove cross-environment compatibility.

This is a project-file/distribution review without an independent legal interpretation. This author's imported `vps-webserver v0.4.1` code is redistributed from Apache-2.0 under GPL-3.0-only; provenance: [config/upstream-version](../../config/upstream-version). The initial Anytsl-Serve selection explains sing-box provenance; standalone AnyTLS scripts are retired.
