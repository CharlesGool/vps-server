"""Singbox nodes: masked values, Clash subscriptions and limit parsing (the page is the single-page UI).

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""

from node_inventory import add_period


class ProxyMixin:


    PRIVATE_FIELDS = ('port', 'credential', 'share', 'cmd-speed', 'cmd-single', 'cmd-multi',
                      'public-port', 'target-port', 'account', 'address', 'value', 'ipv4', 'ipv6')

    def private_value(self, identifier, field):
        """One value the page shows masked until asked; raises ValueError when there is none."""
        if identifier.startswith('frpc:'):
            return self.frpc_masked_value(identifier[5:], field)
        if field not in self.PRIVATE_FIELDS:
            raise ValueError('unsupported field')
        if identifier.startswith('tailscale-'):
            return self.tailscale_private_value(identifier, field)
        if identifier.startswith('domain-'):
            return self.domains_private_value(identifier, field)
        try:
            if identifier.startswith('interface-') and field == 'address':
                index = identifier[10:]
                if not index.isascii() or not index.isdecimal():
                    raise ValueError('invalid interface')
                entries = self.context.address_entries(self.context.STRINGS['en'])
                position = int(index)
                if position >= len(entries):
                    raise ValueError('unknown interface')
                return entries[position][1]
            if identifier == 'iperf' and field in ('port', 'cmd-speed', 'cmd-single', 'cmd-multi'):
                host = (self.headers.get('Host') or '').split(':')[0] or '<server-ip>'
                suffix = {'cmd-speed': '', 'cmd-single': ' -P 1', 'cmd-multi': ' -P 4'}
                return (str(self.context.IPERF_WINDOW.port) if field == 'port' else
                        f'iperf3 -c {host} -p {self.context.IPERF_WINDOW.port}{suffix[field]}')
            if identifier.startswith('forward-') and field in ('public-port', 'target-port'):
                rule = next(item for item in self.context.PORTFWD.list_rules() if item['id'] == identifier[8:])
                return str(rule['public_port' if field == 'public-port' else 'target_port'])
            if identifier == 'frps' and field in ('port', 'credential'):
                node = self.context.frps_node()
                if node is None:
                    raise ValueError('no frps node')
                return str(node['port'] if field == 'port' else node['token'])
            if identifier.startswith('legacy-') and field in ('port', 'credential'):
                protocol = identifier.removeprefix('legacy-')
                node = (self.context.anytls_node() if protocol == 'anytls' else
                        next(item for item in self.context.proxy_nodes() if item['type'] == protocol))
                if node is None:
                    raise ValueError('no legacy node')
                return str(node['port'] if field == 'port' else
                           node['password'] if protocol == 'anytls' else node['secret'])
            return self.managed_private_value(identifier, field)
        except (OSError, TypeError, KeyError, StopIteration) as exc:
            raise ValueError('no such value') from exc


    def managed_private_value(self, identifier, field):
        try:
            inventory = self.context.read_inventory(state_path=self.context.NODE_STATE_PATH,
                                                   config_paths={'proxy': self.context.PROXY_CONFIG})
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
        peer = self.context.ipaddress.ip_address(self.peer_ip())
        if (not self.context.AUTH_ENABLED or len(parts) != 5 or parts[:3] != ["", "clash", "sub"] or
                not self.context.re.fullmatch(r"[0-9a-f]{64}", parts[4]) or
                not (self.context.is_lan_address(str(peer)) or peer.is_loopback)):
            return self.send_html(404, "Not found", {"Cache-Control": "no-store"})
        try:
            inventory = self.context.read_inventory(state_path=self.context.NODE_STATE_PATH,
                                       config_paths={"proxy": self.context.PROXY_CONFIG})
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


    def node_route_summary(self, node, t):
        access = node.get("access")
        if not access:
            return t["node_route_all"]
        if access["mode"] == "internet":
            return t["node_route_internet"]
        return t["node_route_custom_count"].format(count=len(access["destinations"]))


    def node_limits_request(self, form, existing):
        """Turn the limits form into node fields; raises ValueError on bad input.
        Shared by sing-box nodes and the FRPS entry."""
        request = {}
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
            anchor = "-" if unit_value == "days" else "1" if unit_value == "months" else now.strftime("%m-%d")
            mode = f"every:{count}:{unit_value}:{anchor}"
            return count, unit_value, mode, self.context.advance_reset_interval(now, mode).isoformat()
        def date_value(value):
            if not value:
                return None
            if not self.context.re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
                raise ValueError("invalid date")
            return self.context.datetime.fromisoformat(value).replace(tzinfo=self.context.timezone.utc).isoformat()
        expiry_mode = form["expiry_mode"][0]
        if expiry_mode == "set":
            count, unit, _, _ = duration(form["expiry_count"][0], form["expiry_unit"][0])
            # Saving the dialog again with the same length (say, to change the cap) keeps the
            # end date: only a different length starts a new period from now.
            if (existing["expiry_count"], existing["expiry_unit"]) != (count, unit):
                # N months from now on the same day and time (the month's last day when it is
                # shorter), not the first of a month like a monthly reset.
                request.update(expiry_count=count, expiry_unit=unit,
                               expires_at=add_period(now, count, unit).isoformat())
        elif expiry_mode == "none":
            if existing["expiry_count"] is not None:
                request.update(expiry_count=None, expiry_unit=None, expires_at=None)
        else:
            raise ValueError("invalid expiry mode")
        mode = form["reset_mode"][0]
        if mode not in ("none", "repeat", "once", "schedule"):
            raise ValueError("invalid reset mode")
        if mode == "repeat":
            _, _, request["reset_mode"], request["next_reset_at"] = duration(
                form["reset_count"][0], form["reset_unit"][0])
        elif mode == "schedule":
            # On the calendar like scheduled tasks (host local time): weekly, monthly, yearly or once.
            import scheduler
            try:
                spec = scheduler.normalize_spec(self.context.json.loads(form.get("reset_spec", [""])[0] or "null"))
            except (scheduler.ScheduleError, ValueError) as exc:
                raise ValueError("invalid reset schedule") from exc
            if spec["mode"] == "once":
                moment = self.context.datetime.strptime(f"{spec['date']} {spec['time']}", "%Y-%m-%d %H:%M:%S")
                due = moment.astimezone(self.context.timezone.utc)
                if due <= now:
                    raise ValueError("reset must be future")
                request["reset_mode"], request["next_reset_at"] = "once", due.isoformat()
            else:
                request["reset_mode"] = self.context.schedule_reset_mode(spec)
                request["next_reset_at"] = self.context.next_scheduled_reset(now, spec).isoformat()
        elif mode == "once":
            request["reset_mode"] = "once"
            request["next_reset_at"] = date_value(form["next_reset_at"][0])
            if request["next_reset_at"] is None or \
                    self.context.datetime.fromisoformat(request["next_reset_at"]) <= now:
                raise ValueError("reset must be future")
        else:
            request["reset_mode"] = "none"
            request["next_reset_at"] = None
        return request


    def route_proxy_public(self, method, path):
        if method == "GET" and path.startswith("/clash/sub/"):
            self.handle_clash_subscription(path)
            return True
        return False
