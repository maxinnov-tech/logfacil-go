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
from PIL import Image

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
from gui.utils.icon_manager import icons
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
        # Pequena pausa para garantir que o sistema de arquivos esteja estável no boot
        time.sleep(0.5)
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
        # ============================================================
        # HEADER - Ocupa a largura TOTAL da janela (acima de tudo)
        # ============================================================
        self.header = ctk.CTkFrame(self.root, height=64, corner_radius=0,
                                   fg_color=("#e8e8e8", "#1a1a2e"))
        self.header.pack(side="top", fill="x")
        self.header.pack_propagate(False)

        # Logomarca no canto esquerdo do header
        logo_path = icons.resource_path("assets/LogoSistema.png")
        try:
            pil_img = Image.open(logo_path)
            self.header_logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(200, 44))
            self.logo_header = ctk.CTkLabel(self.header, image=self.header_logo_img, text="")
            self.logo_header.pack(side="left", padx=(16, 0))
        except Exception as e:
            logger.error(f"Erro ao carregar logo no header: {e}")
            self.logo_header = ctk.CTkLabel(self.header, text="LogFácil Pro",
                                            font=ctk.CTkFont(size=22, weight="bold"), text_color="#3498db")
            self.logo_header.pack(side="left", padx=(16, 0))

        # ============================================================
        # BARRA DE STATUS - Base da janela
        # ============================================================
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side="bottom", fill="x")

        # ============================================================
        # BODY - Frame que contém Sidebar + Conteúdo principal
        # ============================================================
        self.body = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.body.pack(side="top", fill="both", expand=True)

        # Main container criado PRIMEIRO (antes da sidebar)
        self.main_container = ctk.CTkFrame(self.body, corner_radius=0, fg_color="transparent")
        self.main_container.pack(side="right", fill="both", expand=True)

        # ============================================================
        # VIEWS - Inicializadas ANTES da Sidebar para evitar navegação vazia
        # ============================================================
        self.views["dashboard"] = DashboardTab(self)
        self.views["pdvs"] = PDVMonitorTab(self)
        self.views["settings"] = SettingsTab(self)

        # Log Container (TabView)
        self.log_container = ctk.CTkTabview(self.main_container)
        self.views["logs"] = self.log_container

        # Sidebar criada DEPOIS das views (para que a navegação inicial funcione)
        self.sidebar = Sidebar(self.body, on_change_callback=self._on_nav_change)
        self.sidebar.pack(side="left", fill="y")

        # Garante que a view de Logs é exibida ao iniciar
        # (usamos after para aguardar o primeiro draw da janela)
        self.root.after(100, lambda: self._on_nav_change("logs"))

        # Binds Globais
        self.root.bind("<Control-Shift-F>", lambda e: self._open_global_search())
        self.root.bind("<Control-Shift-f>", lambda e: self._open_global_search())

    def _open_global_search(self):
        GlobalSearch(self)

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
            
            # O título textual foi removido em favor da logo central fixa.
            # Se desejar manter o título junto com a logo de forma discreta, podemos ajustar.
            pass

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
            to_open = []
            while not self.open_queue.empty():
                to_open.append(self.open_queue.get_nowait())
            
            # Ordenação Alfabética do Lote (Garante que mesmo que cheguem fora de ordem no queue, 
            # as abas sejam criadas na ordem correta)
            if to_open:
                to_open.sort(key=lambda p: service_from_path(p).lower())
                for p in to_open:
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
