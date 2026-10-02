"""Visitors pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class VisitorsMixin:
    def page_visitors(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        rows = self.context.recent_visitors()

        def render_row(r):
            scope = r["scope"]
            badge = ""
            if scope in ("loopback", "private"):
                badge = f' <span class="badge">{self.context.html.escape(t["scope_" + scope])}</span>'
            if r["hits"]:
                lastreq = self.context.html.escape(
                    f'{r["last_method"]} {r["last_path"]} → {r["last_status"]}'
                )
            else:
                lastreq = '<span class="muted">—</span>'
            direction = r["direction"] or "in"
            dir_html = (
                f'<span class="dir dir-{direction}">'
                f'{self.context.html.escape(t["dir_" + direction])}</span>'
            )
            return (
                f'<tr data-scope="{self.context.html.escape(scope)}" data-dir="{self.context.html.escape(direction)}">'
                f'<td>{self.context.html.escape(r["ip"])}{badge}</td>'
                f'<td>{dir_html}</td>'
                f'<td>{self.context.html.escape(r["first_seen"])}</td>'
                f'<td>{self.context.html.escape(r["last_seen"])}</td>'
                f'<td class="num">{r["hits"]}</td>'
                f'<td class="num ports">{self.context.html.escape(r["ports"] or "—")}</td>'
                f'<td class="lastreq">{lastreq}</td>'
                "</tr>"
            )

        if not rows:
            table_rows = f'<tr><td colspan="7">{self.context.html.escape(t["no_visits"])}</td></tr>'
        else:
            table_rows = "\n".join(render_row(r) for r in rows)

        heading = t["visitors_heading"].format(n=len(rows), max=self.context.MAX_VISITOR_ROWS)
        body = f"""
        <div class="card wide">
          <h1>{self.context.html.escape(heading)}</h1>
          <div class="filters">
            <button type="button" class="chip active" data-filter="all">{self.context.html.escape(t['show_all'])}</button>
            <button type="button" class="chip" data-filter="inbound">{self.context.html.escape(t['show_inbound'])}</button>
            <button type="button" class="chip" data-filter="public">{self.context.html.escape(t['show_external'])}</button>
          </div>
          <div class="table-scroll">
          <table id="visitors">
            <thead><tr>
              <th>{self.context.html.escape(t['col_ip'])}</th>
              <th>{self.context.html.escape(t['col_dir'])}</th>
              <th>{self.context.html.escape(t['col_first'])}</th>
              <th>{self.context.html.escape(t['col_last'])}</th>
              <th class="num">{self.context.html.escape(t['col_hits'])}</th>
              <th class="num">{self.context.html.escape(t['col_ports'])}</th>
              <th>{self.context.html.escape(t['col_lastreq'])}</th>
            </tr></thead>
            <tbody>
            {table_rows}
            </tbody>
          </table>
          </div>
        </div>
        <script src="/static/visitors.js"></script>
        """
        self.send_html(200, self.render_page(t['visitors'], body, lang, active="visitors"),
                       self.maybe_lang_cookie(query_lang))

    def route_visitors(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/visitors":
            self.page_visitors(lang, query_lang)
            return True
        return False


def init_db(context, ):
    with context.sqlite3.connect(context.DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visitors (
                ip          TEXT PRIMARY KEY,
                first_seen  TEXT NOT NULL,
                last_seen   TEXT NOT NULL,
                hits        INTEGER NOT NULL,
                last_method TEXT NOT NULL,
                last_path   TEXT NOT NULL,
                last_status INTEGER NOT NULL
            )
            """
        )
        # Migrate databases created before connection tracking existed. Adding
        # columns one at a time keeps existing visitor history intact.
        existing = {row[1] for row in conn.execute("PRAGMA table_info(visitors)")}
        for column, ddl in (
            ("conn_seen", "ALTER TABLE visitors ADD COLUMN conn_seen INTEGER NOT NULL DEFAULT 0"),
            ("ports", "ALTER TABLE visitors ADD COLUMN ports TEXT NOT NULL DEFAULT ''"),
            ("scope", "ALTER TABLE visitors ADD COLUMN scope TEXT NOT NULL DEFAULT 'public'"),
            ("direction", "ALTER TABLE visitors ADD COLUMN direction TEXT NOT NULL DEFAULT 'in'"),
        ):
            if column not in existing:
                conn.execute(ddl)
        # Backfill scope for rows that predate the column.
        for (ip,) in conn.execute("SELECT ip FROM visitors WHERE scope = 'public'").fetchall():
            conn.execute("UPDATE visitors SET scope = ? WHERE ip = ?", (context.ip_scope(ip), ip))

def _trim(context, conn):
    conn.execute(
        "DELETE FROM visitors WHERE ip NOT IN "
        "(SELECT ip FROM visitors ORDER BY last_seen DESC LIMIT ?)",
        (context.MAX_VISITOR_ROWS,),
    )

