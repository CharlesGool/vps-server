---
name: project-readme
description: 项目概览与使用说明
metadata:
  version: "1.0.0"
  lang: "zh-CN"
---

# vps-server

## 多语言

**简体中文** | [English](doc/en/README.md) | [繁體中文(台灣)](doc/zh-TW/README.md) | [繁體中文(香港)](doc/zh-HK/README.md) | [हिन्दी](doc/hi/README.md) | [Español](doc/es/README.md) | [العربية](doc/ar/README.md) | [Français](doc/fr/README.md)

## 文档

- 项目概览:[README](README.md)

- 设计思路:[DESIGN](doc/DESIGN.md)

- 项目状态: [LOG](doc/LOG.md)
- 历史记录: [HISTORY](doc/HISTORY.md)
- 变更日志: [CHANGELOG](doc/CHANGELOG.md)
- 提交历史: [COMMITS](doc/COMMITS.md)

- 第三方声明:[THIRD_PARTY_NOTICES](doc/THIRD_PARTY_NOTICES.md)

## 简介

这是一套可选择模块的 Debian/Ubuntu VPS 组合包:用于检查 Web 端口可达性的公开页面,用于测速和记录连接的操作员控制台,按需开启的 iperf3 窗口,以及 sing-box 代理节点.v5.0.0 包含受管节点,流量策略,内网 IP 免密访问,分开的 HTTP/HTTPS 开关,FRPS/本机 FRPC 管理,Lucky 安装入口和直接运行的安装程序.版本范围与检查结果见[变更日志][local-link-001].

## 功能

- **让任何人验证可达性.** 端口 **80** 和
  **443** 上提供刻意保持极简,无需登录的页面.把 IP 交给对方;如果页面能显示,说明对方所在位置能访问你的 Web 端口.页面只报告对方的源 IP,服务器时钟及其到达时使用的端口和协议,不透露其他主机信息.
- **在浏览器中测量吞吐量.** 控制台运行在持久化的随机高位端口,通过 LibreSpeed 引擎进行上传/下载测试.可使用管理员密码,或明确加入名单的私有局域网 IP 访问.登录页始终显示 IP 免密按钮;未获准的访客会被引导用密码登录,再到访问设置中添加内网 IP.安全设置要求最近一次管理员密码验证后才显示 IP 名单或接受修改.名单仅接受单个私有 IPv4 或唯一本地 IPv6 地址,并可单独停用 IP 免密而保留名单.修改密码会使现有会话失效. 普通设置页可直接调整外观和语言;安全设置中的管理员密码验证过期后需重新验证.
- **按需用 iperf3 测量吞吐量和延迟.** 控制台开启限时窗口;`iperf3 -s` 只在窗口期内运行,到期自动关闭.测试者可通过 iperf3 获取带宽;在 Linux 客户端上还可从其 `mean_rtt` 在 `--json` 输出中获取往返时延.该字段来自内核的 `TCP_INFO`;无法读取它的客户端(尤其是 Windows 上 Cygwin 环境中的 iperf3)没有该字段.UDP 模式(`-u`)在所有平台上都提供抖动和丢包数据. 控制台分别显示运行状态和端口;测试窗口关闭时可修改端口,新设置在服务重启后仍有效.
- **记录连接者.** 记录所有端口上的每条入站 TCP 连接,不限于 HTTP;数据从 `/proc/net/tcp[6]` 读取,存入 SQLite,保留最近 1000 条.
- **提供 anytls 代理.** 使用自签名证书的 sing-box,另加 BBR.经过身份验证的 `/proxy` 页面显示节点状态,流量和可编辑的连接设置;有私有局域网地址时,还提供 Clash Meta for Android 一键导入链接和二维码. 订阅 URL 可复制.
- **提供 vmess/vless/trojan/shadowsocks 代理,可选择任意子集.** 另一个 sing-box 进程与 anytls 共用随附的二进制文件.每种已安装协议最初有一个编号节点;控制台可为任意已安装协议新建更多节点,也可单独删除节点.每个节点都有以 GiB 为单位的流量上限,分开的连接和限制编辑功能,随机重置控件,以及相同的局域网 Clash Meta 导入选项.导入 URL 包含不透明令牌;节点连接设置或名称变化后,旧链接失效.公开端口不提供代理配置. 新建节点可手动填写密码或协议所需的密钥/UUID,留空则随机生成;TLS 节点的 SNI 默认为 `www.bing.com`.节点页面列出主机网卡和 Tailscale 地址. 每个节点还支持分别设置上传和下载的 Mbps 限速.达到 GiB 流量上限后,可选择双向限速 1 Mbps 或停止使用;按自定天数,月数或年数重置周期流量.还可以设置可选有效期,到期后停止使用. 也可复制局域网订阅链接.

