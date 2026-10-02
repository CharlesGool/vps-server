---
name: project-readme-zh-cn
description: 项目概览与使用说明
metadata:
  version: "1.0.0"
  lang: "zh-CN"
---

# vps-server

## 多语言

[English](../../README.md) | **简体中文** | [繁體中文(台灣)](../zh-TW/README.md) | [繁體中文(香港)](../zh-HK/README.md) | [हिन्दी](../hi/README.md) | [Español](../es/README.md) | [العربية](../ar/README.md) | [Français](../fr/README.md)

## 文档

- 项目概览:[README](README.md)

- 设计思路:[DESIGN](DESIGN.md)

- 发布历史:[LOG](LOG.md)

- 第三方声明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 简介

这是一套可选择模块的 Debian/Ubuntu VPS 组合包:用于检查 Web 端口可达性的公开页面,用于测速和记录连接的操作员控制台,按需开启的 iperf3 窗口,以及 sing-box 代理节点.v3.0.0 新增受管节点,流量策略,内网 IP 免密访问和明暗外观选项.组合包也包含实验性的 frps 和 Lucky 安装程序.参见[当前状态与验收限制][local-link-001].

## 功能

- **让任何人验证可达性.** 端口 **80** 和
  **443** 上提供刻意保持极简,无需登录的页面.把 IP 交给对方;如果页面能显示,说明对方所在位置能访问你的 Web 端口.页面只报告对方的源 IP,服务器时钟及其到达时使用的端口和协议,不透露其他主机信息.
- **在浏览器中测量吞吐量.** 控制台运行在持久化的随机高位端口,通过 LibreSpeed 引擎进行上传/下载测试.可使用管理员密码,或明确加入名单的私有局域网 IP 访问.登录页始终显示 IP 免密按钮;未获准的访客会被引导用密码登录,再到访问设置中添加内网 IP.安全设置要求最近一次管理员密码验证后才显示 IP 名单或接受修改.名单仅接受单个私有 IPv4 或唯一本地 IPv6 地址,并可单独停用 IP 免密而保留名单.修改密码会使现有会话失效. 普通设置页可直接调整外观和语言;安全设置中的管理员密码验证过期后需重新验证.
- **按需用 iperf3 测量吞吐量和延迟.** 控制台开启限时窗口;`iperf3 -s` 只在窗口期内运行,到期自动关闭.测试者可通过 iperf3 获取带宽;在 Linux 客户端上还可从其 `mean_rtt` 在 `--json` 输出中获取往返时延.该字段来自内核的 `TCP_INFO`;无法读取它的客户端(尤其是 Windows 上 Cygwin 环境中的 iperf3)没有该字段.UDP 模式(`-u`)在所有平台上都提供抖动和丢包数据. 控制台分别显示运行状态和端口;测试窗口关闭时可修改端口,新设置在服务重启后仍有效.
- **记录连接者.** 记录所有端口上的每条入站 TCP 连接,不限于 HTTP;数据从 `/proc/net/tcp[6]` 读取,存入 SQLite,保留最近 1000 条.
- **提供 anytls 代理.** 使用自签名证书的 sing-box,另加 BBR.经过身份验证的 `/proxy` 页面显示节点状态,流量和可编辑的连接设置;有私有局域网地址时,还提供 Clash Meta for Android 一键导入链接和二维码. 订阅 URL 可复制.
- **提供 vmess/vless/trojan/shadowsocks 代理,可选择任意子集.** 另一个 sing-box 进程与 anytls 共用随附的二进制文件.安装 Singbox 不会自动创建节点;控制台可按需新建和删除各协议节点.每个节点都有以 GiB 为单位的流量上限,分开的连接和限制编辑功能,随机重置控件,以及相同的局域网 Clash Meta 导入选项.导入 URL 包含不透明令牌;节点连接设置或名称变化后,旧链接失效.公开端口不提供代理配置. 新建节点可手动填写密码或协议所需的密钥/UUID,留空则随机生成;TLS 节点的 SNI 默认为 `www.bing.com`.节点页面列出主机网卡和 Tailscale 地址. 每个节点还支持分别设置上传和下载的 Mbps 限速.达到 GiB 流量上限后,可选择双向限速 1 Mbps 或停止使用;按自定天数,月数或年数重置周期流量.还可以设置可选有效期,到期后停止使用. 也可复制局域网订阅链接.

全新安装默认只安装 Web 控制台;iperf3,Singbox,FRPS 和 FRPC 可在“设置 → 模块”中按需安装.Lucky 可通过安装参数选择.本预发布标签尚未完成全新主机安装验收.

