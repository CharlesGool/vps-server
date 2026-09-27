# Native shell catalog for deploy/lucky/setup-lucky.sh.
case "$key" in
  root_required) fmt='يلزم التشغيل بصلاحيات root' ;;
  integrity_failure) fmt='فشل التحقق من سلامة ملف Lucky المضمّن' ;;
  malformed_current) fmt='إعدادات Lucky الحالية غير صالحة: %s' ;;
  invalid_public) fmt='قيمة LUCKY_PUBLIC_ADMIN غير صالحة' ;;
  public_warning) fmt='تحذير: تستخدم إدارة Lucky العامة HTTP وترسل بيانات الاعتماد دون تشفير. استخدم نفقًا خاصًا أو وكيلًا عكسيًا يعمل بـ TLS.' ;;
  confirm_required) fmt='يلزم ضبط LUCKY_PUBLIC_CONFIRM="I ACCEPT PUBLIC HTTP" صراحةً على الخادم' ;;
  malformed_overwrite) fmt='إعدادات Lucky الحالية غير صالحة؛ رُفضت الكتابة فوقها: %s' ;;
  invalid_admin_port) fmt='قيمة LUCKY_ADMIN_PORT غير صالحة' ;;
  cannot_reverse) fmt='تعذر التحقق من منفذ استماع الوكيل العكسي في Lucky' ;;
  reverse_conflict) fmt='منفذ إدارة Lucky ‏%s يتعارض مع منفذ الوكيل العكسي في Lucky' ;;
  cannot_console) fmt='تعذر التحقق من منفذ وحدة التحكم' ;;
  cannot_verify_file) fmt='تعذر التحقق من %s: %s' ;;
  cannot_frps) fmt='تعذر التحقق من منفذ frps' ;;
  cannot_forward) fmt='تعذر التحقق من المنافذ المعاد توجيهها: %s' ;;
  reserved_conflict) fmt='منفذ إدارة Lucky ‏%s يتعارض مع منفذ محجوز' ;;
  unavailable) fmt='منفذ إدارة Lucky غير متاح: %s' ;;
  restore_fw) fmt='حالة متدهورة: فشلت استعادة حالة firewalld الخاصة بـ Lucky' ;;
  restore_old) fmt='حالة متدهورة: فشلت استعادة قاعدة جدار الحماية القديمة لـ Lucky' ;;
  remove_new) fmt='حالة متدهورة: تعذرت إزالة قاعدة جدار الحماية الجديدة لـ Lucky' ;;
  restore_file) fmt='حالة متدهورة: تعذرت استعادة %s' ;;
  remove_file) fmt='حالة متدهورة: تعذرت إزالة %s' ;;
  restore_service) fmt='حالة متدهورة: فشلت استعادة خدمة Lucky' ;;
  no_firewall) fmt='تحذير: لا يوجد جدار حماية مدعوم ونشط؛ تحقق من القواعد الخارجية وقيّد الوصول العام لإدارة HTTP يدويًا' ;;
  *) fmt="$key" ;;
esac
