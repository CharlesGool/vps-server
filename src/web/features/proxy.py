"""Singbox nodes: masked values, Clash subscriptions and limit parsing (the page is the single-page UI).

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""

from field_errors import FieldError, schedule_error
from node_inventory import add_period

# The limits dialog's keys under the form names older callers use (see node_limits_request).
LIMIT_KEYS = {"cap_gib": "capGib", "upload_mbps": "uploadMbps", "download_mbps": "downloadMbps",
              "cap_action": "capAction", "expiry_mode": "expiryMode", "expiry_count": "expiryCount",
              "expiry_unit": "expiryUnit", "reset_mode": "resetMode", "reset_count": "resetCount",
              "reset_unit": "resetUnit", "next_reset_at": "nextResetAt"}


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
        """limits_request() for the form shape older callers use: one-item lists under snake_case names."""
        body = {key: form[name][0] for name, key in LIMIT_KEYS.items() if name in form}
        spec = form.get("reset_spec", [""])[0]
        body["resetSpec"] = self.context.json.loads(spec) if spec else None
        return self.limits_request(body, existing)

    def limits_request(self, body, existing):
        """The limits dialog's JSON object as entry fields; raises FieldError (a ValueError) naming the bad key.

        Shared by sing-box nodes, FRPS and every metered feature. Numbers may come as JSON numbers
        or text; a missing or null value is empty.
        """
        context = self.context
        request = {}

        def text(name):
            value = body.get(name)
            if value is None:
                return ""
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise FieldError(name, "type")
            return str(value)

        def amount(name, low, high, low_inclusive=True):
            """A positive decimal within range, or None for an empty value."""
            value = text(name).strip()
            if not value:
                return None
            try:
                number = context.Decimal(value)
            except (ArithmeticError, ValueError) as exc:
                raise FieldError(name, "format") from exc
            if not number.is_finite():
                raise FieldError(name, "format")
            if not (low <= number if low_inclusive else low < number) or number > high:
                raise FieldError(name, "range")
            return number

        def choice(name, allowed):
            value = text(name)
            if value not in allowed:
                raise FieldError(name, "format" if value else "required")
            return value

        # Every value is checked for its type, also one the chosen settings do not use.
        for name in LIMIT_KEYS.values():
            text(name)
        spec = body.get("resetSpec")
        if spec is not None and not isinstance(spec, dict):
            raise FieldError("resetSpec", "type")
        cap = amount("capGib", 0, 100000000, low_inclusive=False)
        request["cap_bytes"] = None if cap is None else int(cap * 1073741824)

        def speed(name):
            value = amount(name, context.Decimal("0.001"), 10000000)
            if value is None:
                return None
            result = int(value * 1000000)
            if result < 1000:
                raise FieldError(name, "range")
            return result
        request["upload_limit_bps"] = speed("uploadMbps")
        request["download_limit_bps"] = speed("downloadMbps")
        request["cap_action"] = choice("capAction", ("throttle", "block"))
        now = context.datetime.now(context.timezone.utc)

        def duration(count_name, unit_name):
            value = text(count_name).strip()
            if not value:
                raise FieldError(count_name, "required")
            try:
                count = int(value)
            except ValueError as exc:
                raise FieldError(count_name, "format") from exc
            if not 1 <= count <= 9999:
                raise FieldError(count_name, "range")
            unit = choice(unit_name, ("days", "months", "years"))
            anchor = "-" if unit == "days" else "1" if unit == "months" else now.strftime("%m-%d")
            mode = f"every:{count}:{unit}:{anchor}"
            try:
                due = context.advance_reset_interval(now, mode)
            except (ValueError, OverflowError) as exc:
                raise FieldError(count_name, "range") from exc
            return count, unit, mode, due.isoformat()

        expiry_mode = choice("expiryMode", ("set", "none"))
        if expiry_mode == "set":
            count, unit, _, _ = duration("expiryCount", "expiryUnit")
            # Saving the dialog again with the same length (say, to change the cap) keeps the
            # end date: only a different length starts a new period from now.
            if (existing["expiry_count"], existing["expiry_unit"]) != (count, unit):
                # N months from now on the same day and time (the month's last day when it is
                # shorter), not the first of a month like a monthly reset.
                try:
                    expires = add_period(now, count, unit)
                except (ValueError, OverflowError) as exc:
                    raise FieldError("expiryCount", "range") from exc
                request.update(expiry_count=count, expiry_unit=unit, expires_at=expires.isoformat())
        elif existing["expiry_count"] is not None:
            request.update(expiry_count=None, expiry_unit=None, expires_at=None)
        mode = choice("resetMode", ("none", "repeat", "once", "schedule"))
        if mode == "repeat":
            _, _, request["reset_mode"], request["next_reset_at"] = duration("resetCount", "resetUnit")
        elif mode == "schedule":
            # On the calendar like scheduled tasks (host local time): weekly, monthly, yearly or once.
            import scheduler
            try:
                spec = scheduler.normalize_spec(spec)
            except (scheduler.ScheduleError, ValueError) as exc:
                raise schedule_error(exc, body.get("resetSpec"), "resetSpec") from exc
            if spec["mode"] == "once":
                moment = context.datetime.strptime(f"{spec['date']} {spec['time']}", "%Y-%m-%d %H:%M:%S")
                due = moment.astimezone(context.timezone.utc)
                if due <= now:
                    raise FieldError("resetSpec.date", "past", "reset must be future")
                request["reset_mode"], request["next_reset_at"] = "once", due.isoformat()
            else:
                request["reset_mode"] = context.schedule_reset_mode(spec)
                request["next_reset_at"] = context.next_scheduled_reset(now, spec).isoformat()
        elif mode == "once":
            value = text("nextResetAt")
            if not value:
                raise FieldError("nextResetAt", "required")
            if not context.re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
                raise FieldError("nextResetAt", "format")
            try:
                due = context.datetime.fromisoformat(value).replace(tzinfo=context.timezone.utc)
            except ValueError as exc:
                raise FieldError("nextResetAt", "format") from exc
            if due <= now:
                raise FieldError("nextResetAt", "past", "reset must be future")
            request["reset_mode"], request["next_reset_at"] = "once", due.isoformat()
        else:
            request["reset_mode"] = "none"
            request["next_reset_at"] = None
        return request


    def route_proxy_public(self, method, path):
        if method == "GET" and path.startswith("/clash/sub/"):
            self.handle_clash_subscription(path)
            return True
        return False
