"""Frp pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class FrpMixin:
    def page_frps(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        if self.context.STATE_FILE.is_file() and "frps" not in self.context.installed_modules(self.context.BASE_DIR):
            return self.page_module_not_installed(lang, query_lang, "FRPS", "FRPS")
        node = self.context.frps_node()
        esc = self.context.html.escape
        if node is None:
            server = (f'<p class="muted">{esc(t["frps_not_installed"])}</p>'
                      f'<a class="button-link frp-install-link" href="/settings/modules">'
                      f'{esc(t["module_install"] + " FRPS")}</a>')
        else:
            running = self.context._run_quiet(['systemctl', 'is-active', '--quiet', self.context.FRPS_SERVICE])
            status = t['node_active'] if running else t['frp_not_running']
            addresses = self.context.address_entries(t)
            address_list = (f'<div class="frp-addresses"><h3>{esc(t["frp_addresses"])}</h3><ul>' +
                            ''.join(f'<li><span>{esc(label)}</span>'
                                    f'{self.private_value_control("interface-" + str(index), "address", t)}</li>'
                                    for index, (label, _) in enumerate(addresses)) + '</ul></div>') if addresses else ''
            toggle_action = 'disable' if running else 'enable'
            toggle = (f'<form method="post" action="/frp/server/toggle" class="node-toggle-form">'
                      f'<input type="hidden" name="action" value="{toggle_action}">'
                      f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "frp:server:" + toggle_action)}">'
                      f'<button type="submit" class="node-toggle" role="switch" aria-checked="{str(running).lower()}" '
                      f'aria-label="{esc(t["frp_stop_server"] if running else t["frp_start_server"], quote=True)}"><span></span></button></form>')
            inline_token = self.context.render_password_field(t, 'frps-inline-token', t['frps_token'], 'token',
                                                 f'maxlength="128" autocomplete="new-password" data-frps-edit-field="credential" placeholder="{esc(t["frp_token_keep"], quote=True)}"')
            edit = (f'<details class="node-inline-edit frp-inline-edit" {"open" if self.context.parse_qs(self.context.urlsplit(self.path).query).get("edit") == ["server"] else ""}><summary><span>{esc(t["frp_edit_server"])}</span>'
                    f'<span>{esc(t["node_cancel"])}</span></summary><form method="post" action="/frp/server/save" autocomplete="off">'
                    f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "frp:server")}">'
                    f'<label>{esc(t["proxy_port"])}<input type="number" name="port" min="1" max="65535" data-frps-edit-field="port" '
                    f'placeholder="{esc(t["frp_port_keep"], quote=True)}"></label>'
                    f'{inline_token}'
                    f'<button type="submit">{esc(t["frp_save"])}</button>'
                    f'</form></details>')
            edit_entry = edit
            server = (f'<div class="frp-status-line"><span class="proxy-node-status {"is-open" if running else "is-closed"}">{esc(status)}</span>{toggle}</div>'
                      f'{edit_entry}'
                      f'<dl class="frp-facts">'
                      f'<div><dt>{esc(t["frps_bind"])}</dt><dd><code>{esc(node["address"])}</code></dd></div>'
                      f'<div><dt>{esc(t["proxy_port"])}</dt><dd>{self.private_value_control("frps", "port", t, endpoint="/frp/server/value")}</dd></div>'
                      f'<div><dt>{esc(t["frps_token"])}</dt><dd>{self.private_value_control("frps", "credential", t, copy=True, endpoint="/frp/server/value")}</dd></div></dl>'
                      f'{address_list}')
        message = self.context.parse_qs(self.context.urlsplit(self.path).query).get("msg", [""])[0]
        feedback = (f'<p class="{"notice" if message == "done" else "error"}" role="status">'
                    f'{esc(t["frp_saved"] if message == "done" else t["frp_save_failed"])}</p>') if message in ("done", "failed") else ""
        body = (f'<div class="frp-workspace">{feedback}'
                f'<section class="card frp-card"><div class="frp-card-head">{self.context.ui_icon("server")}'
                f'<h1>{esc(t["frps_heading"])}</h1></div>{server}</section></div>'
                '<script src="/static/copy.js"></script><script src="/static/private-values.js"></script><script src="/static/frp-editor.js" defer></script>')
        return self.send_html(200, self.render_page(t["frps_heading"], body, lang),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_frpc(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        if self.context.STATE_FILE.is_file() and "frpc" not in self.context.installed_modules(self.context.BASE_DIR):
            return self.page_module_not_installed(lang, query_lang, "FRPC", "FRPC")
        esc = self.context.html.escape
        clients = []
        for name in self.context.frpc_names():
            try:
                item = self.context.frpc_summary(name)
            except (OSError, ValueError):
                continue
            connected = self.context.frpc_connected(name, item['server'], item['port'])
            running_client = self.context._run_quiet(['systemctl', 'is-active', '--quiet', self.context.frpc_unit(name)])
            toggle_action = 'disable' if running_client else 'enable'
            state = t['frp_connected'] if connected else t['frp_disconnected']
            try:
                proxies = (self.context.frpc_structured(name) or {}).get('proxies', [])
            except (OSError, ValueError, KeyError, TypeError):
                proxies = []
            forwarding = ''.join(
                f'<li><strong>{esc(proxy["name"])}</strong><span>{esc(t["frp_forwarding"].format(remote=proxy["remotePort"], local=proxy["localIP"], port=proxy["localPort"]))}</span></li>'
                for proxy in proxies)
            forwarding = f'<ul class="frp-forwarding">{forwarding}</ul>' if forwarding else f'<span class="muted small">{item["proxies"]} {esc(t["frp_proxies"])}</span>'
            clients.append(f'<article class="frp-target-card"><div class="frp-target-head">'
                           f'<strong class="frp-target-name">{esc(name)}</strong>'
                           f'<form method="post" action="/frp/client/card-toggle" class="node-toggle-form">'
                           f'<input type="hidden" name="name" value="{esc(name, quote=True)}">'
                           f'<input type="hidden" name="action" value="{toggle_action}">'
                           f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "frp:toggle:" + name + ":" + toggle_action)}">'
                           f'<button type="submit" class="node-toggle" role="switch" aria-checked="{str(running_client).lower()}" '
                           f'aria-label="{esc(t["frp_stop_client"] if running_client else t["frp_start_client"], quote=True)}"><span aria-hidden="true"></span></button></form>'
                           f'<div class="frp-target-actions"><span class="proxy-node-status {"is-open" if connected else "is-closed"}" '
                           f'data-frpc-state aria-live="polite">{esc(state)}</span>'
                           f'<button type="button" class="frp-test-connection" data-name="{esc(name, quote=True)}" '
                           f'data-csrf="{self.context.access_csrf_token(self.get_cookie("session"), "frp:test:" + name)}" '
                           f'data-testing="{esc(t["frp_testing"], quote=True)}" '
                           f'data-connected="{esc(t["frp_connected"], quote=True)}" '
                           f'data-disconnected="{esc(t["frp_disconnected"], quote=True)}" '
                           f'data-failed="{esc(t["frp_test_failed"], quote=True)}">'
                           f'{esc(t["frp_test_connection"])}</button>'
                           f'<a class="button-link frp-card-edit" href="/frp/client/edit?name={self.context.quote(name)}">{esc(t["frp_edit_client_button"])}</a></div></div>'
                           f'<div class="frp-target-meta">{self.private_value_control(name, "server", t, endpoint="/frp/client/value")}</div>'
                           f'<div class="frp-target-foot">{forwarding}'
                           f'<button type="button" class="node-action node-action-danger frp-client-delete-open" '
                           f'data-dialog-open="frp-delete-{esc(name, quote=True)}">{esc(t["frp_delete_client"])}</button></div>'
                           f'<dialog class="node-confirm-dialog" id="frp-delete-{esc(name, quote=True)}" '
                           f'aria-labelledby="frp-delete-title-{esc(name, quote=True)}"><form method="post" action="/frp/client/delete">'
                           f'<h3 id="frp-delete-title-{esc(name, quote=True)}">{esc(t["frp_delete_client"])}</h3>'
                           f'<p>{esc(t["frp_delete_client_confirm"].format(name=name))}</p>'
                           f'<input type="hidden" name="name" value="{esc(name, quote=True)}">'
                           f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "frp:delete:" + name)}">'
                           f'<div class="node-dialog-actions"><button type="button" data-dialog-close>{esc(t["node_cancel"])}</button>'
                           f'<button type="submit" class="danger">{esc(t["frp_delete_client"])}</button></div>'
                           f'</form></dialog></article>')
        client_list = ''.join(clients) if clients else f'<p class="muted">{esc(t["frp_no_clients"])}</p>'
        client_installed = "frpc" in self.context.installed_modules(self.context.BASE_DIR)
        availability = '' if client_installed else f'<p class="error">{esc(t["frp_client_binary_missing"])}</p>'
        message = self.context.parse_qs(self.context.urlsplit(self.path).query).get('msg', [''])[0]
        feedback = (f'<p class="{"notice" if message == "done" else "error"}" role="status">'
                    f'{esc(t["frp_saved"] if message == "done" else t["frp_save_failed"])}</p>') if message in ('done', 'failed') else ''
        body = (f'<div class="frp-workspace">{feedback}'
                f'<section class="card frp-card"><div class="frp-card-head">{self.context.ui_icon("network")}'
                f'<h1>{esc(t["frp_client_heading"])}</h1></div>{availability}'
                f'<h2 class="frp-instances-heading">{esc(t["frp_instances"])}</h2><div class="frp-client-grid">{client_list}</div>'
                f'<p><a class="button-link frp-install-link" href="{"/frp/client/edit" if client_installed else "/settings/modules"}">'
                f'{esc(t["frp_new_client"] if client_installed else t["module_install"] + " FRPC")}</a></p>'
                '</section></div>'
                '<script src="/static/copy.js"></script><script src="/static/frp-editor.js" defer></script><script src="/static/private-values.js"></script>')
        return self.send_html(200, self.render_page(t["frp_client_heading"], body, lang),
                              {**self.maybe_lang_cookie(query_lang), "Cache-Control": "no-store"})

    def page_frps_edit(self, lang):
        return self.redirect('/frps?edit=server', {'Cache-Control': 'no-store'})

    def page_frpc_edit(self, lang, parsed):
        t, esc = self.context.STRINGS[lang], self.context.html.escape
        name = self.context.parse_qs(parsed.query).get('name', [''])[0]
        if not name and "frpc" not in self.context.installed_modules(self.context.BASE_DIR):
            return self.redirect('/settings/modules', {'Cache-Control': 'no-store'})
        if name:
            try:
                if not self.context.frpc_path(name).is_file() or self.context.frpc_path(name).is_symlink():
                    raise ValueError
            except (OSError, ValueError):
                return self.send_html(404, 'FRPC instance missing', {'Cache-Control': 'no-store'})
        structured = None
        if name:
            try:
                structured = self.context.frpc_structured(name)
            except (OSError, ValueError, KeyError, TypeError):
                pass
        rename = (f'<details class="node-inline-edit frp-rename"><summary><span>{esc(t["frp_rename_client"])}</span>'
                  f'<span>{esc(t["node_cancel"])}</span></summary><form method="post" action="/frp/client/rename">'
                  f'<input type="hidden" name="name" value="{esc(name, quote=True)}">'
                  f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "frp:rename:" + name)}">'
                  f'<label>{esc(t["frp_instance_name"])}<input name="newName" '
                  f'maxlength="32" value="{esc(name, quote=True)}" required></label>'
                  f'<button type="submit">{esc(t["frp_save"])}</button></form></details>') if name else ''
        message = self.context.parse_qs(parsed.query).get('msg', [''])[0]
        feedback = (f'<p class="{"notice" if message == "done" else "error"}" role="status">'
                    f'{esc(t["frp_saved"] if message == "done" else t["frp_save_failed"])}</p>') if message in ('done', 'failed') else ''
        editor = (self.frpc_structured_editor(lang, name, structured) if structured else
                  self.frpc_create_editor(lang) if not name else
                  f'<p class="error">{esc(t["frp_unsupported_config"])}</p>')
        body = (f'<div class="card wide frp-edit"><h1>{esc(name if name else t["frp_new_client"])}</h1>'
                f'{rename}{feedback}<div class="frp-structured">{editor}</div></div>')
        if name:
            body += '<script src="/static/copy.js"></script><script src="/static/private-values.js"></script><script src="/static/frp-editor.js" defer></script>'
        return self.send_html(200, self.render_page(name if name else t['frp_new_client'], body, lang, back_href='/frpc'),
                              {'Cache-Control': 'no-store'})

    def frpc_structured_editor(self, lang, name, config):
        t, esc = self.context.STRINGS[lang], self.context.html.escape
        def reveal(field, masked, label):
            return self.private_value_control(name, field, t, endpoint='/frp/client/value')
        server_token_field = self.context.render_password_field(t, 'frpc-server-token', t['frps_token'], 'token',
                                                   f'maxlength="128" autocomplete="new-password" data-load-token="{esc(name, quote=True)}"')
        base = (f'<input type="hidden" name="name" value="{esc(name, quote=True)}">'
                f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "frp:structured:" + name)}">')
        server = (f'<section class="frp-edit-section"><h2>{esc(t["frp_server_settings"])}</h2>'
                  f'<details class="node-inline-edit"><summary><span>{esc(t["frp_edit_target"])}</span><span>{esc(t["node_cancel"])}</span></summary>'
                  f'<form method="post" action="/frp/client/structured" autocomplete="off">{base}'
                  f'<input type="hidden" name="section" value="server">'
                  f'<label>{esc(t["frp_server_ip"])}<input name="server" data-load-address="{esc(name, quote=True)}" required></label>'
                  f'<label>{esc(t["proxy_port"])}<input type="number" name="port" min="1" max="65535" '
                  f'data-load-port="{esc(name, quote=True)}" required></label>'
                  f'<div class="frp-password-field">{server_token_field}</div>'
                  f'<button type="submit">{esc(t["frp_save"])}</button>'
                  f'</form></details><dl class="frp-facts frp-server-facts"><div><dt>{esc(t["frp_server_ip"])}</dt>'
                  f'<dd>{reveal("server", self.context.masked_frpc_ip(config["serverAddr"]), t["frp_server_ip"])}</dd></div>'
                  f'<div><dt>{esc(t["proxy_port"])}</dt><dd>{reveal("port", "••••••", t["proxy_port"])}</dd></div>'
                  f'<div><dt>{esc(t["frps_token"])}</dt><dd>{reveal("token", "••••••", t["frps_token"])}</dd></div></dl></section>')
        proxy_fields = [('proxy_name', 'name', 'text'), ('proxy_type', 'type', 'text'),
                        ('frp_local_ip', 'localIP', 'text'), ('frp_local_port', 'localPort', 'number'),
                        ('frp_server_port', 'remotePort', 'number')]
        def fields(proxy, suffix):
            result = []
            for label, key, kind in proxy_fields:
                if key == 'type':
                    current = proxy.get('type', 'tcp')
                    options = ''.join(f'<option value="{value}" {"selected" if current == value else ""}>{value.upper()}</option>'
                                      for value in ('tcp', 'udp'))
                    result.append(f'<label>{esc(t[label])}<select name="type">{options}</select></label>')
                else:
                    title = f'<label for="frp-{esc(suffix, quote=True)}-{key}">{esc(t[label])}</label>'
                    result.append(f'<div class="frp-field">{title}'
                                  f'<input id="frp-{esc(suffix, quote=True)}-{key}" name="{"proxyName" if key == "name" else key}" '
                                  f'type="{kind}" aria-label="{esc(t[label], quote=True)}" '
                                  f'value="{esc(str(proxy.get(key, "")), quote=True)}" required></div>')
            return ''.join(result)
        cards = []
        for index, proxy in enumerate(config.get('proxies', [])):
            cards.append(f'<section class="frp-proxy-card"><details class="node-inline-edit"><summary>'
                         f'<span>{esc(t["frp_edit_proxy"])}</span><span>{esc(t["node_cancel"])}</span></summary>'
                         f'<form method="post" action="/frp/client/structured">{base}'
                         f'<input type="hidden" name="section" value="edit"><input type="hidden" name="index" value="{index}">'
                         f'{fields(proxy, str(index))}<button type="submit">{esc(t["frp_save"])}</button></form></details>'
                         f'<div class="frp-proxy-facts"><strong>{esc(proxy["name"])}</strong>'
                         f'<dl class="frp-proxy-fields"><div><dt>{esc(t["proxy_type"])}</dt><dd>{esc(proxy["type"].upper())}</dd></div>'
                         f'<div><dt>{esc(t["frp_local_ip"])}</dt><dd>{esc(proxy["localIP"])}</dd></div>'
                         f'<div><dt>{esc(t["frp_local_port"])}</dt><dd>{proxy["localPort"]}</dd></div>'
                         f'<div><dt>{esc(t["frp_server_port"])}</dt><dd>{proxy["remotePort"]}</dd></div></dl></div>'
                         f'<form method="post" action="/frp/client/structured" class="frp-delete-form" data-confirm="{esc(t["frp_delete_confirm"], quote=True)}">{base}'
                         f'<input type="hidden" name="section" value="delete"><input type="hidden" name="index" value="{index}">'
                         f'<button type="submit" class="node-action danger">{esc(t["frp_delete_proxy"])}</button></form></section>')
        empty = f'<p class="muted">{esc(t["frp_no_proxies"])}</p>' if not cards else ''
        add = (f'<details class="node-inline-edit frp-add-proxy"><summary><span>{esc(t["frp_add_proxy"])}</span>'
               f'<span>{esc(t["node_cancel"])}</span></summary><form method="post" action="/frp/client/structured">{base}'
               f'<input type="hidden" name="section" value="add">{fields({}, "new")}'
               f'<button type="submit">{esc(t["frp_add_proxy"])}</button></form></details>')
        return server + f'<section class="frp-edit-section"><h2>{esc(t["frp_proxy_list_heading"])}</h2>{"".join(cards)}{empty}{add}</section>'

    def frpc_create_editor(self, lang):
        t, esc = self.context.STRINGS[lang], self.context.html.escape
        token_field = self.context.render_password_field(t, 'frpc-new-token', t['frps_token'], 'token',
                                            'maxlength="128" required autocomplete="new-password"')
        return (f'<section class="frp-edit-section"><h2>{esc(t["frp_server_settings"])}</h2>'
                f'<form method="post" action="/frp/client/structured" autocomplete="off">'
                f'<input type="hidden" name="section" value="create">'
                f'<input type="hidden" name="csrf" value="{self.context.access_csrf_token(self.get_cookie("session"), "frp:structured:new")}">'
                f'<label>{esc(t["frp_instance_name"])}<input name="name" maxlength="32" required></label>'
                f'<label>{esc(t["frp_server_ip"])}<input name="server" required></label>'
                f'<label>{esc(t["proxy_port"])}<input type="number" name="port" min="1" max="65535" required></label>'
                f'<div class="frp-password-field">{token_field}</div><button type="submit">{esc(t["frp_new_client"])}</button></form></section>')

    def frpc_address_value(self, parsed):
        name = self.context.parse_qs(parsed.query).get('name', [''])[0]
        try:
            if self.context.frpc_path(name).is_symlink():
                raise ValueError
            address = self.context.frpc_summary(name)['server']
            if not address:
                raise ValueError
        except (OSError, ValueError):
            return self.send_html(404, 'FRPC instance missing', {'Cache-Control': 'no-store'})
        body = self.context.json.dumps({'value': address}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def frpc_private_value(self, parsed):
        query = self.context.parse_qs(parsed.query)
        if set(query) != {'name', 'field'} or any(len(values) != 1 for values in query.values()):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        name, field = query['name'][0], query['field'][0]
        if field not in ('server', 'port', 'token'):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        try:
            if self.context.frpc_path(name).is_symlink():
                raise ValueError
            config = self.context.frpc_structured(name)
            if config is None:
                raise ValueError
            value = (config['serverAddr'] if field == 'server' else
                     str(config['serverPort']) if field == 'port' else config['auth']['token'])
        except (OSError, ValueError, KeyError, TypeError):
            return self.send_html(404, 'FRPC instance missing', {'Cache-Control': 'no-store'})
        body = self.context.json.dumps({'value': value}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        self.wfile.write(body)

    def handle_frpc_test(self):
        if self.headers.get('Content-Type', '').split(';', 1)[0].strip() != 'application/x-www-form-urlencoded':
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        try:
            length = int(self.headers.get('Content-Length', ''))
            if not 0 < length <= 1024:
                raise ValueError
            form = self.context.parse_qs(self.rfile.read(length).decode('utf-8'), strict_parsing=True)
            if set(form) != {'name', 'csrf'} or any(len(values) != 1 for values in form.values()):
                raise ValueError
            name = form['name'][0]
            path = self.context.frpc_path(name)
            if not path.is_file() or path.is_symlink():
                raise ValueError
        except (OSError, UnicodeError, ValueError):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        expected = self.context.access_csrf_token(self.get_cookie('session'), 'frp:test:' + name)
        if not self.context.hmac.compare_digest(form['csrf'][0], expected):
            return self.send_html(403, 'Forbidden', {'Cache-Control': 'no-store'})
        connected = self.context.frpc_test_connection(name)
        if connected is None:
            return self.send_html(429, 'Connection test in progress', {'Cache-Control': 'no-store'})
        body = self.context.json.dumps({'connected': connected}).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def handle_frp_edit(self, path, lang):
        if self.headers.get('Content-Type', '').split(';', 1)[0].strip() != 'application/x-www-form-urlencoded':
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        try:
            length = int(self.headers.get('Content-Length', ''))
            if not 0 < length <= 32768:
                raise ValueError
            form = self.context.parse_qs(self.rfile.read(length).decode('utf-8'), strict_parsing=True, keep_blank_values=True)
            structured = path.endswith('client/structured')
            section = form.get('section', [''])[0]
            required = ({'csrf', 'port', 'token'} if path.endswith('server/save') else
                        {'csrf', 'name', 'newName'} if path.endswith('client/rename') else
                        {'csrf', 'name'} if path.endswith('client/delete') else
                        {'csrf', 'name', 'section', 'server', 'port', 'token'} if structured and section in ('server', 'create') else
                        {'csrf', 'name', 'section', 'index'} if structured and section == 'delete' else
                        {'csrf', 'name', 'section', 'proxyName', 'type', 'localIP', 'localPort', 'remotePort'} if structured and section == 'add' else
                        {'csrf', 'name', 'section', 'index', 'type', 'localIP', 'localPort', 'remotePort', 'proxyName'} if structured and section == 'edit' else
                        {'csrf', 'action'} if path.endswith('server/toggle') else
                        {'csrf', 'name', 'action'})
            if set(form) != required or any(len(v) != 1 for v in form.values()):
                raise ValueError
            name = form.get('name', [''])[0]
            if path.endswith('server/save'):
                action = 'frp:server'
                node = self.context.frps_node()
                if node is None:
                    raise ValueError
                request = {'action': 'server', 'port': int(form['port'][0]) if form['port'][0] else node['port'],
                           'token': form['token'][0] or node['token']}
            elif path.endswith('client/rename'):
                if not self.context.frpc_path(name).is_file() or self.context.frpc_path(name).is_symlink():
                    raise ValueError
                new_name = form['newName'][0]
                self.context.frpc_path(new_name)
                action = 'frp:rename:' + name
                request = {'action': 'rename-client', 'name': name, 'new_name': new_name}
            elif path.endswith('client/delete'):
                if not self.context.frpc_path(name).is_file() or self.context.frpc_path(name).is_symlink():
                    raise ValueError
                action = 'frp:delete:' + name
                request = {'action': 'delete-client', 'name': name}
            elif structured:
                if section not in ('server', 'add', 'edit', 'delete', 'create') or (section != 'create' and not self.context.frpc_path(name).is_file()):
                    raise ValueError
                if section == 'create':
                    self.context.frpc_path(name)
                action = 'frp:structured:' + (name if section != 'create' else 'new')
                values = {'index': int(form['index'][0])} if section in ('edit', 'delete') else {}
                if section in ('server', 'create'):
                    values.update(server=form['server'][0], port=int(form['port'][0]), token=form['token'][0])
                elif section != 'delete':
                    values['proxy'] = {'name': form['proxyName'][0], 'type': form['type'][0],
                                       'localIP': form['localIP'][0], 'localPort': int(form['localPort'][0]),
                                       'remotePort': int(form['remotePort'][0])}
                request = {'action': 'create-structured-client' if section == 'create' else 'structured-client',
                           'name': name, 'section': section, 'values': values}
            elif path.endswith('server/toggle'):
                state = form['action'][0]
                if state not in ('enable', 'disable') or self.context.frps_node() is None:
                    raise ValueError
                action = 'frp:server:' + state
                request = {'action': 'server-' + state}
            else:
                state = form['action'][0]
                if state not in ('enable', 'disable') or not self.context.frpc_path(name).is_file() or self.context.frpc_path(name).is_symlink():
                    raise ValueError
                action = 'frp:toggle:' + name + ':' + state
                request = {'action': state, 'name': name}
        except (UnicodeError, ValueError, OSError):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        if not self.context.hmac.compare_digest(form['csrf'][0], self.context.access_csrf_token(self.get_cookie('session'), action)):
            return self.send_html(403, 'Forbidden', {'Cache-Control': 'no-store'})
        if not self.context.FRP_CONTROL_HELPER.is_file():
            return self.send_html(503, 'FRP helper unavailable', {'Cache-Control': 'no-store'})
        direct = ['/usr/bin/python3', str(self.context.FRP_CONTROL_HELPER)]
        systemd_run = self.context.shutil.which('systemd-run')
        if not systemd_run and self.context.Path('/run/systemd/system').exists():
            return self.send_html(503, 'FRP helper unavailable', {'Cache-Control': 'no-store'})
        command = (['systemd-run', '--pipe', '--wait', '--collect', '--unit=vps-server-frp-control.service', *direct]
                   if systemd_run else direct)
        try:
            result = self.context.subprocess.run(command, input=self.context.json.dumps(request).encode(),
                                    stdout=self.context.subprocess.DEVNULL, stderr=self.context.subprocess.DEVNULL,
                                    timeout=180, check=False)
        except self.context.subprocess.TimeoutExpired:
            if systemd_run:
                self.context._run_quiet(['systemctl', 'stop', 'vps-server-frp-control.service'])
            result = None
        except OSError:
            result = None
        succeeded = bool(result and result.returncode == 0)
        if structured and section == 'create' and succeeded:
            succeeded = self.context.frpc_path(name).is_file() and not self.context.frpc_path(name).is_symlink()
        if path.endswith('client/rename') and succeeded:
            name = new_name
        target = ('/frp/client/edit' if structured and section == 'create' and not succeeded else
                  '/frp/client/edit?name=' + self.context.quote(name) if path in ('/frp/client/structured', '/frp/client/toggle', '/frp/client/rename') else
                  '/frps' if path.startswith('/frp/server/') else '/frpc')
        return self.redirect(target + ('&' if '?' in target else '?') + 'msg=' +
                             ('done' if succeeded else 'failed'),
                             {'Cache-Control': 'no-store'})

    def route_frp(self, method, path, parsed, lang, query_lang):
        if not self.context.AUTH_ENABLED:
            return False
        if method == "GET" and path == "/frps":
            self.page_frps(lang, query_lang)
        elif method == "GET" and path == "/frpc":
            self.page_frpc(lang, query_lang)
        elif method == "GET" and path == "/frp":
            target = ('/frps?edit=server' if self.context.parse_qs(parsed.query).get('edit') == ['server']
                      else '/frpc')
            self.redirect(target, {'Cache-Control': 'no-store'})
        elif method == "GET" and path == "/frp/server/edit":
            self.page_frps_edit(lang)
        elif method == "GET" and path == "/frp/client/edit":
            self.page_frpc_edit(lang, parsed)
        elif method == "GET" and path == "/frp/client/address":
            self.frpc_address_value(parsed)
        elif method == "GET" and path == "/frp/client/value":
            self.frpc_private_value(parsed)
        elif method == "GET" and path == "/frp/server/value":
            query = self.context.parse_qs(parsed.query)
            if (set(query) != {"id", "field"} or query["id"] != ["frps"] or
                    query["field"] not in (["port"], ["credential"])):
                self.send_html(400, "Invalid request", {"Cache-Control": "no-store"})
            else:
                self.handle_proxy_private_value(parsed)
        elif method == "POST" and path == "/frp/client/test":
            self.handle_frpc_test()
        elif method == "POST" and path in ("/frp/server/save", "/frp/client/toggle",
                                                "/frp/client/card-toggle", "/frp/client/rename",
                                                "/frp/client/delete", "/frp/server/toggle",
                                                "/frp/client/structured"):
            self.handle_frp_edit(path, lang)
        else:
            return False
        return True


def frps_node(context, ):
    """Read-only server parameters; do not expose them outside an authenticated console."""
    try:
        text = context.FRPS_CONFIG.read_text()
        fields = dict(context.re.findall(r'^([\w.]+)\s*=\s*(.+?)\s*$', text, context.re.M))
        port = int(fields['bindPort'])
        token = context.json.loads(fields['auth.token'])
        if not 1 <= port <= 65535 or not token:
            return None
        return {'address': fields.get('bindAddr', '"0.0.0.0"').strip('"'),
                'port': port, 'token': token}
    except (OSError, ValueError, KeyError, TypeError):
        return None

def frpc_connected(context, name, server, port):
    """Check this instance's established TCP socket to its configured server."""
    try:
        pid_text = context.subprocess.run(['systemctl', 'show', '-P', 'MainPID', context.frpc_unit(name)],
                                  capture_output=True, text=True, timeout=3, check=True).stdout.strip()
        pid = int(pid_text)
        if pid <= 0 or not server or not port:
            return False
        output = context.subprocess.run(['ss', '-Htnp', 'state', 'established'], capture_output=True,
                                text=True, timeout=3, check=True).stdout
        destinations = {address[4][0] for address in context.socket.getaddrinfo(server, port, type=context.socket.SOCK_STREAM)}
        for line in output.splitlines():
            if f'pid={pid},' not in line:
                continue
            peer = line.split()[3].rsplit(':', 1)
            if len(peer) == 2 and peer[1] == str(port) and peer[0].strip('[]') in destinations:
                return True
    except (OSError, ValueError, IndexError, context.subprocess.SubprocessError):
        pass
    return False

