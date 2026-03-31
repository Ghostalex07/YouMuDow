"""
YouMuDow v4.1 — Ultra Edition (Mejorado)
Requisitos: yt-dlp (pip install yt-dlp) + ffmpeg + tkinter
Opcional:   pip install pillow   (miniaturas en el panel de detalle)
"""

import tkinter as tk
from tkinter import ttk, filedialog
import threading
import queue
import os
import webbrowser
import urllib.request
import io
from datetime import datetime
import re
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from yt_dlp import YoutubeDL

# ──────────────────────────── YT‑DLP BASE CONFIG ────────────────────────────
BROWSER = "firefox"
DEFAULT_DL = os.path.join(os.path.expanduser("~"), "Downloads")
PLACEHOLDER = "Busca en YouTube o pega una URL…"
THUMB_W, THUMB_H = 228, 128

# Paleta de colores
BG      = "#090909"
BG2     = "#111111"
BG3     = "#1a1a1a"
BG4     = "#242424"
BG5     = "#2e2e2e"
ACCENT  = "#8b5cf6"
ACCH    = "#7c3aed"
GREEN   = "#34d399"
RED     = "#f87171"
YELLOW  = "#fbbf24"
CYAN    = "#38bdf8"
FG      = "#ececec"
FGDIM   = "#3a3a3a"
FGMID   = "#666666"
FGSUB   = "#999999"
MONO    = ("Consolas", 9)

