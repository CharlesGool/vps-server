---
name: project-changelog-fr
description: Historique des modifications
metadata:
  version: "1.0.0"
  lang: "fr"
---

# Historique des modifications

## Multilingue

[简体中文](../CHANGELOG.md) | [English](../en/CHANGELOG.md) | [繁體中文(台灣)](../zh-TW/CHANGELOG.md) | [繁體中文(香港)](../zh-HK/CHANGELOG.md) | [हिन्दी](../hi/CHANGELOG.md) | [Español](../es/CHANGELOG.md) | [العربية](../ar/CHANGELOG.md) | **Français**

## Documentation

- Présentation du projet : [README](README.md)

- Justification de la conception : [DESIGN](DESIGN.md)

- État du projet: [LOG](LOG.md)
- Archives historiques: [HISTORY](HISTORY.md)
- Historique des modifications: [CHANGELOG](CHANGELOG.md)
- Historique des commits: [COMMITS](COMMITS.md)

- Avis relatifs aux tiers : [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Historique des modifications

<a id="vps-changelog"></a>

Seules les versions étiquetées sont répertoriées ici. Les entrées suivantes conservent l'historique complet du journal des modifications et enregistrent le contenu de la version actuelle.

### v5.0.0 — 2026-10-03

#### Ajouts

- La console peut lancer un test TCP ou UDP de durée limitée vers un autre serveur iperf3 et affiche des commandes courtes pour le serveur et le client.
- Les pages publiques HTTP et HTTPS ont des interrupteurs et des entrées Home distincts ; l’identité du serveur est enregistrée et affichée dans la navigation et le titre du navigateur.

#### Modifications

- La première installation se termine dans le terminal et n’installe que la console Web par défaut ; les autres modules sont ajoutés au besoin depuis Modules. L’activation de FRPC est indépendante de l’exécution de ses instances clientes.
- Les gestionnaires Web et les styles sont organisés par fonction, avec les ressources statiques dans `src/web/static/` ; la documentation est répartie entre source en chinois simplifié, archives historiques, historique des modifications et traductions.
- Un redémarrage ordinaire du service Web conserve les sessions de connexion non expirées ; changer le mot de passe invalide les anciennes sessions.

#### Corrections

- Les noms d’instances FRPC acceptent les lettres et chiffres Unicode ; réinstaller un module préserve les nœuds et l’état du service et confirme le résultat d’un interrupteur avant le redémarrage.
- La désinstallation complète affiche son message final traduit et se termine avec succès après la suppression du répertoire d’installation.

### v4.0.0 — 2026-09-29

#### Ajouts

- La configuration initiale dans le navigateur permet de choisir les modules, la langue, l’authentification et les ports grâce à un serveur HTTPS temporaire et un mot de passe à usage unique. Depuis les paramètres, la console installée peut ajouter ou supprimer des modules facultatifs et affiche l’état et le journal de chaque opération.
- Les instances FRPC locales peuvent être créées, renommées, modifiées, activées, désactivées, testées et supprimées. L’éditeur prend en charge les proxys TCP et UDP simples authentifiés par jeton, vérifie les modifications avec `frpc` et rétablit la configuration précédente si leur application échoue. L’installation de FRPC est indépendante de FRPS ; son binaire client, dont l’empreinte est vérifiée, est distribué comme fichier `frpc-0.71.0-linux-amd64` de la GitHub Release.
- La page d’accueil dispose de pages et d’entrées distinctes pour FRPS et FRPC. Les pages des fonctions désactivées renvoient vers une page de fermeture traduite.

#### Modifications

- La page d’accueil présente les neuf fonctions principales sous forme de cartes munies chacune d’un interrupteur. La gestion des modules se trouve désormais dans les paramètres ordinaires ; les paramètres de sécurité exigent toujours une vérification récente du mot de passe administrateur.
- Les cartes FRPC et celles des nœuds proxy présentent plus clairement les actions de modification, de test, de révélation et de confirmation. La modification d’une instance conserve l’adresse et le jeton actuels du serveur sauf changement explicite, et les champs des proxys distinguent les ports locaux des ports du serveur.
- La connexion, la navigation dans les paramètres, les icônes des pages, les contrôles de mot de passe, le thème et la mise en page adaptative suivent le design actuel de la console. Le texte utilise les polices du système pour garder des dimensions stables lors de l’actualisation. L’animation de transition entre pages a été supprimée à la suite des retours de l’opérateur ; l’animation lors du redimensionnement reste présente.
- Les interrupteurs du transfert de ports appliquent les règles dans le processus Web en cours sans redémarrer la console. Les soumissions répétées d’une action de module ramènent à la page, et les connexions POST rejetées se ferment correctement sans mal interpréter la requête suivante.

#### Corrections

- L’ajout d’un proxy FRPC ne demande plus l’indice réservé à sa modification ou à sa suppression. La collecte des visites s’arrête lorsque la fonction est désactivée, et les contrôles des nœuds proxy conservent les valeurs enregistrées lorsqu’on les rouvre.

#### Vérifications et limites

- La suite locale a réussi 341 tests, avec 8 tests ignorés. Sur l’hôte de test désigné, les routes authentifiées, la séparation des pages FRPS et FRPC, les interrupteurs des modules, la redirection vers la page de fermeture, la validation de la configuration FRPC et le proxy TCP demandé par l’utilisateur sur le port distant redacted-remote-port ont été vérifiés. L’opérateur a jugé le comportement actuel à l’actualisation acceptable. L’hôte exécute toujours une version de test corrigée ; ce tag officiel des sources ne met pas à lui seul cette installation à niveau.
- L’affichage sur un vrai téléphone, la persistance après redémarrage, une installation complète sur un hôte vierge à partir de ce tag final et toutes les combinaisons réelles des politiques de proxy ou de transfert de ports restent à vérifier. Les trois gros binaires déjà publiés sont inchangés depuis v3.0.0. Le client FRPC est un nouveau fichier de Release de 16 593 080 octets, de SHA-256 `f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068` ; l’installateur vérifie cette empreinte avant de l’utiliser.

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