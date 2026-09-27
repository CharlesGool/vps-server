---
name: project-third-party-notices-ar
description: نسب الحقوق وإشعارات الامتثال للجهات الخارجية
metadata:
  version: "1.0.0"
  lang: "ar"
---

# إشعارات الأطراف الثالثة

تسجّل هذه الوثيقة مكوّنات الأطراف الثالثة المضمّنة والمقدَّمة من نظام التشغيل، وادعاءات المصدر، وحدود مراجعة الإصدارات.

## تعدد اللغات

[English](../THIRD_PARTY_NOTICES.md) | [简体中文](../zh-CN/THIRD_PARTY_NOTICES.md) | [繁體中文(台灣)](../zh-TW/THIRD_PARTY_NOTICES.md) | [繁體中文(香港)](../zh-HK/THIRD_PARTY_NOTICES.md) | [हिन्दी](../hi/THIRD_PARTY_NOTICES.md) | [Español](../es/THIRD_PARTY_NOTICES.md) | **العربية** | [Français](../fr/THIRD_PARTY_NOTICES.md)

## الوثائق

- نظرة عامة على المشروع: [README](README.md)

- مبررات التصميم: [DESIGN](DESIGN.md)

- سجل الإصدارات: [LOG](LOG.md)

- إشعارات الجهات الخارجية: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## إشعارات الجهات الخارجية

يحصر الجدول المكوّنات المضمّنة وتلك التي يوفّرها نظام التشغيل. توجد قيم SHA-256 للملفات السبعة المضمّنة في [dependencies.lock.json][local-link-001]؛ شغّل `python3 tools/verify_dependencies/verify_dependencies.py` من جذر المستودع لمقارنتها محليًا دون اتصال. في 2026-09-27، طابقت ملفات المستودع السبعة أعضاء أرشيفات الإصدارات الأصلية المسجّلة أو ملفات الوسوم بايتًا ببايت. وطابقت ملفات التراخيص المضمّنة أيضًا ملفات المصدر الأصلي المفحوصة أدناه. تثبت هذه الفحوص هوية الملفات، ولا تمثّل رأيًا قانونيًا أو مجموعة تبعيات نظام قابلة لإعادة الإنتاج بالكامل.

