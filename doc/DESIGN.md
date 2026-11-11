---
name: project-design
description: 项目架构与设计约束
metadata:
  version: "2.0.0"
  lang: "zh-CN"
---

# vps-server — 设计

## 多语言

**简体中文** | [English](en/DESIGN.md) | [Español](es/DESIGN.md)

## 文档

- 项目概览: [README](../README.md)

- 设计思路: [DESIGN](DESIGN.md)

- 项目状态: [LOG](LOG.md)
- 历史记录: [HISTORY](HISTORY.md)
- 变更日志: [CHANGELOG](CHANGELOG.md)

- 第三方声明: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## 设计目标

- [x] 用一个认证控制台管理按需启用的网络工具和独立服务.
- [x] 将可替换代码与持久状态分离, 在同一数据布局内保留配置升级.
- [x] 通过受限的权限辅助程序执行服务, 端口和网络规则变更, 提供可查询的后台任务结果.
- [x] 支持简体中文, 英语和西班牙语, 并随附固定摘要的客户端资源.

非目标: 通用容器平台, 任意 FRP 配置编辑器, 自动查找公网 IP, 完全锁定目标操作系统软件包.

## 架构

浏览器通过 Python 标准库 HTTP 服务访问页面与认证接口. `src/web/features/` 按功能提供处理器;独立 systemd 服务运行 Singbox, FRPS, FRPC, Caddy 和 Tailscale. Web 服务使用系统保护选项, 把有限的特权操作交给 root 辅助程序;浏览器终端经过单独的密码验证后运行 root PTY.

安装器在语言选择后启动 `vps-server-install` 后台任务, 前台跟随任务的 `summary.log`, 只显示关键步骤, 地址密码和失败原因. 停止任何服务前检查 Python 版本和主机基础组件的最低版本(`core` 检查: Bash, systemd, SQLite, Python 使用的 OpenSSL 库, 基础命令);各模块的主机条件(nft 能读取规则表, `/dev/net/tun`, 已有 tailscaled, iptables 与 `ss`/`ip`)由 `src/web/host_checks.py` 统一判断, 安装器, 控制台模块任务和未安装模块卡片共用同一结果代码. 控制台安装模块时以 `VPSSRV_MODULE_ONLY=1` 只安装所选模块, Web 和其他模块保持运行. FRPC 保存/重命名先返回等待页, 后台验证并应用配置, 延迟重启实例;状态查询在隧道中断后重试, 成功与失败均以实际任务结果为准.

| 目录 | 职责 |
| --- | --- |
| `.local/` | Git 忽略的维护资料, 历史快照与私有笔记;不参与部署. |
| `.github/` | 持续集成检查和 Actions 依赖更新配置. |
| `src/` | Python 后端, 功能处理器与固定静态资源. |
| `web/` | Vue 共享组件, 设计标记, 功能样式与前端构建配置. |
| `deploy/` | 安装, 卸载, 模块配置脚本与 systemd 模板. |
| `config/` | 版本, 固定依赖摘要及导入来源记录. |
| `lang/` | 界面与安装器翻译;配置值 `zh_cn` 对应简体中文. |
| `third_party/` | 上游可执行文件, 归档, 许可及来源记录. |
| `tools/` | 样式构建, 依赖校验与离线包构建工具. |
| `doc/` | 设计, 状态, 历史, 变更, 第三方声明及译文. |

前端位于 `web/`, 使用 Vue 3, Vite, TypeScript, Tailwind CSS 和 shadcn-vue 模板组件增强服务器页面. Python 继续生成业务表单, 处理认证和权限;Vue 共享顶栏, 底栏, 页头, 卡片集合, 设置分区导航, 主题列表框与模式分段控件. 页面跳转仍使用同源完整导航, 不绕过服务器权限.

`web/src/styles/tokens.css` 是设计数值的唯一来源;功能样式位于 `web/src/styles/legacy/`, 用语义标记对接现有表单. `npm ci && npm run check` 在 `web/` 检查设计, 类型和生产构建, 输出 `web/dist/ui.js` 与 `ui.css`;安装器复制到静态资源目录, 离线包携带已编译文件, VPS 不需要 Node.js. 构建附带 `web/dist/licenses/` 中的依赖原文和版本清单. Git 忽略构建输出及依赖目录.

