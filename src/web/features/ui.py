"""Ui services with host supplied as context."""


def render_copyable(context, t, label, value, ident):
    return f"""
    <div class="copyrow">
      <div class="copyhead">
        <span>{context.html.escape(label)}</span>
        <button type="button" class="copybtn" data-copy="{ident}"
                data-copied="{context.html.escape(t['copied'])}"
                >{context.html.escape(t['copy'])}</button>
      </div>
      <pre class="cmd" id="{ident}">{context.html.escape(value)}</pre>
    </div>
    """

def render_lang_switcher(context, lang, suffix=""):
    parts = []
    for code, name in context.LANG_NAMES.items():
        cls = "lang active" if code == lang else "lang"
        parts.append(f'<a class="{cls}" href="?lang={code}{suffix}">{context.html.escape(name)}</a>')
    return "\n".join(parts)

def render_password_field(context, t, ident, label, name, attributes="", hint=""):
    """Render one independently revealable, initially masked input."""
    field_id = context.html.escape(ident, quote=True)
    field_label = context.html.escape(label)
    show = context.html.escape(t["login_show_password"])
    hide = context.html.escape(t["login_hide_password"])
    accessible_show = context.html.escape(f'{t["login_show_password"]} {label}', quote=True)
    accessible_hide = context.html.escape(f'{t["login_hide_password"]} {label}', quote=True)
    return (f'<label class="password-label" for="{field_id}">{field_label}</label>'
            f'<div class="password-field">'
            f'<input id="{field_id}" type="password" name="{context.html.escape(name, quote=True)}" {attributes}>'
            f'<button type="button" class="password-toggle" aria-controls="{field_id}" '
            f'aria-pressed="false" aria-label="{accessible_show}" '
            f'data-show-label="{show}" data-hide-label="{hide}" '
            f'data-show-accessible="{accessible_show}" data-hide-accessible="{accessible_hide}">'
            f'{show}</button></div>{hint}')

def _inline_md(context, text):
    """Escape first, then re-introduce only `code` and **bold**.

    Everything is HTML-escaped before any markup is added, so nothing in
    LOG.md can inject markup into the page.
    """
    out = context.html.escape(text)
    out = context.re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = context.re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return out

def changelog_section(context, markdown):
    """Return only LOG.md's Changelog body, or None when it is absent/empty."""
    match = context.re.search(r"^## (?:Changelog|变更日志|變更紀錄|變更記錄|परिवर्तन सूची|Historial de cambios|سجل التغييرات|Historique des modifications)[ \t]*$", markdown, context.re.MULTILINE)
    if not match:
        return None
    tail = markdown[match.end():]
    next_section = context.re.search(r"^## [^#]", tail, context.re.MULTILINE)
    section = tail[:next_section.start()] if next_section else tail
    return section if context.re.search(r"^### v[^\s]+", section, context.re.MULTILINE) else None

def development_updates_section(context, markdown):
    """Select the public test-build notes without exposing Handoff details."""
    match = context.re.search(r"^## Development Updates[ \t]*$", markdown, context.re.MULTILINE)
    if not match:
        return None
    tail = markdown[match.end():]
    next_section = context.re.search(r"^## [^#]", tail, context.re.MULTILINE)
    section = tail[:next_section.start()] if next_section else tail
    return section if context.re.search(r"^- ", section, context.re.MULTILINE) else None

