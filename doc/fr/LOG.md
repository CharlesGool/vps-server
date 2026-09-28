---
name: project-log-fr
description: Décisions, limites, bogues et modifications du projet
metadata:
  version: "1.0.0"
  lang: "fr"
---

# vps-server — Journal

Ce registre rassemble les bogues connus, les décisions, les travaux passés, les limites d'acceptation actuelles et les changements publiés. Les tests mentionnés dans l'historique n'ont pas été relancés pour cette migration documentaire.

## Multilingue

[English](../LOG.md) | [简体中文](../zh-CN/LOG.md) | [繁體中文(台灣)](../zh-TW/LOG.md) | [繁體中文(香港)](../zh-HK/LOG.md) | [हिन्दी](../hi/LOG.md) | [Español](../es/LOG.md) | [العربية](../ar/LOG.md) | **Français**

## Documentation

- Présentation du projet : [README](README.md)

- Justification de la conception : [DESIGN](DESIGN.md)

- Historique des versions : [LOG](LOG.md)

- Avis relatifs aux tiers : [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Bogues

- [ ] 2026-09-12 Déterminer si le verrou partagé `_db_lock` doit être dissocié — chaque accès à la page publique prend un verrou à l'échelle du processus et écrit de façon synchrone dans SQLite ; la console partage ce verrou. En théorie, un afflux anonyme peut donc ralentir une page authentifiée. **Mesuré, mais non reproduit** : 60 clients simultanés générant un afflux ont laissé la latence de la console à 0.4–0.6 ms, comme au repos. Consigné pour éviter de redécouvrir ce mécanisme ; ne pas revoir l'architecture sans mesure attestant d'un préjudice.

Aucun autre problème bloquant n'est consigné dans l'ancien état des lieux ; les cas limites des signaux au démarrage et à l'arrêt, la combinaison d'installation avec iperf3 seul et la limitation du débit des connexions ont été corrigés sur `feat/hardening-batch`, qui doit encore être fusionnée et examinée. Cela ne signifie pas que la branche actuelle a été revalidée sur un hôte réel.

## Limitations

- Les contrôles automatisés vérifient les clés des catalogues, les espaces réservés et la structure des documents, mais les nouvelles traductions n’ont pas encore fait l’objet d’une relecture indépendante par des locuteurs natifs.
- Une arborescence de travail active peut contenir à sa racine des données d’exécution ignorées (`admin_password.txt`, `console_port.txt`, `data/`, `certs/`) et un cache Python (`__pycache__/`). Le contrôleur de structure signale ces fichiers locaux ; une exportation propre des fichiers suivis passe le contrôle. Préservez les données lors d’une migration. Sur un montage CIFS présentant les fichiers en mode fixe 0644 et les répertoires en mode 0755, `chmod` ne change pas le mode affiché des secrets locaux ; il faut examiner séparément le contrôle d’accès du montage.
- Les limites actuelles de validation de cette branche sur un hôte réel sont consignées plus bas.

## Décisions

<a id="vps-decisions"></a>

Les décisions datées ci-dessous conservent à la fois les solutions écartées et leurs coûts. Une décision historique ne constitue pas une nouvelle approbation juridique ou de publication.

| Décisions | Motifs, solutions écartées et coûts |
| --- | --- |
| 2026-09-22 — `proxy` est un seul processus sing-box doté d'au plus quatre entrées, et non quatre clones d'anytls | - **Question résolue, solution non écartée :** le binaire sing-box inclus couvre-t-il vmess/vless/trojan/shadowsocks ? Confirmé en exécutant effectivement les quatre simultanément dans un seul processus (et non par le seul `sing-box check`) ; aucun second moteur nécessaire. hysteria2/tuic ont été essayés puis exclus (exigences différentes en matière de champs et de TLS). - **Écarté :** une unité systemd et une configuration par protocole, reproduisant exactement l'organisation propre à anytls — quatre unités à surveiller, trois certificats autosignés redondants et une structure contraire à celle que réclamerait un futur suivi du trafic par nœud (un seul processus dont la liste `inbounds` est déjà la liste des nœuds). - **Coût :** le binaire commun inclus est désormais utilisé par deux modules indépendants ; le `uninstall()` de chacun **doit** vérifier que la configuration de l'autre existe avant de supprimer le binaire (le script inclus d'anytls comporte cette déviation locale documentée — voir `anytls/.upstream-version`). |
| 2026-09-21 — `prompt_new_settings()` se termine par un `return 0` explicite, au lieu de simplement sortir de la boucle | - **Écarté :** laisser le code de retour de la fonction dépendre de sa dernière boucle `for`, comme dans la plupart des autres fonctions de `install.sh` — la dernière instruction de cette boucle était un `[ -n "$value" ] && export ...` isolé ; si le *dernier* paramètre demandé conservait sa valeur par défaut, ce test échouait et son résultat devenait celui de la fonction. Appelée directement (`prompt_new_settings` dans le corps d'un `if`, mais sans bénéficier elle-même d'une exemption de `set -e`), elle arrêtait silencieusement toute l'installation juste après la dernière invite : aucune erreur, aucune copie de fichier, aucune mise à jour de `VERSION`, aucun redémarrage du service. Reproduit en conditions réelles lors du passage de v1.0.4 à v1.1.1 ; corrigé en plaçant l'export dans `if`/`fi` et en ajoutant un `return 0` explicite à la fin. Le résultat de la fonction ne dépend ainsi plus du dernier paramètre demandé. - **Ne pas retirer le `return 0` final sous prétexte que ce serait du code mort.** C'est le correctif, pas du code standard. |
| 2026-09-19 — Les redirections de ports sont des règles iptables DNAT réappliquées depuis JSON à chaque démarrage ; rien n'est écrit hors du processus | - **Écarté :** un relais `socat` en espace utilisateur par règle — plus sûr (aucune modification de la table NAT ni d'`ip_forward`), mais l'utilisateur a explicitement choisi DNAT+MASQUERADE au niveau du noyau pour ce projet. - **Écarté :** `iptables-persistent` pour conserver les règles dans le noyau après redémarrage — la console et un paquet système deviendraient deux sources de vérité pour les mêmes règles. `app.py` réapplique plutôt son propre JSON à chaque démarrage (DESIGN.md, « Port forwarding lifecycle ») : il n'y a donc qu'une source de vérité. - **Écarté :** ramener automatiquement `net.ipv4.ip_forward` à `0` lorsque la dernière redirection est supprimée — ce paramètre concerne tout l'hôte et d'autres logiciels (dont Docker sur l'hôte de test du projet) peuvent avoir besoin qu'il reste activé. - **Coût :** l'arrêt de `vps-server-web` (et non son redémarrage) retire du noyau toutes les redirections, même activées — même choix de sécurité que pour la fenêtre iperf3. Ne pas déplacer les règles dans une unité distincte toujours active pour « corriger » cela : cette solution a déjà été étudiée et écartée. |
| 2026-09-12 — La page publique et la console disposent de points d'écoute et de classes de gestionnaires distincts | - **Écarté :** un seul point d'écoute pour les deux, avec des routes de console protégées par un préfixe de chemin et un contrôle d'authentification — un contrôle peut être défectueux et laisser passer ; une route inexistante ne le peut pas. - **Écarté :** placer la console elle-même sur 80/443 derrière le mot de passe et supprimer le port aléatoire — cela éliminerait la couche de discrétion voulue par `vps-webserver`. - **Coût :** trois points d'écoute dans un même processus et deux classes de gestionnaires où raccorder séparément l'enregistrement des visiteurs. - **Ne pas réintroduire cette solution sous forme d'amélioration.** |
| 2026-09-12 — iperf3 ne fonctionne que pendant une fenêtre limitée dans le temps, ouverte par l'opérateur | - **Écarté :** un `iperf3 -s` public permanent — n'importe qui pourrait saturer indéfiniment la liaison montante, sans indication de ce qui se passe. - **Écarté :** un service permanent avec authentification RSA `--authorized-users-path` — il faudrait transmettre des identifiants par un autre canal avant tout test, ce qui contredit l'objectif « donner l'adresse IP à quelqu'un pour qu'il mesure ». - **Coût :** une personne distante ne peut pas tester sans intervention ; quelqu’un doit d’abord ouvrir une fenêtre. La page publique annonce son ouverture pour indiquer quand se connecter. |
| 2026-09-12 — Le port 443 utilise un certificat autosigné ; pas d'ACME ni de domaine | - **Écarté :** certbot / acme.sh avec un vrai domaine — la page répond à la question « peut-on joindre cette IP ? » et l'avertissement du navigateur prouve déjà qu'elle est joignable. Dépendre d'un domaine et d'une tâche de renouvellement n'apporte rien à cette question. - **Écarté :** ne servir que le port 80 — cela ne permet pas de distinguer « l'hôte est inaccessible » de « le port 443 est précisément bloqué », cas courant qu'il faut détecter. - **Coût :** chaque visite HTTPS affiche un avertissement sur le certificat. C'est attendu ; ne pas le « corriger » avec HSTS ou une exception épinglée. |
| 2026-09-12 — Le binaire sing-box est livré dans le dépôt, donc tout le projet est sous GPL-3.0 | - **Écarté :** télécharger sing-box à l'installation pour garder un petit dépôt et la licence Apache-2.0 — `Anytsl-Serve` a déjà écarté exactement cela afin de pouvoir installer sans accès à GitHub ; revenir sur ce choix ici annulerait discrètement cet objectif. - **Écarté :** supprimer le module anytls pour préserver la licence Apache-2.0 de `vps-webserver` — la demande consistait à réunir les deux projets, pas à en choisir un. - **Coût :** environ 57 Mo dans git, quantité qui augmente à chaque mise à jour de sing-box ; le code Apache-2.0 de `vps-webserver` est redistribué ici sous GPL-3.0. |
| 2026-09-12 — Les projets amont sont intégrés au dépôt, sans être remplacés ni utilisés comme sous-modules | - **Écarté :** laisser vps-server remplacer `vps-webserver` et `Anytsl-Serve`, puis archiver les deux — les trois doivent rester maintenus et publiés indépendamment. - **Écarté :** des sous-modules git pointant vers les deux dépôts amont — un sous-module ne peut pas porter les renommages nécessaires ici (noms des unités, nom du binaire, `VPSWS_` → `VPSSRV_`) et le clonage nécessiterait alors un accès réseau à deux autres dépôts. - **Coût :** le même code se trouve dans trois dépôts et divergera. Atténuation : les fichiers `.upstream-version` consignent précisément le tag amont de chaque arbre intégré et **doivent** être actualisés dans le même commit que toute mise à jour. |

