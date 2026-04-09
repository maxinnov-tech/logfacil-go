"""
Arquivo: gui/tabs/log_tab.py
Descrição: Guia (Tab) Pro para visualização de logs.
Inclui destaque de sintaxe inteligente, motor de renderização otimizado,
controles de serviço integrados e sistema de busca incremental.
"""
import os
import time
import queue
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from core.logger import logger
from core.config import MAX_START_BYTES, MAX_VIEW_LINES, TRIM_BATCH, PAUSED_BUFFER_MAX, TAIL_POLL_INTERVAL_SEC
from core.utils import service_from_path, open_text_auto, seek_tail
from core.os_services import restart_service_components
from gui.components.search import IncrementalSearch
from gui.components.spinner import LoadingSpinner

class LogTab:
    """Aba de visualização de LOG Pro."""
    
    def __init__(self, app, filepath):
        self.app = app
        self.filepath = filepath
        self.service_name = service_from_path(filepath)
        self.stop_event = threading.Event()
        self.q = queue.Queue()
        self.follow = True
        self.unread = 0
        self.appended_since_trim = 0
        self.paused_buffer = []
        self.incremental_search = None
        
        # Design tokens
        self.colors = {
            "ERROR": "#ff4d4d",
            "WARN": "#ffa500",
            "INFO": "#4CAF50",
            "DEBUG": "#888888",
            "bg_header": "#2b2b2b"
        }
        
        self.frame = ctk.CTkFrame(app.log_container, fg_color="transparent")
        self._build_ui()
        self._setup_tags()
        self._start_tail()
        self._schedule_drain()

    def _build_ui(self):
        # Header modernizado
        self.header = ctk.CTkFrame(self.frame, height=50, corner_radius=10, fg_color=self.colors["bg_header"])
        self.header.pack(side="top", fill="x", padx=10, pady=(5, 10))
        self.header.pack_propagate(False)
        
        # Info do Serviço
        title_lbl = ctk.CTkLabel(self.header, text=f"⚡ {self.service_name}", 
                                font=ctk.CTkFont(size=14, weight="bold"), text_color="#4CAF50")
        title_lbl.pack(side="left", padx=15)
        
        # Botões de Ação (Agrupados à direita)
        action_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        action_frame.pack(side="right", padx=10)
        
        self.btn_restart = ctk.CTkButton(action_frame, text="🔄 Reiniciar", width=100, height=28,
                                         command=self._restart_service, fg_color="#d9534f", hover_color="#c9302c")
        self.btn_restart.pack(side="right", padx=5)
        
        self.btn_follow = ctk.CTkButton(action_frame, text="⏸ Pausar", width=100, height=28,
                                         command=self.toggle_follow, fg_color="#555", hover_color="#666")
        self.btn_follow.pack(side="right", padx=5)

        # Status Label sutil
        self.status_label = ctk.CTkLabel(self.header, text="Conectado", text_color="gray", font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left", padx=10)

        # Área de Texto
        font_size = self.app.settings.get("font_size", 13)
        self.text = ctk.CTkTextbox(self.frame, wrap="none", font=ctk.CTkFont(family="Consolas", size=font_size),
                                   activate_scrollbars=True, state="disabled", corner_radius=12)
        self.text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Bindings
        self.text.bind("<MouseWheel>", lambda e: self._on_scroll())
        self.text.bind("<Control-f>", lambda e: self._show_search())
        self.text.bind("<F2>", lambda e: self.toggle_follow())
        
        self._build_context_menu()

    def _setup_tags(self):
        """Configura tags para syntax highlighting."""
        for level, color in self.colors.items():
            if level != "bg_header":
                self.text.tag_config(level, foreground=color)

    def _apply_highlighting(self, start_pos, end_pos):
        """Aplica cores dinamicamente nas linhas de log."""
        try:
            for level in ["ERROR", "WARN", "INFO", "DEBUG"]:
                pos = start_pos
                while True:
                    pos = self.text.search(level, pos, stopindex=end_pos, nocase=False)
                    if not pos: break
                    line_start = f"{pos.split('.')[0]}.0"
                    line_end = f"{pos.split('.')[0]}.end"
                    self.text.tag_add(level, line_start, line_end)
                    pos = line_end
        except: pass

    def _restart_service(self):
        if messagebox.askyesno("Confirmar", f"Reiniciar serviço '{self.service_name}'?"):
            spinner = LoadingSpinner(self.frame, f"Reiniciando {self.service_name}...")
            spinner.show()
            def task():
                success, _ = restart_service_components(self.service_name)
                self.frame.after(0, lambda: self.status_label.configure(text="✅ Reiniciado" if success else "⚠ Erro", text_color="green" if success else "orange"))
                self.frame.after(0, spinner.hide)
            threading.Thread(target=task, daemon=True).start()

    def toggle_follow(self):
        self.follow = not self.follow
        self.btn_follow.configure(text="▶ Seguir" if not self.follow else "⏸ Pausar", fg_color="#4CAF50" if not self.follow else "#555")
        if self.follow:
            self._flush_buffer()
            self.text.see("end")

    def _show_search(self):
        if not self.incremental_search: self.incremental_search = IncrementalSearch(self.text)
        self.incremental_search.show_search_bar()
        return "break"

    def _start_tail(self):
        threading.Thread(target=self._tail_loop, daemon=True).start()

    def _tail_loop(self):
        try:
            f, is_text = open_text_auto(self.filepath)
            seek_tail(f, MAX_START_BYTES)
        except Exception as e:
            self.q.put(f"[ERRO] Falha ao abrir: {e}\n")
            return
        
        decoder = (lambda b: b.decode("utf-8", errors="replace")) if not is_text else None
        while not self.stop_event.is_set():
            chunk = f.read()
            if chunk:
                self.q.put(chunk if is_text else decoder(chunk))
            else:
                time.sleep(TAIL_POLL_INTERVAL_SEC)

    def _schedule_drain(self):
        if not self.stop_event.is_set():
            self._drain()
            self.text.after(80, self._schedule_drain)

    def _drain(self):
        agg = []
        while not self.q.empty(): agg.append(self.q.get_nowait())
        if not agg: return
        data = "".join(agg)
        if self.follow: self._append(data)
        else: self.paused_buffer.append(data)

    def _append(self, data):
        self.text.configure(state="normal")
        start_idx = self.text.index("end-1c")
        self.text.insert("end", data)
        end_idx = self.text.index("end-1c")
        
        self._apply_highlighting(start_idx, end_idx)
        
        self.appended_since_trim += data.count("\n")
        if self.appended_since_trim >= TRIM_BATCH:
            self._trim()
            self.appended_since_trim = 0
            
        if self.follow: self.text.see("end")
        self.text.configure(state="disabled")

    def _trim(self):
        total = int(self.text.index("end-1c").split(".")[0])
        if total > MAX_VIEW_LINES:
            self.text.delete("1.0", f"{total - MAX_VIEW_LINES + 1}.0")

    def _flush_buffer(self):
        if self.paused_buffer:
            self._append("".join(self.paused_buffer))
            self.paused_buffer.clear()

    def update_settings(self, settings):
        self.text.configure(font=ctk.CTkFont(family="Consolas", size=settings.get("font_size", 13)))

    def _on_scroll(self):
        # Auto-pause ao subir o scroll
        visible = self.text.yview()
        if visible[1] < 0.95 and self.follow:
            self.toggle_follow()

    def _build_context_menu(self):
        m = tk.Menu(self.text, tearoff=0, bg="#2b2b2b", fg="white", activebackground="#4CAF50")
        m.add_command(label="📋 Copiar", command=lambda: self.text.event_generate("<<Copy>>"))
        m.add_command(label="🔍 Buscar", command=self._show_search)
        m.add_command(label="🗑 Limpar Tela", command=lambda: [self.text.configure(state="normal"), self.text.delete("1.0", "end"), self.text.configure(state="disabled")])
        self.text.bind("<Button-3>", lambda e: m.tk_popup(e.x_root, e.y_root))
