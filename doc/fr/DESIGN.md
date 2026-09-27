---
name: project-design-fr
description: Architecture et contraintes de conception du projet
metadata:
  version: "1.0.0"
  lang: "fr"
---

# vps-server — Conception

## Multilingue

[English](../DESIGN.md) | [简体中文](../zh-CN/DESIGN.md) | [繁體中文(台灣)](../zh-TW/DESIGN.md) | [繁體中文(香港)](../zh-HK/DESIGN.md) | [हिन्दी](../hi/DESIGN.md) | [Español](../es/DESIGN.md) | [العربية](../ar/DESIGN.md) | **Français**

## Documentation

- Présentation du projet : [README](README.md)

- Justification de la conception : [DESIGN](DESIGN.md)

- Historique des versions : [LOG](LOG.md)

- Avis relatifs aux tiers : [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Objectifs de conception

**Objectifs réalisés dans la version v2.0.0 (voir les [limites de validation][local-link-001]) :**

La version 2.0.0 comprend également des parcours d’installation expérimentaux pour frps et Lucky. Leur fonctionnement n’a pas été validé sur un hôte réel ; les objectifs ci-dessous décrivent les quatre modules documentés auparavant.

- Installer, sur un VPS Debian/Ubuntu neuf, un ensemble unique avec quatre modules sélectionnables
  fournissant cinq fonctionnalités (le module Web comprend la page publique et la console privée) :
  1. **Page publique d'accessibilité** — une page volontairement minimale servie sur les ports TCP
     **80 et 443**, sans authentification, permettant à quiconque ne connaissant que l'adresse IP
     de vérifier dans son navigateur si les ports Web de cet hôte sont accessibles depuis son emplacement.
  2. **Console privée** — un tableau de bord protégé par mot de passe, sur un port élevé aléatoire
     conservé sur disque, permettant de tester les débits montant et descendant dans le navigateur
     et de consulter les connexions entrantes récemment observées.
  3. **Fenêtre iperf3 à la demande** — un point de test de bande passante et de latence
     **désactivé par défaut** ; l'opérateur ouvre depuis la console une fenêtre de durée limitée,
     qui se referme automatiquement à l'échéance.
  4. **Proxy anytls** — une entrée `anytls` de sing-box avec certificat autosigné, ainsi que BBR.
  5. **Proxy** — n'importe quel sous-ensemble des entrées `vmess`/`vless`/`trojan`/`shadowsocks`
     de sing-box, partageant une seule unité systemd, une seule configuration et le même binaire
     sing-box embarqué que le module anytls. Voir « Le module proxy » ci-dessous.
- Pouvoir être installé sans accès réseau sortant en dehors du miroir de paquets de la distribution.
  Le binaire sing-box est livré dans le dépôt.
- Coexister sur le même hôte avec `vps-webserver` et `Anytsl-Serve` sans conflit de noms d'unités
  systemd, de préfixes d'installation ou de variables d'environnement, ni de ports persistants.

**Objectifs suivis et état actuel :**

- [x] 2026-09-19 Trafic, plafond de données et expiration par nœud : les cinq protocoles proxy suivent séparément les volumes montant et descendant de chaque nœud ; après le plafond ou l’expiration, chaque direction est limitée à 1 Mbps. Un cycle mensuel ou à une date définie remet les compteurs à zéro et lève la limite. L’implémentation a passé les essais sur hôte réel le 2026-09-27.
- [x] 2026-09-19 Configuration initiale dans le navigateur : cette version utilise un assistant de configuration de courte durée dans `tools/setup_wizard/setup_wizard.py` lorsque l’installateur interactif ne reçoit aucune valeur `VPSSRV_MODULES`. Il recueille les choix de langue, de modules, de ports et d’authentification ; l’installateur shell n’exécute les actions choisies qu’après validation du résultat. Cette version n’a pas encore été validée sur un hôte réel.
- [ ] 2026-09-22 Achever la prise en charge de frps dans la console pour les jetons et les informations de connexion. L’installateur propose désormais frps, mais le périmètre de la console reste à définir : ces informations désignent-elles un jeton d’authentification, un extrait de configuration client ou une liste des proxys connectés ?
- [ ] Définir le périmètre de la demande plus large de fonctionnalités de `gdy666/lucky` consignée dans l’instantané du 2026-09-22. Le dépôt propose maintenant un parcours d’installation de Lucky, mais aucune liste de fonctionnalités plus larges ni aucun critère de validation n’étaient consignés.
- [x] Terminer la validation des contrôles des nœuds sur un hôte réel : numéros stables, noms modifiables et UUID masqués ; modification du port, de l’identifiant et du SNI des nœuds TLS ; SNI indiqué comme sans objet pour Shadowsocks ; changement aléatoire du port et de l’identifiant sans modifier le SNI. Les contrôles ont passé les essais sur hôte réel le 2026-09-27.
- [x] Toute la Web UI a été repensée avec un système visuel clair et cohérent pour la console, la page publique de connectivité et l’assistant de configuration. La réalisation du 2026-09-27 harmonise espacements et commandes, propose quatre couleurs d’accent mémorisées, des polices et icônes intégrées, un focus visible et des mises en page adaptatives.

La question du verrou SQLite partagé est une [question de mesure connue mais non résolue][local-link-002], pas une obligation de modifier l'architecture. Les travaux achevés et les vérifications historiques figurent dans le [LOG][local-link-003].

**Hors périmètre**

- **Ne remplace pas `vps-webserver` ni `Anytsl-Serve`.** Tous deux restent maintenus et publiés
  indépendamment. vps-server embarque leur code plutôt que de les importer ou de les supplanter ;
  voir les [Décisions][local-link-004] pour le compromis de divergence accepté et son atténuation.
- **Pas d'ACME, de Let's Encrypt ni de nom de domaine.** TLS sur 443 utilise un certificat autosigné.
  La page publique doit répondre à la question « cette IP est-elle accessible ? », à laquelle
  une page d'avertissement du navigateur répond déjà. Renouveler le certificat et dépendre
  d'un domaine n'apporterait rien à cette fonction.
- **Pas d'iperf3 permanent.** Un `iperf3 -s` public sans authentification permettrait à un inconnu
  de saturer la liaison montante de l'hôte aussi longtemps qu'il le souhaite.
- **La page publique ne révèle rien sur l'hôte.** Ni nom d'hôte, ni version du noyau, ni durée de
  fonctionnement, ni inventaire des services, ni liste de ports, ni paramètres anytls. Elle indique
  uniquement que la connexion a abouti, l'IP source vue, l'heure du serveur et le port/protocole
  emprunté parmi les deux.
- **Pas de proxy inverse, de nginx ni de conteneurs.** Le processus Python termine lui-même TLS,
  comme le fait déjà `vps-webserver`.
- **Pas de choix entre plusieurs serveurs de test de débit.** Un seul hôte : celui-ci.

## Architecture

Le service Web, le service anytls et le service proxy facultatif tournent dans des processus distincts ; le service Web lance aussi un processus enfant iperf3 temporaire. La console et la page publique utilisent des écouteurs distincts dans un seul processus Python et partagent l'état en mémoire. Seul le trafic client configuré atteint ces services.

```
                       ┌──────────────────────── vps-server-web.service ───────┐
  anyone, no auth      │                                                       │
  :80  ──────────────► │  public listener (HTTP)  ──┐                          │
  :443 ──────────────► │  public listener (HTTPS) ──┤                          │
                       │                            ├─► ProbeHandler           │
                       │                            │   (reachability page)    │
                       │                            │                          │
  operator, password   │                            │                          │
  :<random> ─────────► │  console listener  ───────►│   ConsoleHandler         │
                       │                            │   ├─ LibreSpeed endpoints│
                       │                            │   ├─ visitor log         │
                       │                            │   └─ iperf3 window ctl ──┼──┐
                       │                            │                          │  │
                       │  connection poller ◄───────┴── /proc/net/tcp[6]       │  │
                       │  (all ports, not just HTTP)                           │  │
                       └───────────────────────────────────────────────────────┘  │
                                                                                   │
  tester with iperf3      :5201 ◄────────────── iperf3 -s  (child process, ────────┘
  client                                         killed when window expires)

                       ┌─── vps-server-anytls.service ───┐
  proxy client ──────► │  sing-box, anytls inbound, TLS  │
  :<random>            │  self-signed cert               │
                       └─────────────────────────────────┘
```

Le schéma montre les unités Web et anytls ; le service facultatif `vps-server-proxy.service` exécute plusieurs entrées indépendantes dans un troisième processus, partageant le binaire sing-box embarqué mais pas l'état des deux autres unités. Chaque module peut être choisi séparément ; voir [Le module proxy][local-link-005].

### Pourquoi la page publique et la console ont des écouteurs distincts

Leurs exigences de sécurité sont opposées ; les fusionner obligerait l'un des deux à abandonner les siennes. La console est authentifiée et utilise un port difficile à deviner précisément pour ne pas être découverte facilement ; la page publique **doit** être facile à découvrir et
**ne doit pas** demander de mot de passe. D'où des ports, gestionnaires de requêtes et tables de routes distincts. Une requête arrivant sur 80/443 ne peut jamais atteindre une route de console : `ProbeHandler` n'en possède aucune. Ce n'est pas un contrôle qui la rejette. C'est essentiel : un contrôle d'autorisation peut comporter un bogue, une route absente non.

La page publique accepte `GET` et `HEAD` sur exactement deux chemins (`/` et `/favicon.ico`) et répond 404 à toute autre requête. Elle ne lit aucune chaîne de requête, n'analyse aucun corps de requête et ne définit aucun cookie.

### Mise à niveau d'une installation existante

`install.sh` détecte une installation existante et propose de conserver sa configuration. Accepter rejoue les valeurs enregistrées par l'installation précédente ; refuser redemande tous les choix. Dans les deux cas, le mot de passe de la console, le port conservé, les certificats et le journal des visiteurs subsistent : l'installateur ne touche jamais à ces fichiers.

Deux enregistrements répondent à deux questions différentes :

- **Les lignes `Environment=` de l'unité systemd** indiquent ce qui a été *défini*. Les rejouer empêche un réglage choisi une fois — un port public personnalisé ou TLS pour la console — de revenir silencieusement à sa valeur par défaut lors de la mise à niveau suivante.
- **`$PREFIX/.install-state`** indique ce que la version installée *connaissait* : sa version, sa liste de modules et les noms de tous les réglages qu'elle comprenait. L'unité ne peut pas le dire, car elle n'enregistre que les réglages auxquels une valeur a été attribuée, pas les réglages qui existaient.

Ce deuxième fichier permet de calculer « ce qui est nouveau dans cette version » : les réglages connus de la version actuelle moins ceux répertoriés dans l'empreinte. Chacun est proposé avec la valeur par défaut de `.env.example` ; appuyer sur Entrée l'accepte.

Une installation antérieure à cette empreinte ne dispose pas d'une telle liste. Plutôt que de présenter une supposition comme une différence, l'installateur indique qu'il ne peut pas la déterminer, conserve toutes les valeurs consignées par l'unité et oriente vers la procédure qui repose toutes les questions. La détection des modules se dégrade de la même manière : sans empreinte, elle déduit la liste des modules à partir des éléments présents sur disque — l'unité Web, l'unité anytls et la présence d'`iperf3`.

Le nœud anytls est préservé pendant une mise à niveau en relisant son port et son mot de passe dans `config.json` puis en les transmettant au script. Sinon, `setup-anytls.sh` attribuerait par défaut de nouvelles valeurs aléatoires aux deux et tous les clients configurés cesseraient de fonctionner lors d'une simple mise à niveau. Voir le piège ci-dessous, qui reste applicable lors d'une *réinstallation volontaire*.

### La section anytls de la console

**Elle se trouve désormais sur `/proxy`, et non sur une page propre** (2026-09-22) : voir « Le module proxy » ci-dessous pour les raisons de la fusion d'anytls et des protocoles du module proxy sur une seule page. `/anytls` existe toujours comme redirection vers `/proxy`, et `POST /anytls/reset` ne change pas ; seules la page autonome `GET /anytls`, son lien de navigation et sa tuile du tableau de bord ont disparu. La description ci-dessous reste valable pour la section anytls de cette page fusionnée.

La console lit le nœud installé dans `VPSSRV_ANYTLS_CONFIG` et affiche son état ainsi qu'une entrée Clash prête à coller et un lien `anytls://`.

Elle n'écrit qu'une seule chose : le bouton « réinitialiser le port et le mot de passe », et même cette opération est déléguée. La console ne modifie pas elle-même `config.json` : elle exécute `setup-anytls.sh reset`, car l'ordre des opérations est facile à inverser : la règle de pare-feu de l'ancien port doit être retirée *avant* l'ouverture du nouveau, sinon chaque réinitialisation laisse une règle `ACCEPT` sur un port où personne n'écoute. Cette logique appartient au script responsable du nœud, et non à deux endroits. La réinitialisation exige une case de confirmation validée côté serveur : l'attribut `required` dans le balisage prévient un clic involontaire, mais pas un client autre qu'un navigateur. La rotation des identifiants interrompt tous les clients configurés tant qu'ils n'ont pas reçu les nouveaux.

Elle s'exécute aussi **hors du bac à sable de ce service**, dans une unité temporaire via `systemd-run --pipe --wait --collect`. L'unité Web utilise `ProtectSystem=strict`, avec pour seul `ReadWritePaths=$PREFIX` ; `/etc` y est donc en lecture seule, alors qu'une réinitialisation doit écrire dans `/etc/vps-server-anytls` et dans un fichier d'unité. La première tentative réelle a échoué en cours de route pour cette raison précise, après avoir déjà retiré la règle de pare-feu de l'ancien port. Ajouter `/etc/systemd/system` à `ReadWritePaths` étendrait définitivement les droits d'écriture du service de longue durée pour faire fonctionner un seul bouton ; préserver le bac à sable est plus important. Sans `systemd-run`, l'appel est direct, ce qui convient puisque les environnements qui en sont dépourvus sont aussi ceux où `install.sh` omet le durcissement.

`setup-anytls.sh reset` vérifie également qu'il peut écrire avant de toucher au pare-feu. Une réinitialisation qui échoue après le retrait de l'ancienne règle laisse un nœud actif mais inaccessible, ce qui est pire qu'un nœud qui n'a jamais démarré.

Deux détails sont essentiels. **Le mot de passe du nœud apparaît en clair dans cette section de la console**, ce qui n'est acceptable que parce que la page relève de `ConsoleHandler`, derrière l'authentification ; `ProbeHandler` n'a pas de route vers elle et un test vérifie que l'écouteur public renvoie 404 pour `/anytls` et ne contient jamais ce mot de passe.
**L'adresse du serveur vient de l'en-tête `Host`
de la requête**, et non d'une recherche : l'adresse ayant permis d'atteindre la console permet aussi d'atteindre le nœud ; une recherche d'IP sortante au moment de l'affichage contredirait la règle interdisant les requêtes sortantes, et quiconque a besoin d'une autre adresse peut modifier la ligne après l'avoir copiée.

Le SNI n'est pas stocké dans la configuration sing-box : `setup-anytls.sh` ne l'inscrit que dans le CN du certificat autosigné. La console le relit donc dans le certificat plutôt que de conserver une deuxième copie susceptible de diverger.

### Le module proxy

L'ancienne liste des tâches demandait si le binaire sing-box déjà embarqué prenait en charge d'autres protocoles qu'anytls, ou s'il fallait un deuxième moteur. C'est bien le cas : `vmess`, `vless`, `trojan` et `shadowsocks` (2022-blake3-aes-128-gcm) passent chacun `sing-box check` et, confirmation obtenue en les exécutant réellement plutôt qu'en validant seulement leur configuration, tous quatre ouvrent leurs ports et acceptent des connexions simultanément dans un seul processus `sing-box run`. Aucun deuxième moteur n'a été ajouté.

Contrairement à anytls, il s'agit **d'une seule unité systemd (`vps-server-proxy.service`) avec plusieurs
entrées simultanées dans un seul `config.json`**, et non de quatre copies du modèle anytls. Raisons : une unité à surveiller au lieu de quatre, un certificat partagé à l'installation initiale et des certificats distincts pour les nouveaux nœuds TLS (shadowsocks n'en a pas besoin), et une structure adaptée à une future comptabilisation du trafic par nœud : un processus dont le tableau `inbounds` constitue déjà la liste des nœuds. `deploy/proxy/setup-proxy.sh` est propre à vps-server, et non importé d'un autre projet, puisque ces quatre protocoles ne proviennent pas d'Anytsl-Serve.

