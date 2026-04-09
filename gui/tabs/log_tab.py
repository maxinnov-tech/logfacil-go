"""
Arquivo: gui/tabs/log_tab.py
Descrição: Guia (Tab) individual responsável pela renderização visual de um arquivo log.
Este é um dos arquivos mais ricos da aplicação, pois manipula a área de texto onde 
os fluxos de dados de saída (tails) são recebidos e desenhados. Sua estrutura engloba 
uma fila em thread (queue) consumindo os outputs dos monitores do backend. Desempenha forte lógica
focada em performance de Tcl/Tk controlando quantas linhas inserir na UI de uma vez, 
gerenciando um limite explícito de logs mostrados em buffer (para evitar estourar a memória RAM 
com o uso contínuo) e a funcionalidade interativa de travar em uma linha congelando (Pause / Folow).
Também exibe controles para ação focada em um serviço único, como de "Restart do serviço".
"""
import os
import time
import queue
import threading
from dataclasses import dataclass, field
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from core.logger import logger
from core.config import MAX_START_BYTES, MAX_VIEW_LINES, TRIM_BATCH, PAUSED_BUFFER_MAX, TAIL_POLL_INTERVAL_SEC
from core.utils import service_from_path, open_text_auto, seek_tail
from core.os_services import restart_service_components
from gui.components.search import IncrementalSearch
from gui.components.spinner import LoadingSpinner

