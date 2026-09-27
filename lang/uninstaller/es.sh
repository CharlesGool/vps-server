# Native shell catalog for deploy/uninstall.sh.
case "$key" in
  need_root) fmt='Debe ejecutarse como root (prueba: sudo bash deploy/uninstall.sh)\n' ;;
  removed_unit) fmt='Se eliminó %s\n' ;;
  no_unit) fmt='No hay ningún archivo de unidad en %s; no hay nada que eliminar.\n' ;;
  purged) fmt='Se eliminó %s (también se borraron la contraseña de administración, el puerto, los certificados y el registro de visitantes).\n' ;;
  kept) fmt='Se conservó %s: la contraseña de administración, el puerto, los certificados y el registro de visitantes siguen allí.\n' ;;
  nothing_left) fmt='%s no existe; no hay nada que borrar.\n' ;;
  anytls_removing) fmt='Eliminando el módulo anytls (%s) ...\n' ;;
  anytls_orphan) fmt='%s está instalado, pero falta %s/anytls/setup-anytls.sh, así que no puede eliminarse automáticamente.\nElimínalo manualmente:\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-anytls\n  (conserva /usr/local/bin/sing-box-vps-server si proxy todavía lo utiliza; elimínalo solo tras confirmar que ningún módulo lo necesita)\n' ;;
  proxy_removing) fmt='Eliminando el módulo proxy (%s) ...\n' ;;
  proxy_orphan) fmt='%s está instalado, pero falta %s/proxy/setup-proxy.sh, así que no puede eliminarse automáticamente.\nElimínalo manualmente:\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-proxy\n  (conserva /usr/local/bin/sing-box-vps-server si anytls todavía lo utiliza)\n' ;;
  done) fmt='\nSe desinstaló vps-server.\n' ;;
  lucky_fw_retained) fmt='Advertencia: se conservó el registro de propiedad de la regla de firewall de Lucky; requiere limpieza manual\n' ;;
  lucky_config_retained) fmt='La configuración de DDNS/proxy inverso de Lucky se conserva en /etc/vps-server-lucky/config.json\n' ;;
  frps_fw_retained) fmt='Advertencia: no se pudo eliminar la regla de firewall de frps; se conservó su registro de propiedad\n' ;;
  error_prefix) fmt='error: %s\n' ;;
  *) fmt="$key\n" ;;
esac
