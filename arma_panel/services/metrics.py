"""CPU and memory usage of the host and of the server process."""

import subprocess


def get_cpu_count():
    try:
        r = subprocess.run(["nproc"], capture_output=True, text=True)
        return max(1, int(r.stdout.strip()))
    except Exception:
        return 1


def get_cpu_ram(pid):
    """Return (cpu %, rss MB) for `pid`. CPU is normalised to the whole host."""
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "pcpu=,rss="], capture_output=True, text=True)
        parts = r.stdout.strip().split()
        cpu = round(float(parts[0]) / get_cpu_count(), 1)
        ram = round(int(parts[1]) / 1024, 1)
        return cpu, ram
    except Exception:
        return 0.0, 0.0


def get_system_ram():
    """Return (used MB, total MB) from /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem = {l.split()[0].rstrip(":"): int(l.split()[1]) for l in lines if len(l.split()) >= 2}
        total = round(mem["MemTotal"] / 1024, 1)
        used  = round((mem["MemTotal"] - mem["MemAvailable"]) / 1024, 1)
        return used, total
    except Exception:
        return 0, 0
