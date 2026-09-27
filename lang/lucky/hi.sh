# Native shell catalog for deploy/lucky/setup-lucky.sh.
case "$key" in
  root_required) fmt='root अधिकार आवश्यक हैं' ;;
  integrity_failure) fmt='Lucky विक्रेता फ़ाइल की अखंडता जाँच विफल रही' ;;
  malformed_current) fmt='मौजूदा Lucky कॉन्फ़िगरेशन अमान्य है: %s' ;;
  invalid_public) fmt='LUCKY_PUBLIC_ADMIN अमान्य है' ;;
  public_warning) fmt='चेतावनी: Lucky का सार्वजनिक प्रबंधन HTTP उपयोग करता है; क्रेडेंशियल बिना एन्क्रिप्शन के भेजे जाते हैं। इसके बजाय निजी टनल या TLS रिवर्स प्रॉक्सी उपयोग करें।' ;;
  confirm_required) fmt='सर्वर पर स्पष्ट रूप से LUCKY_PUBLIC_CONFIRM="I ACCEPT PUBLIC HTTP" सेट करना आवश्यक है' ;;
  malformed_overwrite) fmt='मौजूदा Lucky कॉन्फ़िगरेशन अमान्य है; ओवरराइट नहीं किया जाएगा: %s' ;;
  invalid_admin_port) fmt='LUCKY_ADMIN_PORT अमान्य है' ;;
  cannot_reverse) fmt='Lucky रिवर्स प्रॉक्सी का सुनने वाला पोर्ट सत्यापित नहीं हो सका' ;;
  reverse_conflict) fmt='Lucky प्रबंधन पोर्ट %s, Lucky रिवर्स प्रॉक्सी के पोर्ट से टकराता है' ;;
  cannot_console) fmt='कंसोल पोर्ट सत्यापित नहीं हो सका' ;;
  cannot_verify_file) fmt='%s सत्यापित नहीं हो सका: %s' ;;
  cannot_frps) fmt='frps पोर्ट सत्यापित नहीं हो सका' ;;
  cannot_forward) fmt='फ़ॉरवर्ड किए गए पोर्ट सत्यापित नहीं हो सके: %s' ;;
  reserved_conflict) fmt='Lucky प्रबंधन पोर्ट %s आरक्षित पोर्ट से टकराता है' ;;
  unavailable) fmt='Lucky प्रबंधन पोर्ट उपलब्ध नहीं है: %s' ;;
  restore_fw) fmt='अपूर्ण पुनर्स्थापन: Lucky firewalld स्थिति बहाल नहीं हो सकी' ;;
  restore_old) fmt='अपूर्ण पुनर्स्थापन: पुरानी Lucky फ़ायरवॉल नियम बहाल नहीं हो सकी' ;;
  remove_new) fmt='अपूर्ण पुनर्स्थापन: नई Lucky फ़ायरवॉल नियम हटाई नहीं जा सकी' ;;
  restore_file) fmt='अपूर्ण पुनर्स्थापन: %s बहाल नहीं हो सका' ;;
  remove_file) fmt='अपूर्ण पुनर्स्थापन: %s हटाया नहीं जा सका' ;;
  restore_service) fmt='अपूर्ण पुनर्स्थापन: Lucky सेवा बहाल नहीं हो सकी' ;;
  no_firewall) fmt='चेतावनी: कोई सक्रिय समर्थित फ़ायरवॉल नहीं है; बाहरी फ़ायरवॉल नियम जाँचें और सार्वजनिक HTTP प्रबंधन पहुँच हाथ से सीमित करें' ;;
  *) fmt="$key" ;;
esac
