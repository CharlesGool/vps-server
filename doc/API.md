---
name: api
description: 控制台的令牌接口: 认证, 权限和每个接口的请求与响应
metadata:
  version: "1.0.0"
  lang: "zh-CN"
---

# 令牌接口

本文说明 `/api/v1/*`, 给脚本和其他控制台(集中管理页)使用. 浏览器页面用的 `/api/*` 会话接口不在本文范围, 也不保证稳定.

## 认证

1. 在集中管理页的 API 令牌卡片生成令牌. 令牌形如 `vpss_...`, 只在生成时显示一次, 服务器只保存它的 SHA-256.
2. 主页的集中管理开关关闭时, 所有令牌接口返回 403 `feature_closed`.
3. 每个请求带请求头 `Authorization: Bearer <令牌>`. 不需要会话 Cookie, 也不受"要求客户端证书"和同源检查限制; 控制台访问地址限制照常生效.
4. 令牌错误按登录失败计数, 达到次数后来源地址被封禁(返回 429, `retryAfter` 是剩余秒数).
5. 权限分两种: `read` 只能调用下表的读接口; `write` 还能调用写接口. 只读令牌调用写接口返回 403 `read_only_token`.

令牌最多 20 个. 安全记录里写着每个令牌的生成, 删除, 以及它触发的写操作; 令牌列表显示最近一次使用的时间和来源地址.

## 接口

请求和响应都是 JSON. 成功返回 200; 失败返回 4xx/5xx 和 `{"error": "<代码>"}`.

| 方法和路径 | 权限 | 作用 |
| --- | --- | --- |
| `GET /api/v1/status` | read | 主机名, 版本, 服务器标识, 内核, 资源(同 `monitor`, 不含走势), 本周期总流量, 本项目相关服务的状态, 失败的服务 |
| `GET /api/v1/monitor` | read | 资源监控页的全部数据, 含 24 小时走势(12 段和 24 段平均值) |
| `GET /api/v1/services` | read | 全部 systemd 服务: `unit`, `load`, `active`, `sub`, `description`, `enabled` |
| `GET /api/v1/upgrade` | read | 经接口启动的升级是否在运行(`running`), 当前版本, 升级输出的最后 40 行 |
| `POST /api/v1/services/restart` | write | 重启服务, 请求体 `{"unit": "<名称>.service"}`; 重启控制台自己时立即返回 |
| `POST /api/v1/upgrade` | write | 在后台升级到最新正式版, 或 `{"version": "v7.2.0"}` 指定版本; `variant` 可选 `online`(默认)或 `offline`. 已有升级在运行时返回 409 `busy` |
| `POST /api/v1/backup` | write | 做一份手动配置备份, 返回 `{"name": "<文件名>"}` |

升级和面板里的升级命令一样: 先验证发布签名, 再运行包里的安装器, 控制台会重启一次. 升级从 GitHub 下载; 连不上 GitHub 的主机仍要按 README 的 [升级](../README.md#升级) 手动传文件.

## 示例

```bash
TOKEN=vpss_...
curl -sk -H "Authorization: Bearer $TOKEN" https://203.0.113.5:20000/api/v1/status
curl -sk -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"unit": "vps-server-proxy.service"}' https://203.0.113.5:20000/api/v1/services/restart
```

控制台默认用自签名证书, 上面用 `-k` 跳过校验. 脚本应改用 `--pinnedpubkey` 或换成有效证书(IP 证书或域名转发).
