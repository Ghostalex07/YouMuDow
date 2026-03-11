"""
YouMuDow v4.0 — Versión Suprema
Requisitos: yt-dlp (en PATH)
Opcional:   pip install pillow   (miniaturas en el panel de detalle)
"""
import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
import threading
import queue
import os
import webbrowser
import urllib.request
import io
from datetime import datetime
import re

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ──────────────────────────── PALETA ─────────────────────────────
BG     = "#0d0d0d"
BG2    = "#161616"
BG3    = "#1f1f1f"
BG4    = "#2a2a2a"
ACCENT = "#7c3aed"
ACCH   = "#6d28d9"
GREEN  = "#22c55e"
RED    = "#ef4444"
YELLOW = "#eab308"
CYAN   = "#22d3ee"
FG     = "#f0f0f0"
FGDIM  = "#555555"
FGMID  = "#888888"
MONO   = ("Consolas", 9)
THUMB_W, THUMB_H = 228, 128
PLACEHOLDER = "Busca en YouTube o pega una URL..."
DEFAULT_DL = os.path.join(os.path.expanduser("~"), "Downloads")


# ─────────────────────────── APLICACION ──────────────────────────
class YouMuDow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("YouMuDow  v4.0")
        self.root.geometry("1120x640")
        self.root.minsize(820, 520)
        self.root.configure(bg=BG)

        self.cola: queue.Queue = queue.Queue()
        self.resultados: list  = []
        self.thumb_cache: dict = {}
        self.current_idx: int  = -1
        self.session_path: str = DEFAULT_DL
        self.debug_visible     = False
        self._thumb_ref        = None

        # ── Sincronización y control de procesos ──────────────────
        self._dl_lock       = threading.Lock()
        self._descargando   = False
        self._dl_proc: subprocess.Popen | None     = None
        self._search_proc: subprocess.Popen | None = None
        self._results_lock  = threading.Lock()
        self._detail_cache  = set()

        self._apply_style()
        self._build_ui()

        # Mostrar ruta por defecto
        short = DEFAULT_DL if len(DEFAULT_DL) <= 34 else "..." + DEFAULT_DL[-32:]
        self.lbl_path.config(text=short, fg=FGMID)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ══════════════════════════ ESTILOS ══════════════════════════
    def _apply_style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
        s.configure("TFrame",            background=BG)
        s.configure("TLabel",            background=BG,  foreground=FG)
        s.configure("TLabelframe",       background=BG2, foreground=FGMID)
        s.configure("TLabelframe.Label", background=BG2, foreground=FGMID,
                    font=("Segoe UI", 8))
        s.configure("TEntry",
                    fieldbackground=BG3, foreground=FG,
                    insertcolor=FG, borderwidth=0)
        s.configure("TRadiobutton", background=BG, foreground=FG,
                    indicatorcolor=ACCENT)
        s.map("TRadiobutton", background=[("active", BG)])
        s.configure("Accent.TButton",
                    background=ACCENT, foreground="white",
                    font=("Segoe UI", 10, "bold"),
                    padding=(14, 7), relief="flat")
        s.map("Accent.TButton",
              background=[("active", ACCH), ("disabled", BG3)],
              foreground=[("disabled", FGMID)])
        s.configure("Ghost.TButton",
                    background=BG3, foreground=FG,
                    font=("Segoe UI", 9), padding=(8, 5), relief="flat")
        s.map("Ghost.TButton", background=[("active", BG4)])
        s.configure("SmGhost.TButton",
                    background=BG3, foreground=FGMID,
                    font=("Segoe UI", 8), padding=(5, 3), relief="flat")
        s.map("SmGhost.TButton",
              background=[("active", BG4)], foreground=[("active", FG)])
        s.configure("Treeview",
                    background=BG2, fieldbackground=BG2, foreground=FG,
                    rowheight=26, borderwidth=0, font=("Segoe UI", 9))
        s.configure("Treeview.Heading",
                    background=BG3, foreground=FGMID,
                    font=("Segoe UI", 8, "bold"), relief="flat")
        s.map("Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", "white")])
        s.configure("Vertical.TScrollbar",
                    background=BG3, troughcolor=BG,
                    arrowcolor=FGMID, borderwidth=0, relief="flat")

    # ════════════════════════════ UI ═════════════════════════════
    def _build_ui(self):
        # ── Cabecera ─────────────────────────────────────────────
        top = tk.Frame(self.root, bg=BG, pady=10)
        top.pack(fill="x", padx=14)

        tk.Label(top, text="YouMuDow", bg=BG, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(top, text=" v4", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11)).pack(side="left", padx=(0, 18))

        sb = tk.Frame(top, bg=BG3, padx=10, pady=7)
        sb.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.ent = tk.Entry(sb, bg=BG3, fg=FGMID, insertbackground=FG,
                            relief="flat", font=("Segoe UI", 10), bd=0)
        self.ent.insert(0, PLACEHOLDER)
        self.ent.pack(fill="x", expand=True)
        self.ent.bind("<FocusIn>",  self._ph_in)
        self.ent.bind("<FocusOut>", self._ph_out)
        self.ent.bind("<Return>",   lambda _: self._buscar())
        self.ent.bind("<Control-a>", lambda _: (self.ent.selection_range(0, tk.END), "break")[1])

        self.btn_bus = ttk.Button(top, text="Search",
                                  style="Accent.TButton", command=self._buscar)
        self.btn_bus.pack(side="left")

        # ── Area central: tabla + panel lateral ──────────────────
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=(4, 4))

        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        cols = ("title", "channel", "duration", "status")
        self.tree = ttk.Treeview(left, columns=cols,
                                 show="headings", height=14,
                                 selectmode="extended")
        self.tree.heading("title",    text="TITULO",   anchor="w")
        self.tree.heading("channel",  text="CANAL",    anchor="w")
        self.tree.heading("duration", text="DURACION", anchor="center")
        self.tree.heading("status",   text="ESTADO",   anchor="center")
        self.tree.column("title",    anchor="w",      stretch=True)
        self.tree.column("channel",  anchor="w",      width=170, stretch=False)
        self.tree.column("duration", anchor="center", width=80,  stretch=False)
        self.tree.column("status",   anchor="center", width=120, stretch=False)

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        for tag, color in [("ready", FG), ("queued", YELLOW),
                           ("downloading", CYAN), ("done", GREEN), ("error", RED)]:
            self.tree.tag_configure(tag, foreground=color)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-Button-1>",  lambda _: self._open_yt())
        self.tree.bind("<Button-3>",         self._on_rclick)

        right = tk.Frame(main, bg=BG2, width=256)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)
        self._build_detail(right)

        # ── Controles ────────────────────────────────────────────
        ctrl = tk.Frame(self.root, bg=BG, pady=6)
        ctrl.pack(fill="x", padx=14)

        fbox = tk.Frame(ctrl, bg=BG3, padx=10, pady=6)
        fbox.pack(side="left")
        tk.Label(fbox, text="Formato:", bg=BG3, fg=FGMID,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self.fmt = tk.StringVar(value="mp3")
        for v, l in (("mp3", "MP3"), ("mp4", "MP4")):
            ttk.Radiobutton(fbox, text=l, variable=self.fmt,
                            value=v).pack(side="left", padx=4)

        pbox = tk.Frame(ctrl, bg=BG3, padx=10, pady=6)
        pbox.pack(side="left", padx=8)
        tk.Label(pbox, text="Carpeta:", bg=BG3, fg=FGMID,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.lbl_path = tk.Label(pbox, text="...", bg=BG3, fg=FGMID,
                                 font=("Segoe UI", 9), cursor="hand2")
        self.lbl_path.pack(side="left")
        self.lbl_path.bind("<Button-1>", lambda _: self._pick_folder())
        ttk.Button(pbox, text="...", style="Ghost.TButton",
                   command=self._pick_folder, width=2).pack(side="left", padx=(4, 0))

        bb = tk.Frame(ctrl, bg=BG)
        bb.pack(side="right")
        ttk.Button(bb, text="Abrir carpeta", style="Ghost.TButton",
                   command=self._open_folder).pack(side="right", padx=4)
        ttk.Button(bb, text="Vaciar cola",   style="Ghost.TButton",
                   command=self._clear_queue).pack(side="right")
        ttk.Button(bb, text="+ Añadir a cola", style="Accent.TButton",
                   command=self._encolar).pack(side="right", padx=6)

        # ── Barra de estado ───────────────────────────────────────
        self.sbar = tk.Frame(self.root, bg=BG3, pady=4)
        self.sbar.pack(fill="x", side="bottom")

        self.lbl_status = tk.Label(self.sbar, text="Listo.", bg=BG3, fg=FGMID,
                                   font=("Segoe UI", 8), anchor="w")
        self.lbl_status.pack(side="left", padx=10)

        self.lbl_qc = tk.Label(self.sbar, text="Cola: 0", bg=BG3, fg=FGMID,
                               font=("Segoe UI", 8))
        self.lbl_qc.pack(side="right", padx=10)

        ttk.Button(self.sbar, text="Logs", style="SmGhost.TButton",
                   command=self._toggle_log).pack(side="right", padx=4)

        if not PIL_AVAILABLE:
            tk.Label(self.sbar, text="(instala Pillow para miniaturas)",
                     bg=BG3, fg=FGDIM, font=("Segoe UI", 7)).pack(side="right", padx=6)

        # ── Panel de logs (oculto) ────────────────────────────────
        self.f_log = ttk.LabelFrame(self.root, text="  TERMINAL  ", padding=4)
        self.log = tk.Text(self.f_log, height=9, bg="#060606", fg="#00ff88",
                           font=MONO, relief="flat", state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

        # ── Menu contextual ───────────────────────────────────────
        self.ctx = tk.Menu(self.root, tearoff=0, bg=BG3, fg=FG,
                           activebackground=ACCENT, activeforeground="white",
                           font=("Segoe UI", 9), bd=0, relief="flat")
        self.ctx.add_command(label="  Abrir en YouTube", command=self._open_yt)
        self.ctx.add_command(label="  Copiar URL",       command=self._copy_url)
        self.ctx.add_separator()
        self.ctx.add_command(label="  Añadir a la cola", command=self._encolar)

    # ── Panel lateral de info ─────────────────────────────────────
    def _build_detail(self, parent: tk.Frame):
        tk.Label(parent, text="INFO DEL VIDEO", bg=BG2, fg=FGDIM,
                 font=("Segoe UI", 7, "bold")).pack(pady=(10, 6))

        self.thumb_lbl = tk.Label(
            parent, bg="#0a0a0a",
            text="Selecciona un\nvideo para ver\nla info",
            fg=FGMID, font=("Segoe UI", 9),
            width=THUMB_W, height=THUMB_H)
        self.thumb_lbl.pack(padx=12)

        self.lbl_spin = tk.Label(parent, text="", bg=BG2, fg=FGMID,
                                 font=("Segoe UI", 8))
        self.lbl_spin.pack()

        tk.Frame(parent, bg=BG4, height=1).pack(fill="x", padx=12, pady=6)

        info = tk.Frame(parent, bg=BG2)
        info.pack(fill="x", padx=12)

        self.d_title   = self._dl(info, bold=True, wrap=224)
        self.d_channel = self._dl(info, color=CYAN,  size=8)
        self.d_dur     = self._dl(info, color=FGMID, size=8)
        self.d_date    = self._dl(info, color=FGMID, size=8)
        self.d_views   = self._dl(info, color=FGMID, size=8)

        tk.Frame(parent, bg=BG4, height=1).pack(fill="x", padx=12, pady=8)

        ttk.Button(parent, text="Abrir en YouTube",
                   style="Ghost.TButton",
                   command=self._open_yt).pack(fill="x", padx=12, pady=(0, 4))
        ttk.Button(parent, text="Copiar URL",
                   style="Ghost.TButton",
                   command=self._copy_url).pack(fill="x", padx=12)

    def _dl(self, parent, text="—", bold=False, color=FG, size=9, wrap=0):
        kw = dict(bg=BG2, fg=color, anchor="w", justify="left", text=text,
                  font=("Segoe UI", size, "bold" if bold else "normal"))
        if wrap:
            kw["wraplength"] = wrap
        lbl = tk.Label(parent, **kw)
        lbl.pack(fill="x", pady=1)
        return lbl

    # ══════════════════ PLACEHOLDER ENTRY ════════════════════════
    def _ph_in(self, _):
        if self.ent.get() == PLACEHOLDER:
            self.ent.delete(0, tk.END)
            self.ent.config(fg=FG)

    def _ph_out(self, _):
        if not self.ent.get():
            self.ent.insert(0, PLACEHOLDER)
            self.ent.config(fg=FGMID)

    # ══════════════════ HELPERS ═══════════════════════════════════
    def _status(self, msg: str, color=FGMID):
        self.lbl_status.config(text=msg, fg=color)

    def _qcount(self):
        self.lbl_qc.config(text=f"Cola: {self.cola.qsize()}")

    def _log(self, txt: str):
        self.log.config(state="normal")
        self.log.insert(tk.END, txt + "\n")
        self.log.see(tk.END)
        self.log.config(state="disabled")

    def _row_tag(self, iid: str, tag: str):
        if self.tree.exists(iid):                     # <--- CORRECCIÓN
            self.tree.item(iid, tags=(tag,))

    def _toggle_log(self):
        if not self.debug_visible:
            self.f_log.pack(fill="both", padx=14, pady=(0, 4), before=self.sbar)
            self.debug_visible = True
        else:
            self.f_log.pack_forget()
            self.debug_visible = False

    def _pick_folder(self):
        p = filedialog.askdirectory(title="Selecciona carpeta de descarga")
        if p:
            self.session_path = p
            short = p if len(p) <= 34 else "..." + p[-32:]
            self.lbl_path.config(text=short, fg=FG)

    def _open_folder(self):
        if self.session_path and os.path.isdir(self.session_path):
            if os.name == "nt":
                os.startfile(self.session_path)
            else:
                subprocess.Popen(["xdg-open", self.session_path])
        else:
            self._status("No hay carpeta válida seleccionada.", RED)

    def _clear_queue(self):
        with self.cola.mutex:
            self.cola.queue.clear()
        self._qcount()
        self._status("Cola vaciada.")

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Elimina caracteres prohibidos por el sistema de archivos."""
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()

    # ══════════════════ SELECCION / DETALLE ═══════════════════════
    @staticmethod
    def _yt_video_id(url: str) -> str:
        m = re.search(r'(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})', url)
        return m.group(1) if m else ""

    def _on_select(self, _=None):
        sel = self.tree.selection()
        if not sel:
            return
        try:
            idx = self.tree.index(sel[0])
            with self._results_lock:
                if not (0 <= idx < len(self.resultados)):
                    return
                v = self.resultados[idx]
            self.current_idx = idx
            self._populate_detail(v)

            url = v.get("url", "")
            if not url:
                return

            # Miniatura instantánea desde CDN de YouTube
            vid_id = self._yt_video_id(url)
            if vid_id:
                thumb_url = f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"
                with self._results_lock:
                    if idx < len(self.resultados):
                        self.resultados[idx]["thumbnail"] = thumb_url
                if thumb_url in self.thumb_cache:
                    self._refresh_detail(idx)
                elif PIL_AVAILABLE:
                    self.lbl_spin.config(text="Cargando miniatura...")
                    threading.Thread(target=self._load_thumb,
                                     args=(thumb_url, idx), daemon=True).start()

            # Detalles extra en paralelo (una vez por URL)
            if url not in self._detail_cache:
                self._detail_cache.add(url)
                threading.Thread(target=self._fetch_detail,
                                 args=(url, idx), daemon=True).start()
        except Exception as e:
            self._log(f"[SELECT ERR] {e}")

    def _on_rclick(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.ctx.tk_popup(event.x_root, event.y_root)

    def _populate_detail(self, v: dict):
        self.d_title.config(text=v.get("title", "—"))
        self.d_channel.config(text="  " + v.get("uploader", "—"))
        dur = v.get("duration_string", "—")
        self.d_dur.config(text=f"  {dur}" if dur else "  —")
        date = v.get("upload_date_fmt", "")
        self.d_date.config(text=f"  {date}" if date else "  —")
        views = v.get("view_count_fmt", "")
        self.d_views.config(text=f"  {views}" if views else "  —")

        tu = v.get("thumbnail", "")
        if tu and tu in self.thumb_cache:
            photo = self.thumb_cache[tu]
            self._thumb_ref = photo
            self.thumb_lbl.config(image=photo, text="",
                                  width=THUMB_W, height=THUMB_H)
        else:
            self.thumb_lbl.config(image="",
                                  text="Cargando..." if tu else "Sin miniatura",
                                  width=THUMB_W, height=THUMB_H)

    def _fetch_detail(self, url: str, idx: int):
        """Obtiene fecha, vistas y duración en segundo plano."""
        try:
            fmt = "%(upload_date)s\t%(view_count)s\t%(duration_string)s"
            cmd = ["yt-dlp", "--print", fmt, "--no-playlist",
                   "--no-warnings", "--skip-download", url]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL,
                                    text=True, encoding="utf-8", errors="replace")
            raw, _ = proc.communicate(timeout=20)
            parts = raw.strip().split("\t")

            upload_raw = parts[0] if len(parts) > 0 else ""
            view_raw   = parts[1] if len(parts) > 1 else ""
            dur_raw    = parts[2] if len(parts) > 2 else ""

            date_fmt = ""
            if len(upload_raw) == 8:
                try:
                    date_fmt = datetime.strptime(upload_raw, "%Y%m%d").strftime("%d %b %Y")
                except ValueError:
                    date_fmt = upload_raw

            views_fmt = ""
            try:
                views_fmt = f"{int(view_raw):,}".replace(",", ".") + " vistas"
            except (ValueError, TypeError):
                pass

            with self._results_lock:
                if idx < len(self.resultados):
                    self.resultados[idx].update({
                        "upload_date_fmt": date_fmt,
                        "view_count_fmt":  views_fmt,
                        "duration_string": dur_raw or self.resultados[idx].get("duration_string", ""),
                    })
            self.root.after(0, self._refresh_detail, idx)
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            self.root.after(0, lambda: self._log(f"[DETAIL ERR] {e}"))
        finally:
            self.root.after(0, lambda: self.lbl_spin.config(text=""))

    def _load_thumb(self, tu: str, idx: int):
        """Descarga y escala la miniatura en un hilo secundario."""
        if self.current_idx != idx:
            return
        try:
            req = urllib.request.Request(tu, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = r.read()
            if self.current_idx != idx:
                return
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.thumb_cache[tu] = photo
            self.root.after(0, self._refresh_detail, idx)
        except Exception:
            pass  # miniatura es opcional
        finally:
            self.root.after(0, lambda: self.lbl_spin.config(text=""))

    def _refresh_detail(self, idx: int):
        if self.current_idx == idx:
            with self._results_lock:
                if 0 <= idx < len(self.resultados):
                    self._populate_detail(self.resultados[idx])

    def _reset_detail(self):
        for lbl in (self.d_title, self.d_channel, self.d_dur, self.d_date, self.d_views):
            lbl.config(text="—")
        self.thumb_lbl.config(image="",
                              text="Selecciona un\nvideo para ver\nla info",
                              width=THUMB_W, height=THUMB_H)
        self.lbl_spin.config(text="")
        self._thumb_ref = None

    # ══════════════════ YOUTUBE / CLIPBOARD ══════════════════════
    def _sel_url(self) -> str:
        sel = self.tree.selection()
        if not sel:
            return ""
        idx = self.tree.index(sel[0])
        with self._results_lock:
            return self.resultados[idx].get("url", "") if idx < len(self.resultados) else ""

    def _open_yt(self):
        url = self._sel_url()
        if url:
            webbrowser.open(url)

    def _copy_url(self):
        url = self._sel_url()
        if url:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self._status("URL copiada al portapapeles.", GREEN)

    # ══════════════════ BUSQUEDA ══════════════════════════════════
    def _buscar(self):
        q = self.ent.get().strip()
        if not q or q == PLACEHOLDER:
            return
        if self._search_proc and self._search_proc.poll() is None:
            self._search_proc.terminate()
        self.btn_bus.config(state="disabled")
        self._status(f"Buscando: {q}...", ACCENT)
        threading.Thread(target=self._search_worker, args=(q,), daemon=True).start()

    def _search_worker(self, q: str):
        target = q if q.startswith("http") else f"ytsearch15:{q}"
        fmt = "%(title)s\t%(uploader)s\t%(webpage_url)s\t%(duration_string)s"
        cmd = ["yt-dlp", "--print", fmt, "--flat-playlist", "--no-warnings", target]
        try:
            self._search_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace")

            local_results: list = []
            # Limpiar UI y panel de detalle
            self.root.after(0, lambda: [self.tree.delete(i) for i in self.tree.get_children()])
            self.root.after(0, self._reset_detail)

            for line in self._search_proc.stdout:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 3:
                    res = {
                        "title":           parts[0],
                        "uploader":        parts[1],
                        "url":             parts[2],
                        "duration_string": parts[3] if len(parts) > 3 else "—",
                    }
                    local_results.append(res)
                    self.root.after(0, lambda r=res: self.tree.insert(
                        "", "end",
                        values=(r["title"], r["uploader"],
                                r["duration_string"], "Listo"),
                        tags=("ready",)))

            self._search_proc.wait()
            with self._results_lock:
                self.resultados = local_results
            self._detail_cache.clear()

            n = len(local_results)
            self.root.after(0, lambda: self._status(
                f"{n} resultados encontrados." if n else "Sin resultados.",
                GREEN if n else YELLOW))
        except FileNotFoundError:
            self.root.after(0, lambda: self._status(
                "yt-dlp no encontrado. Comprueba que está instalado.", RED))
        except Exception as e:
            self.root.after(0, lambda: self._status(f"Error en búsqueda: {e}", RED))
            self.root.after(0, lambda: self._log(f"[SEARCH ERR] {e}"))
        finally:
            self._search_proc = None
            self.root.after(0, lambda: self.btn_bus.config(state="normal"))

    # ══════════════════ ENCOLAR ═══════════════════════════════════
    def _encolar(self):
        sel = self.tree.selection()
        if not sel:
            self._status("Selecciona uno o más resultados primero.", YELLOW)
            return

        # Verificar carpeta de destino
        if not self.session_path or not os.path.isdir(self.session_path):
            self._pick_folder()
            if not self.session_path or not os.path.isdir(self.session_path):
                self._status("Selecciona una carpeta de destino válida.", RED)
                return

        encolados = 0
        with self._results_lock:
            for item in sel:
                idx = self.tree.index(item)
                if idx >= len(self.resultados):
                    continue
                tags = self.tree.item(item, "tags")
                if tags and tags[0] in ("queued", "downloading"):
                    continue
                v = self.resultados[idx]
                dur = v.get("duration_string") or "—"
                self.tree.item(item, values=(v["title"], v["uploader"], dur, "En cola"))
                self._row_tag(item, "queued")
                self.cola.put({**v, "path": self.session_path,
                               "fmt": self.fmt.get(), "tree_id": item})
                self._log(f"[QUEUE] {v['title']}")
                encolados += 1

        self._qcount()
        if encolados:
            with self._dl_lock:
                if not self._descargando:
                    self._descargando = True
                    threading.Thread(target=self._dl_worker, daemon=True).start()

    # ══════════════════ WORKER DE DESCARGA ═══════════════════════
    def _dl_worker(self):
        while True:
            try:
                t = self.cola.get(timeout=0.5)
            except queue.Empty:
                break

            # Captura local de t para evitar bug de closure en lambdas
            title     = t["title"]
            uploader  = t["uploader"]
            dur       = t.get("duration_string") or "—"
            tree_id   = t["tree_id"]
            url       = t["url"]
            fmt       = t["fmt"]
            path      = t["path"]

            def _set_row(label: str, tag: str,
                         _id=tree_id, _ti=title, _up=uploader, _du=dur):
                if self.tree.exists(_id):                     # <--- CORRECCIÓN
                    self.tree.item(_id, values=(_ti, _up, _du, label))
                    self._row_tag(_id, tag)

            self.root.after(0, lambda: _set_row("Descargando...", "downloading"))
            self.root.after(0, lambda _t=title: self._status(f"Descargando: {_t[:50]}", CYAN))
            self.root.after(0, self._qcount)

            # Sanitizar nombre para la plantilla de salida
            clean = self._sanitize_filename(title)
            out_tmpl = os.path.join(path, f"{clean}.%(ext)s")

            if fmt == "mp3":
                cmd = [
                    "yt-dlp", "--newline", "--no-warnings",
                    "-o", out_tmpl,
                    "--extract-audio", "--audio-format", "mp3",
                    "--audio-quality", "0",
                    "--embed-thumbnail", "--add-metadata",
                    "--parse-metadata", "%(uploader)s:%(meta_artist)s",
                    url,
                ]
            else:
                cmd = [
                    "yt-dlp", "--newline", "--no-warnings",
                    "-o", out_tmpl,
                    "-f", "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
                    "--merge-output-format", "mp4",
                    "--embed-thumbnail", "--add-metadata",
                    url,
                ]

            try:
                self._dl_proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace")

                for line in self._dl_proc.stdout:
                    stripped = line.rstrip()
                    self.root.after(0, lambda l=stripped: self._log(f"[DL] {l}"))

                self._dl_proc.wait()
                ok = self._dl_proc.returncode == 0
                lbl = "Completado" if ok else "Error"
                tag = "done"      if ok else "error"
                self.root.after(0, lambda l=lbl, g=tag: _set_row(l, g))
                self.root.after(0, lambda _t=title, _ok=ok:
                                self._log(f"[{'OK' if _ok else 'ERR'}] {_t}"))
            except FileNotFoundError:
                self.root.after(0, lambda: self._status(
                    "yt-dlp no encontrado.", RED))
                self.root.after(0, lambda: _set_row("Error", "error"))
            except Exception as e:
                self.root.after(0, lambda err=e: self._log(f"[DL ERR] {err}"))
                self.root.after(0, lambda: _set_row("Error", "error"))
            finally:
                self._dl_proc = None
                self.cola.task_done()
                self.root.after(0, self._qcount)

        with self._dl_lock:
            self._descargando = False
        self.root.after(0, lambda: self._status("Todas las descargas completadas.", GREEN))

    def _on_close(self):
        if self._search_proc and self._search_proc.poll() is None:
            self._search_proc.terminate()
        if self._dl_proc and self._dl_proc.poll() is None:
            self._dl_proc.terminate()
        self.root.destroy()


# ─────────────────────────── MAIN ────────────────────────────────
if __name__ == "__main__":
    if not PIL_AVAILABLE:
        print("[YouMuDow] Pillow no instalado — miniaturas desactivadas.")
        print("  Instala con:  pip install pillow\n")
    root = tk.Tk()
    root.resizable(True, True)
    YouMuDow(root)
    root.mainloop()
