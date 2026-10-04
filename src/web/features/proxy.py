"""Proxy pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class ProxyMixin:
    def page_proxy(self, lang, query_lang):
        """Show the verified, ID-based node inventory."""
        t = self.context.STRINGS[lang]
        installed = self.context.installed_modules(self.context.BASE_DIR)
        if not ({"proxy", "anytls"} & installed):
            return self.page_module_not_installed(lang, query_lang, t["proxy_heading"], t["proxy"], active="proxy")
        try:
            inventory = self.context.read_inventory(
                state_path=self.context.NODE_STATE_PATH,
                config_paths={"anytls": self.context.ANYTLS_CONFIG,
                              "proxy": self.context.PROXY_CONFIG})
            meter = self.context._read_json(self.context.NODE_METER_PATH) or {}
            meter_nodes = meter.get("ledger", {}).get("nodes", {})
        except (OSError, ValueError, TypeError, AttributeError):
            inventory = None
        if inventory is None:
            message = self.context.html.escape(t["node_state_unavailable"])
            return self.send_html(503, self.render_page(t["proxy_heading"],
                                  f'<div class="card"><h1>{self.context.html.escape(t["proxy_heading"])}</h1><p role="alert">{message}</p></div>',
                                  lang, active="proxy"), {"Cache-Control": "no-store"})
        return self.page_managed_nodes(lang, query_lang, inventory, meter_nodes)

    def page_managed_nodes(self, lang, query_lang, inventory, meter_nodes):
        """Render each installed inbound by stable ID, including duplicates."""
        t = self.context.STRINGS[lang]
        esc = self.context.html.escape
        session = self.get_cookie("session")
        host = (self.headers.get("Host") or "").split(":")[0]
        lan_host = self.context.clash_lan_host(host) if self.context.AUTH_ENABLED else None
        key = self.context.parse_qs(self.context.urlsplit(self.path).query).get("msg", [""])[0]
        notice = (f'<p class="{"error" if key == "node_settings_failed" else "notice"}">'
                  f'{esc(t[key])}</p>') if key in self.context.NODE_APPLY_MESSAGE_KEYS else ""
        cards = []
        running = {"anytls": bool(self.context.anytls_node() and self.context.anytls_node()["running"]),
                   "proxy": self.context.proxy_running()}
        addresses_available = self.context.address_entries(t)
        for node in sorted(inventory["nodes"], key=lambda item: item["number"]):
            protocol = node["protocol"]
            module = "anytls" if protocol == "anytls" else "proxy"
            identifier = node["id"]
            token = self.context.node_csrf_token(session, identifier)
            inbound = node["inbound"]
            sni = self.context._cert_common_name(inbound["tls"]["certificate_path"]) if protocol != "shadowsocks" else ""
            sni_fact = (f'<div class="node-fact"><dt>{esc(t["proxy_sni"])}</dt><dd>{esc(sni or "—")}</dd></div>'
                        if protocol != "shadowsocks" else
                        f'<div class="node-fact"><dt>{esc(t["proxy_sni"])}</dt><dd>{esc(t["node_not_applicable"])}</dd></div>')
            sni_input = (f'<label>{esc(t["proxy_sni"])}<input name="sni" value="{esc(sni, quote=True)}" required></label>'
                         if protocol != "shadowsocks" else "")
            addresses = "".join(f'<div class="node-address"><span>{esc(label)}</span><code>{esc(value)}</code></div>'
                                for label, value in addresses_available)
            cap = "" if node["cap_bytes"] is None else str(self.context.Decimal(node["cap_bytes"]) / 1073741824)
            upload_speed = "" if node["upload_limit_bps"] is None else str(self.context.Decimal(node["upload_limit_bps"]) / 1000000)
            download_speed = "" if node["download_limit_bps"] is None else str(self.context.Decimal(node["download_limit_bps"]) / 1000000)
            interval = self.context.reset_interval(node["reset_mode"])
            reset_choice = "none" if node["reset_mode"] == "none" else "once" if node["reset_mode"] == "once" else "repeat"
            reset_count, reset_unit = (interval[0], interval[1]) if interval else (1, "months")
            next_reset = node["next_reset_at"][:16] if node["reset_mode"] == "once" and node["next_reset_at"] else ""
            def radios(name, options, selected):
                return "".join(f'<label class="node-radio"><input type="radio" name="{name}" value="{value}"'
                               f'{" checked" if value == selected else ""}><span>{esc(t[key])}</span></label>'
                               for value, key in options)
            units = (("days", "node_days"), ("months", "node_months"), ("years", "node_years"))
            reset_modes = (("none", "node_reset_none"), ("repeat", "node_reset_repeat")) + \
                          ((("once", "node_reset_once"),) if reset_choice == "once" else ())
            is_active = node["enabled"] and running[module]
            status_key = "node_disabled" if not node["enabled"] else ("node_active" if is_active else "node_stopped")
            status_class = "is-open" if is_active else "is-closed"
            toggle_label = t["node_disable"] if node["enabled"] else t["node_enable"]
            cards.append(f'''
            <article class="proxy-node managed-node">
              <header class="proxy-node-header"><div><span class="proxy-node-protocol">#{node['number']} · {esc(protocol)}</span>
                <h2>{esc(node['name'])}</h2></div>
                <div class="node-header-controls"><span class="proxy-node-status {status_class}">{esc(t[status_key])}</span>
                  <form method="post" action="/proxy/node/toggle" class="node-toggle-form">
                    <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}">
                    <input type="hidden" name="enabled" value="{'no' if node['enabled'] else 'yes'}">
                    <button type="submit" role="switch" aria-checked="{'true' if node['enabled'] else 'false'}" aria-label="{esc(toggle_label, quote=True)}" title="{esc(toggle_label, quote=True)}" class="node-toggle" ><span aria-hidden="true"></span></button>
                  </form></div></header>
              <section class="node-connection"><details class="node-inline-edit" data-node-edit-id="{identifier}"><summary><span>{esc(t['node_manage'])}</span><span>{esc(t['node_cancel'])}</span></summary>
                <form method="post" action="/proxy/node/edit" autocomplete="off" class="node-inline-form">
                  <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}">
                  <div class="node-form-grid">
                    <label>{esc(t['node_name'])}<input name="name" maxlength="64" value="{esc(node['name'], quote=True)}" required></label>
                    <label>{esc(t['proxy_port'])}<input type="number" name="port" min="1" max="65535" data-node-edit-port placeholder="{esc(t['node_keep_port'], quote=True)}"></label>
                    <div class="node-form-field">{self.context.render_password_field(t, 'node-credential-' + identifier, t['node_credential'], 'credential', 'value="" data-node-edit-credential placeholder="' + esc(t['node_keep_credential'], quote=True) + '" autocomplete="new-password"')}</div>
                    {sni_input}
                  </div><button type="submit">{esc(t['node_save_settings'])}</button>
                </form>
              </details>
              <dl class="proxy-node-facts">
                <div class="node-fact"><dt>{esc(t['proxy_port'])}</dt><dd>{self.private_value_control(identifier, 'port', t)}</dd></div>
                {sni_fact}
                <div class="node-fact node-fact-secret"><dt>{esc(t['node_credential'])}</dt><dd class="secret">{self.private_value_control(identifier, 'credential', t, copy=True)}</dd></div>
              </dl></section>
              <div class="proxy-node-addresses">{addresses}</div>
              {self.node_metrics(node, meter_nodes, t)}
              {self.node_clash_share(node, lan_host, t)}
              <div class="node-secondary">
                <button type="button" class="node-action node-access-open" data-dialog-open="node-access-{identifier}">{esc(t['node_limit_manage'])}</button>
                <div class="node-destructive-actions"><button type="button" class="node-action node-action-danger" data-dialog-open="node-reset-{identifier}">{esc(t['node_random_reset'])}</button>
                <button type="button" class="node-action node-action-danger" data-dialog-open="node-delete-{identifier}">{esc(t['node_delete'])}</button></div>
              </div>
              <dialog class="node-access-dialog" id="node-access-{identifier}" aria-labelledby="node-access-title-{identifier}">
                  <form method="post" action="/proxy/node/limits">
                    <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}">
                    <h3 id="node-access-title-{identifier}">{esc(t['node_limit_manage'])}</h3>
                    <div class="node-form-grid">
                      <label>{esc(t['node_cap_gib'])}<input type="number" name="cap_gib" min="0.000001" max="100000000" step="any" value="{cap}" placeholder="{esc(t['node_unlimited'], quote=True)}"></label>
                      <label>{esc(t['node_upload_speed'])}<input type="number" name="upload_mbps" min="0.001" max="10000000" step="any" value="{upload_speed}" placeholder="{esc(t['node_unlimited'], quote=True)}"></label>
                      <label>{esc(t['node_download_speed'])}<input type="number" name="download_mbps" min="0.001" max="10000000" step="any" value="{download_speed}" placeholder="{esc(t['node_unlimited'], quote=True)}"></label>
                    </div>
                    <fieldset class="node-reset-cycle"><legend>{esc(t['node_cap_action'])}</legend>{radios('cap_action', (("throttle", "node_cap_slow"), ("block", "node_cap_block")), node['cap_action'])}</fieldset>
                    <fieldset class="node-reset-cycle"><legend>{esc(t['node_reset_schedule'])}</legend>{radios('reset_mode', reset_modes, reset_choice)}</fieldset>
                    <div class="node-duration"><label>{esc(t['node_reset_every'])}<input type="number" name="reset_count" min="1" max="9999" value="{reset_count}"></label>
                      <fieldset class="node-reset-cycle"><legend>{esc(t['node_reset_unit'])}</legend>{radios('reset_unit', units, reset_unit)}</fieldset></div>
                    {'<label>' + esc(t['node_reset_time_utc']) + '<input type="datetime-local" name="next_reset_at" value="' + next_reset + '"></label>' if reset_choice == 'once' else '<input type="hidden" name="next_reset_at" value="">'}
                    <fieldset class="node-reset-cycle"><legend>{esc(t['node_validity'])}</legend>{radios('expiry_mode', (("none", "node_validity_none"), ("set", "node_validity_set")), 'set' if node['expiry_count'] else 'none')}</fieldset>
                    <div class="node-duration"><label>{esc(t['node_validity_length'])}<input type="number" name="expiry_count" min="1" max="9999" value="{node['expiry_count'] or 1}"></label>
                      <fieldset class="node-reset-cycle"><legend>{esc(t['node_validity_unit'])}</legend>{radios('expiry_unit', units, node['expiry_unit'] or 'months')}</fieldset></div>
                    <div class="node-dialog-actions"><button type="button" class="node-dialog-cancel" data-dialog-close>{esc(t['node_cancel'])}</button>
                    <button type="submit">{esc(t['node_save_limits'])}</button></div>
                  </form>
              </dialog>
              <dialog class="node-confirm-dialog" id="node-reset-{identifier}" aria-labelledby="node-reset-title-{identifier}">
                <form method="post" action="/proxy/node/reset">
                  <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}"><input type="hidden" name="confirm" value="yes">
                  <h3 id="node-reset-title-{identifier}">{esc(t['node_random_reset'])}</h3>
                  <p>{esc(t['node_random_confirm'])}</p>
                  <div class="node-dialog-actions"><button type="button" class="node-dialog-cancel" data-dialog-close>{esc(t['node_cancel'])}</button><button type="submit" class="danger">{esc(t['node_random_reset'])}</button></div>
                </form>
              </dialog>
              <dialog class="node-confirm-dialog" id="node-delete-{identifier}" aria-labelledby="node-delete-title-{identifier}">
                <form method="post" action="/proxy/node/delete">
                  <input type="hidden" name="id" value="{identifier}"><input type="hidden" name="csrf" value="{token}"><input type="hidden" name="confirm" value="yes">
                  <h3 id="node-delete-title-{identifier}">{esc(t['node_delete'])}</h3>
                  <p>{esc(t['node_delete_confirm'])}</p>
                  <div class="node-dialog-actions"><button type="button" class="node-dialog-cancel" data-dialog-close>{esc(t['node_cancel'])}</button><button type="submit" class="danger">{esc(t['node_delete'])}</button></div>
                </form>
              </dialog>
            </article>''')
        protocols = (["anytls"] if self.context.ANYTLS_CONFIG.is_file() else []) + \
                    (["vmess", "vless", "trojan", "shadowsocks"] if self.context.PROXY_CONFIG.is_file() else [])
        protocol_choices = "".join(f'<label class="node-radio"><input type="radio" name="protocol" value="{value}"'
                                   f'{" checked" if index == 0 else ""}><span>{esc(value)}</span></label>'
                                   for index, value in enumerate(protocols))
        create = (f'''<details class="node-create"><summary><span>{esc(t['node_create'])}</span><span>{esc(t['node_cancel'])}</span></summary>
          <form method="post" action="/proxy/node/create" data-node-create
                data-credential-password="{esc(t['node_credential_password_hint'], quote=True)}"
                data-credential-uuid="{esc(t['node_credential_uuid_hint'], quote=True)}"
                data-credential-ss="{esc(t['node_credential_ss_hint'], quote=True)}">
            <input type="hidden" name="csrf" value="{self.context.node_csrf_token(session, 'create')}">
            <fieldset class="node-reset-cycle"><legend>{esc(t['node_protocol'])}</legend>{protocol_choices}</fieldset>
            <div class="node-form-grid">
              <label>{esc(t['node_name'])}<input name="name" maxlength="64" required></label>
              <label>{esc(t['proxy_port'])}<input type="number" name="port" min="1" max="65535" placeholder="{esc(t['node_random_port'], quote=True)}"></label>
              <div class="node-form-field">{self.context.render_password_field(t, 'node-create-credential', t['node_credential'], 'credential', 'value="" placeholder="' + esc(t['node_credential_random'], quote=True) + '" autocomplete="new-password"', '<small class="node-field-hint" data-credential-hint>' + esc(t['node_credential_password_hint']) + '</small>')}</div>
              <label data-sni-field>{esc(t['proxy_sni'])}<input name="sni" value="www.bing.com" placeholder="{esc(t['node_sni_optional'], quote=True)}"></label>
            </div><button type="submit">{esc(t['node_create'])}</button>
          </form></details>''' if protocols else "")
        count = len(cards)
        active_count = sum(bool(n["enabled"] and running["anytls" if n["protocol"] == "anytls" else "proxy"])
                           for n in inventory["nodes"])
        qr_scripts = ('<script src="/static/qrcode.js"></script><script src="/static/qrcode-utf8.js"></script>'
                      '<script src="/static/qrcode-render.js"></script>') if lan_host and cards else ''
        empty_state = ''.join(cards) if cards else f'<p class="muted">{esc(t["node_empty"])}</p>'
        body = f'''<div class="proxy-workspace"><header class="proxy-overview">
          <div><p class="proxy-eyebrow">{esc(t['node_overview'])}</p><h1>{esc(t['proxy_heading'])}</h1></div>
          <div class="proxy-summary" aria-label="{esc(t['node_summary'])}">
            <div><strong>{count}</strong><span>{esc(t['node_total'])}</span></div>
            <div><strong>{active_count}</strong><span>{esc(t['node_active'])}</span></div></div></header>
          {notice}{create}<div class="proxy-node-grid managed-node-grid">{empty_state}</div></div>
          <script src="/static/copy.js"></script>
          <script src="/static/private-values.js"></script>
          <script src="/static/node-controls.js"></script>
          {qr_scripts}'''
        return self.send_html(200, self.render_page(t['proxy_heading'], body, lang, active="proxy"),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def private_value_control(self, identifier, field, t, copy=False, endpoint='/proxy/private-value'):
        esc = self.context.html.escape
        copy = copy or field != 'credential'
        return (f'<span class="private-value" data-private-id="{esc(identifier, quote=True)}" '
                f'data-private-url="{esc(endpoint, quote=True)}" '
                f'data-private-field="{field}" data-show="{esc(t["login_show_password"], quote=True)}" '
                f'data-hide="{esc(t["login_hide_password"], quote=True)}" '
                f'data-error="{esc(t["private_value_failed"], quote=True)}">'
                f'<code data-private-text>••••••</code>'
                f'<button type="button" class="private-reveal" aria-pressed="false">{esc(t["login_show_password"])}</button>'
                + (f'<button type="button" class="private-copy" data-copied="{esc(t["copied"], quote=True)}" data-error="{esc(t["private_copy_failed"], quote=True)}">{esc(t["copy"])}</button>' if copy else '')
                + '</span>')

    def node_clash_share(self, node, lan_host, t):
        if node is None or lan_host is None:
            return ""
        return f'''<div class="node-share" data-share-id="{self.context.html.escape(node['id'], quote=True)}">
          <button type="button" class="private-share-copy" data-copied="{self.context.html.escape(t['copied'], quote=True)}" data-error="{self.context.html.escape(t['private_copy_failed'], quote=True)}"
            aria-label="{self.context.html.escape(t['node_clash_copy_label'], quote=True)}">{self.context.html.escape(t['copy'])}</button>
          <button type="button" class="node-import private-share-import" data-error="{self.context.html.escape(t['private_value_failed'], quote=True)}">{self.context.html.escape(t['node_clash_import'])}</button>
          <details class="qr-details"><summary>{self.context.html.escape(t['node_clash_qr'])}</summary>
            <div class="qr" data-private-qr data-error="{self.context.html.escape(t['private_value_failed'], quote=True)}"></div>
          </details>
        </div>'''

    def handle_proxy_private_value(self, parsed):
        query = self.context.parse_qs(parsed.query)
        identifier = query.get('id', [''])[0]
        field = query.get('field', [''])[0]
        if len(query.get('id', [])) != 1 or len(query.get('field', [])) != 1 or field not in ('port', 'credential', 'share', 'cmd-speed', 'cmd-single', 'cmd-multi', 'public-port', 'target-port', 'account'):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        try:
            if identifier == 'lucky' and field in ('port', 'account', 'credential'):
                data = self.context.lucky_admin()
                if data is None:
                    raise ValueError('no Lucky admin')
                value = str(data['AdminWebListenPort'] if field == 'port' else
                            data.get('AdminAccount', '') if field == 'account' else
                            data.get('AdminPassword', ''))
            elif identifier == 'iperf' and field in ('port', 'cmd-speed', 'cmd-single', 'cmd-multi'):
                host = (self.headers.get('Host') or '').split(':')[0] or '<server-ip>'
                suffix = {'cmd-speed': '', 'cmd-single': ' -P 1', 'cmd-multi': ' -P 4'}
                value = (str(self.context.IPERF_WINDOW.port) if field == 'port' else
                         f'iperf3 -c {host} -p {self.context.IPERF_WINDOW.port}{suffix[field]}')
            elif identifier.startswith('forward-') and field in ('public-port', 'target-port'):
                rule = next(item for item in self.context.PORTFWD.list_rules() if item['id'] == identifier[8:])
                value = str(rule['public_port' if field == 'public-port' else 'target_port'])
            elif identifier == 'frps' and field in ('port', 'credential'):
                node = self.context.frps_node()
                if node is None:
                    raise ValueError('no frps node')
                value = str(node['port'] if field == 'port' else node['token'])
            elif identifier.startswith('legacy-') and field in ('port', 'credential'):
                protocol = identifier.removeprefix('legacy-')
                node = (self.context.anytls_node() if protocol == 'anytls' else
                        next(item for item in self.context.proxy_nodes() if item['type'] == protocol))
                if node is None:
                    raise ValueError('no legacy node')
                value = str(node['port'] if field == 'port' else
                            node['password'] if protocol == 'anytls' else node['secret'])
            else:
                value = self.managed_private_value(identifier, field)
        except (OSError, ValueError, TypeError, KeyError, StopIteration):
            return self.send_html(404, 'Not found', {'Cache-Control': 'no-store'})
        data = self.context.json.dumps({'value': value}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def managed_private_value(self, identifier, field):
        try:
            inventory = self.context.read_inventory(state_path=self.context.NODE_STATE_PATH,
                                       config_paths={'anytls': self.context.ANYTLS_CONFIG, 'proxy': self.context.PROXY_CONFIG})
            node = next(item for item in inventory['nodes'] if item['id'] == identifier)
            if field == 'port':
                value = str(node['port'])
            elif field == 'credential':
                inbound = node['inbound']
                protocol = node['protocol']
                value = (inbound['password'] if protocol == 'shadowsocks' else
                         inbound['users'][0]['uuid' if protocol in ('vmess', 'vless') else 'password'])
            elif field == 'share':
                host = self.context.clash_lan_host((self.headers.get('Host') or '').split(':')[0])
                if host is None:
                    raise ValueError('no LAN address')
                scheme = 'https' if self.context.CONSOLE_TLS else 'http'
                value = (f'{scheme}://{host}:{self.context.CONSOLE_PORT}/clash/sub/'
                         f'{identifier}/{self.context.clash_share_token(node)}')
            else:
                raise ValueError('unsupported node value')
            return value
        except (OSError, ValueError, TypeError, KeyError, StopIteration):
            raise ValueError('no managed node')

    def handle_clash_subscription(self, path):
        parts = path.split("/")
        peer = self.context.ipaddress.ip_address(self.client_address[0])
        if (not self.context.AUTH_ENABLED or len(parts) != 5 or parts[:3] != ["", "clash", "sub"] or
                not self.context.re.fullmatch(r"[0-9a-f]{64}", parts[4]) or
                not (self.context.is_lan_address(str(peer)) or peer.is_loopback)):
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        try:
            inventory = self.context.read_inventory(state_path=self.context.NODE_STATE_PATH,
                                       config_paths={"anytls": self.context.ANYTLS_CONFIG,
                                                     "proxy": self.context.PROXY_CONFIG})
            matches = [node for node in inventory["nodes"] if node["id"] == parts[3]]
            if not matches and parts[3] in self.context.NODE_PROTOCOLS:
                # Previously issued links named the protocol. Preserve the
                # oldest matching node until its token changes or it is removed.
                matches = sorted((node for node in inventory["nodes"]
                                  if node["protocol"] == parts[3]), key=lambda node: node["number"])
            node = matches[0]
            if not self.context.hmac.compare_digest(parts[4], self.context.clash_share_token(node)):
                raise ValueError("stale link")
            host = self.context.clash_lan_host("")
            if host is None:
                raise ValueError("no LAN address")
            data = self.context.clash_profile(node, host).encode("utf-8")
        except (OSError, ValueError, TypeError, KeyError, StopIteration, IndexError):
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        self.send_response(200)
        self.send_header("Content-Type", "text/yaml; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def node_metrics(self, node, meter_nodes, t):
        if node is None:
            return ""
        def size(value):
            return f"{value / 1048576:.1f} MiB"
        used = node["upload_bytes"] + node["download_bytes"]
        cap = node["cap_bytes"]
        try:
            suspect = bool(meter_nodes[node["id"]]["suspect"])
        except (KeyError, TypeError):
            suspect = True
        remaining = ((self.context.datetime.fromisoformat(node["expires_at"]) - self.context.datetime.now(self.context.timezone.utc)).total_seconds()
                     if node["expires_at"] else None)
        expired = remaining is not None and remaining <= 0
        capped = cap is not None and used >= cap
        blocked = expired or (capped and node["cap_action"] == "block")
        limited = suspect or (capped and not blocked)
        limit = t["node_blocked"] if blocked else t["node_limited"] if limited else t["node_normal"]
        cap_label = f"{cap / 1073741824:g} GiB" if cap is not None else t["node_unlimited"]
        reset_label = node["next_reset_at"][:16].replace("T", " ") + " UTC" if node["next_reset_at"] else t["node_no_reset"]
        speed = lambda direction: (f'{node[direction + "_limit_bps"] / 1000000:g} Mbps' if node[direction + "_limit_bps"] is not None else t["node_unlimited"])
        validity_label = (t["node_validity_expired"] if expired else
                          t["node_remaining_hours"].format(count=max(1, int((remaining + 3599) // 3600)))
                          if remaining < 86400 else
                          t["node_remaining_days"].format(count=max(1, int((remaining + 86399) // 86400)))) if remaining is not None else ""
        validity = (f'<div class="node-validity-stat"><small>{self.context.html.escape(t["node_validity"])}</small>'
                    f'<strong>{self.context.html.escape(validity_label)}</strong></div>' if remaining is not None else "")
        return f'''<section class="node-usage" aria-label="{self.context.html.escape(t['node_traffic'])}">
          <div class="node-usage-heading"><h3>{self.context.html.escape(t['node_traffic'])}</h3>
            <span class="node-limit {'is-limited' if limited or blocked else ''}">{self.context.html.escape(limit)}</span></div>
          <div class="node-stats">
            <div><small>{self.context.html.escape(t['node_upload'])}</small><strong>{size(node['upload_bytes'])}</strong><small>{self.context.html.escape(speed('upload'))}</small></div>
            <div><small>{self.context.html.escape(t['node_download'])}</small><strong>{size(node['download_bytes'])}</strong><small>{self.context.html.escape(speed('download'))}</small></div>
            <div><small>{self.context.html.escape(t['node_cap'])}</small><strong>{self.context.html.escape(cap_label)}</strong></div>
            <div><small>{self.context.html.escape(t['node_next_reset'])}</small><strong>{self.context.html.escape(reset_label)}</strong></div>
            {validity}
          </div>
        </section>'''

    def handle_node_control(self, action):
        """Validate the browser request, then identify the node only on server."""
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = 0
        if (not 0 < length <= 4096 or
                self.headers.get("Content-Type", "").split(";", 1)[0].strip() !=
                "application/x-www-form-urlencoded"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        try:
            form = self.context.parse_qs(self.rfile.read(length).decode("utf-8"),
                            strict_parsing=True, keep_blank_values=True)
        except (UnicodeError, ValueError):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if any(len(values) != 1 for values in form.values()):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        session = self.get_cookie("session")
        identifier = form.get("id", [""])[0]
        protocol = form.get("protocol", [""])[0]
        csrf_subject = "create" if action == "create" else identifier
        if not self.context.hmac.compare_digest(form.get("csrf", [""])[0],
                                   self.context.node_csrf_token(session, csrf_subject)):
            return self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
        expected = {
            "create": {"protocol", "csrf", "name", "port", "sni", "credential"},
            "edit": {"id", "csrf", "name", "port", "credential"},
            "limits": {"id", "csrf", "cap_gib", "upload_mbps", "download_mbps",
                       "cap_action", "expiry_mode", "expiry_count", "expiry_unit",
                       "reset_mode", "reset_count", "reset_unit", "next_reset_at"},
            "reset": {"id", "csrf", "confirm"},
            "delete": {"id", "csrf", "confirm"},
            "toggle": {"id", "csrf", "enabled"},
        }.get(action)
        if action == "edit":
            try:
                inventory = self.context.read_inventory(state_path=self.context.NODE_STATE_PATH,
                                           config_paths={"anytls": self.context.ANYTLS_CONFIG, "proxy": self.context.PROXY_CONFIG})
                node = next(node for node in inventory["nodes"] if node["id"] == identifier)
            except (OSError, ValueError, TypeError, StopIteration):
                return self.redirect("/proxy?msg=node_settings_failed")
            if node["protocol"] != "shadowsocks":
                expected = expected | {"sni"}
        if set(form) != expected:
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if action in ("reset", "delete") and form["confirm"][0] != "yes":
            return self.redirect("/proxy?msg=node_settings_failed")
        if action == "toggle" and form["enabled"][0] not in ("yes", "no"):
            return self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
        if action == "create":
            if protocol not in self.context.NODE_PROTOCOLS:
                return self.redirect("/proxy?msg=node_settings_failed")
            try:
                port = int(form["port"][0]) if form["port"][0] else None
                request = {"action": "create", "protocol": protocol,
                           "name": form["name"][0], "port": port}
                if form["credential"][0]:
                    request["credential"] = form["credential"][0]
                if protocol != "shadowsocks":
                    request["sni"] = form["sni"][0].strip() or "www.bing.com"
            except ValueError:
                return self.redirect("/proxy?msg=node_settings_failed")
        else:
            request = {"action": "edit" if action == "limits" else action, "id": identifier}
        if action == "toggle":
            request["enabled"] = form["enabled"][0] == "yes"
        if action == "edit":
            try:
                request["name"] = form["name"][0]
                request["port"] = int(form["port"][0]) if form["port"][0] else node["port"]
                credential = form["credential"][0]
                if credential:
                    request["credential"] = credential
                if node["protocol"] != "shadowsocks":
                    sni = form["sni"][0]
                    current = self.context._cert_common_name(node["inbound"]["tls"]["certificate_path"])
                    if sni != current:
                        request["sni"] = sni
            except (ValueError, KeyError):
                return self.redirect("/proxy?msg=node_settings_failed")
        elif action == "limits":
            try:
                cap = form["cap_gib"][0].strip()
                if cap:
                    amount = self.context.Decimal(cap)
                    if not amount.is_finite() or not 0 < amount <= 100000000:
                        raise ValueError("invalid cap")
                    request["cap_bytes"] = int(amount * 1073741824)
                else:
                    request["cap_bytes"] = None
                def speed(value):
                    if not value.strip():
                        return None
                    amount = self.context.Decimal(value)
                    if not amount.is_finite() or not self.context.Decimal("0.001") <= amount <= 10000000:
                        raise ValueError("invalid speed")
                    result = int(amount * 1000000)
                    if result < 1000:
                        raise ValueError("invalid speed")
                    return result
                request["upload_limit_bps"] = speed(form["upload_mbps"][0])
                request["download_limit_bps"] = speed(form["download_mbps"][0])
                if form["cap_action"][0] not in ("throttle", "block"):
                    raise ValueError("invalid cap action")
                request["cap_action"] = form["cap_action"][0]
                now = self.context.datetime.now(self.context.timezone.utc)
                def duration(count_value, unit_value):
                    count = int(count_value)
                    if not 1 <= count <= 9999 or unit_value not in ("days", "months", "years"):
                        raise ValueError("invalid duration")
                    anchor = "-" if unit_value == "days" else str(now.day) if unit_value == "months" else now.strftime("%m-%d")
                    mode = f"every:{count}:{unit_value}:{anchor}"
                    return count, unit_value, mode, self.context.advance_reset_interval(now, mode).isoformat()
                def date_value(value):
                    if not value:
                        return None
                    if not self.context.re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
                        raise ValueError("invalid date")
                    return self.context.datetime.fromisoformat(value).replace(tzinfo=self.context.timezone.utc).isoformat()
                expiry_mode = form["expiry_mode"][0]
                current = self.context.read_inventory(state_path=self.context.NODE_STATE_PATH,
                                         config_paths={"anytls": self.context.ANYTLS_CONFIG, "proxy": self.context.PROXY_CONFIG})
                existing = next(node for node in current["nodes"] if node["id"] == identifier)
                if expiry_mode == "set":
                    count, unit, _, due = duration(form["expiry_count"][0], form["expiry_unit"][0])
                    if (existing["expiry_count"], existing["expiry_unit"]) != (count, unit):
                        request.update(expiry_count=count, expiry_unit=unit, expires_at=due)
                elif expiry_mode == "none":
                    if existing["expiry_count"] is not None:
                        request.update(expiry_count=None, expiry_unit=None, expires_at=None)
                else:
                    raise ValueError("invalid expiry mode")
                mode = form["reset_mode"][0]
                if mode not in ("none", "repeat", "once"):
                    raise ValueError("invalid reset mode")
                if mode == "repeat":
                    _, _, request["reset_mode"], request["next_reset_at"] = duration(
                        form["reset_count"][0], form["reset_unit"][0])
                elif mode == "once":
                    request["reset_mode"] = "once"
                    request["next_reset_at"] = date_value(form["next_reset_at"][0])
                    if request["next_reset_at"] is None or \
                            self.context.datetime.fromisoformat(request["next_reset_at"]) <= now:
                        raise ValueError("reset must be future")
                else:
                    request["reset_mode"] = "none"
                    request["next_reset_at"] = None
            except (ValueError, self.context.InvalidOperation, OverflowError, KeyError, self.context.InvalidInventory,
                    TypeError, StopIteration):
                return self.redirect("/proxy?msg=node_settings_failed")
        success = self.context.node_control_apply(request)
        key = ({"reset": "node_reset_done", "create": "node_created", "delete": "node_deleted"}
               .get(action, "node_settings_done")) if success else "node_settings_failed"
        return self.redirect(f"/proxy?msg={key}", {"Cache-Control": "no-store"})

    def route_proxy(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/anytls":
            self.redirect("/proxy")
        elif method == "GET" and path == "/proxy":
            if not self.context.AUTH_ENABLED:
                self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
            else:
                self.page_proxy(lang, query_lang)
        elif method == "GET" and path == "/proxy/private-value":
            if not self.context.AUTH_ENABLED:
                self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
            else:
                self.handle_proxy_private_value(parsed)
        elif method == "POST" and path in ("/proxy/node/edit", "/proxy/node/limits",
                                                "/proxy/node/reset", "/proxy/node/create",
                                                "/proxy/node/delete", "/proxy/node/toggle"):
            if not self.context.AUTH_ENABLED:
                self.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
            else:
                self.handle_node_control(path.rsplit("/", 1)[-1])
        else:
            return False
        return True

    def route_proxy_public(self, method, path):
        if method == "GET" and path.startswith("/clash/sub/"):
            self.handle_clash_subscription(path)
            return True
        return False