class _Tooltip:
    def __init__(self, widget: tk.Widget, text_fn):
        self._w = widget
        self._fn = text_fn
        self._tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, event=None):
        text = self._fn()
        if not text:
            return
        x = self._w.winfo_rootx() + 4
        y = self._w.winfo_rooty() + self._w.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self._w)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=text, bg=BG4, fg=FG,
                 font=("Segoe UI", 8), padx=8, pady=4,
                 relief="flat").pack()

    def _hide(self, event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None

class YouMuDow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("YouMuDow  v4.1")
        self.root.geometry("1120x640")
        self._search_proc = None 
        self.root.minsize(820, 520)
        self.root.configure(bg=BG)

        self.cola: queue.Queue = queue.Queue()
        self.resultados: list  = []
        self.thumb_cache: dict = {}
        self.current_idx: int  = -1
        self.session_path: str = DEFAULT_DL
        self.debug_visible     = False
        self._thumb_ref        = None
        self.search_cache      = {}
        self.executor          = ThreadPoolExecutor(max_workers=3)
        self.active_downloads  = 0
        self.active_lock       = threading.Lock()

        self._dl_lock       = threading.Lock()
        self._descargando   = False
        self._results_lock  = threading.Lock()
        self._detail_cache  = set()

        self._apply_style()
        self._build_ui()

        short = DEFAULT_DL if len(DEFAULT_DL) <= 34 else "…" + DEFAULT_DL[-32:]
        self.lbl_path.config(text=short, fg=FGSUB)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _encolar(self):
        sel = self.tree.selection()
        if not sel:
            self._status("No hay elementos seleccionados para encolar.", RED)
            return
        with self._results_lock:
            for item in sel:
                idx = self.tree.index(item)
                if 0 <= idx < len(self.resultados):
                    self.cola.put(self.resultados[idx])
                    self._row_tag(item, "queued")
        self._qcount()
        self._status(f"{len(sel)} video(s) añadido(s) a la cola.", GREEN)
    
    # Lanzar la descarga en un hilo
    threading.Thread(target=self._descargar_cola, daemon=True).start()
    
    def _descargar_cola(self):
        while not self.cola.empty():
            video = self.cola.get()
            url = video.get("url")
            title = self._sanitize_filename(video.get("title", "video"))
            if not url:
                continue

            self._row_tag(self.tree.get_children()[self.resultados.index(video)], "downloading")
            self._show_progress()

            fmt = self.fmt.get()
            out_file = os.path.join(self.session_path, f"{title}.{'mp3' if fmt=='mp3' else 'mp4'}")

            ydl_opts = {
                'format': 'bestaudio/best' if fmt == 'mp3' else 'bestvideo+bestaudio/best',
                'outtmpl': out_file,
                'quiet': True,
                'no_warnings': True,
            }

            if fmt == 'mp3':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]

            try:
                with self._dl_lock:
                    self.active_downloads += 1
                self._log(f"Iniciando descarga: {title}")
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                self._row_tag(self.tree.get_children()[self.resultados.index(video)], "done")
                self._log(f"Descargado: {title}")
            except Exception as e:
                self._row_tag(self.tree.get_children()[self.resultados.index(video)], "error")
                self._log(f"[ERROR] {title}: {e}")
            finally:
                with self._dl_lock:
                    self.active_downloads -= 1
                self._hide_progress()
    
    def _on_close(self):
        """Cerrar la aplicación limpiamente"""
        # Si hay descargas activas, podrías preguntar antes de salir
        if self.active_downloads > 0:
            import tkinter.messagebox as mb
            if not mb.askokcancel("Salir", "Hay descargas en curso. ¿Salir de todas formas?"):
                return
        self.root.destroy()

    def _apply_style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("TLabelframe", background=BG2, foreground=FGMID)
        s.configure("TLabelframe.Label", background=BG2, foreground=FGMID, font=("Segoe UI", 8))
        s.configure("TEntry", fieldbackground=BG3, foreground=FG, insertcolor=FG, borderwidth=0)
        s.configure("TRadiobutton", background=BG, foreground=FG, indicatorcolor=ACCENT)
        s.map("TRadiobutton", background=[("active", BG)])

        s.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Segoe UI", 10, "bold"), padding=(14, 7), relief="flat")
        s.map("Accent.TButton", background=[("active", ACCH), ("disabled", BG3)], foreground=[("disabled", FGMID)])

        s.configure("Ghost.TButton", background=BG3, foreground=FG, font=("Segoe UI", 9), padding=(8, 5), relief="flat")
        s.map("Ghost.TButton", background=[("active", BG4)])

        s.configure("SmGhost.TButton", background=BG3, foreground=FGMID, font=("Segoe UI", 8), padding=(5, 3), relief="flat")
        s.map("SmGhost.TButton", background=[("active", BG4)], foreground=[("active", FG)])

        s.configure("Treeview", background=BG2, fieldbackground=BG2, foreground=FG, rowheight=28, borderwidth=0, font=("Segoe UI", 9))
        s.configure("Treeview.Heading", background=BG3, foreground=FGMID, font=("Segoe UI", 8, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])

        s.configure("Vertical.TScrollbar", background=BG3, troughcolor=BG, arrowcolor=FGMID, borderwidth=0, relief="flat")

        s.configure("Dl.Horizontal.TProgressbar", troughcolor=BG3, background=ACCENT, borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)

    def _build_ui(self):
        top = tk.Frame(self.root, bg=BG, pady=10)
        top.pack(fill="x", padx=14)

        tk.Label(top, text="YouMuDow", bg=BG, fg=FG, font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(top, text=" v4.1", bg=BG, fg=ACCENT, font=("Segoe UI", 11)).pack(side="left", padx=(0, 20))

        sb_outer = tk.Frame(top, bg=BG4, padx=1, pady=1)
        sb_outer.pack(side="left", fill="x", expand=True, padx=(0, 8))
        sb = tk.Frame(sb_outer, bg=BG3, padx=10, pady=7)
        sb.pack(fill="both", expand=True)

        self.ent = tk.Entry(sb, bg=BG3, fg=FGMID, insertbackground=FG, relief="flat", font=("Segoe UI", 10), bd=0)
        self.ent.insert(0, PLACEHOLDER)
        self.ent.pack(fill="x", expand=True)
        self.ent.bind("<FocusIn>", self._ph_in)
        self.ent.bind("<FocusOut>", self._ph_out)
        self.ent.bind("<Return>", lambda _: self._buscar())
        self.ent.bind("<Control-a>", lambda _: (self.ent.selection_range(0, tk.END), "break")[1])

        self.btn_bus = ttk.Button(top, text="Search", style="Accent.TButton", command=self._buscar)
        self.btn_bus.pack(side="left")

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=(4, 4))

        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        cols = ("title", "channel", "duration", "status")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=14, selectmode="extended")
        self.tree.heading("title", text="TÍTULO", anchor="w")
        self.tree.heading("channel", text="CANAL", anchor="w")
        self.tree.heading("duration", text="DURACIÓN", anchor="center")
        self.tree.heading("status", text="ESTADO", anchor="center")
        self.tree.column("title", anchor="w", stretch=True)
        self.tree.column("channel", anchor="w", width=170, stretch=False)
        self.tree.column("duration", anchor="center", width=80, stretch=False)
        self.tree.column("status", anchor="center", width=140, stretch=False)

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        for tag, color in [("ready", FG), ("queued", YELLOW), ("downloading", CYAN), ("done", GREEN), ("error", RED)]:
            self.tree.tag_configure(tag, foreground=color)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-Button-1>", lambda _: self._open_yt())
        self.tree.bind("<Button-3>", self._on_rclick)
        self.tree.bind("<Delete>", self._delete_selected)
        self.tree.bind("<Control-a>", self._select_all)

        right = tk.Frame(main, bg=BG2, width=256)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)
        self._build_detail(right)

        ctrl = tk.Frame(self.root, bg=BG, pady=6)
        ctrl.pack(fill="x", padx=14)

        fbox = tk.Frame(ctrl, bg=BG3, padx=10, pady=6)
        fbox.pack(side="left")
        tk.Label(fbox, text="Formato:", bg=BG3, fg=FGMID, font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self.fmt = tk.StringVar(value="mp3")
        for v, l in (("mp3", "MP3"), ("mp4", "MP4")):
            ttk.Radiobutton(fbox, text=l, variable=self.fmt, value=v).pack(side="left", padx=4)

        pbox = tk.Frame(ctrl, bg=BG3, padx=10, pady=6)
        pbox.pack(side="left", padx=8)
        tk.Label(pbox, text="Carpeta:", bg=BG3, fg=FGMID, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.lbl_path = tk.Label(pbox, text="…", bg=BG3, fg=FGMID, font=("Segoe UI", 9), cursor="hand2")
        self.lbl_path.pack(side="left")
        self.lbl_path.bind("<Button-1>", lambda _: self._pick_folder())
        _Tooltip(self.lbl_path, lambda: self.session_path)

        ttk.Button(pbox, text="…", style="Ghost.TButton", command=self._pick_folder, width=2).pack(side="left", padx=(4, 0))

        bb = tk.Frame(ctrl, bg=BG)
        bb.pack(side="right")
        ttk.Button(bb, text="Abrir carpeta", style="Ghost.TButton", command=self._open_folder).pack(side="right", padx=4)
        ttk.Button(bb, text="Vaciar cola", style="Ghost.TButton", command=self._clear_queue).pack(side="right")
        ttk.Button(bb, text="+ Añadir a cola", style="Accent.TButton", command=self._encolar).pack(side="right", padx=6)

        self.sbar = tk.Frame(self.root, bg=BG3, pady=0)
        self.sbar.pack(fill="x", side="bottom")
        tk.Frame(self.sbar, bg=BG4, height=1).pack(fill="x")
        inner = tk.Frame(self.sbar, bg=BG3, pady=4)
        inner.pack(fill="x")

        self.lbl_status = tk.Label(inner, text="Listo.", bg=BG3, fg=FGMID, font=("Segoe UI", 8), anchor="w")
        self.lbl_status.pack(side="left", padx=10)

        self.progress_var = tk.DoubleVar(value=0)
        self.pbar = ttk.Progressbar(inner, variable=self.progress_var, maximum=100, length=180, style="Dl.Horizontal.TProgressbar")
        self.lbl_speed = tk.Label(inner, text="", bg=BG3, fg=CYAN, font=("Segoe UI", 8))
        self.lbl_qc = tk.Label(inner, text="Cola: 0", bg=BG3, fg=FGMID, font=("Segoe UI", 8))
        self.lbl_qc.pack(side="right", padx=10)

        ttk.Button(inner, text="Logs", style="SmGhost.TButton", command=self._toggle_log).pack(side="right", padx=4)

        if not PIL_AVAILABLE:
            tk.Label(inner, text="(instala Pillow para miniaturas)", bg=BG3, fg=FGDIM, font=("Segoe UI", 7)).pack(side="right", padx=6)

        self.f_log = ttk.LabelFrame(self.root, text="  TERMINAL  ", padding=4)
        self.log = tk.Text(self.f_log, height=9, bg="#050505", fg="#00ff88", font=MONO, relief="flat", state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

        self.ctx = tk.Menu(self.root, tearoff=0, bg=BG3, fg=FG, activebackground=ACCENT, activeforeground="white", font=("Segoe UI", 9), bd=0, relief="flat")
        self.ctx.add_command(label="  Abrir en YouTube", command=self._open_yt)
        self.ctx.add_command(label="  Copiar URL", command=self._copy_url)
        self.ctx.add_separator()
        self.ctx.add_command(label="  Añadir a la cola", command=self._encolar)
        self.ctx.add_command(label="  Eliminar de la lista", command=self._delete_selected)

    def _build_detail(self, parent: tk.Frame):
        tk.Label(parent, text="INFO DEL VIDEO", bg=BG2, fg=FGDIM, font=("Segoe UI", 7, "bold")).pack(pady=(12, 6))

        thumb_frame = tk.Frame(parent, bg=BG4, padx=1, pady=1)
        thumb_frame.pack(padx=12)
        self.thumb_lbl = tk.Label(thumb_frame, bg="#080808", text="Selecciona un\nvideo para ver\nla info", fg=FGMID, font=("Segoe UI", 9), width=THUMB_W, height=THUMB_H)
        self.thumb_lbl.pack()

        self.lbl_spin = tk.Label(parent, text="", bg=BG2, fg=FGMID, font=("Segoe UI", 8))
        self.lbl_spin.pack()

        tk.Frame(parent, bg=BG4, height=1).pack(fill="x", padx=12, pady=6)

        info = tk.Frame(parent, bg=BG2)
        info.pack(fill="x", padx=12)

        self.d_title   = self._dl(info, bold=True, wrap=224)
        self.d_channel = self._dl(info, color=CYAN,  size=8)
        self.d_dur     = self._dl(info, color=FGSUB, size=8)
        self.d_date    = self._dl(info, color=FGSUB, size=8)
        self.d_views   = self._dl(info, color=FGSUB, size=8)

        tk.Frame(parent, bg=BG4, height=1).pack(fill="x", padx=12, pady=8)

        ttk.Button(parent, text="Abrir en YouTube", style="Ghost.TButton", command=self._open_yt).pack(fill="x", padx=12, pady=(0, 4))
        ttk.Button(parent, text="Copiar URL", style="Ghost.TButton", command=self._copy_url).pack(fill="x", padx=12)

    def _dl(self, parent, text="—", bold=False, color=FG, size=9, wrap=0):
        kw = dict(bg=BG2, fg=color, anchor="w", justify="left", text=text, font=("Segoe UI", size, "bold" if bold else "normal"))
        if wrap: kw["wraplength"] = wrap
        lbl = tk.Label(parent, **kw)
        lbl.pack(fill="x", pady=1)
        return lbl

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
        if self.tree.exists(iid):
            self.tree.item(iid, tags=(tag,))

    def _toggle_log(self):
        if not self.debug_visible:
            self.f_log.pack(fill="both", padx=14, pady=(0, 4), before=self.sbar)
            self.debug_visible = True
        else:
            self.f_log.pack_forget()
            self.debug_visible = False

    def _show_progress(self):
        self.pbar.pack(side="left", padx=(6, 4))
        self.lbl_speed.pack(side="left")

    def _hide_progress(self):
        self.pbar.pack_forget()
        self.lbl_speed.pack_forget()
        self.progress_var.set(0)
        self.lbl_speed.config(text="")

    def _pick_folder(self):
        p = filedialog.askdirectory(title="Selecciona carpeta de descarga")
        if p:
            self.session_path = p
            short = p if len(p) <= 34 else "…" + p[-32:]
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

    def _select_all(self, _=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _delete_selected(self, _=None):
        removable_tags = {"ready", "error", "done"}
        to_remove = []
        to_remove_indices = []
        for item in self.tree.selection():
            tags = self.tree.item(item, "tags")
            if not tags or tags[0] in removable_tags:
                to_remove.append(item)
                to_remove_indices.append(self.tree.index(item))
        if not to_remove:
            return
        for item in to_remove:
            self.tree.delete(item)
        with self._results_lock:
            for idx in sorted(to_remove_indices, reverse=True):
                if 0 <= idx < len(self.resultados):
                    self.resultados.pop(idx)

    def _sanitize_filename(self, name: str) -> str:
        name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
        return name[:120]

    def _ph_in(self, _):
        if self.ent.get() == PLACEHOLDER:
            self.ent.delete(0, tk.END)
            self.ent.config(fg=FG)

    def _ph_out(self, _):
        if not self.ent.get():
            self.ent.insert(0, PLACEHOLDER)
            self.ent.config(fg=FGMID)

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
        if self.tree.exists(iid):
            self.tree.item(iid, tags=(tag,))

    def _toggle_log(self):
        if not self.debug_visible:
            self.f_log.pack(fill="both", padx=14, pady=(0, 4), before=self.sbar)
            self.debug_visible = True
        else:
            self.f_log.pack_forget()
            self.debug_visible = False

    def _show_progress(self):
        self.pbar.pack(side="left", padx=(6, 4))
        self.lbl_speed.pack(side="left")

    def _hide_progress(self):
        self.pbar.pack_forget()
        self.lbl_speed.pack_forget()
        self.progress_var.set(0)
        self.lbl_speed.config(text="")

    def _sanitize_filename(self, name: str) -> str:
        name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
        return name[:120]

    def _yt_video_id(self, url: str) -> str:
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
            vid_id = self._yt_video_id(url)
            if vid_id:
                thumb_url = f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"
                with self._results_lock:
                    if idx < len(self.resultados):
                        self.resultados[idx]["thumbnail"] = thumb_url
                if thumb_url in self.thumb_cache:
                    self._refresh_detail(idx)
                elif PIL_AVAILABLE:
                    self.lbl_spin.config(text="Cargando miniatura…")
                    threading.Thread(target=self._load_thumb, args=(thumb_url, idx), daemon=True).start()
            if url not in self._detail_cache:
                self._detail_cache.add(url)
                threading.Thread(target=self._fetch_detail, args=(url, idx), daemon=True).start()
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
        dur = v.get("duration_string", "")
        self.d_dur.config(text=f"  {dur}" if dur else "  —")
        date = v.get("upload_date_fmt", "")
        self.d_date.config(text=f"  {date}" if date else "  —")
        views = v.get("view_count_fmt", "")
        self.d_views.config(text=f"  {views}" if views else "  —")
        tu = v.get("thumbnail", "")
        if tu and tu in self.thumb_cache:
            photo = self.thumb_cache[tu]
            self._thumb_ref = photo
            self.thumb_lbl.config(image=photo, text="", width=THUMB_W, height=THUMB_H)
        else:
            self.thumb_lbl.config(image="", text="Cargando…" if tu else "Sin miniatura", width=THUMB_W, height=THUMB_H)

    def _fetch_detail(self, url: str, idx: int):
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'skip_download': True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                upload_raw = info.get('upload_date', '')
                view_raw = info.get('view_count', '')
                dur_raw = info.get('duration_string', '')

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
                            "view_count_fmt": views_fmt,
                            "duration_string": dur_raw or self.resultados[idx].get("duration_string", ""),
                        })
                self.root.after(0, self._refresh_detail, idx)
        except Exception as e:
            self.root.after(0, lambda: self._log(f"[DETAIL ERR] {e}"))
        finally:
            self.root.after(0, lambda: self.lbl_spin.config(text=""))

    def _load_thumb(self, tu: str, idx: int):
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
            pass
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
        self.thumb_lbl.config(image="", text="Selecciona un\nvideo para ver\nla info", width=THUMB_W, height=THUMB_H)
        self.lbl_spin.config(text="")
        self._thumb_ref = None

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

    def _buscar(self):
        q = self.ent.get().strip()
        if not q or q == PLACEHOLDER:
            return
        if self._search_proc and self._search_proc.poll() is None:
            self._search_proc.terminate()
        self.btn_bus.config(state="disabled")
        self._status(f"Buscando: {q}…", ACCENT)
        self.root.title(f"YouMuDow  v4.1  —  buscando…")
        threading.Thread(target=self._search_worker, args=(q,), daemon=True).start()

    def _search_worker(self, q: str):
        target = q if q.startswith("http") else f"ytsearch15:{q}"
        fmt = "%(title)s\t%(uploader)s\t%(webpage_url)s\t%(duration_string)s"
        ydl_opts = {'quiet': True, 'no_warnings': True}
        cmd = ["yt-dlp", "--print", fmt, "--flat-playlist"] + ydl_opts.get("default_options", []) + [target]

        try:
            self._search_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.root.after(0, lambda: [self.tree.delete(i) for i in self.tree.get_children()])
            self.root.after(0, self._reset_detail)

            local_results = []
            batch = []
            BATCH_SIZE = 5

            def _flush(b: list):
                for r in b:
                    self.tree.insert("", "end", values=(r["title"], r["uploader"], r["duration_string"], "Listo"), tags=("ready",))

            for line in self._search_proc.stdout:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 3:
                    res = {
                        "title": parts[0],
                        "uploader": parts[1],
                        "url": parts[2],
                        "duration_string": parts[3] if len(parts) > 3 else "—",
                    }
                    local_results.append(res)
                    batch.append(res)
                    if len(batch) >= BATCH_SIZE:
                        snapshot = batch[:]
                        batch.clear()
                        self.root.after(0, _flush, snapshot)

            if batch:
                snapshot = batch[:]
                self.root.after(0, _flush, snapshot)

            self._search_proc.wait()
            with self._results_lock:
                self.resultados = local_results
            self._detail_cache.clear()
            self.search_cache[q] = local_results

            n = len(local_results)
            msg = f"{n} resultados encontrados." if n else "Sin resultados."
            color = GREEN if n else YELLOW
            self.root.after(0, lambda: self._status(msg, color))
            self.root.after(0, lambda: self.root.title("YouMuDow  v4.1"))

        except File as e:
            self.root.after(0, lambda: self._log(f"[SEARCH ERR] {e}"))

if __name__ == "__main__":
    root = tk.Tk()
    root.resizable(True, True)
    app = YouMuDow(root)
    root.mainloop()