## Limitations et état actuel de validation

<a id="vps-current-state"></a>

La version 2.0.0 comprend des parcours d’installation expérimentaux pour frps et Lucky. Leur fonctionnement n’a pas été validé sur un hôte réel ; la nouvelle organisation du dépôt n’a fait l’objet que de vérifications automatisées locales pendant ce cycle de publication.

L'instantané des sources du 2026-09-22 décrivait `feat/proxy-protocols` empilée sur `feat/hardening-batch`, non fusionnée. La version 2.0.0 reprend l'arborescence actuelle du projet issue de ces branches, mais les essais du module proxy par l'opérateur sur un hôte réel restent en attente. Les corrections de déduplication des adresses et d'IP publique appliquées indépendamment ont été prises en compte lors de l'examen des branches. Aucune vérification de la fonctionnalité proxy sur un hôte réel n'est revendiquée ici ; l'ancien conteneur utilisait un faux `systemctl` parce que systemd ne tournait pas en PID 1. Les résultats des suites 147/147, 150/150, 153/153 et 156/156, ainsi que les vérifications antérieures sur un hôte réel ci-dessous, sont historiques et non de nouvelles validations.

### Branch record (2026-09-22 status snapshot)

<a id="vps-branch-record-2026-09-22"></a>

L'état initial décrivait la fonctionnalité comme implémentée et testée par son auteur, dans l'attente de l'examen par l'opérateur, empilée sur `feat/hardening-batch` pour son sélecteur indépendant de modules par questions oui/non. Dans la première vérification sur Docker jetable, systemd ne pouvait pas tourner en PID 1 ; `systemctl` a donc été simulé. Les vérifications réelles de configuration sing-box, les règles iptables, le renouvellement des identifiants, la désinstallation tenant compte du binaire partagé et une installation sans intervention suivie d'une nouvelle exécution de mise à niveau ont été exercés. Deux bogues découverts alors ont été corrigés : la validation invalide de `PROXY_PROTOCOLS` était ignorée (zéro entrée), et un port généré dépassait la limite uint16 de sing-box. Le registre annonce 19 nouveaux tests et 147/147 réussites à cette étape ; cela ne constitue **pas** une validation systemd ou sur hôte réel du proxy.

Des essais ultérieurs par l'opérateur ont révélé une séparation artificielle entre `/anytls` et `/proxy`, ainsi que plusieurs cartes principales affichées côte à côte dans la mise en page flex. La branche regroupe désormais toutes les sections des nœuds installés dans une seule carte sur `/proxy`, y redirige `/anytls` et utilise une seule entrée de navigation. La déduplication des adresses et la suppression de la détection automatique de l'IP publique par `get_ip()` ont été réappliquées depuis `main` sur cette branche, plutôt que fusionnées, en raison de la réécriture simultanée de la page proxy ; l’examen **doit** rapprocher ces applications indépendantes. Le registre historique indique une fixture de régression combinant anytls et proxy et des tests de redirection réussis à 150/150, puis un correctif de compte à rebours iperf3 et d'exemple de commande réappliqué depuis `main` à 153/153.

Une demande ultérieure de l'opérateur a remplacé le bouton global de réinitialisation du proxy par un bouton par protocole. `setup-proxy.sh reset <protocol>` préserve les identifiants et les ports des autres protocoles ; `reset` sans argument renouvelle toujours tous les protocoles depuis un terminal, mais pas depuis la console. Des essais en conteneur jetable ont renouvelé un protocole parmi quatre installés, préservé les autres ainsi que l'ensemble des protocoles, et rejeté un nom inconnu sans changer la configuration. Le registre historique annonce six tests ajoutés ou réécrits et 156/156 réussites ; il ne s'agit ici ni d'une nouvelle validation ni d'une annonce de publication.

Pour les travaux publiés auparavant, l'état mentionnait un contrôle par l'opérateur sur hôte réel de la redirection des ports v1.1.0 après le banc d'essai jetable à trois conteneurs et 119/119 tests unitaires. Avant v1.0.0, il consignait les contrôles par l'opérateur sur hôte réel de la page publique sur les deux ports, de la console et du test dans le navigateur, d'iperf3 atteignant 2.8 Gbit/s sur réseau local et refusant les connexions après la fermeture de la fenêtre, de l'installation, la réinitialisation et la suppression d'anytls, de la conservation des réglages lors d'une mise à niveau, et des trois langues de l'interface. Ce sont des observations historiques, non une acceptation de la branche actuelle. L'ancien état désignait la mesure du verrou SQLite comme prochaine investigation, n'indiquait aucun blocage et n'incluait pas dans le périmètre le suivi du trafic, l'assistant de première utilisation, frps, les fonctionnalités `gdy666/lucky` ou les nœuds hautement personnalisables. Leurs emplacements actuels sont [Bogues][local-link-001] et [Objectifs de conception][local-link-002].

## Réorganisation du dépôt dans la version v2.0.0

Ce dépôt place l’implémentation Web dans `src/web/app.py`. Les commandes d’installation et de suppression se trouvent dans `deploy/install.sh` et `deploy/uninstall.sh` ; le code opérationnel est dans `deploy/systemd/`, `deploy/anytls/` et `deploy/proxy/`. Le binaire amd64, les métadonnées de version et la mention d’origine se trouvent désormais dans `third_party/sing-box/{sing-box,sing-box.version,LICENSE}`. Les ressources tierces servies directement restent dans `static/third_party/` ; le vérificateur des dépendances se trouve dans `tools/verify_dependencies/`. L’installation conserve une structure plate (`$PREFIX/app.py`, `$PREFIX/static/`, `$PREFIX/anytls/`, `$PREFIX/proxy/`, `$PREFIX/sing-box`) et les paramètres des modules utilisent toujours `/etc/vps-server-anytls/` et `/etc/vps-server-proxy/`. Les anciens noms de chemins dans les décisions datées et les travaux terminés décrivent leur dépôt historique, pas les instructions actuelles. Les contrôles de migration hors ligne ne sont pas une validation sur hôte réel ou avec systemd ; l’acceptation par l’opérateur reste en attente.

## Historique des travaux terminés

<a id="vps-completed-work"></a>

Ces éléments terminés constituent le registre daté de mise en œuvre et de vérification de l'ancien carnet de tâches, et non un compte rendu de tests nouvellement exécutés. Pour les objectifs restants, voir [Objectifs de conception][local-link-003] ; la question `_db_lock` non résolue figure dans [Bogues][local-link-004].

- Terminé : 2026-09-12 Empêcher l'affichage du commentaire du mainteneur sur la page du journal des changements — `render_changelog()` ne gérait pas les commentaires ; chaque ligne entre `<!--` et `-->` devenait un paragraphe sur la page dans les trois langues. Problème visible dans v1.0.0, corrigé dans v1.0.1.

- Terminé : 2026-09-12 Définir l'architecture et rédiger `DESIGN.md` — fait avant tout code.

- Terminé : 2026-09-12 Intégrer `vps-webserver` v0.4.1 — copier `app.py`, `static/`, `tests/`, `install.sh`, `uninstall.sh`, `systemd/` depuis le tag amont ; inscrire le tag dans `.upstream-version` ; renommer le préfixe d'environnement `VPSWS_` en `VPSSRV_` dans le même commit.

- Terminé : 2026-09-12 Scinder `app.py` en deux gestionnaires — `ConsoleHandler` conserve toutes les routes existantes ; ajouter `ProbeHandler`, qui ne sert que `/` et `/favicon.ico` ; démarrer les points d'écoute publics sur 80 et 443 à côté de celui de la console.

- Terminé : 2026-09-12 Créer la page publique de vérification d'accessibilité — IP source, horloge du serveur, protocole et port d'arrivée, sans autre information sur l'hôte ; pas de JavaScript. La feuille de style a finalement été intégrée dans `PROBE_CSS`, plutôt que dans `static/probe.css` ; le point d'écoute public n'a donc aucune route servant des fichiers.

- Terminé : 2026-09-12 Mettre en œuvre la fenêtre iperf3 — route de console pour ouvrir/fermer, `subprocess.Popen("iperf3 -s -p …")`, échéance en mémoire, thread d'expiration, ouverture/retrait du pare-feu, nettoyage sur `SIGTERM`.

- Terminé : 2026-09-12 Signaler la fenêtre ouverte sur la page publique — port et minutes restantes, pour que la personne distante sache quand se connecter.

- Terminé : 2026-09-12 Intégrer `Anytsl-Serve` v1.2.0 — `anytls/setup-anytls.sh`, le binaire sing-box et `sing-box.version` ; renommer l'unité en `vps-server-anytls.service` et le binaire en `sing-box-vps-server` ; inscrire le tag dans `anytls/.upstream-version`.

- Terminé : 2026-09-12 Transformer `install.sh` en menu de modules — web / anytls / iperf3 sélectionnables indépendamment ; refuser si 80 ou 443 est déjà occupé ; refuser si l'unité amont `sing-box-anytls.service` fonctionne ; ignorer anytls hors amd64. **Écrit, mais jamais exécuté** — voir l'élément de vérification plus bas.

