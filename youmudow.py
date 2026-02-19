import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import queue
import os
import webbrowser

class SpartanDualMode:
    def __init__(self, root):
        self.root = root
        self.root.title("Spartan Downloader v4.0")
        self.root.geometry("900x500") # Altura inicial compacta
        
        self.cola_descargas = queue.Queue()
        self.esta_descargando = False
        self.resultados = []
        self.debug_visible = False # Estado inicial

        self.setup_ui()

    def setup_ui(self):
        # --- PANEL SUPERIOR: BÚSQUEDA ---
        f_bus = ttk.Frame(self.root, padding=10)
        f_bus.pack(fill="x")
        
        self.ent_bus = ttk.Entry(f_bus, font=("Monospace", 10))
        self.ent_bus.pack(side="left", fill="x", expand=True, padx=5)
        self.ent_bus.bind("<Return>", lambda e: self.buscar())
        
        self.btn_bus = ttk.Button(f_bus, text="SEARCH", command=self.buscar)
        self.btn_bus.pack(side="left")

        # --- PANEL CENTRAL: TABLA ---
        self.tree = ttk.Treeview(self.root, columns=("T", "C", "U"), show="headings", height=8)
        self.tree.heading("T", text="TITLE")
        self.tree.heading("C", text="CHANNEL")
        self.tree.heading("U", text="URL")
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        # --- PANEL DE CONTROL ---
        f_ctrl = ttk.Frame(self.root, padding=10)
        f_ctrl.pack(fill="x")
        
        self.fmt = tk.StringVar(value="mp3")
        ttk.Radiobutton(f_ctrl, text="MP3", variable=self.fmt, value="mp3").pack(side="left", padx=5)
        ttk.Radiobutton(f_ctrl, text="MP4", variable=self.fmt, value="mp4").pack(side="left", padx=5)
        
        ttk.Button(f_ctrl, text="📥 ADD TO QUEUE", command=self.encolar).pack(side="left", padx=10)
        
        # INTERRUPTOR DEBUG
        self.btn_debug = ttk.Button(f_ctrl, text="🛠️ SHOW DEBUG", command=self.toggle_debug)
        self.btn_debug.pack(side="right")

        # --- CONSOLA DE LOGS (OCULTA POR DEFECTO) ---
        self.f_debug = ttk.LabelFrame(self.root, text=" LIVE TERMINAL LOGS ")
        self.log = tk.Text(self.f_debug, height=12, bg="#000", fg="#0F0", font=("Monospace", 9))
        self.log.pack(fill="both", expand=True, padx=5, pady=5)
        
    def toggle_debug(self):
        """Alterna la visibilidad de la consola de logs."""
        if not self.debug_visible:
            self.f_debug.pack(fill="both", expand=True, padx=10, pady=5)
            self.root.geometry("900x800") # Agrandar ventana
            self.btn_debug.config(text="🛠️ HIDE DEBUG")
            self.debug_visible = True
        else:
            self.f_debug.pack_forget()
            self.root.geometry("900x500") # Volver a tamaño normal
            self.btn_debug.config(text="🛠️ SHOW DEBUG")
            self.debug_visible = False

    def write_log(self, txt):
        self.log.insert(tk.END, f"{txt}\n")
        self.log.see(tk.END)

    def buscar(self):
        query = self.ent_bus.get().strip()
        if not query: return
        self.btn_bus.config(state="disabled")
        self.write_log(f"[INFO] Searching for: {query}")
        threading.Thread(target=self._search_process, args=(query,), daemon=True).start()

    def _search_process(self, q):
        target = q if q.startswith("http") else f"ytsearch10:{q}"
        cmd = ["yt-dlp", "--print", "%(title)s || %(uploader)s || %(webpage_url)s", "--flat-playlist", target]
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.resultados = []
            self.root.after(0, lambda: [self.tree.delete(i) for i in self.tree.get_children()])

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None: break
                if line:
                    line = line.strip()
                    if " || " in line:
                        p = line.split(" || ")
                        res = {"title": p[0], "uploader": p[1], "url": p[2]}
                        self.resultados.append(res)
                        self.root.after(0, lambda r=res: self.tree.insert("", "end", values=(r['title'], r['uploader'], r['url'])))
            
            err = process.stderr.read()
            if err: self.root.after(0, lambda: self.write_log(f"[ERROR] {err}"))

        except Exception as e:
            self.root.after(0, lambda: self.write_log(f"[EXCEPTION] {e}"))
        finally:
            self.root.after(0, lambda: self.btn_bus.config(state="normal"))

    def encolar(self):
        sel = self.tree.selection()
        if not sel: return
        path = filedialog.askdirectory()
        if not path: return

        idx = self.tree.index(sel[0])
        video = self.resultados[idx]
        tarea = {**video, 'path': path, 'fmt': self.fmt.get()}
        self.cola_descargas.put(tarea)
        self.write_log(f"[QUEUE] Added: {tarea['title']}")
        
        if not self.esta_descargando:
            self.esta_descargando = True
            threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while not self.cola_descargas.empty():
            t = self.cola_descargas.get()
            cmd = ["yt-dlp", "--newline", "-o", f"{t['path']}/%(title)s.%(ext)s"]
            if t['fmt'] == "mp3":
                cmd += ["-x", "--audio-format", "mp3"]
            cmd.append(t['url'])

            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    # Solo escribimos al log, si el usuario quiere verlo, activa el Modo Debug
                    self.root.after(0, lambda l=line: self.write_log(f"[DL] {l.strip()}"))
                proc.wait()
            except Exception as e:
                self.root.after(0, lambda: self.write_log(f"[DL ERROR] {e}"))
            self.cola_descargas.task_done()
        self.esta_descargando = False

if __name__ == "__main__":
    root = tk.Tk()
    app = SpartanDualMode(root)
    root.mainloop()