Il **partage le binaire sing-box embarqué avec le module anytls** (`/usr/local/bin/sing-box-vps-server`), au lieu d'emporter une seconde copie d'environ 57 Mo. La fonction `uninstall()` de chaque module vérifie que la configuration de *l'autre* module n'existe plus avant de supprimer ce binaire. Le script embarqué `setup-anytls.sh` du module anytls a reçu ce contrôle comme écart local documenté (voir `deploy/anytls/.upstream-version`), précisément parce que le binaire n'appartient plus au seul module anytls.

`PROXY_PROTOCOLS` (liste séparée par des virgules, les quatre par défaut) est validé dans un tableau global et non renvoyé par une substitution de commande `$(...)`. Une première version le validait dans une fonction appelée par `read -ra x <<< "$(fn)"` ; `exit 1` dans le sous-shell de cette substitution n'arrêtait que celui-ci : le script parent continuait silencieusement avec une liste vide et démarrait un service sans entrées. Même catégorie de bogue que celui de `prompt_new_settings()` dans les [Décisions][local-link-006]. Le port de chaque protocole provient d'une plage distincte de 5 000 ports sous 60 000 (et non d'une plage de 10 000 à partir de 60 000, qui débordait le `uint16 listen_port` de sing-box au-delà de 65535 si l'installation tirait un port élevé ; cela a été découvert lors de cinq installations neuves répétées, et non lors de la première). La préservation des identifiants à la mise à niveau fonctionne comme `preserve_anytls()` : `preserve_proxy()` relit dans `config.json` le port et l'identifiant de chaque protocole installé, ainsi que l'*ensemble* des protocoles, afin qu'une nouvelle exécution avec `VPSSRV_MODULES=proxy` n'en retire ni n'en ajoute silencieusement.

