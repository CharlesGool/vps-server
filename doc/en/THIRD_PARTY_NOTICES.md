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
| frps | 0.72.0 | [frps](https://github.com/fatedier/frp) | Apache-2.0 | Independent server binary. | fatedier/frp contributors | Retain license; official archive has no NOTICE. | 2026-11-06 |
| frpc | 0.72.0 | [frpc](https://github.com/fatedier/frp) | Apache-2.0 | Instance client binary. | fatedier/frp contributors | Retain attribution and full license. | 2026-11-06 |
| Lucky | 2.27.2 | [Lucky](https://github.com/gdy666/lucky) | MIT | Independent management service. | gdy (2022) | Retain attribution and full license. | 2026-09-27 |
| sing-box | 1.13.21 / `628cb31ffa79cffffd34c2f9cde6cae044e4fc12` | [sing-box](https://github.com/SagerNet/sing-box) | GPL-3.0-or-later | Independent proxy core. | nekohasekai (2022) | Retain source access and upstream naming/affiliation conditions. | 2026-11-06 |
| LibreSpeed | 6.2.1 | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0 | Browser speed-test engine. | LibreSpeed contributors | Retain LGPL/GPL texts, provide corresponding source and replaceable client files. | 2026-09-27 |
| qrcode-generator | js2.0.4 / `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT | Client QR library. | Kazuhiko Arase (2009) | Retain attribution and full license. | 2026-09-27 |
| Inter | Fontsource 5.3.0 | [Inter](https://github.com/fontsource/font-files/tree/main/fonts/google/inter) | OFL-1.1 | Bundled font, 400/600/700. | The Inter Project Authors (2016) | Retain OFL/attribution and reserved font-name conditions. | 2026-09-27 |
| Noto Sans SC | Fontsource 5.3.0 | [Noto Sans SC](https://github.com/fontsource/font-files/tree/main/fonts/google/noto-sans-sc) | OFL-1.1 | Bundled font, 400/700. | Google Inc. | Retain OFL and attribution. | 2026-09-27 |
| Lucide | main, 2026-09-27; additional icons from lucide 1.52.0 | [Lucide](https://github.com/lucide-icons/lucide) | ISC | Bundled SVG icons. | Lucide Icons and Contributors; Cole Bemis | Retain attribution and full license. | 2026-10-07 |
| xterm.js / Fit Addon | 6.0.0 / 0.11.0 | [xterm.js / Fit Addon](https://github.com/xtermjs/xterm.js) | MIT | Terminal rendering and fitting. | The xterm.js authors; SourceLair; Christopher Jeffrey | Retain both original license/attribution texts. | 2026-10-05 |
| iperf3 | 3.22 | [iperf3](https://github.com/esnet/iperf) | BSD-3-Clause | Static build from unchanged source for TCP/UDP tests. | The Regents of the University of California / Lawrence Berkeley National Laboratory | Retain attribution and full license. | 2026-10-04 |
| OpenSSL | 3.5.9 (LTS) | [OpenSSL](https://github.com/openssl/openssl) | Apache-2.0 | Static build of the command-line tool from unchanged source; only signs console client certificates. | The OpenSSL Project Authors | Retain full license. | 2026-11-08 |
| Tailscale | 1.104.5 | [Tailscale](https://pkgs.tailscale.com/stable/tailscale_1.104.5_amd64.tgz) | BSD-3-Clause | Official static client/daemon archive. | Tailscale Inc & contributors (2020) | Retain LICENSE, PATENTS and original dependency notices/licenses. | 2026-11-06 |
| nftables, iptables, iproute2 + 29 libraries | Debian 13 amd64, nftables 1.1.3-1, iptables 1.8.11-2, iproute2 6.15.0-1, glibc 2.41-12+deb13u4, pcre2 10.46-1~deb13u3 (trixie-security) | [nftables, iptables, iproute2 + 29 libraries](https://snapshot.debian.org/archive/debian/20261020T000000Z/) | Per-package copyright: GPL/LGPL/BSD and others. | Private runtime with its own loader and glibc, supplied only in complete offline packages. | Upstream package authors; see original archive notices. | Distribute complete corresponding sources, patches and package notices together. | 2026-11-06 |

Verification dates are the original provenance-check dates; publication on 2026-10-05 rechecked artifact hashes, not every upstream provenance claim. Upstream frp, Lucky, Singbox, LibreSpeed and QR artifacts are unchanged. Inter/Noto versions identify Fontsource packages, not internal font versions. No third-party Python packages, image datasets or model weights are included. Python, systemd, the host OpenSSL library (used by Python TLS), iptables and similar OS components are not pinned by this lock (the installer checks minimum versions); their licenses/security updates follow distribution channels.

The Vue frontend adds Vue 3.5.43, vue-i18n 11.4.18, Reka UI 2.11.0, Tailwind CSS 4.3.3, clsx 2.1.1 and tailwind-merge 3.7.0 (MIT), @lucide/vue 1.52.0 (ISC), and class-variance-authority 0.7.1 (Apache-2.0). Exact identities and download sources are in the [npm lock file](../../web/package-lock.json). They provide shared components and compiled browser resources; copyright ownership follows upstream texts. Verified on 2026-10-06. Distribution retains original copyrights and license texts. The build copies them and a version/source-download manifest to `web/dist/licenses/`, retained by installation and offline packages. Build-tool notices are included as well; this does not imply those tools run on the VPS.

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
- [OpenSSL](../../third_party/openssl/LICENSE.txt)
- [Tailscale LICENSE](../../third_party/tailscale/LICENSE)
- [Tailscale PATENTS](../../third_party/tailscale/PATENTS)
- [Tailscale dependencies](../../third_party/tailscale/DEPENDENCY_NOTICES.md)
- [Tailscale license manifest](../../third_party/tailscale/license-manifest.json)

Tailscale's 79 dependency licenses, freetype license and 3 NOTICE files total 83 original files in `third_party/tailscale/licenses/`; the manifest pins origins and hashes. The upstream dependency list still calls freetype Unknown; this project supplements the original BSD-style text at a fixed revision without altering that list. The nftables runtime retains each package's `usr/share/doc/<package>/copyright`; package names/hashes are in [component.txt](../../third_party/nft/component.txt).

### Source Code Offer

- sing-box: [v1.13.21 source](https://github.com/SagerNet/sing-box/tree/628cb31ffa79cffffd34c2f9cde6cae044e4fc12), [source archive](https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.21.tar.gz).
- LibreSpeed: [v6.2.1 source](https://github.com/librespeed/speedtest/tree/v6.2.1).
- iperf3: [3.22 source archive](https://downloads.es.net/pub/iperf/iperf-3.22.tar.gz), SHA-256 `1c0d0fb02c52626111d6e132db80edfbf27bbaff8bd9245df2a371dcb0b35a92`.
- OpenSSL: [3.5.9 source archive](https://github.com/openssl/openssl/releases/download/openssl-3.5.9/openssl-3.5.9.tar.gz), SHA-256 `603f5602e2eef00d77fbd429d34dcd5822bb301757a1bc9cdb24c670f1eb859a`.
- Tailscale: [v1.104.5 source](https://github.com/tailscale/tailscale/tree/v1.104.5).

The complete Release includes `third_party/nft/nft-runtime-trixie.tar.gz` and `third_party/nft/nft-sources-trixie.tar.gz`, pinned to SHA-256 `fdfe2657a925c4bda0f8c7c9538180030b3fcae74ee8c457072f8b422938ec68` and `cd6bd6335adb81e11fa5ad66792827c36531e85b528eee309016a48f96d6d8a3`. The source archive supplies 25 upstream source groups, Debian patches and source descriptors corresponding to 32 binary packages; files are pinned in [source-manifest.json](../../third_party/nft/source-manifest.json). The build script downloads and verifies them from Debian; a source checkout alone does not include these two nft archives. Source descriptors/patches restore the corresponding Debian tree with packaging build files. Hosts prefer a working system nft/iptables and use the private runtime only otherwise, without replacing system commands.

Unchanged iperf3 source was built on Ubuntu 22.04 x86-64 with `./configure --enable-static-bin --disable-shared --without-sctp && make -j2` and stripped, without SCTP/OpenSSL authentication; static name-resolution compatibility on older hosts still needs acceptance.

Unchanged OpenSSL source was built on Ubuntu 22.04 x86-64 with `./Configure linux-x86_64 no-shared no-module no-dso no-engine no-tests no-docs -static -O2 && make build_programs` and stripped; build options are in [component.txt](../../third_party/openssl/component.txt).

### Compliance Review

Publication review on 2026-10-05: hashes for 15 pinned artifacts and 84 Tailscale notices/licenses passed, nft corresponding sources accompanied the runtime and original licenses were unchanged. The [license decision](LOG.md#decisions) records GPL-3.0-only. Distribution analysis:

- sing-box is distributed as a separate executable/process, not statically linked into Python; separation does not waive GPL source/notice obligations. Upstream naming conditions remain, without affiliation or endorsement.
- LibreSpeed JavaScript remains independently replaceable, with LGPL/GPL texts. `speedtest-ui.js` is project glue; Python endpoints implement the protocol independently rather than copying the PHP backend.
- nft repackages unchanged Debian artifacts with original notices and complete corresponding source packages; separate paths do not waive package obligations.
- Tailscale retains original dependency notices, patent grant and supplemental original texts; license identity checks do not prove cross-environment compatibility.

This is a project-file/distribution review without an independent legal interpretation. This author's imported `vps-webserver v0.4.1` code is redistributed from Apache-2.0 under GPL-3.0-only; provenance: [config/upstream-version](../../config/upstream-version). The initial Anytsl-Serve selection explains sing-box provenance; standalone AnyTLS scripts are retired.
