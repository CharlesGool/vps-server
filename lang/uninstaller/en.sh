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
  done) fmt='\nvps-server has been uninstalled.\n' ;;
  lucky_fw_retained) fmt='Warning: Lucky firewall ownership record retained; manual cleanup needed\n' ;;
  lucky_config_retained) fmt='Lucky DDNS/reverse proxy configuration retained in /etc/vps-server-lucky/config.json\n' ;;
  frps_fw_retained) fmt='Warning: owned frps firewall rule could not be removed; ownership record retained\n' ;;
  error_prefix) fmt='error: %s\n' ;;
  *) fmt="$key\n" ;;
esac
