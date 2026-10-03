# Native shell catalog for deploy/uninstall.sh.
case "$key" in
  need_root) fmt='يجب التشغيل بصلاحيات root (جرّب: sudo bash deploy/uninstall.sh)\n' ;;
  removed_unit) fmt='تمت إزالة %s\n' ;;
  no_unit) fmt='لا يوجد ملف وحدة في %s — لا شيء لإزالته.\n' ;;
  purged) fmt='حُذف %s (ومعه كلمة مرور الإدارة والمنفذ والشهادات وسجل الزوار).\n' ;;
  kept) fmt='تم الاحتفاظ بـ %s — ما زالت كلمة مرور الإدارة والمنفذ والشهادات وسجل الزوار موجودة.\n' ;;
  nothing_left) fmt='%s غير موجود — لا شيء لحذفه.\n' ;;
  anytls_removing) fmt='تجري إزالة وحدة anytls ‏(%s) ...\n' ;;
  anytls_orphan) fmt='%s مثبّت لكن %s/anytls/setup-anytls.sh مفقود، لذا لا يمكن إزالته تلقائيًا.\nأزله يدويًا:\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-anytls\n  (احتفظ بـ /usr/local/bin/sing-box-vps-server إذا كانت وحدة proxy تستخدمه؛ لا تحذفه إلا بعد التأكد من عدم استخدام أي وحدة له)\n' ;;
  proxy_removing) fmt='تجري إزالة وحدة proxy ‏(%s) ...\n' ;;
  proxy_orphan) fmt='%s مثبّت لكن %s/proxy/setup-proxy.sh مفقود، لذا لا يمكن إزالته تلقائيًا.\nأزله يدويًا:\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-proxy\n  (احتفظ بـ /usr/local/bin/sing-box-vps-server إذا كانت وحدة anytls تستخدمه)\n' ;;
  frpc_removed) fmt='اكتمل تنظيف FRPC.\n' ;;
  frpc_unowned) fmt='تعذّر التحقق من ملكية FRPC لهذا المشروع؛ احتُفظ بالملفات وسجلات المنافذ الحالية.\n' ;;
  ports_released) fmt='حُذفت %s سجلات منافذ خاصة بـ vps-server.\n' ;;
  cleanup_failed) fmt='تعذّر إكمال تنظيف FRPC أو سجل المنافذ.\n' ;;
  done) fmt='\nاكتملت إزالة vps-server.\n' ;;
  lucky_fw_retained) fmt='تحذير: تم الاحتفاظ بسجل ملكية قاعدة جدار الحماية لـ Lucky؛ يلزم تنظيفه يدويًا\n' ;;
  lucky_config_retained) fmt='تم الاحتفاظ بإعدادات Lucky لـ DDNS والوكيل العكسي في /etc/vps-server-lucky/config.json\n' ;;
  frps_fw_retained) fmt='تحذير: تعذرت إزالة قاعدة جدار الحماية الخاصة بـ frps؛ تم الاحتفاظ بسجل ملكيتها\n' ;;
  error_prefix) fmt='خطأ: %s\n' ;;
  *) fmt="$key\n" ;;
esac
