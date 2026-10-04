---
name: project-readme
description: 项目概览与使用说明
metadata:
  version: "1.0.0"
  lang: "zh-CN"
---

# vps-server

## 多语言

**简体中文** | [English](doc/en/README.md) | [Español](doc/es/README.md)

## 文档

- 项目概览:[README](README.md)

- 设计思路:[DESIGN](doc/DESIGN.md)

- 项目状态: [LOG](doc/LOG.md)
- 历史记录: [HISTORY](doc/HISTORY.md)
- 变更日志: [CHANGELOG](doc/CHANGELOG.md)

- 第三方声明:[THIRD_PARTY_NOTICES](doc/THIRD_PARTY_NOTICES.md)

## 简介

vps-server 为 Debian/Ubuntu VPS 提供 Web 端口可达性页面,测速与连接日志控制台,并可安装代理,FRP,Lucky 和 Tailscale 模块.当前分支准备 v6.0.0 测试候选;正式版本仍是 v5.1.0.进度见[项目状态](doc/LOG.md).

## 功能

- **公开可达性页面:** 在启用后通过 80 和 443 端口显示访问者 IP,服务器时间及连接端口和协议;443 使用自签名证书.页面无需登录,不显示主机配置.
- **私有控制台:** 在单独的持久化端口提供 LibreSpeed 上传/下载测速和最近 1000 条入站 TCP 连接记录.管理员密码或获准的私有 IP 可用于登录.
- **iperf3:** 从控制台开启限时窗口,到期自动关闭.Linux 客户端的 `--json` 输出可提供 `mean_rtt`;无法读取 `TCP_INFO` 的客户端不会显示该字段.UDP 测试可查看抖动和丢包.
- **代理节点:** 一个 sing-box 服务承载 AnyTLS,VMess,VLESS,Trojan 和 Shadowsocks.控制台管理节点连接,流量上限,速率限制,周期重置和有效期;局域网可导入 Clash Meta 配置.
- **FRP:** 控制台管理本机 FRPS 的端口,令牌和服务状态,以及本机 FRPC 实例和简单的令牌认证 TCP/UDP 代理.编辑时验证配置,失败则恢复;不监测其他设备上的客户端.FRPC 安装使用仓库随附资源.
- **Lucky:** 当前版本可与其他模块一同安装或卸载;控制台只显示管理地址和运行状态,并提供原生管理页入口.Lucky 自身更改管理端口后,控制台定期刷新地址和 `PORTS.md` 登记.完整功能复刻留待后续版本.
- **Tailscale:** 可安装或卸载随离线包提供的 Linux 客户端;控制台显示状态,连通性,设备和服务日志,可一次保存多项 DNS,路由,出口节点,防护模式,SSH 等 Linux 设置.设备 IPv4 和 IPv6 分别按需显示或复制.加入 Tailnet 仍需能访问所选控制服务器.
- **终端:** 首页入口提供浏览器内 root 终端.仅管理员密码会话在短期验证有效时可连接;断开或离开页面会结束对应 PTY 进程.终端渲染资源随离线包提供.

首次安装仅启用 Web 控制台;其他模块按需安装.功能边界,登录规则及 FRP 编辑限制见[设计文档](doc/DESIGN.md).

## 要求

- 操作系统:Debian 11+ 或 Ubuntu 20.04+,systemd,以 root 身份运行
- 运行时:Python 3.9+(发行版自带的 `python3` 即可,无需安装 Python 依赖)
- 架构:整个项目仅支持 x86-64 Linux;安装程序在写入系统状态前拒绝其他平台
- web 模块使用默认公开端口时,80 和 443 **必须**保持空闲;若已被 nginx,Apache,Caddy 或 `vps-webserver` 占用,安装程序将拒绝安装,而不会争抢端口
- 其他依赖:目标机须有系统自带的 Bash,systemd,Python 和常用基础工具.完整离线包随附 FRP,Lucky,Tailscale,sing-box,iperf3 与私有 nftables 运行时;目标机无需 Git 或软件包镜像.控制服务器认证,服务更新和跨设备连接本身仍需要网络.
- 最低要求:上述系统,运行时和架构.若启用公开页面,其端口须空闲;完整离线包,解压目录和已安装程序合计建议预留至少 1 GiB 磁盘空间.

## 安装

### 快速安装

以 root 身份在目标机运行;默认仅安装 Web 控制台,首次交互安装会先显示 1/2/3 语言选项,再打印随机管理端口和密码.无人值守安装可用 `VPSSRV_DEFAULT_LANG=en|zh_cn|es` 指定语言.正式 v6.0.0 尚未发布;以下源码命令只用于此测试分支,完整离线模块请使用下方的压缩包流程.

