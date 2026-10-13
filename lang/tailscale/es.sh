# Native shell catalog for deploy/tailscale/setup-tailscale.sh.
case "$key" in
  root_required) fmt='Se requiere root' ;;
  asset_missing) fmt='Falta el paquete de Tailscale incluido' ;;
  integrity_failure) fmt='El paquete de Tailscale incluido no superó la comprobación de integridad' ;;
  daemon_active) fmt='Ya hay un demonio de Tailscale activo; no se iniciará una segunda instancia' ;;
  port_registered) fmt='El puerto de Tailscale ya está registrado para otro servicio' ;;
  *) fmt="$key" ;;
esac
