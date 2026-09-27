---
name: project-readme-ar
description: نظرة عامة على المشروع وطريقة استخدامه
metadata:
  version: "1.0.0"
  lang: "ar"
---

# vps-server

## تعدد اللغات

[English](../../README.md) | [简体中文](../zh-CN/README.md) | [繁體中文(台灣)](../zh-TW/README.md) | [繁體中文(香港)](../zh-HK/README.md) | [हिन्दी](../hi/README.md) | [Español](../es/README.md) | **العربية** | [Français](../fr/README.md)

## الوثائق

- نظرة عامة على المشروع: [README](README.md)

- مبررات التصميم: [DESIGN](DESIGN.md)

- سجل الإصدارات: [LOG](LOG.md)

- إشعارات الجهات الخارجية: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)

## مقدمة

حزمة بوحدات قابلة للاختيار لخادم VPS يعمل بنظام Debian/Ubuntu: صفحة عامة لفحص إمكانية الوصول إلى منافذ الويب، ولوحة للمشغّل لاختبارات السرعة وتسجيل الاتصالات، ونافذة iperf3 عند الطلب، وعُقد وكيل sing-box. يتضمن الإصدار 2.0.0 أيضًا وحدة `proxy` ذات البروتوكولات الأربعة ومثبّتَي frps وLucky التجريبيين. انظر [الحالة الراهنة وحدود القبول][local-link-001].

## الوظائف

- **إثبات إمكانية الوصول للجميع.** صفحة بسيطة عمدًا على المنفذين **80** و
  **443**، بلا تسجيل دخول. أعطِ شخصًا عنوان IP؛ فإذا ظهرت الصفحة، كانت منافذ الويب لديك قابلة للوصول من موقعه. تعرض عنوان IP المصدر لديه، ووقت الخادم، والمنفذ والبروتوكول اللذين وصل عبرهما، ولا تعرض أي معلومات أخرى عن المضيف.
- **قياس معدل النقل من المتصفح.** تُجري لوحة محمية بكلمة مرور على منفذ عالٍ عشوائي محفوظ اختبارات الرفع والتنزيل باستخدام محرك LibreSpeed.
- **قياس معدل النقل وزمن الاستجابة عبر iperf3 عند الطلب.** تفتح اللوحة نافذة محددة المدة؛ لا يعمل `iperf3 -s` إلا خلالها، ويتوقف تلقائيًا عند انتهائها. يحصل المختبِر على معدل النقل من iperf3، ويحصل أيضًا على زمن الذهاب والإياب على عميل Linux من `mean_rtt` في مخرجات `--json`؛ يأتي هذا الحقل من `TCP_INFO` في النواة، ولا يظهر على العملاء الذين لا يمكنهم قراءته، ولا سيما iperf3 تحت Cygwin على Windows. يضيف وضع UDP (`-u`) التذبذب وفقد الحزم على جميع المنصات.
- **تسجيل المتصلين.** كل اتصال TCP وارد، على أي منفذ لا HTTP فقط، يُقرأ من `/proc/net/tcp[6]` ويُخزّن في SQLite مع الاحتفاظ بأحدث 1000 اتصال.
- **تقديم وكيل anytls.** sing-box بشهادة ذاتية التوقيع، مع BBR. عند تثبيت هذه الوحدة، تعرض صفحة `/proxy` في اللوحة حالة العقدة ومدخل Clash الخاص بها ورابط `anytls://` مع زر للنسخ، فلا يلزم الرجوع إلى الطرفية لمشاركة العقدة مع عميل.
- **تقديم وكيل vmess/vless/trojan/shadowsocks بأي مجموعة فرعية منها.** عملية sing-box إضافية تشارك وحدة anytls الملف التنفيذي المضمّن نفسه. عند تثبيتها، تحصل صفحة `/proxy` المشتركة في اللوحة على قسم لكل بروتوكول يبيّن منفذه ومعرّف UUID أو كلمة مروره ومدخل Clash ورابط المشاركة ورمز QR. ولكل بروتوكول زر إعادة ضبط خاص به، لا يغيّر بيانات اعتماد البروتوكولات الأخرى.

الوحدات القابلة للاختيار هي web وiperf3 وanytls وproxy وfrps وLucky. تظل وحدتا frps وLucky تجريبيتين؛ ولم يُقبل سلوكهما على مضيف حقيقي لهذا الإصدار.

**ما ليس من الأهداف:** لا ACME ولا أسماء نطاقات (الشهادة على 443 ذاتية التوقيع عمدًا)؛ ولا iperf3 دائم التشغيل؛ ولا وكيل عكسي أو حاويات. لا تكشف الصفحة العامة مطلقًا عن اسم المضيف أو النواة أو مدة التشغيل أو قائمة الخدمات أو إعدادات الوكيل. لا يحل هذا المشروع محل `vps-webserver` أو `Anytsl-Serve`؛ إذ يستمر صيانتهما بصورة مستقلة وتُضمّن شفرتهما هنا بدلًا من دمجهما فيه.