def render_changelog(context, markdown):
    """Render LOG's changelog headings and lists after selecting its section."""
    html_parts = []
    in_list = False
    in_item = False
    in_comment = False
    started = False  # skip notes before the first version

    def close_list():
        nonlocal in_list, in_item
        if in_item:
            html_parts.append("</li>")
            in_item = False
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    for raw in markdown.splitlines():
        stripped = raw.strip()
        # A comment is, by definition, not for the reader. Without this the
        # maintainer's note at the foot of the file came out as a run of
        # paragraphs on the changelog page — escaped `<!--` and all — because
        # every line it contains falls through to the plain-paragraph branch.
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_comment = True
            continue
        if stripped.startswith(("### v", "### dev-", "### test-")):
            started = True
            close_list()
            html_parts.append(f"<h2>{context._inline_md(stripped[4:])}</h2>")
            continue
        if not started:
            continue
        if stripped.startswith("#### "):
            close_list()
            html_parts.append(f"<h3>{context._inline_md(stripped[5:])}</h3>")
        elif stripped.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            if in_item:
                html_parts.append("</li>")
            html_parts.append(f"<li>{context._inline_md(stripped[2:])}")
            in_item = True
        elif not stripped:
            close_list()
        elif in_item:
            # A wrapped bullet: keep it inside the same <li>.
            html_parts.append(f" {context._inline_md(stripped)}")
        else:
            html_parts.append(f"<p>{context._inline_md(stripped)}</p>")
    close_list()
    return "\n".join(html_parts)

def ui_icon(context, name):
    """Inline a bundled, trusted icon so it inherits text color."""
    if name not in context._UI_ICON_NAMES:
        raise ValueError("unknown UI icon")
    if name not in context._UI_ICON_CACHE:
        source = (context.BASE_DIR / "static" / "icons" / "lucide" / f"{name}.svg").read_text(encoding="utf-8")
        context._UI_ICON_CACHE[name] = source.replace("<svg", '<svg class="ui-icon" aria-hidden="true" focusable="false"', 1)
    return context._UI_ICON_CACHE[name]

def render_theme_menu(context, lang):
    t = context.STRINGS[lang]
    theme_options = "".join(
        f'<button type="button" data-theme-choice="{choice}" aria-pressed="{str(choice == "slate-blue").lower()}">'
        f'<span class="theme-swatch theme-swatch-{choice}" aria-hidden="true"></span>{context.html.escape(t[key])}</button>'
        for choice, key in (("slate-blue", "theme_slate_blue"), ("sage", "theme_sage"),
                            ("teal", "theme_teal"), ("plum", "theme_plum"),
                            ("ocean", "theme_ocean"), ("olive", "theme_olive"),
                            ("terracotta", "theme_terracotta"), ("indigo", "theme_indigo"))
    )
    return (f'<details class="theme-menu"><summary>{context.html.escape(t["theme_label"])}</summary>'
            f'<div class="theme-options" role="group" aria-label="{context.html.escape(t["theme_label"], quote=True)}">'
            f'{theme_options}</div></details>')

