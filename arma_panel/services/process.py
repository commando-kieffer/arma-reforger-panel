"""Finding, starting and stopping the dedicated server process."""

import subprocess
import time

from .. import config

SERVER_BINARY = "./ArmaReforgerServer"


def build_server_args():
    """Build the launch arguments. `-loadSessionSave` is always passed: with no
    save files it's a no-op, and including it keeps panel-launched and
    systemd-launched starts behaving the same way. The 'enabled' toggle in the
    UI controls only the `persistence` block in config.json (autosave)."""
    args = ["-config", config.SERVER_CONFIG, "-loadSessionSave"]
    if config.MAX_FPS:
        args.append(f"-maxFPS={config.MAX_FPS}")
    return args


def get_server_pid():
    try:
        r = subprocess.run(["pgrep", "-f", "ArmaReforgerServer"], capture_output=True, text=True)
        pids = r.stdout.strip().splitlines()
        return int(pids[0]) if pids else None
    except Exception:
        return None


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
