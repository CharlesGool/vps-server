---
name: project-third-party-notices-zh-cn
description: 第三方署名与合规声明
metadata:
  version: "1.0.0"
  lang: "zh-CN"
---

# 第三方声明

本文记录随附和由操作系统提供的第三方组件,源码相关声明及发布审核限制.

## 多语言

[English](../THIRD_PARTY_NOTICES.md) | **简体中文** | [繁體中文(台灣)](../zh-TW/THIRD_PARTY_NOTICES.md) | [繁體中文(香港)](../zh-HK/THIRD_PARTY_NOTICES.md) | [हिन्दी](../hi/THIRD_PARTY_NOTICES.md) | [Español](../es/THIRD_PARTY_NOTICES.md) | [العربية](../ar/THIRD_PARTY_NOTICES.md) | [Français](../fr/THIRD_PARTY_NOTICES.md)

## 文档

- 项目概览:[README](README.md)

- 设计思路:[DESIGN](DESIGN.md)

- 发布历史:[LOG](LOG.md)

- 第三方声明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 第三方声明

下表列出随附组件及由操作系统提供的组件.七个随附构件在 [dependencies.lock.json][local-link-001] 中记录了检出文件的 SHA-256;从仓库根目录运行 `python3 tools/verify_dependencies/verify_dependencies.py`,可离线比较其字节.2026-09-27,仓库中的全部七个文件均与记录的上游发布归档成员或标签文件逐字节一致.随附的许可证文件也与下文核验的上游文件一致.这些检查确认构件身份,不构成法律意见,也不能建立完全可复现的系统依赖闭包.