```bash
git clone --branch release/v6.0.0-test.1 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

### 常规安装

```bash
git clone --branch release/v6.0.0-test.1 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env  # 可选: 按注释设置覆盖值
bash deploy/install.sh
```

`PREFIX` 默认是 `/root/apps/vps-server`,只存放可替换的程序文件.密码,控制台端口,证书,运行数据,安装记录和 `.env` 默认保存在 `/var/lib/vps-server`;首次安装可在命令环境中设置 `VPSSRV_STATE_DIR` 改用其他外部目录.可用 `VPSSRV_MODULES=web,iperf3,proxy,frps,lucky,tailscale` 明确选择服务端模块;省略时只安装 Web.AnyTLS 是 `proxy` 中的协议,没有独立模块或服务.安装后在 Settings → Modules 安装或移除可选模块.HTTP 和 HTTPS 公开页面分别从 Home 启用;管理控制台使用独立端口.FRPC 需在需要本机客户端时单独安装.

### 离线安装包

v6.0.0 测试包将包含完整源码和已校验的 Tailscale,nftables 等离线资源;生成及目标机安装均不要求目标机具备 Git.测试包发布后先核对提供的 SHA-256,再将包解压到独立目录,不要直接覆盖已安装的 `$PREFIX`.当前测试包尚未发布,以下命令中的 `<测试包>` 须替换为实际文件名:

```bash
mkdir -p /root/vps-server-v6-test
tar -xzf /root/<测试包>.tar.gz -C /root/vps-server-v6-test --strip-components=1
cd /root/vps-server-v6-test
bash deploy/install.sh
```

有网络的构建机可从**干净且已提交**的工作树制作测试包;目标机只接收最后的 `.tar.gz`.构建机需要 Python 3,Git,`dpkg-deb` 和 GNU tar,资源获取脚本会校验固定摘要.包内同时提供 nftables 运行文件,相应源码及 Tailscale 归档:

```bash
python3 tools/build_offline/fetch_assets.py --output-dir .local/offline-assets
python3 tools/build_offline/build_offline.py \
  --tailscale-archive .local/offline-assets/tailscale_1.102.4_amd64.tgz \
  --nft-runtime .local/offline-assets/nft-runtime-bullseye.tar.gz \
  --nft-sources .local/offline-assets/nft-sources-bullseye.tar.gz \
  --version "test-$(git rev-parse --short=7 HEAD)" \
  --output .local/vps-server-test.tar.gz
```


## 指南

安装摘要会显示控制台地址,管理员密码和已安装模块.公开页面默认关闭;在控制台 Home 启用后,从另一台机器访问 `http://<ip>/` 和 `https://<ip>/` 验证 80/443 可达性.HTTPS 使用自签名证书.用 `systemctl status vps-server-web` 检查服务,再登录控制台管理模块,代理节点和 FRP.

需要 iperf3 时,先在控制台开启限时窗口,然后在另一台机器运行 `iperf3 -c <ip> -p 5201 --json`.窗口结束后端口停止监听.源码不附带自动测试套件;按已启用的模块手动验收.服务路径,限制和状态文件见[设计文档](doc/DESIGN.md).

代理节点的流量上限按(上传+下载)×2 计入;界面显示已计入的数值,计量数据不完整本身不会提前限速.月度重置从所选月份的第 1 日 00:00 UTC 执行;天和年的周期保持原有计算方式.节点网卡地址默认遮盖,可按需显示或复制.在“最近访问者”可确认后清除历史;之后的新访问和仍在连接中的设备会重新记录.设置页面直接显示模块安装卡片;进度在最后一次输出后 30 秒收起,完成提示只在本次操作页面短暂显示,刷新或重新进入不会重现.顶栏“更新日志”右侧的“详细日志”汇总模块操作历史与服务日志;服务日志可按等级筛选.清空模块历史会截断该文件,清空某项服务日志只隐藏此前的记录,不删除整机 journal.Lucky 沿用自身管理页面;当前网络无法直连时可通过 SSH 转发管理端口.

### 配置

每个变量都有可用的默认值;首次安装可从源码目录的 `.env` 导入,之后由状态根中的 `.env` 保存.关键变量如下:

| 变量 | 含义 | 默认值 | 是否必需 |
|---|---|---|---|
| `VPSSRV_STATE_DIR` | 首次安装前在命令环境设置的持久状态根;不从 `.env` 改动位置 | `/var/lib/vps-server` | 否 |
| `VPSSRV_PUBLIC_HTTP_PORT` | 公开可达性页面的明文端口 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公开可达性页面的 TLS 端口 | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 首次安装是否提供公开页面;安装后 HTTP/HTTPS 可分别在 Home 开关 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台端口;`0` 表示生成并记住端口 | `0` | 否 |
| `VPSSRV_AUTH` | 控制台是否要求密码 | `1` | 否 |
| `VPSSRV_IPERF_PORT` | 已开启的 iperf3 窗口监听的端口 | `5201` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台不可超过的时长上限 | `60` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `es` | `en` | 否 |

完整说明:[配置参考][local-link-002].

## 升级

v6.0.0 候选建立持久状态布局 `1`.v5.1.0 及更早版本**不支持自动迁移**.仍有旧数据时,先备份到安装目录外,再全新安装;已经删除且没有备份的数据无法恢复.安装器发现旧服务但缺少状态时,会在修改服务前停止.

后续从布局 `1` 升级时,在独立目录检出新源码,使用相同的 `PREFIX` 和 `VPSSRV_STATE_DIR` 运行安装程序.保留状态根和 `/etc` 中的模块配置;安装器沿用密码,端口,证书,运行数据和已记录模块,不会再次打印旧密码.先保留代码与数据备份,升级后核对服务状态,管理端口,登录及所用模块.自定义状态路径需在后续安装中沿用;改换路径要自行转移并核验.

## 卸载

在安装源码目录以 root 身份运行,并沿用安装时的 `PREFIX` 和 `SERVICE_NAME`(准确命令见安装摘要):

```bash
KEEP_DATA=1 bash deploy/uninstall.sh  # 停止服务,保留程序和持久状态
bash deploy/uninstall.sh              # 完全卸载,删除默认状态根
```

两种模式都会停止本项目管理的服务并释放端口登记.保留数据模式保存程序,状态根,统一代理配置,FRPS 配置,FRPC 实例配置及 Tailscale 设备身份;完全卸载删除本项目命名的这些配置与恢复副本.共享 FRPC 的主机请先核对实例归属.自定义到状态根之外的数据路径不会自动删除.详细清理范围见[设计文档](doc/DESIGN.md#完整卸载).

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
