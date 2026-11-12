---
name: project-log
description: 项目缺陷, 限制, 决策和交接
metadata:
  version: "2.0.0"
  lang: "zh-CN"
---

# 日志

## 多语言

**简体中文** | [English](en/LOG.md) | [Español](es/LOG.md)

## 文档

- 项目概览: [README](../README.md)

- 设计思路: [DESIGN](DESIGN.md)

- 项目状态: [LOG](LOG.md)
- 历史记录: [HISTORY](HISTORY.md)
- 变更日志: [CHANGELOG](CHANGELOG.md)

- 第三方声明: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 记录

- [历史记录](HISTORY.md)
- [变更日志](CHANGELOG.md)

## 缺陷

- [x] FRPC 保存成功但页面空响应或重命名显示 Invalid request: v5.2.2 用后台等待页和结果重试修复.
- [x] 编辑原值, 隐私控件, 删除悬浮反馈, 字体与按钮/筛选布局不一致: v5.2.2 修复, 操作员确认.
- [x] 升级时 FRPC 断开导致安装终止: v5.2.2 改为 systemd 后台安装.
- [x] Git 安装缺少 Tailscale 归档: v5.2.1 修复.
- [ ] Python 3.9, 其他目标发行版, 整机重启恢复和真实移动设备仍需独立验收.
- [ ] 已登录 Tailscale 退出及真实 Tailnet 路由策略未在本次测试机验证. v5.3.0 发布前操作员在真机确认 Tailscale 工作正常, 退出及路由策略的专项验证仍待.
- [ ] 月度配额与真实持续流量/限速策略没有在 v5.2.2 发布时重新全面验证;此前操作员确认不等于本次独立复测.
- [ ] 英语/西班牙语文档尚无独立母语审阅.
- [x] 2026-10-21 vmshell Debian 13 (KVM) 主机上节点计量服务反复重启, 日志只有 `cannot list nftables tables`, Singbox 因依赖计量被停止. 原因: 该主机镜像未装 nftables, 计量回退到随包 nft 0.9.8, 它读不了 Debian 13 iptables-nft 规则; 运行时检查只执行 `nft --version`, 安装预检因此放行. v5.4.0 修复: 检查改为读取规则表, 随附运行库换成 Debian 13 nft/iptables 及其 glibc.
- [x] 2026-11-06 在 `KVM11553` 上用 `v5.6.0-test.1` 升级时, 前台跟随安装进度的进程在开始后打印 `Terminated` 退出, 后台安装本身完成. 原因(已在容器中复现): 从控制台 root 终端运行时, 终端在 Web 单元的控制组里, 安装重启 Web 时 systemd 向整个控制组发 SIGTERM; 交互式 bash 忽略 SIGTERM, 所以 Web 停止还要等 90 秒超时. 已修复(v5.6.3): 跟随进程捕获 TERM/HUP 并说明安装仍在后台继续, 在控制台终端内运行时预先提示; 控制台关闭和退出时向终端发 SIGHUP, 重启约 1 秒完成.
- [ ] 2026-10-21 控制台 root 终端从 Web 进程派生, 继承 Web 单元的 `ProtectSystem=strict`, 不能用 apt 安装软件包或修改 `/etc`. 改为 systemd-run 独立单元的修改被 Claude Code 权限检查拦下, 未实施, 待操作员决定.

以上未勾选项为验收缺口, 不代表已复现的运行故障.

## 限制

- 已删除且没有备份的旧状态目录无法恢复, 因为原始数据已不存在.
- 仅凭本机网卡不能可靠推断 NAT 后的公网地址;本项目不查询外部公网 IP 服务.
- 任意复杂 FRP 配置不能由现有结构化编辑器无损重建;未支持字段需保留并通过原生配置管理.

## 决策

