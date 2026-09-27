# Native shell catalog for deploy/frps/setup-frps.sh.
case "$key" in
  root_required) fmt='Droits root requis' ;;
  integrity_failure) fmt='Échec du contrôle d’intégrité du binaire frps fourni' ;;
  existing_invalid) fmt='La configuration frps existante est invalide ; les identifiants ne seront pas remplacés' ;;
  existing_invalid_detail) fmt='La configuration frps existante est invalide : %s' ;;
  invalid_bind) fmt='FRPS_BIND_PORT est invalide' ;;
  invalid_token) fmt='FRPS_TOKEN est invalide' ;;
  reserved_check) fmt='Impossible de vérifier les ports réservés dans %s : %s' ;;
  forward_check) fmt='Impossible de vérifier les ports redirigés : %s' ;;
  port_conflict) fmt='Le port frps %s entre en conflit avec un port web/proxy/redirigé réservé' ;;
  port_unavailable) fmt='Le port frps %s est indisponible : %s' ;;
  rollback_degraded) fmt='ÉTAT DÉGRADÉ : échec du retour arrière frps ou du rétablissement du service précédent' ;;
  start_failed) fmt='Échec du démarrage de frps' ;;
  firewall_allow) fmt='Attention : ouvrez manuellement le port TCP frps dans le pare-feu' ;;
  firewall_remove) fmt='Attention : impossible de retirer la règle pare-feu frps précédemment créée' ;;
  firewall_rollback) fmt='ÉTAT DÉGRADÉ : échec du retour arrière du pare-feu frps' ;;
  ownership_failed) fmt='Échec de la mise à jour de la propriété de la règle pare-feu frps' ;;
  *) fmt="$key" ;;
esac
