# Native shell catalog for deploy/lucky/setup-lucky.sh.
case "$key" in
  root_required) fmt='需要 root 權限' ;;
  integrity_failure) fmt='Lucky 第三方檔案完整性驗證失敗' ;;
  malformed_current) fmt='現有 Lucky 設定格式錯誤：%s' ;;
  invalid_public) fmt='LUCKY_PUBLIC_ADMIN 無效' ;;
  public_warning) fmt='警告：Lucky 公開管理介面使用 HTTP，憑證會以明文傳送。請改用私人通道或 TLS 反向代理。' ;;
  confirm_required) fmt='必須在伺服器端明確設定 LUCKY_PUBLIC_CONFIRM="I ACCEPT PUBLIC HTTP"' ;;
  malformed_overwrite) fmt='現有 Lucky 設定格式錯誤；拒絕覆寫：%s' ;;
  invalid_admin_port) fmt='LUCKY_ADMIN_PORT 無效' ;;
  cannot_reverse) fmt='無法驗證 Lucky 反向代理監聽連接埠' ;;
  reverse_conflict) fmt='Lucky 管理連接埠 %s 與 Lucky 反向代理監聽連接埠衝突' ;;
  cannot_console) fmt='無法驗證主控台連接埠' ;;
  cannot_verify_file) fmt='無法驗證 %s：%s' ;;
  cannot_frps) fmt='無法驗證 frps 連接埠' ;;
  cannot_forward) fmt='無法驗證轉送連接埠：%s' ;;
  reserved_conflict) fmt='Lucky 管理連接埠 %s 與保留連接埠衝突' ;;
  unavailable) fmt='Lucky 管理連接埠無法使用：%s' ;;
  restore_fw) fmt='降級：Lucky firewalld 狀態復原失敗' ;;
  restore_old) fmt='降級：舊 Lucky 防火牆規則復原失敗' ;;
  remove_new) fmt='降級：新 Lucky 防火牆規則移除失敗' ;;
  restore_file) fmt='降級：無法復原 %s' ;;
  remove_file) fmt='降級：無法移除 %s' ;;
  restore_service) fmt='降級：Lucky 服務復原失敗' ;;
  no_firewall) fmt='警告：沒有啟用受支援的防火牆；請檢查外部防火牆規則，並手動限制公開 HTTP 管理存取' ;;
  *) fmt="$key" ;;
esac
