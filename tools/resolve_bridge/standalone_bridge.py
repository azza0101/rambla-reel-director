"""Standalone RMBL B ROLL bridge launched by DaVinci Resolve."""
from __future__ import annotations

from dataclasses import dataclass
import json
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable
import tkinter as tk

APP_ROOT = Path(__file__).resolve().parents[2]
def current_desktop_name() -> str:
    if os.name != 'nt':
        return 'Default'
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    user32.GetThreadDesktop.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    handle = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
    name = ctypes.create_unicode_buffer(512)
    needed = wintypes.DWORD()
    if not user32.GetUserObjectInformationW(handle, 2, name, ctypes.sizeof(name), ctypes.byref(needed)):
        raise OSError('Cannot identify the desktop for the bridge instance lock')
    return name.value


def instance_port_for_desktop(name: str) -> int:
    if name.casefold() == 'default':
        return 38742
    return 41000 + int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % 10000


DESKTOP_NAME = current_desktop_name()
INSTANCE_PORT = instance_port_for_desktop(DESKTOP_NAME)
RELEASE_VERSION = (APP_ROOT / "RAMBLA_VERSION").read_text(encoding="utf-8").strip()


def bridge_build_token() -> str:
    return hashlib.sha256(Path(__file__).read_bytes() + (APP_ROOT / 'RAMBLA_VERSION').read_bytes()).hexdigest()


LOADED_BUILD = bridge_build_token()


def default_destination() -> str:
    if os.environ.get("RAMBLA_BRIDGE_DESTINATION_EXPLICIT") != "1":
        return "active"
    value = os.environ.get("RAMBLA_BRIDGE_DESTINATION", "active")
    return value if value in {"active", "new"} else "active"


def window_geometry(screen_width: int, screen_height: int, *, requested_height: int, package_visible: bool) -> str:
    """Return a useful bridge size without extending below the Windows work area."""
    preferred_width = 660 if package_visible and screen_width >= 1600 else 600
    width = min(preferred_width, max(520, screen_width - 80))
    wanted = max(840, requested_height + 60) if package_visible else max(680, requested_height + 40)
    height = min(wanted, max(560, screen_height - 80))
    return f"{width}x{height}"


def draw_bridge_mark(canvas: Any) -> None:
    """Draw the bridge identity from the same geometry as the RMBL mark."""
    canvas.create_line(8, 37, 64, 37, fill="#d8ff5b", width=4)
    canvas.create_arc(13, 9, 59, 55, start=0, extent=180, style="arc", outline="#f7f8ff", width=5)
    canvas.create_line(18, 23, 18, 42, fill="#f7f8ff", width=4)
    canvas.create_line(54, 23, 54, 42, fill="#f7f8ff", width=4)
    canvas.create_oval(32, 30, 40, 38, fill="#7c6cf2", outline="")


