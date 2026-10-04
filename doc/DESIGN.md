---
name: project-design
description: 项目架构与设计约束
metadata:
  version: "1.0.0"
  lang: "zh-CN"
---

# vps-server — 设计

## 多语言

**简体中文** | [English](en/DESIGN.md) | [Español](es/DESIGN.md)

## 文档

- 项目概览:[README](../README.md)

- 设计思路:[DESIGN](DESIGN.md)

- 项目状态: [LOG](LOG.md)
- 历史记录: [HISTORY](HISTORY.md)
- 变更日志: [CHANGELOG](CHANGELOG.md)

- 第三方声明:[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 设计目标

<a id="vps-design-goals"></a>

**当前版本已实现的目标(见[验收限制][local-link-001]):**

当前安装程序默认部署 Web 控制台,其他服务端模块由 `VPSSRV_MODULES` 或后续模块管理选择.FRPC 另行安装.以下保留各功能形成时的目标与验证记录;具体时间以历史记录为准.

- 在一台全新的 Debian/Ubuntu VPS 上,安装可按需启用的控制台和网络模块
  (web 模块包括公开页面及私有控制台):
  1. **公开可达性页面** —— 一个刻意做得极简,无需鉴权,在 TCP
     **80 和 443**
     端口上提供服务的页面,让任何只拿到这个 IP 的人都能在浏览器里确认
     这台主机的 Web 端口从他所在的位置是否可达.
  2. **私有控制台** —— 一个运行在持久化随机高位端口的仪表盘,提供浏览器上传/下载测速和近期入站连接日志.可使用管理员密码,或明确加入名单的私有局域网 IP 访问.
  3. **按需开启的 iperf3 窗口** —— 一个带宽/延迟测试端点,
     **默认关闭**;
     操作员从控制台开启一个限时窗口,窗口到期后自动关闭.
  4. **统一代理** —— 一个 sing-box 服务承载 AnyTLS,VMess,VLESS,Trojan,Shadowsocks.
  5. **Tailscale** —— 本机 Linux 客户端状态,偏好,设备列表及日志.
- 完整离线包随附服务二进制和节点计量所需的私有 nftables 运行时;目标机安装不下载源码或系统包.
- 能与 `vps-webserver` 和 `Anytsl-Serve` 共存于同一台主机上,不与它们在
  systemd unit 名称,安装前缀,环境变量前缀或持久化端口上发生冲突.

**持续跟踪的目标与当前状态:**

- [ ] 2026-10-04 v6 目标机验收:统一代理迁移须保留旧节点 ID,端口,凭据,证书和计量状态;完整离线包需在受支持的 Debian/Ubuntu 系统上无 Git,无仓库网络访问地完成安装.Tailscale 加入 Tailnet 仍需控制服务器可达.
- [x] 2026-09-19 按节点统计流量并设置流量上限:五种代理协议分别统计上传与下载.原有达到上限后双向限速 1 Mbps 及每月或指定时间重置的行为已于 2026-09-27 通过真实主机测试.当前分支新增上传与下载独立限速,达到流量上限后选择双向限速 1 Mbps 或停止使用,按天/月/年设置重复周期,以及到期后停止使用的可选有效期.新规则与状态迁移通过自动化检查;测试机已验证界面和迁移,尚未逐一验证真实流量.
- [x] 2026-09-19 基于浏览器的初次配置曾由 `tools/setup_wizard/setup_wizard.py` 提供;该流程已退役,旧向导源码及专用语言包已清理.v5.0.0 的首次安装直接在终端完成,默认仅安装 Web 控制台.
- [x] 2026-09-22 在已登录控制台提供 FRPS / FRPC 连接信息.页面报告本机 FRPS unit 状态,绑定地址,网卡地址,端口和认证令牌;敏感值仅在点击显示或复制时读取.FRPC 连接模板使用已安装服务器的值和可替换的服务器地址占位符.服务器无法查看其他设备上 FRPC 的运行状态.
- [x] 2026-09-29 管理本机 FRP 配置.已登录操作员无需再次验证管理员密码,即可修改 FRPS 绑定端口和令牌,编辑及验证本机 FRPC 实例,并启动或停止实例.实例页面按需显示已保存的 IP 和令牌.临时 root 辅助程序在 Web unit 的只读系统沙盒外执行固定操作;更改的本机监听端口会在启动前登记到 `~/apps/PORTS.md`,停用后释放,验证或服务操作失败时恢复旧配置;其他设备上的 FRPC 实例不受影响.模块页面可独立于 FRPS 安装带固定校验和的 FRPC 二进制文件及 `frpc@.service` 模板,依据这两者而非实例配置判断安装状态.在控制台单独卸载 FRPC 模块时会停止实例并保留其配置;运行 `deploy/uninstall.sh` 且不设置 `KEEP_DATA=1` 时,完整卸载会删除本项目命名的 FRPC 配置和恢复副本.
- FRPS 编辑辅助程序持有端口登记锁.旧安装缺少当前 FRPS 端口登记时,先按现有配置补记;若该端口已登记给其他服务则拒绝修改.更换端口前预留新端口,保存失败时撤销新登记,成功后释放旧登记;只修改令牌时保留当前端口登记.
- [x] 2026-09-29 将 FRPS 和本机 FRPC 控件呈现为操作卡片.FRPS 使用与节点页面相同的行内编辑模式和服务开关.每个 FRPC 实例都有遮蔽的目标 IP,根据套接字判断的连接状态,以及单独的“测试连接”操作;该操作使用已保存的凭据执行不带代理的 FRPC 登录.实例页面显示服务器字段及各代理的类型,本地 IP,本地端口和远程端口;只有选择“编辑”才打开编辑界面,保存后返回该实例.字段编辑器只接受它能表示的简单令牌认证 TCP/UDP 配置,对不支持的 TOML 保持原样.每张目标卡片仅代表本机实例;初始连接状态要求该实例 systemd 主进程拥有与配置中的服务器及端口之间已建立的套接字.

FRPC 卡片检查,2026-09-29:操作员提供的四张截图显示旧连接模板,无法直接显示的遮蔽信息,高级 TOML 面板,以及缺少测试操作的服务器卡片.在部署的 `test-d09835d` 版本上,Chromium 以 390 和 1440 CSS px 检查了实例列表,遮蔽和显示后的服务器信息,收起与展开的编辑控件,代理信息,连接测试状态,以及保存后返回同一实例.多余面板已移除,两项信息均按需载入,四项代理信息全部可见,两种宽度均无横向溢出.界面沿用项目现有卡片样式;此次浏览器检查未覆盖真实移动设备及代理流量.
- [x] 2026-09-29 的浏览器初次设置流程已退役.当前 Settings → Modules 可从已安装,版本匹配的源码包安装遗漏模块,或启用及停用已安装模块.临时 systemd 任务在 Web 服务外运行安装程序;模块选择保留既有模块和凭据.公开 HTTP,HTTPS 开关分别影响对应监听器,控制台仍可访问.原向导的测试记录保留在历史文档中.

退役的初次设置监听器曾在提供服务前将随机端口登记到 `~/apps/PORTS.md`,关闭时删除登记;临时设置密码只允许一个浏览器会话使用.当前模块页面位于普通 Settings,使用已登录会话;仅向单独的特权 systemd 任务提交固定模块名称及操作.任务在 Web 服务外记录进度,因此安装过程中允许 Web 重启.停用代理模块不会删除节点或凭据;使用节点控件时,已停用 unit 仍保持停止.iperf3 和公开页面开关会重启 Web 服务以应用监听器变更,控制台仍可访问.
- [ ] 后续版本完整复刻 Lucky 功能.当前版本仅提供模块安装,卸载及进入 Lucky 原生管理页面的入口;后续 1:1 功能复刻的具体范围与验收标准届时确定.
- [ ] v6 Tailscale 目标机验收:当前控制台已实现 Linux 客户端概览,常规设置,设备列表和运行日志;Web 管理端口及节点中继端口也纳入 `PORTS.md`.这些行为还需在测试机确认,OpenWrt 专有的 dnsmasq 转发不适用于本项目的 Debian/Ubuntu 目标机.
- [x] 完成节点控制的实机验收:删除节点后显示编号保持连续,全部删除后新节点从 1 开始,隐藏的 UUID 保持身份不变;名称,端口,凭据和 TLS SNI 可修改;Shadowsocks 的 SNI 显示为不适用;随机重置端口和凭据时保留 SNI.每个节点可单独停用并保留配置和流量记录,再用原端口启用.控制功能已于 2026-09-27 通过真实主机测试.
- [x] Web UI 采用统一的间距和控件样式,随附字体和图标,清晰的焦点状态以及响应式布局,覆盖控制台和公开连通页.普通设置页有八种可记忆的主题色和独立的明暗模式;切换模式不会改变主题色.

登录页使用与界面其他部分相同的项目名称及 Home 链接.卡片页脚把运行版本链接到 Changelog,并允许登录前选择语言.主题控件仍位于普通 Settings.每个可编辑密码字段默认遮蔽,带有独立且可访问的显示/隐藏控件;切换可见性不会清空值,转移焦点或提交表单.
已登录页面的页眉仅包含 Home,Changelog,Settings 和 Sign out;各功能入口放在 Dashboard.子页面有 Back 链接.普通设置和安全设置在桌面宽度使用侧边导航,在较窄宽度使用可滚动的一行导航.在普通设置中选择 Security 组会跳到其入口卡片;打开受保护页面须使用独立操作并通过管理员验证.各页面使用彼此关联但不同的标签图标.
按 2026-09-29 的要求,切换页面使用普通浏览器导航,不再使用路由动画或页面动态效果设置.调整窗口大小时,先冻结可见控件,再移至新布局.受保护页面进入浏览器历史前会隐藏,重访时须重新向服务器请求;退出登录后不能从缓存查看控制台页面.
在开发版本中,Web Changelog 会在正式标签的历史记录上方显示 `LOG.md` 中的当前测试版本说明.运行版本取自部署的 `VERSION` 标记;正式发布历史保留本地化译文,缺少译文的测试版本说明回退为英文.

共用 SQLite 锁的疑虑是[尚未解决的测量问题][local-link-002],并非要求变更架构.历史已完成工作和验证记录见 [LOG][local-link-003].

**非目标**

- **不是 `vps-webserver` 或 `Anytsl-Serve` 的替代品.** 两者都会继续独立维护,
  独立发版.vps-server 只是把它们的代码内嵌(vendor)进来,而不是导入或取代它们;
  这样做在漂移问题上要承担什么代价,以及如何缓解,见[决策][local-link-004].
- **没有 ACME / Let's Encrypt / 域名.** 443 上的 TLS 是自签名证书.公开页面的
  职责只是回答"你到底能不能连到这个 IP",浏览器的证书警告页面本身就已经回答了
  这个问题.证书续期和域名依赖对这个职责没有任何帮助.
- **没有常驻的 iperf3.** 一个无需鉴权的公开 `iperf3 -s` 会让任何陌生人随心所欲地
  占满这台主机的上行带宽.
- **公开页面不暴露关于主机的任何信息.** 没有主机名,没有内核版本,没有运行时长,
  没有服务清单,没有端口列表,没有 anytls 参数.它只报告:你连上了,它看到的
  源 IP,服务器时钟,以及你是通过哪个端口/协议到达的.
- **没有反向代理,没有 nginx,没有容器.** Python 进程自己终止 TLS,
  就像 `vps-webserver` 已经做的那样.
- **没有多服务器测速选择器.** 只有一台主机,就是这台.

## 架构

Web,统一代理和可选的 Tailscale 服务各自运行;AnyTLS 是统一代理中的一种入站协议.Web 服务还会启动临时 iperf3 子进程.控制台和公开页面在一个 Python 进程中使用不同的监听器并共享内存状态.只有经过配置的客户端流量会到达这些服务.

```
                       ┌──────────────────────── vps-server-web.service ───────┐
  anyone, no auth      │                                                       │
  :80  ──────────────► │  public listener (HTTP)  ──┐                          │
  :443 ──────────────► │  public listener (HTTPS) ──┤                          │
                       │                            ├─► ProbeHandler           │
                       │                            │   (reachability page)    │
                       │                            │                          │
  operator, password   │                            │                          │
  :<random> ─────────► │  console listener  ───────►│   ConsoleHandler         │
                       │                            │   ├─ LibreSpeed endpoints│
                       │                            │   ├─ visitor log         │
                       │                            │   └─ iperf3 window ctl ──┼──┐
                       │                            │                          │  │
                       │  connection poller ◄───────┴── /proc/net/tcp[6]       │  │
                       │  (all ports, not just HTTP)                           │  │
                       └───────────────────────────────────────────────────────┘  │
                                                                                   │
  tester with iperf3      :5201 ◄────────────── iperf3 -s  (child process, ────────┘
  client                                         killed when window expires)

                       ┌─── vps-server-proxy.service ────────┐
  proxy client ──────► │  one sing-box process, five protocols  │
  :<node port>        │  AnyTLS is an inbound protocol          │
                       └────────────────────────────────────────┘
```

代理模块只有一份 sing-box 配置和一个服务.节点计量由共用的 `vps-server-node-meter.service` 管理.旧 AnyTLS 服务在带备份的升级迁移完成后退役.

### 功能模块

`src/web/app.py` 负责进程配置,认证边界,监听器和兼容旧调用方的名称.`ConsoleHandler` 组合 `src/web/features/` 中的功能 mixin;各模块包含对应路由,页面和操作.同一模块中的服务函数接收 `context` 参数;入口将自身模块作为 context 传入,保持现有公开 Python 导入可用.其他项目复用功能时,需提供所选功能引用的设置,服务函数和标准库对象,以及适用的 HTTP 辅助方法.功能模块不导入本应用入口.

| 功能 | 后端模块 | 前端源文件 |
| --- | --- | --- |
| 登录与访问 | `features/auth.py` | `src/web/static/password-fields.js`, `src/web/static/styles/login.css` |
| 设置 | `features/settings.py` | `src/web/static/access-settings.js`, `src/web/static/settings-sections.js`, `src/web/static/styles/settings.css` |
| 首页与模块管理 | `features/modules.py` | `src/web/static/module-controls.js`, `src/web/static/module-status.js`, `src/web/static/styles/dashboard.css`, `src/web/static/styles/modules.css` |
| 浏览器测速 | `features/speedtest.py` | `src/web/static/speedtest-ui.js`, `src/web/static/styles/speedtest.css` |
| iperf3 窗口与对外测试 | `features/iperf.py`, `features/iperf_client.py` | `src/web/static/iperf-countdown.js`, `src/web/static/styles/iperf.css` |
| FRPS 与 FRPC | `features/frp.py` | `src/web/static/frp-editor.js`, `src/web/static/styles/frp.css` |
| 代理节点与 AnyTLS | `features/proxy.py`, `features/proxy_service.py` | `src/web/static/node-controls.js`, `src/web/static/private-values.js`, `src/web/static/styles/proxy.css`, `src/web/static/styles/nodes.css` |
| 端口转发 | `features/portfwd.py` | `src/web/static/styles/forms.css` 中的共用表单样式 |
| 最近访客 | `features/visitors.py` | `src/web/static/visitors.js`, `src/web/static/styles/visitors.css` |
| 变更日志 | `features/changelog.py` | `src/web/static/styles/changelog.css` |
| Lucky 状态 | `features/lucky.py` | 共用卡片样式 |
| Tailscale 状态,设置与设备 | `features/tailscale.py`, `tailscale_control.py` | `src/web/static/styles/modules.css`,共用私有值控件 |
| 浏览器 root 终端 | `features/terminal.py`, `terminal_session.py` | 随附 xterm.js 与 Fit Addon,`src/web/static/terminal.js` |
| 公开可达性页面 | `features/public.py` | `src/web/static/styles/public.css`,嵌入响应 |

`features/system.py` 提供共用的主机命令和防火墙辅助函数;`features/ui.py` 提供共用渲染函数.节点控制器及 FRP/模块辅助程序仍位于 `src/web/`,可独立于 HTTP 处理器复用.各 JavaScript 文件只绑定本功能的页面元素;共用脚本处理主题,复制,密码显示和选择控件.按顺序排列的 CSS 源文件位于 `src/web/static/styles/`,由 `python3 tools/build_styles/build_styles.py` 生成 `src/web/static/style.css`,保持原有规则顺序.安装程序将 Python 模块,`features/` 与 `static/` 保持在 `$PREFIX/src/web/`;根目录的 `$PREFIX/app.py` 只调用该包的 `main()`.v6 候选的持久数据位于独立状态根,旧版平铺代码文件不作为当前运行入口.复用功能时须提供 context 适配层及对应样式和脚本;这些路由没有独立的认证策略.

### 为什么公开页面和控制台是两个独立的监听器

它们的安全姿态是完全相反的,把它们合并只会强迫其中一个放弃自己的姿态.
控制台需要鉴权,放在一个不可猜测的端口上,正是为了让它不那么容易被随意发现;
公开页面则**必须**容易被发现,
并且**禁止**要求密码.所以:不同的端口,不同的请求处理器,
不同的路由表.一个打到 80/443 上的请求永远到不了控制台的路由,因为
`ProbeHandler` 根本没有那些路由——不是因为某个检查拦下了它.这正是重点所在:
一个鉴权检查可能有 bug,一个不存在的路由不可能有.

公开页面只接受 `GET` 和 `HEAD`,且仅限两个路径(`/` 和 `/favicon.ico`),其余一律
以 404 回应.它不读取查询字符串,不解析请求体,也不设置任何 cookie.

### 在已有安装上升级

`v6.0.0` 候选建立持久状态布局 `1`:程序文件仍位于 `$PREFIX`,默认状态根位于 `/var/lib/vps-server`.密码,控制台端口,证书,运行数据,安装记录及 `.env` 保存在状态根;`/etc/vps-server/state-dir` 记录状态根位置.状态根由 root 管理,目录权限为 `0700`.后续安装程序**必须**继续读取布局 `1`,并在替换程序文件时保留这些状态.

安装器通过状态根的 `.layout-version`, `install-state` 和 `paths.json` 辨认受支持安装.三者缺失或不一致,以及关键密码,会话密钥或端口文件丢失时,它在修改服务前拒绝升级.带有 v5.1.0 及更早布局的安装不自动迁移;操作员须先备份原有数据并明确执行全新安装.已经删除且没有备份的旧数据无法恢复.正常升级从独立源码目录运行安装器,**禁止**以删除 `$PREFIX` 作为保留数据的方式.若只替换代码目录,保留的状态根仍可供同一布局的后续版本读取.

应用内设置及模块管理都使用状态根,直接读取 `$PREFIX/data` 等旧路径的入口已改为统一的状态路径.代理配置和节点清单分别位于 `/etc/vps-server-proxy/` 与 `/etc/vps-server-nodes/`;旧 `/etc/vps-server-anytls/` 只作为升级迁移输入.Tailscale 身份状态保存在状态根的 `tailscale/`;FRP 配置仍位于 `/etc/frp/`.`PORTS.md` 位于安装目录的上一级.自定义持久路径写入 `paths.json`,后续安装若发现它们变化则拒绝静默切换,由操作员手动处理.

### 完整卸载

完整卸载由 `deploy/uninstall.sh` 在移除 `$PREFIX` 前调用 `src/web/uninstall_cleanup.py`.它在全局 FRPC unit 与项目模板一致,存在项目二进制归属标记,或完整卸载发现控制台可识别的命名实例时处理 FRPC;先停止实例,再移除适用的模板和经过固定 SHA-256 校验的二进制文件.默认完整卸载删除 `frpc-*.toml`,对应的 Unicode 别名和 `.deleted-frpc-*.toml` 恢复副本;`KEEP_DATA=1` 保留这些配置文件.卸载器持有安装目录同级的 `.ports.lock`,复用 `console_port.py` 的格式校验与原子写入,释放 `PORTS.md` 中以 `vps-server` 命名的行,同时保留其他项目的行.完整卸载且发现控制台识别的 `frpc-*.toml` 时,即使旧 FRPC 模板与当前模板不同,也会停止这些实例并删除该模板,匹配摘要的二进制与项目命名配置;这是本项目完整卸载的显式范围.没有可识别实例且无法确认归属时,FRPC 文件和其登记行保留,其他项目的行始终保留;二进制校验失败则中止清理.

`KEEP_DATA=1` 保留 `$PREFIX` 和 `$VPSSRV_STATE_DIR`;默认完整卸载在完成服务与端口清理后,只删除带有布局标记 `1` 的状态根.自定义到状态根之外的路径不自动清除,以免误删其他应用的数据.

### 统一代理模块

<a id="vps-proxy-module"></a>

`/proxy` 展示 AnyTLS,VMess,VLESS,Trojan 和 Shadowsocks 节点;`/anytls` 只为旧书签重定向到同一页面.五种协议共用 `/etc/vps-server-proxy/config.json`, `vps-server-proxy.service`, `/usr/local/bin/sing-box-vps-server`,安装和卸载入口.每个受管节点以稳定 ID 关联配置,流量限制和 Clash 分享.新建 TLS 节点各有自签名证书;Shadowsocks 不需要证书.

旧安装中的 `/etc/vps-server-anytls/config.json` 由 `proxy_migration.py` 检查并合并:先归档旧配置,节点清单,计量和服务文件,再保留节点 ID,端口,凭据及证书进行切换.只有新配置通过 sing-box 校验且服务状态恢复后,才退役旧 unit;完整安装成功后移除旧配置目录.失败时恢复旧服务和文件,归档保留在状态根的 `data/`.

节点创建,编辑,启停,删除和重置在 `node_control.py` 的锁下更新配置,清单,防火墙,计量和 `PORTS.md`.公开端口在操作前检查监听与登记,失败时撤销新登记;停用或删除时释放本项目的登记.流量上限按(上传+下载)×2 计入,内核配额使用原始计量的一半阈值.计量缺口不触发提前限速.月度周期在每月 1 日 00:00 UTC 重置;天和年沿用原周期规则.

节点页面默认遮盖网卡地址,端口及凭据,显示/复制请求由认证后的私有值接口提供.缺少受管清单或清单与配置不一致时,页面提示迁移/修复,不使用旧编辑路径.历史独立模块设计和退役原因见 [HISTORY](HISTORY.md#retired-anytls-console).

### Tailscale 模块

离线包包含官方 Linux amd64 静态归档.安装器验证散列,创建 `vps-server-tailscale.service` 和私有状态目录,固定 UDP 端口先登记到 `PORTS.md` 再启动.Tailscale 控制台通过本机 socket 和固定 CLI 参数读取状态,偏好,连通性与设备列表,以及 systemd journal;私有地址和账户默认遮盖.登录密钥仅作为临时 root 文件传给 CLI,命令结束后删除,不写进项目状态.常规设置在同一表单中收集更改,用一次 Linux `tailscale set` 调用应用;空白的路由,出口节点与中继端口输入保持原值,清除由独立复选框表达.设备 IPv4/IPv6 分别按需读取,本机子网和可用出口节点可快速填入.实验性低内存选项经固定参数辅助任务写入独立 systemd drop-in `GOGC=10`,重启服务并在失败时尝试恢复原配置;较低 GOGC 可能增加 CPU 开销.这些控制不模拟 OpenWrt 的 dnsmasq 转发或路由器防火墙选项.安装二进制可离线完成,加入 Tailnet 需要访问所选控制服务器.

Lucky 保留原生管理页面;本项目只显示管理地址,运行状态及打开按钮,不展示由 Lucky 自身管理的账户和密码.页面每 5 秒读取当前配置端口,Web 进程也每 5 秒检查端口变化;特权助手确认 Lucky 进程实际监听后,原子更新 `PORTS.md` 中仅属于 Lucky 的行,监听消失时移除旧行.在测试机上,即使 `AllowInternetaccess=false`,Lucky 仍监听通配地址,同一局域网可访问其 HTTP 管理页;这个选项不能当作只绑定 `localhost` 的保证.Lucky HTTP 登录不提供传输加密.

浏览器终端只在已启用 Web 管理功能且管理员密码会话的短期验证有效时开放,IP 免密会话不能打开.root PTY 通过同源且带 CSRF 令牌的 WebSocket 建立,连接断开,离开页面或验证到期即终止进程;命令内容不写入控制台访问日志.xterm.js 静态文件与许可证随离线包提供,不使用 CDN.

### iperf3 窗口生命周期

1. 操作员登录控制台,选择一个时长(默认 10 分钟,上限由 `VPSSRV_IPERF_MAX_MINUTES`
   限定),点击打开.
2. 控制台把 `iperf3 -s -p <port>` 作为子进程启动,在当前生效的防火墙上开放该端口,
   并把截止时间记在内存里.
3. 窗口开启期间,**公开页面**会显示 iperf3 正在接受连接,在哪个端口上,还剩多少
   时间——远端的测试者需要知道这些信息,而且这不属于敏感信息:这个窗口本来就是
   刻意开放的.
4. 到达截止时间(或操作员主动请求关闭,或服务停止)时,子进程会被终止,防火墙
   规则也会被撤销.

这个窗口的状态保存在内存里,不落盘:如果服务挂掉,窗口也就随之消失,这是失败时
更安全的方向.一次重启永远不会把一个已开启的窗口复活.

延迟数据取自 iperf3 自身 `--json` 输出中的(TCP 信息块里的)`mean_rtt` 字段,
是在测试者一侧读到的;服务端不需要为此额外写任何代码.这个字段来自内核的
`TCP_INFO`,因此在 Linux 客户端上存在,在读不到它的客户端上则缺失——例如
Windows 上 Cygwin 下的 iperf3 会报告吞吐量但没有 `mean_rtt`.UDP 模式(`-u`)
在任何环境下都会报告抖动和丢包,当测试者不在 Linux 上时,这是更具可移植性的
方案.

选择的端口单独保存在应用数据目录中.只能在窗口关闭时从控制台修改;保存前会检查是否与已安装服务,端口转发或当前监听端口冲突.

### 端口转发生命周期

一个转发规则会把这台主机上的一个公网 TCP/UDP 端口,转发到一台通过 Tailscale 或
局域网可达的设备上——这样一台拥有公网 IP 的主机就能替一台没有公网 IP 的设备
出面.和 iperf3 窗口不同,这属于配置,而不是对上行带宽的限时租借:它本应在
重启或重新引导之后依然存在,所以实现方式也不一样.

1. 操作员从控制台添加一条规则:协议(tcp/udp/both),一个公网端口,以及一个
   目标 `host:port`.在任何东西触碰 iptables 之前,`PortForwardManager.add()`
   会先拒绝一个已经被本次安装占用的公网端口(控制台,公开页面,iperf3,
   anytls 节点,已安装的 proxy 协议,或另一条转发规则).
2. 规则中的每一个协议都会变成四条 `iptables` 规则,全部打上
   `-m comment --comment vps-server-portfwd-<id>` 标记,以便和表里已有的其他
   规则区分开来:
   - `nat`/`PREROUTING`:把公网端口 DNAT 到 `target_host:target_port`.
   - `nat`/`POSTROUTING`:对发往目标的流量做 MASQUERADE,让回复流量经由这台
     主机路由回来,而不是从目标自己的默认网关出去——这样目标看到的客户端
     就是这台主机.
   - `filter`/`FORWARD`:每个方向各一条 ACCEPT 规则,因为该链上的默认 `DROP`
     策略(例如在 Docker 主机上很常见)否则会悄悄吞掉被转发的流量.
3. `net.ipv4.ip_forward` 会在第一条规则需要它时被打开
   (`_ensure_ip_forward()`),并且永远不会再关闭——原因见[决策][local-link-007]
   (2026-09-19).
4. 规则集保存在 `PORTFWD_STATE_FILE`(JSON)里,而不只是留在内存中.每次
   进程启动都会调用 `PortForwardManager.load()`,它会无条件地先撤销,再重新
   加上每一条已启用规则的 iptables 状态——内核的表在重启之后什么都不会记得,
   而如果这只是一次服务重启,表里可能还留着上一次运行的规则,所以不论是哪种
   情况,这都是唯一需要处理正确的路径.
5. 一次干净的停止(`SIGTERM`,和 iperf3 窗口用的是同一个信号处理器)会调用
   `PortForwardManager.shutdown()`,它会撤销每一条已启用规则的 iptables 状态,
   但不会去动 JSON 里的 `enabled` 标记——重启这个服务,或者重启主机,都**必须**
   通过 `load()` 把它们全部直接带回来.这和 iperf3 窗口是同一个失败安全方向:
   如果管理这份状态的进程没有在运行,这份状态就**禁止**
   悄悄地比它活得更久.

`target_host` **必须**是一个字面的 IPv4 地址,不能是主机名:`iptables --to-destination` 只接受地址,而且本项目在请求时不做任何出站 DNS 查询
(见"零第三方运行时依赖"那条决策).一台 Tailscale 设备的 IP 是稳定的,可以在
该设备上用 `tailscale status` 或 `tailscale ip` 查到.

## 设计约束

- **禁止**将控制台路由放入 `ProbeHandler`;鉴权不能替代独立的公开路由表.
- iperf3 需要有时间限制,并在关闭或停止服务时撤销防火墙规则.
- 每次进程启动时从 JSON 重放持久化的转发;干净停止时撤销运行时规则,不重置主机级 `ip_forward` 开关.
- 升级须保留节点凭据和选定设置;轮换应使用所属模块的配置脚本,在 Web unit 文件系统沙箱外运行.
- 从 v6.0.0 起,后续版本**必须**保持持久状态布局 `1` 可读,**禁止**把默认持久状态移回 `$PREFIX`.安装器**禁止**自动迁移 v5.1.0 及更早布局;检测到旧服务或关键状态缺失时**必须**先于服务变更拒绝安装.自定义状态路径改变时**必须**由操作员手动转移,**禁止**静默重置.
- 没有有害延迟的证据,不要拆分共用的 `_db_lock`:历史上 60 个并发请求的测量未重现减速.见[缺陷][local-link-008].

## 外部接口

- HTTP/HTTPS:80/443 上的公开监听器只提供可达性页面;操作员控制台使用单独的持久化端口.iperf3 仅在鉴权后开启的限时窗口中监听.
- 控制台读取 `/proc/net/tcp[6]` 记录入站 TCP 连接;公开路由不导出代理凭据.
- `install.sh` 使用随附二进制及私有 nftables 运行时,不在目标机调用软件包镜像或查询公网 IP.`setup-proxy.sh` 管理统一 sing-box unit 和证书.iptables 在存在时管理临时开放的 iperf3 端口与已启用的转发;systemd 监管服务并在 Web 沙箱外运行受限的节点操作辅助程序.

## 技术栈

| 层 | 选择 | 版本 | 原因 |
|---|---|---|---|
| 运行时 | Python,仅标准库 | 3.9+ | 继承自 `vps-webserver`:不需要第三方 Python 包;发行版维护的解释器及标准库仍需要安全更新 |
| HTTP 服务器 | `http.server.ThreadingHTTPServer` | stdlib | 三个监听器各自的请求量都不大;上框架只是死重量 |
| TLS | Python `ssl` + 随附 sing-box 生成的自签名证书 | stdlib / sing-box | 没有域名,没有 ACME(见非目标) |
| 存储 | `sqlite3` | stdlib | 访客日志**必须**在重启后保留 |
| 测速引擎 | LibreSpeed,原样内嵌(vendored) | v6.2.1 | LGPL-3.0;已经在 `vps-webserver` 中内嵌并跑通 |
| 二维码渲染 | kazuhikoarase/qrcode-generator,未修改的随附副本 | js2.0.4 | MIT;体积小,无需构建步骤,与 LibreSpeed 一样通过普通 `<script>` 标签使用 |
| 带宽探测 | 随附的 x86-64 Linux `iperf3` | 3.22 | 测试者在客户端一侧本来就已经普遍具备的事实标准工具 |
| 代理核心 | sing-box,内嵌二进制(amd64) | v1.13.14 | GPL-3.0;直接分发二进制能让安装保持离线可用 |
| Init | systemd | — | 目标操作系统的默认选择 |
| 安装脚本 | Bash | — | 继承自两个上游项目 |

各方案及其被否决的替代方案和理由见[决策][local-link-009],这里不重复.

## 复现要求

<a id="vps-reproduction-requirements"></a>

### 环境

- 操作系统:Debian 11+ / Ubuntu 20.04+,systemd,以 root 身份运行
- 运行时:Python 3.9+(发行版自带的 python3 即可)
- 架构:整个项目仅支持 x86-64 Linux;FRPC,FRPS,iperf3,sing-box,Lucky,Tailscale,nftables 的随附可执行文件都面向此平台.
- 硬件:无需 GPU;完整离线包,解压目录和已安装程序合计建议至少 1 GiB 可用磁盘,内存
  只需 VPS 通常具备的量即可
- 随附构件完整性检查:在仓库根目录运行 `python3 tools/verify_dependencies/verify_dependencies.py`.它会对照[dependencies.lock.json][local-link-010],通过 SHA-256 在不执行文件的情况下比对九个受版本控制的第三方可分发文件.已记录的版本与上游修订号来自先前项目记录,并非经独立核实的上游身份;LibreSpeed 的准确上游修订号未记录.
- `app.py` 只使用标准库,因此没有第三方 Python 包锁.这个构件锁不是依赖恢复命令,也不是完整的系统包锁;见 [THIRD_PARTY_NOTICES.md][local-link-011].

### 外部依赖

| 项目 | 来源 | 存放位置 |
|---|---|---|
| `iperf3` | 随本仓库分发的静态构件 | `$PREFIX/vendor/iperf3/iperf3` |
| `frpc`,`frps` | 随本仓库分发 | `third_party/frp/`,安装后按模块复制 |
| nftables 及运行库 | Debian 11 官方包,构建离线包时随附 | `$PREFIX/vendor/nft/`,不写入系统包数据库 |
| Tailscale 客户端 | 官方 Linux 静态归档,构建离线包时随附 | `/usr/local/bin/tailscale-vps-server` 与 `tailscaled-vps-server` |
| Bash,systemd,Python,tar,coreutils | 受支持系统的基础环境 | 系统路径 |
| sing-box 二进制 | 随本仓库分发 | `/usr/local/bin/sing-box-vps-server` |
| LibreSpeed 引擎和 qrcode-generator 库 | 随本仓库分发 | `$PREFIX/src/web/static/` |
| TLS 证书 | 由安装程序在首次运行时生成 | `$VPSSRV_CERT_DIR` |

FRPC,FRPS 和 iperf3 可从本仓库安装,无需在安装时下载.其他缺失的系统包仍可能由安装程序从目标 Debian/Ubuntu 仓库安装,不选择精确版本或仓库快照.Python,OpenSSL,shell/系统工具及 systemd 同样由目标系统提供.主机操作员依靠所选发行版持续维护安全更新的软件包渠道.这避免随附这些二进制文件,但不同主机,不同时刻的包版本,散列及传递依赖解析可能不同;**尚未实现严格,完全可复现的依赖
恢复**.要实现它,需要另行批准安装程序修改并选择发行版/仓库快照.锁文件可机读的 `exclusions` 记录了这一边界,而非虚构的锁定.

无需 API 密钥.Web 服务和安装程序均不进行出站公网 IP 查询.

### 路径与挂载

<a id="vps-paths-mounts"></a>

| 路径 | 由谁提供 | 用途 |
|---|---|---|
| `$PREFIX` | 安装程序;root 账户默认 `~/apps/vps-server` | 可替换的程序代码,静态资源和随附构件 |
| `$VPSSRV_STATE_DIR` | 安装程序;默认 `/var/lib/vps-server` | 布局标记,安装记录,路径清单,密码,端口,证书和运行数据 |
| `$VPSSRV_DATA_DIR` | 安装程序,默认 `$VPSSRV_STATE_DIR/data` | `visitors.db`,`session_secret.txt`,`portfwd.json`,`login-access.json` |
| `$VPSSRV_CERT_DIR` | 安装程序,默认 `$VPSSRV_STATE_DIR/certs` | Web 自签名证书和密钥 |
| `/etc/vps-server/state-dir` | 安装程序 | 保存状态根位置,供独立辅助程序读取 |
| `/etc/vps-server-proxy/` | 安装程序 | sing-box 的 `config.json`(多个入站)及初始自签名证书;新节点证书位于 `/etc/vps-server-nodes/certs/` |
| `$VPSSRV_STATE_DIR/tailscale/` | Tailscale 守护进程 | 设备身份与本机连接状态 |

### 配置参考

<a id="vps-configuration-reference"></a>

所有变量都使用 `VPSSRV_` 前缀.这不是装饰性的:`vps-webserver` 占用
`VPSWS_` 前缀,`Anytsl-Serve` 占用 `ANYTLS_` 前缀,三者可能同时装在一台主机上,
如果前缀共用,一个项目的 `.env` 就可能悄悄改动另一个项目的配置.

| 变量 | 含义 | 默认值 | 是否必需 |
|---|---|---|---|
| `PREFIX` | 程序安装根目录,通过安装/卸载命令设置,不从 `.env` 读取 | root 主目录中的 `apps/vps-server` | 否 |
| `VPSSRV_STATE_DIR` | 持久状态根,首次安装前在命令环境设置;`.env` 不能修改该位置 | `/var/lib/vps-server` | 否 |
| `VPSSRV_DATA_DIR` | SQLite,会话密钥和功能状态 | `$VPSSRV_STATE_DIR/data` | 否 |
| `VPSSRV_HOST` | 所有监听器的绑定地址 | `0.0.0.0` | 否 |
| `VPSSRV_PUBLIC_HTTP_PORT` | 公开可达性页面,明文 | `80` | 否 |
| `VPSSRV_PUBLIC_HTTPS_PORT` | 公开可达性页面,TLS | `443` | 否 |
| `VPSSRV_PUBLIC_ENABLE` | 首次安装是否提供公开页面 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT` | 控制台端口;`0` = 生成一次并持久化 | `0` | 否 |
| `VPSSRV_CONSOLE_PORT_FILE` | 生成的控制台端口记在哪里 | `$VPSSRV_STATE_DIR/console_port.txt` | 否 |
| `VPSSRV_CONSOLE_TLS` | 控制台是否走 HTTPS | `0` | 否 |
| `VPSSRV_AUTH` | 控制台是否要求登录 | `1` | 否 |
| `VPSSRV_PASSWORD_FILE` | 明文控制台密码;在设置中修改时需验证当前密码 | `$VPSSRV_STATE_DIR/admin_password.txt` | 否 |
| `VPSSRV_IP_ALLOWLIST_FILE` | 私有 IP 免密名单的可选路径 | `$VPSSRV_DATA_DIR/login-access.json` | 否 |
| `VPSSRV_CERT_DIR` | 自签名证书的位置 | `$VPSSRV_STATE_DIR/certs` | 否 |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | 改用操作员自备的证书 | — | 否 |
| `VPSSRV_IPERF_PORT` | iperf3 窗口监听的端口 | `5201` | 否 |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | 预填的窗口时长 | `10` | 否 |
| `VPSSRV_IPERF_MAX_MINUTES` | 控制台不可超过的硬上限 | `60` | 否 |
| `VPSSRV_IPERF_ENABLE` | 是否允许开启窗口 | `1` | 否 |
| `VPSSRV_PORTFWD_ENABLE` | 是否显示端口转发页面并允许新增转发 | `1` | 否 |
| `VPSSRV_PORTFWD_MAX_RULES` | 已配置转发规则数量的上限 | `20` | 否 |
| `VPSSRV_TRUST_PROXY` | 记录访客时是否信任 `X-Forwarded-For` | `0` | 否 |
| `VPSSRV_TRACK_CONNECTIONS` | 是否轮询 `/proc/net/tcp[6]` 以记录所有端口的连接 | `1` | 否 |
| `VPSSRV_CONN_POLL_SECONDS` | 轮询间隔 | `5` | 否 |
| `VPSSRV_MAX_TEST_MB` | 单次测速传输量上限,单位 MB | `200` | 否 |
| `VPSSRV_TEST_SECONDS` | 每个方向的测量窗口 | `10` | 否 |
| `VPSSRV_WARMUP_SECONDS` | 每个方向开始时被丢弃的预热时长 | `2` | 否 |
| `VPSSRV_DOWNLOAD_STREAMS` / `VPSSRV_UPLOAD_STREAMS` | 每个方向的并行流数 | `6` / `3` | 否 |
| `VPSSRV_PING_SAMPLES` | 用于计算延迟数值的往返次数 | `20` | 否 |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `es` | `en` | 否 |
| `PROXY_PROTOCOLS`,`PROXY_SNI` | 统一代理的初始协议集合和 TLS 名称;包含 AnyTLS | 见 `.env.example` | 否 |
| `VPSSRV_PROXY_CONFIG` | 控制台读取已安装节点集合的位置 | `/etc/vps-server-proxy/config.json` | 否 |
| `VPSSRV_PROXY_SERVICE` | 控制台检查节点存活状态的 unit | `vps-server-proxy.service` | 否 |

旧版 `ANYTLS_*` 与 `VPSSRV_ANYTLS_*` 仅供升级迁移读取,新配置不再创建独立 AnyTLS 服务.

## 从零安装

1. `git clone <repo>` 并 `cd` 进去——验证:`ls -lh third_party/sing-box/sing-box` 能看到一个约 57 MB 的文件.
2. `bash deploy/install.sh` ——首次运行直接安装 Web 控制台并打印地址和密码;需要其他服务端模块时设置 `VPSSRV_MODULES`,或安装后在 Settings → Modules 操作.
3. `systemctl status vps-server-web` ——验证:`active (running)`.
4. 在 Home 启用公开 HTTP 后,从另一台机器上打开 `http://<ip>/` ——验证:可达性页面能正常渲染,并显示出
   你自己的源 IP.
5. 在 Home 启用公开 HTTPS 后,从另一台机器上打开 `https://<ip>/` 并接受证书警告——验证:同一个页面,
   协议那一行显示为 HTTPS.
6. 打开 `http://<ip>:<console port>/` 并登录——验证:仪表盘能加载出来,并且
   iperf3 控制项显示窗口处于关闭状态.
7. 从控制台打开一个 5 分钟的 iperf3 窗口,然后在另一台机器上运行
   `iperf3 -c <ip> -p 5201 --json` ——验证:能报告出吞吐量,且输出中存在
   `mean_rtt`.
8. 如果安装了代理模块:`systemctl status vps-server-proxy` ——验证统一服务运行;在控制台创建 AnyTLS 节点后检查该节点端口与配置.

## 数据设计

已登录的 Settings 页面直接显示运行模块卡片,旧 `/settings/modules` 路径重定向到对应锚点.可选模块的安装与卸载由串行 root 辅助程序执行;`data/module-job.json` 保存任务状态,`data/module-job.log` 保存当前输出,`data/module-history.log` 追加操作历史.模块区仅在当前操作页面短时显示安装/卸载进度,最后输出后 30 秒收起,刷新或重新进入不重现完成提示.独立的 `/settings/logs` 页面汇总模块操作历史及 Web,Singbox(含节点流量与访问管理),FRPS,FRPC,Lucky,Tailscale 的 journal;服务日志可按 journal 优先级筛选.模块历史不含优先级.清空模块历史会截断本项目记录文件;清空服务日志只在 `data/log-clear.json` 写入显示截止时间,不删除整机 journal.

Home 的功能开关独立于模块安装状态.公开 Web 监听器,代理节点,Tailscale,FRPS,FRPC,端口转发和临时 iperf3 窗口占用的主机端口登记在安装目录同级的 `PORTS.md`;运行时开关和节点操作共用 `.ports.lock` 与原子写入,失败时回滚新登记,停止或删除后只释放本项目的行.Web 沙盒保持安装目录上级只读,运行时登记交给固定参数的 systemd 辅助任务.iperf3 只有窗口实际打开时登记端口,关闭或 Web 重启时释放.FRPC 组开关在停止实例前记录活跃实例,重新启用时仅恢复它们.Proxy nodes 组只控制统一 sing-box 服务.Home 的 FRPS 入口为 `/frps`,FRPC 列表入口为 `/frpc`,Tailscale 入口为 `/tailscale`;旧 `/frp` 书签重定向到 FRPC 列表.

访客数据库,`portfwd.json` 和 `login-access.json` 保存在 `$VPSSRV_DATA_DIR`.最近访问者页可通过已登录会话与 CSRF 校验清空访客数据库;清空请求本身不重新写入,后续访问及仍在连接中的设备会重新记录.控制台密码,选定端口,Web 证书及 `install-state` 保存在 `$VPSSRV_STATE_DIR`;程序安装目录可独立替换.sing-box 模块的配置及证书位于 `/etc/vps-server-proxy/`.见[路径与挂载][local-link-012].iperf3 截止时间只存于内存,重启后不会保留.

### 数据模型与文件布局

```
<project root>/
├── snapshots/                 # private snapshots; not part of the Git repository
└── repo/                      # Git working tree; paths below are relative to it
    ├── README.md              # entry point for users and documentation navigation
    ├── config/VERSION         # release version used in checkout
    ├── src/web/app.py         # web service implementation
    ├── deploy/
    │   ├── install.sh         # module-selecting installer
    │   ├── uninstall.sh       # module removal
    │   ├── systemd/vps-server-web.service
    │   ├── proxy/setup-proxy.sh
    │   ├── frps/setup-frps.sh
    │   ├── lucky/setup-lucky.sh
    │   └── tailscale/setup-tailscale.sh
    ├── src/web/static/        # first-party UI assets and vendored browser libraries
    │   └── third_party/
    │       ├── librespeed/    # speedtest.js, speedtest_worker.js
    │       └── qrcode/        # qrcode.js, qrcode-utf8.js
    ├── lang/                  # interface catalogs for web, installers, and tools
    ├── third_party/sing-box/
    │   ├── sing-box           # vendored amd64 binary
    │   ├── sing-box.version   # binary version metadata
    │   └── LICENSE            # original upstream notice
    ├── third_party/tailscale/  # pinned static-client metadata and license
    ├── third_party/nft/        # pinned Debian runtime metadata
    ├── tools/build_offline/    # checked offline asset and archive builder
    ├── tools/verify_dependencies/verify_dependencies.py # checks config/dependencies.lock.json from repo root
    ├── config/dependencies.lock.json
    ├── config/upstream-version # records: vps-webserver v0.4.1
    ├── LICENSE                # GPL-3.0
    └── doc/
        ├── DESIGN.md          # architecture, constraints, and tracked goals
        ├── LOG.md             # current status, bugs, decisions, and handoff
        ├── HISTORY.md         # historical work and prior handoffs
        ├── CHANGELOG.md       # formal version changes
        ├── THIRD_PARTY_NOTICES.md
        ├── en/               # English translation
        └── es/               # Spanish translation
```

安装后,Web 代码和浏览器资源位于 `$PREFIX/src/web/`,代理可执行文件位于 `$PREFIX/sing-box`.兼容入口 `$PREFIX/app.py` 仍是 systemd 的 `ExecStart`,但只调用 `src.web.app.main()`;资源的 HTTP URL 不变.安装与卸载脚本在检出目录中分别为 `deploy/install.sh` 和 `deploy/uninstall.sh`.v6 候选的持久状态根与安装目录分开;先前版本的目录内数据不自动迁移.

只有 `repo/` 由 Git 跟踪;`snapshots/` 独立且私有.由[README][local-link-013] 入门,使用 [LOG][local-link-014] 查阅历史验证和发布记录,并参考[第三方声明][local-link-015]了解上游构件.文档不会使快照或已安装主机变成可复现的源码检出.

SQLite 的表结构原样继承自 `vps-webserver`:只有一张 `visits` 表,会裁剪到只保留
最近的 1000 行.`portfwd.json` 是一份扁平的 JSON 规则对象列表(`id`,`label`,
`protocol`,`public_port`,`target_host`,`target_port`,`enabled`,`created`)
——见 `PortForwardManager` 在 `src/web/app.py` 中的实现.

## 已知限制与注意事项

- **绑定 80 和 443 需要 root 权限,并且这两个端口必须原本是空闲的.** 如果 nginx,
  Apache,Caddy,或者另一个 `vps-webserver` 实例已经占用了其中任意一个端口,
  安装程序会直接拒绝安装,而不是去抢占它.安装前请先用
  `ss -lntp '( sport = :80 or sport = :443 )'` 检查一下.
- **公开页面确实是公开的.** 任何猜到或扫描到这个 IP 的人都能看到它,每一次这样
  的访问都会进入访客日志.这是设计上的特性,但也意味着一个被扫描到的 IP 上的
  访客日志会在几小时内被互联网背景噪声塞满.
- **服务名称与上游隔离.** 统一代理 unit 为 `vps-server-proxy.service`;Tailscale unit 为 `vps-server-tailscale.service`,不会覆盖系统已有的标准 Tailscale unit.
- **整个离线包仅支持 x86-64 Linux.** 随附 sing-box,Tailscale 和 nftables 构件均为 amd64;安装器在修改状态前拒绝其他架构.跨发行版运行仍待目标机验收.
- **自签名 TLS 意味着每次访问 443 都会有浏览器警告.** 这是预期行为,不值得为了
  "修掉"它而加例外或 HSTS 头.
- **重启会关闭任何已开启的 iperf3 窗口.** 这是有意为之的;见前面的生命周期
  一节.
- **停止服务会撤销每一条端口转发,哪怕它是已启用的
  .** 这是有意为之的,
  和 iperf3 窗口对称;见前面端口转发生命周期一节.`systemctl restart` 或者
  重启主机会把它们直接全部带回来——`systemctl stop` 之后停在那里则不会.
- **`net.ipv4.ip_forward` 会被自动打开,且永远不会再关闭.** 这是一个
  全主机范围的单一开关;主机上的其他软件(比如 Docker)可能已经依赖它,
  所以删掉最后一条转发规则不会去动它.如果主机上没有别的东西需要它,
  就手动关掉它.
- **一条转发规则只覆盖原始 `iptables` 能看到的范围.** 如果 `ufw` 或
  `firewalld` 正在运行,并且自己也有一条默认拒绝的 `FORWARD` 策略,它们的链
  会先于这个功能追加的规则被求值,可能仍然需要为同一个端口单独加一条放行
  规则,流量才能通过.
- **sing-box 二进制超过了 GitHub 建议的文件大小.** 大约 55 MB,超过了
  50 MB 的软限制,因此每次 push 都会打印一条建议使用 Git LFS 的
  "Large files detected" 警告.Push 依然能成功;硬限制是 100 MB.未来
  sing-box 升级版本时可能最终会越过这个界限,到那时该怎么处理(用 LFS,还是
  不再随仓库分发这个二进制)应该是一个刻意做出的决定,而不是发版当天才碰到的
  意外.
- **运行脚本要用 `bash <script>`,不要用 `./<script>`.** 可执行位记录在
  git 索引里,所以一份全新的 clone 会带有这个位——但在 CIFS/SMB 挂载上的工作
  副本不会,在那上面执行 `./install.sh` 会失败,报 "Permission denied".
- **重新内嵌任何可执行文件都会丢失它的权限位.** 维护者的工作副本在 CIFS 上,
  所以在那上面解压出来再 `git add` 的文件,会被记录成 `100644`,即使上游是
  `100755`.这已经在 `sing-box` 二进制上发生过一次,并且弄坏了整个 anytls
  模块.重新内嵌之后,用 `git ls-files -s` 检查一下,并用
  `git update-index --chmod=+x <path>` 恢复这个位——在那个挂载上单独
  `chmod +x` 是没有效果的.
- **节点页面列出网卡和 Tailscale 地址.** 旧的安装时公网地址区块已移除:它在 VPS 上重复显示网卡地址,在 NAT 后也可能误导用户.设置脚本会清除旧安装留下的 `public-ip.txt`;控制台不读取它.
- **`body` 传给 `render_page()` 时** **必须**恰好包含一个顶层元素. `<main>` 使用 `display: flex`,未覆盖 `flex-direction`,因此多个顶层兄弟元素(例如每个协议一个 `<div class="card wide">`)会并排而非上下堆叠.这是 `/proxy` 页面早期版本真实发布过的缺陷,操作员报告为“布局乱了”.每个页面都用一个外层卡片包住全部内容,重复分区则在其内部以 `.node-addr` div 嵌套.
- **拆卸时需要用与安装时相同的 `PREFIX` 和 `SERVICE_NAME`.** 不带任何环境变量
  运行 `uninstall.sh` 会读取默认值,在那些路径上什么都找不到,并报告"成功",
  实际上什么都没删.安装程序结束时打印的那一行会给出填好了具体值的完整命令;
  请照抄那一行,而不是凭记忆自己敲.

## 扩展

### 扩展方法

- **新增一个模块**(安装程序可以选择性安装的其他东西):新增一个
  `deploy/<name>/setup-<name>.sh`,一个 systemd unit(放在 `deploy/systemd/` 中或由配置脚本生成),在
  `deploy/install.sh` 的模块菜单里加一个分支,并在 `deploy/uninstall.sh` 里加一个对应的
  拆卸分支.各模块之间互不调用.
- **新增一个控制台页面**:给 `ConsoleHandler` 加一个路由.不要给
  `ProbeHandler` 加路由——它的路由表几乎为空是一个安全属性,不是疏漏.
- **新增一种语言**:在每个 `lang/<component>/` 目录下添加对应的文案文件,并在 Web 语言选择器,变更日志映射,安装程序及模块脚本的词条加载器中登记语言代码,然后添加对应的 `doc/<BCP47>/` 文档目录树.
- **新增一种颜色**:在 `:root` 中加一个 token(位于 `src/web/static/style.css`),*并且*
  在 `prefers-color-scheme: light` 区块里补上对应的浅色模式的值,然后使用
  这个 token.不要在组件规则里直接写十六进制颜色值——字面量没法跟着主题走,
  所以它只在被人肉眼调出来的那个模式下是对的,在另一个模式下就是错的,而且
  没有任何机制会报告这个问题.任何被用作填充背景的值都需要一个配对的
  `--on-*` 前景色:读起来适合作为文字的值,往往并不是在白色文字背后读起来
  合适的值.提交前请在两种模式下都对照 WCAG AA(4.5:1)检查一遍;
  源码不再包含自动化测试,结构和对比度都需要人工检查.
- **刷新一个内嵌的上游依赖**:从上游的 tag 重新拷贝,在同一个 commit 里更新
  对应的 `.upstream-version` 文件,并在 [LOG.md][local-link-016] 里记一笔这次升级.
  绝不要就地手改内嵌代码——一个没有反映回上游的本地改动,会让下一次刷新
  变成一次悄无声息的回退.

[local-link-001]: HISTORY.md#当前状态与验收限制
[local-link-002]: LOG.md#缺陷
[local-link-003]: HISTORY.md#已完成工作历史
[local-link-004]: LOG.md#决策
[local-link-005]: #vps-proxy-module
[local-link-006]: LOG.md#决策
[local-link-007]: LOG.md#决策
[local-link-008]: LOG.md#缺陷
[local-link-009]: LOG.md#决策
[local-link-010]: ../config/dependencies.lock.json
[local-link-011]: THIRD_PARTY_NOTICES.md
[local-link-012]: #路径与挂载
[local-link-013]: ../README.md
[local-link-014]: LOG.md
[local-link-015]: THIRD_PARTY_NOTICES.md
[local-link-016]: CHANGELOG.md#变更日志
