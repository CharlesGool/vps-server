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
  done) fmt='\nvps-server 已卸载完成。\n' ;;
  lucky_fw_retained) fmt='警告：Lucky 防火墙归属记录已保留；需要手动清理\n' ;;
  lucky_config_retained) fmt='Lucky DDNS/反向代理配置已保留在 /etc/vps-server-lucky/config.json\n' ;;
  frps_fw_retained) fmt='警告：无法删除归属本项目的 frps 防火墙规则；归属记录已保留\n' ;;
  error_prefix) fmt='错误：%s\n' ;;
  *) fmt="$key\n" ;;
esac
