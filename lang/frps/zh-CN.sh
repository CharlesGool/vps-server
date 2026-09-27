# Native shell catalog for deploy/frps/setup-frps.sh.
case "$key" in
  root_required) fmt='需要 root 权限' ;;
  integrity_failure) fmt='frps 第三方文件完整性校验失败' ;;
  existing_invalid) fmt='现有 frps 配置无效；拒绝替换凭据' ;;
  existing_invalid_detail) fmt='现有 frps 配置无效：%s' ;;
  invalid_bind) fmt='FRPS_BIND_PORT 无效' ;;
  invalid_token) fmt='FRPS_TOKEN 无效' ;;
  reserved_check) fmt='无法检查 %s 中的保留端口：%s' ;;
  forward_check) fmt='无法检查转发端口：%s' ;;
  port_conflict) fmt='frps 端口 %s 与已保留的 web/proxy/转发端口冲突' ;;
  port_unavailable) fmt='frps 端口 %s 不可用：%s' ;;
  rollback_degraded) fmt='降级：frps 回滚或原有服务恢复失败' ;;
  start_failed) fmt='frps 启动失败' ;;
  firewall_allow) fmt='警告：请手动在防火墙中放行 frps TCP 端口' ;;
  firewall_remove) fmt='警告：无法删除此前归属本项目的 frps 防火墙规则' ;;
  firewall_rollback) fmt='降级：frps 防火墙回滚失败' ;;
  ownership_failed) fmt='更新 frps 防火墙规则归属记录失败' ;;
  *) fmt="$key" ;;
esac