- Terminé : 2026-09-12 Étendre `uninstall.sh` pour supprimer les modules présents — suppression complète par défaut, `KEEP_DATA=1` pour garder la base des visiteurs ; anytls est supprimé avant `$PREFIX`, car son script de suppression se trouve dans `$PREFIX`. **Écrit, mais jamais exécuté.**

- Terminé : 2026-09-12 Exécuter réellement `install.sh` de bout en bout — réalisé par l'opérateur sur un hôte systemd réel avec un préfixe isolé. Le service a démarré, le récapitulatif était correct et l'instance déployée servait la page publique sur 18080 et 18443 avec le bon port d'arrivée, répondait 404 aux routes de la console sur le port public et répondait sur le port de la console. Deux bogues révélés et corrigés : la dernière ligne « pour supprimer » ignorait `PREFIX`/`SERVICE_NAME` (la suppression balayait alors silencieusement les emplacements par défaut sans rien retirer) et tous les exemples d'utilisation indiquaient `./script.sh`, inutilisable depuis une copie de travail CIFS.

- Terminé : 2026-09-12 Vérifier la fenêtre iperf3 dans le bac à sable systemd — effectué sur une véritable instance installée. `NoNewPrivileges` et `ProtectSystem=strict` n'empêchent pas `firewall_port()` : l'ouverture d'une fenêtre ajoutait `-A INPUT -p tcp -m tcp --dport 5201 -j ACCEPT`, sa fermeture retirait la règle. Après suppression, il ne restait ni unité, ni répertoire, ni règle, ni processus, ni point d'écoute.

- Terminé : 2026-09-12 Exécuter `install.sh` avec le module anytls — effectué. La première tentative a échoué avant l'installation de sing-box (le binaire était enregistré avec le mode `100644`, CIFS ayant perdu le bit d'exécution pendant l'intégration, et `install_singbox` vérifiait `-x`) ; après correction des deux côtés, le module s'est installé, les trois constantes renommées se sont retrouvées aux emplacements voulus, le service a démarré et `uninstall.sh` a supprimé l'unité, le binaire, le répertoire de configuration et la règle de pare-feu.

- Terminé : 2026-09-12 Afficher le nœud anytls installé dans la console — `/anytls` indique si le service fonctionne et propose une entrée Clash et un lien `anytls://` copiables. Lecture seule ; `setup-anytls.sh` reste responsable de l'état du nœud.

- Terminé : 2026-09-12 Vérifier `refuse_if_upstream_running` — les trois branches ont été exercées : une unité amont active provoque un refus avec code de sortie 1, son absence permet de continuer et `VPSSRV_ALLOW_DUAL_ANYTLS=1` avertit puis continue. Vérification en dirigeant la protection vers une unité réellement active, plutôt qu'en installant `Anytsl-Serve` : la logique des branches est prouvée, mais la collision exacte ne s'est encore jamais produite sur un hôte.

- Terminé : 2026-09-12 Auditer les couleurs de la console selon WCAG AA dans les deux thèmes — cinq véritables échecs corrigés, le pire étant la ligne iperf « fenêtre ouverte », avec un rapport de 1.77:1 en thème clair, presque invisible sur blanc. Chaque couleur de composant est désormais un jeton sémantique doté d'une valeur pour le thème clair ; `StylesheetTest` protège cette structure.

- Terminé : 2026-09-12 Déduire `VERSION` du vrai tag plutôt que la coder en dur — `app.py` affecte littéralement `VERSION = "0.1.0"`, ce qu'interdit le §1 de `project-management` dans `references/webui.md`, qui le classe parmi les erreurs courantes : un oubli à la publication laisse l'interface afficher la version précédente sans aucun signalement. Lire `git describe --tags --exact-match` à l'installation (ou intégrer le résultat à l'étape de copie de `install.sh`) et utiliser `dev-<short sha>` en repli plutôt qu'un tag obsolète. Hérité de `vps-webserver` ; repéré en lisant webui.md pour le travail sur les couleurs, non corrigé alors car hors périmètre.

- Terminé : 2026-09-12 Rendre `install.sh` compatible avec les mises à niveau — il détecte une installation existante, propose de conserver sa configuration, réapplique les réglages consignés dans les lignes `Environment=` de l'unité, préserve les identifiants du nœud anytls et ne demande que les réglages absents de la version installée. Pour les installations antérieures à `$PREFIX/.install-state`, il déduit les modules présents du disque et précise qu'il ne peut pas calculer la différence concernant les nouveaux réglages.

- Terminé : 2026-09-12 Ajouter un bouton de console pour renouveler le port et le mot de passe anytls — `/anytls/reset`, avec confirmation validée par le serveur ; il appelle `setup-anytls.sh reset` au lieu d'écrire directement l'état du nœud.

- Terminé : 2026-09-12 Effectuer une vraie mise à niveau d'une ancienne installation — réalisé par l'opérateur. Le processus fonctionnait : les réglages ont été réappliqués et le nœud anytls a gardé son port et son mot de passe. Deux bogues découverts et corrigés : le récapitulatif affichait le port public par défaut plutôt que celui restauré, car `PUBLIC_HTTP_PORT` était calculé avant la restauration (la vérification de conflit utilisait la même valeur périmée et surveillait donc le mauvais port) ; le bouton de réinitialisation de la console échouait totalement, car `ProtectSystem=strict` du service web rend `/etc` accessible en lecture seule.

- Terminé : 2026-09-12 Cliquer une fois sur le bouton de réinitialisation anytls après réinstallation — fait, puis vérifié sur l'hôte : le port a changé, le nœud écoute sur le nouveau, la nouvelle règle de pare-feu est présente, **la règle de l'ancien port a été retirée** (aucune règle ACCEPT oubliée) et l'unité temporaire a été nettoyée. Quatre réinstallations successives n'ont laissé aucune règle en double.

- Terminé : 2026-09-12 Audit complet de la sécurité, de la concurrence Python, de la justesse des scripts shell et des divergences documentation/code — onze défauts réels découverts et corrigés ; voir le commit d'audit. Les principaux étaient `VPSSRV_CONSOLE_PORT=0` dans `.env.example`, qui ouvrait le port 0 (une console changeant de port à chaque redémarrage), `install.sh`, qui arrêtait le service avant de vérifier les ports (le laissant arrêté en cas de conflit sans rapport), et une règle de pare-feu orpheline à chaque changement de port anytls hors de `reset`.

- Terminé : 2026-09-12 Renforcer les cas limites du démarrage et de l'arrêt de `main()` dans `app.py` — `try/finally` encadre désormais toute la séquence de démarrage, et non seulement `console.serve_forever()` ; un signal pendant `start_public_listeners()`/`PORTFWD.load()` déclenche ainsi le nettoyage. Les nouveaux `SIGTERM`/`SIGINT` sont ignorés dès le début du nettoyage, afin qu'un second signal pendant `IPERF_WINDOW.close()` n'interrompe pas le retrait de la règle de pare-feu. Chaque point d'écoute reçoit `shutdown()` avant `server_close()`, ce qui évite la trace d'exception `OSError` lors du redémarrage. Un nouveau test au niveau sous-processus lance le vrai `app.py`, confirme qu'il accepte une connexion, envoie un vrai `SIGTERM` et vérifie une sortie rapide et propre : premier test de `main()` lui-même, plutôt que des seules classes de gestionnaires.

- Terminé : 2026-09-12 `VPSSRV_MODULES=iperf3` seul n'installe silencieusement rien — corrigé en rejetant explicitement cette combinaison avec un message clair (iperf3 est un bouton de la console ; sans web, aucune console ne permet de l'ouvrir). Vérifié en conteneur jetable : la voie sans intervention échoue désormais avec le nouveau message, au lieu de se terminer silencieusement avec le code 0.

- Terminé : 2026-09-12 Limiter les tentatives sur `/login` — ajout de `LoginRateLimiter` : une IP qui échoue trop souvent pendant une fenêtre est bloquée pour une durée fixe, puis débloquée par une connexion correcte ou à l'expiration. Simple défense supplémentaire, conformément au périmètre : le mot de passe généré résistait déjà largement à la force brute. Vérification par des tests unitaires directs du limiteur et un test HTTP confirmant que la vraie route `/login` renvoie 429 après blocage.

- Terminé : 2026-09-12 Supprimer la vieille règle ACCEPT `--dport 31515` laissée sur l'hôte du mainteneur par un cycle installation/suppression antérieur à l'accès à `close_firewall` depuis `reset` — `iptables -D INPUT -p tcp --dport 31515 -j ACCEPT`. Ce n'est pas un bogue du code actuel ; consigné pour ne pas le prendre pour tel ultérieurement.

- Terminé : 2026-09-12 Auditer la mise en page de la console — le champ du formulaire iperf était placé un rem au-dessus du bouton, car `.inline-form label` héritait de `margin-bottom: 1rem` et flex `align-items: flex-end` aligne les boîtes en incluant leurs marges ; la grille du tableau de bord restait limitée à deux colonnes alors que les tuiles étaient passées à quatre ; la grille clés/valeurs, les formulaires en ligne et les lignes de copie n'avaient aucune règle pour les écrans étroits. Aucune largeur fixe en pixels et chaque cible tactile respecte le minimum WCAG 2.2 de 24 pixels CSS.

- Terminé : 2026-09-12 Vérifier les boutons de copie dans un navigateur en HTTP non chiffré — fonctionnement confirmé par l'opérateur : la solution de repli `document.execCommand` fonctionne donc en contexte non sécurisé. `navigator.clipboard` est indéfini hors contexte sécurisé, configuration par défaut ; c'est donc la solution de repli `document.execCommand` de `static/copy.js` qui est effectivement utilisée. Les tests unitaires portent sur le balisage de la page, pas sur le comportement du navigateur.

