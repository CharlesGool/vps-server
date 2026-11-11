"""One-click Windows setup for a console client certificate.

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


def windows_script_name(subject):
    return "vps-server-setup-" + subject.rsplit(" ", 1)[-1] + ".cmd"