`.github/` 运行相同检查, `.claude/settings.json` 在编辑后运行模板设计检查. `tools/check-project/check_project.py` 另检查 Python/Bash/JavaScript, 翻译, 文档和固定构件. `tools/build-offline/build_offline.py` 生成两个安装包: 离线版(默认)内置全部第三方程序和 Debian 13 运行库(nft, iptables, `ip`, `ss`); `--variant online` 的在线版不含大型二进制, 安装时由 `src/web/online_assets.py` 按 `config/online-assets.json` 下载并逐个校验 SHA-256. 这些上游二进制不提交到 Git, 构建离线版时用同一模块下载到 `third_party/`(被 Git 忽略)再打包;nftables 运行库和对应源码由 `fetch_assets.py` 下载并核验. 两个包的安装和解压只依赖 python3, 不依赖 curl, tar, gzip 或 Git. 版本来自后端实际构建标识, 作为组件属性传入;正式变更日志继续取自三语言 CHANGELOG.

## 设计约束

- **必须**在认证与权限复验后提供敏感数据;初始 HTML **禁止**包含隐藏的真实凭据. 编辑已有对象**必须**载入原值, 不能用空白字段覆盖未修改值.
- 端口**必须**先锁定并登记归属再启用监听;失败时释放新增登记, **禁止**抢占其他项目的登记.
- FRP 修改**必须**先验证, 失败时保留或尽可能恢复原配置;高级非受管配置**禁止**被结构化编辑器丢弃.
- 流量配额按 `(上传 + 下载) × 2` 计入;读取计量失败**禁止**被当作达到配额. 周期重置**必须**同步重建内核 quota.
- FRPS 与节点使用同一套计费和 nft 规则, 按 bindPort 计量(`src/web/frps_meter.py`, 独立表 `vps_server_frps`);FRPS 服务依赖计量服务, 计量失败时**必须**停止 FRPS.
- 客户端证书**必须**用随附的 openssl 和项目自带的最小配置签发; 证书包**必须**用 SHA1/3DES 加密和 SHA1 MAC 导出(OpenSSL 3 默认的 AES/PBKDF2 在 macOS 上报密码错误);新的证书颁发机构**必须**先在主机 TLS 库上通过双向 TLS 自检.
- 新签发的 CA 和设备证书的 CN 带主机名(只保留 ASCII 字母数字, 点和横线);已有 CA 不改名, 改名会使已发证书失效. 设置文件由 `cert_setup.py` 生成, 带证书的版本只在签发页提供: Windows 是 .cmd 加内嵌 PowerShell, 只写当前用户的证书库和 HKCU 策略, 不需要管理员权限, 私钥导入为不可导出; macOS 是用户范围的描述文件(PKCS#12 载荷不含密码, 安装时由系统询问, 加 Chrome 和 Edge 的策略载荷); Linux 是 bash 脚本, 用 pk12util 导入到 `~/.pki/nssdb`, 并用 sudo 合并各浏览器策略目录下的 `vps-server.json`, 保留其他条目.
- iperf3 服务端**必须**限时运行, Web 停止时关闭临时进程与本项目转发规则. **禁止**重置整个主机的 `ip_forward` 或删除其他程序的防火墙规则.
- TLS 握手**必须**在各连接的工作线程中完成并设置超时;在接受连接的线程中握手会让空闲连接阻塞整个监听器.
- 重启 Web 期间**禁止**持有 `.ports.lock`;新 Web 进程启动时通过同一锁释放残留登记.
- 单模块安装**禁止**停止, 重装或禁用其他模块的服务.
- 公开监听器与控制台路由边界**必须**分离. 信任代理地址头时**禁止**依赖其地址进行 IP 免密认证.
- 信任代理地址头时, 客户端地址**必须**取代理追加的最后一个 `X-Forwarded-For` 项; 左侧各项可被客户端伪造, **禁止**用于封禁和访问限制.
- 控制台页面**禁止**使用内联脚本和内联事件属性; 响应默认带 `script-src 'self'` 的 Content-Security-Policy 和禁止嵌入的头. 内联样式保留允许, 因为 xterm.js 和 UI 在运行时设置样式.
- 控制台访问限制在 TLS 握手前按来源地址断开连接, 本机回环地址始终允许; 设置文件变化后立即生效, 文件损坏时按关闭处理, 以免把所有人挡在外面.
- 控制台**必须**只提供 HTTPS. 客户端证书由控制台自建 CA(`certs/client-ca.*`)签发, 服务器**禁止**保存设备私钥;TLS 层只请求不强制证书(`CERT_OPTIONAL`), "要求证书"在 HTTP 层逐请求检查并核对未撤销的序列号, 以便 Clash 订阅照常访问, 撤销无需重建 TLS. 开启要求前当前连接**必须**已出示有效证书, 要求期间**禁止**撤销当前连接使用的证书.
- 同布局安装**必须**保留持久状态;旧布局或缺失定位文件**禁止**被当作空白安装自动覆盖.
- 第三方构件**必须**核验固定摘要并携带原始许可与对应源码获取方式. 文件身份校验不代表系统依赖完全锁定.

## 设计标记

采用最新 Web UI 起始模板的字号, 字重, 行高, 间距, 圆角, 阴影, 容器, 八主题色与动效标记. 共享组件直接来自模板;顶栏和页头使用真实同源链接以保留 Python 路由. `tokens.css` 追加 `compat-*` 标记, 仅用于网络模块已有表格/对话框的尺寸和状态变体;字号, 字重, 圆角和主题色已统一到模板标记. `--toast-lifetime-error` 为失败 Toast 的显示时长(8 秒). 保存失败后服务器带 `msg` 参数重定向回页面时, 前端用 Toast 显示页面内的错误提示并移除页面内的副本. 新组件和页面只引用标记. 检查命令: `cd web && npm run check`.

## 数据设计

| 位置 | 数据 |
| --- | --- |
| `/var/lib/vps-server` | 默认状态根, 布局 1;由 `/etc/vps-server/state-dir` 定位. |
| `admin_password.txt`, `console_port.txt`, `.env`, `paths.json`, `.layout-version` | 认证, 固定端口, 配置及路径/布局元数据. |
| `certs/` | TLS 证书与私钥;客户端证书 CA(`client-ca.pem`, `client-ca.key`)与签发记录 `client-auth.json`(要求开关, 序列号, 设备名, 撤销状态). |
| `data/` | SQLite 访客库, 会话与签名密钥, 功能状态, 节点清单和后台任务; 登录安全设置(`login-ban.json`, `console-access.json`, `alerts.json`), 安全记录(`security-audit.jsonl`)和登录过的地址(`known-logins.json`). |
| `/etc/vps-server-proxy/config.json` | Singbox 运行配置;节点身份与策略由受管清单协调. |
| `/etc/vps-server-frps/frps.toml` | FRPS 服务端配置. |
| `/etc/vps-server-frps/traffic.json`, `traffic-meter.json` | FRPS 流量条目(配额, 限速, 有效期, 用量)与计量账本. |
| `/etc/frp/frpc-<name>.toml` | FRPC 实例配置;非 ASCII 名称映射到稳定的 unit 别名. |
| `/etc/vps-server-caddy` | 域名转发: 站点清单 `sites.json`, Cloudflare 令牌 `cloudflare-token`(均为 `0600`), DNS 同步结果 `dns.json`, 生成的 Caddy 配置 `caddy.json`. |
| `/var/lib/vps-server-caddy` | Caddy 的证书和 ACME 账号, 归 `vps-server-caddy` 用户. |
| `~/apps/PORTS.md`, `~/apps/.ports.lock` | 主机端口归属清单与互斥锁. |

状态文件按敏感等级限制权限, Web 不把备份或配置作为静态资源公开. FRPC 任务文件 `data/frp-jobs/*.json` 权限为 `0600`, 执行前移除请求凭据, 结果以任务状态保存. 转发规则保存为项目 JSON 并在启动时重放, 不保存整个主机规则集. 安装前备份和人工恢复流程见 README.

## 外部接口

- Web 页面与表单只面向本项目管理操作;受保护的显示/复制接口在认证后返回敏感值. `/frp/client/structured` 和 `/frp/client/rename` 是 POST 操作, 不是独立展示页.
- LibreSpeed 客户端使用 `/speedtest/garbage`, `/speedtest/empty`, `/speedtest/getip` 与原创 Python 后端交互;结果反映当前客户端到服务器的链路.
- 权限辅助程序通过白名单动作调用 systemd, FRP 验证器, nft/iptables 与安装器;不提供任意命令执行 API. root PTY 仅供经过密码复验的终端会话.
- FRPC 连接用户指定的服务器, 结构化编辑只支持简单 token 认证 TCP/UDP 代理.
- Tailscale CLI 与本机守护进程通信, 登录和路由审批由控制服务器/Tailnet 处理.
- Lucky 模块已移除, 由域名转发取代: 安装器升级时调用 `module_manager.remove_legacy_lucky()`, 先把 `/etc/vps-server-lucky` 归档到状态目录, 再停止服务, 删除 nft 表, 本项目放行的防火墙规则, 端口登记和程序文件.
- 域名转发(`caddy` 模块)由 `src/web/caddy_sites.py` 管理: 控制台经 `systemd-run` 以 root 调用它修改站点和令牌, 它生成 Caddy 原生 JSON 配置(每个域名一条到 `127.0.0.1:<端口>` 的反向代理, 其他域名和直接用 IP 访问一律断开连接), 再通过 Unix 套接字上的管理接口热加载. Caddy 以 `vps-server-caddy` 用户运行, 只有绑定低端口的能力, 证书由它自己的自动 HTTPS 用 HTTP-01/TLS-ALPN-01 申请, 因此需要 80 和 443, 也不支持泛域名. Caddy 服务启用时, `public_listener_enabled()` 一律读作关闭, 公开可达性页面让出 80/443, `PORTS.md` 中两行改登记给 Caddy; 关闭或卸载模块时按原开关还给公开页面. DNS 记录用 Cloudflare API 维护(A, 有公网 IPv6 时加 AAAA, 仅 DNS): 添加站点时立即同步, `vps-server-caddy-dns.timer` 每 5 分钟比较本机地址, 地址变化, 上次失败或距上次检查超过一小时才请求 Cloudflare. 本机地址取自内核为外部路由选择的源地址, 只接受公网地址, 不请求外部服务.
- 站点端口等于控制台端口时, 该域名指向控制台本身: Caddy 对这个域名请求客户端证书(`verify_if_given`, 用控制台客户端 CA 的副本 `/etc/vps-server-caddy/client-ca.pem` 校验), 经回环 TLS 连接控制台, 并覆盖写入三个请求头: 只有 root 和 Caddy 能读到的 `proxy-key` 密钥, 证书序列号, 访问者地址. 控制台只在连接来自回环地址且密钥匹配时采信这些头: 用序列号查自己的证书记录(吊销照常生效, 是否必须出示证书仍由控制台决定), 用访问者地址做登录封禁, 访问地址限制和安全记录; IP 白名单登录和只限内网的 Clash 订阅对这类请求不可用. 控制台的连接级访问限制因此放行回环地址, 改为逐个请求检查. 控制台端口或客户端 CA 变化时, DNS 定时任务会重新生成并热加载 Caddy 配置.
- 每个站点可以停用(从 Caddy 配置中移除, DNS 记录和证书保留)和编辑(目标端口或控制台, 后端是否 HTTPS, 发给后端的 Host). 后端为 HTTPS 时不校验其证书; Caddy 对 HTTPS 后端默认改写 Host, 所以两种 Host 选择都显式写入配置. Caddy 把所有站点的访问日志写到 `/var/lib/vps-server-caddy/logs/access.log`(JSON, 5 MB 轮转, 保留 2 份), 控制台的 `/domains/log` 按域名从文件末尾读取最近 200 条. 站点变更, DNS 记录增删改, 本机 IP 变化和同步失败追加到 `/etc/vps-server-caddy/dns-history.jsonl`(保留最近 200 条). IP 变化, DNS 同步失败和证书临近过期(域名少于 7 天, IP 少于 1 天)通过控制台已有的 Bark 设置推送, 同一事件一天最多一次(`alerts-sent.json`); 检测不到任何公网地址时不视为 IP 变化.
- 站点还可以有其他域名(最多 8 个, 与主域名同一目标, 各自有 DNS 记录和证书, 不能与其他站点重复), 允许访问的地址或网段(最多 32 条, 其他来源返回 403, 按连接地址判断), 以及基本认证(用户名和至少 8 位密码; 密码经 `caddy hash-password` 从标准输入生成 bcrypt 哈希, 只保存哈希, Caddy 缓存校验结果). 指向控制台的站点不设基本认证, 由控制台自己登录. 编辑时去掉的其他域名会删除其 DNS 记录.
- "IP 访问的 HTTPS 证书"开关加入一个 `ip` 站点(本机公网 IPv4). Caddy 只为它申请和续期证书(`tls.certificates.automate`), 不建路由: 80/443 对裸 IP 不提供任何内容, 控制台仍只在随机端口. Let's Encrypt 只用 `shortlived` 配置签发 IP 证书(约 6 天, 由 Caddy 按续期信息自动续), 只能用 HTTP-01/TLS-ALPN-01 验证, 这两种验证由 Caddy 在 80/443 上处理, 不需要路由. 控制台以 root 运行, 直接读 Caddy 存储里的证书和私钥(`caddy_sites.ip_certificate()`), 每 30 秒查一次站点, 证书文件变化时重建 TLS 上下文, 读不到时退回自签名证书; 用 `VPSSRV_TLS_CERT` 指定的证书优先. IP 站点不建 DNS 记录, 本机地址变化时 DNS 定时任务改写站点.
- 地址来自本机网卡及已配置的 FRPC 服务器地址, 安装器不请求外部服务查询公网 IP.
