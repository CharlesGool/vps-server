# Native shell catalog for deploy/caddy/setup-caddy.sh.
case "$key" in
  root_required) fmt='root required' ;;
  integrity_failure) fmt='Caddy vendor integrity failure' ;;
  port_busy) fmt='Port %s is used by another program; domain forwarding needs ports 80 and 443' ;;
  start_failed) fmt='Caddy did not start; the public reachability page was restored' ;;
  no_firewall) fmt='No active ufw or firewalld; make sure ports 80 and 443 are reachable' ;;
  installed) fmt='Domain forwarding is running on ports 80 and 443' ;;
esac