| المكوّن / المورد | الإصدار / التجزئة | المصدر | الترخيص حسب السجل | كيفية الاستخدام | الإسناد / مسار الترخيص الأصلي | التزامات الإصدار التي تتطلب مراجعة | تاريخ التحقق |
| --- | --- | --- | --- | --- | --- | --- | --- |
| frps | `v0.71.0`; binary SHA-256 `b95dee2bf29a021c562565cdf2116376b9fa7590361bd36ef57041a04d0e6654` | [fatedier/frp](https://github.com/fatedier/frp) | Apache-2.0 وفق ترخيص المصدر الأصلي | برنامج frps مضمّن | [included license](../../third_party/frp/LICENSE); [artifact record](../../third_party/frp/component.txt) | احتفظ برخصة Apache-2.0 المضمّنة؛ لم يتضمن أرشيف الملف التنفيذي الرسمي ملف NOTICE | 2026-09-27: تطابق الأرشيف والملف التنفيذي والترخيص |
| Lucky | `v2.27.2`; binary SHA-256 `7d3193cf969e8ed041761544b41786bcc368d46b9cf4d4d679a5bc215bd3357a` | [gdy666/lucky](https://github.com/gdy666/lucky) | MIT وفق ترخيص المصدر الأصلي | برنامج Lucky مضمّن | [included license](../../third_party/lucky/LICENSE); [artifact record](../../third_party/lucky/component.txt) | احتفظ بإشعار حقوق النشر ورخصة MIT المضمّنين | 2026-09-27: تطابق الأرشيف والملف التنفيذي والترخيص |
| sing-box | `v1.13.14`؛ المراجعة `25a600db24f7680ad9806ce5427bd0ab8afe1114`؛ SHA-256 للملف التنفيذي `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7` | [SagerNet/sing-box](https://github.com/SagerNet/sing-box) | GPL الإصدار 3 أو أحدث، إضافةً إلى شرط التسمية الخاص بالمصدر الأصلي (كما ورد في الإشعار) | ملف تنفيذي مضمّن تتشاركه anytls وproxy | [الإشعار الأصلي][local-link-002]؛ [النص الكامل لـGPL][local-link-003] | احتفظ بروابط المصدر المطابق وشرط التسمية/الارتباط الأصلي | 2026-09-27: تطابق الأرشيف والملف التنفيذي والترخيص ومراجعة الوسم |
| LibreSpeed | `v6.2.1` | [LibreSpeed](https://github.com/librespeed/speedtest) | LGPL-3.0 وفق ترخيص المصدر الأصلي | محرك متصفح مضمّن | [نص LGPL الأصلي][local-link-006] و[نص GPL][local-link-007] | احتفظ بنص الترخيص وأبقِ المصدر الأصلي متاحًا | 2026-09-27: تطابق ملفا الوسم والترخيص |
| qrcode-generator | `js2.0.4`؛ المراجعة `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8` | [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) | MIT وفق ترخيص المصدر الأصلي | مكتبة QR مضمّنة تعمل لدى العميل | [نص MIT الأصلي][local-link-008] | الاحتفاظ بإشعارات حقوق النشر والترخيص المطلوبة | 2026-09-27: تطابق ملفا الوسم والترخيص |
| iperf3 | حزمة توزيعة؛ الإصدار غير مثبّت | [ESnet/iperf](https://github.com/esnet/iperf) | BSD-3-Clause كما سُجّل سابقًا | يُشغّل برنامجًا منفصلًا مثبّتًا من نظام التشغيل؛ لا يُعاد توزيعه هنا | حقوق النشر غير مسجّلة؛ توفّر حزمة نظام التشغيل الترخيص الأصلي | إعادة التقييم إذا ضُمّن أو أُعيد توزيعه لاحقًا | غير مسجّل؛ يُعاد التحقق قبل التوزيع |

يحدّد السجل الحالي للمشروع GPL-3.0 ترخيصًا له ([LICENSE][local-link-009])، ويسجّل إعادة توزيع الملف التنفيذي sing-box المرخّص بموجب GPL سببًا لذلك؛ وتحتفظ [القرارات][local-link-010] بالمبررات والبدائل المرفوضة. يصف السجل السابق `vps-webserver` بأنه مرخّص أصلًا بموجب Apache-2.0، ويُعاد توزيعه هنا بموجب GPL-3.0. يوثّق هذا الجرد الملفات والشروط التي فُحصت لإصدار v2.0.0؛ ولا يقدّم رأيًا قانونيًا مستقلًا.

لا توجد حزم Python من أطراف ثالثة. يستخدم `src/web/app.py` المكتبة القياسية، ولذلك لا يوجد ملف قفل لحزم Python. لا يثبّت قفل الملفات المضمّنة المذكور أعلاه إصدارات Python أو iperf3 أو الحزم النظامية الأخرى التي يقدّمها نظام التشغيل؛ تُدار إصداراتها وتحديثاتها الأمنية عبر قنوات الحزم الخاصة بتوزيعة Debian/Ubuntu المستهدفة. لا يختار المثبّت إصدارات محددة للحزم ولا لقطة ثابتة للمستودع؛ ولا تزال إعادة إنتاج مجموعة التبعيات النظامية بالكامل دون حل (انظر [متطلبات إعادة الإنتاج][local-link-011]).

---

## sing-box

يعيد هذا المستودع توزيع الملف التنفيذي sing-box باسم `third_party/sing-box/sing-box` في نسخة المستودع. في 2026-09-27، طابقت بايتاته والترخيص الأصلي المضمّن أرشيف الإصدار الرسمي v1.13.14. يُثبّت باسم `/usr/local/bin/sing-box-vps-server`.

- المكوّن: `sing-box`
- المشروع الأصلي: https://github.com/SagerNet/sing-box
- Copyright (C) 2022 by nekohasekai <contact-sagernet@sekai.icu>
- الإصدار: `v1.13.14`
- مراجعة المصدر: `25a600db24f7680ad9806ce5427bd0ab8afe1114`
- الملف الموزّع: `sing-box-1.13.14-linux-amd64.tar.gz`
- SHA-256 للملف التنفيذي في المستودع: `68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`
- الترخيص: GNU GPL الإصدار 3 أو أي إصدار لاحق، مع شرط التسمية/الارتباط الخاص بالمصدر الأصلي؛ انظر [`third_party/sing-box/LICENSE`][local-link-012].

بلغت تجزئة SHA-256 لأرشيف الإصدار المنزّل `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697`. طابق الملف التنفيذي والترخيص في المستودع محتويات الأرشيف المستخرجة بايتًا ببايت.

### المصدر المقابل

أُحيل وسم v1.13.14 في 2026-09-27 إلى مراجعة المصدر `25a600db24f7680ad9806ce5427bd0ab8afe1114`. ترافق الروابط التالية إلى المصدر الأصلي الملف التنفيذي المضمّن:

- شجرة المصدر ذات الوسم: https://github.com/SagerNet/sing-box/tree/v1.13.14
- مراجعة المصدر المحددة: https://github.com/SagerNet/sing-box/tree/25a600db24f7680ad9806ce5427bd0ab8afe1114
- أرشيف المصدر: https://github.com/SagerNet/sing-box/archive/refs/tags/v1.13.14.tar.gz

أرشيف Release الأصلي المذكور في سجل المشروع السابق هو:

- https://github.com/SagerNet/sing-box/releases/download/v1.13.14/sing-box-1.13.14-linux-amd64.tar.gz

هذا المشروع مستقل ولا ينتمي إلى مؤلفي sing-box أو SagerNet ولا يحظى بتأييدهم.

---

## LibreSpeed

يستخدم اختبار السرعة في المتصفح محرك عميل LibreSpeed مضمّنًا. في 2026-09-27، طابق ملفا JavaScript المضمّنان والترخيص ملفات وسم v6.2.1 الأصلية بايتًا ببايت.

- المكوّن: محرك عميل LibreSpeed — `static/third_party/librespeed/speedtest.js`، `static/third_party/librespeed/speedtest_worker.js`
- المشروع الأصلي: https://github.com/librespeed/speedtest
- الإصدار: `v6.2.1`
- الترخيص: GNU LGPL الإصدار 3؛ النص الكامل في [`static/licenses/LGPL-3.0.txt`][local-link-013]
- التحقق: طابق الملفان والترخيص الأصلي وسم v6.2.1؛ ولم تُسجّل مراجعة commit الدقيقة للوسم في هذا الجرد.

`static/speedtest-ui.js` شفرة ربط خاصة بهذا المشروع وليست جزءًا من LibreSpeed. تعيد نقاط النهاية من جهة الخادم في `src/web/app.py` (`/speedtest/garbage`، `/speedtest/empty`، `/speedtest/getip`) تنفيذ عقد العميل/الخادم الموثّق لدى LibreSpeed؛ وهي شفرة أصلية غير مشتقة من الواجهة الخلفية PHP الأصلية.

نص LGPL-3.0 مضمّن ورابط المصدر الأصلي متاح؛ ولا يقدّم هذا الجرد رأيًا قانونيًا مستقلًا بشأن الجمع بينهما.

---

## qrcode-generator

تعرض صفحة `/proxy` في اللوحة روابط المشاركة على هيئة رموز QR قابلة للمسح باستخدام هذه المكتبة المضمّنة التي تعمل لدى العميل. في 2026-09-27، طابق ملفا JavaScript المضمّنان والترخيص الأصلي ملفات وسم js2.0.4 بايتًا ببايت.

- المكوّن: `static/third_party/qrcode/qrcode.js`، `static/third_party/qrcode/qrcode-utf8.js`
- المشروع الأصلي: https://github.com/kazuhikoarase/qrcode-generator
- Copyright (c) 2009 Kazuhiko Arase
- الإصدار: `js2.0.4`
- مراجعة المصدر: `83b7e8fe3fddd3b0368dbafd6ce56995bd25e3c8`
- الترخيص: MIT؛ النص الكامل في [`static/licenses/MIT.txt`][local-link-014]
- التحقق: طابق الملفان الملفين الأصليين `js/dist/qrcode.js` و`js/dist/qrcode_UTF8.js`؛ وطابق الترخيص الأصلي MIT أيضًا.

`static/qrcode-render.js` شفرة ربط خاصة بهذا المشروع (تجد عناصر `[data-qr-text]` وتملؤها برمز SVG المعروض) وليست جزءًا من المكتبة المضمّنة.

إشعار حقوق النشر وترخيص MIT مضمّنان مع مكتبة العميل.

---

## iperf3

- المكوّن: `iperf3`
- المشروع الأصلي: https://github.com/esnet/iperf
- الترخيص: BSD 3-Clause
- مُعدّل: لا
- **لا يُعاد توزيعه.** يُثبّت `iperf3` من مستودع حزم نظام التشغيل عبر `install.sh`، ويُستدعى بوصفه برنامجًا منفصلًا عبر حدّ العملية. لا تُشحن شفرة iperf3 أو ملفه التنفيذي في هذا المستودع؛ ولذلك لا ينطبق هنا شرط الإسناد الخاص بـBSD، المرتبط بإعادة التوزيع، وفقًا للسجل السابق؛ أعد التقييم إذا تغير أسلوب التوزيع. وهو مذكور لأن المشروع يعتمد عليه وقت التشغيل.

---

## ملفات مضمّنة من مشاريع المؤلف نفسه

ليست من أطراف ثالثة، ولكنها مسجّلة هنا لأن الشفرة لم تنشأ في هذا المستودع، ولمصدرها أهمية عند التحديث:

- `src/web/app.py` ، `static/speedtest-ui.js`، `static/style.css`، `static/visitors.js`، `tests/`، `deploy/install.sh`، `deploy/uninstall.sh`، `deploy/systemd/` — من `vps-webserver` v0.4.1 ‏(Apache-2.0 في المشروع الأصلي، أُعيد ترخيصه هنا بـGPL-3.0). انظر `config/upstream-version`.
- `deploy/anytls/setup-anytls.sh`، `third_party/sing-box/sing-box`، `third_party/sing-box/sing-box.version` — من `Anytsl-Serve` v1.2.0 ‏(GPL-3.0 في المشروع الأصلي). انظر `deploy/anytls/.upstream-version`.

---

لا يتضمن المشروع خطوطًا أو أيقونات أو صورًا أو مجموعات بيانات أو أوزان نماذج من أطراف ثالثة. لا تجري الخدمة طلبات صادرة وقت التشغيل؛ الاتصال الصادر الاختياري الوحيد هو البحث عن عنوان IP العام أثناء التثبيت، ويتحول فشله إلى تحذير.

[local-link-001]: ../../config/dependencies.lock.json
[local-link-002]: ../../third_party/sing-box/LICENSE
[local-link-003]: ../../LICENSE
[local-link-004]: #المصدر-المقابل
[local-link-005]: LOG.md#القرارات
[local-link-006]: ../../static/licenses/LGPL-3.0.txt
[local-link-007]: ../../LICENSE
[local-link-008]: ../../static/licenses/MIT.txt
[local-link-009]: ../../LICENSE
[local-link-010]: LOG.md#القرارات
[local-link-011]: DESIGN.md#متطلبات-إعادة-الإنتاج
[local-link-012]: ../../third_party/sing-box/LICENSE
[local-link-013]: ../../static/licenses/LGPL-3.0.txt
[local-link-014]: ../../static/licenses/MIT.txt
