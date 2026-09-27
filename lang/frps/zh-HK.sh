# Native shell catalog for deploy/frps/setup-frps.sh.
case "$key" in
  root_required) fmt='需要 root 權限' ;;
  integrity_failure) fmt='frps 第三方檔案完整性驗證失敗' ;;
  existing_invalid) fmt='現有 frps 設定無效；拒絕更換憑證' ;;
  existing_invalid_detail) fmt='現有 frps 設定無效：%s' ;;
  invalid_bind) fmt='FRPS_BIND_PORT 無效' ;;
  invalid_token) fmt='FRPS_TOKEN 無效' ;;
  reserved_check) fmt='無法檢查 %s 中的保留連接埠：%s' ;;
  forward_check) fmt='無法檢查轉送連接埠：%s' ;;
  port_conflict) fmt='frps 連接埠 %s 與保留的 web/proxy/轉送連接埠衝突' ;;
  port_unavailable) fmt='frps 連接埠 %s 無法使用：%s' ;;
  rollback_degraded) fmt='降級：frps 回復或原有服務復原失敗' ;;
  start_failed) fmt='frps 啟動失敗' ;;
  firewall_allow) fmt='警告：請手動在防火牆開放 frps TCP 連接埠' ;;
  firewall_remove) fmt='警告：無法移除之前由本專案建立的 frps 防火牆規則' ;;
  firewall_rollback) fmt='降級：frps 防火牆回復失敗' ;;
  ownership_failed) fmt='更新 frps 防火牆規則歸屬記錄失敗' ;;
  *) fmt="$key" ;;
esac
