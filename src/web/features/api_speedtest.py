"""JSON API for the browser speed test: the visitor's address and LibreSpeed settings."""


class SpeedtestApiMixin:
    API_ROUTES_SPEEDTEST = {("GET", "speedtest"): "api_speedtest"}

    def api_speedtest(self):
        context = self.context
        if context.closed_page_module("/speedtest"):
            return self.api_error(403, "feature_closed", url="/closed?module=speedtest")
        # Maps onto LibreSpeed's own settings; the test endpoints stay under /speedtest/.
        return self.api_ok({
            "clientIp": self.client_ip(),
            "config": {
                "url_dl": "/speedtest/garbage", "url_ul": "/speedtest/empty",
                "url_ping": "/speedtest/empty", "url_getIp": "/speedtest/getip",
                # ping+jitter, download, upload; the address is already shown.
                "test_order": "P_D_U",
                "time_dl_max": context.TEST_SECONDS, "time_ul_max": context.TEST_SECONDS,
                "time_dlGraceTime": context.WARMUP_SECONDS, "time_ulGraceTime": context.WARMUP_SECONDS,
                "count_ping": context.PING_SAMPLES,
                "xhr_dlMultistream": context.DOWNLOAD_STREAMS, "xhr_ulMultistream": context.UPLOAD_STREAMS,
                "garbagePhp_chunkSize": min(100, context.MAX_TEST_MB),
                "overheadCompensationFactor": context.OVERHEAD_FACTOR,
            },
        })
