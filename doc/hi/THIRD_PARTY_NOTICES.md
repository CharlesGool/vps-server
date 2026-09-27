---
name: project-third-party-notices-hi
description: तृतीय-पक्ष श्रेय और अनुपालन सूचनाएँ
metadata:
  version: "1.0.0"
  lang: "hi"
---

# तृतीय-पक्ष सूचनाएँ

यह दस्तावेज़ साथ वितरित और OS से मिलने वाले तृतीय-पक्ष घटकों, स्रोत-संबंधी दावों और रिलीज़ समीक्षा की सीमाओं का अभिलेख है।

## बहुभाषी

[English](../THIRD_PARTY_NOTICES.md) | [简体中文](../zh-CN/THIRD_PARTY_NOTICES.md) | [繁體中文(台灣)](../zh-TW/THIRD_PARTY_NOTICES.md) | [繁體中文(香港)](../zh-HK/THIRD_PARTY_NOTICES.md) | **हिन्दी** | [Español](../es/THIRD_PARTY_NOTICES.md) | [العربية](../ar/THIRD_PARTY_NOTICES.md) | [Français](../fr/THIRD_PARTY_NOTICES.md)

## दस्तावेज़ीकरण

- परियोजना का परिचय: [README](README.md)

- डिज़ाइन का औचित्य: [DESIGN](DESIGN.md)

- रिलीज़ का इतिहास: [LOG](LOG.md)

- तृतीय-पक्ष सूचनाएँ: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## तृतीय-पक्ष सूचनाएँ

यह तालिका साथ वितरित और OS द्वारा प्रदान किए गए घटकों की सूची देती है। साथ वितरित सात आर्टिफ़ैक्ट के चेकआउट SHA-256 मान [dependencies.lock.json][local-link-001] में हैं; उनकी ऑफ़लाइन तुलना के लिए रिपॉज़िटरी रूट से `python3 tools/verify_dependencies/verify_dependencies.py` चलाएँ। 2026-09-27 को रिपॉज़िटरी की सातों फ़ाइलें अपने दर्ज अपस्ट्रीम रिलीज़ आर्काइव के सदस्यों या टैग फ़ाइलों से बाइट-दर-बाइट मेल खाती थीं। शामिल लाइसेंस फ़ाइलें भी नीचे जाँची गई अपस्ट्रीम फ़ाइलों से मेल खाती थीं। ये जाँच आर्टिफ़ैक्ट की पहचान स्थापित करती हैं, कानूनी राय या पूरी तरह पुनरुत्पादनीय सिस्टम निर्भरता-समूह नहीं।

