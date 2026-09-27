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

Le tableau inventorie les composants et affirmations relatives aux sources déjà documentés ici. Les sept éléments tiers distribués avec le projet ont des empreintes SHA-256 calculées localement dans [dependencies.lock.json][local-link-001] ; exécutez `python3 tools/verify_dependencies/verify_dependencies.py` depuis la racine du dépôt pour comparer hors ligne les octets du dépôt. Cette vérification n'établit ni l'identité des éléments d'origine, ni les termes des licences originales, ni la conformité de la publication. Aucune date de nouvelle vérification des licences d'origine ou de la distribution n'est revendiquée. Avant toute distribution, vérifiez les versions consignées, les textes originaux des licences, les droits d'auteur, les obligations applicables de fourniture des sources et toute analyse de séparation au regard des éléments effectivement distribués. Ce tableau ne vaut pas autorisation de publication.

| Composant / ressource | Version / empreinte | Source | Licence consignée | Utilisation | Attribution / chemin de la licence originale | Obligations de publication à vérifier | Vérifié le |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0, per bundled license | Exécutable frps embarqué | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | Conserver la licence Apache-2.0 incluse et vérifier les obligations NOTICE avant distribution | Repository artifact hash verified; upstream identity pending |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT, per bundled license | Exécutable Lucky embarqué | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | Conserver les mentions de droit d’auteur et de licence MIT incluses | Repository artifact hash verified; upstream identity pending |
| sing-box | `v1.13.14` ; révision `25a600db24f7680ad9806ce5427bd0ab8afe1114` ; SHA-256 du binaire `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL version 3 ou ultérieure avec condition de dénomination de l'amont (selon la mention) | Exécutable embarqué partagé par anytls et proxy | [mention d'origine][local-link-002] ; [texte intégral GPL][local-link-003] | Source correspondante et condition de dénomination ; vérifier les [liens de sources consignés][local-link-004] et les [Décisions][local-link-005] | Non consigné ; revérifier avant distribution |
| LibreSpeed | `v6.2.1`, selon le relevé antérieur | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0, selon le relevé antérieur | Moteur de navigateur embarqué | non consigné ici ; [texte LGPL original][local-link-006] et [texte GPL][local-link-007] | Vérifier la combinaison avec la bibliothèque et la disponibilité des sources | Non consigné ; revérifier avant distribution |
| qrcode-generator | `js2.0.4` ; révision `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT, selon le relevé antérieur | Bibliothèque QR côté client embarquée | [texte MIT original][local-link-008] | Conserver les mentions d’attribution et de licence requises | Non consigné ; revérifier avant distribution |
| iperf3 | Paquet de la distribution ; version non figée | [ESnet/iperf](https://github.com/esnet/iperf) | BSD-3-Clause, selon le relevé antérieur | Programme distinct installé par le système ; non redistribué ici | Non consigné ; licence originale fournie par le paquet système | Réévaluer en cas d'inclusion ou de redistribution ultérieure | Non consigné ; revérifier avant distribution |

Le relevé existant identifie la GPL-3.0 comme licence du projet ([LICENSE][local-link-009]) et invoque la redistribution de l'exécutable sing-box sous GPL pour la justifier ; les [Décisions][local-link-010] conservent le raisonnement et les autres possibilités rejetées. Le relevé antérieur décrit `vps-webserver` comme publié sous Apache-2.0 en amont et redistribué ici sous GPL-3.0. Ce sont des affirmations historiques du projet, et non une nouvelle conclusion juridique ; vérifier les obligations et la compatibilité avant publication.

Il n'existe aucun paquet Python tiers. `src/web/app.py` utilise la bibliothèque standard : il n'y a donc pas de fichier de verrouillage des paquets Python. Le verrouillage des éléments embarqués ci-dessus ne fige ni Python, ni iperf3, ni les autres paquets système : leurs versions et mises à jour de sécurité sont gérées par les dépôts de la distribution Debian/Ubuntu visée. L'installateur ne choisit pas de versions exactes des paquets ni de copie figée d'un dépôt ; l'ensemble des dépendances système entièrement reproductible reste non résolu (voir [Exigences de reproduction][local-link-011]).

---

## sing-box

Ce dépôt redistribue un exécutable sing-box sous le nom `third_party/sing-box/sing-box` dans le dépôt. Son identité de version amont était affirmée dans le relevé précédent, mais n'a pas fait l'objet d'une vérification indépendante lors de cet audit local des empreintes. Il est installé sous `/usr/local/bin/sing-box-vps-server`.

- Composant : `sing-box`
- Projet amont : https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- Version : `v1.13.14`
- Révision source : `25a600db24f7680ad9806ce5427bd0ab8afe1114`
- Élément distribué : `sing-box-1.13.14-linux-amd64.tar.gz`
- SHA-256 du binaire du dépôt : `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- Licence : GNU GPL version 3 ou toute version ultérieure, plus la condition amont relative au nom/à l'association ; voir [`third_party/sing-box/LICENSE`][local-link-012]

Le relevé précédent mentionne une comparaison octet par octet avec l'archive Release d'origine. Cet audit n'a vérifié que le SHA-256 du binaire du dépôt ; l'équivalence avec la version publiée exige encore une comparaison indépendante avec l'amont.

### Source correspondante

Le relevé antérieur identifie les liens suivants vers les sources correspondantes de la version revendiquée ; cet audit n'a pas comparé leur contenu au binaire du dépôt. Confirmer la correspondance et les obligations de fourniture des sources avant redistribution :

- Arbre source étiqueté : https://github.com/SagerNet/sing-box/tree/v1.13.14
- Révision source exacte : https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- Archive source : https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

L'archive Release amont citée dans le relevé précédent est :

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

Ce projet est indépendant et n'est ni affilié aux auteurs de sing-box ou de SagerNet, ni approuvé par eux.

---

## LibreSpeed

Le test de débit dans le navigateur utilise un moteur client LibreSpeed embarqué. La version et l'équivalence avec l'amont consignées n'ont pas été vérifiées indépendamment lors de cet audit.

- Composant : moteur client LibreSpeed — `static/third_party/librespeed/speedtest.js`, `static/third_party/librespeed/speedtest_worker.js`
- Projet amont : https://github.com/librespeed/speedtest
- Version : `v6.2.1`
- Licence : GNU LGPL version 3 ; texte intégral dans [`static/licenses/LGPL-3.0.txt`][local-link-013]
- Relevé antérieur : les deux fichiers étaient décrits comme identiques octet par octet à la version publiée en amont ; seules les empreintes locales du dépôt ont été vérifiées lors de cet audit. La révision source amont exacte n'est pas consignée.

`static/speedtest-ui.js` est le code de liaison propre à ce projet et ne fait pas partie de LibreSpeed. Les points d'accès côté serveur dans `src/web/app.py` (`/speedtest/garbage`, `/speedtest/empty`, `/speedtest/getip`) réimplémentent le contrat client/serveur documenté de LibreSpeed ; il s'agit de code original et non de code dérivé du serveur PHP amont.

Le relevé précédent évaluait la combinaison de la LGPL-3.0 avec cette œuvre GPL-3.0 ; confirmer les obligations de publication avant distribution.

---

## qrcode-generator

La page `/proxy` de la console affiche sous forme de code QR le lien de partage de chaque adresse anytls au moyen de cette bibliothèque côté client embarquée. La version et l'équivalence avec l'amont consignées n'ont pas été vérifiées indépendamment lors de cet audit.

- Composant : `static/third_party/qrcode/qrcode.js`, `static/third_party/qrcode/qrcode-utf8.js`
- Projet amont : https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- Version : `js2.0.4`
- Révision source : `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- Licence : MIT ; texte intégral dans [`static/licenses/MIT.txt`][local-link-014]
- Relevé antérieur : les deux fichiers étaient décrits comme identiques octet par octet aux fichiers amont `js/dist/qrcode.js` et `js/dist/qrcode_UTF8.js` ; seules les empreintes locales du dépôt ont été vérifiées lors de cet audit.

`static/qrcode-render.js` est le code de liaison propre au projet (recherche les éléments `[data-qr-text]` et les remplit avec le SVG généré) ; il ne fait pas partie de la bibliothèque embarquée.

Le relevé précédent évaluait la combinaison de MIT avec cette œuvre GPL-3.0 ; confirmer les obligations de conservation des mentions avant distribution.

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