def render_page(context, title, body, lang, active=None, show_nav=True, password_authenticated=False,
                ip_authenticated=False, bare=False, back_href=None):
    t = context.STRINGS[lang]
    server_label = context.server_label()
    label_badge = (f'<span class="server-label" title="{context.html.escape(server_label, quote=True)}">'
                   f'{context.html.escape(server_label)}</span>' if server_label else '')
    page_title = (f"{server_label} — {title} — {t['title']}" if server_label
                  else f"{title} — {t['title']}")
    favicon = ('login' if bare else 'modules' if title == t['modules_heading'] else
               'security' if back_href == '/settings' else
               active if active in ('home', 'speedtest', 'iperf', 'proxy', 'portfwd',
                                    'visitors', 'changelog', 'settings') else
               'frp' if title in (t['frp_heading'], t['frps_heading'], t['frp_client_heading'])
               or back_href in ('/frps', '/frpc') else 'lucky' if title == 'Lucky' else 'home')
    version_tag = f'<a class="version" href="/changelog">{context.html.escape(context.VERSION_LABEL)}</a>'
    nav = ""
    if show_nav:
        def link(href, key):
            cls = ' class="active"' if active == key else ""
            current = ' aria-current="page"' if active == key else ""
            icons = {"home": "server", "changelog": "scroll-text", "settings": "settings-2"}
            return f'<a{cls}{current} href="{href}">{context.ui_icon(icons[key])}<span>{context.html.escape(t[key])}</span></a>'

        # No session to end when auth is off — offering "Log out" would be a
        # link to nowhere (the route itself redirects to / in that mode).
        logout_link = (f'<a href="/logout">{context.ui_icon("log-out")}<span>{context.html.escape(t["logout"])}</span></a>'
                       if context.AUTH_ENABLED and (password_authenticated or ip_authenticated) else "")
        nav = f"""
        <nav class="topnav" aria-label="{context.html.escape(t['nav_label'], quote=True)}">
          <div class="brandwrap">
            <a class="brand" href="/">{context.ui_icon('server')}<span>{context.html.escape(t['title'])}</span></a>
            {label_badge}
            {version_tag}
          </div>
          <div class="navlinks">
            {link('/', 'home')}
            {link('/changelog', 'changelog')}
            {link('/settings', 'settings') if context.AUTH_ENABLED and (password_authenticated or ip_authenticated) else ''}
            {logout_link}
          </div>
        </nav>
        """
    elif bare:
        nav = (f'<header class="app-login-header"><a class="app-login-brand" href="/">'
               f'{context.ui_icon("server")}<span>{context.html.escape(t["title"])}</span></a>'
               f'{label_badge}</header>')
    elif not bare:
        lang_menu = (f'<details class="language-menu"><summary>{context.html.escape(context.LANG_NAMES[lang])}</summary>'
                     f'<div class="language-options">{context.render_lang_switcher(lang)}</div></details>')
        theme_menu = context.render_theme_menu(lang)
        nav = f"""
        <nav class="topnav minimal" aria-label="{context.html.escape(t['nav_label'], quote=True)}">
          <div class="brandwrap">
            <a class="brand" href="/">{context.ui_icon('server')}<span>{context.html.escape(t['title'])}</span></a>
            {label_badge}
            <span class="version">{context.html.escape(context.VERSION_LABEL)}</span>
          </div>
          <div class="navlinks">{theme_menu}{lang_menu}</div>
        </nav>
        """
    if show_nav and active != 'home':
        destination = back_href or '/'
        destination_label = (t['access_security'] if destination == '/settings/security' else
                             t['settings'] if destination == '/settings' else
                             t['frps_heading'] if destination == '/frps' else
                             t['frp_client_heading'] if destination == '/frpc' else
                             t['frp_heading'] if destination == '/frp' else t['dashboard'])
        body = (f'<a class="page-back" href="{context.html.escape(destination, quote=True)}">'
                f'{context.html.escape(t["back_to"].format(destination=destination_label))}</a>' + body)
    history_guard = ('<script src="/static/auth-history.js"></script>'
                     if password_authenticated or ip_authenticated else '')
    return f"""<!doctype html>
<html lang="{context.HTML_LANG_TAGS.get(lang, lang)}"{context.RTL_ATTR.get(lang, "")}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{context.html.escape(page_title)}</title>
<link rel="icon" type="image/svg+xml" href="/static/favicon-{favicon}.svg">
<script src="/static/layout-motion.js"></script>
{history_guard}
<script>try{{var v=localStorage.getItem('vps-server-theme');if(['slate-blue','sage','teal','plum','ocean','olive','terracotta','indigo'].indexOf(v)>=0)document.documentElement.dataset.theme=v;if(localStorage.getItem('vps-server-mode')==='dark')document.documentElement.classList.add('dark')}}catch(e){{}}</script>
<link rel="stylesheet" href="/static/style.css">
<script src="/static/theme.js" defer></script>
<script src="/static/password-fields.js" defer></script>
<script src="/static/reference-select.js" defer></script>
</head>
<body{' class="login-page"' if bare else ''}>
{nav}
<main{' class="app-login-main"' if bare else ''}>
{body}
</main>
</body>
</html>"""