| 组件/资源 | 版本/散列 | 来源 | 所记录的许可证 | 用途 | 署名/原始许可证路径 | 待审核的发布义务 | 核验日期 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0,依据上游许可证 | 随附的 frps 可执行文件 | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | 保留随附的 Apache-2.0 许可证;官方二进制归档中没有 NOTICE 文件 | 2026-09-27:归档,二进制文件及许可证一致 |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT,依据上游许可证 | 随附的 Lucky 可执行文件 | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | 保留随附的 MIT 版权及许可声明 | 2026-09-27:归档,二进制文件及许可证一致 |
| sing-box | `v1.13.14`;修订号 `25a600db24f7680ad9806ce5427bd0ab8afe1114`;二进制 SHA-256 `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL 第 3 版或更高版本,另附上游命名条件(据声明所述) | 供 anytls 和 proxy 共用的随附可执行文件 | [上游声明][local-link-002];[GPL 全文][local-link-003] | 保留对应源码链接及上游名称/关联条件 | 2026-09-27:归档,二进制文件,许可证及标签修订号一致 |
| LibreSpeed | `v6.2.1` | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0,依据上游许可证 | 随附的浏览器引擎 | [原始 LGPL 文本][local-link-006]和[GPL 文本][local-link-007] | 保留许可证文本并确保上游源码可获得 | 2026-09-27:两个标签文件及许可证一致 |
| qrcode-generator | `js2.0.4`;修订号 `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT,依据上游许可证 | 随附的客户端二维码库 | [原始 MIT 文本][local-link-008] | 保留必要的版权与许可声明 | 2026-09-27:两个标签文件及许可证一致 |
| Inter | `5.3.0` | [Fontsource Inter](https://github.com/fontsource/font-files/blob/main/fonts/google/inter/README.md) | SIL OFL 1.1 | 随附的拉丁界面字体,400/600/700 字重 | [license](../../static/licenses/OFL-Inter.txt) | 保留随附的许可证及版权声明 | 2026-09-27 |
| Noto Sans SC | `5.3.0` | [Fontsource Noto Sans SC](https://github.com/fontsource/font-files/blob/main/fonts/google/noto-sans-sc/README.md) | SIL OFL 1.1 | 随附的 CJK 界面字体,400/700 字重 | [license](../../static/licenses/OFL-Noto-Sans-SC.txt) | 保留随附的许可证及版权声明 | 2026-09-27 |
| Lucide icons | `main` 2026-09-27 | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC | 随附的界面 SVG 图标 | [license](../../static/licenses/Lucide-ISC.txt) | 保留随附的许可证及版权声明 | 2026-09-27 |
| iperf3 | 发行版软件包;未锁定版本 | [ESnet/iperf](https://github.com/esnet/iperf) | 此前记录为 BSD-3-Clause | 作为独立的操作系统安装程序调用;本项目不重新分发 | 未记录版权;操作系统软件包提供原始许可证 | 若以后随附或重新分发,须重新评估 | 未记录;分发前重新核实 |

现有项目记录将本项目的许可证标为 GPL-3.0([LICENSE][local-link-009]),并将重新分发 GPL 许可的 sing-box 可执行文件作为选择该许可证的理由;[决策][local-link-010]保留了其理由及被否决的替代方案.先前记录称 `vps-webserver` 上游采用 Apache-2.0,在本项目中以 GPL-3.0 重新分发.本清单记录了为 v2.0.0 核验的文件与条款;不提供独立的法律意见.

本项目没有第三方 Python 包.`src/web/app.py` 使用标准库,因此没有 Python 包锁.上述随附构件的锁文件没有锁定由操作系统提供的 Python,iperf3 或其他系统包:其版本和安全更新由目标 Debian/Ubuntu 发行版的软件包渠道管理.安装程序不选择精确的包版本或仓库快照;完整可复现的系统依赖闭包仍未解决(见[复现要求][local-link-011]).

---

## sing-box

本仓库以 `third_party/sing-box/sing-box` 路径重新分发 sing-box 可执行文件.2026-09-27,其字节及随附的上游许可证与官方 v1.13.14 发布归档一致.安装路径为 `/usr/local/bin/sing-box-vps-server`.

- 组件:`sing-box`
- 上游项目:https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- 版本:`v1.13.14`
- 源码修订号:`25a600db24f7680ad9806ce5427bd0ab8afe1114`
- 分发构件:`sing-box-1.13.14-linux-amd64.tar.gz`
- 仓库内二进制文件 SHA-256:`68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- 许可证:GNU GPL 第 3 版或任何后续版本,另附上游名称/关联条件;参见 [`third_party/sing-box/LICENSE`][local-link-012]

下载的发布归档 SHA-256 为 `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697`.仓库内的二进制文件和许可证与解压出的对应文件逐字节一致.

### 对应源码

2026-09-27,v1.13.14 标签解析到源码修订号 `25a600db24f7680ad9806ce5427bd0ab8afe1114`.以下上游源码链接与随附的可执行文件一同提供:

- 已打标签的源码树:https://github.com/SagerNet/sing-box/tree/v1.13.14
- 准确的源码修订号:https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- 源码归档:https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

先前项目记录引用的上游 Release 归档为:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

本项目独立于 sing-box 和 SagerNet 的作者,与其没有关联,也未获其背书.

---

## LibreSpeed

浏览器测速使用随附的 LibreSpeed 客户端引擎.2026-09-27,两个随附的 JavaScript 文件及许可证与上游 v6.2.1 标签文件逐字节一致.

- 组件:LibreSpeed 客户端引擎——`static/third_party/librespeed/speedtest.js`,`static/third_party/librespeed/speedtest_worker.js`
- 上游项目:https://github.com/librespeed/speedtest
- 版本:`v6.2.1`
- 许可证:GNU LGPL 第 3 版;全文见 [`static/licenses/LGPL-3.0.txt`][local-link-013]
- 核验:两个文件及原始许可证与 v6.2.1 标签一致;本清单没有记录准确的标签提交.

`static/speedtest-ui.js` 是本项目自己的衔接代码,不属于 LibreSpeed.`src/web/app.py` 中的服务端端点(`/speedtest/garbage`,`/speedtest/empty`,`/speedtest/getip`)重新实现了 LibreSpeed 文档所述的客户端/服务端约定;它们是原创代码,不是上游 PHP 后端的派生代码.

LGPL-3.0 全文已随附,上游源码已提供链接;本清单不提供关于组合使用的独立法律意见.

---

## qrcode-generator

控制台 `/proxy` 页面使用这个随附的客户端库,将分享链接渲染为可扫描的二维码.2026-09-27,两个随附的 JavaScript 文件及原始许可证与上游 js2.0.4 标签文件逐字节一致.

- 组件:`static/third_party/qrcode/qrcode.js`,`static/third_party/qrcode/qrcode-utf8.js`
- 上游项目:https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- 版本:`js2.0.4`
- 源码修订号:`83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- 许可证:MIT;全文见 [`static/licenses/MIT.txt`][local-link-014]
- 核验:两个文件与上游 `js/dist/qrcode.js` 和 `js/dist/qrcode_UTF8.js` 一致;原始 MIT 许可证也一致.

`static/qrcode-render.js` 是本项目自己的衔接代码(查找 `[data-qr-text]` 元素并填入渲染后的 SVG),不属于随附的库.

MIT 版权及许可声明与客户端库一同随附.

---

## iperf3

- 组件:`iperf3`
- 上游项目:https://github.com/esnet/iperf
- 许可证:BSD 3-Clause
- 是否修改:否
- **未重新分发.** `iperf3` 由 `install.sh` 从操作系统软件包仓库安装,通过进程边界作为独立程序调用.本仓库不包含 iperf3 的代码或二进制文件,因此按先前记录,随重新分发而产生的 BSD 署名要求在此并未触发;若分发方式改变,须重新评估.之所以列出,是因为本项目运行时依赖它.

---

## 随附本作者其他项目的代码

不属于第三方,但这些代码并非源自本仓库,其来源对未来更新仍有意义:

- `src/web/app.py`, `static/speedtest-ui.js`,`static/style.css`,`static/visitors.js`,
  `tests/`,`deploy/install.sh`,`deploy/uninstall.sh`,`deploy/systemd/`——来自 `vps-webserver`
  v0.4.1(上游 Apache-2.0,在此重新授权为 GPL-3.0).见 `config/upstream-version`.
- `deploy/anytls/setup-anytls.sh`,`third_party/sing-box/sing-box`,`third_party/sing-box/sing-box.version`——来自
  `Anytsl-Serve` v1.2.0(上游 GPL-3.0).见 `deploy/anytls/.upstream-version`.

---

本项目不包含第三方字体,图标,图片,数据集或模型权重.服务运行时不发起出站请求;唯一可选的出站调用是在安装期间查询公网 IP,失败后只给出警告.

[local-link-001]: ../../config/dependencies.lock.json
[local-link-002]: ../../third_party/sing-box/LICENSE
[local-link-003]: ../../LICENSE
[local-link-004]: #对应源码
[local-link-005]: LOG.md#决策
[local-link-006]: ../../static/licenses/LGPL-3.0.txt
[local-link-007]: ../../LICENSE
[local-link-008]: ../../static/licenses/MIT.txt
[local-link-009]: ../../LICENSE
[local-link-010]: LOG.md#决策
[local-link-011]: DESIGN.md#复现要求
[local-link-012]: ../../third_party/sing-box/LICENSE
[local-link-013]: ../../static/licenses/LGPL-3.0.txt
[local-link-014]: ../../static/licenses/MIT.txt
