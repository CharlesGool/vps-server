# Native shell catalog for deploy/uninstall.sh.
case "$key" in
  need_root) fmt='必須以 root 執行（試試：sudo bash deploy/uninstall.sh）\n' ;;
  removed_unit) fmt='已移除 %s\n' ;;
  no_unit) fmt='%s 不存在 —— 沒有需要移除的 unit 檔案。\n' ;;
  purged) fmt='已刪除 %s（管理員密碼、連接埠、憑證及訪客記錄均已清除）。\n' ;;
  kept) fmt='已保留 %s —— 管理員密碼、連接埠、憑證及訪客記錄仍然存在。\n' ;;
  nothing_left) fmt='%s 不存在 —— 沒有需要刪除的資料。\n' ;;
  anytls_removing) fmt='正在解除安裝 anytls 模組（%s）...\n' ;;
  anytls_orphan) fmt='%s 已安裝，但 %s/anytls/setup-anytls.sh 已不存在，無法自動解除安裝。\n請手動清理：\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-anytls\n  （如果 proxy 模組仍在使用 /usr/local/bin/sing-box-vps-server，請保留它；僅在確認沒有模組使用時才清理）\n' ;;
  proxy_removing) fmt='正在解除安裝 proxy 模組（%s）...\n' ;;
  proxy_orphan) fmt='%s 已安裝，但 %s/proxy/setup-proxy.sh 已不存在，無法自動解除安裝。\n請手動清理：\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-proxy\n  （如果 anytls 模組仍在使用 /usr/local/bin/sing-box-vps-server，請保留它）\n' ;;
  frpc_removed) fmt='FRPC 清理完成.\n' ;;
  frpc_unowned) fmt='未能確認 FRPC 檔案屬於本項目,已保留現有 FRPC 檔案及其連接埠登記.\n' ;;
  ports_released) fmt='已釋放 %s 條 vps-server 連接埠登記.\n' ;;
  cleanup_failed) fmt='無法完成 FRPC 或連接埠登記清理.\n' ;;
  done) fmt='\nvps-server 已解除安裝。\n' ;;
  lucky_fw_retained) fmt='警告：Lucky 防火牆歸屬記錄已保留；需要手動清理\n' ;;
  lucky_config_retained) fmt='Lucky DDNS/反向代理設定已保留在 /etc/vps-server-lucky/config.json\n' ;;
  frps_fw_retained) fmt='警告：無法刪除由本專案建立的 frps 防火牆規則；歸屬記錄已保留\n' ;;
  error_prefix) fmt='錯誤：%s\n' ;;
  *) fmt="$key\n" ;;
esac