首次安装默认只安装 Web 控制台.`VPSSRV_MODULES` 可选择 web,iperf3,anytls,proxy,frps 和 Lucky; 可选模块也可在控制台中安装.FRPC 作为单独的本机客户端功能安装.

经过身份验证的 FRPS 页面显示本机服务状态,网卡地址和连接设置;令牌及端口在用户要求显示前保持遮蔽.FRPS 端口和令牌可直接编辑,服务可开启或关闭.独立的 FRPC 页面以卡片列出本机客户端实例,遮蔽目标 IP,并根据已建立的 TCP 套接字显示连接状态.“测试连接”会使用保存的服务器地址,端口和令牌另行执行一次 FRPC 登录.实例页面按需显示 IP 或令牌,编辑前也会列出每条 TCP/UDP 代理的类型,本地 IP,本地端口和远程端口.保存后留在同一实例页面,验证配置文件,失败时恢复原配置.这些 FRP 操作使用已登录会话;修改密码,IP 免密等安全设置操作才要求最近一次管理员密码验证.字段编辑器只处理简单的令牌认证 TCP/UDP 配置,不会修改其无法表示的 FRPC TOML.此控制台不监测其他设备上的 FRPC 实例.模块页面分别检查本机 FRPC 可执行文件和 `frpc@.service` 模板,而不是用是否存在实例配置判断安装状态.缺少其中任一文件时提供“安装”.安装使用经过校验和验证的 FRPC v0.71.0 发行资源,不会自行建立连接或监听端口.模块日志记录安装和校验结果.FRPC 与 FRPS v0.71.0 二进制文件都随仓库提供;FRPC 模块安装优先读取本地 `vendor/frp/frpc`,并可从安装程序保留的源码包读取随附副本,无需访问 GitHub.两者的来源和 SHA-256 见[第三方声明](doc/THIRD_PARTY_NOTICES.md).卸载时会停止本机 FRPC 实例,在 `data/` 下备份其配置,并保留配置文件供日后重新安装.

**非目标:** 不提供 ACME 或域名(443 刻意使用自签名证书);不提供常驻 iperf3;不提供反向代理或容器;公开页面绝不暴露主机名,内核,运行时间,服务列表或代理参数.本项目不取代 `vps-webserver` 或 `Anytsl-Serve`——二者继续独立维护,其代码在此以随附副本形式使用,而非并入项目.

## 要求

- 操作系统:Debian 11+ 或 Ubuntu 20.04+,systemd,以 root 身份运行
- 运行时:Python 3.9+(发行版自带的 `python3` 即可,无需安装 Python 依赖)
- 架构:整个项目仅支持 x86-64 Linux;安装程序在写入系统状态前拒绝其他平台
- web 模块使用默认公开端口时,80 和 443 **必须**保持空闲;若已被 nginx,Apache,Caddy 或 `vps-webserver` 占用,安装程序将拒绝安装,而不会争抢端口
- 外部服务:运行时不需要.FRPS,FRPC 和 iperf3 的安装使用随附构件;其他缺失的系统包仍可能需要发行版软件包镜像;节点摘要只使用网卡地址和可用的 Tailscale 地址,不进行出站公网 IP 查询.
- 最低要求:上述系统,运行时,架构及空闲端口.未记录其他推荐硬件配置;约 180 MB 的 VPS 磁盘空间可容纳随附二进制文件.

## 安装

### 快速安装

以 root 身份运行;默认仅安装 Web 控制台,并在终端打印随机管理端口和密码.以下标签命令安装已发布的 v5.0.0;本次离线二进制与精简改动仍只在当前开发源码中,尚未发布为该标签.

