"""One-click setup for a console client certificate: Windows, macOS, Linux.

Each download makes Chrome (and Edge or Chromium where present) pick the
certificate for this console's addresses on its own, through the browser
policy AutoSelectCertificateForUrls, and imports the certificate when the
download carries it (only the copy offered right after issuing does).

Windows:

The download is a .cmd file so a double click runs it; its first lines hand
the rest of the file to PowerShell. It needs no administrator rights: the
certificate goes into the current user's store and the browser policy into
HKCU, which Chrome and Edge both read.

What it does, in order:
1. Looks for the certificate (by subject CN, with its private key) in
   Cert:\\CurrentUser\\My. When missing and a PKCS#12 bundle is embedded, asks
   for the import password and imports it with a non-exportable key.
2. For each of Chrome and Edge that is installed, writes
   AutoSelectCertificateForUrls entries for this console's addresses. Other
   entries are kept; entries for the same addresses are replaced; values are
   renumbered from 1, as the browsers require.
"""
import base64
import json
import plistlib
import uuid

LAUNCHER = ("@echo off\r\n"
            "powershell -NoProfile -ExecutionPolicy Bypass -Command "
            "\"$s = [IO.File]::ReadAllText('%~f0'); "
            "Invoke-Expression $s.Substring($s.IndexOf('#PS' + 'START'))\"\r\n"
            "echo.\r\n"
            "pause\r\n"
            "exit /b\r\n"
            "#PSSTART\r\n")

BODY = r"""
$ErrorActionPreference = 'Stop'
$subject = {subject}
$issuer = {issuer}
$patterns = @({patterns})
$bundle = {bundle}
try {
  $cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq "CN=$subject" -and $_.HasPrivateKey } | Select-Object -First 1
  if ($cert) {
    Write-Host {msg_found}
  } elseif ($bundle) {
    $password = Read-Host {msg_password} -AsSecureString
    $file = [IO.Path]::GetTempFileName()
    try {
      [IO.File]::WriteAllBytes($file, [Convert]::FromBase64String($bundle))
      Import-PfxCertificate -FilePath $file -CertStoreLocation Cert:\CurrentUser\My -Password $password | Out-Null
    } finally { Remove-Item $file -Force -ErrorAction SilentlyContinue }
    Write-Host {msg_imported}
  } else {
    Write-Host {msg_missing} -ForegroundColor Yellow
    exit 1
  }
  $browsers = @(
    @{ Name = 'Chrome'; Exe = 'chrome.exe'; Key = 'Google\Chrome' },
    @{ Name = 'Edge'; Exe = 'msedge.exe'; Key = 'Microsoft\Edge' })
  $done = 0
  foreach ($browser in $browsers) {
    $installed = $false
    foreach ($root in 'HKLM:', 'HKCU:') {
      if (Test-Path "$root\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\$($browser.Exe)") { $installed = $true }
    }
    if (-not $installed) { continue }
    $key = "HKCU:\SOFTWARE\Policies\$($browser.Key)\AutoSelectCertificateForUrls"
    if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
    $item = Get-Item $key
    $keep = @()
    foreach ($name in ($item.Property | Where-Object { $_ -match '^\d+$' } | Sort-Object { [int]$_ })) {
      $value = $item.GetValue($name)
      $pattern = $null
      try { $pattern = (ConvertFrom-Json $value).pattern } catch { }
      if ($patterns -notcontains $pattern) { $keep += $value }
    }
    foreach ($name in $item.Property) { Remove-ItemProperty -Path $key -Name $name }
    $rules = $keep + @($patterns | ForEach-Object {
      ConvertTo-Json -Compress @{ pattern = $_; filter = @{ ISSUER = @{ CN = $issuer }; SUBJECT = @{ CN = $subject } } } })
    $number = 1
    foreach ($rule in $rules) {
      New-ItemProperty -Path $key -Name "$number" -PropertyType String -Value $rule | Out-Null
      $number++
    }
    if (Test-Path "HKLM:\SOFTWARE\Policies\$($browser.Key)\AutoSelectCertificateForUrls") {
      Write-Host ({msg_machine} + $browser.Name) -ForegroundColor Yellow
    }
    Write-Host ({msg_browser} + $browser.Name)
    $done++
  }
  if ($done -eq 0) { Write-Host {msg_no_browser} -ForegroundColor Yellow; exit 1 }
  Write-Host {msg_done} -ForegroundColor Green
} catch {
  Write-Host ({msg_failed} + $_.Exception.Message) -ForegroundColor Red
  exit 1
}
"""

MESSAGES = ("found", "password", "imported", "missing", "machine", "browser", "no_browser", "done", "failed")


def _quote(text):
    """A PowerShell single-quoted literal: nothing inside is expanded."""
    return "'" + str(text).replace("'", "''") + "'"


def windows_script(t, subject, issuer, patterns, bundle=None):
    """The .cmd file's bytes (UTF-8, CRLF)."""
    values = {"subject": _quote(subject), "issuer": _quote(issuer),
              "patterns": ", ".join(_quote(pattern) for pattern in patterns),
              "bundle": _quote(base64.b64encode(bundle).decode("ascii") if bundle else "")}
    values.update({f"msg_{key}": _quote(t[f"cert_setup_{key}"]) for key in MESSAGES})
    body = BODY
    for name, value in values.items():
        body = body.replace("{" + name + "}", value)
    return (LAUNCHER + body.strip("\n").replace("\n", "\r\n") + "\r\n").encode("utf-8")


def _rules(subject, issuer, patterns):
    return [json.dumps({"pattern": pattern, "filter": {"ISSUER": {"CN": issuer}, "SUBJECT": {"CN": subject}}},
                       separators=(",", ":")) for pattern in patterns]


