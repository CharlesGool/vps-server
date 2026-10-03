# Native shell catalog for deploy/uninstall.sh.
case "$key" in
  need_root) fmt='root के रूप में चलाना आवश्यक है (कोशिश करें: sudo bash deploy/uninstall.sh)\n' ;;
  removed_unit) fmt='%s हटाया गया\n' ;;
  no_unit) fmt='%s पर कोई unit फ़ाइल नहीं है — हटाने के लिए कुछ नहीं।\n' ;;
  purged) fmt='%s मिटा दिया गया (प्रशासक पासवर्ड, पोर्ट, प्रमाणपत्र और विज़िटर लॉग भी हट गए)।\n' ;;
  kept) fmt='%s रखा गया — प्रशासक पासवर्ड, पोर्ट, प्रमाणपत्र और विज़िटर लॉग अब भी मौजूद हैं।\n' ;;
  nothing_left) fmt='%s मौजूद नहीं है — मिटाने के लिए कुछ नहीं।\n' ;;
  anytls_removing) fmt='anytls मॉड्यूल हटाया जा रहा है (%s) ...\n' ;;
  anytls_orphan) fmt='%s इंस्टॉल है, लेकिन %s/anytls/setup-anytls.sh नहीं मिला; इसे अपने आप नहीं हटाया जा सकता।\nइसे हाथ से हटाएँ:\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-anytls\n  (यदि proxy अभी /usr/local/bin/sing-box-vps-server का उपयोग करता है तो इसे रखें; कोई मॉड्यूल उपयोग नहीं करता, यह जाँचने के बाद ही हटाएँ)\n' ;;
  proxy_removing) fmt='proxy मॉड्यूल हटाया जा रहा है (%s) ...\n' ;;
  proxy_orphan) fmt='%s इंस्टॉल है, लेकिन %s/proxy/setup-proxy.sh नहीं मिला; इसे अपने आप नहीं हटाया जा सकता।\nइसे हाथ से हटाएँ:\n  systemctl disable --now %s\n  rm -f /etc/systemd/system/%s\n  rm -rf /etc/vps-server-proxy\n  (यदि anytls अभी /usr/local/bin/sing-box-vps-server का उपयोग करता है तो इसे रखें)\n' ;;
  frpc_removed) fmt='FRPC की सफ़ाई पूरी हुई।\n' ;;
  frpc_unowned) fmt='FRPC का स्वामित्व सत्यापित नहीं हो सका; मौजूदा FRPC फ़ाइलें और उनके पोर्ट रिकॉर्ड रखे गए हैं।\n' ;;
  ports_released) fmt='vps-server की %s पोर्ट प्रविष्टियाँ हटाई गईं।\n' ;;
  cleanup_failed) fmt='FRPC या पोर्ट रजिस्टर की सफ़ाई पूरी नहीं हुई।\n' ;;
  done) fmt='\nvps-server हटा दिया गया है।\n' ;;
  lucky_fw_retained) fmt='चेतावनी: Lucky फ़ायरवॉल स्वामित्व रिकॉर्ड रखा गया है; हाथ से सफ़ाई आवश्यक है\n' ;;
  lucky_config_retained) fmt='Lucky DDNS/रिवर्स प्रॉक्सी कॉन्फ़िगरेशन /etc/vps-server-lucky/config.json में रखा गया है\n' ;;
  frps_fw_retained) fmt='चेतावनी: frps की फ़ायरवॉल नियम नहीं हट सका; स्वामित्व रिकॉर्ड रखा गया है\n' ;;
  error_prefix) fmt='त्रुटि: %s\n' ;;
  *) fmt="$key\n" ;;
esac