## المتطلبات

- النظام: Debian 11+ أو Ubuntu 20.04+ مع systemd، والتشغيل بصلاحيات root.
- بيئة التشغيل: Python 3.9+ (يكفي `python3` الخاص بالتوزيعة؛ لا توجد تبعيات Python يلزم تثبيتها).
- البنية: أي بنية لوحدتي web وiperf3؛ و**x86-64 فقط** لوحدات anytls وproxy وfrps وLucky، لأن الملفات التنفيذية المضمّنة تستهدف amd64.
- لوحدة web على منافذها العامة الافتراضية، **يجب** أن يكون المنفذان 80 و443 متاحين؛ يرفض المثبّت التثبيت بدلًا من مزاحمة nginx أو Apache أو Caddy أو `vps-webserver`.
- الخدمات الخارجية: لا شيء وقت التشغيل. يحتاج التثبيت إلى مرآة حزم التوزيعة؛ وقد يتصل البحث الاختياري عن عنوان IP العام بخدمة خارجية.
- الحد الأدنى: النظام وبيئة التشغيل والبنية والمنافذ المتاحة المذكورة أعلاه. لم تُسجّل متطلبات إضافية موصى بها للعتاد؛ ويمكن لخادم VPS بسعة قرص تقارب 150 MB استيعاب الملف التنفيذي المضمّن.

## التثبيت

تثبيت سريع بسطر واحد (أحدث وسم إصدار، دون متغيرات إعداد):

```bash
git clone --branch v2.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server && cd vps-server && bash deploy/install.sh
```

خطوة بخطوة، مع الإعداد:

```bash
# Always clone a tag, not the default branch — the branch tip may be mid-work.
# Latest release tag: git ls-remote --tags https://github.com/CharlesGool/vps-server.git
git clone --branch v2.0.0 --depth 1 https://github.com/CharlesGool/vps-server.git vps-server
cd vps-server
cp .env.example .env   # optional — every variable has a working default
bash deploy/install.sh
```

يسأل `deploy/install.sh` عن الوحدات المراد تثبيتها، ولغة الواجهة، وحماية اللوحة بكلمة مرور، والمنافذ المستخدمة. يتضمن وسم v2.0.0 الوحدات الست كلها القابلة للاختيار؛ وتظل frps وLucky تجريبيتين.

**إعادة تشغيله تُحدّث التثبيت في مكانه.** يكتشف التثبيت الموجود ويعرض الإبقاء على إعداداته، ولا يسأل إلا عن الإعدادات التي لم تكن متاحة في الإصدار المثبّت، مع عرض قيمتها الافتراضية، لذا يُعدّ ضغط Enter إجابة صالحة. تبقى كلمة مرور اللوحة والمنفذ المحفوظ والشهادات وسجل الزوار وبيانات اعتماد عقدة anytls، وكذلك منفذ وبيانات اعتماد كل بروتوكول proxy مثبّت. أجب بـ`n` عن سؤال الترقية لإعادة السؤال عن الإعدادات بدلًا من ذلك.

## إرشادات

### بدء سريع

يضع الإصدار 2.0.0 تنفيذ الويب في `src/web/app.py` ويشغّل المثبّتات من `deploy/`. توجد الملفات التنفيذية المضمّنة وإشعارات تراخيصها تحت `third_party/`، وبيانات الإصدار في `config/`. تبقى الملفات المثبّتة في تخطيط مسطح تحت `$PREFIX`؛ ولا ينقل تغيير تخطيط نسخة المستودع بيانات التشغيل. اجتازت المسارات الجديدة الاختبارات المحلية، لكن هذا الإصدار لم يُقبل بعد على مضيف حقيقي.

```bash
bash deploy/install.sh                       # interactive: temporary browser setup wizard
sudo VPSSRV_MODULES=web,iperf3 bash deploy/install.sh   # unattended, no prompts
systemctl status vps-server-web              # is it up
bash deploy/anytls/setup-anytls.sh status           # anytls node details, if that module is installed
bash deploy/proxy/setup-proxy.sh status             # proxy node details, if that module is installed
```

ثم من جهاز آخر:

```bash
curl -sS  http://<ip>/                     # reachability over plain HTTP
curl -sSk https://<ip>/                    # ... and over TLS (self-signed)
iperf3 -c <ip> -p 5201 --json              # only while a window is open
```

### التحقق من عمله

بعد `bash deploy/install.sh`، ينبغي أن ترى كتلة ملخّص تذكر كل وحدة مثبّتة ومنفذها. ثم:

