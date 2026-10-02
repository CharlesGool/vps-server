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

[简体中文](../LOG.md) | [English](../en/LOG.md) | [繁體中文(台灣)](../zh-TW/LOG.md) | [繁體中文(香港)](../zh-HK/LOG.md) | [हिन्दी](../hi/LOG.md) | [Español](../es/LOG.md) | [العربية](../ar/LOG.md) | **Français**

## Documentation

- Présentation du projet : [README](README.md)

- Justification de la conception : [DESIGN](DESIGN.md)

- État du projet: [LOG](LOG.md)
- Archives historiques: [HISTORY](HISTORY.md)
- Historique des modifications: [CHANGELOG](CHANGELOG.md)
- Historique des commits: [COMMITS](COMMITS.md)

- Avis relatifs aux tiers : [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Archives

- [Archives historiques](HISTORY.md)
- [Historique des modifications](CHANGELOG.md)
- [Historique des commits](COMMITS.md)

## Bogues

- [ ] 2026-09-12 Déterminer si le verrou partagé `_db_lock` doit être dissocié — chaque accès à la page publique prend un verrou à l'échelle du processus et écrit de façon synchrone dans SQLite ; la console partage ce verrou. En théorie, un afflux anonyme peut donc ralentir une page authentifiée. **Mesuré, mais non reproduit** : 60 clients simultanés générant un afflux ont laissé la latence de la console à 0.4–0.6 ms, comme au repos. Consigné pour éviter de redécouvrir ce mécanisme ; ne pas revoir l'architecture sans mesure attestant d'un préjudice.

Aucun autre problème bloquant n'est consigné dans l'ancien état des lieux ; les cas limites des signaux au démarrage et à l'arrêt, la combinaison d'installation avec iperf3 seul et la limitation du débit des connexions ont été corrigés sur `feat/hardening-batch`, qui doit encore être fusionnée et examinée. Cela ne signifie pas que la branche actuelle a été revalidée sur un hôte réel.

## Limitations

- Les contrôles automatisés vérifient les clés des catalogues, les espaces réservés et la structure des documents, mais les nouvelles traductions n’ont pas encore fait l’objet d’une relecture indépendante par des locuteurs natifs.
- Avant la migration, les sources en chinois simplifié des quatre documents principaux et leurs anciennes traductions se trouvaient dans des chemins différents ; la base complète d’une même synchronisation n’a pas pu être reconstituée. Les sept langues ont été entièrement resynchronisées avec le texte actuel en chinois simplifié ; les prochaines mises à jour reprendront la traduction incrémentale depuis ce commit. Les comptes rendus d’essais qui n’existaient qu’en anglais sont conservés comme archives historiques ; leur périmètre est précisé dans [HISTORY](HISTORY.md).
- Lors de la standardisation du 2026-10-03, les anciennes données d’exécution et caches ignorés par Git ont été déplacés sans modification de la racine des sources vers `private/local-runtime-prestandardization-20261003/` ; l’arbre de travail actuel passe le contrôle de structure. Si un montage CIFS présente toujours les fichiers en mode 0644 et les répertoires en mode 0755, `chmod` ne change pas le mode affiché des fichiers confidentiels locaux ; examinez séparément le contrôle d’accès du montage.
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

## Passation

La branche de publication actuelle, le travail terminé, les résultats des contrôles, les étapes restantes et la prochaine action sont tenus à jour dans la [passation actuelle du LOG.md en chinois simplifié](../LOG.md#交接).
