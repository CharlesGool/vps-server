# Native shell catalog for deploy/uninstall.sh.
case "$key" in
  need_root) fmt='Exécution en tant que root requise (essayez : sudo bash deploy/uninstall.sh)\n' ;;
  removed_unit) fmt='%s supprimé\n' ;;
  no_unit) fmt='Aucun fichier unité à %s : rien à supprimer.\n' ;;
  purged) fmt='%s supprimé (mot de passe administrateur, port, certificats et journal des visiteurs effacés).\n' ;;
  kept) fmt='%s conservé : le mot de passe administrateur, le port, les certificats et le journal des visiteurs sont toujours présents.\n' ;;
  nothing_left) fmt='%s est absent : rien à supprimer.\n' ;;
  anytls_removing) fmt='Suppression du module anytls (%s) ...\n' ;;
  anytls_orphan) fmt='%s est installé, mais %s/anytls/setup-anytls.sh est absent : impossible de le supprimer automatiquement.\nSupprimez-le manuellement :\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-anytls\n  (conservez /usr/local/bin/sing-box-vps-server si proxy l’utilise encore ; ne le supprimez qu’après vérification qu’aucun module ne l’utilise)\n' ;;
  proxy_removing) fmt='Suppression du module proxy (%s) ...\n' ;;
  proxy_orphan) fmt='%s est installé, mais %s/proxy/setup-proxy.sh est absent : impossible de le supprimer automatiquement.\nSupprimez-le manuellement :\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-proxy\n  (conservez /usr/local/bin/sing-box-vps-server si anytls l’utilise encore)\n' ;;
  done) fmt='\nvps-server a été désinstallé.\n' ;;
  lucky_fw_retained) fmt='Attention : propriété de la règle pare-feu Lucky conservée ; nettoyage manuel nécessaire\n' ;;
  lucky_config_retained) fmt='Configuration DDNS/proxy inverse Lucky conservée dans /etc/vps-server-lucky/config.json\n' ;;
  frps_fw_retained) fmt='Attention : règle pare-feu frps non supprimée ; propriété conservée\n' ;;
  error_prefix) fmt='erreur : %s\n' ;;
  *) fmt="$key\n" ;;
esac
