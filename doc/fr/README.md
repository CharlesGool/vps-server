---
name: project-readme-fr
description: Présentation et utilisation du projet
metadata:
  version: "1.0.0"
  lang: "fr"
---

# vps-server

## Multilingue

[简体中文](../../README.md) | [English](../en/README.md) | [繁體中文(台灣)](../zh-TW/README.md) | [繁體中文(香港)](../zh-HK/README.md) | [हिन्दी](../hi/README.md) | [Español](../es/README.md) | [العربية](../ar/README.md) | **Français**

## Documentation

- Présentation du projet : [README](README.md)

- Justification de la conception : [DESIGN](DESIGN.md)

- État du projet: [LOG](LOG.md)
- Archives historiques: [HISTORY](HISTORY.md)
- Historique des modifications: [CHANGELOG](CHANGELOG.md)
- Historique des commits: [COMMITS](COMMITS.md)

- Avis relatifs aux tiers : [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Introduction

Un ensemble de modules sélectionnables pour un VPS Debian/Ubuntu : page publique pour vérifier l’accès aux ports Web, console opérateur pour les tests de débit et le journal des connexions, fenêtre iperf3 à la demande et nœuds proxy sing-box. v5.0.0 comprend des nœuds gérés, des politiques de trafic, l’accès sans mot de passe depuis des IP privées, des commandes HTTP/HTTPS séparées, la gestion de FRPS et de FRPC local, l’installation de Lucky et un programme d’installation direct dans le terminal. La portée de la version et les vérifications figurent dans l’[historique des modifications][local-link-001].

## Fonctionnalités

- **Prouve l'accessibilité à tout le monde.** Une page volontairement minimale sur les ports **80** et
  **443**, sans connexion. Communiquez l'adresse IP : si la page s'affiche, vos ports web sont accessibles depuis l'endroit où se trouve la personne. Elle indique son adresse IP source, l'heure du serveur et le port et protocole d'arrivée, sans autre information sur l'hôte.
- **Mesure le débit depuis un navigateur.** La console, sur un port élevé aléatoire conservé entre les démarrages, effectue des tests montants et descendants avec LibreSpeed. Elle accepte le mot de passe administrateur ou une IP privée du réseau local explicitement autorisée. Le bouton d’accès par IP reste toujours visible ; une personne non autorisée est invitée à se connecter par mot de passe puis à ajouter une IP privée dans les réglages. Les paramètres de sécurité exigent une vérification récente du mot de passe administrateur avant d’afficher la liste des IP ou d’accepter une modification. Cette liste accepte des adresses IPv4 privées ou IPv6 locales uniques, individuellement, et l’accès par IP peut être désactivé sans supprimer les entrées. Changer le mot de passe invalide les sessions existantes. La page de réglages généraux permet de choisir directement l’apparence et la langue ; une fois la vérification du mot de passe administrateur expirée, les paramètres de sécurité demandent une nouvelle vérification.
- **Mesure le débit et la latence avec iperf3, à la demande.** La console ouvre une fenêtre de durée limitée ; `iperf3 -s` ne fonctionne que pendant cette fenêtre et s'arrête à son expiration. La personne qui teste obtient le débit avec iperf3 et, sur un client Linux, le temps aller-retour via `mean_rtt` dans la sortie `--json` : ce champ provient du `TCP_INFO` du noyau et manque sur les clients qui ne peuvent pas le lire, notamment iperf3 sous Cygwin sur Windows. Le mode UDP (`-u`) ajoute la gigue et la perte sur toutes les plateformes. La console affiche séparément l’état et le port ; ce dernier peut être changé lorsque la fenêtre est fermée et reste enregistré après un redémarrage du service.
- **Journalise les connexions.** Toutes les connexions TCP entrantes, quel que soit le port et pas seulement HTTP, sont lues depuis `/proc/net/tcp[6]`, stockées dans SQLite ; les 1 000 plus récentes sont conservées.
- **Fournit un proxy anytls.** sing-box utilise un certificat autosigné et BBR. La page authentifiée `/proxy` affiche l’état du nœud, son trafic et ses paramètres de connexion modifiables ; lorsqu’une adresse LAN privée est disponible, elle propose aussi un lien d’importation directe dans Clash Meta for Android et un code QR. L’URL d’abonnement peut aussi être copiée.
- **Fournit des proxies vmess/vless/trojan/shadowsocks dans toute combinaison.** Un autre processus sing-box partage le binaire embarqué avec anytls. Chaque protocole installé commence avec un nœud numéroté ; la console permet d’en créer davantage pour tout protocole installé et de supprimer chaque nœud séparément. Chaque nœud possède un plafond de trafic en GiB, des éditeurs distincts pour la connexion et les limites, une réinitialisation aléatoire et la même option d’importation dans Clash Meta accessible uniquement sur le LAN. L’URL d’importation contient un jeton opaque et devient invalide lorsque le nom ou les paramètres de connexion du nœud changent. Les ports publics ne servent pas les configurations proxy. À la création d’un nœud, on peut saisir un mot de passe ou une clé/UUID propre au protocole ou laisser le champ vide pour en générer un aléatoirement ; le SNI TLS par défaut est `www.bing.com`. La page affiche les adresses des interfaces et de Tailscale. Chaque nœud accepte des limites de débit indépendantes en montée et en descente, en Mbps. Lorsque le plafond de trafic en GiB est atteint, on peut limiter les deux sens à 1 Mbps ou bloquer l’usage. Le trafic de la période est remis à zéro tous les nombres de jours, mois ou années choisis. Une durée de validité facultative bloque l’usage à son terme. Le lien d’abonnement LAN peut aussi être copié.

La page FRPS accessible après connexion affiche l’état du service serveur local, les adresses de ses interfaces et ses paramètres de connexion. Le port et le jeton restent masqués jusqu’à ce que l’opérateur demande à les afficher. Il peut modifier le port et le jeton sur place et activer ou arrêter le service. La page FRPC distincte présente les instances clientes locales sous forme de cartes, avec une adresse IP masquée et un indicateur de connexion fondé sur une socket TCP établie. Le bouton Tester la connexion effectue une connexion FRPC indépendante avec le serveur, le port et le jeton enregistrés. La page d’une instance affiche, avant modification, le type de chaque proxy TCP/UDP, son IP locale, son port local et son port distant ; l’IP et le jeton du serveur ne sont révélés qu’à la demande. Après un enregistrement, l’opérateur reste sur cette page. Le fichier est vérifié et la configuration précédente est rétablie en cas d’échec. Ces opérations FRP requièrent une session connectée ; la vérification récente du mot de passe administrateur reste réservée aux opérations des paramètres de sécurité, notamment le changement de mot de passe et la gestion de l’accès par IP sans mot de passe. L’éditeur de champs accepte uniquement les configurations TCP/UDP simples authentifiées par jeton qu’il sait représenter et ne modifie pas les autres fichiers TOML de FRPC. La console ne prétend pas afficher l’état en direct des instances FRPC installées sur d’autres appareils. La page Modules vérifie séparément le binaire FRPC local et le modèle `frpc@.service`, indépendamment de la présence de configurations d’instances. Elle propose Installer s’il manque l’un des deux. L’installation utilise le binaire FRPC v0.71.0 dont l’empreinte est vérifiée et ne crée ni connexion ni port d’écoute. Le journal du module consigne le téléchargement et sa vérification. Pour une installation hors ligne, télécharger [frpc-0.71.0-linux-amd64](https://github.com/CharlesGool/vps-server/releases/download/v4.0.0/frpc-0.71.0-linux-amd64) (16 593 080 octets ; SHA-256 `f79fff8de3089ec711ff8bdd4b73e00dfe491a1c3d754983c8b0f8d58c21b068`) et le placer dans `~/apps/vps-server/vendor/frp/frpc` avant de choisir Installer. La même empreinte est vérifiée pour un fichier téléchargé ou placé manuellement. La désinstallation arrête les instances FRPC locales, archive leurs configurations sous `data/` et conserve les fichiers de configuration pour une réinstallation ultérieure.

La première installation n’installe que Web. `VPSSRV_MODULES` permet de choisir d’autres modules serveur parmi web, iperf3, anytls, proxy, frps et lucky ; FRPC est une fonction cliente locale distincte.

**Hors périmètre :** ni ACME ni noms de domaine (le certificat sur 443 est volontairement autosigné) ; pas d'iperf3 permanent ; pas de proxy inverse ni de conteneurs ; la page publique ne révèle jamais le nom de l'hôte, le noyau, la durée de fonctionnement, la liste des services ou les paramètres des proxys. Ce projet ne remplace pas `vps-webserver` ou `Anytsl-Serve` : tous deux restent maintenus indépendamment et leur code est embarqué ici plutôt qu'absorbé.

## Prérequis

- Système : Debian 11+ ou Ubuntu 20.04+, systemd, exécution en tant que root.
- Environnement : Python 3.9+ (le `python3` de la distribution suffit ; aucune dépendance Python à installer).
- Architecture : toute architecture pour web et iperf3 ; **x86-64 uniquement** pour anytls, proxy, frps et Lucky, car les exécutables embarqués ciblent amd64.
- Pour le module web sur ses ports publics par défaut, les ports 80 et 443 **doivent** être libres : l'installateur refuse de concurrencer nginx, Apache, Caddy ou `vps-webserver`.
- Services externes : aucun à l’exécution. L’installation nécessite le miroir de paquets de la distribution ; les récapitulatifs des nœuds utilisent les adresses des interfaces et, si disponible, de Tailscale, sans recherche externe de l’IP publique.
- Minimum : système, environnement, architecture et ports libres indiqués ci-dessus. Aucun matériel recommandé supplémentaire n'est consigné ; un VPS avec environ 150 Mo de disque peut accueillir le binaire embarqué.

## Installation

### Installation rapide

Exécutez en tant que root ; par défaut, seule la console Web est installée et le terminal affiche un port administratif et un mot de passe aléatoires.

```bash
git clone --branch v5.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

### Installation standard

```bash
git clone --branch v5.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env  # facultatif : adaptez les valeurs selon les commentaires
bash deploy/install.sh
```

`PREFIX` vaut `/root/apps/vps-server` par défaut. La première installation s’effectue dans le terminal sans assistant dans le navigateur. Utilisez `VPSSRV_MODULES=web,iperf3,anytls,proxy,frps,lucky` pour choisir les modules serveur ; sans cette variable, seul Web est installé. Installez ou retirez les fonctions facultatives depuis Settings → Modules. Les pages publiques HTTP et HTTPS s’activent séparément depuis Home ; la console administrative utilise un autre port. Installez FRPC séparément lorsqu’un client local est nécessaire ; le fichier à télécharger et son chemin hors ligne sont indiqués plus haut.

## Conseils

### Quick start

Le code Web se trouve dans `src/web/`, les ressources statiques dans `src/web/static/` et l’installateur dans `deploy/`. Les exécutables et licences fournis se trouvent dans `third_party/` ; les métadonnées de version dans `config/`. L’installation conserve son ancien agencement plat ; la réorganisation des sources ne déplace pas les données d’exécution.

```bash
bash deploy/install.sh                       # première installation de la console Web dans le terminal
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # installation sans intervention ni questions
systemctl status vps-server-web              # vérifie si le service est actif
bash deploy/anytls/setup-anytls.sh status           # détails du nœud anytls si ce module est installé
bash deploy/proxy/setup-proxy.sh status             # détails du nœud proxy si ce module est installé
```

Ensuite, depuis une autre machine :

```bash
curl -sS  http://<ip>/                     # vérifie l’accessibilité par HTTP non chiffré
curl -sSk https://<ip>/                    # ... puis par TLS (certificat autosigné)
iperf3 -c <ip> -p 5201 --json              # uniquement tant qu’une fenêtre est ouverte
```

### Verify it works

Après `bash deploy/install.sh`, un récapitulatif doit nommer chaque module installé et son port. Ensuite :

- `systemctl status vps-server-web` indique `active (running)`.
- Depuis **une autre machine**, `http://<ip>/` affiche une page intitulée « Reachable » et votre propre IP publique. `https://<ip>/` affiche la même page après acceptation de l'avertissement de certificat, avec HTTPS à la ligne du protocole.
- Une connexion à `http://<ip>:<console port>/` affiche le tableau de bord, sa commande iperf3 et une fenêtre fermée.
- Après ouverture d'une fenêtre de 5 minutes, `iperf3 -c <ip> -p 5201 --json` exécuté depuis une autre machine indique un débit et contient `mean_rtt`. Cinq minutes après, la même commande ne peut plus se connecter : la fenêtre s'est refermée normalement, ce n'est pas une panne.
- Avec anytls : `systemctl status vps-server-anytls` indique `active (running)`.
- Avec proxy : `systemctl status vps-server-proxy` indique `active (running)`.

### Configuration

Chaque variable a une valeur par défaut fonctionnelle ; `.env` est facultatif. Les plus importantes :

| Variable | Signification | Défaut | Obligatoire |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | Page publique d'accessibilité, en clair | `80` | non |
| `VPSSRV_PUBLIC_HTTPS_PORT` | Page publique d'accessibilité, TLS | `443` | non |
| `VPSSRV_PUBLIC_ENABLE` | Activer la page publique | `0` | non |
| `VPSSRV_CONSOLE_PORT` | Port de la console ; `0` en génère un et le conserve | `0` | non |
| `VPSSRV_AUTH` | Exiger un mot de passe sur la console | `1` | non |
| `VPSSRV_IPERF_PORT` | Port d'écoute de la fenêtre iperf3 ouverte | `5201` | non |
| `VPSSRV_IPERF_MAX_MINUTES` | Durée maximale autorisée par la console | `60` | non |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | non |

Référence complète : [référence de configuration][local-link-002].

## Mise à niveau

Pour mettre à niveau, utilisez une copie de travail récente et relancez l’installateur avec le même répertoire d’installation et les mêmes modules. Conservez une sauvegarde des données persistantes jusqu’à la vérification des services et de la console mis à niveau.

## Désinstallation

Exécutez en tant que root depuis le dépôt de l'installateur, avec les valeurs `PREFIX` et `SERVICE_NAME` utilisées lors de l'installation (le récapitulatif de l'installateur affiche la commande exacte de désinstallation). Pour retirer les modules et unités installés **en conservant
les données** dans `$PREFIX` en vue d'une réinstallation :

```bash
KEEP_DATA=1 bash deploy/uninstall.sh
```

Pour retirer les modules installés **et supprimer aussi les données** (dont le journal des visiteurs, le mot de passe de la console, le port enregistré et les certificats dans `$PREFIX`) :

```bash
bash deploy/uninstall.sh
```

Dans les deux cas, les services anytls/proxy et leurs configurations de module distinctes sont supprimés s'ils existent. `KEEP_DATA=1` conserve `$PREFIX`, mais pas ces configurations de module.

## Remerciements

Le test de débit dans le navigateur utilise [LibreSpeed](https://github.com/librespeed/speedtest) ; le rendu des codes QR utilise
[qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) ; le moteur proxy intégré est
[sing-box](https://github.com/SagerNet/sing-box). Les modules expérimentaux embarquent
[frp](https://github.com/fatedier/frp) et
[Lucky](https://github.com/gdy666/lucky). Voir les [mentions relatives aux tiers][local-link-003] pour l’inventaire et les chemins des licences originales.

## Licence

Licence du projet : GPL-3.0 (SPDX : `GPL-3.0-only`) ; lire le texte intégral dans [LICENSE][local-link-004]. La justification historique de cette combinaison se trouve dans les [Décisions][local-link-005]. Les composants embarqués, leurs licences originales, les sources vérifiées des artefacts et les limites restantes de l’examen juridique figurent dans [THIRD_PARTY_NOTICES.md][local-link-006].

Ce projet n'est ni affilié à sing-box/SagerNet ou LibreSpeed, ni approuvé par eux.

[local-link-001]: CHANGELOG.md
[local-link-002]: DESIGN.md#référence-de-configuration
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#décisions
[local-link-006]: THIRD_PARTY_NOTICES.md