经过身份验证的 FRPS 页面显示本机服务状态,网卡地址和连接设置;令牌及端口在用户要求显示前保持遮蔽.FRPS 端口和令牌可直接编辑,服务可开启或关闭.独立的 FRPC 页面以卡片列出本机客户端实例,遮蔽目标 IP,并根据已建立的 TCP 套接字显示连接状态.“测试连接”会使用保存的服务器地址,端口和令牌另行执行一次 FRPC 登录.实例页面按需显示 IP 或令牌,编辑前也会列出每条 TCP/UDP 代理的类型,本地 IP,本地端口和远程端口.保存后留在同一实例页面,验证配置文件,失败时恢复原配置.这些 FRP 操作使用已登录会话;修改密码,IP 免密等安全设置操作才要求最近一次管理员密码验证.字段编辑器只处理简单的令牌认证 TCP/UDP 配置,不会修改其无法表示的 FRPC TOML.此控制台不监测其他设备上的 FRPC 实例.模块页面分别检查本机 FRPC 可执行文件和 `frpc@.service` 模板,而不是用是否存在实例配置判断安装状态.缺少其中任一文件时提供“安装”;FRPC 已安装但没有实例时提供“创建实例”链接.安装使用经过校验和验证的 FRPC v0.71.0 发行资源,不会自行建立连接或监听端口.模块日志记录下载和验证结果.离线安装时,先下载 [frpc-0.71.0-linux-amd64](https://github.com/CharlesGool/vps-server/releases/download/v4.0.0/frpc-0.71.0-linux-amd64) (16,593,080 字节;SHA-256:`f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`),放到 `~/apps/vps-server/vendor/frp/frpc`,再选择“安装”.安装任务对下载或手动放入的文件执行相同的摘要校验.卸载时会停止本机 FRPC 实例,在 `data/` 下备份其配置,并保留配置文件供日后重新安装.

**非目标:** 不提供 ACME 或域名(443 刻意使用自签名证书);不提供常驻 iperf3;不提供反向代理或容器;公开页面绝不暴露主机名,内核,运行时间,服务列表或代理参数.本项目不取代 `vps-webserver` 或 `Anytsl-Serve`——二者继续独立维护,其代码在此以随附副本形式使用,而非并入项目.

## 要求

- 操作系统:Debian 11+ 或 Ubuntu 20.04+,systemd,以 root 身份运行
- 运行时:Python 3.9+(发行版自带的 `python3` 即可,无需安装 Python 依赖)
- 架构:web 与 iperf3 模块支持任意架构;anytls,proxy,frps 和 Lucky **仅支持 x86-64**,因为随附的可执行文件面向 amd64
- web 模块使用默认公开端口时,80 和 443 **必须**保持空闲;若已被 nginx,Apache,Caddy 或 `vps-webserver` 占用,安装程序将拒绝安装,而不会争抢端口
- 外部服务:运行时不需要.安装需要发行版软件包镜像;节点摘要只使用网卡地址和可用的 Tailscale 地址,不进行出站公网 IP 查询.
- 最低要求:上述系统,运行时,架构及空闲端口.未记录其他推荐硬件配置;约 150 MB 的 VPS 磁盘空间可容纳随附二进制文件.

## 安装

`v4.1.0-test.1` 是供手动验证全新安装的预发布版;尚未在全新主机上完成安装验收.在 Debian 或 Ubuntu 主机上运行:

```bash
git clone --branch v4.1.0-test.1 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
sudo bash deploy/install.sh
```

全新安装默认只安装 Web 控制台,随机选择并保存管理端口,生成管理员密码.安装成功后,终端会打印访问地址和密码;其他模块在控制台的“设置 → 模块”中安装.默认目录为 root 账户的 `~/apps/vps-server`,也可通过 `PREFIX` 指定.

## 指南

### 快速开始

v2.0.0 将 Web 实现放在 `src/web/app.py`,安装程序从 `deploy/` 运行.随附的二进制文件及许可证声明位于 `third_party/`;发布元数据位于 `config/`.已安装文件仍平铺在 `$PREFIX` 下;检出目录的布局变化不会迁移运行数据.新路径通过了本地测试,但本版本尚未在真实主机上完成验收.

```bash
sudo bash deploy/install.sh                  # 全新安装默认只安装 Web
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # 按需选择额外模块
systemctl status vps-server-web              # 检查服务是否运行
bash deploy/anytls/setup-anytls.sh status           # 若已安装该模块,查看 anytls 节点详情
bash deploy/proxy/setup-proxy.sh status             # 若已安装该模块,查看代理节点详情
```

启用相应模块或公网端口后,再从另一台机器验证:

```bash
curl -sS  http://<ip>/                     # 检查明文 HTTP 的可达性
curl -sSk https://<ip>/                    # 检查 TLS 的可达性(自签名证书)
iperf3 -c <ip> -p 5201 --json              # 仅在测试窗口开启时使用
```

### 验证运行

运行 `bash deploy/install.sh` 后应看到列出每个已安装模块及其端口的摘要.接着:

- `systemctl status vps-server-web` 显示 `active (running)`.
- 全新安装时,HTTP 和 HTTPS 页面默认关闭.在首页分别开启后,再从另一台机器访问 `http://<ip>/` 或 `https://<ip>/`.
- 使用终端打印的地址和密码登录控制台;只有安装 iperf3 模块后才会出现其控件.
- 安装 iperf3 模块并开启测试服务后,可在另一台机器运行 `iperf3 -c <ip> -p 5201 --json`;窗口关闭后该命令无法连接.
- 若安装了 anytls:`systemctl status vps-server-anytls` 显示 `active (running)`.
- 若安装了 proxy:`systemctl status vps-server-proxy` 显示 `active (running)`.

### 配置

每个变量都有可用的默认值;`.env` 可选.关键变量如下:

| 变量 | 含义 | 默认值 | 是否必需 |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | 公开可达性页面的明文端口 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公开可达性页面的 TLS 端口 | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 是否提供公开页面 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台端口;`0` 表示生成并记住端口 | `0` | 否 |
| `VPSSRV_AUTH` | 控制台是否要求密码 | `1` | 否 |
| `VPSSRV_IPERF_PORT` | 已开启的 iperf3 窗口监听的端口 | `5201` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台不可超过的时长上限 | `60` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | 否 |

完整说明:[配置参考][local-link-002].

## 升级

升级时使用当前检出版本,并沿用原安装目录和模块选择重新运行安装程序.在确认升级后的服务和控制台正常前,保留持久数据的备份.

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

[local-link-001]: LOG.md#当前状态与验收限制
[local-link-002]: DESIGN.md#配置参考
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#决策
[local-link-006]: THIRD_PARTY_NOTICES.md