@dataclass
class LogTab:
    app: "App"
    filepath: str
    frame: ctk.CTkFrame = field(init=False)
    text: ctk.CTkTextbox = field(init=False)
    btn_frame: ctk.CTkFrame = field(init=False)
    btn_restart: ctk.CTkButton = field(init=False)
    status_label: ctk.CTkLabel = field(init=False)
    service_label: ctk.CTkLabel = field(init=False)
    stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    q: "queue.Queue[str]" = field(default_factory=queue.Queue, init=False)
    follow: bool = field(default=True, init=False)
    unread: int = field(default=0, init=False)
    appended_since_trim: int = field(default=0, init=False)
    paused_buffer: list = field(default_factory=list, init=False)
    service_name: str = field(init=False)
    incremental_search: IncrementalSearch = field(default=None, init=False)

    def __post_init__(self):
        self.service_name = service_from_path(self.filepath)
        self.frame = ctk.CTkFrame(self.app.notebook)
        self._build_ui()
        self._start_tail()
        self._schedule_drain()

    def _build_ui(self):
        self.btn_frame = ctk.CTkFrame(self.frame, height=60, fg_color="transparent")
        self.btn_frame.pack(side="top", fill="x", padx=5, pady=5)
        self.btn_frame.pack_propagate(False)
        
        left_frame = ctk.CTkFrame(self.btn_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="y")
        
        self.service_label = ctk.CTkLabel(left_frame, text=f"⚡ {self.service_name}",
                                          font=ctk.CTkFont(size=14, weight="bold"), text_color="#4CAF50")
        self.service_label.pack(side="top", anchor="w")
        
        separator = ctk.CTkFrame(self.btn_frame, width=2, height=40, fg_color="#555555")
        separator.pack(side="left", padx=15)
        separator.pack_propagate(False)
        
        self.btn_restart = ctk.CTkButton(self.btn_frame, text="🔄 Reiniciar", command=self._restart_service,
                                         fg_color="#d9534f", hover_color="#c9302c", height=35, width=120)
        self.btn_restart.pack(side="left", padx=5)
        
        self.status_label = ctk.CTkLabel(self.btn_frame, text="", text_color="gray")
        self.status_label.pack(side="left", padx=10)
        
        text_frame = ctk.CTkFrame(self.frame)
        text_frame.pack(side="top", fill="both", expand=True, padx=5, pady=(0, 5))
        
        
        font_size = self.app.settings.get("font_size", 13)
        self.text = ctk.CTkTextbox(text_frame, wrap="none", font=ctk.CTkFont(family="Consolas", size=font_size),
                                   activate_scrollbars=True, state="disabled")
        self.text.pack(side="left", fill="both", expand=True)
        
        self.text.bind("<MouseWheel>", self._on_scroll)
        self.text.bind("<Control-f>", self._show_search)
        self.text.bind("<F2>", lambda e: self.toggle_follow())
        
        self._build_context_menu()
    
    def _show_search(self, event=None):
        if not self.incremental_search:
            self.incremental_search = IncrementalSearch(self.text)
        self.incremental_search.show_search_bar()
        return "break"
    
    def _on_scroll(self, event=None):
        self._update_follow_from_view()
    
    def _restart_service(self):
        def do_restart():
            spinner = LoadingSpinner(self.frame, f"Reiniciando {self.service_name}...")
            spinner.show()
            self.btn_restart.configure(state="disabled", text="⏳ Reiniciando...")
            
            def restart_thread():
                try:
                    success, messages = restart_service_components(self.service_name)
                    self.frame.after(0, lambda: self._restart_callback(success, messages))
                finally:
                    self.frame.after(0, lambda: spinner.hide())
            
            threading.Thread(target=restart_thread, daemon=True).start()
        
        if messagebox.askyesno("Confirmar", f"Reiniciar serviço '{self.service_name}'?"):
            do_restart()
    
    def _restart_callback(self, success: bool, messages: list):
        self.btn_restart.configure(state="normal", text="🔄 Reiniciar")
        if success:
            self.status_label.configure(text="✅ Serviço reiniciado!", text_color="green")
        else:
            self.status_label.configure(text="⚠ Erro no restart", text_color="orange")
        self.frame.after(5000, lambda: self.status_label.configure(text=""))
    
    def _build_context_menu(self):
        menu = tk.Menu(self.text, tearoff=0, bg="#2b2b2b", fg="white",
                       activebackground="#404040", activeforeground="white")
        menu.add_command(label="📋 Copiar", command=self._copy_selected)
        menu.add_command(label="✨ Selecionar tudo", command=self._select_all)
        menu.add_separator()
        menu.add_command(label="🔍 Buscar...    Ctrl+F", command=self._show_search)
        menu.add_separator()
        menu.add_command(label="⏸️ Pausar/Seguir    F2", command=self.toggle_follow)
        menu.add_command(label="⬇️ Ir para o fim", command=self.scroll_to_end)
        menu.add_separator()
        menu.add_command(label="🔄 Reiniciar serviço", command=self._restart_service)
        self.text.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
    
    def _copy_selected(self):
        try:
            selected = self.text.get("sel.first", "sel.last")
            self.text.clipboard_clear()
            self.text.clipboard_append(selected)
        except Exception:
            pass
    
    def _select_all(self):
        self.text.configure(state="normal")
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.configure(state="disabled")
    
    def _update_follow_from_view(self):
        try:
            visible_range = self.text.yview()
            at_bottom = float(visible_range[1]) >= 0.999
            self.follow = at_bottom
            if at_bottom:
                self._flush_buffer()
        except Exception:
            pass
    
    def toggle_follow(self):
        self.follow = not self.follow
        if self.follow:
            self.scroll_to_end()
            self._flush_buffer()
    
    def scroll_to_end(self):
        self.text.see("end")
        self._update_follow_from_view()
    
    def _start_tail(self):
        threading.Thread(target=self._tail_loop, daemon=True).start()
    
    def _open_file(self):
        f, is_text = open_text_auto(self.filepath)
        seek_tail(f, MAX_START_BYTES)
        return f, is_text
    
    def _tail_loop(self):
        try:
            f, is_text = self._open_file()
        except Exception as e:
            self.q.put(f"[ERRO] Falha ao abrir: {e}\n")
            return
        
        decoder = (lambda b: b.decode("utf-8", errors="replace")) if not is_text else None
        
        while not self.stop_event.is_set():
            try:
                chunk = f.read()
                if chunk:
                    data = chunk if is_text else decoder(chunk)
                    self.q.put(data)
                else:
                    time.sleep(TAIL_POLL_INTERVAL_SEC)
                    try:
                        size = os.path.getsize(self.filepath)
                        pos = f.tell()
                        if size < pos:
                            f.close()
                            f, is_text = self._open_file()
                            decoder = (lambda b: b.decode("utf-8", errors="replace")) if not is_text else None
                    except Exception:
                        pass
            except Exception as e:
                self.q.put(f"\n[ERRO de leitura] {e}\n")
                time.sleep(TAIL_POLL_INTERVAL_SEC)
        
        try:
            f.close()
        except Exception:
            pass
    
    def _schedule_drain(self):
        if self.stop_event.is_set():
            return
        self._drain()
        self.text.after(90, self._schedule_drain)
    
    def _drain(self):
        budget = 400
        agg = []
        total_newlines = 0
        
        while budget:
            try:
                item = self.q.get_nowait()
            except queue.Empty:
                break
            agg.append(item)
            total_newlines += item.count("\n") or 1
            budget -= 1
        
        if not agg:
            return
        
        data = "".join(agg)
        if self.follow:
            self._append(data)
        else:
            self.paused_buffer.append(data)
            if len(self.paused_buffer) > PAUSED_BUFFER_MAX:
                self.paused_buffer = self.paused_buffer[-PAUSED_BUFFER_MAX:]
            self.unread += total_newlines
    
    def _append(self, data: str):
        if not data:
            return
        
        self.text.configure(state="normal")
        self.text.insert("end", data)
        self.appended_since_trim += data.count("\n")
        if self.appended_since_trim >= TRIM_BATCH:
            self._trim()
            self.appended_since_trim = 0
        if self.follow:
            self.text.see("end")
        self.text.configure(state="disabled")
    
    def _trim(self):
        total_lines = int(self.text.index("end-1c").split(".")[0])
        if total_lines > MAX_VIEW_LINES:
            excess = total_lines - MAX_VIEW_LINES
            self.text.delete("1.0", f"{excess+1}.0")
    
    def _flush_buffer(self):
        if not self.paused_buffer:
            return
        combo = "".join(self.paused_buffer)
        self.paused_buffer.clear()
        self.unread = 0
        if combo:
            self._append(combo)

    def update_settings(self, settings):
        """Atualiza visualmente a aba com novas configurações."""
        try:
            new_font_size = settings.get("font_size", 13)
            self.text.configure(font=ctk.CTkFont(family="Consolas", size=new_font_size))
        except Exception as e:
            logger.error(f"Erro ao atualizar fonte da aba {self.service_name}: {e}")