| घटक / संसाधन | संस्करण / हैश | स्रोत | दर्ज लाइसेंस | उपयोग | श्रेय / मूल लाइसेंस पथ | समीक्षा योग्य रिलीज़ दायित्व | सत्यापन तारीख |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | अपस्ट्रीम लाइसेंस के अनुसार Apache-2.0 | साथ वितरित frps executable | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | शामिल Apache-2.0 लाइसेंस बनाए रखें; आधिकारिक बाइनरी आर्काइव में NOTICE फ़ाइल नहीं थी | 2026-09-27: आर्काइव, बाइनरी और लाइसेंस मेल खाते थे |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | अपस्ट्रीम लाइसेंस के अनुसार MIT | साथ वितरित Lucky executable | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | शामिल MIT कॉपीराइट और लाइसेंस सूचना रखें | 2026-09-27: आर्काइव, बाइनरी और लाइसेंस मेल खाते थे |
| sing-box | `v1.13.14`; संशोधन `25a600db24f7680ad9806ce5427bd0ab8afe1114`; बाइनरी SHA-256 `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL संस्करण 3 या बाद का, साथ में upstream की नाम-संबंधी शर्त (सूचना के अनुसार) | साथ वितरित निष्पादन फ़ाइल, anytls और proxy दोनों के लिए | [upstream सूचना][local-link-002]; [GPL का पूरा पाठ][local-link-003] | अनुरूप स्रोत लिंक और अपस्ट्रीम नाम/संबद्धता शर्त बनाए रखें | 2026-09-27: आर्काइव, बाइनरी, लाइसेंस और टैग संशोधन मेल खाते थे |
| LibreSpeed | `v6.2.1` | [LibreSpeed](https://github.com/librespeed/speedtest) | अपस्ट्रीम लाइसेंस के अनुसार LGPL-3.0 | साथ वितरित ब्राउज़र इंजन | [मूल LGPL पाठ][local-link-006] और [GPL पाठ][local-link-007] | लाइसेंस पाठ और अपस्ट्रीम स्रोत उपलब्ध रखें | 2026-09-27: दो टैग फ़ाइलें और लाइसेंस मेल खाते थे |
| qrcode-generator | `js2.0.4`; संशोधन `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | अपस्ट्रीम लाइसेंस के अनुसार MIT | साथ वितरित क्लाइंट-पक्ष QR लाइब्रेरी | [मूल MIT पाठ][local-link-008] | अनिवार्य कॉपीराइट और लाइसेंस सूचनाएँ बनाए रखें | 2026-09-27: दो टैग फ़ाइलें और लाइसेंस मेल खाते थे |
| Inter | `5.3.0` | [Fontsource Inter](https://github.com/fontsource/fontsource/tree/main/packages/inter) | SIL OFL 1.1 | साथ दिया गया लैटिन इंटरफ़ेस फ़ॉन्ट, 400/600/700 भार | [license](../../static/licenses/OFL-Inter.txt) | साथ दिए गए लाइसेंस और कॉपीराइट सूचना रखें | 2026-09-27 |
| Noto Sans SC | `5.3.0` | [Fontsource Noto Sans SC](https://github.com/fontsource/fontsource/tree/main/packages/noto-sans-sc) | SIL OFL 1.1 | साथ दिया गया CJK इंटरफ़ेस फ़ॉन्ट, 400/700 भार | [license](../../static/licenses/OFL-Noto-Sans-SC.txt) | साथ दिए गए लाइसेंस और कॉपीराइट सूचना रखें | 2026-09-27 |
| Lucide icons | `main` 2026-09-27 | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC | साथ दिए गए इंटरफ़ेस SVG आइकन | [license](../../static/licenses/Lucide-ISC.txt) | साथ दिए गए लाइसेंस और कॉपीराइट सूचना रखें | 2026-09-27 |
| iperf3 | वितरण का पैकेज; संस्करण तय नहीं | [ESnet/iperf](https://github.com/esnet/iperf) | पहले दर्ज BSD-3-Clause | OS से स्थापित अलग प्रोग्राम के रूप में चलाया जाता है; यहाँ पुनर्वितरित नहीं | कॉपीराइट दर्ज नहीं; OS पैकेज मूल लाइसेंस देता है | बाद में साथ वितरित या पुनर्वितरित करने पर दोबारा आकलन करें | दर्ज नहीं; वितरण से पहले फिर सत्यापित करें |

मौजूदा परियोजना अभिलेख इस परियोजना का लाइसेंस GPL-3.0 ([LICENSE][local-link-009]) बताता है और इसका कारण GPL लाइसेंस वाली sing-box निष्पादन फ़ाइल का पुनर्वितरण बताता है; [निर्णय][local-link-010] तर्क और अस्वीकृत विकल्प सुरक्षित रखते हैं। पिछला अभिलेख `vps-webserver` का upstream लाइसेंस Apache-2.0 और यहाँ उसका पुनर्वितरण GPL-3.0 के अंतर्गत बताता है। यह सूची v2.0.0 के लिए जाँची गई फ़ाइलों और शर्तों को दर्ज करती है; यह स्वतंत्र कानूनी राय नहीं है।

तृतीय-पक्ष Python पैकेज नहीं हैं। `src/web/app.py` मानक लाइब्रेरी इस्तेमाल करता है, इसलिए Python पैकेज लॉक नहीं है। ऊपर दिया साथ वितरित फ़ाइलों का लॉक OS द्वारा दिए Python, iperf3 या अन्य सिस्टम पैकेज को पिन नहीं करता: उनके संस्करण और सुरक्षा अपडेट लक्षित Debian/Ubuntu वितरण के पैकेज चैनल सँभालते हैं। इंस्टॉलर सटीक पैकेज संस्करण या रिपॉज़िटरी स्नैपशॉट नहीं चुनता; सिस्टम निर्भरताओं का पूरी तरह पुनरुत्पादनीय समाधान अब भी लंबित है ([पुनरुत्पादन आवश्यकताएँ][local-link-011] देखें)।

---

## sing-box

यह रिपॉज़िटरी sing-box निष्पादन फ़ाइल को `third_party/sing-box/sing-box` पथ पर पुनर्वितरित करती है। 2026-09-27 को इसकी बाइटें और शामिल अपस्ट्रीम लाइसेंस आधिकारिक v1.13.14 रिलीज़ आर्काइव से मेल खाते थे। इसे `/usr/local/bin/sing-box-vps-server` के रूप में स्थापित किया जाता है।

- घटक: `sing-box`
- upstream परियोजना: https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- संस्करण: `v1.13.14`
- स्रोत संशोधन: `25a600db24f7680ad9806ce5427bd0ab8afe1114`
- वितरित फ़ाइल: `sing-box-1.13.14-linux-amd64.tar.gz`
- रिपॉज़िटरी बाइनरी SHA-256: `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- लाइसेंस: GNU GPL संस्करण 3 या बाद का, साथ में upstream की नाम/संबद्धता शर्त; [`third_party/sing-box/LICENSE`][local-link-012] देखें

डाउनलोड किए गए रिलीज़ आर्काइव का SHA-256 `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697` था। रिपॉज़िटरी की बाइनरी और लाइसेंस उसके निकाले गए सदस्यों से बाइट-दर-बाइट मेल खाते थे।

### संबंधित स्रोत

2026-09-27 को v1.13.14 टैग का स्रोत संशोधन `25a600db24f7680ad9806ce5427bd0ab8afe1114` था। निम्न अपस्ट्रीम स्रोत लिंक साथ वितरित निष्पादन फ़ाइल के लिए दिए गए हैं:

- टैग किया स्रोत ट्री: https://github.com/SagerNet/sing-box/tree/v1.13.14
- सटीक स्रोत संशोधन: https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- स्रोत आर्काइव: https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

पिछले परियोजना अभिलेख में उल्लिखित upstream Release आर्काइव:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

यह परियोजना स्वतंत्र है और sing-box या SagerNet के लेखकों से संबद्ध या उनके द्वारा समर्थित नहीं है।

---

## LibreSpeed

ब्राउज़र गति परीक्षण साथ वितरित LibreSpeed क्लाइंट इंजन इस्तेमाल करता है। 2026-09-27 को इसकी दोनों साथ वितरित JavaScript फ़ाइलें और लाइसेंस अपस्ट्रीम v6.2.1 टैग की फ़ाइलों से बाइट-दर-बाइट मेल खाते थे।

- घटक: LibreSpeed क्लाइंट इंजन — `static/third_party/librespeed/speedtest.js`, `static/third_party/librespeed/speedtest_worker.js`
- upstream परियोजना: https://github.com/librespeed/speedtest
- संस्करण: `v6.2.1`
- लाइसेंस: GNU LGPL संस्करण 3; पूरा पाठ [`static/licenses/LGPL-3.0.txt`][local-link-013] में
- सत्यापन: दोनों फ़ाइलें और मूल लाइसेंस v6.2.1 टैग से मेल खाते थे; इस सूची में टैग का सटीक commit दर्ज नहीं है।

`static/speedtest-ui.js` इस परियोजना का अपना संयोजक कोड है, LibreSpeed का हिस्सा नहीं। `src/web/app.py` के सर्वर-पक्ष एंडपॉइंट (`/speedtest/garbage`, `/speedtest/empty`, `/speedtest/getip`) LibreSpeed के दस्तावेज़ित क्लाइंट/सर्वर अनुबंध को नए सिरे से लागू करते हैं; ये मूल कोड हैं, upstream PHP बैकएंड से व्युत्पन्न नहीं।

LGPL-3.0 पाठ साथ वितरित है और अपस्ट्रीम स्रोत का लिंक दिया गया है; यह सूची इस संयोजन पर स्वतंत्र कानूनी राय नहीं देती।

---

## qrcode-generator

कंसोल का `/proxy` पृष्ठ इस साथ वितरित क्लाइंट-पक्ष लाइब्रेरी से शेयर लिंक के स्कैन करने योग्य QR कोड बनाता है। 2026-09-27 को इसकी दोनों साथ वितरित JavaScript फ़ाइलें और मूल लाइसेंस अपस्ट्रीम js2.0.4 टैग की फ़ाइलों से बाइट-दर-बाइट मेल खाते थे।

- घटक: `static/third_party/qrcode/qrcode.js`, `static/third_party/qrcode/qrcode-utf8.js`
- upstream परियोजना: https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- संस्करण: `js2.0.4`
- स्रोत संशोधन: `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- लाइसेंस: MIT; पूरा पाठ [`static/licenses/MIT.txt`][local-link-014] में
- सत्यापन: दोनों फ़ाइलें अपस्ट्रीम की `js/dist/qrcode.js` और `js/dist/qrcode_UTF8.js` से मेल खाती थीं; मूल MIT लाइसेंस भी मेल खाता था।

`static/qrcode-render.js` इस परियोजना का अपना संयोजक कोड है (यह `[data-qr-text]` तत्व खोजकर उनमें रेंडर किया SVG डालता है), साथ वितरित लाइब्रेरी का हिस्सा नहीं।

MIT कॉपीराइट और लाइसेंस सूचना क्लाइंट लाइब्रेरी के साथ वितरित है।

---

## iperf3

- घटक: `iperf3`
- upstream परियोजना: https://github.com/esnet/iperf
- लाइसेंस: BSD 3-Clause
- संशोधित: नहीं
- **पुनर्वितरित नहीं।** `iperf3` को `install.sh` ऑपरेटिंग सिस्टम के पैकेज रिपॉज़िटरी से स्थापित करता है और इसे अलग प्रक्रिया के रूप में चलाया जाता है। इस रिपॉज़िटरी में iperf3 का कोड या बाइनरी नहीं आती, इसलिए पिछले अभिलेख के अनुसार पुनर्वितरण पर लागू BSD श्रेय आवश्यकता यहाँ उत्पन्न नहीं होती; वितरण का तरीका बदलने पर दोबारा मूल्यांकन करें। इसे सूचीबद्ध किया गया है क्योंकि रनटाइम पर परियोजना इस पर निर्भर है।

---

## इस लेखक की अपनी परियोजनाओं से लिया गया कोड

ये तृतीय-पक्ष नहीं हैं, फिर भी यहाँ दर्ज हैं क्योंकि कोड का उद्गम इस रिपॉज़िटरी में नहीं हुआ और अपडेट के लिए उसकी उत्पत्ति जानना आवश्यक है:

- `src/web/app.py`, `static/speedtest-ui.js`, `static/style.css`, `static/visitors.js`, `tests/`, `deploy/install.sh`, `deploy/uninstall.sh`, `deploy/systemd/` — `vps-webserver` v0.4.1 से (upstream Apache-2.0, यहाँ GPL-3.0 के अंतर्गत पुनर्लाइसेंस)। `config/upstream-version` देखें।
- `deploy/anytls/setup-anytls.sh`, `third_party/sing-box/sing-box`, `third_party/sing-box/sing-box.version` — `Anytsl-Serve` v1.2.0 से (upstream GPL-3.0)। `deploy/anytls/.upstream-version` देखें।

---

कोई तृतीय-पक्ष फ़ॉन्ट, आइकन, छवि, डेटासेट या मॉडल वज़न शामिल नहीं है। रनटाइम पर सेवा कोई बाहर जाने वाला अनुरोध नहीं करती; एकमात्र वैकल्पिक बाहरी कॉल स्थापना के दौरान सार्वजनिक-IP खोज है, जो विफल होने पर केवल चेतावनी देती है।

[local-link-001]: ../../config/dependencies.lock.json
[local-link-002]: ../../third_party/sing-box/LICENSE
[local-link-003]: ../../LICENSE
[local-link-004]: #संबंधित-स्रोत
[local-link-005]: LOG.md#निर्णय
[local-link-006]: ../../static/licenses/LGPL-3.0.txt
[local-link-007]: ../../LICENSE
[local-link-008]: ../../static/licenses/MIT.txt
[local-link-009]: ../../LICENSE
[local-link-010]: LOG.md#निर्णय
[local-link-011]: DESIGN.md#पुनर्निर्माण-की-आवश्यकताएँ
[local-link-012]: ../../third_party/sing-box/LICENSE
[local-link-013]: ../../static/licenses/LGPL-3.0.txt
[local-link-014]: ../../static/licenses/MIT.txt
