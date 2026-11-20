# Native shell catalog for deploy/uninstall.sh.
case "$key" in
  need_root) fmt='must run as root (try: sudo bash deploy/uninstall.sh)\n' ;;
  removed_unit) fmt='Removed %s\n' ;;
  no_unit) fmt='No unit file at %s — nothing to remove.\n' ;;
  purged) fmt='Deleted %s (admin password, port, certificates and visitor log are gone).\n' ;;
  kept) fmt='Kept %s — admin password, port, certificates and visitor log are still there.\n' ;;
  nothing_left) fmt='%s does not exist — nothing to delete.\n' ;;
  anytls_removing) fmt='Removing the anytls module (%s) ...\n' ;;
  anytls_orphan) fmt='%s is installed but %s/anytls/setup-anytls.sh is gone, so it cannot be removed automatically.\nRemove it by hand:\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-anytls\n  (keep /usr/local/bin/sing-box-vps-server if proxy still uses it; remove it only after confirming no module uses it)\n' ;;
  proxy_removing) fmt='Removing the proxy module (%s) ...\n' ;;
  proxy_orphan) fmt='%s is installed but %s/proxy/setup-proxy.sh is gone, so it cannot be removed automatically.\nRemove it by hand:\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-proxy\n  (leave /usr/local/bin/sing-box-vps-server if the anytls module still uses it)\n' ;;
  frpc_removed) fmt='FRPC cleanup complete.\n' ;;
  frpc_unowned) fmt='FRPC ownership could not be verified; existing FRPC files and their port registrations were kept.\n' ;;
  ports_released) fmt='Released %s vps-server port registrations.\n' ;;
  cleanup_failed) fmt='Could not complete FRPC or port-registry cleanup.\n' ;;
  tailscale_stop_failed) fmt='Could not stop the Tailscale service' ;;
  done) fmt='\nvps-server has been uninstalled.\n' ;;
  lucky_fw_retained) fmt='Warning: Lucky firewall ownership record retained; manual cleanup needed\n' ;;
  lucky_config_retained) fmt='Lucky DDNS/reverse proxy configuration retained in /etc/vps-server-lucky/config.json\n' ;;
  frps_fw_retained) fmt='Warning: owned frps firewall rule could not be removed; ownership record retained\n' ;;
  prefix_not_project) fmt='Refusing to delete %s: it does not look like a vps-server installation (no app.py or src/web/). Check PREFIX, or delete %s by hand if it really is one. Nothing was changed.\n' ;;
  purge_head) fmt='A full uninstall permanently deletes:\n' ;;
  purge_prefix) fmt='  - the program directory %s\n' ;;
  purge_state) fmt='  - the state directory %s (admin password, certificates, settings and logs)\n' ;;
  purge_backups) fmt='  - %s configuration backup(s) in %s\n' ;;
  purge_drive) fmt='  - %s Mini Drive file(s), %s in total\n' ;;
  purge_modules) fmt='  - the node, FRPS/FRPC, domain forwarding and Tailscale settings of this project\n' ;;
  purge_data_key) fmt='  - the data key %s\n' ;;
  purge_outside_kept) fmt='Kept: %s (outside the state directory) and the data key it needs.\n' ;;
  purge_needs_confirm) fmt='A full uninstall deletes the data listed above and must be confirmed. Run it in a terminal, or set VPSSRV_UNINSTALL_YES=1 to run it unattended; KEEP_DATA=1 removes the services and keeps the data. Nothing was changed.\n' ;;
  purge_confirm) fmt='Type yes to delete all of this (anything else, or no answer within %s seconds, cancels): ' ;;
  purge_cancelled) fmt='Cancelled; nothing was changed.\n' ;;
  data_key_removed) fmt='Deleted the data key %s.\n' ;;
  data_key_kept) fmt='Kept the data key %s: %s may still hold data encrypted with it.\n' ;;
  error_prefix) fmt='error: %s\n' ;;
  *) fmt="$key\n" ;;
esac
