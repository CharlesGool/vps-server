# Native shell catalog for deploy/caddy/setup-caddy.sh.
case "$key" in
  root_required) fmt='需要 root 权限' ;;
  integrity_failure) fmt='Caddy 程序校验失败' ;;
  port_busy) fmt='端口 %s 被其他程序占用;域名转发需要 80 和 443 端口' ;;
  start_failed) fmt='Caddy 未能启动;已恢复公开探测页' ;;
  no_firewall) fmt='未检测到启用的 ufw 或 firewalld;请确认 80 和 443 端口可以从外部访问' ;;
  installed) fmt='域名转发已在 80 和 443 端口运行' ;;
esac
