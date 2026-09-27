# Native shell catalog for deploy/lucky/setup-lucky.sh.
case "$key" in
  root_required) fmt='Se requieren permisos de root' ;;
  integrity_failure) fmt='Falló la comprobación de integridad del binario Lucky incluido' ;;
  malformed_current) fmt='La configuración existente de Lucky está mal formada: %s' ;;
  invalid_public) fmt='LUCKY_PUBLIC_ADMIN no es válido' ;;
  public_warning) fmt='ADVERTENCIA: la administración pública de Lucky usa HTTP; las credenciales se transmiten sin cifrar. Usa un túnel privado o un proxy inverso TLS.' ;;
  confirm_required) fmt='Se requiere LUCKY_PUBLIC_CONFIRM="I ACCEPT PUBLIC HTTP" explícito en el servidor' ;;
  malformed_overwrite) fmt='La configuración existente de Lucky está mal formada; se rechaza la sobrescritura: %s' ;;
  invalid_admin_port) fmt='LUCKY_ADMIN_PORT no es válido' ;;
  cannot_reverse) fmt='No se pudo verificar el puerto del proxy inverso de Lucky' ;;
  reverse_conflict) fmt='El puerto de administración Lucky %s entra en conflicto con el del proxy inverso de Lucky' ;;
  cannot_console) fmt='No se pudo verificar el puerto de consola' ;;
  cannot_verify_file) fmt='No se pudo verificar %s: %s' ;;
  cannot_frps) fmt='No se pudo verificar el puerto frps' ;;
  cannot_forward) fmt='No se pudieron verificar los puertos redirigidos: %s' ;;
  reserved_conflict) fmt='El puerto de administración Lucky %s entra en conflicto con un puerto reservado' ;;
  unavailable) fmt='El puerto de administración Lucky no está disponible: %s' ;;
  restore_fw) fmt='DEGRADADO: falló la restauración del estado firewalld de Lucky' ;;
  restore_old) fmt='DEGRADADO: falló la restauración de la regla de firewall anterior de Lucky' ;;
  remove_new) fmt='DEGRADADO: no se pudo retirar la nueva regla de firewall de Lucky' ;;
  restore_file) fmt='DEGRADADO: no se pudo restaurar %s' ;;
  remove_file) fmt='DEGRADADO: no se pudo eliminar %s' ;;
  restore_service) fmt='DEGRADADO: falló la restauración del servicio Lucky' ;;
  no_firewall) fmt='ADVERTENCIA: no hay un firewall compatible activo; comprueba el firewall externo y limita manualmente el acceso público a la administración por HTTP' ;;
  *) fmt="$key" ;;
esac
