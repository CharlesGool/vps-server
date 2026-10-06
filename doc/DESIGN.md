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

浏览器通过 Python 标准库 HTTP 服务访问页面与认证接口. `src/web/features/` 按功能提供处理器;独立 systemd 服务运行 Singbox, FRPS, FRPC, Lucky 和 Tailscale. Web 服务使用系统保护选项, 把有限的特权操作交给 root 辅助程序;浏览器终端经过单独的密码验证后运行 root PTY.

安装器在语言选择后启动 `vps-server-install` 后台任务. FRPC 保存/重命名先返回等待页, 后台验证并应用配置, 延迟重启实例;状态查询在隧道中断后重试, 成功与失败均以实际任务结果为准.

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

前端位于 `web/`, 使用 Vue 3, Vite, TypeScript, Tailwind CSS 和 shadcn-vue 模板组件增强服务器页面. Python 继续生成业务表单, 处理认证和权限;Vue 共享顶栏, 页头, 卡片集合, 设置分区导航, 主题列表框与模式分段控件. 页面跳转仍使用同源完整导航, 不绕过服务器权限.

`web/src/styles/tokens.css` 是设计数值的唯一来源;功能样式位于 `web/src/styles/legacy/`, 用语义标记对接现有表单. `npm ci && npm run check` 在 `web/` 检查设计, 类型和生产构建, 输出 `web/dist/ui.js` 与 `ui.css`;安装器复制到静态资源目录, 离线包携带已编译文件, VPS 不需要 Node.js. 构建附带 `web/dist/licenses/` 中的依赖原文和版本清单. Git 忽略构建输出及依赖目录.

`.github/` 运行相同检查, `.claude/settings.json` 在编辑后运行模板设计检查. `tools/check-project/check_project.py` 另检查 Python/Bash/JavaScript, 翻译, 文档和固定构件. 离线包由 `tools/build-offline/build_offline.py` 生成, 固定资产由 `fetch_assets.py` 核验. 版本来自后端实际构建标识, 作为组件属性传入;正式变更日志继续取自三语言 CHANGELOG.

## 设计约束

- **必须**在认证与权限复验后提供敏感数据;初始 HTML **禁止**包含隐藏的真实凭据. 编辑已有对象**必须**载入原值, 不能用空白字段覆盖未修改值.
- 端口**必须**先锁定并登记归属再启用监听;失败时释放新增登记, **禁止**抢占其他项目的登记.
- FRP 修改**必须**先验证, 失败时保留或尽可能恢复原配置;高级非受管配置**禁止**被结构化编辑器丢弃.
- 流量配额按 `(上传 + 下载) × 2` 计入;读取计量失败**禁止**被当作达到配额. 周期重置**必须**同步重建内核 quota.
- iperf3 服务端**必须**限时运行, Web 停止时关闭临时进程与本项目转发规则. **禁止**重置整个主机的 `ip_forward` 或删除其他程序的防火墙规则.
- 公开监听器与控制台路由边界**必须**分离. 信任代理地址头时**禁止**依赖其地址进行 IP 免密认证.
- 同布局安装**必须**保留持久状态;旧布局或缺失定位文件**禁止**被当作空白安装自动覆盖.
- 第三方构件**必须**核验固定摘要并携带原始许可与对应源码获取方式. 文件身份校验不代表系统依赖完全锁定.

## 设计标记

采用最新 Web UI 起始模板的字号, 字重, 行高, 间距, 圆角, 阴影, 容器, 八主题色与动效标记. 共享组件直接来自模板;顶栏和页头使用真实同源链接以保留 Python 路由. `tokens.css` 追加 `compat-*` 标记, 仅用于网络模块已有表格/对话框的尺寸和状态变体;字号, 字重, 圆角和主题色已统一到模板标记. 新组件和页面只引用标记. 检查命令: `cd web && npm run check`.

## 数据设计

| 位置 | 数据 |
| --- | --- |
| `/var/lib/vps-server` | 默认状态根, 布局 1;由 `/etc/vps-server/state-dir` 定位. |
| `admin_password.txt`, `console_port.txt`, `.env`, `paths.json`, `.layout-version` | 认证, 固定端口, 配置及路径/布局元数据. |
| `certs/` | TLS 证书与私钥. |
| `data/` | SQLite 访客库, 会话与签名密钥, 功能状态, 节点清单和后台任务. |
| `/etc/vps-server-proxy/config.json` | Singbox 运行配置;节点身份与策略由受管清单协调. |
| `/etc/vps-server-frps/frps.toml` | FRPS 服务端配置. |
| `/etc/frp/frpc-<name>.toml` | FRPC 实例配置;非 ASCII 名称映射到稳定的 unit 别名. |
| `/etc/vps-server-lucky` | Lucky 原生设置及任务. |
| `~/apps/PORTS.md`, `~/apps/.ports.lock` | 主机端口归属清单与互斥锁. |

状态文件按敏感等级限制权限, Web 不把备份或配置作为静态资源公开. FRPC 任务文件 `data/frp-jobs/*.json` 权限为 `0600`, 执行前移除请求凭据, 结果以任务状态保存. 转发规则保存为项目 JSON 并在启动时重放, 不保存整个主机规则集. 安装前备份和人工恢复流程见 README.

## 外部接口

- Web 页面与表单只面向本项目管理操作;受保护的显示/复制接口在认证后返回敏感值. `/frp/client/structured` 和 `/frp/client/rename` 是 POST 操作, 不是独立展示页.
- LibreSpeed 客户端使用 `/speedtest/garbage`, `/speedtest/empty`, `/speedtest/getip` 与原创 Python 后端交互;结果反映当前客户端到服务器的链路.
- 权限辅助程序通过白名单动作调用 systemd, FRP 验证器, nft/iptables 与安装器;不提供任意命令执行 API. root PTY 仅供经过密码复验的终端会话.
- FRPC 连接用户指定的服务器, 结构化编辑只支持简单 token 认证 TCP/UDP 代理.
- Tailscale CLI 与本机守护进程通信, 登录和路由审批由控制服务器/Tailnet 处理. Lucky 使用独立的原生管理端口.
- 地址来自本机网卡及已配置的 FRPC 服务器地址, 安装器不请求外部服务查询公网 IP.
