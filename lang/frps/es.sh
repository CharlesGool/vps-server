# Native shell catalog for deploy/frps/setup-frps.sh.
case "$key" in
  root_required) fmt='Se requieren permisos de root' ;;
  integrity_failure) fmt='Falló la comprobación de integridad del binario frps incluido' ;;
  existing_invalid) fmt='La configuración existente de frps no es válida; no se reemplazarán las credenciales' ;;
  existing_invalid_detail) fmt='La configuración existente de frps no es válida: %s' ;;
  invalid_bind) fmt='FRPS_BIND_PORT no es válido' ;;
  invalid_token) fmt='FRPS_TOKEN no es válido' ;;
  reserved_check) fmt='No se pudieron comprobar los puertos reservados en %s: %s' ;;
  forward_check) fmt='No se pudieron comprobar los puertos redirigidos: %s' ;;
  port_conflict) fmt='El puerto frps %s entra en conflicto con un puerto web/proxy/redirigido reservado' ;;
  port_unavailable) fmt='El puerto frps %s no está disponible: %s' ;;
  rollback_degraded) fmt='DEGRADADO: falló la reversión de frps o la restauración del servicio anterior' ;;
  start_failed) fmt='No se pudo iniciar frps' ;;
  firewall_allow) fmt='Advertencia: abre manualmente el puerto TCP de frps en el firewall' ;;
  firewall_remove) fmt='Advertencia: no se pudo eliminar la regla de firewall de frps previamente creada' ;;
  firewall_rollback) fmt='DEGRADADO: falló la reversión de las reglas de firewall de frps' ;;
  ownership_failed) fmt='No se pudo actualizar el registro de propiedad de la regla de firewall de frps' ;;
  *) fmt="$key" ;;
esac