- يُظهر `systemctl status vps-server-web` الحالة `active (running)`.
- يُظهر فتح `http://<ip>/` من **جهاز آخر** صفحة عنوانها "Reachable" تعرض عنوان IP العام الخاص بك. ويُظهر فتح `https://<ip>/` الصفحة نفسها بعد قبول تحذير الشهادة، مع HTTPS في سطر البروتوكول.
- يُظهر تسجيل الدخول إلى `http://<ip>:<console port>/` لوحة التحكم مع عنصر التحكم في iperf3 والنافذة مغلقة.
- بعد فتح نافذة لخمس دقائق، يُظهر `iperf3 -c <ip> -p 5201 --json` من جهاز آخر معدل النقل ويتضمن `mean_rtt`. وبعد خمس دقائق يفشل الأمر نفسه في الاتصال؛ وهذا إغلاق النافذة تلقائيًا، وليس عطلًا.
- إذا ثبّتَّ anytls: يُظهر `systemctl status vps-server-anytls` الحالة `active (running)`.
- إذا ثبّتَّ proxy: يُظهر `systemctl status vps-server-proxy` الحالة `active (running)`.

### الإعداد

لكل متغير قيمة افتراضية صالحة؛ وملف `.env` اختياري. أهم المتغيرات:

| المتغير | المعنى | القيمة الافتراضية | مطلوب |
|---|---|---|---|
| `VPSSRV_PUBLIC_HTTP_PORT` | صفحة التحقق العامة، بنص واضح | `80` | لا |
| `VPSSRV_PUBLIC_HTTPS_PORT` | صفحة التحقق العامة، عبر TLS | `443` | لا |
| `VPSSRV_PUBLIC_ENABLE` | تفعيل الصفحة العامة | `1` | لا |
| `VPSSRV_CONSOLE_PORT` | منفذ اللوحة؛ القيمة `0` تولّد منفذًا وتحفظه | `0` | لا |
| `VPSSRV_AUTH` | اشتراط كلمة مرور للوحة | `1` | لا |
| `VPSSRV_IPERF_PORT` | المنفذ الذي تستمع عليه نافذة iperf3 المفتوحة | `5201` | لا |
| `VPSSRV_IPERF_MAX_MINUTES` | الحد الأقصى الذي لا يمكن تجاوزه من اللوحة | `60` | لا |
| `VPSSRV_DEFAULT_LANG` | `en` / `zh_cn` / `zh_tw` / `zh_hk` / `hi` / `es` / `ar` / `fr` | `en` | لا |

المرجع الكامل: [مرجع الإعدادات][local-link-002].

## إلغاء التثبيت

شغّل الأمر بصلاحيات root من نسخة المثبّت، باستخدام قيمتي `PREFIX` و`SERVICE_NAME` نفسيهما المستخدمتين عند التثبيت (يطبع ملخّص المثبّت أمر الإزالة الدقيق). لإزالة الوحدات والخدمات المثبّتة **مع
الاحتفاظ بالبيانات** داخل `$PREFIX` لإعادة تثبيت لاحقة:

```bash
KEEP_DATA=1 bash deploy/uninstall.sh
```

لإزالة الوحدات المثبّتة **وحذف البيانات أيضًا** (بما في ذلك سجل الزوار وكلمة مرور اللوحة والمنفذ المحفوظ والشهادات داخل `$PREFIX`):

```bash
bash deploy/uninstall.sh
```

يفكّ كلا الوضعين خدمات anytls/proxy وإعدادات وحداتهما المنفصلة إذا كانت مثبّتة. يحتفظ `KEEP_DATA=1` بـ`$PREFIX`، لا بإعدادات تلك الوحدات.

## شكر وتقدير

يستخدم اختبار المتصفح [LibreSpeed](https://github.com/librespeed/speedtest)؛ ويستخدم عرض رموز QR مكتبة
[qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator)؛ ومحرك الوكيل المضمّن هو
[sing-box](https://github.com/SagerNet/sing-box). تضم الوحدات التجريبية
[frp](https://github.com/fatedier/frp) و
[Lucky](https://github.com/gdy666/lucky). راجع [إشعارات الأطراف الثالثة][local-link-003] لجرد المكوّنات ومسارات تراخيصها الأصلية.

## الترخيص

ترخيص المشروع: GPL-3.0 ‏(SPDX: `GPL-3.0-only`)؛ اقرأ النص الكامل في [LICENSE][local-link-004]. مبررات الجمع التاريخية في [القرارات][local-link-005]. ترد المكوّنات المضمّنة وتراخيصها الأصلية ومصادر الملفات المتحقق منها وحدود المراجعة القانونية المتبقية في [THIRD_PARTY_NOTICES.md][local-link-006].

لا ينتمي هذا المشروع إلى sing-box/SagerNet أو LibreSpeed ولا يحظى بتأييدهما.

[local-link-001]: LOG.md#القيود-وحالة-القبول-الحالية
[local-link-002]: DESIGN.md#configuration-reference
[local-link-003]: THIRD_PARTY_NOTICES.md
[local-link-004]: ../../LICENSE
[local-link-005]: LOG.md#القرارات
[local-link-006]: THIRD_PARTY_NOTICES.md
