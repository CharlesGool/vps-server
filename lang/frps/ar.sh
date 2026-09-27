# Native shell catalog for deploy/frps/setup-frps.sh.
case "$key" in
  root_required) fmt='يلزم التشغيل بصلاحيات root' ;;
  integrity_failure) fmt='فشل التحقق من سلامة ملف frps المضمّن' ;;
  existing_invalid) fmt='إعدادات frps الحالية غير صالحة؛ لن تُستبدل بيانات الاعتماد' ;;
  existing_invalid_detail) fmt='إعدادات frps الحالية غير صالحة: %s' ;;
  invalid_bind) fmt='قيمة FRPS_BIND_PORT غير صالحة' ;;
  invalid_token) fmt='قيمة FRPS_TOKEN غير صالحة' ;;
  reserved_check) fmt='تعذر فحص المنافذ المحجوزة في %s: %s' ;;
  forward_check) fmt='تعذر فحص المنافذ المعاد توجيهها: %s' ;;
  port_conflict) fmt='منفذ frps ‏%s يتعارض مع منفذ محجوز للويب أو الوكيل أو التوجيه' ;;
  port_unavailable) fmt='منفذ frps ‏%s غير متاح: %s' ;;
  rollback_degraded) fmt='حالة متدهورة: فشل التراجع عن تثبيت frps أو استعادة الخدمة السابقة' ;;
  start_failed) fmt='تعذر بدء frps' ;;
  firewall_allow) fmt='تحذير: افتح منفذ TCP الخاص بـ frps في جدار الحماية يدويًا' ;;
  firewall_remove) fmt='تحذير: تعذرت إزالة قاعدة جدار الحماية السابقة الخاصة بـ frps' ;;
  firewall_rollback) fmt='حالة متدهورة: فشل التراجع عن قواعد جدار الحماية لـ frps' ;;
  ownership_failed) fmt='فشل تحديث سجل ملكية قاعدة جدار الحماية لـ frps' ;;
  *) fmt="$key" ;;
esac