La page `/proxy` de la console affiche une section par nœud installé : port, UUID ou mot de passe, SNI relu depuis le certificat du nœud, ainsi qu’une entrée Clash et un lien de partage (`vmess://`, `vless://`, `trojan://`, `ss://`) pour chaque adresse détectée. **Chaque protocole possède son propre bouton de réinitialisation**, et non un bouton commun « tout réinitialiser » : un opérateur a signalé qu'un bouton global imposerait la rotation de protocoles que personne ne souhaitait modifier ; par exemple, la fuite d'un UUID vmess ne devrait pas nécessiter de reconfigurer aussi tous les clients trojan/vless/shadowsocks. `setup-proxy.sh reset <protocol>` ne change que le port et l'identifiant du protocole concerné ; `load_installed_vars()` relit d'abord sur disque les valeurs actuelles de *tous les autres* protocoles pour les conserver. `reset` sans argument fait toujours tourner les identifiants de tous les protocoles installés : cette option reste disponible en terminal et dans les scripts, mais pas dans l'interface de la console. Les deux formes suivent le même schéma `systemd-run` hors du bac à sable qu'`anytls_reset()`, pour la même raison liée à `ProtectSystem=strict`. Le partage du service systemd a un coût réel (voir plus haut) : réinitialiser un protocole redémarre tout le service ; les *connexions* des autres protocoles sont donc brièvement interrompues même si leurs identifiants restent inchangés.

L’installateur crée d’abord une entrée pour chaque protocole sélectionné. La console gérée peut ensuite créer plusieurs nœuds numérotés pour tout protocole installé, supprimer chaque nœud et conserver un module installé sans écouteur. Les ID des nœuds restent stables et masqués dans l’interface visible ; chaque formulaire et abonnement Clash cible l’ID, ce qui distingue les nœuds d’un même protocole. L’éditeur de connexion prend la place des informations de la carte ; le plafond de trafic, l’expiration et les cycles de réinitialisation utilisent un autre formulaire. La création ou la suppression d’un nœud met à jour la configuration sing-box, l’inventaire, le pare-feu et la comptabilité nft sous un même verrou, avec retour arrière en cas d’échec. Chaque nouveau nœud TLS reçoit son propre certificat autosigné. Les polices intégrées à la console utilisent `font-display: optional` pour éviter un changement tardif après le premier affichage.

