# Native shell catalog for deploy/uninstall.sh.
case "$key" in
  need_root) fmt='必须以 root 运行（试试：sudo bash deploy/uninstall.sh）\n' ;;
  removed_unit) fmt='已删除 %s\n' ;;
  no_unit) fmt='%s 不存在 —— 没有需要删除的 unit 文件。\n' ;;
  purged) fmt='已删除 %s（管理员密码、端口、证书和访问日志都已清除）。\n' ;;
  kept) fmt='已保留 %s —— 管理员密码、端口、证书和访问日志都还在。\n' ;;
  nothing_left) fmt='%s 不存在 —— 没有需要删除的数据。\n' ;;
  anytls_removing) fmt='正在卸载 anytls 模块（%s）...\n' ;;
  anytls_orphan) fmt='%s 已安装，但 %s/anytls/setup-anytls.sh 已不存在，无法自动卸载。\n请手动清理：\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-anytls\n  （如果 proxy 模块仍在使用 /usr/local/bin/sing-box-vps-server，请保留它；仅在确认没有模块使用时才清理）\n' ;;
  proxy_removing) fmt='正在卸载 proxy 模块（%s）...\n' ;;
  proxy_orphan) fmt='%s 已安装，但 %s/proxy/setup-proxy.sh 已不存在，无法自动卸载。\n请手动清理：\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-proxy\n  （如果 anytls 模块仍在使用 /usr/local/bin/sing-box-vps-server，请保留它）\n' ;;
  frpc_removed) fmt='FRPC 清理完成.\n' ;;
  frpc_unowned) fmt='无法确认 FRPC 文件归属本项目,已保留现有 FRPC 文件及其端口登记.\n' ;;
  ports_released) fmt='已释放 %s 条 vps-server 端口登记.\n' ;;
  cleanup_failed) fmt='无法完成 FRPC 或端口登记清理.\n' ;;
  tailscale_stop_failed) fmt='无法停止 Tailscale 服务' ;;
  done) fmt='\nvps-server 已卸载完成。\n' ;;
  lucky_fw_retained) fmt='警告：Lucky 防火墙归属记录已保留；需要手动清理\n' ;;
  lucky_config_retained) fmt='Lucky DDNS/反向代理配置已保留在 /etc/vps-server-lucky/config.json\n' ;;
  frps_fw_retained) fmt='警告：无法删除归属本项目的 frps 防火墙规则；归属记录已保留\n' ;;
  prefix_not_project) fmt='拒绝删除 %s：它不像 vps-server 的安装目录（没有 app.py 或 src/web/）。请检查 PREFIX；如果它确实是安装目录，请手动删除 %s。未做任何改动。\n' ;;
  purge_head) fmt='完全卸载会永久删除：\n' ;;
  purge_prefix) fmt='  - 程序目录 %s\n' ;;
  purge_state) fmt='  - 状态目录 %s（管理员密码、证书、设置和日志）\n' ;;
  purge_backups) fmt='  - %s 份配置备份（%s）\n' ;;
  purge_drive) fmt='  - 迷你网盘中的 %s 个文件，共 %s\n' ;;
  purge_modules) fmt='  - 本项目的节点、FRPS/FRPC、域名转发和 Tailscale 设置\n' ;;
  purge_data_key) fmt='  - 数据密钥 %s\n' ;;
  purge_outside_kept) fmt='保留：%s（在状态目录之外）及其所需的数据密钥。\n' ;;
  purge_needs_confirm) fmt='完全卸载会删除上面列出的数据，必须确认。请在终端中运行；无人值守时设置 VPSSRV_UNINSTALL_YES=1；KEEP_DATA=1 只卸载服务并保留数据。未做任何改动。\n' ;;
  purge_confirm) fmt='输入 yes 删除以上全部内容（输入其他内容或 %s 秒内无回答则取消）：' ;;
  purge_cancelled) fmt='已取消，未做任何改动。\n' ;;
  data_key_removed) fmt='已删除数据密钥 %s。\n' ;;
  data_key_kept) fmt='已保留数据密钥 %s：%s 中可能仍有用它加密的数据。\n' ;;
  error_prefix) fmt='错误：%s\n' ;;
  *) fmt="$key\n" ;;
esac
