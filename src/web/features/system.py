"""System services with host supplied as context."""


def _cmd_output(context, cmd):
    """Stdout of `cmd` if it succeeded, empty string otherwise. Never raises."""
    try:
        result = context.subprocess.run(
            cmd, stdout=context.subprocess.PIPE, stderr=context.subprocess.DEVNULL,
            check=False, text=True,
        )
    except OSError:
        return ""
    return result.stdout if result.returncode == 0 else ""

def _run_quiet(context, cmd):
    try:
        return context.subprocess.run(
            cmd, stdout=context.subprocess.DEVNULL, stderr=context.subprocess.DEVNULL, check=False
        ).returncode == 0
    except OSError:
        return False

def firewall_backend(context, ):
    """Which firewall is actually running, or None.

    `ufw status` exits 0 whether or not ufw is enabled, so the exit code alone
    would happily "open" a port in a firewall that is not filtering anything
    and report success.
    """
    if context.shutil.which("ufw") and "Status: active" in context._cmd_output(["ufw", "status"]):
        return "ufw"
    if context.shutil.which("firewall-cmd") and context._cmd_output(["firewall-cmd", "--state"]).strip() == "running":
        return "firewalld"
    if context.shutil.which("iptables"):
        return "iptables"
    return None

def firewall_port(context, port, opening):
    """Open or close `port`/tcp. Best effort; returns True if a rule was applied.

    A host with no firewall, or one managed by something not handled here,
    must still get a usable window — so a failure is reported to stderr and
    otherwise ignored rather than blocking the operator.
    """
    backend = context.firewall_backend()
    if backend == "ufw":
        cmd = ["ufw", "allow", f"{port}/tcp"] if opening else \
              ["ufw", "delete", "allow", f"{port}/tcp"]
    elif backend == "firewalld":
        flag = "--add-port" if opening else "--remove-port"
        cmd = ["firewall-cmd", f"{flag}={port}/tcp"]
    elif backend == "iptables":
        flag = "-I" if opening else "-D"
        cmd = ["iptables", flag, "INPUT", "-p", "tcp", "--dport", str(port),
               "-j", "ACCEPT"]
    else:
        return False
    if context._run_quiet(cmd):
        return True
    print(context._log_text('log_firewall_open' if opening else 'log_firewall_close', port=port, backend=backend), file=context.sys.stderr)
    return False