`PortForwardManager.reserved_ports()` considère le port de chaque protocole proxy installé comme ceux du nœud anytls et de la console : il est réservé, si bien qu'une règle de transfert ne peut pas cibler un port déjà occupé par un protocole proxy.

**La page `/proxy` de la console affiche également le nœud anytls**, s'il est installé. Un opérateur a jugé artificiel de placer anytls sur une page distincte : de son point de vue, ce sont tous des « nœuds proxy », quel que soit le moteur indépendant qui sert chacun d'eux. `/anytls` redirige vers cette page ; `POST /anytls/reset` reste inchangé, hormis la redirection finale vers `/proxy`. Les deux modules conservent un état entièrement indépendant (`public-ip.txt` et `SERVER_IP` d'anytls ne sont pas ceux du module proxy ; chacun peut être configuré différemment) et leurs propres boutons de réinitialisation ; seule la page d'affichage est commune.

La page des nœuds affiche les adresses des interfaces de l’hôte et, si elle existe, l’adresse Tailscale. Elle n’affiche plus l’IP publique enregistrée à l’installation.

### Cycle de vie d'une fenêtre iperf3

1. L'opérateur s'authentifie dans la console, choisit une durée (10 minutes par défaut, plafonnée par `VPSSRV_IPERF_MAX_MINUTES`) et clique pour ouvrir la fenêtre.
2. La console lance `iperf3 -s -p <port>` comme processus enfant, ouvre le port dans le pare-feu actif et enregistre l'échéance en mémoire.
3. Tant que la fenêtre est ouverte, la **page publique** indique qu'iperf3 accepte les connexions, sur quel port et pour combien de temps encore. Le client distant qui réalise le test doit le savoir ; ce n'est pas sensible puisque la fenêtre est ouverte délibérément.
4. À l'échéance (ou à la demande de l'opérateur, ou à l'arrêt du service), le processus enfant est arrêté et la règle de pare-feu retirée.

La fenêtre est conservée en mémoire, pas sur disque : si le service s'arrête brutalement, la fenêtre disparaît, ce qui est le mode d'échec sûr. Un redémarrage ne rouvre jamais une fenêtre.

La latence est extraite de la sortie `--json` d'iperf3 (champ `mean_rtt` du bloc d'informations TCP) côté client de test ; aucun code supplémentaire n'est nécessaire côté serveur. Ce champ provient du `TCP_INFO` du noyau : il est donc présent sur un client Linux et absent sur un client qui ne peut pas le lire. Sous Cygwin sur Windows, iperf3 indique le débit, mais pas `mean_rtt`. Le mode UDP (`-u`) indique partout la gigue et les pertes : c'est la solution portable lorsque le client de test n'est pas sous Linux.

Le port choisi est enregistré séparément dans le répertoire de données de l’application. Il ne peut être changé depuis la console que lorsque la fenêtre est fermée ; avant l’enregistrement, les ports des services installés, des transferts et des processus à l’écoute sont vérifiés.

### Cycle de vie du transfert de ports

Un transfert relaie un port public TCP/UDP de cet hôte vers un appareil joignable via Tailscale ou le réseau local : un hôte disposant d'une IP publique peut ainsi servir de relais à un autre qui n'en a pas. Contrairement à la fenêtre iperf3, c'est une configuration et non un prêt temporaire de la liaison montante : elle doit subsister après le redémarrage du service ou de l'hôte et est donc réalisée différemment.

1. L'opérateur ajoute une règle depuis la console : protocole (tcp/udp/les deux), port public et cible `host:port`. `PortForwardManager.add()` refuse un port public déjà utilisé par cette installation (console, page publique, iperf3, nœud anytls ou autre transfert) avant toute modification d'iptables.
2. Chaque protocole de la règle devient quatre règles `iptables`, toutes marquées `-m comment --comment vps-server-portfwd-<id>` pour les distinguer des autres règles déjà présentes :
   - `nat`/`PREROUTING` : DNAT du port public vers `target_host:target_port`.
   - `nat`/`POSTROUTING` : MASQUERADE du trafic destiné à la cible, pour que les réponses repassent par cet hôte au lieu de suivre la passerelle par défaut de la cible ; celle-ci voit cet hôte comme client.
   - `filter`/`FORWARD` : une règle ACCEPT dans chaque sens, faute de quoi une politique `DROP` par défaut sur cette chaîne (courante, par exemple, sur un hôte Docker) éliminerait silencieusement le trafic transféré.
3. `net.ipv4.ip_forward` est activé la première fois qu'une règle en a besoin (`_ensure_ip_forward()`), puis n'est jamais désactivé : voir les [Décisions][local-link-007] (2026-09-19) pour la raison.
4. Les règles résident dans `PORTFWD_STATE_FILE` (JSON), pas seulement en mémoire. À chaque démarrage du processus, `PortForwardManager.load()` retire puis réajoute systématiquement les règles iptables de chaque transfert activé. Les tables du noyau ne survivent pas à un redémarrage de l'hôte et peuvent encore contenir celles de la précédente exécution lors d'un simple redémarrage du service ; cette même procédure doit fonctionner dans les deux cas.
5. Un arrêt normal (`SIGTERM`, géré par le même gestionnaire de signal que la fenêtre iperf3) appelle `PortForwardManager.shutdown()`, qui retire les règles iptables de tous les transferts activés sans changer le champ JSON `enabled` : un redémarrage du service ou de l'hôte **doit** les restaurer immédiatement via `load()`. C'est la même logique de sûreté que pour la fenêtre iperf3 : si le processus gestionnaire ne fonctionne plus, ses règles
   **ne doivent pas** lui survivre silencieusement.

`target_host` **doit** être une adresse IPv4 littérale, pas un nom d'hôte : `iptables --to-destination` attend une adresse et ce projet n'effectue aucune recherche DNS sortante lors d'une requête (voir la décision « Aucune dépendance tierce à l'exécution »). L'IP d'un appareil Tailscale est stable et visible dans `tailscale status` ou `tailscale ip` sur cet appareil.

## Contraintes de conception

