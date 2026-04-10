"""
Arquivo: gui/app.py
Descrição: Classe Principal (Shell) do LogFácil Pro v2.
Orquestra o layout moderno com barra lateral, navegação entre seções
e integração via Barramento de Eventos. Gerencia o ciclo de vida global
da aplicação, incluindo monitoramento de pastas e atualizações.
"""
import os
import time
import threading
import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from core.logger import logger
from core.config import VERSION, DEFAULT_ROOT, CURRENT_VERSION, GITHUB_REPO, SCAN_INTERVAL_SEC
from core.os_services import restart_service_components
from core.utils import service_from_path, find_latest_by_service
from core.event_bus import event_bus
from core.settings_manager import SettingsManager

from gui.managers.update_manager import AutoUpdateManager
from gui.components.navigation import Sidebar
from gui.tabs.dashboard_tab import DashboardTab
from gui.tabs.log_tab import LogTab
from gui.tabs.pdv_tab import PDVMonitorTab
from gui.tabs.settings_tab import SettingsTab
from gui.managers.global_search import GlobalSearch
from gui.components.status_bar import StatusBar

class FolderWatcher(threading.Thread):
    def __init__(self, app: "App", root_dir: str):
        super().__init__(daemon=True)
        self.app = app
        self.root_dir = root_dir
        self.stop_event = threading.Event()
        self.latest_by_service = {}
    
    def run(self):
        self._scan_and_open(initial=True)
        while not self.stop_event.is_set():
            self._scan_and_open(initial=False)
            for _ in range(int(SCAN_INTERVAL_SEC / 0.1)):
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)
    
    def _scan_and_open(self, initial=False):
        try:
            latest_map = find_latest_by_service(self.root_dir)
            
            # Ordenação Alfabética (conforme solicitado pelo usuário)
            ordered_items = sorted(latest_map.items())
            
            for svc, path in ordered_items:
                prev = self.latest_by_service.get(svc)
                if prev is None:
                    self.latest_by_service[svc] = path
                    self.app.enqueue_open(path)
                elif prev != path:
                    self.latest_by_service[svc] = path
                    self.app.enqueue_switch_service_log(svc, path)
        except Exception as e:
            logger.error(f"Erro no scan da pasta do watcher: {e}")

