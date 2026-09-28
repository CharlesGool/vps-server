// Renders every [data-qr-text] element as a scannable QR code, using the
// vendored kazuhikoarase/qrcode-generator (static/third_party/qrcode/qrcode.js +
// static/third_party/qrcode/qrcode-utf8.js
// for multi-byte text such as a Chinese interface's "LAN-eth0" label).
// Own code, not part of the vendored library — see doc/THIRD_PARTY_NOTICES.md.
(function () {
  function renderAll() {
    var nodes = document.querySelectorAll("[data-qr-text]");
    for (var i = 0; i < nodes.length; i += 1) {
      var el = nodes[i];
      var text = el.getAttribute("data-qr-text");
      if (!text) continue;
      try {
        // Type 0 lets the library pick the smallest size that fits the
        // data; "M" balances scan reliability against QR density for a
        // share link that can run past 100 characters.
        var qr = qrcode(0, "M");
        qr.addData(text);
        qr.make();
        el.innerHTML = qr.createSvgTag({ scalable: true });
      } catch (err) {
        el.textContent = "";
      }
    }
  }
  window.renderPrivateQr = function (el, value) {
    if (!el || !value) return;
    var qr = qrcode(0, "M");
    qr.addData(value);
    qr.make();
    el.innerHTML = qr.createSvgTag({ scalable: true });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderAll);
  } else {
    renderAll();
  }
})();
