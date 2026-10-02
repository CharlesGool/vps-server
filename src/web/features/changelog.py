"""Changelog pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class ChangelogMixin:
    def page_changelog(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        # Follow the UI language and make a missing translation visible.
        localized = self.context.CHANGELOG_PATHS.get(lang)
        fallback = self.context.BASE_DIR / "doc" / "en" / "CHANGELOG.md"
        path = localized if localized and localized.exists() else fallback
        notice = ""
        if localized and path != localized:
            notice = f'<p class="muted small">{self.context.html.escape(t["changelog_fallback"])}</p>'

        source = path.read_text(encoding="utf-8") if path.exists() else ""
        section = self.context.changelog_section(source)
        development = ""
        if self.context.VERSION.startswith(("dev-", "test-")):
            log_path = self.context.BASE_DIR / "doc" / "en" / "LOG.md"
            updates = self.context.development_updates_section(log_path.read_text(encoding="utf-8")) if log_path.exists() else None
            if not updates and path != fallback:
                english = self.context.BASE_DIR / "doc" / "LOG.md"
                updates = self.context.development_updates_section(english.read_text(encoding="utf-8")) if english.exists() else None
                if updates:
                    development = f'<p class="muted small">{self.context.html.escape(t["development_fallback"])}</p>'
            if updates:
                development += self.context.render_changelog(f"### {self.context.VERSION_LABEL}\n{updates}")
        if section:
            content = development + notice + self.context.render_changelog(section)
        else:
            # Missing file or section must not render other LOG modules as release notes.
            content = development + f'<p class="muted">{self.context.html.escape(t["changelog_missing"])}</p>'
        body = f"""
        <div class="card wide">
          <h1>{self.context.html.escape(t['changelog'])} <span class="version-inline">{self.context.html.escape(self.context.VERSION_LABEL)}</span></h1>
          <div class="changelog">
          {content}
          </div>
        </div>
        """
        self.send_html(200, self.render_page(t['changelog'], body, lang, active="changelog"),
                       self.maybe_lang_cookie(query_lang))

    def route_changelog(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/changelog":
            self.page_changelog(lang, query_lang)
            return True
        return False