- Ne pas ajouter de routes de console à `ProbeHandler` ; l'authentification ne remplace pas la table de routes publique distincte.
- Limiter la durée d'iperf3 et retirer la règle de pare-feu à la fermeture ou à l'arrêt.
- Réappliquer les transferts conservés dans le JSON au démarrage du processus ; retirer les règles actives lors d'un arrêt normal sans réinitialiser le réglage `ip_forward` valable pour tout l'hôte.
- Préserver les identifiants des nœuds et les réglages choisis lors des mises à niveau ; confier les rotations aux scripts responsables, hors du bac à sable du système de fichiers de l'unité Web.
- Ne pas dissocier le verrou `_db_lock` partagé sans preuve d'une latence préjudiciable : la mesure historique avec 60 générateurs de trafic n'a pas reproduit de ralentissement. Voir les [Bogues][local-link-008].

## Interfaces externes

- HTTP/HTTPS : les écouteurs publics sur 80/443 n'exposent que la page d'accessibilité ; la console de l'opérateur utilise un autre port, conservé sur disque. iperf3 n'écoute que dans une fenêtre de durée limitée ouverte après authentification.
- La console lit `/proc/net/tcp[6]` pour journaliser les connexions TCP entrantes ; aucune route publique ne divulgue les secrets des proxys.
- `install.sh` utilise le gestionnaire de paquets de la distribution et peut rechercher l'IP publique pendant l'installation ; le service lui-même n'effectue aucune requête sortante à l'exécution. `setup-anytls.sh` et `setup-proxy.sh` gèrent les unités sing-box et les certificats. iptables gère l'exposition temporaire d'iperf3 et les transferts activés ; systemd supervise les services et exécute les réinitialisations d'identifiants hors du bac à sable Web.

## Pile technique

| Couche | Choix | Version | Justification |
|---|---|---|---|
| Exécution | Python, bibliothèque standard uniquement | 3.9+ | Hérité de `vps-webserver` : aucun paquet Python tiers ; l'interpréteur et les bibliothèques gérés par la distribution nécessitent néanmoins des mises à jour de sécurité |
| Serveur HTTP | `http.server.ThreadingHTTPServer` | stdlib | Trois écouteurs avec peu de requêtes chacun ; un framework serait superflu |
| TLS | `ssl` + certificat autosigné généré par `openssl` | stdlib / distribution | Ni domaine ni ACME (voir les exclusions) |
| Stockage | `sqlite3` | stdlib | Le journal des visiteurs **doit** survivre aux redémarrages |
| Moteur de test de débit | LibreSpeed, embarqué sans modification | v6.2.1 | LGPL-3.0 ; déjà embarqué et fonctionnel dans `vps-webserver` |
| Génération des codes QR | kazuhikoarase/qrcode-generator, embarqué sans modification | js2.0.4 | MIT ; léger, sans étape de compilation, simple balise `<script>` comme LibreSpeed |
| Mesure de bande passante | `iperf3` fourni par la distribution | version non fixée par ce projet | Outil de référence dont disposent déjà les clients de test |
| Moteur proxy | sing-box, binaire embarqué (amd64) | v1.13.14 | GPL-3.0 ; le binaire livré permet une installation hors ligne |
| Initialisation | systemd | — | Système par défaut de l'OS cible |
| Installation | Bash | — | Hérité des deux projets d'origine |

Les solutions écartées et les raisons de chaque choix figurent dans les [Décisions][local-link-009] : ne pas les répéter ici.

## Conditions de reproduction

### Environnement

- OS : Debian 11+ / Ubuntu 20.04+, systemd, exécution en tant que root.
- Exécution : Python 3.9+ (le python3 de la distribution suffit).
- Architecture : **x86-64 uniquement** pour les modules anytls et proxy ; tous deux utilisent le même binaire sing-box amd64 embarqué. Les modules Web et iperf3 sont indépendants de l'architecture.
- Matériel : pas de GPU ; environ 150 Mo de disque (dont environ 57 Mo pour le binaire sing-box), la quantité de RAM habituelle d'un VPS suffit.
- Contrôle d'intégrité des artefacts embarqués : depuis la racine du dépôt, exécuter `python3 tools/verify_dependencies/verify_dependencies.py`. Cette commande compare par SHA-256 les cinq distributions tierces suivies avec [dependencies.lock.json][local-link-010], sans les exécuter. Les champs de version et de révision amont enregistrés proviennent des archives antérieures du projet, pas d'identités amont vérifiées indépendamment. La révision amont exacte de LibreSpeed n'est pas enregistrée.
- Il n'existe pas de verrou des paquets Python tiers car `app.py` utilise la bibliothèque standard. Ce verrou d'artefacts n'est ni une commande de restauration des dépendances ni un verrou complet des paquets système ; voir [THIRD_PARTY_NOTICES.md][local-link-011].

### Dépendances externes

| Élément | Source | Emplacement |
|---|---|---|
| `iperf3` | gestionnaire de paquets de la distribution (`apt-get install iperf3`) | chemin système |
| `openssl`, `curl`, `jq`, `iproute2`, `procps`, `iptables`, `ca-certificates` | gestionnaire de paquets de la distribution ou installation existante sur l'hôte | chemin système |
| Binaire sing-box | livré dans ce dépôt | `/usr/local/bin/sing-box-vps-server` |
| Moteur LibreSpeed et bibliothèque qrcode-generator | livrés dans ce dépôt | `$PREFIX/static/` |
| Certificats TLS | générés par l'installateur au premier lancement | `$VPSSRV_CERT_DIR` |

L'installateur installe les paquets système manquants (dont `iperf3`, facultatif) depuis les dépôts Debian/Ubuntu cibles, sans choisir de versions exactes ni d'instantanés de dépôt. Python, OpenSSL, les outils shell et système et systemd sont aussi fournis par l'OS cible. L'opérateur s'appuie sur les canaux de paquets maintenus pour la sécurité de la distribution choisie. Cela évite d'embarquer leurs binaires, mais les versions, empreintes et résolutions des dépendances transitives peuvent varier selon l'hôte et le moment ; **une restauration des dépendances
strictement reproductible n'est pas obtenue**. Il faudrait pour cela une modification de l'installateur approuvée séparément et un instantané choisi de la distribution et de ses dépôts. Le champ `exclusions` lisible par machine du verrou consigne cette limite, et non un verrouillage fictif.

Aucune clé API. Le service Web ne recherche pas l'IP publique par requête sortante à l'exécution. L'installateur peut effectuer une recherche sortante facultative ; son échec ne produit qu'un avertissement.

### Chemins et montages

| Chemin | Fourni par | Rôle |
|---|---|---|
| `$PREFIX` | installateur, valeur par défaut `/opt/vps-server` | Code, ressources statiques, fichiers de ports conservés |
| `$VPSSRV_DATA_DIR` | installateur, valeur par défaut `$PREFIX/data` | `visitors.db`, `session_secret.txt`, `portfwd.json` |
| `$VPSSRV_CERT_DIR` | installateur, valeur par défaut `$PREFIX/certs` | Certificat autosigné et clé pour 443 |
| `/etc/vps-server-anytls/` | installateur | `config.json` de sing-box et son propre certificat autosigné |
| `/etc/vps-server-proxy/` | installateur | `config.json` de sing-box (plusieurs entrées) et son certificat autosigné initial ; les certificats des nouveaux nœuds sont dans `/etc/vps-server-nodes/certs/` |