def _photo_line(image: Any, color: str, start: tuple[int, int], end: tuple[int, int], width: int = 2) -> None:
    """Small deterministic raster line helper for the native Tk title-bar icon."""
    x0, y0 = start; x1, y1 = end
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    error = dx + dy
    while True:
        radius = max(0, width // 2)
        image.put(color, to=(max(0, x0 - radius), max(0, y0 - radius), min(96, x0 + radius + 1), min(96, y0 + radius + 1)))
        if x0 == x1 and y0 == y1:
            break
        twice = 2 * error
        if twice >= dy:
            error += dy; x0 += sx
        if twice <= dx:
            error += dx; y0 += sy


def build_bridge_icon(tk: Any, logo_path: Path) -> Any:
    """Compose the supplied RMBL mark with a bridge above it for this app only."""
    icon = tk.PhotoImage(width=96, height=96)
    icon.put("#181d39", to=(0, 0, 96, 96))
    original = tk.PhotoImage(file=str(logo_path))
    scaled = original.subsample(17, 17)
    icon.tk.call(str(icon), "copy", str(scaled), "-to", 13, 25)
    # Suspension bridge overlay: towers, cables and lime deck sit above the RMBL mark.
    icon.put("#f7f8ff", to=(18, 7, 24, 31)); icon.put("#f7f8ff", to=(72, 7, 78, 31))
    _photo_line(icon, "#f7f8ff", (21, 8), (48, 23), 3)
    _photo_line(icon, "#f7f8ff", (48, 23), (75, 8), 3)
    _photo_line(icon, "#f7f8ff", (21, 8), (8, 22), 3)
    _photo_line(icon, "#f7f8ff", (75, 8), (88, 22), 3)
    icon.put("#d8ff5b", to=(7, 28, 89, 34))
    return icon


def _rounded_points(x1: int, y1: int, x2: int, y2: int, radius: int) -> list[int]:
    radius = min(radius, max(1, (x2 - x1) // 2), max(1, (y2 - y1) // 2))
    return [x1+radius,y1, x2-radius,y1, x2,y1, x2,y1+radius, x2,y2-radius,
            x2,y2, x2-radius,y2, x1+radius,y2, x1,y2, x1,y2-radius,
            x1,y1+radius, x1,y1]


class RoundedPanel(tk.Canvas):
    def __init__(self, parent: Any, *, fill: str = "#202746", outline: str = "#3d456d", height: int = 90, radius: int = 18, padding: int = 16):
        super().__init__(parent, height=height, bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.fill, self.outline, self.radius, self.padding = fill, outline, radius, padding
        self.body = tk.Frame(self, bg=fill)
        self._window = self.create_window(padding, padding, anchor="nw", window=self.body)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _event: Any = None) -> None:
        width, height = max(2, self.winfo_width()), max(2, self.winfo_height())
        self.delete("panel-bg")
        self.create_polygon(_rounded_points(1, 1, width-1, height-1, self.radius), smooth=True,
                            splinesteps=24, fill=self.fill, outline=self.outline, width=1, tags="panel-bg")
        self.tag_lower("panel-bg")
        self.itemconfigure(self._window, width=max(1, width-self.padding*2), height=max(1, height-self.padding*2))


class RoundedButton(tk.Canvas):
    def __init__(self, parent: Any, *, text: str, command: Callable[[], None], accent: bool = False, state: str = "normal"):
        super().__init__(parent, height=40, bg=parent.cget("bg"), highlightthickness=0, bd=0, cursor="hand2")
        self._text, self._command, self._accent, self._state, self._hover = text, command, accent, state, False
        self.bind("<Configure>", self._draw); self.bind("<Enter>", self._enter); self.bind("<Leave>", self._leave); self.bind("<Button-1>", self._click)

    def configure(self, cnf: Any = None, **kwargs: Any) -> Any:
        if "state" in kwargs:
            self._state = str(kwargs.pop("state"))
            super().configure(cursor="arrow" if self._state == "disabled" else "hand2")
        if "text" in kwargs:
            self._text = str(kwargs.pop("text"))
        result = super().configure(cnf, **kwargs) if cnf is not None or kwargs else None
        self._draw()
        return result

    config = configure

    def _enter(self, _event: Any) -> None: self._hover = True; self._draw()
    def _leave(self, _event: Any) -> None: self._hover = False; self._draw()
    def _click(self, _event: Any) -> None:
        if self._state != "disabled": self._command()

    def _draw(self, _event: Any = None) -> None:
        self.delete("all")
        width, height = max(20, self.winfo_width()), max(20, self.winfo_height())
        if self._state == "disabled": fill, outline, ink = "#282d4b", "#3a4164", "#747b9d"
        elif self._accent: fill, outline, ink = (("#e6ff84", "#efffae", "#111522") if self._hover else ("#d8ff5b", "#e8ff98", "#111522"))
        else: fill, outline, ink = (("#514d8d", "#8c82ee", "#ffffff") if self._hover else ("#343b62", "#575f8d", "#f7f8ff"))
        self.create_polygon(_rounded_points(1, 1, width-1, height-1, 14), smooth=True, splinesteps=24, fill=fill, outline=outline, width=1)
        self.create_text(width/2, height/2, text=self._text, fill=ink, font=("Segoe UI Semibold", 10))


class CompactChoiceRow(tk.Canvas):
    """Compact click row that lights up when the option is selected."""
    def __init__(self, parent: Any, *, title: str, description: str, variable: Any):
        super().__init__(parent, height=50, bg=parent.cget("bg"), highlightthickness=0, bd=0, cursor="hand2")
        self.title, self.description, self.variable = title, description, variable
        self.bind("<Configure>", self._draw); self.bind("<Button-1>", self._toggle)
        variable.trace_add("write", lambda *_: self._draw())

    def _toggle(self, _event: Any = None) -> None:
        self.variable.set(not bool(self.variable.get()))

    def _draw(self, _event: Any = None) -> None:
        self.delete("all"); width=max(200,self.winfo_width()); active=bool(self.variable.get())
        fill,outline=("#292951","#8f82ff") if active else ("#171c35","#343c65")
        self.create_polygon(_rounded_points(1,1,width-1,49,13),smooth=True,splinesteps=24,fill=fill,outline=outline,width=2 if active else 1)
        if active:self.create_polygon(_rounded_points(2,8,7,42,3),smooth=True,fill="#d8ff5b",outline="")
        self.create_text(15,17,text=self.title,anchor="w",fill="#ffffff" if active else "#dce0f2",font=("Segoe UI Semibold",9))
        self.create_text(15,35,text=self.description,anchor="w",fill="#c5cae1" if active else "#8f97b8",font=("Segoe UI",8))
        self.create_text(width-18,25,text="✓" if active else "",anchor="e",fill="#d8ff5b",font=("Segoe UI Semibold",12))


class DestinationCard(tk.Canvas):
    """Mutually exclusive destination card with an explicit selected state."""
    def __init__(self, parent: Any, *, title: str, description: str, value: str, variable: Any, recommended: bool = False, on_select: Callable[[str], None] | None = None):
        super().__init__(parent, height=58, bg=parent.cget("bg"), highlightthickness=0, bd=0, cursor="hand2")
        self.title,self.description,self.value,self.variable,self.recommended=title,description,value,variable,recommended
        self.bind("<Configure>",self._draw); self.bind("<Button-1>",lambda _event:(on_select or variable.set)(value))
        variable.trace_add("write",lambda *_:self._draw())

    def _draw(self, _event: Any = None) -> None:
        self.delete("all"); width=max(200,self.winfo_width()); selected=self.variable.get()==self.value
        fill,outline=("#25304c","#d8ff5b") if selected else ("#171c35","#343c65")
        self.create_polygon(_rounded_points(1,1,width-1,57,13),smooth=True,splinesteps=24,fill=fill,outline=outline,width=2 if selected else 1)
        self.create_oval(14,18,32,36,fill=fill,outline="#d8ff5b" if selected else "#697193",width=2)
        if selected:self.create_oval(19,23,27,31,fill="#d8ff5b",outline="")
        self.create_text(42,17,text=self.title,anchor="w",fill="#f7f8ff",font=("Segoe UI Semibold",9))
        self.create_text(42,39,text=self.description,anchor="w",fill="#b8bfd9",font=("Segoe UI",8))
        if self.recommended:
            self.create_text(width-14,17,text="PREDEFINITA",anchor="e",fill="#d8ff5b",font=("Segoe UI Semibold",7))


class ProgressBar(tk.Canvas):
    def __init__(self, parent: Any):
        super().__init__(parent, height=12, bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.value = 0
        self.bind("<Configure>", self._draw)

    def configure(self, cnf: Any = None, **kwargs: Any) -> Any:
        if "value" in kwargs: self.value = max(0, min(100, int(kwargs.pop("value") or 0)))
        result = super().configure(cnf, **kwargs) if cnf is not None or kwargs else None
        self._draw(); return result

    config = configure

    def _draw(self, _event: Any = None) -> None:
        self.delete("all"); width=max(2,self.winfo_width())
        self.create_polygon(_rounded_points(0,1,width,11,5),smooth=True,fill="#29304f",outline="")
        if self.value:
            filled=max(10,int(width*self.value/100))
            self.create_polygon(_rounded_points(0,1,filled,11,5),smooth=True,fill="#d8ff5b",outline="")


class StatusPill(RoundedPanel):
    def __init__(self, parent: Any):
        super().__init__(parent, fill="#30202a", outline="#774052", height=46, radius=14, padding=11)
        self.label = tk.Label(self.body, text="● CONNESSIONE IN CORSO", bg=self.fill, fg="#ff9d9d", font=("Segoe UI Semibold", 10), anchor="w")
        self.label.pack(fill="both", expand=True)

    def configure(self, cnf: Any = None, **kwargs: Any) -> Any:
        text = kwargs.pop("text", None); style = kwargs.pop("style", None)
        if style:
            ready = style == "Lime.TLabel"
            self.fill, self.outline = (("#173a2b", "#3f8b61") if ready else ("#30202a", "#774052"))
            self.body.configure(bg=self.fill); self.label.configure(bg=self.fill, fg="#d8ff5b" if ready else "#ff9d9d")
        if text is not None: self.label.configure(text=text)
        result = super().configure(cnf, **kwargs) if cnf is not None or kwargs else None
        self._redraw(); return result

    config = configure


def discover_base() -> str:
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))
    from launch_local_v5 import source_build_token
    expected_build = source_build_token(APP_ROOT)
    candidates = []
    for port in range(8810, 8820):
        try:
            url = f"http://127.0.0.1:{port}"
            with urllib.request.urlopen(url + "/health", timeout=.3) as response:
                row = json.loads(response.read().decode())
            if row.get("status") == "ok" and row.get('build_token') == expected_build:
                candidates.append((port, url))
        except Exception:
            pass
    return max(candidates)[1] if candidates else ""


def http_request(base: str, path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=320 if path.endswith("/capture") else 12) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode()).get("detail")
        except Exception:
            detail = None
        raise RuntimeError(detail or f"RMBL B ROLL HTTP {exc.code}") from exc


class ServerTransport:
    """HTTP transport that rediscovers RMBL B ROLL after a port change."""
    def __init__(self) -> None:
        self.base = ""
        self.launch_attempted = 0.0

    def __call__(self, path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.base:
            self.base = discover_base()
        if not self.base:
            if not self.launch_attempted or time.monotonic() - self.launch_attempted > 20:
                self.launch_attempted = time.monotonic()
                launcher = APP_ROOT / "RAMBLA_REEL_DIRECTOR.vbs"
                if os.name == "nt" and launcher.is_file():
                    subprocess.Popen(["wscript.exe", str(launcher)], creationflags=0x08000000)
            raise RuntimeError("RMBL B ROLL non è aperta")
        try:
            return http_request(self.base, path, method, payload)
        except (OSError, urllib.error.URLError):
            self.base = discover_base()
            if not self.base:
                raise RuntimeError("RMBL B ROLL non è raggiungibile")
            return http_request(self.base, path, method, payload)


@dataclass(frozen=True)
class BridgeSnapshot:
    connected: bool
    status: dict[str, Any]
    package: dict[str, Any] | None
    error: str = ""


class BridgeClient:
    def __init__(self, *, request_json: Callable[..., dict[str, Any]], session_id: str | None = None):
        self.request_json = request_json
        self.session_id = session_id or uuid.uuid4().hex
        self.current_package: dict[str, Any] | None = None

    def poll_once(self) -> BridgeSnapshot:
        try:
            session = self.request_json("/api/curation/resolve-bridge/session", "POST", {"bridge_session_id": self.session_id})
            self.session_id = str(session.get("bridge_session_id") or self.session_id)
            status = self.request_json("/api/curation/resolve-bridge/status")
            if not status.get("connected"):
                return BridgeSnapshot(False, status, None, str(status.get("detail") or "Resolve non collegato"))
            # The focused timeline may already be a generated v1/v2. Filtering
            # by its id would hide a valid source-timeline package.
            query = urllib.parse.urlencode({"resolve_project": status.get("project", ""), "bridge_session_id": self.session_id})
            rows = self.request_json("/api/curation/resolve-handoffs/pending?" + query).get("packages") or []
            package = max(rows, key=lambda row: row.get("created_at", ""), default=None)
            previous = self.current_package
            if previous and (not package or previous.get('created_at','') >= package.get('created_at','')):
                if previous.get('status') in {'applying','completed','failed'}:
                    package = self.request_json(f"/api/curation/resolve-handoffs/{previous['package_id']}/status")
            if package and not package.get("bridge_received_at"):
                package = self.request_json(f"/api/curation/resolve-handoffs/{package['package_id']}/received", "POST", {"bridge_session_id": self.session_id})
            self.current_package = package
            return BridgeSnapshot(True, status, package)
        except Exception as exc:
            return BridgeSnapshot(False, {}, None, str(exc))

    def apply(self, destination_mode: str) -> dict[str, Any]:
        if not self.current_package or not self.current_package.get("bridge_received_at"):
            raise RuntimeError("Package has not been received by this bridge session")
        status = self.request_json("/api/curation/resolve-bridge/status")
        return self.request_json(f"/api/curation/resolve-handoffs/{self.current_package['package_id']}/apply", "POST", {
            "destination_mode": destination_mode,
            "current_project": status.get("project", ""),
            "current_timeline_id": status.get("timeline_id", ""),
        })

    def package_status(self) -> dict[str, Any]:
        if not self.current_package:
            return {}
        row = self.request_json(f"/api/curation/resolve-handoffs/{self.current_package['package_id']}/status")
        self.current_package = row
        return row

    def discard(self) -> dict[str, Any]:
        if not self.current_package:
            raise RuntimeError("Nessun pacchetto")
        row = self.request_json(f"/api/curation/resolve-handoffs/{self.current_package['package_id']}/discard", "POST")
        self.current_package = None
        return row

    def capture(self, *, detect_videos: bool, include_v1: bool,
                force_recalculate: bool = False) -> dict[str, Any]:
        return self.request_json("/api/curation/resolve-bridge/capture", "POST", {
            "detect_videos": detect_videos, "include_v1": include_v1,
            "force_recalculate": force_recalculate,
        })

    def open_project(self) -> dict[str, Any]:
        return self.request_json('/api/curation/resolve-bridge/open', 'POST')


class SingleInstance:
    """Local lock and focus channel for one bridge window per machine."""
    def __init__(self, *, port: int = INSTANCE_PORT, on_focus: Callable[[], None] | None = None):
        self.port = port
        self.on_focus = on_focus or (lambda: None)
        self.server: socket.socket | None = None
        self.stop = threading.Event()

    def acquire(self) -> bool:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind(("127.0.0.1", self.port))
            server.listen(2)
            server.settimeout(.2)
        except OSError:
            server.close()
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=.5) as peer:
                    peer.sendall(b"FOCUS\n")
            except OSError:
                pass
            return False
        self.server = server
        threading.Thread(target=self._listen, name="rambla-bridge-focus", daemon=True).start()
        return True

    def _listen(self) -> None:
        while not self.stop.is_set() and self.server:
            try:
                peer, _ = self.server.accept()
                with peer:
                    if peer.recv(32).strip() == b"FOCUS":
                        self.on_focus()
            except socket.timeout:
                continue
            except OSError:
                break

    def close(self) -> None:
        self.stop.set()
        if self.server:
            try:
                self.server.close()
            except OSError:
                pass
            self.server = None


class BridgeApp:
    POLL_MS = 1000

    def __init__(self, root: Any, client: BridgeClient, *, single_instance: SingleInstance | None = None, build_ui: bool = True):
        self.root, self.client, self.single_instance = root, client, single_instance
        self.timer = None
        self.closed = False
        self.applying = False
        self.focus_requested = threading.Event()
        self.widgets: dict[str, Any] = {}
        self._last_package_id = ""
        self._destination_explicit = os.environ.get("RAMBLA_BRIDGE_DESTINATION_EXPLICIT") == "1"
        self._brand_images: list[Any] = []
        if build_ui:
            self._build_ui()

    def _build_ui(self) -> None:
        self.root.title(f"RMBL B ROLL {RELEASE_VERSION}")
        self.root.geometry("600x680")
        self.root.minsize(520, 560)
        self.root.resizable(True, True)
        self.root.configure(bg="#11152b")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        # Scrollable bridge surface: resizing never hides APPLICA on smaller displays.
        viewport = tk.Canvas(self.root, bg="#11152b", highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=viewport.yview, bg="#242b4b", troughcolor="#11152b", activebackground="#7c6cf2", bd=0, highlightthickness=0)
        viewport.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y"); viewport.pack(side="left", fill="both", expand=True)
        shell = tk.Frame(viewport, bg="#11152b", padx=16, pady=14)
        shell_window = viewport.create_window(0, 0, anchor="nw", window=shell)
        shell.bind("<Configure>", lambda _event: viewport.configure(scrollregion=viewport.bbox("all")))
        viewport.bind("<Configure>", lambda event: viewport.itemconfigure(shell_window, width=event.width))
        self.root.bind("<MouseWheel>", lambda event: viewport.yview_scroll(int(-event.delta / 120), "units"))
        self.widgets["content"] = shell

        header = RoundedPanel(shell, fill="#181d39", outline="#434b77", height=86, radius=20, padding=12); header.pack(fill="x", pady=(0, 10))
        logo_path = APP_ROOT / "backend" / "assets" / "branding" / "rmbl_mark_white.png"
        if logo_path.is_file():
            try:
                bridge_icon = build_bridge_icon(tk, logo_path)
                header_icon = bridge_icon.subsample(2, 2)
                self._brand_images.extend([bridge_icon, header_icon])
                self.root.iconphoto(True, bridge_icon)
                tk.Label(header.body, image=header_icon, bg="#181d39", bd=0).pack(side="left", padx=(0, 14))
            except tk.TclError:
                mark = tk.Canvas(header.body, width=72, height=56, bg="#181d39", highlightthickness=0); mark.pack(side="left", padx=(0, 13)); draw_bridge_mark(mark)
        else:
            mark = tk.Canvas(header.body, width=72, height=56, bg="#181d39", highlightthickness=0); mark.pack(side="left", padx=(0, 13)); draw_bridge_mark(mark)
        heading = tk.Frame(header.body, bg="#181d39"); heading.pack(side="left", fill="x", expand=True)
        wordmark_path = APP_ROOT / "backend" / "assets" / "branding" / "rmbl_wordmark_white.png"
        if wordmark_path.is_file():
            try:
                wordmark = tk.PhotoImage(file=str(wordmark_path)).subsample(14, 14)
                self._brand_images.append(wordmark)
                tk.Label(heading, image=wordmark, bg="#181d39", bd=0).pack(anchor="w")
            except tk.TclError:
                tk.Label(heading, text="RMBL / BRIDGE", bg="#181d39", fg="#f7f8ff", font=("Segoe UI Semibold", 19)).pack(anchor="w")
        else:
            tk.Label(heading, text="RMBL / BRIDGE", bg="#181d39", fg="#f7f8ff", font=("Segoe UI Semibold", 19)).pack(anchor="w")
        tk.Label(heading, text=f"RESOLVE HANDOFF  ·  {RELEASE_VERSION}", bg="#181d39", fg="#aeb6df", font=("Segoe UI Semibold", 9)).pack(anchor="w", pady=(3, 0))

        self.widgets["connection"] = StatusPill(shell); self.widgets["connection"].pack(fill="x", pady=(0, 12))
        card = RoundedPanel(shell, height=78, radius=16, padding=12); card.pack(fill="x", pady=(0, 9))
        tk.Label(card.body, text="TIMELINE ATTIVA", bg="#202746", fg="#9299bc", font=("Segoe UI Semibold", 8), anchor="w").pack(fill="x")
        self.widgets["timeline"] = tk.Label(card.body, text="Timeline in attesa…", bg="#202746", fg="#f1f3ff", font=("Segoe UI", 10), justify="left", anchor="w"); self.widgets["timeline"].pack(fill="x", pady=(5, 0))

        options_card = RoundedPanel(shell, fill="#181d39", outline="#343c65", height=344, radius=18, padding=12); options_card.pack(fill="x", pady=(0, 9))
        options = options_card.body
        self.detect_videos = tk.BooleanVar(value=os.environ.get('RAMBLA_BRIDGE_DETECT', '1') == '1'); self.include_v1 = tk.BooleanVar(value=os.environ.get('RAMBLA_BRIDGE_V1', '0') == '1')
        tk.Label(options,text="ANALISI DELLA TIMELINE",bg="#181d39",fg="#9299bc",font=("Segoe UI Semibold",8),anchor="w").pack(fill="x",pady=(0,6))
        CompactChoiceRow(options,title="Rileva i video già presenti",description="Analizza le tracce video superiori e segnala le frasi già coperte",variable=self.detect_videos).pack(fill="x",pady=(0,5))
        CompactChoiceRow(options,title="Considera anche la traccia principale V1",description="Include il montato principale nel controllo delle coperture esistenti",variable=self.include_v1).pack(fill="x",pady=(0,9))
        self.widgets["capture"] = RoundedButton(options, text="USA AUDIO IN RMBL B ROLL", command=self.capture_audio); self.widgets["capture"].pack(fill="x", pady=(0, 7))
        self.widgets["recalculate"] = RoundedButton(options, text="RICALCOLA AUDIO · IN → OUT", command=lambda: self.capture_audio(force_recalculate=True)); self.widgets["recalculate"].pack(fill="x", pady=(0, 7))
        self.widgets['open'] = RoundedButton(options, text='APRI RMBL B ROLL · PROGETTO SALVATO', command=self.open_rambla); self.widgets['open'].pack(fill='x')
        self.widgets["capture_status"] = tk.Label(options, text="", bg="#181d39", fg="#b9c1e0", font=("Segoe UI", 9), wraplength=520, justify="left", anchor="w"); self.widgets["capture_status"].pack(fill="x", pady=(6, 0))

        tk.Label(shell, text="PACCHETTO DA RMBL B ROLL", bg="#11152b", fg="#aeb6df", font=("Segoe UI Semibold", 9), anchor="w").pack(fill="x", pady=(6, 7))
        package_card = RoundedPanel(shell, height=108, radius=16, padding=12); package_card.pack(fill="x")
        self.widgets["package"] = tk.Label(package_card.body, text="Nessun pacchetto ricevuto", bg="#202746", fg="#f1f3ff", font=("Segoe UI", 9), justify="left", anchor="w", wraplength=520); self.widgets["package"].pack(fill="both", expand=True)
        self.destination = tk.StringVar(value=default_destination())
        destinations = tk.Frame(shell, bg="#11152b"); destinations.pack(fill="x", pady=(12, 5))
        tk.Label(destinations,text="DESTINAZIONE",bg="#11152b",fg="#9299bc",font=("Segoe UI Semibold",8),anchor="w").pack(fill="x",pady=(0,6))
        DestinationCard(destinations,title="IMPORTA SULLA TIMELINE ATTIVA",description="Crea prima una copia TEMP. Non sposta né modifica le clip già presenti",value="active",variable=self.destination,recommended=True,on_select=self._select_destination).pack(fill="x",pady=(0,7))
        DestinationCard(destinations,title="CREA UNA NUOVA TIMELINE TEMP",description="Genera una timeline separata contenente soltanto il nuovo montaggio",value="new",variable=self.destination,on_select=self._select_destination).pack(fill="x")
        self.widgets["progress"] = ProgressBar(shell); self.widgets["progress"].pack(fill="x", pady=(12, 8))
        self.widgets["message"] = tk.Label(shell, text="L'applicazione parte soltanto quando premi APPLICA.", bg="#11152b", fg="#b9c1e0", font=("Segoe UI", 9), wraplength=520, justify="left", anchor="w"); self.widgets["message"].pack(fill="x", pady=(0, 8))
        actions = tk.Frame(shell, bg="#11152b"); actions.pack(fill="x", pady=(0, 8))
        self.widgets["apply"] = RoundedButton(actions, text="APPLICA", command=self.apply, accent=True, state="disabled"); self.widgets["apply"].pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.widgets["discard"] = RoundedButton(actions, text="SCARTA", command=self.discard, state="disabled"); self.widgets["discard"].pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._fit_window(package_visible=False)

    def _select_destination(self, value: str) -> None:
        self._destination_explicit = True
        self.destination.set(value)

    def _fit_window(self, *, package_visible: bool) -> None:
        if not hasattr(self.root, "winfo_screenheight"):
            return
        self.root.update_idletasks()
        content = self.widgets.get("content")
        requested = int(content.winfo_reqheight() if content is not None else self.root.winfo_reqheight())
        geometry = window_geometry(
            int(self.root.winfo_screenwidth()),
            int(self.root.winfo_screenheight()),
            requested_height=requested,
            package_visible=package_visible,
        )
        self.root.geometry(geometry)

    def start(self) -> None:
        self.poll()

    def poll(self) -> None:
        if self.closed: return
        if self._maybe_update(): return
        if self.focus_requested.is_set():
            self.focus_requested.clear(); self._focus_now()
        if self.applying: self._poll_apply()
        else: self._render(self.client.poll_once())
        self.timer = self.root.after(self.POLL_MS, self.poll)

    def _maybe_update(self) -> bool:
        if self.applying or (self.client.current_package or {}).get('status') == 'applying':
            return False
        try:
            changed = bridge_build_token() != LOADED_BUILD
        except OSError:
            return False
        if not changed:
            return False
        self._restart_for_update()
        return True

    def _restart_for_update(self) -> None:
        env = {**os.environ, 'RAMBLA_BRIDGE_SESSION_ID': self.client.session_id}
        for attribute, key in [('detect_videos','RAMBLA_BRIDGE_DETECT'), ('include_v1','RAMBLA_BRIDGE_V1')]:
            if hasattr(self, attribute):
                env[key] = '1' if getattr(self, attribute).get() else '0'
        if hasattr(self, 'destination'):
            env['RAMBLA_BRIDGE_DESTINATION'] = self.destination.get()
            env['RAMBLA_BRIDGE_DESTINATION_EXPLICIT'] = '1' if self._destination_explicit else '0'
        self.close()
        subprocess.Popen([sys.executable, str(Path(__file__).resolve())], cwd=str(APP_ROOT), env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def _render(self, snapshot: BridgeSnapshot) -> None:
        if not self.widgets: return
        self.widgets["connection"].configure(text="● RMBL B ROLL CONNECTED" if snapshot.connected else "● BRIDGE OFFLINE", style="Lime.TLabel" if snapshot.connected else "Bad.TLabel")
        if snapshot.status:
            row = snapshot.status
            self.widgets["timeline"].configure(text=f"{row.get('project','')}\n{row.get('timeline','')}\nFrame {row.get('mark_in','?')} → {row.get('mark_out','?')} · {row.get('range_source','timeline')}")
        elif snapshot.error: self.widgets["timeline"].configure(text=snapshot.error)
        package = snapshot.package
        if package:
            summary = package.get("summary") or {}; changes = package.get("change_summary") or {}
            self.widgets["package"].configure(text=f"NUOVA REVISIONE · v{package.get('revision',1)}\nDurata {float(summary.get('duration_seconds') or 0):.1f}s\n{summary.get('broll_count',0)} B-roll · {summary.get('subtitle_count',0)} subs · {summary.get('title_count',0)} frasi · {summary.get('generic_broll_count',0)} generiche\nDifferenze: +{changes.get('broll_added',0)} / -{changes.get('broll_removed',0)} B-roll")
            received = bool(package.get("bridge_received_at"))
            self.widgets["apply"].configure(state="normal" if received else "disabled")
            self.widgets["discard"].configure(state="normal")
            self.widgets["message"].configure(text="Pacchetto ricevuto. Controlla la destinazione e premi APPLICA.")
            self.widgets["progress"].configure(value=100)
            if package.get('status') in {'failed','applying','completed'}:
                self._render_job(package)
            package_id = str(package.get("package_id") or "")
            if package_id and package_id != self._last_package_id:
                self._last_package_id = package_id
                self.root.after_idle(lambda: self._fit_window(package_visible=True))
        else:
            self.widgets["package"].configure(text="Nessun pacchetto ricevuto\nInvia il montaggio dalla sezione EXPORT TIMELINE di RMBL B ROLL.")
            self.widgets["apply"].configure(state="disabled"); self.widgets["discard"].configure(state="disabled"); self.widgets["progress"].configure(value=0)
            if self._last_package_id:
                self._last_package_id = ""
                self.root.after_idle(lambda: self._fit_window(package_visible=False))

    def apply(self) -> None:
        try:
            row = self.client.apply(self.destination.get()); self.applying = row.get("status") == "applying"; self._render_job(row)
        except Exception as exc: self._show_error(str(exc))

    def _poll_apply(self) -> None:
        try:
            row = self.client.package_status(); self.applying = row.get("status") == "applying"; self._render_job(row)
        except Exception as exc:
            self.applying = False; self._show_error(str(exc))

    def _render_job(self, row: dict[str, Any]) -> None:
        if not self.widgets: return
        progress = row.get("progress") or {}; self.widgets["progress"].configure(value=int(progress.get("percent") or 0))
        status = row.get("status") or ""; message = progress.get("message") or status
        if status == "completed":
            message = "✓ ESPORTATO SU RESOLVE · timeline pronta"; self.widgets["apply"].configure(state="disabled")
        elif status == "failed":
            message = "Errore: " + str(row.get("error") or message); self.widgets["apply"].configure(state="normal")
        else: self.widgets["apply"].configure(state="disabled")
        self.widgets["message"].configure(text=message)

    def discard(self) -> None:
        try:
            self.client.discard(); self._render(BridgeSnapshot(True, {}, None))
        except Exception as exc: self._show_error(str(exc))

    def capture_audio(self, force_recalculate: bool = False) -> None:
        self.widgets["capture"].configure(state="disabled"); self.widgets["recalculate"].configure(state="disabled")
        activity = "Ricalcolo forzato dell'audio tra IN e OUT" if force_recalculate else "Render audio e invio a RMBL B ROLL"
        self.widgets["capture_status"].configure(text=activity + " in corso…"); self.root.update_idletasks()
        try:
            row = self.client.capture(
                detect_videos=bool(self.detect_videos.get()), include_v1=bool(self.include_v1.get()),
                force_recalculate=force_recalculate,
            )
            detected = len(row.get("existing_video_ranges") or []); reused = "Audio precedente riutilizzato" if row.get("reused_audio") else "Nuovo audio renderizzato"
            interval = f"Frame {row.get('mark_in','?')} → {row.get('mark_out','?')} ({row.get('range_source','timeline')})"
            self.widgets["capture_status"].configure(text=f"✓ {reused} · {interval} · {detected} intervalli video rilevati · RMBL B ROLL aperta")
            self._focus_rambla(row.get("url", ""))
        except Exception as exc: self._show_error(str(exc), target="capture_status")
        finally:
            self.widgets["capture"].configure(state="normal"); self.widgets["recalculate"].configure(state="normal")

    def open_rambla(self) -> None:
        try:
            row = self.client.open_project()
            self._focus_rambla(row['url'])
            label = 'Ultimo progetto salvato' if row.get('opened_from') == 'last_saved' else 'Progetto della timeline'
            self.widgets['capture_status'].configure(text='✓ ' + label + ' · ' + str(row.get('name') or row.get('project_id')))
        except Exception as exc:
            self._show_error(str(exc), target='capture_status')

    def _focus_rambla(self, relative_url: str) -> None:
        launcher = APP_ROOT / 'launch_local_v5.py'
        project_id = (urllib.parse.parse_qs(urllib.parse.urlparse(relative_url).query).get('project') or [''])[0]
        if project_id and launcher.is_file():
            log_path = APP_ROOT / '.curation-logs' / 'bridge-open-app.log'
            log_path.parent.mkdir(exist_ok=True)
            with log_path.open('ab') as log:
                subprocess.Popen([sys.executable, str(launcher), 'start', '--project', project_id], cwd=str(APP_ROOT), stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=0x08000000 if os.name == 'nt' else 0)

    def _show_error(self, message: str, target: str = "message") -> None:
        if self.widgets: self.widgets[target].configure(text="Errore: " + message)

    def focus(self) -> None:
        self.focus_requested.set()

    def _focus_now(self) -> None:
        self.root.deiconify(); self.root.lift(); self.root.focus_force()

    def close(self) -> None:
        self.closed = True
        if self.timer is not None:
            try: self.root.after_cancel(self.timer)
            except Exception: pass
        if self.single_instance: self.single_instance.close()
        self.root.destroy()


def main() -> int:
    import tkinter as tk
    lock = SingleInstance()
    if not lock.acquire():
        return 0
    root = tk.Tk(); transport = ServerTransport(); client = BridgeClient(request_json=transport, session_id=os.environ.get('RAMBLA_BRIDGE_SESSION_ID') or None)
    runtime_name = 'bridge-runtime.json' if DESKTOP_NAME.casefold() == 'default' else f'bridge-runtime-test-{INSTANCE_PORT}.json'
    (APP_ROOT.parent / 'rambla-data' / runtime_name).write_text(
        json.dumps({'pid':os.getpid(), 'version':RELEASE_VERSION, 'build':LOADED_BUILD, 'desktop':DESKTOP_NAME}), encoding='utf-8')
    app = BridgeApp(root, client, single_instance=lock, build_ui=True); lock.on_focus = app.focus
    app.start(); root.mainloop(); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        log = APP_ROOT / '.curation-logs' / 'bridge-startup.log'
        log.parent.mkdir(exist_ok=True)
        log.write_text(traceback.format_exc(), encoding='utf-8')
        if os.name == 'nt' and DESKTOP_NAME.casefold() == 'default':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, f'Avvio del bridge non riuscito. Dettagli: {log}', 'RMBL B ROLL', 0x10)
        raise
