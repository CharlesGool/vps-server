# Native shell catalog for deploy/frps/setup-frps.sh.
case "$key" in
  root_required) fmt='root अधिकार आवश्यक हैं' ;;
  integrity_failure) fmt='frps विक्रेता फ़ाइल की अखंडता जाँच विफल रही' ;;
  existing_invalid) fmt='मौजूदा frps कॉन्फ़िगरेशन अमान्य है; क्रेडेंशियल नहीं बदले जाएँगे' ;;
  existing_invalid_detail) fmt='मौजूदा frps कॉन्फ़िगरेशन अमान्य है: %s' ;;
  invalid_bind) fmt='FRPS_BIND_PORT अमान्य है' ;;
  invalid_token) fmt='FRPS_TOKEN अमान्य है' ;;
  reserved_check) fmt='%s में आरक्षित पोर्ट जाँचे नहीं जा सके: %s' ;;
  forward_check) fmt='फ़ॉरवर्ड किए गए पोर्ट जाँचे नहीं जा सके: %s' ;;
  port_conflict) fmt='frps पोर्ट %s आरक्षित web/proxy/फ़ॉरवर्ड पोर्ट से टकराता है' ;;
  port_unavailable) fmt='frps पोर्ट %s उपलब्ध नहीं है: %s' ;;
  rollback_degraded) fmt='अपूर्ण पुनर्स्थापन: frps रोलबैक या पिछली सेवा बहाली विफल रही' ;;
  start_failed) fmt='frps शुरू नहीं हो सका' ;;
  firewall_allow) fmt='चेतावनी: फ़ायरवॉल में frps TCP पोर्ट हाथ से खोलें' ;;
  firewall_remove) fmt='चेतावनी: पहले से स्वामित्व वाली frps फ़ायरवॉल नियम नहीं हट सकी' ;;
  firewall_rollback) fmt='अपूर्ण पुनर्स्थापन: frps फ़ायरवॉल रोलबैक विफल रहा' ;;
  ownership_failed) fmt='frps फ़ायरवॉल स्वामित्व रिकॉर्ड अपडेट नहीं हो सका' ;;
  *) fmt="$key" ;;
esac
