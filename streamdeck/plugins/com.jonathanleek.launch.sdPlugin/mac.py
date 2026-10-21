"""Sources about this Mac: the load dial and the containers key.

Everything here is read without sudo or extra tools: CPU ticks from the
kernel (host_statistics), GPU utilisation from the IOAccelerator's
PerformanceStatistics in ioreg, memory from vm_stat and the kernel's
pressure level, processes from ps, containers from OrbStack's docker CLI.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import re
import subprocess

import render
from sources import Source, View, source

DOCKER = "/usr/local/bin/docker"  # OrbStack's CLI

# ---- readers (each returns plain numbers so tests can stub them) ----


class _Ticks:
    """CPU busy % since the previous call, from host_statistics."""

    def __init__(self) -> None:
        self.lib = ctypes.CDLL(ctypes.util.find_library("System"))
        self.lib.mach_host_self.restype = ctypes.c_uint
        self.prev: list[int] | None = None

    def read(self) -> list[int]:
        info = (ctypes.c_uint * 4)()  # user, system, idle, nice
        n = ctypes.c_uint(4)
        if self.lib.host_statistics(self.lib.mach_host_self(), 3, info, ctypes.byref(n)) != 0:  # HOST_CPU_LOAD_INFO
            raise OSError("host_statistics failed")
        return list(info)

    def percent(self) -> float:
        now = self.read()
        prev, self.prev = self.prev, now
        if prev is None:
            return 0.0
        d = [b - a for a, b in zip(prev, now)]
        total = sum(d)
        return 100.0 * (d[0] + d[1] + d[3]) / total if total else 0.0


_ticks: _Ticks | None = None


def cpu_percent() -> float:
    global _ticks
    if _ticks is None:
        _ticks = _Ticks()
    return _ticks.percent()


def gpu_percent() -> float:
    out = subprocess.run(["ioreg", "-r", "-d", "1", "-c", "IOAccelerator"], capture_output=True, text=True, timeout=3).stdout
    values = [int(v) for v in re.findall(r'"Device Utilization %"=(\d+)', out)]
    return float(max(values, default=0))


def memory() -> tuple[float, float, int]:
    """(used GB, total GB, pressure 1 normal / 2 warn / 4 critical).
    Used is Activity Monitor's: app (anonymous - purgeable) + wired + compressed."""
    out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=3).stdout
    page = int(re.search(r"page size of (\d+) bytes", out).group(1))
    pages = {k.strip(): int(v) for k, v in re.findall(r"^([^:]+):\s+(\d+)\.", out, re.M)}
    used = (
        pages["Anonymous pages"] - pages["Pages purgeable"]
        + pages["Pages wired down"] + pages["Pages occupied by compressor"]
    ) * page
    total = int(_sysctl("hw.memsize"))
    pressure = int(_sysctl("kern.memorystatus_vm_pressure_level"))
    return used / 2**30, total / 2**30, pressure


def _sysctl(name: str) -> str:
    return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=3, check=True).stdout.strip()


def top_processes(by: str, n: int = 3) -> list[tuple[str, float, float]]:
    """[(name, cpu % of one core, rss GB)] sorted by "cpu" or "mem"."""
    out = subprocess.run(
        ["ps", "-Aceo", "pcpu=,rss=,comm=", "-r" if by == "cpu" else "-m"],
        capture_output=True, text=True, timeout=3,
    ).stdout
    rows = []
    for line in out.splitlines()[:n]:
        cpu, rss, name = line.split(None, 2)
        rows.append((name, float(cpu), int(rss) / 2**20))
    return rows


def running_containers() -> list[str] | None:
    """Compose project (or container name) per running container; None if
    OrbStack isn't running."""
    try:
        r = subprocess.run(
            [DOCKER, "ps", "--format", '{{.Label "com.docker.compose.project"}}\t{{.Names}}'],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    out = []
    for line in r.stdout.splitlines():
        project, _, name = line.partition("\t")
        out.append(project or name)
    return out


# ---- load dial ----

C_CPU = "#c7781c"
C_GPU = "#2f8f83"
C_MEM = {1: "#4a7fc1", 2: "#c7a21c", 4: "#c0392b"}  # by pressure level
VIEWS = ["overview", "cpu", "mem"]


def _gb(x: float) -> str:
    return f"{x:.0f}G" if x >= 10 else f"{x:.1f}G"


@source("load")
class Load(Source):
    """Turn: overview -> top CPU -> top memory. Press runs the dial's argv
    (Activity Monitor), handled by the plugin."""

    interval = 2.0

    def rotate(self, ctx, ticks):
        ctx.state["view"] = (ctx.state.get("view", 0) + ticks) % len(VIEWS)

    def view(self, ctx):
        which = VIEWS[ctx.state.get("view", 0)]
        if which == "overview":
            cpu, gpu = cpu_percent(), gpu_percent()
            used, total, pressure = memory()
            mem = 100.0 * used / total if total else 0.0
            return View(layout="layouts/load.json", feedback={
                "cpu_bar": {"value": round(cpu), "bar_fill_c": C_CPU},
                "cpu_val": f"{cpu:.0f}%",
                "gpu_bar": {"value": round(gpu), "bar_fill_c": C_GPU},
                "gpu_val": f"{gpu:.0f}%",
                "mem_bar": {"value": round(mem), "bar_fill_c": C_MEM.get(pressure, C_MEM[4])},
                "mem_val": _gb(used),
            })
        cpu_percent()  # keep the tick baseline fresh for when we turn back
        rows = top_processes(which)
        feedback: dict = {"head": "Top CPU" if which == "cpu" else "Top memory"}
        for i in range(3):
            name, pcpu, rss = rows[i] if i < len(rows) else ("", 0.0, 0.0)
            feedback[f"name{i}"] = name
            feedback[f"val{i}"] = "" if not name else f"{pcpu:.0f}%" if which == "cpu" else _gb(rss)
        return View(layout="layouts/top.json", feedback=feedback)


# ---- containers key ----


def _project(name: str) -> str:
    return re.sub(r"_[0-9a-f]{6}$", "", name)  # astro dev's project_<hash>


@source("containers")
class Containers(Source):
    """Running containers and their project. Press runs the key's argv (open
    OrbStack); holding stops every running container."""

    interval = 5.0

    def view(self, ctx):
        running = running_containers()
        if running is None:
            return View(image=render.tile(["off"], render.C_BASE, footer="OrbStack", fg=render.C_DIM))
        if not running:
            return View(image=render.tile(["0"], render.C_BASE, footer="containers", fg=render.C_DIM))
        projects = sorted({_project(p) for p in running})
        footer = projects[0] if len(projects) == 1 else f"{len(projects)} projects"
        if len(footer) > 15:  # about what fits under a key at 15px
            footer = footer[:14] + "…"
        return View(image=render.tile([str(len(running))], render.C_REPO, footer=footer))

    def hold(self, ctx):
        ids = subprocess.run([DOCKER, "ps", "-q"], capture_output=True, text=True, timeout=3).stdout.split()
        if ids:
            # stopping takes a while; don't block the plugin's event loop
            subprocess.Popen([DOCKER, "stop", *ids], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
