# Native shell catalog for deploy/tailscale/setup-tailscale.sh.
case "$key" in
  root_required) fmt='需要 root 权限' ;;
  asset_missing) fmt='缺少随附的 Tailscale 安装包' ;;
  integrity_failure) fmt='随附的 Tailscale 安装包完整性校验失败' ;;
  daemon_active) fmt='主机上已有运行中的 Tailscale 守护进程；拒绝启动第二个实例' ;;
  port_registered) fmt='Tailscale 端口已被其他服务登记' ;;
  *) fmt="$key" ;;
esac