- Terminé : 2026-09-12 Tests des nouvelles fonctions — `ProbeHandler` répond 404 à toutes les routes de la console ; la fenêtre iperf3 expire et tue son processus enfant ; elle ne survit pas à un redémarrage. Les tests couvrent cela ; `firewall_port` est simulé dans les tests de fenêtre afin que la suite ne touche jamais au pare-feu de l'hôte.

- Terminé : 2026-09-12 Rédiger `LICENSE` (GPL-3.0), `LICENSES/` et `THIRD_PARTY_NOTICES.md` — sing-box (GPL-3.0, avec SHA-256 et liens vers le code source correspondant), LibreSpeed (LGPL-3.0), iperf3 (BSD-3-Clause, installé par la distribution et donc non redistribué).

- Terminé : 2026-09-12 Traduire les six documents de gouvernance dans `translated_zh_cn/` et `translated_zh_tw/` — actuellement des modèles non traduits ; distribuer `doc-translator`, une instance par document et par langue.

- Terminé : 2026-09-12 Vérification de bout en bout sur une véritable deuxième machine — accéder à la page publique par 80 et 443 depuis l'extérieur de l'hôte, ouvrir une fenêtre, exécuter `iperf3 -c <ip> --json` et confirmer la présence de `mean_rtt`.

- Terminé : 2026-09-12 Corriger l'échec silencieux de l'installation d'iperf3 par `install_iperf3()` — la fonction exécutait `apt-get update -qq && apt-get install -y -qq iperf3` en une chaîne `&&` dont toute la sortie était masquée. L'échec d'un seul dépôt sans rapport pendant `apt-get update` (un fichier `.list` tiers périmé, constaté sur un vrai VPS) empêchait toute tentative d'installation, sans diagnostic. Correctif : réessayer `apt-get update` jusqu'à trois fois, tenter l'installation même si la mise à jour n'a pas entièrement réussi, définir `DEBIAN_FRONTEND=noninteractive` et ne plus masquer les sorties d'apt. Vérifié par une exécution complète de `install.sh` dans un conteneur Debian 12 jetable avec systemd (et non sur cet hôte réel, pour éviter d'y occuper 80/443 et d'y lancer des services) contenant précisément le dépôt défectueux : iperf3 installé, `vps-server-web.service` actif, console et point d'écoute public répondant HTTP 200. Publié en v1.0.2.

- Terminé : 2026-09-12 Corriger le correctif incomplet de v1.0.2 pour l'installation d'iperf3 — l'opérateur a rencontré un échec réel lors de la mise à niveau d'un hôte de v1.0.1 à v1.0.2 : `apt-get update` signalait une réussite, mais le CDN de `security.debian.org` fournissait un index de paquets périmé ; `apt-get install` recevait donc une erreur 404 en téléchargeant un `.deb` dont l'index venait pourtant d'annoncer l'existence. Réessayer seulement `update` (correctif de v1.0.2) ne résout pas systématiquement ce cas, car la nouvelle tentative peut toucher le même serveur périmé. `install_iperf3()` réessaie désormais toute la paire mise à jour puis installation, jusqu'à trois fois ; confirmation avec un banc d'essai apt simulé qui échoue une fois puis réussit, les mêmes reproductions Docker/conteneur à dépôt défectueux utilisées pour v1.0.2 et une nouvelle exécution complète de `install.sh` en conteneur. Correction également de la section `## Install` du README, qui contenait depuis v1.0.0 les emplacements non remplis de `templates/README.md` (`<repo-url>`, exemple de tag `v0.1.0` jamais publié) : remplacement par la véritable URL GitHub et le tag de la version actuelle. Publié en v1.0.3.

- Terminé : 2026-09-12 Afficher les vraies adresses de la machine dans le récapitulatif final de l'installation — il affichait littéralement les emplacements `<this-server>` / `<本机地址>` : les URL de la page publique et de la console devaient être corrigées à la main avant utilisation ; sur une machine joignable seulement par ZeroTier ou Tailscale, rien n'aidait l'opérateur à choisir l'adresse à essayer. `primary_ip()` prend l'adresse source de `ip -4 route get`, celle que le noyau utiliserait réellement pour sortir de la machine ; `other_ips()` énumère les autres avec leur interface, en réutilisant le filtre d'interfaces de conteneur/pont de `setup-anytls.sh`, mais en conservant volontairement les interfaces VPN, souvent utilisées pour joindre la console. Chaque voie d'échec revient à l'ancien emplacement plutôt que de faire échouer l'installation. Vérifié dans un conteneur systemd jetable doté d'une seconde interface : sortie et alignement des colonnes corrects dans les trois langues, chaque adresse affichée répondait HTTP 200 et la simulation d'une absence totale de `ip` produisait encore le code 0. Publié en v1.0.4.