### Référence de configuration

Toutes les variables utilisent le préfixe `VPSSRV_`. Ce n'est pas une question d'esthétique : `vps-webserver` utilise `VPSWS_` et `Anytsl-Serve` utilise `ANYTLS_`. Les trois peuvent cohabiter sur le même hôte ; un préfixe commun permettrait au `.env` d'un projet de reconfigurer silencieusement un autre.

| Variable | Signification | Valeur par défaut | Obligatoire |
|---|---|---|---|
| `PREFIX` | Racine d'installation. Transmise à `install.sh`/`uninstall.sh`, **non** lue dans `.env` : ce chemin est nécessaire avant qu'une installation existe pour fournir ce `.env` | `/opt/vps-server` | non |
| `VPSSRV_DATA_DIR` | SQLite et secret de session | `$PREFIX/data` | non |
| `VPSSRV_HOST` | Adresse d'écoute de tous les écouteurs | `0.0.0.0` | non |
| `VPSSRV_PUBLIC_HTTP_PORT` | Page publique d'accessibilité, sans chiffrement | `80` | non |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Page publique d'accessibilité, TLS | `443` | non |
| `VPSSRV_PUBLIC_ENABLE` | Activer la page publique | `1` | non |
| `VPSSRV_CONSOLE_PORT` | Port de la console ; `0` = générer une fois et conserver | `0` | non |
| `VPSSRV_CONSOLE_PORT_FILE` | Fichier conservant le port généré de la console | `$PREFIX/console_port.txt` | non |
| `VPSSRV_CONSOLE_TLS` | Servir la console en HTTPS | `0` | non |
| `VPSSRV_AUTH` | Exiger l'authentification à la console | `1` | non |
| `VPSSRV_PASSWORD_FILE` | Mot de passe de la console en clair, modifiable par l'opérateur | `$PREFIX/admin_password.txt` | non |
| `VPSSRV_CERT_DIR` | Emplacement du certificat autosigné | `$PREFIX/certs` | non |
| `VPSSRV_TLS_CERT` / `VPSSRV_TLS_KEY` | Utiliser à la place un certificat fourni par l'opérateur | — | non |
| `VPSSRV_IPERF_PORT` | Port d'écoute de la fenêtre iperf3 | `5201` | non |
| `VPSSRV_IPERF_DEFAULT_MINUTES` | Durée préremplie de la fenêtre | `10` | non |
| `VPSSRV_IPERF_MAX_MINUTES` | Limite absolue que la console ne peut dépasser | `60` | non |
| `VPSSRV_IPERF_ENABLE` | Autoriser l'ouverture de fenêtres | `1` | non |
| `VPSSRV_PORTFWD_ENABLE` | Afficher la page de transfert de ports et autoriser de nouveaux transferts | `1` | non |
| `VPSSRV_PORTFWD_MAX_RULES` | Nombre maximal de transferts configurés | `20` | non |
| `VPSSRV_TRUST_PROXY` | Tenir compte de `X-Forwarded-For` lors de l'enregistrement des visiteurs | `0` | non |
| `VPSSRV_TRACK_CONNECTIONS` | Sonder `/proc/net/tcp[6]` pour journaliser les connexions sur tous les ports | `1` | non |
| `VPSSRV_CONN_POLL_SECONDS` | Intervalle de sondage | `5` | non |
| `VPSSRV_MAX_TEST_MB` | Taille maximale d'un transfert de test de débit, en Mo | `200` | non |
| `VPSSRV_TEST_SECONDS` | Fenêtre de mesure dans chaque sens | `10` | non |
| `VPSSRV_WARMUP_SECONDS` | Préchauffage ignoré au début de chaque sens | `2` | non |
| `VPSSRV_DOWNLOAD_STREAMS` / `VPSSRV_UPLOAD_STREAMS` | Flux parallèles dans chaque sens | `6` / `3` | non |
| `VPSSRV_PING_SAMPLES` | Allers-retours utilisés pour calculer la latence | `20` | non |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | non |
| `ANYTLS_PORT`, `ANYTLS_PASSWORD`, `SNI`, `SERVER_IP` | Le module anytls conserve les noms d'origine | voir `.env.example` | non |
| `VPSSRV_ANYTLS_CONFIG` | Fichier où la console lit le nœud installé | `/etc/vps-server-anytls/config.json` | non |
| `VPSSRV_ANYTLS_SERVICE` | Unité contrôlée par la console pour vérifier l'activité du nœud | `vps-server-anytls.service` | non |
| `VPSSRV_ANYTLS_SETUP` | Script exécuté par la console pour renouveler les identifiants du nœud | `$PREFIX/anytls/setup-anytls.sh` | non |
| `PROXY_PROTOCOLS`, `PROXY_SNI`, `SERVER_IP` | Paramètres du script du module proxy lui-même : module propre au projet, sans contrainte d'importation, mais noms sans préfixe pour conserver la distinction entre script et console d'anytls | voir `.env.example` | non |
| `VPSSRV_PROXY_CONFIG` | Fichier où la console lit les nœuds installés | `/etc/vps-server-proxy/config.json` | non |
| `VPSSRV_PROXY_SERVICE` | Unité contrôlée par la console pour vérifier l'activité des nœuds | `vps-server-proxy.service` | non |
| `VPSSRV_PROXY_SETUP` | Script exécuté par la console pour renouveler les identifiants du protocole choisi | `$PREFIX/proxy/setup-proxy.sh` | non |

Le module anytls conserve volontairement les noms de variables d'`Anytsl-Serve` plutôt que de les renommer `VPSSRV_ANYTLS_*` : le générateur de configuration embarqué les lit et les renommer imposerait de modifier du code importé, précisément ce que la politique d'importation cherche à éviter.

## Installation à partir de zéro

1. `git clone <repo>` puis entrer dans le répertoire avec `cd` ; vérifier : `ls -lh third_party/sing-box/sing-box` affiche un fichier d'environ 57 Mo.
2. `bash deploy/install.sh` ; une exécution interactive démarre un assistant temporaire dans le navigateur pour choisir les modules, la langue de l’interface, l’authentification de la console et les ports. Ouvrir l’URL affichée et saisir son jeton à usage unique ; après validation et application des choix, vérifier que le récapitulatif du terminal indique chaque module et son port.
3. `systemctl status vps-server-web` ; vérifier : `active (running)`.
4. Depuis une autre machine, ouvrir `http://<ip>/` ; vérifier : la page d'accessibilité s'affiche et indique votre propre IP source.
5. Depuis une autre machine, ouvrir `https://<ip>/` et accepter l'avertissement relatif au certificat ; vérifier : la même page s'affiche avec HTTPS dans la ligne du protocole.
6. Ouvrir `http://<ip>:<console port>/` et se connecter ; vérifier : le tableau de bord charge et affiche la commande iperf3, fenêtre fermée.
7. Ouvrir depuis la console une fenêtre iperf3 de cinq minutes, puis exécuter sur une autre machine `iperf3 -c <ip> -p 5201 --json` ; vérifier : le débit est indiqué et `mean_rtt` apparaît dans la sortie.
8. Si le module anytls a été installé : `systemctl status vps-server-anytls` ; vérifier : `active (running)` et la synthèse de l'installateur affichait une ligne de configuration client.

