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


def window_geometry(screen_width: int, screen_height: int, *, requested_height: int, package_visible: bool) -> str:
    """Return a useful bridge size without extending below the Windows work area."""
    width = min(760 if package_visible else 680, max(560, screen_width - 80))
    wanted = max(760, requested_height + 40) if package_visible else max(640, requested_height)
    height = min(wanted, max(560, screen_height - 90))
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

    def capture(self, *, detect_videos: bool, include_v1: bool) -> dict[str, Any]:
        return self.request_json("/api/curation/resolve-bridge/capture", "POST", {
            "detect_videos": detect_videos, "include_v1": include_v1,
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
        self._brand_images: list[Any] = []
        if build_ui:
            self._build_ui()

    def _build_ui(self) -> None:
        import tkinter as tk
        from tkinter import ttk
        self.root.title(f"RMBL B ROLL {RELEASE_VERSION}")
        self.root.geometry("680x700")
        self.root.minsize(560, 560)
        self.root.configure(bg="#11152b")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(self.root); style.theme_use("clam")
        style.configure("R.TFrame", background="#11152b")
        style.configure("Header.TFrame", background="#181d39")
        style.configure("Card.TFrame", background="#202746")
        style.configure("R.TLabel", background="#11152b", foreground="#e8ebff", font=("Segoe UI", 10))
        style.configure("Eyebrow.TLabel", background="#181d39", foreground="#aeb6df", font=("Segoe UI Semibold", 9))
        style.configure("Title.TLabel", background="#181d39", foreground="#f7f8ff", font=("Segoe UI Semibold", 19))
        style.configure("Card.TLabel", background="#202746", foreground="#e8ebff", font=("Segoe UI", 10))
        style.configure("Lime.TLabel", background="#183727", foreground="#d8ff5b", font=("Segoe UI Semibold", 10), padding=9)
        style.configure("Bad.TLabel", background="#3a202b", foreground="#ff9d9d", font=("Segoe UI Semibold", 10), padding=9)
        style.configure("R.TButton", background="#343b62", foreground="#f7f8ff", padding=11, font=("Segoe UI Semibold", 10), borderwidth=1)
        style.map("R.TButton", background=[("active", "#4e4a86")])
        style.configure("Apply.TButton", background="#d8ff5b", foreground="#111522", padding=12, font=("Segoe UI Semibold", 11))
        style.map("Apply.TButton", background=[("disabled", "#343b62"), ("active", "#ebff9a")])
        style.configure("R.Horizontal.TProgressbar", background="#d8ff5b", troughcolor="#29304f", borderwidth=0)

        shell = ttk.Frame(self.root, style="R.TFrame", padding=20); shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell, style="Header.TFrame", padding=14); header.pack(fill="x", pady=(0, 14))
        logo_path = APP_ROOT / "backend" / "assets" / "branding" / "rmbl_mark_white.png"
        if logo_path.is_file():
            try:
                bridge_icon = build_bridge_icon(tk, logo_path)
                header_icon = bridge_icon.subsample(2, 2)
                self._brand_images.extend([bridge_icon, header_icon])
                self.root.iconphoto(True, bridge_icon)
                ttk.Label(header, image=header_icon, style="Title.TLabel").pack(side="left", padx=(0, 13))
            except tk.TclError:
                mark = tk.Canvas(header, width=72, height=56, bg="#181d39", highlightthickness=0); mark.pack(side="left", padx=(0, 13)); draw_bridge_mark(mark)
        else:
            mark = tk.Canvas(header, width=72, height=56, bg="#181d39", highlightthickness=0); mark.pack(side="left", padx=(0, 13)); draw_bridge_mark(mark)
        heading = ttk.Frame(header, style="Header.TFrame"); heading.pack(side="left", fill="x", expand=True)
        wordmark_path = APP_ROOT / "backend" / "assets" / "branding" / "rmbl_wordmark_white.png"
        if wordmark_path.is_file():
            try:
                wordmark = tk.PhotoImage(file=str(wordmark_path)).subsample(14, 14)
                self._brand_images.append(wordmark)
                ttk.Label(heading, image=wordmark, style="Title.TLabel").pack(anchor="w")
            except tk.TclError:
                ttk.Label(heading, text="RMBL / BRIDGE", style="Title.TLabel").pack(anchor="w")
        else:
            ttk.Label(heading, text="RMBL / BRIDGE", style="Title.TLabel").pack(anchor="w")
        ttk.Label(heading, text=f"RESOLVE HANDOFF  ·  {RELEASE_VERSION}", style="Eyebrow.TLabel").pack(anchor="w", pady=(2, 0))
        self.widgets["connection"] = ttk.Label(shell, text="● CONNESSIONE IN CORSO", style="Bad.TLabel"); self.widgets["connection"].pack(fill="x", pady=(0, 12))
        card = ttk.Frame(shell, style="Card.TFrame", padding=14); card.pack(fill="x", pady=(0, 10))
        self.widgets["timeline"] = ttk.Label(card, text="Timeline in attesa…", style="Card.TLabel", justify="left"); self.widgets["timeline"].pack(anchor="w")
        options = ttk.Frame(shell, style="R.TFrame"); options.pack(fill="x", pady=4)
        self.detect_videos = tk.BooleanVar(value=os.environ.get('RAMBLA_BRIDGE_DETECT', '1') == '1'); self.include_v1 = tk.BooleanVar(value=os.environ.get('RAMBLA_BRIDGE_V1', '0') == '1')
        ttk.Checkbutton(options, text="Detect videos · segnala le frasi già coperte", variable=self.detect_videos).pack(anchor="w", pady=3)
        ttk.Checkbutton(options, text="Includi anche V1 · considera la traccia principale", variable=self.include_v1).pack(anchor="w", pady=3)
        self.widgets["capture"] = ttk.Button(options, text="USA AUDIO IN RMBL B ROLL", style="R.TButton", command=self.capture_audio); self.widgets["capture"].pack(fill="x", pady=(9, 5))
        self.widgets['open'] = ttk.Button(options, text='APRI RMBL B ROLL · PROGETTO SALVATO', style='R.TButton', command=self.open_rambla)
        self.widgets['open'].pack(fill='x', pady=(4, 5))
        self.widgets["capture_status"] = ttk.Label(options, text="", style="R.TLabel", wraplength=540); self.widgets["capture_status"].pack(anchor="w", pady=(0, 8))
        ttk.Label(shell, text="PACCHETTO DA RMBL B ROLL", style="R.TLabel").pack(anchor="w", pady=(8, 5))
        package_card = ttk.Frame(shell, style="Card.TFrame", padding=14); package_card.pack(fill="x")
        self.widgets["package"] = ttk.Label(package_card, text="Nessun pacchetto ricevuto", style="Card.TLabel", justify="left", wraplength=530); self.widgets["package"].pack(anchor="w")
        self.destination = tk.StringVar(value=os.environ.get('RAMBLA_BRIDGE_DESTINATION', 'new'))
        destinations = ttk.Frame(shell, style="R.TFrame"); destinations.pack(fill="x", pady=(10, 5))
        ttk.Radiobutton(destinations, text="CREA NUOVA TIMELINE · TEMP (predefinito)", value="new", variable=self.destination).pack(anchor="w", pady=3)
        ttk.Radiobutton(destinations, text="IMPORTA SULLA TIMELINE ATTIVA · con copia TEMP", value="active", variable=self.destination).pack(anchor="w", pady=3)
        self.widgets["progress"] = ttk.Progressbar(shell, maximum=100, value=0, style="R.Horizontal.TProgressbar"); self.widgets["progress"].pack(fill="x", pady=(10, 5))
        self.widgets["message"] = ttk.Label(shell, text="L'applicazione parte soltanto quando premi APPLICA.", style="R.TLabel", wraplength=540); self.widgets["message"].pack(anchor="w", pady=(0, 9))
        actions = ttk.Frame(shell, style="R.TFrame"); actions.pack(fill="x")
        self.widgets["apply"] = ttk.Button(actions, text="APPLICA", style="Apply.TButton", command=self.apply, state="disabled"); self.widgets["apply"].pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.widgets["discard"] = ttk.Button(actions, text="SCARTA", style="R.TButton", command=self.discard, state="disabled"); self.widgets["discard"].pack(side="left", fill="x", expand=True, padx=(5, 0))
        self._fit_window(package_visible=False)

    def _fit_window(self, *, package_visible: bool) -> None:
        if not hasattr(self.root, "winfo_screenheight"):
            return
        self.root.update_idletasks()
        requested = int(self.root.winfo_reqheight())
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
                self._fit_window(package_visible=True)
        else:
            self.widgets["package"].configure(text="Nessun pacchetto ricevuto\nInvia il montaggio dalla sezione EXPORT TIMELINE di RMBL B ROLL.")
            self.widgets["apply"].configure(state="disabled"); self.widgets["discard"].configure(state="disabled"); self.widgets["progress"].configure(value=0)
            if self._last_package_id:
                self._last_package_id = ""
                self._fit_window(package_visible=False)

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

    def capture_audio(self) -> None:
        self.widgets["capture"].configure(state="disabled"); self.widgets["capture_status"].configure(text="Render audio e invio a RMBL B ROLL in corso…"); self.root.update_idletasks()
        try:
            row = self.client.capture(detect_videos=bool(self.detect_videos.get()), include_v1=bool(self.include_v1.get()))
            detected = len(row.get("existing_video_ranges") or []); reused = "Audio precedente riutilizzato" if row.get("reused_audio") else "Nuovo audio renderizzato"
            self.widgets["capture_status"].configure(text=f"✓ {reused} · {detected} intervalli video rilevati · RMBL B ROLL aperta")
            self._focus_rambla(row.get("url", ""))
        except Exception as exc: self._show_error(str(exc), target="capture_status")
        finally: self.widgets["capture"].configure(state="normal")

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
