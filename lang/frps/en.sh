# Native shell catalog for deploy/frps/setup-frps.sh.
case "$key" in
  root_required) fmt='root required' ;;
  integrity_failure) fmt='frps vendor integrity failure' ;;
  existing_invalid) fmt='Existing frps configuration is invalid; refusing to replace credentials' ;;
  existing_invalid_detail) fmt='Existing frps configuration is invalid: %s' ;;
  invalid_bind) fmt='Invalid FRPS_BIND_PORT' ;;
  invalid_token) fmt='Invalid FRPS_TOKEN' ;;
  reserved_check) fmt='Cannot check reserved ports in %s: %s' ;;
  forward_check) fmt='Cannot check forwarded ports: %s' ;;
  port_conflict) fmt='frps port %s conflicts with a reserved web/proxy/forward port' ;;
  port_unavailable) fmt='frps port %s unavailable: %s' ;;
  rollback_degraded) fmt='DEGRADED: frps rollback or prior service restoration failed' ;;
  start_failed) fmt='frps failed to start' ;;
  firewall_allow) fmt='Warning: allow frps TCP port in firewall manually' ;;
  firewall_remove) fmt='Warning: could not remove previously owned frps firewall rule' ;;
  firewall_rollback) fmt='DEGRADED: frps firewall rollback failed' ;;
  ownership_failed) fmt='frps firewall ownership update failed' ;;
  *) fmt="$key" ;;
esac