## Conception des données

La base des visiteurs et `portfwd.json` (règles de transfert activées) subsistent dans `$VPSSRV_DATA_DIR`. Le mot de passe de la console, le port choisi, les certificats Web et `.install-state` résident dans `$PREFIX` ; les configurations des modules sing-box et leurs certificats se trouvent dans `/etc/vps-server-anytls/` et `/etc/vps-server-proxy/`. Voir [Chemins et montages][local-link-012]. L'échéance iperf3 demeure en mémoire et ne survit pas à un redémarrage.

### Modèle de données et arborescence des fichiers

```
<project root>/
├── snapshots/                 # private snapshots; not part of the Git repository
└── repo/                      # Git working tree; paths below are relative to it
    ├── README.md              # entry point for users and documentation navigation
    ├── config/VERSION         # release version used in checkout
    ├── src/web/app.py         # web service implementation
    ├── deploy/
    │   ├── install.sh         # module-selecting installer
    │   ├── uninstall.sh       # module removal
    │   ├── systemd/vps-server-web.service
    │   ├── anytls/setup-anytls.sh
    │   ├── proxy/setup-proxy.sh
    │   ├── frps/setup-frps.sh
    │   └── lucky/setup-lucky.sh
    ├── static/                # first-party UI assets and vendored browser libraries
    │   └── third_party/
    │       ├── librespeed/    # speedtest.js, speedtest_worker.js
    │       └── qrcode/        # qrcode.js, qrcode-utf8.js
    ├── lang/                  # interface catalogs for web, installers, and tools
    ├── third_party/sing-box/
    │   ├── sing-box           # vendored amd64 binary
    │   ├── sing-box.version   # binary version metadata
    │   └── LICENSE            # original upstream notice
    ├── tools/verify_dependencies/verify_dependencies.py # checks config/dependencies.lock.json from repo root
    ├── config/dependencies.lock.json
    ├── config/upstream-version # records: vps-webserver v0.4.1
    ├── deploy/anytls/.upstream-version # records: Anytsl-Serve v1.2.0
    ├── tests/
    ├── LICENSE                # GPL-3.0
    └── doc/
        ├── DESIGN.md          # architecture, constraints, and tracked goals
        ├── LOG.md             # bugs, dated decisions, verification, release history
        ├── THIRD_PARTY_NOTICES.md
        └── <lang>/            # translated docs (seven language directories)
```

Ces chemins concernent uniquement le dépôt : l’installation conserve `$PREFIX/app.py`, `$PREFIX/sing-box` et `$PREFIX/static/`. Les URL HTTP des ressources restent inchangées. Dans le dépôt, l’installateur et le désinstallateur sont `deploy/install.sh` et `deploy/uninstall.sh` ; le point d’entrée Web installé reste `$PREFIX/app.py`.

Seul `repo/` est suivi par Git ; `snapshots/` est séparé et privé. Commencer par le [README][local-link-013], consulter le [LOG][local-link-014] pour les vérifications historiques et l'historique des versions, et les [avis relatifs aux tiers][local-link-015] pour les ressources amont. La documentation ne transforme ni un instantané ni un hôte où le projet est installé en copie reproductible du dépôt source.

Le schéma SQLite est repris sans modification de `vps-webserver` : une table `visits`, limitée aux 1 000 lignes les plus récentes. `portfwd.json` est une liste JSON plate d'objets de règles (`id`, `label`, `protocol`, `public_port`, `target_host`, `target_port`, `enabled`, `created`) ; voir `PortForwardManager` dans `src/web/app.py`.

## Limites connues et pièges

