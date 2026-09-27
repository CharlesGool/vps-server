# Native shell catalog for deploy/lucky/setup-lucky.sh.
case "$key" in
  root_required) fmt='需要 root 权限' ;;
  integrity_failure) fmt='Lucky 第三方文件完整性校验失败' ;;
  malformed_current) fmt='现有 Lucky 配置格式错误：%s' ;;
  invalid_public) fmt='LUCKY_PUBLIC_ADMIN 无效' ;;
  public_warning) fmt='警告：Lucky 公共管理界面使用 HTTP，凭据会以明文传输。请改用私有隧道或 TLS 反向代理。' ;;
  confirm_required) fmt='必须在服务器端明确设置 LUCKY_PUBLIC_CONFIRM="I ACCEPT PUBLIC HTTP"' ;;
  malformed_overwrite) fmt='现有 Lucky 配置格式错误；拒绝覆盖：%s' ;;
  invalid_admin_port) fmt='LUCKY_ADMIN_PORT 无效' ;;
  cannot_reverse) fmt='无法验证 Lucky 反向代理监听端口' ;;
  reverse_conflict) fmt='Lucky 管理端口 %s 与 Lucky 反向代理监听端口冲突' ;;
  cannot_console) fmt='无法验证控制台端口' ;;
  cannot_verify_file) fmt='无法验证 %s：%s' ;;
  cannot_frps) fmt='无法验证 frps 端口' ;;
  cannot_forward) fmt='无法验证转发端口：%s' ;;
  reserved_conflict) fmt='Lucky 管理端口 %s 与保留端口冲突' ;;
  unavailable) fmt='Lucky 管理端口不可用：%s' ;;
  restore_fw) fmt='降级：Lucky firewalld 状态恢复失败' ;;
  restore_old) fmt='降级：旧 Lucky 防火墙规则恢复失败' ;;
  remove_new) fmt='降级：新 Lucky 防火墙规则删除失败' ;;
  restore_file) fmt='降级：无法恢复 %s' ;;
  remove_file) fmt='降级：无法删除 %s' ;;
  restore_service) fmt='降级：Lucky 服务恢复失败' ;;
  no_firewall) fmt='警告：没有活动且受支持的防火墙；请检查外部防火墙规则，并手动限制公共 HTTP 管理访问' ;;
  *) fmt="$key" ;;
esac