```bash
git clone --branch v5.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

### 常规安装

```bash
git clone --branch v5.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env  # 可选: 按注释设置覆盖值
bash deploy/install.sh
```

`PREFIX` 默认是 `/root/apps/vps-server`.首次安装无需浏览器设置向导.可用 `VPSSRV_MODULES=web,iperf3,anytls,proxy,frps,lucky` 明确选择服务端模块;省略时只安装 Web.安装后在 Settings → Modules 安装或移除可选模块.HTTP 和 HTTPS 公开页面分别从 Home 启用;管理控制台使用独立端口.FRPC 需在需要本机客户端时单独安装;安装直接使用仓库随附的二进制文件.

## 指南

### 快速开始

Web 实现位于 `src/web/`,静态资源位于 `src/web/static/`,安装程序位于 `deploy/`.FRPC,FRPS,iperf3 等随附二进制文件及许可证记录位于 `third_party/`;发布元数据位于 `config/`.安装目录仍采用既有平铺布局;更新源码布局不会迁移该目录中的运行数据.

源码不附带自动测试套件.改动后应按实际启用的模块手动验证安装,控制台和服务行为.当前源码的离线构件尚未进入上面的 v5.0.0 标签;使用该标签安装时,行为仍以对应版本的文档为准.

```bash
bash deploy/install.sh                       # 首次仅安装 Web 控制台
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # 明确选择 Web 与 iperf3
systemctl status vps-server-web              # 检查服务是否运行
bash deploy/anytls/setup-anytls.sh status           # 若已安装该模块,查看 anytls 节点详情
bash deploy/proxy/setup-proxy.sh status             # 若已安装该模块,查看代理节点详情
```

然后在另一台机器上运行:

```bash
curl -sS  http://<ip>/                     # 检查明文 HTTP 的可达性
curl -sSk https://<ip>/                    # 检查 TLS 的可达性(自签名证书)
iperf3 -c <ip> -p 5201 --json              # 仅在测试窗口开启时使用
```

### 验证运行

运行 `bash deploy/install.sh` 后核对终端打印的管理地址,密码和模块摘要.公开端口默认关闭;在控制台启用后再从另一台机器检查:

- `systemctl status vps-server-web` 显示 `active (running)`.
- 从**另一台机器**打开 `http://<ip>/`,显示标题为“Reachable”的页面及你自己的公网 IP.接受证书警告后打开 `https://<ip>/`,会看到相同页面,协议行显示 HTTPS.
- 登录 `http://<ip>:<console port>/`,仪表盘显示 iperf3 控件,窗口处于关闭状态.
- 开启五分钟窗口后,在另一台机器运行 `iperf3 -c <ip> -p 5201 --json`,会得到吞吐量数值且包含 `mean_rtt`.五分钟后相同命令无法连接——这表示窗口自动关闭,并非故障.
- 若安装了 anytls:`systemctl status vps-server-anytls` 显示 `active (running)`.
- 若安装了 proxy:`systemctl status vps-server-proxy` 显示 `active (running)`.

### 配置

每个变量都有可用的默认值;`.env` 可选.关键变量如下:

| 变量 | 含义 | 默认值 | 是否必需 |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | 公开可达性页面的明文端口 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公开可达性页面的 TLS 端口 | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 首次安装是否提供公开页面;安装后 HTTP/HTTPS 可分别在 Home 开关 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台端口;`0` 表示生成并记住端口 | `0` | 否 |
| `VPSSRV_AUTH` | 控制台是否要求密码 | `1` | 否 |
| `VPSSRV_IPERF_PORT` | 已开启的 iperf3 窗口监听的端口 | `5201` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台不可超过的时长上限 | `60` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | 否 |

完整说明:[配置参考][local-link-002].

## 升级

升级时使用当前检出版本,并沿用原安装目录和模块选择重新运行安装程序.已安装代理的旧配置由安装程序导入受管节点清单;导入失败时须检查配置和服务日志,控制台不会回退到旧编辑入口.在确认升级后的服务和控制台正常前,保留持久数据的备份.

## 卸载

以 root 身份从安装程序的检出目录运行卸载脚本,使用与安装时相同的 `PREFIX` 和 `SERVICE_NAME`(安装摘要会打印准确的卸载命令).要移除已安装的模块及 unit,**同时
保留** `$PREFIX` 中的数据供以后重装:

```bash
KEEP_DATA=1 bash deploy/uninstall.sh
```

要移除模块并**删除数据**(包括 `$PREFIX` 中的访客日志,控制台密码,已保存端口及证书):

```bash
bash deploy/uninstall.sh
```

两种模式都会在已安装时移除 anytls/proxy 服务及其各自的模块配置.`KEEP_DATA=1` 保留 `$PREFIX`,不保留这些模块配置.

## 致谢

浏览器测速使用 [LibreSpeed](https://github.com/librespeed/speedtest) ;二维码渲染使用
[qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) ;随附的代理核心为
[sing-box](https://github.com/SagerNet/sing-box). 实验性模块随附
[frp](https://github.com/fatedier/frp) 和
[Lucky](https://github.com/gdy666/lucky). 组件清单和原始许可证路径见[第三方声明][local-link-003].

## 许可证

项目许可证:GPL-3.0(SPDX:`GPL-3.0-only`);请阅读完整的 [LICENSE][local-link-004].历史组合理由见[决策][local-link-005].随附组件,其原始许可证,已核验的构件来源及剩余法律审查限制见 [THIRD_PARTY_NOTICES.md][local-link-006].

本项目与 sing-box/SagerNet 或 LibreSpeed 无关联,亦未获其背书.

[local-link-001]: doc/CHANGELOG.md
[local-link-002]: doc/DESIGN.md#配置参考
[local-link-003]: doc/THIRD_PARTY_NOTICES.md
[local-link-004]: LICENSE
[local-link-005]: doc/LOG.md#决策
[local-link-006]: doc/THIRD_PARTY_NOTICES.md
