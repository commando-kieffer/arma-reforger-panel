"""Finding, starting and stopping the dedicated server process."""

import os
import signal
import subprocess
import time

from .. import config

SERVER_BINARY = "./ArmaReforgerServer"
SERVER_NAME = "ArmaReforgerServer"

# The systemd unit install.sh creates for the server. It restarts the server
# when it dies from a signal other than SIGINT, SIGTERM, SIGHUP or SIGPIPE.
SYSTEMD_UNIT = "arma-server.service"

PROC_DIR = "/proc"

# Force stop: how long the server gets to quit after SIGINT, then how long to
# wait for SIGKILL to take effect.
INTERRUPT_WAIT = 10.0
KILL_WAIT = 5.0
POLL_INTERVAL = 0.25


def build_server_args():
    """Build the launch arguments. `-loadSessionSave` is always passed: with no
    save files it's a no-op, and including it keeps panel-launched and
    systemd-launched starts behaving the same way. Whether new saves are made
    is set in config.json by the Persistence card (services/persistence.py)."""
    args = ["-config", config.SERVER_CONFIG, "-loadSessionSave"]
    if config.MAX_FPS:
        args.append(f"-maxFPS={config.MAX_FPS}")
    return args


def find_server_pids():
    """Pids of every running server process, oldest first.

    A process counts when the program it runs (argv[0]) is the server binary,
    so an editor or a `tail` with the binary's name in its arguments doesn't.
    Exited processes waiting to be reaped have no command line and don't
    count either.
    """
    try:
        names = os.listdir(PROC_DIR)
    except OSError:
        return []
    return sorted(int(name) for name in names
                  if name.isdigit() and int(name) != os.getpid() and _is_server(int(name)))


def get_server_pid():
    pids = find_server_pids()
    return pids[0] if pids else None


def get_process_uptime(pid):
    try:
        r = subprocess.run(["ps", "-o", "etimes=", "-p", str(pid)], capture_output=True, text=True)
        return int(r.stdout.strip())
    except Exception:
        return 0


def format_uptime(seconds):
    if seconds < 60:    return f"{seconds}s"
    if seconds < 3600:  return f"{seconds // 60}m {seconds % 60}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def start_server():
    """Launch the server detached from the panel so it survives panel restarts."""
    subprocess.Popen([SERVER_BINARY] + build_server_args(), cwd=config.SERVER_DIR,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    time.sleep(1)


def stop_server(pid):
    subprocess.run(["kill", str(pid)], check=True)


def force_stop():
    """Stop every server process, even one that ignores a normal stop: SIGINT
    first, then SIGKILL for the processes still there after INTERRUPT_WAIT.

    Returns {"found": pids, "killed": pids that needed SIGKILL, "remaining":
    pids still running at the end, "denied": pids the panel may not signal,
    "systemd": whether a process belonged to the arma-server unit}.
    """
    found = find_server_pids()
    result = {"found": found, "killed": [], "remaining": [], "denied": [],
              "systemd": any(_in_systemd_unit(pid) for pid in found)}
    alive = _signal(found, signal.SIGINT, result["denied"])
    alive = _wait_for_exit(alive, INTERRUPT_WAIT)
    if alive:
        result["killed"] = alive
        alive = _wait_for_exit(_signal(alive, signal.SIGKILL, result["denied"]), KILL_WAIT)
    result["remaining"] = sorted(set(alive) | set(result["denied"]))
    return result


def _signal(pids, sig, denied):
    """Send `sig` to `pids`; return the ones that got it."""
    sent = []
    for pid in pids:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            continue
        except PermissionError:
            if pid not in denied:
                denied.append(pid)
            continue
        sent.append(pid)
    return sent


def _wait_for_exit(pids, timeout):
    """The pids still running server processes after up to `timeout` seconds."""
    deadline = time.monotonic() + timeout
    alive = [pid for pid in pids if _is_server(pid)]
    while alive and time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)
        alive = [pid for pid in alive if _is_server(pid)]
    return alive


def _is_server(pid):
    # The pid is read again each time, so a pid reused by another program
    # after the server exited isn't mistaken for it.
    try:
        with open(os.path.join(PROC_DIR, str(pid), "cmdline"), "rb") as f:
            argv0 = f.read().split(b"\0", 1)[0]
    except OSError:
        return False
    return os.path.basename(argv0.decode("utf-8", "replace")) == SERVER_NAME


def _in_systemd_unit(pid):
    try:
        with open(os.path.join(PROC_DIR, str(pid), "cgroup"), encoding="utf-8") as f:
            return any(line.rstrip("\n").endswith("/" + SYSTEMD_UNIT) for line in f)
    except OSError:
        return False
