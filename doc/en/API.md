---
name: api-en
description: "The console's token API: authentication, permissions, and the request and response of every endpoint"
metadata:
  version: "1.0.0"
  lang: "en"
---

# Token API

This document describes `/api/v1/*`, for scripts and other consoles (the Central management page). The `/api/*` session API used by the browser pages is out of scope and not guaranteed to be stable.

## Authentication

1. Generate a token in the API tokens card on the Central management page. A token looks like `vpss_...`, is shown only once when generated, and the server stores only its SHA-256.
2. When the Central management switch on the home page is off, every token endpoint returns 403 `feature_closed`.
3. Every request carries the header `Authorization: Bearer <token>`. No session cookie is needed, and the "require client certificate" and same-origin checks do not apply; the console access limit still applies.
4. A wrong token counts as a failed login; once the limit is reached the source address is banned (429 is returned, and `retryAfter` is the remaining seconds). Token endpoints are limited only by the source address's own ban, not by the global pause on password logins.
5. There are two permission levels: `read` may call only the read endpoints in the table below; `write` may also call the write endpoints. A read-only token calling a write endpoint gets 403 `read_only_token`.

There can be at most 20 tokens. The security log records each token's creation and deletion and the write operations it triggers; the token list shows the time and source address of the last use.

## Endpoints

Requests and responses are JSON. Success returns 200; failure returns 4xx/5xx and `{"error": "<code>"}`. When a response is rejected because of one particular input it may also carry `field` (the key in the request body, with dots for nesting) and `reason` (one of `required`, `type`, `format`, `range`, `too_long`, `too_short`, `exists`, `not_found`, `past`, `port_in_use`); the `error` codes are unaffected.

| Method and path | Permission | Purpose |
| --- | --- | --- |
| `GET /api/v1/status` | read | Host name, version, server identifier, kernel, resources (same as `monitor`, without the trends), total traffic this cycle, the status of this project's services, failed services |
| `GET /api/v1/monitor` | read | All data of the Resources page, including the 24-hour trends (12-segment and 24-segment averages) |
| `GET /api/v1/services` | read | All systemd services: `unit`, `load`, `active`, `sub`, `description`, `enabled` |
| `GET /api/v1/upgrade` | read | Whether an upgrade started through the API or the System page is running (`running`), the current version, the package type of this host (`variant`), the exit code of the last upgrade (`lastExit`, `null` when there is no record), the last 40 lines of the upgrade output |
| `POST /api/v1/services/restart` | write | Restart a running service of this project (`systemctl try-restart`; a stopped one stays stopped), request body `{"unit": "<name>.service"}`; only installed `vps-server*.service` and `frpc@*.service` in `/etc/systemd/system` are accepted, and anything else returns 403 `unit_not_allowed`; when restarting the console itself it returns immediately |
| `POST /api/v1/upgrade` | write | Upgrade in the background to the latest stable release, or to `{"version": "v7.2.0"}`; `variant` may be `online` or `offline`, defaulting to the type this host was installed with (`offline` when there is no record). Returns 409 `busy` when an upgrade or an installation is already running
 |
| `POST /api/v1/backup` | write | Make a manual configuration backup, returns `{"name": "<file name>"}` |

An upgrade works like the upgrade command in the panel: it verifies the release signature first, then runs the installer in the package, and the console restarts once. The upgrade downloads from GitHub; a host that cannot reach GitHub still needs to transfer files manually as described in the README's [Upgrade](README.md#upgrade).

## Examples

```bash
TOKEN=vpss_...
curl -sk -H "Authorization: Bearer $TOKEN" https://203.0.113.5:20000/api/v1/status
curl -sk -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"unit": "vps-server-proxy.service"}' https://203.0.113.5:20000/api/v1/services/restart
```

The console uses a self-signed certificate by default, and the commands above skip verification with `-k`. Scripts should use `--pinnedpubkey` instead, or switch to a valid certificate (an IP certificate or domain forwarding).