def macos_profile(t, subject, issuer, patterns, bundle=None):
    """A configuration profile (.mobileconfig), installed from System Settings.

    User scope: the identity goes into the login keychain, where Chrome looks.
    No password is stored; macOS asks for the import password while installing.
    One profile per host and certificate: a later download for the same
    certificate replaces it.
    """
    serial = subject.rsplit(" ", 1)[-1]
    base = "vps-server.client-cert." + serial
    rules = _rules(subject, issuer, patterns)

    def payload(kind, name, **extra):
        return {"PayloadType": kind, "PayloadVersion": 1, "PayloadIdentifier": f"{base}.{name}",
                "PayloadUUID": str(uuid.uuid4()).upper(), "PayloadDisplayName": subject, **extra}

    content = []
    if bundle:
        content.append(payload("com.apple.security.pkcs12", "identity", PayloadContent=bundle,
                               PayloadCertificateFileName=f"vps-server-{serial}.p12"))
    content += [payload("com.google.Chrome", "chrome", AutoSelectCertificateForUrls=rules),
                payload("com.microsoft.Edge", "edge", AutoSelectCertificateForUrls=rules)]
    profile = {"PayloadType": "Configuration", "PayloadVersion": 1, "PayloadIdentifier": base,
               "PayloadUUID": str(uuid.uuid4()).upper(), "PayloadScope": "User",
               "PayloadDisplayName": f"vps-server {subject}", "PayloadDescription": t["client_cert_autoselect"],
               "PayloadContent": content}
    return plistlib.dumps(profile)


LINUX = r"""#!/usr/bin/env bash
# vps-server: client certificate setup. Run it with: bash <this file>
set -euo pipefail
SUBJECT={subject}
BUNDLE={bundle}
say() { printf '%s\n' "$*"; }
fail() { say {msg_failed}; }
trap fail ERR
if [ -n "$BUNDLE" ]; then
  command -v pk12util >/dev/null && command -v certutil >/dev/null || { say {msg_nss}; exit 1; }
  db="$HOME/.pki/nssdb"
  mkdir -p "$db"
  [ -f "$db/cert9.db" ] || certutil -d "sql:$db" -N --empty-password
  if certutil -d "sql:$db" -L | grep -qF "${SUBJECT##* }"; then
    say {msg_found}
  else
    file="$(mktemp)"
    printf '%s' "$BUNDLE" | base64 -d > "$file"
    say {msg_password}
    pk12util -d "sql:$db" -i "$file" || { rm -f "$file"; exit 1; }
    rm -f "$file"
    say {msg_imported_linux}
  fi
fi
SUDO=''
[ "$(id -u)" -eq 0 ] || SUDO=sudo
done=0
for entry in 'google-chrome google-chrome-stable:/etc/opt/chrome/policies/managed:Chrome'              'chromium chromium-browser:/etc/chromium/policies/managed:Chromium'              'microsoft-edge microsoft-edge-stable:/etc/opt/edge/policies/managed:Edge'; do
  commands="${entry%%:*}"; rest="${entry#*:}"; dir="${rest%%:*}"; name="${rest#*:}"
  found=''
  for command in $commands; do command -v "$command" >/dev/null && found=1; done
  [ -n "$found" ] || continue
  $SUDO mkdir -p "$dir"
  $SUDO python3 - "$dir/vps-server.json" {rules} <<'PY'
import json, os, sys
path, rules = sys.argv[1], sys.argv[2:]
mine = {json.loads(rule)["pattern"] for rule in rules}
try:
    with open(path) as handle:
        data = json.load(handle)
except (OSError, ValueError):
    data = {}
kept = []
for rule in data.get("AutoSelectCertificateForUrls", []):
    try:
        pattern = json.loads(rule).get("pattern")
    except (TypeError, ValueError, AttributeError):
        pattern = None
    if pattern not in mine:
        kept.append(rule)
data["AutoSelectCertificateForUrls"] = kept + rules
with open(path + ".tmp", "w") as handle:
    json.dump(data, handle, indent=2)
os.chmod(path + ".tmp", 0o644)
os.replace(path + ".tmp", path)
PY
  say {msg_browser}"$name"
  done=1
done
[ "$done" = 1 ] || { say {msg_no_browser}; exit 1; }
say {msg_done_linux}
"""


def _sh(text):
    """A POSIX shell single-quoted literal."""
    return "'" + str(text).replace("'", "'\\''") + "'"


def linux_script(t, subject, issuer, patterns, bundle=None):
    """A bash script: NSS database import plus a merged Chrome/Chromium/Edge policy file."""
    values = {"subject": _sh(subject), "bundle": _sh(base64.b64encode(bundle).decode("ascii") if bundle else ""),
              "rules": " ".join(_sh(rule) for rule in _rules(subject, issuer, patterns)),
              "msg_nss": _sh(t["cert_setup_nss_missing"]),
              "msg_imported_linux": _sh(t["cert_setup_imported_linux"]), "msg_done_linux": _sh(t["cert_setup_done_linux"])}
    values.update({f"msg_{key}": _sh(t[f"cert_setup_{key}"]) for key in MESSAGES})
    body = LINUX
    for name, value in values.items():
        body = body.replace("{" + name + "}", value)
    return body.encode("utf-8")


EXTENSIONS = {"windows": ".cmd", "macos": ".mobileconfig", "linux": ".sh"}


def file_name(system, subject):
    return "vps-server-setup-" + subject.rsplit(" ", 1)[-1] + EXTENSIONS[system]

