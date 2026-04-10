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
from core.config import MAX_START_BYTES, MAX_VIEW_LINES, TRIM_BATCH, PAUSED_BUFFER_MAX, TAIL_POLL_INTERVAL_SEC, SERVICE_COMPONENTS
from core.utils import service_from_path, open_text_auto, seek_tail
from core.os_services import restart_service_components, check_service_status
from gui.components.search import IncrementalSearch
from gui.components.spinner import LoadingSpinner
from gui.components.minimap import LogMinimap
from gui.utils.icon_manager import icons

class LogTab:
    """Aba de visualização de LOG Pro."""
    
    def __init__(self, app, filepath, parent_frame):
        self.app = app
        self.filepath = filepath
        self.frame = parent_frame
        self.service_name = service_from_path(filepath)
        self.stop_event = threading.Event()
        self.q = queue.Queue()
        self.follow = True
        self.unread = 0
        self.appended_since_trim = 0
        self.paused_buffer = []
        self.incremental_search = None
        
        # Design tokens - Paleta Pastel / Soft Tech
        self.colors = {
            "ERROR": "#ff6b6b",    # Vermelho Pastel
            "WARN": "#ffd93d",     # Amarelo Pastel
            "INFO": "#6bc167",     # Verde Soft
            "DEBUG": "#868e96",    # Cinza Médio
            "bg_header": ("#dbdbdb", "#212121"),
            "highlight_color": "#4dabf7" # Azul Profissional suave
        }
        self.custom_highlight_term = ""
        self.custom_highlight_color = self.colors["highlight_color"]
        
        # Nome do serviço Windows correspondente (para verificação de status)
        components = SERVICE_COMPONENTS.get(self.service_name, {})
        win_services = components.get("services", [])
        self._win_service = win_services[0] if win_services else None
        self._svc_status  = None   # None = desconhecido | True = rodando | False = parado
        
        self._build_ui()
        self._setup_tags()
        self._start_tail()
        self._schedule_drain()
        # Inicia monitoramento de status (apenas se há serviço mapeado)
        if self._win_service:
            self._schedule_status_check()

    def _build_ui(self):
        # Header modernizado
        self.header = ctk.CTkFrame(self.frame, height=50, corner_radius=10, fg_color=self.colors["bg_header"])
        self.header.pack(side="top", fill="x", padx=10, pady=(5, 10))
        self.header.pack_propagate(False)
        
        # Info do Serviço + Indicador de Status
        info_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        info_frame.pack(side="left", padx=15)

        # Canvas para o círculo pulsante de status
        self.status_canvas = tk.Canvas(
            info_frame, width=14, height=14,
            bg=self.header.cget("fg_color")[1] if isinstance(self.header.cget("fg_color"), tuple) else "#212121",
            highlightthickness=0
        )
        self.status_canvas.pack(side="left", padx=(0, 6))
        self._dot = self.status_canvas.create_oval(2, 2, 12, 12, fill="#888888", outline="")
        self._pulse_step = 0

        title_lbl = ctk.CTkLabel(info_frame, text=f"⚡ {self.service_name}",
                                 font=ctk.CTkFont(size=14, weight="bold"), text_color="#3498db")
        title_lbl.pack(side="left")

        # Tooltip do status (aparece ao lado do círculo)
        self._status_tooltip_text = "Verificando..."
        self.status_canvas.bind("<Enter>", self._show_status_tooltip)
        self.status_canvas.bind("<Leave>", self._hide_status_tooltip)
        self._tooltip_win = None
        
        # Botões de Ação (Agrupados à direita)
        action_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        action_frame.pack(side="right", padx=10)
        
        self.btn_restart = ctk.CTkButton(action_frame, text=" Reiniciar", width=110, height=32,
                                         image=icons.get_icon("restart", size=(16, 16)),
                                         command=self._restart_service, fg_color="#d9534f", hover_color="#c9302c")
        self.btn_restart.pack(side="right", padx=5)
        
        self.btn_follow = ctk.CTkButton(action_frame, text=" Pausar", width=110, height=32,
                                         image=icons.get_icon("pause", size=(16, 16)),
                                         command=self.toggle_follow, fg_color="#555", hover_color="#666")
        self.btn_follow.pack(side="right", padx=5)

        # Status Label sutil
        self.status_label = ctk.CTkLabel(self.header, text="Conectado", text_color="gray", font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left", padx=10)

        # Barra de Marcadores Customizados (Highlighters)
        self.highlighter_bar = ctk.CTkFrame(self.frame, height=40, corner_radius=10)
        self.highlighter_bar.pack(side="top", fill="x", padx=10, pady=(0, 5))
        
        ctk.CTkLabel(self.highlighter_bar, text="🔖 Marcador:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(15, 5))
        
        self.entry_highlight = ctk.CTkEntry(self.highlighter_bar, placeholder_text="Termo para destacar...", 
                                           width=250, height=28, font=ctk.CTkFont(size=12))
        self.entry_highlight.pack(side="left", padx=5)
        self.entry_highlight.bind("<KeyRelease>", lambda e: self._update_custom_highlight())

        # Marcador simples
        self.color_btns = []

        # Container Principal da Visualização (Texto + Minimapa)
        self.view_container = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.view_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 1. Área de Texto (Criar primeiro para o minimapa usar)
        font_size = self.app.settings.get("font_size", 13)
        self.text = ctk.CTkTextbox(self.view_container, wrap="none", font=ctk.CTkFont(family="Consolas", size=font_size),
                                   activate_scrollbars=True, state="disabled", corner_radius=15, 
                                   border_width=1, border_color=("#dbdbdb", "#333333"))
        self.text.pack(side="left", fill="both", expand=True)
        
        # 2. Minimapa (Criar depois do texto)
        self.minimap = LogMinimap(self.view_container, self.text)
        self.minimap.pack(side="right", fill="y", padx=(5, 0))
        
        # Bindings
        self.text.bind("<MouseWheel>", lambda e: self._on_scroll())
        self.text.bind("<Control-f>", lambda e: self._show_search())
        self.text.bind("<F2>", lambda e: self.toggle_follow())
        
        self._build_context_menu()

    def _setup_tags(self):
        """Configura tags para syntax highlighting."""
        for level, color in self.colors.items():
            # Pula configurações que não são cores de nível de log
            if level in ["ERROR", "WARN", "INFO", "DEBUG"]:
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
            
            # Aplica realce customizado
            if self.custom_highlight_term:
                pos = start_pos
                while True:
                    pos = self.text.search(self.custom_highlight_term, pos, stopindex=end_pos, nocase=True)
                    if not pos or pos == "": break
                    line_end = f"{pos}+{len(self.custom_highlight_term)}c"
                    self.text.tag_add("CUSTOM_HL", pos, line_end)
                    pos = line_end
        except Exception as e:
            logger.debug(f"Erro no realce de sintaxe: {e}")

    def _set_highlight_color(self, color):
        self.custom_highlight_color = color
        self.text.tag_config("CUSTOM_HL", background=color, foreground="white")
        # Força re-aplicação em todo o texto visível
        self._update_custom_highlight()

    def _update_custom_highlight(self):
        self.custom_highlight_term = self.entry_highlight.get()
        self.text.tag_remove("CUSTOM_HL", "1.0", "end")
        self.text.tag_config("CUSTOM_HL", background=self.custom_highlight_color, foreground="white")
        if self.custom_highlight_term:
            self._apply_highlighting("1.0", "end")

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
        icon = icons.get_icon("play" if not self.follow else "pause", size=(16, 16))
        self.btn_follow.configure(text=" Seguir" if not self.follow else " Pausar", 
                                  image=icon,
                                  fg_color="#3498db" if not self.follow else "#555")
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

    # --- Métodos do Indicador de Status ---

    def _schedule_status_check(self):
        """Agenda uma verificação de status do serviço Windows em background."""
        if self.stop_event.is_set(): return
        threading.Thread(target=self._check_status_worker, daemon=True).start()
        # Re-agenda a cada 10 segundos
        self.frame.after(10000, self._schedule_status_check)

    def _check_status_worker(self):
        """Verifica o status real do serviço Windows sem travar a UI."""
        if not self._win_service: return
        exists, running, msg = check_service_status(self._win_service)
        self._svc_status = running if exists else None
        self._status_tooltip_text = msg
        self.frame.after(0, self._update_status_ui)

    def _update_status_ui(self):
        """Atualiza a cor do círculo baseado no status."""
        if self._svc_status is True:
            color = "#2ecc71" # Verde rodando
            if not hasattr(self, "_pulsing"):
                self._pulsing = True
                self._pulse()
        elif self._svc_status is False:
            color = "#e74c3c" # Vermelho parado
            self._pulsing = False
        else:
            color = "#888888" # Cinza desconhecido/não mapeado
            self._pulsing = False
        
        self.status_canvas.itemconfig(self._dot, fill=color)

    def _pulse(self):
        """Efeito de pulsação suave no círculo verde."""
        if not hasattr(self, "_pulsing") or not self._pulsing or self._svc_status is not True:
            self.status_canvas.itemconfig(self._dot, outline="")
            return

        # Varia o outline para simular pulso
        self._pulse_step = (self._pulse_step + 1) % 10
        alpha = abs(5 - self._pulse_step) / 5.0 # 0.0 a 1.0
        
        # Cor de brilho verde
        glow_color = "#2ecc71"
        self.status_canvas.itemconfig(self._dot, outline=glow_color, width=2 if alpha > 0.5 else 0)
        
        self.frame.after(200, self._pulse)

    def _show_status_tooltip(self, event):
        """Exibe um mini-tooltip com o status detalhado."""
        self._hide_status_tooltip()
        x = event.x_root + 10
        y = event.y_root + 10
        
        self._tooltip_win = tk.Toplevel()
        self._tooltip_win.wm_overrideredirect(True)
        self._tooltip_win.geometry(f"+{x}+{y}")
        
        lbl = tk.Label(self._tooltip_win, text=self._status_tooltip_text, 
                       bg="#333", fg="white", padx=5, pady=2, font=("Segoe UI", 9))
        lbl.pack()

    def _hide_status_tooltip(self, event=None):
        if self._tooltip_win:
            self._tooltip_win.destroy()
            self._tooltip_win = None
