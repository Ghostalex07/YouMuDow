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

# ─────────────────────────────── COLOR PALETTE ──────────────────────────────────────
BG      = "#090909"
BG2     = "#111111"
BG3     = "#1a1a1a"
BG4     = "#242424"
BG5     = "#2e2e2e"
ACCENT  = "#8b5cf6"   # Vibrant violet
ACCH    = "#7c3aed"
GREEN   = "#34d399"   # Soft emerald
RED     = "#f87171"   # Coral red
YELLOW  = "#fbbf24"
CYAN    = "#38bdf8"
FG      = "#ececec"
FGDIM   = "#3a3a3a"
FGMID   = "#666666"
FGSUB   = "#999999"
MONO    = ("Consolas", 9)

THUMB_W, THUMB_H = 228, 128
PLACEHOLDER      = "Search on YouTube or paste a URL…"
DEFAULT_DL       = os.path.join(os.path.expanduser("~"), "Downloads")

# Regex to parse yt-dlp progress lines
# Example: [download]  45.3% of    8.12MiB at    1.20MiB/s ETA 00:04
_RE_PROGRESS = re.compile(
    r"\[download\]\s+([\d.]+)%.*?at\s+([\d.]+\s*\S+/s)", re.IGNORECASE
)
_RE_PROGRESS_SIMPLE = re.compile(r"\[download\]\s+([\d.]+)%")


# ─────────────────────────────── TOOLTIP ─────────────────────────────────────
class _Tooltip:
    """Minimalist Tooltip with no external dependencies."""
    def __init__(self, widget: tk.Widget, text_fn):
        self._w   = widget
        self._fn  = text_fn
        self._tip = None
        # Bind mouse enter and leave events to show/hide the tooltip
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, event=None):
        text = self._fn()
        if not text:
            return
        # Calculate position for the tooltip
        x = self._w.winfo_rootx() + 4
        y = self._w.winfo_rooty() + self._w.winfo_height() + 4
        self._tip = tw = tk.Toplevel(self._w)
        tw.wm_overrideredirect(True) # Remove window decorations
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=text, bg=BG4, fg=FG,
                 font=("Segoe UI", 8), padx=8, pady=4,
                 relief="flat").pack()

    def _hide(self, event=None):
        # Destroy the tooltip window if it exists
        if self._tip:
            self._tip.destroy()
            self._tip = None


