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
  frpc_removed) fmt='Limpieza de FRPC completada.\n' ;;
  frpc_unowned) fmt='No se pudo verificar que FRPC pertenezca al proyecto; se conservaron los archivos y registros de puertos.\n' ;;
  ports_released) fmt='Se liberaron %s registros de puertos de vps-server.\n' ;;
  cleanup_failed) fmt='No se pudo completar la limpieza de FRPC o del registro de puertos.\n' ;;
  tailscale_stop_failed) fmt='No se pudo detener el servicio de Tailscale' ;;
  done) fmt='\nSe desinstaló vps-server.\n' ;;
  lucky_fw_retained) fmt='Advertencia: se conservó el registro de propiedad de la regla de firewall de Lucky; requiere limpieza manual\n' ;;
  lucky_config_retained) fmt='La configuración de DDNS/proxy inverso de Lucky se conserva en /etc/vps-server-lucky/config.json\n' ;;
  frps_fw_retained) fmt='Advertencia: no se pudo eliminar la regla de firewall de frps; se conservó su registro de propiedad\n' ;;
  prefix_not_project) fmt='No se elimina %s: no parece una instalación de vps-server (no tiene app.py ni src/web/). Revisa PREFIX, o elimina %s a mano si de verdad lo es. No se ha cambiado nada.\n' ;;
  purge_head) fmt='Una desinstalación completa elimina de forma permanente:\n' ;;
  purge_prefix) fmt='  - el directorio del programa %s\n' ;;
  purge_state) fmt='  - el directorio de estado %s (contraseña de administrador, certificados, ajustes y registros)\n' ;;
  purge_backups) fmt='  - %s copia(s) de configuración en %s\n' ;;
  purge_drive) fmt='  - %s archivo(s) de Mini Drive, %s en total\n' ;;
  purge_modules) fmt='  - los ajustes de nodos, FRPS/FRPC, reenvío de dominios y Tailscale de este proyecto\n' ;;
  purge_data_key) fmt='  - la clave de datos %s\n' ;;
  purge_outside_kept) fmt='Se conservan: %s (fuera del directorio de estado) y la clave de datos que necesitan.\n' ;;
  purge_needs_confirm) fmt='Una desinstalación completa elimina los datos indicados arriba y debe confirmarse. Ejecútala en un terminal, o define VPSSRV_UNINSTALL_YES=1 para hacerlo sin intervención; KEEP_DATA=1 quita los servicios y conserva los datos. No se ha cambiado nada.\n' ;;
  purge_confirm) fmt='Escribe yes para eliminar todo esto (cualquier otra respuesta, o ninguna en %s segundos, cancela): ' ;;
  purge_cancelled) fmt='Cancelado; no se ha cambiado nada.\n' ;;
  data_key_removed) fmt='Se eliminó la clave de datos %s.\n' ;;
  data_key_kept) fmt='Se conserva la clave de datos %s: %s puede contener aún datos cifrados con ella.\n' ;;
  error_prefix) fmt='error: %s\n' ;;
  *) fmt="$key\n" ;;
esac
