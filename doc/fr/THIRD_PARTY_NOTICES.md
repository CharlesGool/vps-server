---
name: project-third-party-notices-fr
description: Attributions et avis de conformité des tiers
metadata:
  version: "1.0.0"
  lang: "fr"
---

# Mentions relatives aux tiers

Ce document recense les composants tiers embarqués et fournis par le système d'exploitation, les affirmations relatives aux sources et les limites de vérification avant publication.

## Multilingue

[English](../THIRD_PARTY_NOTICES.md) | [简体中文](../zh-CN/THIRD_PARTY_NOTICES.md) | [繁體中文(台灣)](../zh-TW/THIRD_PARTY_NOTICES.md) | [繁體中文(香港)](../zh-HK/THIRD_PARTY_NOTICES.md) | [हिन्दी](../hi/THIRD_PARTY_NOTICES.md) | [Español](../es/THIRD_PARTY_NOTICES.md) | [العربية](../ar/THIRD_PARTY_NOTICES.md) | **Français**

## Documentation

- Présentation du projet : [README](README.md)

- Justification de la conception : [DESIGN](DESIGN.md)

- Historique des versions : [LOG](LOG.md)

- Avis relatifs aux tiers : [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## Avis relatifs aux tiers

Le tableau inventorie les composants embarqués et ceux fournis par le système d’exploitation. Les sept artefacts embarqués ont des empreintes SHA-256 du dépôt dans [dependencies.lock.json][local-link-001] ; exécutez `python3 tools/verify_dependencies/verify_dependencies.py` depuis la racine du dépôt pour les comparer hors ligne. Le 2026-09-27, les sept fichiers du dépôt correspondaient octet par octet aux membres des archives de publication ou aux fichiers des tags amont concernés. Les fichiers de licence inclus correspondaient également aux fichiers amont vérifiés ci-dessous. Ces contrôles établissent l’identité des artefacts, mais ne constituent ni un avis juridique ni un ensemble de dépendances système entièrement reproductible.

| Composant / ressource | Version / empreinte | Source | Licence consignée | Utilisation | Attribution / chemin de la licence originale | Obligations de publication à vérifier | Vérifié le |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0, selon la licence amont | Exécutable frps embarqué | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | Conserver la licence Apache-2.0 incluse ; aucune mention NOTICE ne figurait dans l’archive binaire officielle | 2026-09-27 : archive, binaire et licence vérifiés identiques |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT, selon la licence amont | Exécutable Lucky embarqué | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | Conserver les mentions de droit d’auteur et de licence MIT incluses | 2026-09-27 : archive, binaire et licence vérifiés identiques |
| sing-box | `v1.13.14` ; révision `25a600db24f7680ad9806ce5427bd0ab8afe1114` ; SHA-256 du binaire `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL version 3 ou ultérieure avec condition de dénomination de l'amont (selon la mention) | Exécutable embarqué partagé par anytls et proxy | [mention d'origine][local-link-002] ; [texte intégral GPL][local-link-003] | Conserver les liens vers les sources correspondantes et la condition amont relative au nom et à l’association | 2026-09-27 : archive, binaire, licence et révision du tag vérifiés identiques |
| LibreSpeed | `v6.2.1` | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0, selon la licence amont | Moteur de navigateur embarqué | [texte LGPL original][local-link-006] et [texte GPL][local-link-007] | Conserver le texte de la licence et rendre les sources amont accessibles | 2026-09-27 : deux fichiers du tag et licence vérifiés identiques |
| qrcode-generator | `js2.0.4` ; révision `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT, selon la licence amont | Bibliothèque QR côté client embarquée | [texte MIT original][local-link-008] | Conserver les mentions d’attribution et de licence requises | 2026-09-27 : deux fichiers du tag et licence vérifiés identiques |
| Inter | `5.3.0` | [Fontsource Inter](https://github.com/fontsource/fontsource/tree/main/packages/inter) | SIL OFL 1.1 | Police latine intégrée, graisses 400/600/700 | [license](../../static/licenses/OFL-Inter.txt) | Conserver la licence et la notice de droits incluses | 2026-09-27 |
| Noto Sans SC | `5.3.0` | [Fontsource Noto Sans SC](https://github.com/fontsource/fontsource/tree/main/packages/noto-sans-sc) | SIL OFL 1.1 | Police CJK intégrée, graisses 400/700 | [license](../../static/licenses/OFL-Noto-Sans-SC.txt) | Conserver la licence et la notice de droits incluses | 2026-09-27 |
| Lucide icons | `main` 2026-09-27 | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC | Icônes SVG intégrées pour l’interface | [license](../../static/licenses/Lucide-ISC.txt) | Conserver la licence et la notice de droits incluses | 2026-09-27 |
| iperf3 | Paquet de la distribution ; version non figée | [ESnet/iperf](https://github.com/esnet/iperf) | BSD-3-Clause, selon le relevé antérieur | Programme distinct installé par le système ; non redistribué ici | Non consigné ; licence originale fournie par le paquet système | Réévaluer en cas d'inclusion ou de redistribution ultérieure | Non consigné ; revérifier avant distribution |

Le relevé existant identifie la GPL-3.0 comme licence du projet ([LICENSE][local-link-009]) et invoque la redistribution de l'exécutable sing-box sous GPL pour la justifier ; les [Décisions][local-link-010] conservent le raisonnement et les autres possibilités rejetées. Le relevé antérieur décrit `vps-webserver` comme publié sous Apache-2.0 en amont et redistribué ici sous GPL-3.0. Cet inventaire consigne les fichiers et les conditions vérifiés pour v2.0.0 ; il ne constitue pas un avis juridique indépendant.

Il n'existe aucun paquet Python tiers. `src/web/app.py` utilise la bibliothèque standard : il n'y a donc pas de fichier de verrouillage des paquets Python. Le verrouillage des éléments embarqués ci-dessus ne fige ni Python, ni iperf3, ni les autres paquets système : leurs versions et mises à jour de sécurité sont gérées par les dépôts de la distribution Debian/Ubuntu visée. L'installateur ne choisit pas de versions exactes des paquets ni de copie figée d'un dépôt ; l'ensemble des dépendances système entièrement reproductible reste non résolu (voir [Exigences de reproduction][local-link-011]).

---

## sing-box

Ce dépôt redistribue un exécutable sing-box sous le nom `third_party/sing-box/sing-box` dans le dépôt. Le 2026-09-27, ses octets et la licence amont incluse correspondaient à l’archive officielle de la version v1.13.14. Il est installé sous `/usr/local/bin/sing-box-vps-server`.

- Composant : `sing-box`
- Projet amont : https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- Version : `v1.13.14`
- Révision source : `25a600db24f7680ad9806ce5427bd0ab8afe1114`
- Élément distribué : `sing-box-1.13.14-linux-amd64.tar.gz`
- SHA-256 du binaire du dépôt : `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- Licence : GNU GPL version 3 ou toute version ultérieure, plus la condition amont relative au nom/à l'association ; voir [`third_party/sing-box/LICENSE`][local-link-012]

Le SHA-256 de l’archive de publication téléchargée était `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697`. Le binaire et la licence du dépôt correspondaient octet par octet aux membres extraits de cette archive.

### Source correspondante

Le 2026-09-27, le tag v1.13.14 pointait vers la révision source `25a600db24f7680ad9806ce5427bd0ab8afe1114`. Les liens suivants vers les sources amont accompagnent l’exécutable embarqué :

- Arbre source étiqueté : https://github.com/SagerNet/sing-box/tree/v1.13.14
- Révision source exacte : https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- Archive source : https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

L'archive Release amont citée dans le relevé précédent est :

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

Ce projet est indépendant et n'est ni affilié aux auteurs de sing-box ou de SagerNet, ni approuvé par eux.

---

## LibreSpeed

Le test de débit dans le navigateur utilise un moteur client LibreSpeed embarqué. Le 2026-09-27, ses deux fichiers JavaScript embarqués et sa licence correspondaient octet par octet aux fichiers du tag amont v6.2.1.

- Composant : moteur client LibreSpeed — `static/third_party/librespeed/speedtest.js`, `static/third_party/librespeed/speedtest_worker.js`
- Projet amont : https://github.com/librespeed/speedtest
- Version : `v6.2.1`
- Licence : GNU LGPL version 3 ; texte intégral dans [`static/licenses/LGPL-3.0.txt`][local-link-013]
- Vérification : les deux fichiers et la licence originale correspondaient au tag v6.2.1 ; le commit exact du tag n’est pas consigné dans cet inventaire.

`static/speedtest-ui.js` est le code de liaison propre à ce projet et ne fait pas partie de LibreSpeed. Les points d'accès côté serveur dans `src/web/app.py` (`/speedtest/garbage`, `/speedtest/empty`, `/speedtest/getip`) réimplémentent le contrat client/serveur documenté de LibreSpeed ; il s'agit de code original et non de code dérivé du serveur PHP amont.

Le texte de la LGPL-3.0 est inclus et les sources amont sont liées ; cet inventaire ne constitue pas un avis juridique indépendant sur leur combinaison.

---

## qrcode-generator

La page `/proxy` de la console affiche les liens de partage sous forme de codes QR lisibles au moyen de cette bibliothèque côté client embarquée. Le 2026-09-27, ses deux fichiers JavaScript embarqués et la licence originale correspondaient octet par octet aux fichiers du tag amont js2.0.4.

- Composant : `static/third_party/qrcode/qrcode.js`, `static/third_party/qrcode/qrcode-utf8.js`
- Projet amont : https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- Version : `js2.0.4`
- Révision source : `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- Licence : MIT ; texte intégral dans [`static/licenses/MIT.txt`][local-link-014]
- Vérification : les deux fichiers correspondaient aux fichiers amont `js/dist/qrcode.js` et `js/dist/qrcode_UTF8.js` ; la licence MIT originale correspondait également.

`static/qrcode-render.js` est le code de liaison propre au projet (recherche les éléments `[data-qr-text]` et les remplit avec le SVG généré) ; il ne fait pas partie de la bibliothèque embarquée.

La mention de droit d’auteur et la licence MIT sont incluses avec la bibliothèque cliente.

---

## iperf3

- Composant : `iperf3`
- Projet amont : https://github.com/esnet/iperf
- Licence : BSD 3-Clause
- Modifié : non
- **Non redistribué.** `iperf3` est installé depuis le dépôt de paquets du système d'exploitation par `install.sh` et appelé comme programme distinct, à travers une frontière de processus. Aucun code ni binaire iperf3 n'est fourni dans ce dépôt ; selon le relevé antérieur, l'obligation d'attribution BSD liée à la redistribution n'est donc pas déclenchée ici. Réévaluer si les modalités de distribution changent. Ce composant figure dans la liste parce que le projet en dépend à l'exécution.

---

## Code intégré provenant des autres projets de cet auteur

Il ne s'agit pas de composants tiers ; ils sont néanmoins consignés ici parce que le code ne provient pas de ce dépôt et que sa provenance importe lors des mises à jour :

- `src/web/app.py`, `static/speedtest-ui.js`, `static/style.css`, `static/visitors.js`, `tests/`, `deploy/install.sh`, `deploy/uninstall.sh`, `deploy/systemd/` — provenant de `vps-webserver` v0.4.1 (Apache-2.0 en amont, replacé sous GPL-3.0 ici). Voir `config/upstream-version`.
- `deploy/anytls/setup-anytls.sh`, `third_party/sing-box/sing-box`, `third_party/sing-box/sing-box.version` — provenant de `Anytsl-Serve` v1.2.0 (GPL-3.0 en amont). Voir `deploy/anytls/.upstream-version`.

---

Aucune police, icône, image, jeu de données ou pondération de modèle tiers n'est inclus. À l'exécution, le service ne fait aucune requête sortante ; seul un accès facultatif à un service de recherche de l'IP publique pendant l'installation peut sortir, et son échec n'entraîne qu'un avertissement.

[local-link-001]: ../../config/dependencies.lock.json
[local-link-002]: ../../third_party/sing-box/LICENSE
[local-link-003]: ../../LICENSE
[local-link-004]: #source-correspondante
[local-link-005]: LOG.md#décisions
[local-link-006]: ../../static/licenses/LGPL-3.0.txt
[local-link-007]: ../../LICENSE
[local-link-008]: ../../static/licenses/MIT.txt
[local-link-009]: ../../LICENSE
[local-link-010]: LOG.md#décisions
[local-link-011]: DESIGN.md#conditions-de-reproduction
[local-link-012]: ../../third_party/sing-box/LICENSE
[local-link-013]: ../../static/licenses/LGPL-3.0.txt
[local-link-014]: ../../static/licenses/MIT.txt