def log_visit(context, ip, method, path, status):
    if not context.module_feature_enabled(context.BASE_DIR, "visitors"):
        return
    ts = context.datetime.now(context.timezone.utc).isoformat(timespec="seconds")
    with context._db_lock, context.sqlite3.connect(context.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO visitors (ip, first_seen, last_seen, hits, last_method,
                                  last_path, last_status, scope)
            VALUES (?, ?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                last_seen   = excluded.last_seen,
                hits        = hits + 1,
                last_method = excluded.last_method,
                last_path   = excluded.last_path,
                last_status = excluded.last_status
            """,
            (ip, ts, ts, method, path[:512], status, context.ip_scope(ip)),
        )
        context._trim(conn)

def record_connections(context, observations):
    """Record remote IPs seen in the kernel TCP table.

    `observations` maps an IP to {"ports": set, "inbound": bool}. These rows
    carry no method/path — the peer did not necessarily speak HTTP.
    """
    if not observations or not context.module_feature_enabled(context.BASE_DIR, "visitors"):
        return
    ts = context.datetime.now(context.timezone.utc).isoformat(timespec="seconds")
    with context._db_lock, context.sqlite3.connect(context.DB_FILE) as conn:
        for ip, entry in observations.items():
            port_text = ",".join(str(p) for p in sorted(entry["ports"])[:8])
            direction = "in" if entry["inbound"] else "out"
            conn.execute(
                """
                INSERT INTO visitors (ip, first_seen, last_seen, hits, last_method,
                                      last_path, last_status, conn_seen, ports,
                                      scope, direction)
                VALUES (?, ?, ?, 0, '', '', 0, 1, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    conn_seen = conn_seen + 1,
                    ports     = excluded.ports,
                    -- once a peer has ever connected in, it stays a visitor
                    direction = CASE WHEN visitors.direction = 'in' THEN 'in'
                                     ELSE excluded.direction END
                """,
                (ip, ts, ts, port_text, context.ip_scope(ip), direction),
            )
        context._trim(conn)

def recent_visitors(context, limit=None):
    if limit is None:
        limit = context.MAX_VISITOR_ROWS
    with context.sqlite3.connect(context.DB_FILE) as conn:
        conn.row_factory = context.sqlite3.Row
        return conn.execute(
            "SELECT ip, first_seen, last_seen, hits, conn_seen, ports, scope, "
            "direction, last_method, last_path, last_status "
            "FROM visitors ORDER BY last_seen DESC LIMIT ?",
            (limit,),
        ).fetchall()

def _decode_addr(context, field):
    """Decode a `/proc/net/tcp[6]` hex address into (ip, port).

    Addresses are stored as little-endian 32-bit words, so each 8-hex-digit
    group has to be byte-swapped before it means anything.
    """
    hex_addr, _, hex_port = field.partition(":")
    port = int(hex_port, 16)
    raw = bytes.fromhex(hex_addr)
    words = [raw[i:i + 4][::-1] for i in range(0, len(raw), 4)]
    packed = b"".join(words)
    addr = context.ipaddress.ip_address(packed)
    # ::ffff:1.2.3.4 is the same machine as 1.2.3.4; show the familiar form.
    if isinstance(addr, context.ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return str(addr), port

def _read_proc_net(context, path):
    try:
        with open(path, "r") as fh:
            return fh.read().splitlines()[1:]  # drop the header row
    except OSError:
        return []

def observed_connections(context, ):
    """Remote IP -> {"ports": set(local ports), "inbound": bool}.

    Every TCP socket with a real peer is reported, whatever the port and
    whatever the connection state (see TCP_PEER_STATES) — that is the point:
    any device that talked to this machine should show up, not only the ones
    that hit a port we happen to be listening on right now. UDP and ICMP are
    *not* covered; the kernel keeps no peer address for them.

    Direction is still derived (local port in the listening set == someone
    connected to us) so that our *own* outbound connections — a git pull, an
    API call — are visible but not mislabelled as visitors.
    """
    listening = set()
    established = []
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in context._read_proc_net(path):
            parts = line.split()
            if len(parts) < 4:
                continue
            local, remote, state = parts[1], parts[2], parts[3]
            try:
                if state == context.TCP_LISTEN:
                    listening.add(context._decode_addr(local)[1])
                elif state in context.TCP_PEER_STATES:
                    established.append((context._decode_addr(local), context._decode_addr(remote)))
            except (ValueError, IndexError):
                continue  # a malformed row must not kill the poller

    observations = {}
    for (_, local_port), (remote_ip, remote_port) in established:
        inbound = local_port in listening
        entry = observations.setdefault(remote_ip, {"ports": set(), "inbound": False})
        # Record the port that identifies the service being used: ours when
        # they connected in, theirs when we connected out.
        entry["ports"].add(local_port if inbound else remote_port)
        if inbound:
            entry["inbound"] = True
    return observations

def connection_poller(context, stop_event):
    while not stop_event.is_set():
        try:
            if context.module_feature_enabled(context.BASE_DIR, "visitors"):
                context.record_connections(context.observed_connections())
        except Exception as exc:  # never let the poller take the server down
            print(context._log_text('log_connection_poller', error=exc), file=context.sys.stderr)
        stop_event.wait(context.CONN_POLL_SECONDS)