# ─────────────────────────────── APPLICATION ──────────────────────────────────
class YouMuDow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("YouMuDow  v4.1")
        self.root.geometry("1120x640")
        self.root.minsize(820, 520)
        self.root.configure(bg=BG)

        # Application state variables
        self.cola: queue.Queue = queue.Queue()
        self.resultados: list  = []
        self.thumb_cache: dict = {}
        self.current_idx: int  = -1
        self.session_path: str = DEFAULT_DL
        self.debug_visible     = False
        self._thumb_ref        = None

        # Threading locks and process handles
        self._dl_lock       = threading.Lock()
        self._descargando   = False
        self._dl_proc: subprocess.Popen | None     = None
        self._search_proc: subprocess.Popen | None = None
        self._results_lock  = threading.Lock()
        self._detail_cache  = set()

        # Initialize UI and styles
        self._apply_style()
        self._build_ui()

        # Format default path for display
        short = DEFAULT_DL if len(DEFAULT_DL) <= 34 else "…" + DEFAULT_DL[-32:]
        self.lbl_path.config(text=short, fg=FGSUB)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ═══════════════════════════ STYLES ═══════════════════════════════════════
    def _apply_style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        
        # General configurations
        s.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
        s.configure("TFrame",            background=BG)
        s.configure("TLabel",            background=BG, foreground=FG)
        s.configure("TLabelframe",       background=BG2, foreground=FGMID)
        s.configure("TLabelframe.Label", background=BG2, foreground=FGMID,
                    font=("Segoe UI", 8))
        s.configure("TEntry",
                    fieldbackground=BG3, foreground=FG,
                    insertcolor=FG, borderwidth=0)
        s.configure("TRadiobutton", background=BG, foreground=FG,
                    indicatorcolor=ACCENT)
        s.map("TRadiobutton", background=[("active", BG)])

        # Accent buttons
        s.configure("Accent.TButton",
                    background=ACCENT, foreground="white",
                    font=("Segoe UI", 10, "bold"),
                    padding=(14, 7), relief="flat")
        s.map("Accent.TButton",
              background=[("active", ACCH), ("disabled", BG3)],
              foreground=[("disabled", FGMID)])

        # Ghost buttons (transparent/subtle)
        s.configure("Ghost.TButton",
                    background=BG3, foreground=FG,
                    font=("Segoe UI", 9), padding=(8, 5), relief="flat")
        s.map("Ghost.TButton", background=[("active", BG4)])

        # Small ghost buttons
        s.configure("SmGhost.TButton",
                    background=BG3, foreground=FGMID,
                    font=("Segoe UI", 8), padding=(5, 3), relief="flat")
        s.map("SmGhost.TButton",
              background=[("active", BG4)], foreground=[("active", FG)])

        # Treeview (Data grid) configurations
        s.configure("Treeview",
                    background=BG2, fieldbackground=BG2, foreground=FG,
                    rowheight=28, borderwidth=0, font=("Segoe UI", 9))
        s.configure("Treeview.Heading",
                    background=BG3, foreground=FGMID,
                    font=("Segoe UI", 8, "bold"), relief="flat")
        s.map("Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", "white")])

        # Scrollbar configuration
        s.configure("Vertical.TScrollbar",
                    background=BG3, troughcolor=BG,
                    arrowcolor=FGMID, borderwidth=0, relief="flat")

        # Custom progress bar
        s.configure("Dl.Horizontal.TProgressbar",
                    troughcolor=BG3, background=ACCENT,
                    borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)

    # ═══════════════════════════ UI ═══════════════════════════════════════════
    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        top = tk.Frame(self.root, bg=BG, pady=10)
        top.pack(fill="x", padx=14)

        tk.Label(top, text="YouMuDow", bg=BG, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(top, text=" v4.1", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11)).pack(side="left", padx=(0, 20))

        # Search box with simulated accent border
        sb_outer = tk.Frame(top, bg=BG4, padx=1, pady=1)
        sb_outer.pack(side="left", fill="x", expand=True, padx=(0, 8))
        sb = tk.Frame(sb_outer, bg=BG3, padx=10, pady=7)
        sb.pack(fill="both", expand=True)

        # Search entry field
        self.ent = tk.Entry(sb, bg=BG3, fg=FGMID, insertbackground=FG,
                            relief="flat", font=("Segoe UI", 10), bd=0)
        self.ent.insert(0, PLACEHOLDER)
        self.ent.pack(fill="x", expand=True)
        # Event bindings for placeholder and search triggers
        self.ent.bind("<FocusIn>",   self._ph_in)
        self.ent.bind("<FocusOut>",  self._ph_out)
        self.ent.bind("<Return>",    lambda _: self._buscar())
        self.ent.bind("<Control-a>", lambda _: (self.ent.selection_range(0, tk.END), "break")[1])

        self.btn_bus = ttk.Button(top, text="Search",
                                  style="Accent.TButton", command=self._buscar)
        self.btn_bus.pack(side="left")

        # ── Main Central Area ─────────────────────────────────────────────────
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=(4, 4))

        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        # Treeview (results list)
        cols = ("title", "channel", "duration", "status")
        self.tree = ttk.Treeview(left, columns=cols,
                                 show="headings", height=14,
                                 selectmode="extended")
        self.tree.heading("title",    text="TITLE",    anchor="w")
        self.tree.heading("channel",  text="CHANNEL",  anchor="w")
        self.tree.heading("duration", text="DURATION", anchor="center")
        self.tree.heading("status",   text="STATUS",   anchor="center")
        
        self.tree.column("title",    anchor="w",      stretch=True)
        self.tree.column("channel",  anchor="w",      width=170, stretch=False)
        self.tree.column("duration", anchor="center", width=80,  stretch=False)
        self.tree.column("status",   anchor="center", width=140, stretch=False)

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        # Tags for coloring rows based on status
        for tag, color in [
            ("ready",       FG),
            ("queued",      YELLOW),
            ("downloading", CYAN),
            ("done",        GREEN),
            ("error",       RED),
        ]:
            self.tree.tag_configure(tag, foreground=color)

        # Bindings for treeview interactions
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-Button-1>",  lambda _: self._open_yt())
        self.tree.bind("<Button-3>",         self._on_rclick) # Right click
        # Shortcuts: Del -> delete ready rows · Ctrl+A -> select all
        self.tree.bind("<Delete>",           self._delete_selected)
        self.tree.bind("<Control-a>",        self._select_all)

        # Right side detail panel
        right = tk.Frame(main, bg=BG2, width=256)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)
        self._build_detail(right)

        # ── Bottom Controls ───────────────────────────────────────────────────
        ctrl = tk.Frame(self.root, bg=BG, pady=6)
        ctrl.pack(fill="x", padx=14)

        # Format selector (MP3/MP4)
        fbox = tk.Frame(ctrl, bg=BG3, padx=10, pady=6)
        fbox.pack(side="left")
        tk.Label(fbox, text="Format:", bg=BG3, fg=FGMID,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self.fmt = tk.StringVar(value="mp3")
        for v, l in (("mp3", "MP3"), ("mp4", "MP4")):
            ttk.Radiobutton(fbox, text=l, variable=self.fmt,
                            value=v).pack(side="left", padx=4)

        # Download path selector
        pbox = tk.Frame(ctrl, bg=BG3, padx=10, pady=6)
        pbox.pack(side="left", padx=8)
        tk.Label(pbox, text="Folder:", bg=BG3, fg=FGMID,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.lbl_path = tk.Label(pbox, text="…", bg=BG3, fg=FGMID,
                                  font=("Segoe UI", 9), cursor="hand2")
        self.lbl_path.pack(side="left")
        self.lbl_path.bind("<Button-1>", lambda _: self._pick_folder())
        _Tooltip(self.lbl_path, lambda: self.session_path)

        ttk.Button(pbox, text="…", style="Ghost.TButton",
                   command=self._pick_folder, width=2).pack(side="left", padx=(4, 0))

        # Action buttons
        bb = tk.Frame(ctrl, bg=BG)
        bb.pack(side="right")
        ttk.Button(bb, text="Open Folder",   style="Ghost.TButton",
                   command=self._open_folder).pack(side="right", padx=4)
        ttk.Button(bb, text="Clear Queue",     style="Ghost.TButton",
                   command=self._clear_queue).pack(side="right")
        ttk.Button(bb, text="+ Add to Queue", style="Accent.TButton",
                   command=self._encolar).pack(side="right", padx=6)

        # ── Status Bar ────────────────────────────────────────────────────────
        self.sbar = tk.Frame(self.root, bg=BG3, pady=0)
        self.sbar.pack(fill="x", side="bottom")

        # Visual separator for the status bar
        tk.Frame(self.sbar, bg=BG4, height=1).pack(fill="x")

        inner = tk.Frame(self.sbar, bg=BG3, pady=4)
        inner.pack(fill="x")

        self.lbl_status = tk.Label(inner, text="Ready.", bg=BG3, fg=FGMID,
                                    font=("Segoe UI", 8), anchor="w")
        self.lbl_status.pack(side="left", padx=10)

        # Progress bar (hidden until there is an active download)
        self.progress_var = tk.DoubleVar(value=0)
        self.pbar = ttk.Progressbar(inner, variable=self.progress_var,
                                    maximum=100, length=180,
                                    style="Dl.Horizontal.TProgressbar")
        self.lbl_speed = tk.Label(inner, text="", bg=BG3, fg=CYAN,
                                   font=("Segoe UI", 8))

        self.lbl_qc = tk.Label(inner, text="Queue: 0", bg=BG3, fg=FGMID,
                                font=("Segoe UI", 8))
        self.lbl_qc.pack(side="right", padx=10)

        ttk.Button(inner, text="Logs", style="SmGhost.TButton",
                   command=self._toggle_log).pack(side="right", padx=4)

        if not PIL_AVAILABLE:
            tk.Label(inner, text="(install Pillow for thumbnails)",
                     bg=BG3, fg=FGDIM, font=("Segoe UI", 7)).pack(side="right", padx=6)

        # ── Logs Panel (hidden by default) ────────────────────────────────────
        self.f_log = ttk.LabelFrame(self.root, text="  TERMINAL  ", padding=4)
        self.log = tk.Text(self.f_log, height=9, bg="#050505", fg="#00ff88",
                           font=MONO, relief="flat", state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

        # ── Context Menu ──────────────────────────────────────────────────────
        self.ctx = tk.Menu(self.root, tearoff=0, bg=BG3, fg=FG,
                           activebackground=ACCENT, activeforeground="white",
                           font=("Segoe UI", 9), bd=0, relief="flat")
        self.ctx.add_command(label="  Open in YouTube", command=self._open_yt)
        self.ctx.add_command(label="  Copy URL",        command=self._copy_url)
        self.ctx.add_separator()
        self.ctx.add_command(label="  Add to queue", command=self._encolar)
        self.ctx.add_command(label="  Remove from list", command=self._delete_selected)

    # ── Side Detail Panel ─────────────────────────────────────────────────────
    def _build_detail(self, parent: tk.Frame):
        tk.Label(parent, text="VIDEO INFO", bg=BG2, fg=FGDIM,
                 font=("Segoe UI", 7, "bold")).pack(pady=(12, 6))

        # Subtle border frame for the thumbnail
        thumb_frame = tk.Frame(parent, bg=BG4, padx=1, pady=1)
        thumb_frame.pack(padx=12)
        self.thumb_lbl = tk.Label(
            thumb_frame, bg="#080808",
            text="Select a\nvideo to see\nthe info",
            fg=FGMID, font=("Segoe UI", 9),
            width=THUMB_W, height=THUMB_H)
        self.thumb_lbl.pack()

        self.lbl_spin = tk.Label(parent, text="", bg=BG2, fg=FGMID,
                                  font=("Segoe UI", 8))
        self.lbl_spin.pack()

        tk.Frame(parent, bg=BG4, height=1).pack(fill="x", padx=12, pady=6)

        info = tk.Frame(parent, bg=BG2)
        info.pack(fill="x", padx=12)

        # Video metadata labels
        self.d_title   = self._dl(info, bold=True, wrap=224)
        self.d_channel = self._dl(info, color=CYAN,  size=8)
        self.d_dur     = self._dl(info, color=FGSUB, size=8)
        self.d_date    = self._dl(info, color=FGSUB, size=8)
        self.d_views   = self._dl(info, color=FGSUB, size=8)

        tk.Frame(parent, bg=BG4, height=1).pack(fill="x", padx=12, pady=8)

        ttk.Button(parent, text="Open in YouTube",
                   style="Ghost.TButton",
                   command=self._open_yt).pack(fill="x", padx=12, pady=(0, 4))
        ttk.Button(parent, text="Copy URL",
                   style="Ghost.TButton",
                   command=self._copy_url).pack(fill="x", padx=12)

    def _dl(self, parent, text="—", bold=False, color=FG, size=9, wrap=0):
        # Helper method to create metadata labels
        kw = dict(bg=BG2, fg=color, anchor="w", justify="left", text=text,
                  font=("Segoe UI", size, "bold" if bold else "normal"))
        if wrap:
            kw["wraplength"] = wrap
        lbl = tk.Label(parent, **kw)
        lbl.pack(fill="x", pady=1)
        return lbl

    # ═══════════════════ PLACEHOLDER ENTRY ════════════════════════════════════
    def _ph_in(self, _):
        # Clear placeholder text on focus
        if self.ent.get() == PLACEHOLDER:
            self.ent.delete(0, tk.END)
            self.ent.config(fg=FG)

    def _ph_out(self, _):
        # Restore placeholder if entry is empty
        if not self.ent.get():
            self.ent.insert(0, PLACEHOLDER)
            self.ent.config(fg=FGMID)

    # ═══════════════════ HELPERS ══════════════════════════════════════════════
    def _status(self, msg: str, color=FGMID):
        self.lbl_status.config(text=msg, fg=color)

    def _qcount(self):
        self.lbl_qc.config(text=f"Queue: {self.cola.qsize()}")

    def _log(self, txt: str):
        # Insert log text into the terminal view
        self.log.config(state="normal")
        self.log.insert(tk.END, txt + "\n")
        self.log.see(tk.END)
        self.log.config(state="disabled")

    def _row_tag(self, iid: str, tag: str):
        if self.tree.exists(iid):
            self.tree.item(iid, tags=(tag,))

    def _toggle_log(self):
        # Show or hide the logs panel
        if not self.debug_visible:
            self.f_log.pack(fill="both", padx=14, pady=(0, 4), before=self.sbar)
            self.debug_visible = True
        else:
            self.f_log.pack_forget()
            self.debug_visible = False

    def _show_progress(self):
        """Shows the progress bar and speed label."""
        self.pbar.pack(side="left", padx=(6, 4))
        self.lbl_speed.pack(side="left")

    def _hide_progress(self):
        """Hides the progress bar and resets variables."""
        self.pbar.pack_forget()
        self.lbl_speed.pack_forget()
        self.progress_var.set(0)
        self.lbl_speed.config(text="")

    def _pick_folder(self):
        # Open dialog to pick a download directory
        p = filedialog.askdirectory(title="Select download folder")
        if p:
            self.session_path = p
            short = p if len(p) <= 34 else "…" + p[-32:]
            self.lbl_path.config(text=short, fg=FG)

    def _open_folder(self):
        # Open the current download folder in the OS file explorer
        if self.session_path and os.path.isdir(self.session_path):
            if os.name == "nt":
                os.startfile(self.session_path)
            else:
                subprocess.Popen(["xdg-open", self.session_path])
        else:
            self._status("No valid folder selected.", RED)

    def _clear_queue(self):
        # Empty the queue thread-safely
        with self.cola.mutex:
            self.cola.queue.clear()
        self._qcount()
        self._status("Queue cleared.")

    def _select_all(self, _=None):
        """Ctrl+A: Select all rows in the tree."""
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _delete_selected(self, _=None):
        """Del: Delete selected rows that are 'ready', 'done', or 'error'."""
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
        # Remove from results list as well (in reverse order to maintain index validity)
        with self._results_lock:
            for idx in sorted(to_remove_indices, reverse=True):
                if 0 <= idx < len(self.resultados):
                    self.resultados.pop(idx)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        # Sanitize string to make it a safe filename
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()

    # ═══════════════════ SELECTION / DETAIL ══════════════════════════════════
    @staticmethod
    def _yt_video_id(url: str) -> str:
        # Extract YouTube video ID from standard URLs
        m = re.search(r'(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})', url)
        return m.group(1) if m else ""

    def _on_select(self, _=None):
        # Handle user clicking on a row in the treeview
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
            
            # Request thumbnail fetching
            vid_id = self._yt_video_id(url)
            if vid_id:
                thumb_url = f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg"
                with self._results_lock:
                    if idx < len(self.resultados):
                        self.resultados[idx]["thumbnail"] = thumb_url
                if thumb_url in self.thumb_cache:
                    self._refresh_detail(idx)
                elif PIL_AVAILABLE:
                    self.lbl_spin.config(text="Loading thumbnail…")
                    threading.Thread(target=self._load_thumb,
                                     args=(thumb_url, idx), daemon=True).start()
            
            # Fetch extra metadata if not cached yet
            if url not in self._detail_cache:
                self._detail_cache.add(url)
                threading.Thread(target=self._fetch_detail,
                                 args=(url, idx), daemon=True).start()
        except Exception as e:
            self._log(f"[SELECT ERR] {e}")

    def _on_rclick(self, event):
        # Handle right click context menu on the treeview
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.ctx.tk_popup(event.x_root, event.y_root)

    def _populate_detail(self, v: dict):
        # Update UI details panel with selected video info
        self.d_title.config(text=v.get("title", "—"))
        self.d_channel.config(text="  " + v.get("uploader", "—"))
        dur = v.get("duration_string", "")
        self.d_dur.config(text=f"  {dur}" if dur else "  —")
        date = v.get("upload_date_fmt", "")
        self.d_date.config(text=f"  {date}" if date else "  —")
        views = v.get("view_count_fmt", "")
        self.d_views.config(text=f"  {views}" if views else "  —")
        
        # Display thumbnail if available in cache
        tu = v.get("thumbnail", "")
        if tu and tu in self.thumb_cache:
            photo = self.thumb_cache[tu]
            self._thumb_ref = photo
            self.thumb_lbl.config(image=photo, text="",
                                   width=THUMB_W, height=THUMB_H)
        else:
            self.thumb_lbl.config(image="",
                                   text="Loading…" if tu else "No thumbnail",
                                   width=THUMB_W, height=THUMB_H)

    def _fetch_detail(self, url: str, idx: int):
        """Fetches upload date, views, and duration asynchronously in the background."""
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

            # Format upload date
            date_fmt = ""
            if len(upload_raw) == 8:
                try:
                    date_fmt = datetime.strptime(upload_raw, "%Y%m%d").strftime("%d %b %Y")
                except ValueError:
                    date_fmt = upload_raw

            # Format views counter
            views_fmt = ""
            try:
                views_fmt = f"{int(view_raw):,}".replace(",", ".") + " views"
            except (ValueError, TypeError):
                pass

            # Update results data lock-safely
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
        """Downloads and scales the thumbnail image in a secondary thread."""
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
            # Trigger a refresh on the main GUI thread
            self.root.after(0, self._refresh_detail, idx)
        except Exception:
            pass
        finally:
            self.root.after(0, lambda: self.lbl_spin.config(text=""))

    def _refresh_detail(self, idx: int):
        # Wrapper to safely update details pane if it's still the active index
        if self.current_idx == idx:
            with self._results_lock:
                if 0 <= idx < len(self.resultados):
                    self._populate_detail(self.resultados[idx])

    def _reset_detail(self):
        # Reset detail pane to initial state
        for lbl in (self.d_title, self.d_channel, self.d_dur, self.d_date, self.d_views):
            lbl.config(text="—")
        self.thumb_lbl.config(image="",
                               text="Select a\nvideo to see\nthe info",
                               width=THUMB_W, height=THUMB_H)
        self.lbl_spin.config(text="")
        self._thumb_ref = None

    # ═══════════════════ YOUTUBE / CLIPBOARD ════════════════════════════════
    def _sel_url(self) -> str:
        # Helper to get the selected URL from the treeview
        sel = self.tree.selection()
        if not sel:
            return ""
        idx = self.tree.index(sel[0])
        with self._results_lock:
            return self.resultados[idx].get("url", "") if idx < len(self.resultados) else ""

    def _open_yt(self):
        # Open URL in default system browser
        url = self._sel_url()
        if url:
            webbrowser.open(url)

    def _copy_url(self):
        # Copy URL to OS clipboard
        url = self._sel_url()
        if url:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self._status("URL copied to clipboard.", GREEN)

    # ═══════════════════ SEARCH ══════════════════════════════════════════════
    def _buscar(self):
        # Trigger youtube search functionality
        q = self.ent.get().strip()
        if not q or q == PLACEHOLDER:
            return
        # Cancel any previous ongoing search
        if self._search_proc and self._search_proc.poll() is None:
            self._search_proc.terminate()
        
        # Disable button and update UI
        self.btn_bus.config(state="disabled")
        self._status(f"Searching: {q}…", ACCENT)
        self.root.title(f"YouMuDow  v4.1  —  searching…")
        
        # Start background search worker
        threading.Thread(target=self._search_worker, args=(q,), daemon=True).start()

    def _search_worker(self, q: str):
        # If it's a URL, search that URL, otherwise run a typical YouTube search query
        target = q if q.startswith("http") else f"ytsearch15:{q}"
        fmt    = "%(title)s\t%(uploader)s\t%(webpage_url)s\t%(duration_string)s"
        cmd    = ["yt-dlp", "--print", fmt, "--flat-playlist", "--no-warnings", target]
        try:
            # Spawn subprocess
            self._search_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace")

            # Clear UI prior to appending results
            self.root.after(0, lambda: [self.tree.delete(i) for i in self.tree.get_children()])
            self.root.after(0, self._reset_detail)

            local_results: list = []
            batch: list         = []
            BATCH_SIZE = 5   # insert in batches to reduce after() overhead

            def _flush(b: list):
                # Helper function to append tree items on main GUI thread
                for r in b:
                    self.tree.insert("", "end",
                                     values=(r["title"], r["uploader"],
                                             r["duration_string"], "Ready"),
                                     tags=("ready",))

            # Parse yt-dlp flat-playlist output
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
                    batch.append(res)
                    if len(batch) >= BATCH_SIZE:
                        snapshot = batch[:]
                        batch.clear()
                        self.root.after(0, _flush, snapshot)

            # Insert any remaining residual results
            if batch:
                snapshot = batch[:]
                self.root.after(0, _flush, snapshot)

            self._search_proc.wait()
            # Update class properties
            with self._results_lock:
                self.resultados = local_results
            self._detail_cache.clear()

            # Finalize search UI status
            n = len(local_results)
            msg   = f"{n} results found." if n else "No results."
            color = GREEN if n else YELLOW
            self.root.after(0, lambda: self._status(msg, color))
            self.root.after(0, lambda: self.root.title("YouMuDow  v4.1"))

        except FileNotFoundError:
            self.root.after(0, lambda: self._status(
                "yt-dlp not found. Please ensure it is installed.", RED))
            self.root.after(0, lambda: self.root.title("YouMuDow  v4.1"))
        except Exception as e:
            self.root.after(0, lambda: self._status(f"Search error: {e}", RED))
            self.root.after(0, lambda: self._log(f"[SEARCH ERR] {e}"))
            self.root.after(0, lambda: self.root.title("YouMuDow  v4.1"))
        finally:
            # Re-enable the search button regardless of the result
            self._search_proc = None
            self.root.after(0, lambda: self.btn_bus.config(state="normal"))

    # ═══════════════════ ENQUEUE ══════════════════════════════════════════════
    def _encolar(self):
        # Enqueue selected list items for downloading
        sel = self.tree.selection()
        if not sel:
            self._status("Select one or more results first.", YELLOW)
            return
            
        # Validate target folder
        if not self.session_path or not os.path.isdir(self.session_path):
            self._pick_folder()
            if not self.session_path or not os.path.isdir(self.session_path):
                self._status("Please select a valid destination folder.", RED)
                return
                
        encolados = 0
        with self._results_lock:
            for item in sel:
                idx = self.tree.index(item)
                if idx >= len(self.resultados):
                    continue
                # Do not enqueue already queued or downloading items
                tags = self.tree.item(item, "tags")
                if tags and tags[0] in ("queued", "downloading"):
                    continue
                    
                v   = self.resultados[idx]
                dur = v.g
