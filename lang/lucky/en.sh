# Native shell catalog for deploy/lucky/setup-lucky.sh.
case "$key" in
  root_required) fmt='root required' ;;
  integrity_failure) fmt='Lucky vendor integrity failure' ;;
  malformed_current) fmt='Malformed existing Lucky configuration: %s' ;;
  invalid_public) fmt='Invalid LUCKY_PUBLIC_ADMIN' ;;
  public_warning) fmt='WARNING: Lucky public admin uses HTTP: credentials are transmitted unencrypted. Use a private tunnel or TLS reverse proxy instead.' ;;
  confirm_required) fmt='Explicit server-side LUCKY_PUBLIC_CONFIRM="I ACCEPT PUBLIC HTTP" required' ;;
  malformed_overwrite) fmt='Malformed existing Lucky configuration; refusing overwrite: %s' ;;
  invalid_admin_port) fmt='Invalid LUCKY_ADMIN_PORT' ;;
  cannot_reverse) fmt='Cannot verify Lucky reverse proxy listener' ;;
  reverse_conflict) fmt='Lucky admin port %s conflicts with Lucky reverse proxy listener' ;;
  cannot_console) fmt='Cannot verify console port' ;;
  cannot_verify_file) fmt='Cannot verify %s: %s' ;;
  cannot_frps) fmt='Cannot verify frps port' ;;
  cannot_forward) fmt='Cannot verify forwarded ports: %s' ;;
  reserved_conflict) fmt='Lucky admin port %s conflicts with reserved port' ;;
  unavailable) fmt='Lucky admin port unavailable: %s' ;;
  restore_fw) fmt='DEGRADED: Lucky firewalld state restore failed' ;;
  restore_old) fmt='DEGRADED: old Lucky firewall rule restore failed' ;;
  remove_new) fmt='DEGRADED: new Lucky firewall rule removal failed' ;;
  restore_file) fmt='DEGRADED: could not restore %s' ;;
  remove_file) fmt='DEGRADED: could not remove %s' ;;
  restore_service) fmt='DEGRADED: Lucky service restore failed' ;;
  no_firewall) fmt='WARNING: no active supported firewall; verify external firewall rules and restrict public HTTP admin access manually' ;;
  *) fmt="$key" ;;
esac
