# Native shell catalog for deploy/tailscale/setup-tailscale.sh.
case "$key" in
  root_required) fmt='Root required' ;;
  asset_missing) fmt='Bundled Tailscale asset missing' ;;
  integrity_failure) fmt='Tailscale bundled archive failed its integrity check' ;;
  daemon_active) fmt='An existing Tailscale daemon is active; refusing a second instance' ;;
  port_registered) fmt='The Tailscale port is already registered to another service' ;;
  *) fmt="$key" ;;
esac
