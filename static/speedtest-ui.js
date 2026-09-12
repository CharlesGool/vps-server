(function () {
  const cfg = JSON.parse(document.getElementById("speedtest-config").textContent);
  const t = JSON.parse(document.getElementById("speedtest-i18n").textContent);

  const runBtn = document.getElementById("run");
  const el = {
    download: {
      value: document.getElementById("download-value"),
      bar: document.getElementById("download-bar"),
      state: document.getElementById("download-state"),
    },
    upload: {
      value: document.getElementById("upload-value"),
      bar: document.getElementById("upload-bar"),
      state: document.getElementById("upload-state"),
    },
  };
  const latencyEl = {
    value: document.getElementById("latency-value"),
    state: document.getElementById("latency-state"),
  };
  const jitterEl = {
    value: document.getElementById("jitter-value"),
  };

  // A rough ceiling used only to scale the visual bar (1 Gbps). The numeric
  // value is always exact; the bar is just eye candy.
  const BAR_MAX_MBPS = 1000;

  function showThroughput(dir, statusText, running) {
    if (statusText === "" ) return;
    if (statusText === "Fail") {
      el[dir].state.textContent = "error";
      return;
    }
    const mbps = parseFloat(statusText);
    if (isNaN(mbps)) return;
    el[dir].value.textContent = mbps.toFixed(2);
    el[dir].bar.style.width = Math.min(100, (mbps / BAR_MAX_MBPS) * 100).toFixed(1) + "%";
    el[dir].state.textContent = running ? t.measuring : t.done;
  }

  function reset() {
    for (const dir of ["download", "upload"]) {
      el[dir].value.textContent = t.idle;
      el[dir].bar.style.width = "0%";
      el[dir].state.textContent = t.waiting;
    }
    latencyEl.value.textContent = t.idle;
    latencyEl.state.textContent = t.waiting;
    jitterEl.value.textContent = t.idle;
  }

  function run() {
    reset();
    runBtn.disabled = true;
    runBtn.textContent = t.running;

    const s = new Speedtest();
    s.setParameter("url_dl", cfg.urlDl);
    s.setParameter("url_ul", cfg.urlUl);
    s.setParameter("url_ping", cfg.urlPing);
    s.setParameter("url_getIp", cfg.urlGetIp);
    s.setParameter("test_order", cfg.testOrder);
    s.setParameter("time_dl_max", cfg.timeDlMax);
    s.setParameter("time_ul_max", cfg.timeUlMax);
    s.setParameter("time_dlGraceTime", cfg.warmup);
    s.setParameter("time_ulGraceTime", cfg.warmup);
    s.setParameter("count_ping", cfg.pingSamples);
    s.setParameter("xhr_dlMultistream", cfg.downloadStreams);
    s.setParameter("xhr_ulMultistream", cfg.uploadStreams);
    s.setParameter("garbagePhp_chunkSize", cfg.chunkSizeMiB);
    s.setParameter("overheadCompensationFactor", cfg.overhead);

    s.onupdate = function (data) {
      showThroughput("download", data.dlStatus, data.testState === 1);
      showThroughput("upload", data.ulStatus, data.testState === 3);

      if (data.pingStatus !== "") {
        if (data.pingStatus === "Fail") {
          latencyEl.state.textContent = "error";
        } else {
          latencyEl.value.textContent = parseFloat(data.pingStatus).toFixed(1);
          latencyEl.state.textContent = data.testState === 2 ? t.measuring : t.done;
        }
      }
      if (data.jitterStatus !== "" && data.jitterStatus !== "Fail") {
        jitterEl.value.textContent = parseFloat(data.jitterStatus).toFixed(1);
      }
    };

    s.onend = function () {
      runBtn.disabled = false;
      runBtn.textContent = t.run_test;
    };

    s.start();
  }

  runBtn.addEventListener("click", run);
})();