- Terminé : 2026-09-19 Redirection de ports gérée par la console — permet de rediriger un port TCP/UDP public de cet hôte vers un appareil accessible par Tailscale ou le réseau local (cas où « cette machine possède une IP publique, mais pas l'appareil cible »). Mise en œuvre : iptables DNAT + MASQUERADE par règle, avec commentaire d'identification ; règles conservées en JSON et réappliquées de manière idempotente à chaque démarrage du service (un simple redémarrage comme un redémarrage de la machine les restaure depuis ce fichier ; les tables du noyau seules n'en gardent aucune trace). `net.ipv4.ip_forward` est activé dès que nécessaire et volontairement jamais désactivé automatiquement, car d'autres logiciels de l'hôte peuvent en dépendre. Nouvelle page de console `/portfwd` : ajouter/activer/désactiver/supprimer, protocole tcp/udp/les deux, vérification des conflits entre le port public et tous les autres points d'écoute déjà utilisés par cette installation. Vérifié sur un banc Docker jetable à trois conteneurs (pas cet hôte réel, qui utilise déjà son propre état iptables/NAT Docker, pour les mêmes raisons que les autres tests complets de ce document) : un conteneur « vps » relié à deux réseaux simulait la séparation public/privé, un conteneur « target » l'appareil Tailscale/réseau local et un conteneur « client » un visiteur public. Confirmé en situation : redirections TCP et UDP de bout en bout ; passage automatique de `net.ipv4.ip_forward` de `0` à `1` à la première règle activée ; activation/désactivation modifiant immédiatement l'accessibilité ; arrêt forcé puis deux redémarrages consécutifs du processus réappliquant `portfwd.json` sans doublon iptables ; `SIGTERM` propre retirant toutes les règles du noyau tout en conservant `enabled: true` sur disque pour leur retour au redémarrage ; conflit avec le port de la console et IP cible invalide rejetés avec les bons messages. 119/119 tests unitaires réussis, dont les nouvelles classes `PortForwardManagerTest` (iptables simulé) et `PortForwardConsoleTest` (requêtes HTTP réelles aux routes). Au moment de ce registre, le travail était sur `feat/portfwd`, non fusionné ni publié, dans l'attente du test manuel de l'opérateur ; l'état ultérieur consigne ce test et la [publication v1.1.0][local-link-005].

- Terminé : 2026-09-21 Corriger l'arrêt silencieux de `install.sh` pendant une vraie mise à niveau, découvert par l'opérateur en passant un hôte réel de v1.0.4 à v1.1.1 (`v1.1.0` avait introduit deux nouveaux paramètres `VPSSRV_PORTFWD_*` étaient la première occasion où une mise à niveau devait effectivement demander un nouveau réglage). Dans `prompt_new_settings()`, la dernière boucle `for` se terminait par un `[ -n "$value" ] && export "$var=$value"` isolé ; conserver la valeur par défaut du *dernier* réglage demandé faisait échouer ce test, dont le code de retour devenait celui de la fonction ; appelée directement dans un corps de `if`, sans être elle-même exemptée de `set -e`, elle tuait l'installation juste après la dernière invite sans aucun message d'erreur : ni copie de fichiers, ni mise à jour de `VERSION`, ni redémarrage, laissant la machine silencieusement à l'ancienne version tout en donnant l'impression que la mise à niveau était terminée. Reproduit deux fois sur l'hôte réel de l'opérateur (même symptôme et même valeur périmée d'`ActiveEnterTimestamp`) ; cause précise trouvée avec `bash -x` et une reproduction bash isolée de l'interaction entre `set -e`, `&&` et la boucle. Correctif : envelopper l'export dans `if`/`fi` et ajouter un `return 0` final explicite. Vérifié de deux manières : extrait bash isolé prouvant exactement le mécanisme et sa correction, puis reproduction complète en conteneur systemd jetable — installation de la vraie v1.0.4 suivie d'une session interactive réelle `bash install.sh` via un véritable pseudo-terminal (avec `expect`, et non une entrée standard non interactive ou par tube qui aurait masqué le bogue) pour passer à v1.1.1 : le script non corrigé mourait à la même ligne que chez l'opérateur ; le script corrigé terminait, actualisait `VERSION` et redémarrait le service. Publié en v1.1.2.

- Terminé : 2026-09-19 Prendre en charge davantage de protocoles proxy, à l'exemple de vaxilu/x-ui — anytls était alors le seul type de nœud ; l'utilisateur ne s'attendait pas à un surcoût réel en ajoutant vmess/vless/trojan/shadowsocks, par exemple. Il fallait d'abord décider si sing-box (déjà intégré) couvrait les protocoles souhaités ou si un deuxième moteur était nécessaire. **Question résolue : il les couvre** — confirmé en exécutant effectivement vmess/vless/trojan/shadowsocks(2022-blake3-aes-128-gcm) simultanément dans un seul processus `sing-box run`, et pas seulement en réussissant `check` ; hysteria2/tuic ont été essayés puis écartés (exigences différentes pour les champs/TLS, hors périmètre de cette étape). Nouveau module `proxy/setup-proxy.sh` (propre au projet, non intégré depuis l'amont) : une unité systemd et un config.json pour n'importe quel sous-ensemble des quatre protocoles, partageant le binaire sing-box intégré avec anytls ; `install.sh` a reçu un module `proxy` avec ses propres questions oui/non pour chaque protocole, la conservation des ports et identifiants en cas de mise à niveau (`preserve_proxy()`) et une protection d'architecture amd64 partagée avec anytls. La première version affichait sur `/proxy` une section par protocole installé (port, UUID/mot de passe, SNI commun, entrée Clash, lien de partage, QR) et un seul bouton « tout réinitialiser » ; l'[historique ultérieur de la branche][local-link-006] décrit les boutons individuels qui l'ont remplacé. `PortForwardManager.reserved_ports()` réserve désormais aussi tous les ports proxy installés. Deux vrais bogues découverts par les tests (et non une simple inspection) et corrigés : le `exit 1` de la validation du protocole était absorbé dans un sous-shell de substitution de commande (un `PROXY_PROTOCOLS` invalide pouvait donner une configuration sans aucune entrée) ; la plage aléatoire des ports trojan dépassait la limite uint16 de `listen_port` de sing-box, au-delà de 65535. Vérifié en conteneur Docker jetable (systemd ne pouvait pas démarrer en PID 1 dans la configuration Docker de cette session, donc `systemctl` y était simulé ; tous les autres chemins — génération de configuration, vraies règles iptables, renouvellement d'identifiants, désinstallation respectant le binaire commun — étaient réellement exercés) : cinq nouvelles installations successives, réduction/extension du sous-ensemble de protocoles, réinitialisation, désinstallation et installation `install.sh` complète sans intervention suivie d'une nouvelle exécution en mode mise à niveau confirmant que `preserve_proxy()` maintient ports, UUID, mots de passe et ensemble des protocoles identiques. 19 nouveaux tests unitaires ajoutés à `tests/test_app.py` (147/147 réussis). Construit sur `feat/proxy-protocols`, empilée sur `feat/hardening-batch` non fusionnée (son sélecteur de modules oui/non n'existait pas encore sur `main`) ; ni fusionné, ni publié, ni tagué — examen propre à l'opérateur et test sur hôte réel encore en attente.

- Terminé : 2026-09-19 Code QR pour ajouter un nœud — chaque bloc d'adresse de la page anytls possède désormais un code QR dépliable « Scan to add » contenant le lien de partage de cette adresse, à côté du lien texte copiable existant. Mise en œuvre : kazuhikoarase/qrcode-generator intégré (MIT, `static/qrcode.js` et `static/qrcode-utf8.js` pour les libellés multioctets), rendu côté client en SVG intégré par `static/qrcode-render.js` propre au projet, qui recherche les éléments `[data-qr-text]` ; réutilisable pour tout autre type de nœud ajouté ensuite. Vérification : un test HTTP confirme que le lien de partage est correctement échappé en HTML dans l'attribut (un `&` brut le tronquerait) et que les trois scripts sont référencés ; séparément, le contenu exact du fichier intégré a été exécuté sous Node avec un vrai lien de partage anytls (incluant un libellé Unicode), produisant un SVG QR valide de 41×41 modules, et non un code vide ou cassé — meilleure approximation d'une vérification dans un vrai navigateur disponible dans cet environnement sans écran (pas de serveur X).

- Terminé : 2026-09-19 Installateur modulaire — remplacement du menu numéroté 1/2/3/4 de `install.sh` par trois questions oui/non indépendantes (web, iperf3, anytls), chacun choisi individuellement plutôt qu'à partir d'une liste fixe de combinaisons ; `VPSSRV_MODULES` demeure inchangé pour l'exécution scriptée sans intervention. Les invites concernant iperf3 sont entièrement omises si la réponse pour web est non, puisqu'il n'y aurait alors pas de console pour le piloter. Vérifié en conteneur jetable avec les quatre combinaisons de réponses (défauts, web seul, tous, anytls seul) et les deux régressions en mode sans intervention.

[local-link-001]: #bogues
[local-link-002]: DESIGN.md#objectifs-de-conception
[local-link-003]: DESIGN.md#objectifs-de-conception
[local-link-004]: #bogues
[local-link-005]: #vps-release-v1-1-0
[local-link-006]: #branch-record-2026-09-22-status-snapshot
[local-link-007]: THIRD_PARTY_NOTICES.md

## Passation

- Branche : `feat/node-management`, issue de `feat/ui-redesign` et suivant le dépôt GitHub officiel. Aucune règle temporaire du projet n’a été trouvée.
- Terminé : L’éditeur appelle le secret de connexion « mot de passe » ; le bouton « trafic et cycle » reste en place à l’ouverture. Chaque nœud accepte des limites distinctes en montée et descente, le choix entre 1 Mbps dans les deux sens ou le blocage après le plafond en GiB, des remises à zéro récurrentes tous les nombres de jours/mois/années choisis et une durée de validité facultative bloquante. L’état de version un passe à la version deux à la lecture tout en gardant les ID, les volumes et les plafonds ; les anciennes dates absolues sont effacées pour éviter que leur ancien ralentissement devienne un blocage. Le bouton d’accès par IP reste visible ; les adresses non autorisées sont invitées à se connecter avec le mot de passe puis à ajouter une IP privée dans les réglages. Modifier les réglages d’accès exige toujours le mot de passe. Chaque nœud géré possède un bouton de copie juste avant « Importer dans Clash Meta » ; il copie l’URL d’abonnement LAN. Les cartes se répartissent automatiquement sur 1 à 6 colonnes selon la largeur, sans dépasser 6 sur grand écran. Les informations d’une carte étroite se placent les unes sous les autres.
- Vérifications : 308 tests automatisés réussis (8 ignorés), compilation Python et vérification des espaces des différences réussies. Chromium a vérifié sur l’hôte de test le message d’IP non autorisée et le formulaire des nœuds sur ordinateur et à 390 px ; le bouton de trafic est resté en place à l’ouverture et à la fermeture. nft a accepté en mode vérification les nouvelles règles de débit par sens et de blocage par quota. Le trafic réel avec chaque politique reste à tester. L’hôte de test comptait 3 vrais nœuds ; 3 cartes ont été dupliquées temporairement dans le navigateur pour contrôler la grille, sans créer de nœuds réels. Chromium a confirmé de 1 à 6 colonnes respectivement à 390, 900, 1200, 1440, 1920 et 2560 px, toujours 6 à 3840 px, sans débordement horizontal, ainsi que la copie d’une URL d’abonnement LAN.
- Déploiement : L’hôte de test exécutait la version candidate précédente depuis le répertoire standard de l’application ; les anciens fichiers et l’état des nœuds avaient été sauvegardés hors du dépôt. L’état était déjà passé en version deux. Lors du contrôle du 2026-09-27, les services Web, proxy, compteur de nœuds et AnyTLS étaient actifs et activés au démarrage. Aucun redémarrage réel de l’hôte n’a eu lieu.
- Alignement sur la norme actuelle (2026-09-28) : Les pages de proxy géré et ancien, Lucky, frps, iperf3 et de transfert de ports masquent les identifiants enregistrés et les ports configurés au premier affichage. Une requête autorisée ne récupère une valeur qu’après Show, Copy, Import ou QR ; Hide, la fermeture du QR ou la sortie de la page effacent la valeur révélée. Dans l’éditeur de nœud, laisser vide le nouveau port conserve le port actuel. Le texte des pages Lucky et frps est traduit dans les huit langues de l’interface. La ponctuation des documents chinois a été normalisée sans modifier les exemples de code. La version installée lit désormais la marque de déploiement `VERSION` avant la version fournie dans `config/VERSION`.
- Vérifications de cet alignement : 309 tests réussis (8 ignorés), aucune erreur aux contrôles du format documentaire et du multilinguisme, compilation Python et contrôle des espaces des différences réussis. La structure passe sur une exportation propre des fichiers suivis ; elle échoue dans le répertoire de travail à cause des fichiers d’exécution et caches ignorés déjà décrits dans Limitations. Chromium a vérifié le masquage initial, Show/Hide ainsi que la création et la suppression du QR sur une instance locale. Sur l’hôte de test, connexion LAN, pages de nœuds masquées, révélation autorisée, livraison du script statique, quatre services actifs et écoute Web configurée ont été vérifiés. Chromium a confirmé le retour au masquage après navigation. Le navigateur a refusé la lecture du presse-papiers ; son contenu réel n’a donc pas été vérifié.
- Déploiement de cet alignement : Le répertoire standard de l’application a été mis à jour sur l’hôte de test après sauvegarde de ses anciens fichiers hors du dépôt. Seul le service Web a été redémarré ; son activation au démarrage sous systemd demeure. Aucun redémarrage de l’hôte ni transfert réel pour les politiques n’a été effectué. et la révision de développement déployée a été inscrite.
- Alignement de sécurité actuel : les paramètres de sécurité exigent une vérification du mot de passe administrateur ; la permission dure 10 minutes fixes. La vérification renouvelle la session ; une session limitée à l’IP ne peut ni lire la liste ni modifier les réglages avant cette vérification. Pendant cette période, changer le mot de passe ne demande que la nouvelle valeur et sa confirmation et invalide les anciennes sessions. La liste des IPv4 privées et IPv6 locales uniques possède son propre interrupteur ; chaque accès par IP vérifie à nouveau la liste et l’interrupteur. Le bouton d’import Clash est visible sans survol et le tableau de bord comporte des liens vers le journal des modifications et les paramètres.
- Vérifications de cet alignement : 311 tests automatisés réussis (8 ignorés) ; contrôles du format documentaire et multilingue sans erreur ; compilation Python et contrôle des espaces du diff réussis. Le contrôle des liens locaux signale encore 20 erreurs héritées de fragments traduits (20 dans la base inchangée) ; aucun nouveau lien rompu n’a été ajouté. Chromium a confirmé les tuiles Journal des modifications et Paramètres du tableau de bord, la page de sécurité et son contrôle IP indépendant, un bouton d’import Clash lisible à 390 px et l’absence de défilement horizontal de la page.
- Déploiement de cet alignement : l’hôte de test a reçu la version candidate après une sauvegarde, avec droits 0600, des anciens fichiers Web, catalogues, documents et liste IP. Seul Web a été redémarré. La page de connexion affichait la révision de développement déployée, les quatre services étaient actifs et l’ancien fichier de liste IP était inchangé. Aucun redémarrage réel ni accès par IP depuis un appareil autorisé n’a été testé.
- Réglages actuels : le lien de connexion administrateur redondant a été retiré de la navigation. Les réglages généraux réunissent l’apparence et la langue et sont accessibles à toute session authentifiée, y compris par IP seule. La page Sécurité distincte et toutes les modifications de sécurité exigent toujours l’autorisation temporaire après vérification du mot de passe administrateur. Le formulaire de vérification a une carte moins large et un bouton correctement espacé et aligné. Un lien Tableau de bord précède désormais le test de débit dans la navigation, et Sécurité reprend la même présentation en carte que les autres réglages.
- Vérifications de ce travail : 311 tests automatisés ont réussi (8 ignorés) ; le format documentaire et les traductions n’ont présenté aucune erreur, et la compilation Python ainsi que la vérification des espaces du diff ont réussi. Chromium a confirmé les mises en page bureau et 390 px sans débordement horizontal, la conservation du thème après changement de langue, l’entrée Sécurité distincte, l’espacement du bouton de vérification et le retour correct aux réglages généraux après connexion. La limite des sessions IP seules et la redirection à l’expiration de l’autorisation ont été testées automatiquement ; l’accès réel depuis un appareil autorisé reste à vérifier. Chromium a aussi confirmé l’alignement des trois cartes de réglages et le retour au tableau de bord par le lien supérieur.
- Déploiement de ce travail : l’hôte de test désigné exécute `dev-5c518c0` dans le répertoire standard de l’application. Le code Web précédent, les styles, la version, le fichier de mot de passe administrateur et la liste IP sont sauvegardés hors du dépôt avec des droits 0600 ; ces deux derniers fichiers sont inchangés. Seul Web a été redémarré. Web, proxy, node-meter et AnyTLS étaient actifs et activés au démarrage ; la console écoutait toujours sur son adresse et son port configurés. Chromium a vérifié la connexion LAN et les pages de réglages généraux et de Sécurité. Aucun redémarrage réel n’a été effectué.
- Gestion actuelle des accès aux nœuds : l’ancien éditeur des limites et du cycle s’appelle désormais Gestion des accès dans les huit langues de l’interface. Le plafond de trafic, les limites distinctes de débit montant et descendant, l’action à la limite, l’intervalle de remise à zéro et la durée de validité s’ouvrent dans une boîte de dialogue distincte. À la largeur normale d’une carte, Gestion des accès, Réinitialisation aléatoire et Supprimer le nœud tiennent sur une ligne. Le lien de navigation précédant le test de débit s’appelle désormais Accueil.
- Vérifications de ce travail : 311 tests automatisés réussis (8 ignorés), compilation Python et contrôle des espaces du diff réussis. Chromium a confirmé une seule ligne de trois boutons sur les cartes de bureau en chinois et en anglais, ainsi que dans une vue anglaise de 390 px. Dans la vue étroite, le dialogue a activé son premier champ et gardé Annuler et Enregistrer visibles pendant le défilement. Aucune limite n’a été enregistrée sur l’hôte de test.
- Déploiement de ce travail : l’hôte de test désigné exécute `dev-a785fe5` dans le répertoire standard de l’application. Une sauvegarde de l’ancien code Web, des styles, du script, des langues et de la version, protégée en mode 0600, se trouve hors du répertoire de l’application. Seul le service Web a été redémarré. Les services Web, proxy, node-meter et AnyTLS étaient actifs et activés au démarrage ; la console écoutait toujours sur son adresse et son port précédents et servait la nouvelle version sur le LAN. L’hôte n’a pas été redémarré.
- Revue actuelle des normes (2026-09-28) : les anciens fragments de titre invalides dans les traductions utilisent désormais des ancres stables communes à toutes les langues. Les récapitulatifs d’installation de proxy et d’anytls n’énumèrent que les adresses des interfaces et de Tailscale si disponible, suppriment l’ancien `public-ip.txt` et ne recherchent pas l’IP publique à l’extérieur. `SERVER_IP` n’est plus une option d’installation. Deux liens Fontsource périmés ont été remplacés par des pages sources accessibles.
- Vérifications de cette revue : 311 tests automatisés réussis (8 ignorés) après le changement des récapitulatifs ; syntaxe shell, tests des catalogues et contrôle des espaces du diff réussis. Les 32 documents avaient zéro erreur de format ; quatre avertissements concernent les noms des langues dans la navigation anglaise. Les contrôles multilingue et des liens locaux avaient zéro erreur ; les 13 destinations externes distinctes ont été ouvertes ou vérifiées à leur destination de redirection. Une exportation propre des fichiers suivis a passé le contrôle de structure. Le contrôleur signale cinq entrées d’exécution ou de cache ignorées dans l’arborescence, dont `certs/` ; elles figurent dans les Limitations. Aucune règle temporaire de projet n’a été trouvée.
- Déploiement de cette revue : l’hôte de test désigné exécute `dev-2b7983f` dans le répertoire standard de l’application. Une sauvegarde des anciens scripts, catalogues, documents et de la version, protégée en mode 0600, se trouve hors du répertoire ; les données persistantes des nœuds et les paramètres d’accès n’ont pas changé. Seul le service Web a été redémarré. Les services Web, proxy, node-meter et AnyTLS étaient actifs et activés au démarrage ; la console écoutait toujours sur `0.0.0.0:31080` et servait la nouvelle version sur le LAN. Des échantillons isolés sur l’hôte ont confirmé que les deux récapitulatifs énumèrent les interfaces et Tailscale, omettent l’adresse publique fournie et suppriment l’ancien fichier d’adresse publique. L’hôte n’a pas été redémarré et aucune installation de production n’a été exécutée.
- Publication : les commits `2b7983f` et `933bafa` ont été examinés par rapport à l’ancien état de `origin/feat/node-management` ; le dépôt officiel est public. Aucun identifiant réel, adresse d’hôte privée ou chemin de déploiement local n’a été trouvé dans les changements publiés. Les deux commits ont été poussés sur cette branche ; `main` n’a pas changé.
- Alignement actuel de l'apparence Web (2026-09-28) : les paramètres ordinaires proposent désormais les huit couleurs d'accent prescrites et des modes clair/sombre séparés. Les deux choix persistent dans le stockage local, sont restaurés avant le chargement du CSS et restent indépendants lorsqu'ils sont activés. Les composants partagés existants utilisent des variables de couleur sémantiques dans les deux modes ; l'en-tête étroit enveloppe désormais sa marque et sa version avec un zoom élevé. Les huit catalogues d'interface utilisateur incluent les nouvelles étiquettes d'options. Aucune règle de projet temporaire n'a été trouvée.
- Vérifie cet alignement : 311 tests automatisés réussis (8 ignorés) ; Syntaxe Python et JavaScript, format de document, catalogues multilingues, liens locaux et espaces diff transmis sans erreur. Le vérificateur de documents a retenu deux avertissements de nom propre dans la navigation anglaise. Chromium a confirmé la persistance du thème et du mode après le rechargement et le changement de langue, les 16 combinaisons couleur/mode avaient un contraste d'au moins 4,5 : 1 pour le corps, le texte en sourdine et le bouton principal, et la page Paramètres arabes n'avait pas de débordement horizontal à 390, 320 ou 195 px CSS (la dernière approximativement un zoom de 200 % à 390 px). La disposition des paramètres du bureau et la disposition sombre du mobile ont été inspectées visuellement.
- Déploiement pour cet alignement : l'hôte de test désigné exécute `dev-abe8f0d` à partir du répertoire d'application standard. L'application d'exécution précédente, les styles, le script de thème, les catalogues, les documents et la version ont été sauvegardés en dehors de ce répertoire avec le mode 0600. La racine déployée `app.py` et la copie source, les styles, le script de thème, les catalogues et les documents correspondent désormais à cette révision. Seul le service Web a été redémarré ; les données persistantes et les paramètres d’accès n’ont pas été modifiés. La réponse de connexion LAN inclut les nouveaux choix de thème, le mode d'amorçage et la version, et le script de thème est servi. Web, proxy, node-meter et AnyTLS étaient actifs et activés pour le démarrage ; la console est restée sur son écouteur existant. Aucun redémarrage réel ni aucun transfert de stratégie en direct n'ont été effectués.
- Publication de la version (2026-09-28) : l'opérateur a signalé que les tests fonctionnels ont réussi et a explicitement demandé une version majeure. `v3.0.0` balise `4e26aea` sur la branche `main` du référentiel public officiel ; la version GitHub est publiée, la source balisée est exportée vers le répertoire d'instantanés voisin standard et le journal des modifications complet est synchronisé avec la page enfant `My Projects/vps-server` Notion existante. La description du référentiel a été mise à jour. Les trois blobs exécutables de plus de 10 Mo sont inchangés par rapport à `v2.0.0` ; aucun nouveau blob volumineux ou actif Release n’était nécessaire. L'hôte de test reste sur sa version de développement précédemment déployée ; cette publication ne l'a pas mis à jour.
- Contrôles et travail restant : 311 tests automatisés réussis (8 ignorés) ; Syntaxe Shell et Python, hachages de dépendances, 32 formats de document, structure multilingue, liens locaux, structure de projet d'exportation propre, espaces blancs diff, version `3.0.0` de l'archive finale, `main` distant et cibles de balises, état de version, hachages de fichiers d'instantanés et la page parente, le titre et le contenu Notion ont tous été vérifiés. Quatre avertissements de documents existants concernent les noms de langues dans la navigation en anglais. Un redémarrage réel de l'hôte, une importation dans Clash Meta pour Android sur un vrai téléphone, un transfert en direct via chaque stratégie et une admission IP à partir d'un appareil sur liste autorisée n'ont pas été observés de manière indépendante dans cette préparation de version. Action suivante : vérifier ces comportements sur la cible lorsque cela est possible ; aucune autre étape de publication n’est en cours.
## Historique des modifications

<a id="vps-changelog"></a>

Seules les versions étiquetées sont répertoriées ici. Les entrées suivantes conservent l'historique complet du journal des modifications et enregistrent le contenu de la version actuelle.

### v3.0.0 — 2026-09-28

#### Ajouts

- Les nœuds gérés AnyTLS, VMess, VLESS, Trojan et Shadowsocks peuvent être créés, modifiés, désactivés, réinitialisés et supprimés individuellement. Les numéros d'affichage restent contigus ; les UUID cachés préservent l’identité. Les détails de connexion peuvent être copiés ou importés dans Clash Meta pour Android par lien ou code QR.
- Chaque nœud suit le trafic montant et descendant et prend en charge un plafond de GiB, des limites de vitesse directionnelles distinctes, des réinitialisations récurrentes en jours, mois ou années et une période de validité facultative. Un plafond atteint peut limiter les deux sens à 1 Mbps ou bloquer l'accès ; une période de validité expirée bloque l’accès.
- Un accès sans mot de passe est disponible à une liste blanche d'adresses IP privées explicite. Les paramètres de sécurité nécessitent une vérification récente du mot de passe de l'administrateur, y compris pour les sessions IP uniquement, avant d'exposer ou de modifier les informations d'identification et les règles d'accès.

#### Modifications

- Unification des présentations de la console et de la connexion, des cartes de nœuds réactives, de la navigation dans le tableau de bord et des paramètres. Les paramètres ordinaires proposent désormais huit couleurs d’accent persistantes et des modes clair/sombre indépendants. Les informations d'identification stockées et les ports configurés sont masqués jusqu'à leur révélation ou utilisation autorisée.
- La vue iperf3 sépare l'état du service de son port modifiable. Les mises à niveau du programme d'installation préservent le point d'entrée Web d'exécution et les modules préparés. Les résumés de configuration du proxy affichent les adresses des interfaces et, si disponibles, celles de Tailscale, sans recherche d’adresse IP publique. Les fragments de documents traduits et les liens vers des sources tierces ont été réparés.

#### Vérification et limites

- L'opérateur signale que les tests fonctionnels ont réussi. La suite locale a réussi 311 tests (dont 8 ignorés) ; l'hôte de test désigné a servi les nouveaux actifs de connexion et de thème avec les services Web, proxy, compteur de nœuds et AnyTLS actifs et activés pour le démarrage. Un redémarrage réel et chaque transfert de stratégie en direct n'ont pas été observés de manière indépendante dans cette préparation de version.
- Aucun blob nouveau ou modifié de plus de 10 MB n’a été ajouté. Les exécutables existants sing-box (57 995 520 octets), frps (20 332 728 octets) et Lucky (10 883 644 octets) ont les mêmes ID de blob Git que dans `v2.0.0` ; les enregistrements de provenance et de licence restent dans [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md) . frps et Lucky restent expérimentaux.

### v2.0.0 — 2026-09-27

#### Changed

- Les points d’entrée de l’installation et de la désinstallation ont été déplacés vers `deploy/install.sh` et `deploy/uninstall.sh`, le code Web vers `src/web/`, les dépendances embarquées vers `third_party/` et les métadonnées de version vers `config/`. Les scripts qui utilisaient les anciens chemins du dépôt doivent être mis à jour ; les données d’exécution installées restent à leur emplacement actuel.
- Les anciens documents de tâches en attente, d’état, de décisions et d’historique des modifications ont été regroupés dans `DESIGN.md` et `LOG.md` ; les huit ensembles linguistiques et les liens locaux ont été migrés vers la structure documentaire standard. Les textes de l’interface se trouvent maintenant dans `lang/`, avec des noms de fichiers BCP-47.

#### Added

- Le module proxy à quatre protocoles, sa page commune dans la console, les commandes de renouvellement des identifiants propres à chaque protocole et l’assistant de configuration dans le navigateur ont été intégrés.
- Les installateurs expérimentaux de frps et Lucky et leurs exécutables embarqués ont été intégrés. Leurs fichiers de licence originaux et les empreintes des artefacts figurent dans l’inventaire des composants tiers.

#### Verification and limits

- Suite de tests unitaires locale : 271 tests réussis, 8 ignorés. Les vérifications des empreintes des dépendances, de la documentation et de la structure multilingue ont réussi. Le vérificateur de documents a signalé quatre avertissements concernant les libellés de navigation des documents en anglais.
- Le 2026-09-27, les copies des sept artefacts embarqués dans le dépôt correspondaient aux fichiers des versions amont concernées ; les fichiers de licence originaux des exécutables embarqués correspondaient à ceux de ces archives. Aucune interprétation juridique indépendante n’a été obtenue.
- La validation de cette organisation du dépôt sur un hôte réel avec systemd et la relecture indépendante des traductions par des locuteurs natifs restent en attente. frps et Lucky sont expérimentaux dans cette version.

### v1.1.2 — 2026-09-21

#### Fixed

- Une mise à niveau avec `install.sh` depuis une version antérieure à l'ajout d'un nouveau réglage (comme les réglages de redirection de ports de v1.1.0 pour les utilisateurs de v1.0.4) pouvait s'arrêter silencieusement juste après l'invite du dernier nouveau réglage — avant toute copie de fichiers, mise à jour de `VERSION` ou relance du service — sans message d'erreur. L'hôte restait ainsi à l'ancienne version alors que l'installation semblait s'achever normalement.

### v1.1.1 — 2026-09-20

#### Fixed

- La section Installation du README utilisait encore `--branch v1.0.4` dans la commande rapide sur une ligne comme dans les instructions détaillées. Quiconque les suivait juste après la publication de v1.1.0 installait donc la version précédente, sans la redirection des ports.

### v1.1.0 — 2026-09-19

<a id="vps-release-v1-1-0"></a>

#### Added

- **Redirection de ports gérée depuis la console.** Une nouvelle page « Port forward » permet de rediriger un port TCP/UDP public de cet hôte vers un appareil accessible par Tailscale ou le réseau local — utile lorsque cette machine possède une IP publique et que l'appareil cible n'en possède pas. La console permet d'ajouter, d'activer, de désactiver et de supprimer les règles ; avant application, chacune est comparée à tous les ports déjà utilisés par l'installation (console, page publique, iperf3, anytls). Les règles reposent sur `iptables` DNAT + MASQUERADE et sont automatiquement réappliquées à chaque démarrage du service : un redémarrage du service ou de la machine rétablit immédiatement toutes les redirections actives au lieu de les perdre. `net.ipv4.ip_forward` est activé automatiquement lors du premier besoin. Définir `VPSSRV_PORTFWD_ENABLE=0` pour supprimer entièrement cette fonctionnalité d'une installation.

### v1.0.4 — 2026-09-12

#### Changed

- Le récapitulatif final de l'installation affiche désormais les vraies adresses IP de la machine à la place de l'emplacement littéral `<this-server>`, qu'il fallait remplacer à la main pour rendre les URL utilisables. L'adresse que le noyau utiliserait réellement pour sortir de la machine figure dans les lignes de la page publique et de la console ; sur une machine à plusieurs interfaces, toutes les autres adresses sont listées en dessous avec le nom de leur interface. Un nœud joignable uniquement par ZeroTier ou Tailscale apparaît ainsi sans qu'il faille deviner son adresse. Si aucune adresse ne peut être lue, l'ancien emplacement est affiché comme auparavant, pour qu'une installation par ailleurs réussie n'échoue pas pour une question de présentation.

### v1.0.3 — 2026-09-12

#### Fixed

- `install_iperf3()` pouvait encore échouer malgré le correctif de v1.0.2. `apt-get update` peut signaler une réussite alors que le CDN de `security.debian.org` fournit un index de paquets périmé ; le `apt-get install` suivant reçoit alors une erreur 404 en essayant de récupérer un `.deb` dont l'index venait d'annoncer l'existence — constaté sur un hôte réel passant de v1.0.1 à v1.0.2. Une seule nouvelle tentative de `update` ne suffisait pas systématiquement, puisqu'elle pouvait aboutir au même serveur périmé. L'installateur réessaie désormais ensemble la mise à jour puis l'installation, jusqu'à trois fois ; une tentative ultérieure aboutissant à un miroir synchronisé permet de récupérer.
- La section `## Install` du README contenait encore des emplacements de modèle non remplis : littéralement `<repo-url>` et un exemple de tag `v0.1.0` sous lequel le projet n'a jamais publié de version. Ils indiquent désormais les vraies valeurs : l'URL GitHub du projet et le tag de sa version actuelle.

### v1.0.2 — 2026-09-12

#### Fixed

- `install.sh` pouvait échouer silencieusement à installer iperf3 : les étapes de mise à jour et d'installation apt étaient chaînées et toute leur sortie masquée. Un seul dépôt défectueux sans rapport — un fichier `.list` tiers périmé, comme sur un vrai VPS — faisait échouer la mise à jour et empêchait toute installation d'iperf3, sans explication visible. Le script réessaie désormais la mise à jour, tente l'installation même si celle-ci a échoué et ne masque plus les erreurs d'apt lorsque l'installation échoue réellement.

### v1.0.1 — 2026-09-12

#### Fixed

- La page du journal des changements affichait comme de simples paragraphes le commentaire du mainteneur en bas du fichier CHANGELOG — celui précisant quels titres restent en anglais —, y compris les délimiteurs
  `<!--` et `-->` échappés, dans les trois langues. Le moteur de rendu ne traitait pas du tout les commentaires. Seul l'affichage était touché ; rien d'autre n'était affecté.

### v1.0.0 — 2026-09-12

Première version. Elle réunit deux projets existants — une console de test de débit VPS protégée par mot de passe et un installateur `anytls` fondé sur sing-box — et ajoute deux fonctions qu'aucun ne possédait : une fenêtre iperf3 à la demande et une page publique permettant à chacun de vérifier si votre IP répond sur le Web.

#### Added

- **Page publique de vérification d'accessibilité sur les ports 80 et 443, sans connexion.** Donnez l'IP à quelqu'un : si la page s'affiche, vos ports Web sont joignables depuis son emplacement. Elle indique son adresse source, l'horloge du serveur, ainsi que le port et le protocole d'arrivée — sans autre information sur l'hôte. Le service sur les deux ports est délibéré : il distingue « l'hôte est inaccessible » de « le port 443 est précisément bloqué ».
- **Fenêtre iperf3 à la demande.** La console ouvre une fenêtre limitée dans le temps ; `iperf3` ne fonctionne que pendant cette période, ouvre son port dans le pare-feu actif et ferme le serveur et le port à l'expiration de la fenêtre, sur demande ou à l'arrêt du service. Il n'existe aucune option « laisser tourner », car un serveur iperf3 ouvert permettrait à n'importe qui de saturer la liaison montante. Tant qu'une fenêtre est ouverte, la page publique le signale pour indiquer à la personne effectuant le test quand se connecter.
- **Test de débit dans le navigateur et journal des visiteurs**, accessibles depuis la console : mesure des débits montant et descendant avec le moteur LibreSpeed et relevé de chaque connexion TCP entrante, quel que soit le port — pas seulement HTTP — lu depuis la table des connexions du noyau.
- **Module proxy anytls.** sing-box avec certificat autosigné, ainsi que BBR. La console affiche le port, le mot de passe et le SNI du nœud, propose son entrée Clash et son lien `anytls://` avec boutons de copie et permet de renouveler les identifiants.
- **Installateur à sélection de modules.** web, iperf3 et anytls sont choisis indépendamment, en mode interactif ou par `VPSSRV_MODULES` pour une exécution sans intervention. Il refuse d'entrer en conflit avec le port occupé par un autre processus et ignore anytls hors x86-64 plutôt que d'installer un binaire inexécutable.
- **Réinstallation prenant en charge les mises à niveau.** Une nouvelle exécution de l'installateur détecte l'installation existante, propose de garder sa configuration, réapplique les réglages consignés dans l'unité du service, conserve les identifiants du nœud anytls et ne demande que les réglages absents de la version installée. Pour les installations antérieures à cet enregistrement, la liste des modules est lue sur le disque.
- **Trois langues d'interface** — anglais, chinois simplifié, chinois traditionnel — choisies à l'installation, modifiables à chaque visite et mémorisées.
- **Installation hors ligne.** Le binaire sing-box est livré dans le dépôt ; l'installation ne nécessite donc rien d'autre que le miroir de paquets de votre distribution.

**Notes de version (v1.0.0) :**

- Tout le projet est sous GPL-3.0, car il redistribue le binaire sing-box sous GPL-3.0. Les licences des composants et les liens vers le code source correspondant requis par la GPL figurent dans [THIRD_PARTY_NOTICES.md][local-link-007].
- TLS sur 443 utilise un certificat autosigné : ni domaine ni ACME. L'avertissement du navigateur prouve néanmoins que le port répond, ce qui est précisément la question à laquelle cette page sert à répondre.
- `mean_rtt` dans la sortie JSON d'iperf3 provient de `TCP_INFO` du noyau : un client Linux indique donc le temps aller-retour, tandis qu'un client incapable de le lire — iperf3 sous Cygwin sous Windows, par exemple — n'indique que le débit. Le mode UDP (`-u`) fournit partout la gigue et la perte de paquets.
- Le module anytls fonctionne uniquement sur x86-64. Les modules web et iperf3 sont indépendants de l'architecture.

## Historique des commits

Ces entrées conservent les sujets des commits Git dans l’ordre chronologique. La dernière entrée correspond à ce commit de documentation.

- `b3cc391` docs: add documentation skeleton and agreed design
- `63f1680` feat(web): vendor the web module and add the public page and iperf3 window
- `c0def78` feat(anytls): vendor the anytls module and record third-party licences
- `dc70d9b` feat(install): turn the installer into a module menu
- `fcf7878` fix(install): print a teardown command that actually works
- `6022737` docs: record that the iperf3 window works under systemd sandboxing
- `790b7c6` fix(anytls): install the sing-box binary that was there all along
- `f0862d0` feat(console): add an anytls node page, and stop the iperf buttons competing
- `aa01a30` feat(console): show the anytls port, password and every usable address
- `901cc0c` fix(ui): make the copy button quiet, and every colour survive light mode
- `5c6e65a` feat(anytls): let the console rotate the node's port and password
- `27e2c9d` docs(anytls): keep the upstream tag as the file's last line
- `03bb980` feat(install): carry an existing install's settings across an upgrade
- `33d8488` fix(anytls): run the reset outside this service's sandbox
- `00bf933` fix(anytls): stop a raw iptables line leaking into the install summary
- `c8330ba` fix: eleven defects from a full audit
- `0be4851` docs(backlog): tick the anytls vendoring item, done since c0def78
- `a9d6b1d` fix(ui): align the iperf form, and let the layout survive a narrow screen
- `3843ccb` docs: correct two stale backlog ticks and the mean_rtt claim
- `cc0cf4d` docs: record three more verifications, and what is left
- `8e2ea5e` chore(release): v1.0.0
- `40a4bc3` fix(changelog): stop rendering the maintainer comment to readers
- `bbc7bd1` chore(release): v1.0.1
- `98d3bf7` chore(release): v1.0.2
- `aceecfd` chore(release): v1.0.3
- `e723745` chore(release): v1.0.4
- `4983c10` refactor(docs): migrate docs to doc/ + doc/<lang>/ layout
- `a468514` docs(i18n): scaffold five extended-language placeholders, fix README Install
- `42ffe49` docs(i18n): sync README Install one-liner to zh_cn/zh_tw translations
- `0bbb682` feat(portfwd): console-managed iptables port forwarding
- `2b3caee` docs(backlog): record web-based first-run setup page idea
- `14608c6` chore(release): v1.1.0
- `eace062` chore(release): v1.1.1
- `9e09d8a` fix(install): stop install.sh silently dying mid-upgrade
- `5451526` refactor(project): publish standardized project tree
- `f300ab7` docs(log): record GitHub synchronization
- `53c390c` chore(release): prepare v2.0.0 content
- `f9eb612` docs(release): verify bundled artifact provenance
- `5868549` docs(log): record v2.0.0 publication handoff
- `56c9ed5` docs(readme): translate installation example comments
- `51e89bc` feat(nodes): scaffold numbering and refresh proxy workspace
- `ed58969` feat(nodes): add managed controls and traffic policing
- `d0d6ae7` docs: restore required multilingual sections
- `84b9599` fix(web): show development revision in checkout
- `e986c51` fix(install): create flat entry during in-place install
- `eaceed8` fix(install): stage modules during in-place install
- `5ff2a6b` fix(web): condense mobile navigation
- `2477fcc` docs: record node deployment handoff
- `d31e40f` docs(log): synchronize commit history
- `0696e4b` fix(nodes): keep sustained traffic within 1 Mbps
- `da5f84f` docs(log): record measured node acceptance
- `b74b412` feat(proxy): add Clash Meta import and GiB node controls
- `773eedf` feat(web): unify console and setup interface design
- `9a615ab` feat(nodes): support multiple nodes and in-place editing
- `6c1459d` docs(log): record node management delivery
- `47b3686` feat(console): refine nodes, login and iperf3 port
- `3d69356` docs(log): record GitHub synchronization
- `6e461a3` fix(iperf): clarify finished state
- `a676537` feat(nodes): add per-node switch and compact numbering
- `ab02c17` docs(log): record node switch acceptance
- `860cdc4` feat(auth): add private-IP access and admin settings
- `ad08a80` feat(web): refine access screens and proxy node cards
- `be8b4a5` feat(nodes): add flexible limits and persistent IP login entry
- `b0a9c6c` feat(web): copy Clash links and fit up to six node columns
- `d07b40a` fix(web): mask configured values and align project documents
- `7065e18` fix(web): honor installed version stamp
- `b870053` fix(web): prioritize deployed stamp over stale git metadata
- `81f1e13` feat(auth): align security settings and dashboard access
- `7524ec3` docs(log): record security alignment checks and deployment
- `b1a8f21` feat(web): separate preferences from security settings
- `dd9627f` fix(web): keep security entry visible in settings
- `0fc871a` fix(auth): return to requested settings page after login
- `5c518c0` fix(web): add dashboard link and align security card
- `9db2482` docs(log): record settings review and deployment
- `fdf8fbc` feat(nodes): move access limits into dialog
- `a785fe5` fix(nodes): keep action buttons on one row
- `d03abb7` docs(log): record access dialog and test deployment
- `2b7983f` fix(standards): align setup addresses and document links
- `933bafa` docs(log): finish standards audit handoff
- `e2778a5` docs(log): record formal branch publication
- `abe8f0d` feat(web): align appearance with current theme standard
- `2d624db` docs(log): record appearance deployment
- `4e26aea` chore(release): prepare v3.0.0 content
- (this commit) docs(log): record v3.0.0 publication
