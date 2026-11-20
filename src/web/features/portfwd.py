"""Port forwarding: iptables rules and the rule store (the page is the single-page UI).

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


def _valid_port(context, value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None

def _valid_target_host(context, value):
    # IPv4 only, matching every other address-handling function in this file
    # (local_addresses(), tailscale_address()) — and a literal address is
    # required anyway, since iptables --to-destination cannot take a hostname.
    try:
        context.ipaddress.IPv4Address(value)
    except ValueError:
        return False
    return True

def _portfwd_comment(context, rule_id):
    return f"{context.PORTFWD_TAG_PREFIX}{rule_id}"

def _portfwd_specs(context, rule, legacy=False):
    """[(table, chain, match-args, action-args)] for one rule.

    The same list builds both the -A and the -D command for a rule — only the
    verb differs — so closing a rule can never drift from opening it by one
    flag the way two hand-written copies eventually would.

    ``legacy`` gives the DNAT rule as versions up to 7.4.0 wrote it, without
    the destination-type match, only so that withdrawing a rule also removes
    that older form after an upgrade.
    """
    comment = context._portfwd_comment(rule["id"])
    protocols = ["tcp", "udp"] if rule["protocol"] == "both" else [rule["protocol"]]
    specs = []
    for proto in protocols:
        prerouting = ["-p", proto, "--dport", str(rule["public_port"])]
        if not legacy:
            # Only connections to this host's own addresses. Traffic it merely routes
            # (Tailscale exit-node clients, Docker containers) keeps its destination.
            prerouting += ["-m", "addrtype", "--dst-type", "LOCAL"]
        specs.append(("nat", "PREROUTING", prerouting,
            ["-m", "comment", "--comment", comment, "-j", "DNAT",
             "--to-destination", f'{rule["target_host"]}:{rule["target_port"]}']))
        specs.append(("nat", "POSTROUTING",
            ["-p", proto, "-d", rule["target_host"], "--dport", str(rule["target_port"])],
            ["-m", "comment", "--comment", comment, "-j", "MASQUERADE"]))
        specs.append(("filter", "FORWARD",
            ["-p", proto, "-d", rule["target_host"], "--dport", str(rule["target_port"])],
            ["-m", "comment", "--comment", comment, "-j", "ACCEPT"]))
        specs.append(("filter", "FORWARD",
            ["-p", proto, "-s", rule["target_host"], "--sport", str(rule["target_port"])],
            ["-m", "comment", "--comment", comment, "-j", "ACCEPT"]))
    return specs

def _ensure_ip_forward(context, ):
    """Turn on net.ipv4.ip_forward if it is not already on.

    Never turned back off: it is a single host-wide toggle, and other
    software already running here (Docker, for one) may depend on it too.
    Symmetrically closing it when the last forward is removed would risk
    breaking whatever else asked for it first — see doc/LOG.md#决策.
    """
    try:
        current = context.Path("/proc/sys/net/ipv4/ip_forward").read_text().strip()
    except OSError:
        return False
    if current != "1":
        return context._run_quiet(["sysctl", "-w", "net.ipv4.ip_forward=1"])
    return True

def portfwd_rule_apply(context, rule, opening):
    """Add (opening=True) or withdraw (opening=False) one rule's iptables state.

    Return whether every requested rule was applied or withdrawn. An absent
    rule is already withdrawn; partial additions are removed before failure.
    """
    from nft_runtime import iptables_command
    iptables = iptables_command()
    if not iptables:
        print(context._log_text('log_iptables_missing'), file=context.sys.stderr)
        return False
    ok = True
    for table, chain, match, action in context._portfwd_specs(rule):
        verb = "-A" if opening else "-D"
        cmd = [iptables, "-t", table, verb, chain, *match, *action]
        if not context._run_quiet(cmd):
            if opening or context._run_quiet([iptables, "-t", table, "-C", chain, *match, *action]):
                ok = False
    if not opening:
        # A DNAT rule left by an older version matches every destination. Withdraw that
        # form too (normally it is simply absent), so the startup replay in load() and
        # every later withdrawal replace it with the current one.
        for table, chain, match, action in context._portfwd_specs(rule, legacy=True):
            if chain == "PREROUTING":
                for _ in range(4):
                    if not context._run_quiet([iptables, "-t", table, "-D", chain, *match, *action]):
                        break
    if opening and not ok:
        # A partially applied rule must not be left in the kernel after the
        # caller reports a failure. Every spec carries this rule's own tag.
        for table, chain, match, action in context._portfwd_specs(rule):
            context._run_quiet([iptables, "-t", table, "-D", chain, *match, *action])
        print(context._log_text('log_portfwd_apply', rule_id=rule['id']), file=context.sys.stderr)
    return ok

class PortForwardManager:
    """Console-configured DNAT rules, one process-wide instance (PORTFWD).

    State is plain JSON, read into memory once and rewritten on every change.
    A rule's `enabled` flag is the source of truth for whether it should be
    live; whether it actually IS live in the kernel right now is never read
    back from iptables, only driven forward from here — see load().
    """

    def __init__(self, state_file, max_rules):
        self._state_file = state_file
        self._max_rules = max_rules
        self._lock = self.context.threading.RLock()
        self._rules = self._read()
        self._applied = set()

    def _read(self):
        try:
            data = self.context.json.loads(self._state_file.read_text())
        except (OSError, ValueError):
            return []
        return data if isinstance(data, list) else []

    def _write(self):
        tmp = self._state_file.with_suffix(".json.tmp")
        tmp.write_text(self.context.json.dumps(self._rules, indent=2))
        tmp.replace(self._state_file)

    def list_rules(self):
        with self._lock:
            return [{**rule, "applied": rule["id"] in self._applied} for rule in self._rules]

    def reserved_ports(self, exclude_id=None):
        """Every public port this install already answers on.

        Checked before a forward is added or re-enabled — DNAT would
        otherwise silently steal traffic meant for the console, the public
        page, the iperf3 window, the anytls node, or any installed proxy
        protocol.
        """
        reserved = {self.context.PUBLIC_HTTP_PORT, self.context.PUBLIC_HTTPS_PORT, self.context.CONSOLE_PORT}
        if self.context.IPERF_ENABLED:
            reserved.add(self.context.IPERF_WINDOW.port)
        node = self.context.anytls_node()
        if node and node.get("port"):
            try:
                reserved.add(int(node["port"]))
            except (TypeError, ValueError):
                pass
        frps = self.context.frps_node()
        if frps:
            reserved.add(frps['port'])
        for pnode in self.context.proxy_nodes():
            if pnode.get("port"):
                try:
                    reserved.add(int(pnode["port"]))
                except (TypeError, ValueError):
                    pass
        with self._lock:
            for r in self._rules:
                if r["id"] != exclude_id:
                    reserved.add(r["public_port"])
        return reserved

    def add(self, protocol, public_port, target_host, target_port, label):
        if not self.context.portfwd_enabled():
            return None, "portfwd_module_disabled"
        with self._lock:
            if len(self._rules) >= self._max_rules:
                return None, "portfwd_limit"
            if public_port in self.reserved_ports():
                return None, "portfwd_port_taken"
            rule = {
                "id": self.context.secrets.token_hex(4),
                "label": label[:80],
                "protocol": protocol,
                "public_port": public_port,
                "target_host": target_host,
                "target_port": target_port,
                "enabled": True,
                "created": self.context.datetime.now(self.context.timezone.utc).isoformat(timespec="seconds"),
            }
            owner = "vps-server portfwd " + rule["id"]
            try:
                reserved = self.context.reserve_owned_port(self.context.BASE_DIR, public_port, owner)
            except (OSError, ValueError):
                return None, "portfwd_port_taken"
            if not self.context._ensure_ip_forward() or not self.context.portfwd_rule_apply(rule, opening=True):
                if reserved:
                    self.context.release_owned_port(self.context.BASE_DIR, public_port, owner)
                return None, "portfwd_apply_failed"
            self._rules.append(rule)
            try:
                self._write()
            except OSError:
                self._rules.pop()
                self.context.portfwd_rule_apply(rule, opening=False)
                if reserved:
                    self.context.release_owned_port(self.context.BASE_DIR, public_port, owner)
                return None, "portfwd_apply_failed"
            self._applied.add(rule["id"])
            return rule, "portfwd_added"

    def remove(self, rule_id):
        with self._lock:
            rule = next((r for r in self._rules if r["id"] == rule_id), None)
            if rule is None:
                return "portfwd_not_found"
            if rule["enabled"] and not self.context.portfwd_rule_apply(rule, opening=False):
                return "portfwd_apply_failed"
            previous = self._rules
            self._rules = [r for r in self._rules if r["id"] != rule_id]
            try:
                self._write()
            except OSError:
                self._rules = previous
                if rule["enabled"] and self.context._ensure_ip_forward():
                    self.context.portfwd_rule_apply(rule, opening=True)
                return "portfwd_apply_failed"
            self._applied.discard(rule_id)
            self.context.release_owned_port(self.context.BASE_DIR, rule["public_port"],
                                            "vps-server portfwd " + rule_id)
            return "portfwd_removed"

    def set_enabled(self, rule_id, enabled):
        with self._lock:
            rule = next((r for r in self._rules if r["id"] == rule_id), None)
            if rule is None:
                return "portfwd_not_found"
            if rule["enabled"] == enabled and (not enabled or rule_id in self._applied):
                return "portfwd_enabled" if enabled else "portfwd_disabled"
            if enabled and rule["public_port"] in self.reserved_ports(exclude_id=rule_id):
                return "portfwd_port_taken"
            owner = "vps-server portfwd " + rule_id
            reserved = False
            if enabled:
                try:
                    reserved = self.context.reserve_owned_port(self.context.BASE_DIR, rule["public_port"], owner)
                except (OSError, ValueError):
                    return "portfwd_port_taken"
                if not self.context._ensure_ip_forward() or not self.context.portfwd_rule_apply(rule, opening=True):
                    if reserved:
                        self.context.release_owned_port(self.context.BASE_DIR, rule["public_port"], owner)
                    return "portfwd_apply_failed"
            else:
                if not self.context.portfwd_rule_apply(rule, opening=False):
                    return "portfwd_apply_failed"
            previous = rule["enabled"]
            rule["enabled"] = enabled
            try:
                self._write()
            except OSError:
                rule["enabled"] = previous
                if enabled:
                    self.context.portfwd_rule_apply(rule, opening=False)
                    if reserved:
                        self.context.release_owned_port(self.context.BASE_DIR, rule["public_port"], owner)
                elif self.context._ensure_ip_forward():
                    self.context.portfwd_rule_apply(rule, opening=True)
                return "portfwd_apply_failed"
            if enabled:
                self._applied.add(rule_id)
            else:
                self._applied.discard(rule_id)
                self.context.release_owned_port(self.context.BASE_DIR, rule["public_port"], owner)
            return "portfwd_enabled" if enabled else "portfwd_disabled"

    def load(self):
        """Reapply every enabled rule at process startup.

        The kernel remembers nothing across a reboot, and may still hold last
        run's rules if this is only a service restart — so each enabled rule
        is withdrawn before it is (re-)added, which is safe to do unconditio-
        nally whether the rule was already present or not.
        """
        with self._lock:
            self._applied.clear()
            if any(r["enabled"] for r in self._rules) and not self.context._ensure_ip_forward():
                return False
            success = True
            for rule in self._rules:
                if rule["enabled"]:
                    owner = "vps-server portfwd " + rule["id"]
                    try:
                        self.context.reserve_owned_port(self.context.BASE_DIR, rule["public_port"], owner)
                    except (OSError, ValueError):
                        success = False
                        continue
                    self.context.portfwd_rule_apply(rule, opening=False)
                    if self.context.portfwd_rule_apply(rule, opening=True):
                        self._applied.add(rule["id"])
                    else:
                        self.context.release_owned_port(self.context.BASE_DIR, rule["public_port"], owner)
                        success = False
            return success

    def shutdown(self):
        """Withdraw every enabled rule's kernel state on a clean stop.

        Deliberately not marked disabled in PORTFWD_STATE_FILE: restarting
        the service, or the host, must bring every one of these straight back
        via load(), the same fail-safe direction the iperf3 window already
        takes — if the thing managing the state is not running, the state
        must not silently outlive it.
        """
        with self._lock:
            for rule in self._rules:
                if rule["enabled"]:
                    self.context.portfwd_rule_apply(rule, opening=False)
                    # One failed registry release must not leave the remaining
                    # rules' kernel state behind.
                    try:
                        self.context.release_owned_port(self.context.BASE_DIR, rule["public_port"],
                                                        "vps-server portfwd " + rule["id"])
                    except Exception as exc:
                        print(self.context._log_text('log_portfwd_release_failed', error=type(exc).__name__),
                              file=self.context.sys.stderr)
            self._applied.clear()

def portfwd_switch_revision(context, ):
    try:
        state = context.PORTFWD_SWITCH_FILE.stat()
        return [state.st_ino, state.st_mtime_ns]
    except FileNotFoundError:
        return [0, 0]

def publish_portfwd_state(context, enabled):
    target = context.PORTFWD_APPLIED_FILE
    temporary = target.with_suffix(".tmp")
    revision = context.portfwd_switch_revision()
    temporary.write_text(context.json.dumps({"enabled": enabled, "revision": revision}) + "\n")
    context.os.chmod(temporary, 0o600)
    context.os.replace(temporary, target)
    return revision

def watch_portfwd_switch(context, stop_event):
    active = context.portfwd_enabled()
    revision = context.publish_portfwd_state(active)
    while not stop_event.wait(0.2):
        desired = context.portfwd_enabled()
        if desired != active:
            try:
                if desired:
                    if not context.PORTFWD.load():
                        raise RuntimeError("port forwarding rules were not applied")
                else:
                    context.PORTFWD.shutdown()
            except Exception as exc:
                print(f"Port forward switch reconciliation failed: {exc}", file=context.sys.stderr)
                continue
            active = desired
        if context.portfwd_switch_revision() != revision:
            revision = context.publish_portfwd_state(active)