| 日期 | 决策 | 状态 | 原因 |
| --- | --- | --- | --- |
| 2026-11-05 | 主机没有能读取规则的 nftables 时, 安装器(离线版和在线版)和控制台模块任务都用 apt 自动安装 `nftables` 后再检查. | 接受 | 用户要求装 Singbox 时一并装好, 不再让用户到终端执行命令. |
| 2026-11-05 | 控制台支持 TLS 客户端证书登录: 自建 CA 按设备签发 `.p12`, 开启"要求客户端证书"后禁用密码登录, 密码只用于敏感操作的二次验证;root 可用 `client_cert.py disable` 恢复. | 接受 | 用户要求用公钥/私钥方式代替密码;IP 加自签名证书下浏览器 Passkey 不可用, 客户端证书可用. |
| 2026-11-05 | 控制台只提供 HTTPS, 忽略 `VPSSRV_CONSOLE_TLS=0`, 原 HTTP 安装升级时改为 HTTPS. 取代 2026-10-13 的"升级保留原设置". | 接受 | 用户要求强制 HTTPS. |
| 2026-10-23 | Release 提供离线版和在线版两个安装包: 离线版内置全部第三方程序与系统工具(含 iproute2), 在线版安装时下载并校验第三方程序, 缺少的系统工具用 apt 安装. | 接受 | 精简镜像没有 curl, tar, gzip, 又可能断网, 需要一个自带全部依赖的包; 联网机器只需约 4 MB 的小包. |
| 2026-10-21 | 完整离线包随附 Debian 13 nft 与 iptables-nft 及其 glibc, 经自带加载器运行; 主机上能读取规则的 nft/iptables 优先. 取代 2026-10-04 的 Debian 11 运行库. | 接受 | 旧 nft 0.9.8 读不了 Debian 13 iptables-nft 写入的规则, 新版程序又不能直接用旧 glibc 运行. |
| 2026-10-13 | 全新安装的控制台默认使用 HTTPS 和自签名证书; 升级保留原设置. 开启 HTTPS 时会话 Cookie 带 `Secure`. 升级保留部分已被 2026-11-05 的强制 HTTPS 取代. | 接受 | 自签名证书不能证明服务器身份, 但能防止密码和会话被明文窃听. |
| 2026-10-13 | 对 10 个未合并的旧本地分支(`archive/*` 3 个, `feat/two-stage-setup`, `fix/frpc-unicode-name`, `refactor/feature-modules`, `refactor/feature-modules-repo`, `release/v4.0.0`, `release/v4.1.0-test.1`, `test/host-validation-wip`)使用 `git branch -D`. 豁免 all-in-one Git 规范 `分支和历史` 规则 2 的"禁止 `git branch -D`", 范围仅限这些分支, 一次性. | 接受 | 用户确认这些分支已废弃, 末端 SHA 已记录在本地私有笔记. |
| 2026-10-07 | 顶栏左上角只显示项目名称, 不显示项目标志. 豁免 all-in-one Web UI 用户约定 `页面框架和导航` 规则 2 的"左上角必须显示项目标志和名称", 范围仅限共享顶栏, 浏览器标签页图标不变. | 接受 | 用户在当前对话中明确要求, 认为标志显示效果不好. |
| 2026-10-05 | 按最新模板重写 18 份文档, 保留原始第三方许可. | 接受 | 用户要求整体重写, 原始许可仍承担分发声明义务. |
| 2026-10-05 | 安装和 FRPC 更新使用后台任务. | 接受 | 服务重启可能中断承载安装或保存响应的连接. |
| 2026-10-04 | 持久状态采用独立布局 1. | 接受 | 替换代码目录不能删除凭据和配置. |
| 2026-10-04 | 自动迁移 v5.1.0 及更早布局. | 拒绝 | 旧目录包含混合状态, 无法安全假定路径和归属. |
| 2026-10-04 | AnyTLS 纳入统一 Singbox 服务. | 接受 | 统一节点管理与流量策略, 移除重复控制路径. |
| 2026-10-04 | 完整离线包包含 nft 运行库及对应源包. | 接受 | 固定服务构件不足以补齐缺失系统库, 基础系统仍为前提. |
| 2026-10-03 | 移除自动测试目录, 按变更做工具检查和人工验收. | 接受 | 遵循操作员明确要求. |
| 2026-09-19 | 转发使用内核 DNAT 与项目 JSON 重放. | 接受 | 避免用户态转发开销和对全局规则集的接管. |
| 2026-09-12 | 采用 GPL-3.0-only, 保留组件独立声明和[合规审查](THIRD_PARTY_NOTICES.md#合规审查). | 接受 | 分发包含 GPL 代理核心, 项目作者按该许可公开本项目. |
| 2026-09-21 | 提示函数以显式 `return 0` 结束. | 接受 | 最后一个空值测试可在 `set -e` 下静默终止安装. |
| 2026-09-12 | 公开页面和控制台使用独立监听器与路由. | 接受 | 公开处理器不包含管理路由, 控制台保留独立随机端口. |
| 2026-09-12 | iperf3 使用限时窗口, 不提供常驻服务. | 接受 | 限制未经安排的持续带宽消耗. |
| 2026-09-12 | 公开 HTTPS 使用自签名证书, 不依赖 ACME. | 接受 | 页面检查 IP/端口可达性, 不要求域名与续期. |
| 2026-09-12 | 本作者项目使用随附副本, 不使用子模块或归档原项目. | 接受 | 三个项目独立维护, 导入修订在来源文件中记录. |

## 交接

当前分支: `main`, 与 `origin/main` 同步. 当前正式版本: v6.2.1(标签 `v6.2.1`, GitHub Release 含离线版, 在线版安装包与 `SHA256SUMS`). 服务机 `ubt-sev` 运行 v5.5.1(HTTPS 28211 端口, 模块 web), 本次未部署.

已完成: v5.7.0 发布, 变更见 `doc/CHANGELOG.md`: 登录失败封禁开关(关闭时只标记), 逐次加长的封禁, IPv6 按 /64 计数和全局上限, 反向代理下取最后一个 `X-Forwarded-For` 项, CSP 和禁止嵌入的响应头, 控制台访问限制(`src/web/console_access.py`), 登录设备与闲置超时, 安全记录和 Bark 登录提醒(`src/web/security_events.py`); 管理员密码按用户决定继续明文保存. 发布前的测试预发布为 `v5.7.0-test.1` 和 `v5.7.0-test.2`(后者整理了安全卡片排版). v5.6.3 发布, 变更见 `doc/CHANGELOG.md`: pcre2 安全更新, `Terminated` 修复, 证书四步导入说明, 上游二进制移出 Git. v5.6.2 发布, 随附组件升到 Tailscale 1.104.5(修复 TS-2026-014 至 017), sing-box 1.13.21, frp 0.72.0, 并在升级时替换本项目安装的旧 FRPC 客户端; 在一次性 Debian 13 容器中从 v5.6.1(含 web, proxy, frps, tailscale 与 FRPC 实例)原地升级验证: 各服务运行, 版本正确, FRPC 被替换且标记更新, 五种协议节点监听, shadowsocks/trojan/vless 实际转发 HTTPS 成功, frpc 到 frps 隧道可用, 完全卸载无残留; Tailscale 只验证守护进程运行, 未登录 Tailnet. v5.6.1 发布, 只把前端 vue-i18n 升到 11.4.18 以消除两个 XSS 公告(现有代码不可利用), 发布说明强烈建议升级; v5.6.0 发布, 变更见 `doc/CHANGELOG.md`: 控制台只提供 HTTPS; TLS 客户端证书登录(`src/web/client_cert.py`, 设置 > 安全 > 客户端证书, 要求证书后密码只作敏感操作的二次验证); 主机缺少可用 nftables 时安装器和控制台 Singbox 安装任务自动 apt 安装; 安装器在 web 模块缺少 openssl 时用 apt 安装. 发布前的测试预发布为 `v5.6.0-test.1`.

检查结果: `check_project.py` 通过(含 `npm run check`). 本机端到端脚本验证了签发, mTLS 证书登录, 无证书时拦截, Clash 订阅不受拦截, 要求期间拒绝密码登录和撤销当前证书, `client_cert.py disable` 恢复, 撤销后不再接受. 操作员在 vmshell 主机 `KVM11553` 上用 `v5.6.0-test.1` 离线包原地升级, 在 Windows Chrome 上完成证书签发, 导入, 弹出证书选择, 证书登录并开启要求, 确认测试通过. 远程探测确认该主机控制台在 TLS 1.2 和 1.3 下都发出证书请求.

未验证: 真实主机上 apt 自动安装 nftables/openssl(该主机 Singbox 原已安装); HTTP 安装升级为 HTTPS 的过程; macOS, Android, iOS 导入 `.p12`(OpenSSL 3 默认 AES-256 加密, 很旧的系统可能不支持); 无证书设备被拦截, 开启要求后终端二次验证和 Clash 订阅在真实设备上的表现(操作员只概括确认通过).

依赖审查(2026-11-06): npm 依赖 0 个已知漏洞; Tailscale, sing-box, frp 已在 v5.6.2 升级. Lucky 2.27.2, iperf3 3.22, xterm.js 6.0.0, qrcode-generator js2.0.4 为各自最新或同大版本最新; LibreSpeed 6.3.1 的安全项只涉及 PHP 后端镜像. nft 运行库 2026-11-06 逐包对照 trixie, trixie-updates, trixie-proposed-updates 和 trixie-security 的当前索引, 只有 pcre2 有安全更新(此前快照只取了主仓库, 漏了 security 仓库), 已更新.

真机验证(2026-11-06): 操作员在一台 VPS 上用 v5.6.3 离线包经 SSH 原地升级, 后台退出码 0, `vps-server-web` 为 active, 版本 5.6.3, 安装的 pcre2 库为新版本. 随后在控制台自带的终端里再次升级: 预先显示了终端会断开, 安装在后台继续的提示, 不再只打印 `Terminated`; 重新登录后后台退出码为 0. 新证书导入页尚未在真机确认.

真机验证(2026-11-08): 操作员在局域网测试机上联网安装 `v5.7.0-test.1` 和 `v5.7.0-test.2`, 确认失败计数, 关闭封禁时只标记, 开启时第 6 次被拒并提示剩余秒数, 以及新排版正常. 未验证: 真实 Bark 推送, 真实反向代理后运行, 控制台访问限制在真机上开启和用恢复命令关闭. v5.7.0 同时发布了 README 和安装器解压显式使用 `tar` 过滤器的修复(已在 Python 3.13, 3.14 和无过滤器环境验证).

剩余步骤: v5.6.3 已发布以下改动, 其中证书导入步骤未在 macOS, Android, iOS 实测: `Terminated` 修复(见缺陷); 证书生成页改为四步导入说明(下载不等于导入, 各系统导入方法, Firefox 单独证书库, 完全退出浏览器, 确认后再开启要求), 安全设置在有证书但当前连接未出示时提示原因; 上游二进制(sing-box, frps, frpc, Lucky, Tailscale 归档)不再提交到 Git, 构建离线版时按 `config/online-assets.json` 下载校验, `build_offline.py` 不再需要 `--tailscale-archive`; nft 运行库的 pcre2 换成 trixie-security 的 10.46-1~deb13u3(GHSA-r9hj-j2rw-4q3m, JIT 栈分配过大), 其余 31 个包与 Debian 13 当前版本一致. 历史提交中仍保留旧二进制, 未改写历史. 控制台 root 终端是否改为在 Web 沙箱外运行, 待操作员决定(见缺陷). 离线包约 167 MB, 可考虑只随附 `ip`. `tokens.css` 中的 `compat-*` 数字标记缺少语义名称. 英语/西班牙语文档尚无母语审阅. Singbox 关闭端口时不区分规则归属, systemd 环境值未加引号, 升级失败不自动回滚程序, 旧 `.py` 不清理, 待决定是否处理.

v5.8.0 已发布(变更见 `doc/CHANGELOG.md`, 测试预发布 `v5.8.0-test.1`): 客户端证书改用随附的静态 OpenSSL 3.5.9 LTS(`third_party/openssl/`, 安装到 `vendor/openssl/`)和项目自带的最小配置; 起因是一台主机的 OpenSSL 1.1.1k 把系统 openssl.cnf 的 v3_ca 与 `-addext` 合并, 颁发机构写了两次 Basic Constraints, 连自验证都失败(本机用 1.1.1k 复现). 颁发机构须先通过主机 TLS 库上的双向 TLS 自检, 不通过时换新并撤销其旧证书; 新增 `client_cert.py check`. 安装器新增 core 检查: Bash 4.1, systemd 240, SQLite 3.24, Python 用的 OpenSSL 库 1.1.1, `/usr/bin/python3` 3.9+, 基础命令, 在线版 CA 证书; `ip`/`ss` 能力不足时改用随附版本, 主机 iperf3 须 3.1+. 已验证: `check_project.py` 通过; Debian 11 容器(Python 3.9.2, libssl 1.1.1w)core 检查通过, 随附和系统 openssl 签发均通过自检. 未验证: 出问题的那台主机实机; 主机 libssl 为 1.1.1k 时的握手自检; 完整安装流程. 另: Debian 11 的 security 源已移到 archive.debian.org, 未改源的主机无法 apt 更新.

v5.8.0 同时发布 FRPS 流量统计和限制, 逻辑与 Singbox 节点相同(`src/web/frps_meter.py`): 计量 bindPort(所有 frpc 隧道流量经过它), 复用 `node_accounting` 与 `node_meter` 规则(独立表 `vps_server_frps`, 状态 `/etc/vps-server-frps/traffic.json`, 服务 `vps-server-frps-meter.service`, FRPS `Requires` 它, 计量失败时停止 FRPS); FRPS 页面显示用量并用与节点相同的限制对话框编辑; FRPS 模块因此需要 nft. 已验证: `check_project.py` 通过; 假后端单元测试(计数, 配额后限速, 端口随 frps.toml 变化); Debian 13 容器真实 nft 下计数准确, 封禁生效. 未验证: 真机上 1 Mbps 限速实测(回环测试不准), 控制台页面实际显示, 安装/卸载流程. 已知: 修改 bindPort 后最多约 2 秒新端口未计量.

真机验证(2026-11-08): 操作员在 vmshell 主机 `KVM11553`(主机 TLS 库 OpenSSL 3.5.7)用 `v5.8.0-test.1` 离线包从控制台终端原地升级, `client_cert.py check` 显示随附 openssl 且原 CA 自检通过; 证书签发与登录, FRPS 流量卡片与配额限制等测试操作员确认一切正常. 仍未验证: 主机 TLS 库为 OpenSSL 1.1.1k 的那台主机.

域名转发(已于 v6.0.0 发布, 2026-11-10, `bafc692` 起): 新增 `caddy` 模块, 按子域名把 HTTPS 转发到本机端口, 随附 Caddy 2.11.9 占用 80/443 并自动申请证书, Cloudflare API 维护 A/AAAA 记录; 开启时公开可达性页面让出 80/443. 同期: Lucky 管理页经控制台 `/lucky/` 显示, 管理端口只允许本机连接(`lucky_guard.py`), 修复 Lucky 开启 HTTPS 后的循环跳转, 修复在线版把按目录存放的 CA 误判为缺失(`0e52e3b`). 已验证: `check_project.py` 通过; 一次性 Ubuntu 24.04 系统容器中安装, 转发(`*.localhost` 内部证书), HTTP 跳转, 未知域名断开, 删除, 开关模块时探测页和 `PORTS.md` 交接, 控制台卸载/重装, 安装器重跑, 完整卸载无残留; Cloudflare 同步逻辑用模拟接口验证. 测试版 `test-0e52e3b` 已用在线包升级部署到一台 VPS, 全部模块运行. 未验证: IPv6 记录, ufw/firewalld 开启时放行 80/443.

后续(2026-11-10 至 11-11, 已于 v6.0.0 发布): Lucky 模块移除(升级时归档并清理); 控制台可挂到域名和本机 IP(Caddy 校验客户端证书, IP 证书为 Let's Encrypt 6 天证书); 站点启停, 编辑, 后端 HTTPS 与 Host 选择, 访问日志, 变更记录, Bark 通知, 其他域名, IP 白名单, 基本认证. 已验证: 一次性容器中各项功能与从 `c6356ea` 升级; 测试主机上用真实 Cloudflare 区域和 Let's Encrypt 签发验证了子域名, 其他域名, 基本认证, 白名单, 启停, 访问日志和删除时清理 DNS, IP 证书与客户端证书访问. 未验证: 6 天 IP 证书的自动续期, Bark 通知的真实推送(只用模拟发送验证), 泛域名证书与证书导出(未实现, 需要带 DNS 插件的 Caddy 或自行实现 ACME DNS 验证). 2026-11-11: IP 证书改为只供控制台原端口使用(80/443 不再对裸 IP 提供控制台, 控制台读取 Caddy 存储中的证书并在文件变化时换上), 强制重签一次验证了无路由时 HTTP-01 签发和控制台自动换用; 域名表单改为分行布局和统一字号.


v6.1.0(2026-11-11, `706962b` 至 `9f3faf4`): 客户端证书一键设置文件(`src/web/cert_setup.py`, Windows .cmd, macOS 描述文件, Linux 脚本, 浏览器策略 `AutoSelectCertificateForUrls`), 签发页把一键设置放在第一步; 新 CA 和设备证书名带主机名; 证书包改用 SHA1/3DES 以便 macOS 导入; 域名转发站点卡片按钮统一. 验证情况见 `doc/CHANGELOG.md`. 测试主机此前运行 `test-9f3faf4`(按文件复制部署).
v6.2.0(2026-11-12, `a02b7a8` 至 `661dc00`): 迷你网盘(`src/web/file_share.py`, `src/web/features/files.py`, 数据在 `data/files/`, 默认关闭); IP 证书独立为首页卡片(`ipcert`, 域名转发的开关存于 `/etc/vps-server-caddy/domains-enabled`); Caddy 运行时公开可达性页面由 Caddy 返回(`caddy_sites.probe_handler()`); 首页"公开页面"一个开关(`web_public` 任务); 多个 Cloudflare 令牌(`cloudflare-tokens.json`). 验证情况见 `doc/CHANGELOG.md`. 英语/西班牙语 README 和 DESIGN 此前缺少域名转发相关内容, 本次从 `bafc692` 之前的版本起同步.

v6.2.1(2026-11-12, `17897ca`, `5d09097`): Caddy 的控制台站点保留访问者的 Host(此前为 `127.0.0.1:端口`, 迷你网盘链接, Clash 订阅, 网页终端来源检查因此出错); Caddy 运行时"公开页面"链接改用本机公网 IPv4. 验证见 `doc/CHANGELOG.md`.
临时项目规则: 未发现.