- **L'écoute sur 80 et 443 exige les droits root et des ports libres.** Si nginx, Apache, Caddy ou une autre instance de `vps-webserver` occupe l'un des deux, l'installateur refuse de continuer plutôt que de se disputer le port. Vérifier avant installation avec `ss -lntp '( sport = :80 or sport = :443 )'`.
- **La page publique est réellement publique.** Quiconque devine ou balaie l'IP la voit, et chaque accès est inscrit au journal des visiteurs. C'est voulu, mais une IP balayée voit aussi son journal se remplir en quelques heures du bruit de fond d'Internet.
- **Les noms d'unités diffèrent volontairement de ceux du projet d'origine.** `Anytsl-Serve` installe `sing-box-anytls.service` ; ce projet installe `vps-server-anytls.service` et un binaire nommé séparément, afin que les deux puissent coexister. L'installateur refuse néanmoins de poursuivre si l'unité d'origine tourne, car deux entrées anytls sur un seul hôte relèveraient presque certainement d'une erreur, pas d'une intention.
- **La version d'`iperf3` n'est pas fixée.** Le paquet vient de la distribution ; sa version varie selon la publication. Le protocole réseau est stable dans la série 3.x, mais un client bien plus ancien que le serveur peut échouer lors de la négociation de version.
- **amd64 uniquement pour anytls et proxy.** Le binaire embarqué n'est pas multiarchitecture ; sur arm64, l'installateur ignore le module en expliquant pourquoi au lieu d'installer un binaire impossible à exécuter.
- **TLS autosigné provoque chaque fois un avertissement du navigateur sur 443.** C'est prévu et ne justifie pas un « correctif » par exception ou en-tête HSTS.
- **Un redémarrage ferme toute fenêtre iperf3 ouverte.** C'est volontaire ; voir son cycle de vie.
- **L'arrêt du service retire tous les transferts
de ports, y compris les transferts activés.** C'est voulu et symétrique avec la fenêtre iperf3 ; voir le cycle de vie des transferts. `systemctl restart` ou un redémarrage de l'hôte les rétablit immédiatement, mais pas un `systemctl stop` suivi d'un arrêt prolongé.
- **`net.ipv4.ip_forward` est activé automatiquement et jamais désactivé.** Ce réglage concerne tout l'hôte ; d'autres logiciels (Docker, par exemple) peuvent déjà en dépendre. Supprimer le dernier transfert ne le modifie donc pas. Le désactiver manuellement si aucun autre logiciel de l'hôte n'en a besoin.
- **Un transfert ne couvre que ce que les règles `iptables` brutes voient.** Si `ufw` ou `firewalld` applique sa propre politique `FORWARD` de refus par défaut, ses chaînes sont évaluées avant la règle ajoutée par cette fonctionnalité ; il peut encore falloir y autoriser ce port pour que le trafic passe.
- **Le binaire sing-box dépasse la taille de fichier recommandée par GitHub.** Avec environ 55 Mo, il dépasse la limite indicative de 50 Mo : chaque push affiche un avertissement « Large files detected » suggérant Git LFS. Les pushs fonctionnent néanmoins ; la limite stricte est de 100 Mo. Une future mise à jour de sing-box pourrait la franchir : il faudra alors prendre une décision explicite (LFS ou arrêt de la livraison du binaire), plutôt que découvrir le problème le jour de la publication.
- **Exécuter les scripts avec `bash <script>`, et non `./<script>`.** Le bit exécutable figure dans l'index Git et une copie fraîche l'a donc, mais pas une copie de travail sur un montage CIFS/SMB ; `./install.sh` y échoue avec « Permission denied ».
- **Réimporter un exécutable fait perdre son bit exécutable.** La copie de travail du responsable est sur CIFS ; un fichier extrait là puis ajouté par `git add` est enregistré en `100644`, même s'il était en `100755` en amont. Cela s'est déjà produit pour le binaire `sing-box` et a rendu tout le module anytls inutilisable. Après réimportation, vérifier avec `git ls-files -s` et restaurer le bit avec `git update-index --chmod=+x <path>` : `chmod +x` seul est sans effet sur ce montage.
- **Exécuter directement `setup-anytls.sh` renouvelle son port et son mot de passe.** Par défaut, il attribue de nouvelles valeurs aléatoires à `ANYTLS_PORT` et `ANYTLS_PASSWORD` et réécrit `config.json` à chaque exécution : l'invoquer à la main invalide donc tous les clients configurés avec les anciennes valeurs. `install.sh` ne le fait plus : lors d'une mise à niveau, il relit les deux valeurs dans `config.json` et les transmet au script ; un appel direct continue néanmoins de les modifier. Pour conserver le nœud, transmettre les valeurs actuelles, affichées toutes deux dans la section anytls de `/proxy` de la console : `ANYTLS_PORT=<current> ANYTLS_PASSWORD='<current>' bash deploy/anytls/setup-anytls.sh`. Comportement amont conservé volontairement. `setup-anytls.sh reset` les renouvelle volontairement ; le bouton de réinitialisation de la console est le moyen pris en charge pour le demander.
- **La page des nœuds affiche les adresses des interfaces et de Tailscale.** L’ancien bloc d’adresse publique relevée à l’installation a été retiré : sur un VPS, il répétait l’adresse de l’interface et pouvait induire en erreur derrière un NAT. L’installation peut encore enregistrer `public-ip.txt` pour les scripts de configuration ; la console ne le lit pas.
- **Le `body` transmis à `render_page()`** **doit** contenir exactement un élément de premier niveau. `<main>` utilise `display: flex` sans surcharge de `flex-direction` : plusieurs éléments frères de premier niveau (par exemple un `<div class="card wide">` par protocole) s'alignent horizontalement au lieu de s'empiler. Ce bogue a réellement été livré dans une ancienne version de `/proxy` et signalé par un opérateur comme un problème de mise en page. Chaque page enveloppe donc tout dans une seule carte externe, avec les sections répétées imbriquées dans des div `.node-addr`.
- **La désinstallation nécessite les mêmes `PREFIX` et `SERVICE_NAME` qu'à l'installation.** Sans variables d'environnement, `uninstall.sh` utilise les valeurs par défaut, ne trouve rien à ces chemins et annonce avoir réussi sans rien supprimer. La dernière ligne de l'installateur affiche la commande exacte avec les valeurs renseignées : l'utiliser plutôt que de la retaper de mémoire.

## Extension

### Comment étendre le projet

- **Un nouveau module** (un élément que l'installateur peut configurer facultativement) : ajouter un script `deploy/<name>/setup-<name>.sh`, son unité systemd (livrée dans `deploy/systemd/` ou générée par le script), une branche au menu de modules d'`deploy/install.sh` et une branche de désinstallation dans `deploy/uninstall.sh`. Les modules ne s'appellent pas entre eux.
- **Une nouvelle page de console** : ajouter une route à `ConsoleHandler`. Ne pas ajouter de routes à `ProbeHandler` : sa table de routes presque vide est une propriété de sécurité, non un oubli.
- **Une nouvelle langue** : ajouter des catalogues correspondants dans chaque répertoire `lang/<component>/`, enregistrer le code dans le sélecteur de langue Web et la correspondance du journal des modifications, dans l’installateur, l’assistant de configuration et les chargeurs des scripts de modules, puis ajouter une arborescence documentaire correspondante `doc/<BCP47>/`.
- **Une nouvelle couleur** : ajouter un jeton dans `:root` de `static/style.css` *et* une valeur pour le mode clair dans le bloc `prefers-color-scheme: light`, puis utiliser ce jeton. Ne jamais écrire de valeur hexadécimale directement dans une règle de composant : une valeur littérale ne peut pas suivre le thème et devient correcte seulement dans le mode où elle a été jugée à l'œil, incorrecte dans l'autre, sans qu'aucun contrôle ne le signale. Toute couleur utilisée comme fond plein exige une couleur de premier plan `--on-*` associée : la valeur lisible comme texte convient rarement derrière un texte blanc. Vérifier les deux modes selon WCAG AA (4.5:1) avant de valider ; `tests/test_app.py::StylesheetTest` vérifie la partie structurelle, mais ne peut pas juger le rapport de contraste.
- **Actualiser une ressource amont embarquée** : recopier depuis le tag amont, mettre à jour le fichier `.upstream-version` correspondant dans le même commit et noter la mise à jour dans le [LOG.md][local-link-016]. Ne jamais modifier directement le code embarqué : une modification locale absente en amont produirait une régression silencieuse au prochain renouvellement.

[local-link-001]: LOG.md#limitations-et-état-actuel-de-validation
[local-link-002]: LOG.md#bogues
[local-link-003]: LOG.md#historique-des-travaux-terminés
[local-link-004]: LOG.md#décisions
[local-link-005]: #le-module-proxy
[local-link-006]: LOG.md#décisions
[local-link-007]: LOG.md#décisions
[local-link-008]: LOG.md#bogues
[local-link-009]: LOG.md#décisions
[local-link-010]: ../../config/dependencies.lock.json
[local-link-011]: THIRD_PARTY_NOTICES.md
[local-link-012]: #chemins-et-montages
[local-link-013]: ../../README.md
[local-link-014]: LOG.md
[local-link-015]: THIRD_PARTY_NOTICES.md
[local-link-016]: LOG.md#historique-des-modifications
