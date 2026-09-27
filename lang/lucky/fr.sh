# Native shell catalog for deploy/lucky/setup-lucky.sh.
case "$key" in
  root_required) fmt='Droits root requis' ;;
  integrity_failure) fmt='Échec du contrôle d’intégrité du binaire Lucky fourni' ;;
  malformed_current) fmt='La configuration Lucky existante est mal formée : %s' ;;
  invalid_public) fmt='LUCKY_PUBLIC_ADMIN est invalide' ;;
  public_warning) fmt='ATTENTION : l’administration publique de Lucky utilise HTTP ; les identifiants circulent sans chiffrement. Utilisez un tunnel privé ou un proxy inverse TLS.' ;;
  confirm_required) fmt='La confirmation LUCKY_PUBLIC_CONFIRM="I ACCEPT PUBLIC HTTP" doit être définie explicitement sur le serveur' ;;
  malformed_overwrite) fmt='La configuration Lucky existante est mal formée ; écrasement refusé : %s' ;;
  invalid_admin_port) fmt='LUCKY_ADMIN_PORT est invalide' ;;
  cannot_reverse) fmt='Impossible de vérifier le port du proxy inverse Lucky' ;;
  reverse_conflict) fmt='Le port administrateur Lucky %s entre en conflit avec celui du proxy inverse Lucky' ;;
  cannot_console) fmt='Impossible de vérifier le port de la console' ;;
  cannot_verify_file) fmt='Impossible de vérifier %s : %s' ;;
  cannot_frps) fmt='Impossible de vérifier le port frps' ;;
  cannot_forward) fmt='Impossible de vérifier les ports redirigés : %s' ;;
  reserved_conflict) fmt='Le port administrateur Lucky %s entre en conflit avec un port réservé' ;;
  unavailable) fmt='Port administrateur Lucky indisponible : %s' ;;
  restore_fw) fmt='ÉTAT DÉGRADÉ : échec du rétablissement de l’état firewalld Lucky' ;;
  restore_old) fmt='ÉTAT DÉGRADÉ : échec du rétablissement de l’ancienne règle pare-feu Lucky' ;;
  remove_new) fmt='ÉTAT DÉGRADÉ : impossible de retirer la nouvelle règle pare-feu Lucky' ;;
  restore_file) fmt='ÉTAT DÉGRADÉ : impossible de restaurer %s' ;;
  remove_file) fmt='ÉTAT DÉGRADÉ : impossible de supprimer %s' ;;
  restore_service) fmt='ÉTAT DÉGRADÉ : échec du rétablissement du service Lucky' ;;
  no_firewall) fmt='ATTENTION : aucun pare-feu compatible actif ; vérifiez les règles externes et limitez manuellement l’accès public à l’administration HTTP' ;;
  *) fmt="$key" ;;
esac
