# Native shell catalog for deploy/caddy/setup-caddy.sh.
case "$key" in
  root_required) fmt='se requiere root' ;;
  integrity_failure) fmt='Falló la verificación de integridad de Caddy' ;;
  port_busy) fmt='El puerto %s está en uso por otro programa; el reenvío de dominios necesita los puertos 80 y 443' ;;
  start_failed) fmt='Caddy no se inició; se restauró la página pública de accesibilidad' ;;
  no_firewall) fmt='No hay ufw ni firewalld activos; asegúrate de que los puertos 80 y 443 sean accesibles' ;;
  installed) fmt='El reenvío de dominios funciona en los puertos 80 y 443' ;;
esac