class App:
    def __init__(self):
        logger.info("="*50)
        logger.info(f"Iniciando LogFácil Pro v{VERSION}")
        logger.info("="*50)
        
        self.settings = SettingsManager()
        self.open_tabs = {}
        self.tab_by_service = {}
        self.views = {}
        
        self._setup_window()
        self._setup_layout()
        self._setup_queues()
        self._setup_close_handler()
        
        # Inicia componentes globais
        self.update_manager = AutoUpdateManager(self)
        self.root.after(3000, self.update_manager.check_updates_silent)
        
        # Inscrisções no Event Bus
        event_bus.subscribe("navigate", self._on_navigation_request)
        
        # Carrega pasta inicial
        self._start_watcher()
        
        logger.info("Sistema v2.0 inicializado")

    def _setup_window(self):
        ctk.set_appearance_mode(self.settings.get("appearance_mode", "dark"))
        ctk.set_default_color_theme(self.settings.get("ui_theme", "blue"))
        
        self.root = ctk.CTk()
        self.root.title(f"LogFácil Pro v{VERSION}")
        self.root.geometry("1400x850")
        self.root.minsize(1000, 700)

    def _setup_layout(self):
        # 1. Primeiro definimos o Main Container (mas não empacotamos ainda para respeitar a ordem)
        self.main_container = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        
        # 2. Barra de Status (Garante a base total)
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side="bottom", fill="x")
        
        # 3. Initialize Views
        self.views["dashboard"] = DashboardTab(self)
        self.views["pdvs"] = PDVMonitorTab(self)
        self.views["settings"] = SettingsTab(self)
        
        # 4. Log Container
        self.log_container = ctk.CTkTabview(self.main_container)
        self.views["logs"] = self.log_container
        
        # Top Header (Contextual)
        self.header = ctk.CTkFrame(self.main_container, height=60, corner_radius=0)
        self.header.pack(side="top", fill="x")
        self.header.pack_propagate(False)

        # 1. Botão de Toggle (Menu Hambúrguer)
        self.menu_btn = ctk.CTkButton(self.header, text="☰", width=40, height=40,
                                      fg_color="transparent", hover_color=("#dbdbdb", "#333333"),
                                      text_color=("#3498db"), font=ctk.CTkFont(size=22),
                                      command=self._toggle_sidebar)
        self.menu_btn.pack(side="left", padx=10)
        
        # 2. Título da Aba
        self.header_title = ctk.CTkLabel(self.header, text="Dashboard", font=ctk.CTkFont(size=18, weight="bold"))
        self.header_title.pack(side="left", padx=10)

        # Agora sim inicializamos o Sidebar (depois de ter views e cabeçalho prontos)
        self.sidebar = Sidebar(self.root, on_change_callback=self._on_nav_change)
        self.sidebar.pack(side="left", fill="y")
        
        # Agore empacotamos o Main Container por último para preencher o resto
        self.main_container.pack(side="left", fill="both", expand=True)
        
        # Binds Globais
        self.root.bind("<Control-Shift-F>", lambda e: self._open_global_search())
        self.root.bind("<Control-Shift-f>", lambda e: self._open_global_search())

    def _open_global_search(self):
        GlobalSearch(self)

    def _toggle_sidebar(self):
        if self.sidebar.winfo_ismapped():
            self.sidebar.pack_forget()
        else:
            self.sidebar.pack(side="left", fill="y", before=self.main_container)

    def _on_nav_change(self, view_id):
        # Esconde todas as views
        for v in self.views.values():
            if hasattr(v, 'frame'):
                v.frame.pack_forget()
            else:
                v.pack_forget()
        
        # Mostra a selecionada com padding para ficar elegante
        target = self.views.get(view_id)
        if target:
            if hasattr(target, 'frame'):
                target.frame.pack(fill="both", expand=True, padx=10, pady=10)
            else:
                target.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Atualiza título do header
            titles = {"dashboard": "Dashboard", "logs": "Monitoramento de Logs", "pdvs": "Status de PDVs", "settings": "Configurações"}
            self.header_title.configure(text=titles.get(view_id, "LogFácil"))

    def _on_navigation_request(self, view_id):
        self.sidebar.select(view_id)

    def _setup_queues(self):
        self.open_queue = queue.Queue()
        self.switch_queue = queue.Queue()
        self.root.after(120, self._consume_queues)

    def _setup_close_handler(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _choose_root(self):
        current = self.settings.get("last_folder") or DEFAULT_ROOT
        path = filedialog.askdirectory(initialdir=current)
        if path:
            self.settings.set("last_folder", path)
            self._restart_watcher()
            # Se a aba de configurações estiver aberta, ela precisará ser atualizada
            event_bus.emit("navigate", "settings") 

    def _restart_watcher(self):
        self._stop_watcher()
        self._start_watcher()

    def _start_watcher(self):
        root_dir = self.settings.get("last_folder") or DEFAULT_ROOT
        self.watcher = FolderWatcher(self, root_dir)
        self.watcher.start()

    def _stop_watcher(self):
        if hasattr(self, 'watcher') and self.watcher:
            self.watcher.stop_event.set()
        self.watcher = None

    def enqueue_open(self, path: str):
        self.open_queue.put(path)

    def enqueue_switch_service_log(self, service: str, path: str):
        self.switch_queue.put((service, path))

    def _consume_queues(self):
        try:
            while not self.switch_queue.empty():
                svc, path = self.switch_queue.get_nowait()
                self._switch_log_for_service(svc, path)
            while not self.open_queue.empty():
                p = self.open_queue.get_nowait()
                self._open_log_enforcing_one_per_service(p)
        except Exception as e:
            logger.error(f"Erro ao consumir filas: {e}")
        self.root.after(200, self._consume_queues)

    def _switch_log_for_service(self, service: str, new_path: str):
        old_path = self.tab_by_service.get(service)
        if old_path and old_path != new_path:
            self._close_log(old_path)
        self._open_log_enforcing_one_per_service(new_path)

    def _open_log_enforcing_one_per_service(self, filepath: str):
        if not os.path.isfile(filepath): return
        svc = service_from_path(filepath)
        
        # Garante que não tenha tab duplicada para o mesmo serviço
        try:
            self.log_container.tab(svc)
            # Se encontrou, apenas foca nela
            self.log_container.set(svc)
            return
        except:
            pass

        # Se não existe, cria no container
        self.log_container.add(svc)
        tab_frame = self.log_container.tab(svc)
        
        # Inicializa o LogTab dentro dessa aba oficial
        tab = LogTab(self, filepath, tab_frame)
        
        self.open_tabs[filepath] = tab
        self.tab_by_service[svc] = filepath
        event_bus.emit("log_opened", len(self.open_tabs))
        
        # Se split estiver ativo e container direito estiver vazio, foca nele? 
        # Por enquanto, mantém o comportamento padrão.
        
        # Força o sistema a "desenhar" a aba imediatamente
        self.root.update_idletasks()

    def _close_log(self, filepath: str):
        tab = self.open_tabs.pop(filepath, None)
        if tab:
            tab.stop_event.set()
            svc = service_from_path(filepath)
            if self.tab_by_service.get(svc) == filepath:
                del self.tab_by_service[svc]
            
            try: self.log_container.delete(svc)
            except: pass
            
            event_bus.emit("log_opened", len(self.open_tabs))

    def _restart_all_services(self):
        if not self.open_tabs: return
        services = set(tab.service_name for tab in self.open_tabs.values())
        if messagebox.askyesno("Confirmar", f"Reiniciar TODOS os {len(services)} serviços?"):
            def task():
                for s in sorted(services): restart_service_components(s)
                self.root.after(0, lambda: messagebox.showinfo("Fim", "Reinicialização concluída"))
            threading.Thread(target=task, daemon=True).start()

    def apply_settings(self):
        for tab in self.open_tabs.values():
            if hasattr(tab, 'update_settings'): tab.update_settings(self.settings)

    def _on_close(self):
        logger.info("Encerrando LogFácil Pro...")
        self._stop_watcher()
        os._exit(0)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    App().run()