def frpc_test_connection(context, name):
    """Make a separate proxy-free FRPC login using the saved server credentials."""
    if not context._frpc_probe_lock.acquire(blocking=False):
        return None
    try:
        config = context.frpc_structured(name)
        if config is None or not context.FRPC_BINARY.is_file():
            return False
        content = context.frpc_build(config['serverAddr'], config['serverPort'], config['auth']['token'], [])
        with context.tempfile.TemporaryDirectory(prefix='vps-frpc-probe-') as directory:
            path = context.Path(directory) / 'frpc.toml'
            descriptor = context.os.open(path, context.os.O_WRONLY | context.os.O_CREAT | context.os.O_EXCL, 0o600)
            with context.os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(content)
            try:
                result = context.subprocess.run([str(context.FRPC_BINARY), '-c', str(path)],
                                        stdout=context.subprocess.PIPE, stderr=context.subprocess.STDOUT,
                                        timeout=7, check=False)
                output = result.stdout or b''
            except context.subprocess.TimeoutExpired as exc:
                output = exc.stdout or b''
        return b'login to server success' in output
    except (OSError, ValueError, KeyError, TypeError, context.subprocess.SubprocessError):
        return False
    finally:
        context._frpc_probe_lock.release()

def masked_frpc_ip(context, address):
    try:
        parsed = context.ipaddress.ip_address(address)
        parts = str(parsed).split('.' if parsed.version == 4 else ':')
        return '.'.join(parts[:2] + ['*', '*']) if parsed.version == 4 else ':'.join(parts[:4]) + ':…'
    except ValueError:
        return '••••••'
