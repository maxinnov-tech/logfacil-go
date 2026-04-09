"""
Arquivo: gui/app.py
Descrição: Classe Principal da Interface Gráfica (GUI) do LogFácil.
Este é o coração visual da aplicação. Ele orquestra os componentes da aba (Notebooks),
layout geral, barra superior, rodapé, e menu de controles.
É nesse arquivo que fica hospedada a Thread observadora (FolderWatcher), encarregada
de constantemente verificar alterações no diretório raiz do LOG e injetar novos
arquivos visualizáveis perfeitamente em suas próprias abas de sistema utilizando filas.
Ele amarra a interação entre módulos Visuais e Funcionais essenciais da plataforma.
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
from gui.managers.update_manager import AutoUpdateManager
from gui.tabs.log_tab import LogTab
from gui.tabs.pdv_tab import PDVMonitorTab
from gui.dialogs.settings_dialog import SettingsDialog
from core.settings_manager import SettingsManager

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
            for svc, path in latest_map.items():
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
        logger.info(f"Iniciando LogFácil v{VERSION}")
        logger.info("="*50)
        
        self.settings = SettingsManager()
        self._setup_window()
        self._build_topbar()
        self._setup_notebook()
        self._setup_queues()
        self._start_watcher()
        self._setup_footer()
        self._setup_close_handler()
        self._setup_pdv_monitor_tab()
        
        self.update_manager = AutoUpdateManager(self)
        self.root.after(3000, self.update_manager.check_updates_silent)
        
        logger.info("Interface inicializada com sucesso")
    
    def _setup_window(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title(f"LogFácil v{VERSION} - Monitor de Serviços")
        self.root.geometry("1400x800")
        self.root.minsize(800, 600)
    
    def _build_topbar(self):
        bar = ctk.CTkFrame(self.root, height=60, corner_radius=0)
        bar.pack(side="top", fill="x", padx=0, pady=0)
        bar.pack_propagate(False)
        
        ctk.CTkLabel(bar, text="📁 Raiz LOG:", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(15, 5))
        
        self.entry = ctk.CTkEntry(bar, width=500, height=35, placeholder_text="Caminho da pasta LOG")
        self.entry.pack(side="left", padx=5)
        self.entry.insert(0, DEFAULT_ROOT)
        
        ctk.CTkButton(bar, text="📂 Escolher pasta", command=self._choose_root, height=35, width=120).pack(side="left", padx=5)
        
        settings_btn = ctk.CTkButton(bar, text="⚙️", width=40, height=35, command=self._show_settings_menu)
        settings_btn.pack(side="right", padx=5)
        
        ctk.CTkButton(bar, text="🔄 Reiniciar Todos", command=self._restart_all_services, height=35,
                      width=180, fg_color="#f0ad4e", hover_color="#eea236").pack(side="right", padx=5)
    
    def _show_settings_menu(self):
        menu = tk.Menu(self.root, tearoff=0, bg="#2b2b2b", fg="white",
                       activebackground="#404040", activeforeground="white")
        
        menu.add_command(label="🔄 Verificar Atualizações", command=self.update_manager.check_and_update)
        menu.add_command(label="⚙️ Configurações", command=self._open_settings)
        menu.add_separator()
        menu.add_command(label="ℹ️ Sobre", command=self._show_about)
        
        try:
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()
    
    def _show_about(self):
        about_text = f"""
LogFácil - Monitor de Serviços
Versão: {CURRENT_VERSION}

Um sistema completo para:
• Monitoramento de logs em tempo real
• Reinicialização de serviços Windows
• Identificação de múltiplos PDVs
• Atualização automática via GitHub

GitHub: https://github.com/{GITHUB_REPO}
"""
        messagebox.showinfo("Sobre o LogFácil", about_text.strip())
    
    def _open_settings(self):
        SettingsDialog(self.root, self)

    def apply_settings(self):
        """Aplica as configurações atuais em toda a aplicação."""
        if hasattr(self, 'open_tabs'):
            for tab in self.open_tabs.values():
                if hasattr(tab, 'update_settings'):
                    tab.update_settings(self.settings)
        logger.info("Configurações aplicadas na UI.")
    
    def _setup_footer(self):
        footer = ctk.CTkFrame(self.root, height=25, corner_radius=0)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        ctk.CTkLabel(footer, text=f"v{VERSION} • LogFácil", text_color="#888888").pack(side="right", padx=10)
    
    def _setup_notebook(self):
        self.notebook = ctk.CTkTabview(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 5))
    
    def _setup_queues(self):
        self.open_tabs = {}
        self.tab_by_service = {}
        self.open_queue = queue.Queue()
        self.switch_queue = queue.Queue()
        self.watcher = None
        self.root.after(120, self._consume_queues)
    
    def _setup_close_handler(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _setup_pdv_monitor_tab(self):
        self.notebook.add("📊 PDVs")
        self.pdv_monitor = PDVMonitorTab(self)
        
        for name, frame in list(self.notebook._tab_dict.items()):
            if name == "📊 PDVs" and frame != self.pdv_monitor.frame:
                try:
                    frame.destroy()
                except Exception:
                    pass
                self.notebook._tab_dict[name] = self.pdv_monitor.frame
                break
    
    def _choose_root(self):
        path = filedialog.askdirectory(initialdir=self.entry.get() or DEFAULT_ROOT)
        if path:
            self.entry.delete(0, "end")
            self.entry.insert(0, path)
            self._restart_watcher()
    
    def _restart_watcher(self):
        self._stop_watcher()
        self._start_watcher()
    
    def _start_watcher(self):
        root_dir = self.entry.get().strip() or DEFAULT_ROOT
        self.watcher = FolderWatcher(self, root_dir)
        self.watcher.start()
    
    def _stop_watcher(self):
        if self.watcher:
            self.watcher.stop_event.set()
            self.watcher = None
    
    def enqueue_open(self, path: str):
        self.open_queue.put(path)
    
    def enqueue_switch_service_log(self, service: str, path: str):
        self.switch_queue.put((service, path))
    
    def _consume_queues(self):
        try:
            while True:
                try:
                    svc, path = self.switch_queue.get_nowait()
                    self._switch_log_for_service(svc, path)
                except queue.Empty:
                    break
            
            while True:
                try:
                    p = self.open_queue.get_nowait()
                    self._open_log_enforcing_one_per_service(p)
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"Erro ao consumir filas: {e}")
        
        self.root.after(200, self._consume_queues)
    
    def _switch_log_for_service(self, service: str, new_path: str):
        try:
            old_path = self.tab_by_service.get(service)
            if old_path and old_path != new_path:
                self._close_log(old_path)
            self._open_log_enforcing_one_per_service(new_path)
        except Exception as e:
            logger.error(f"Erro ao trocar log: {e}")
    
    def _open_log_enforcing_one_per_service(self, filepath: str):
        try:
            if not os.path.isfile(filepath):
                return
            
            svc = service_from_path(filepath)
            existing_path = self.tab_by_service.get(svc)
            
            if existing_path and existing_path != filepath:
                self._close_log(existing_path)
            
            if filepath in self.open_tabs:
                tab = self.open_tabs[filepath]
                for tab_name, tab_frame in self.notebook._tab_dict.items():
                    if tab_frame == tab.frame:
                        self.notebook.set(tab_name)
                        break
                self.tab_by_service[svc] = filepath
                return
            
            tab_name = svc
            base_name = tab_name
            counter = 1
            while tab_name in self.notebook._tab_dict:
                tab_name = f"{base_name} ({counter})"
                counter += 1
            
            self.notebook.add(tab_name)
            tab = LogTab(self, filepath)
            
            for name, frame in list(self.notebook._tab_dict.items()):
                if name == tab_name and frame != tab.frame:
                    try:
                        frame.destroy()
                    except Exception:
                        pass
                    self.notebook._tab_dict[name] = tab.frame
                    break
            
            self.open_tabs[filepath] = tab
            self.tab_by_service[svc] = filepath
            self.notebook.set(tab_name)
            
        except Exception as e:
            logger.error(f"Erro ao abrir log: {e}")
    
    def _close_log(self, filepath: str):
        try:
            tab = self.open_tabs.pop(filepath, None)
            if not tab:
                return
            
            tab.stop_event.set()
            
            for tab_name, tab_frame in list(self.notebook._tab_dict.items()):
                if tab_frame == tab.frame:
                    try:
                        self.notebook.delete(tab_name)
                    except Exception:
                        pass
                    break
            
            svc = service_from_path(filepath)
            if self.tab_by_service.get(svc) == filepath:
                del self.tab_by_service[svc]
        except Exception as e:
            logger.error(f"Erro ao fechar log: {e}")
    
    def _restart_all_services(self):
        if not hasattr(self, 'open_tabs') or not self.open_tabs:
            messagebox.showinfo("Info", "Nenhum serviço sendo monitorado.")
            return
        
        services = set(tab.service_name for tab in self.open_tabs.values())
        
        if messagebox.askyesno("Confirmar", f"Reiniciar TODOS os {len(services)} serviços?"):
            for tab in self.open_tabs.values():
                tab.btn_restart.configure(state="disabled")
            
            def restart_all_thread():
                for service in sorted(services):
                    try:
                        restart_service_components(service)
                    except Exception:
                        pass
                self.root.after(0, self._restart_all_callback)
            
            threading.Thread(target=restart_all_thread, daemon=True).start()
    
    def _restart_all_callback(self):
        if hasattr(self, 'open_tabs'):
            for tab in self.open_tabs.values():
                tab.btn_restart.configure(state="normal")
        messagebox.showinfo("Concluído", "Reinicialização em massa concluída!")
    
    def _on_close(self):
        logger.info("Encerrando aplicação...")
        self._stop_watcher()
        if hasattr(self, 'pdv_monitor'):
            self.pdv_monitor.parar_monitoramento()
        if hasattr(self, 'open_tabs'):
            for t in list(self.open_tabs.values()):
                t.stop_event.set()
        self.root.destroy()
        logger.info("Aplicação encerrada")
        sys.exit(0)
    
    def run(self):
        self.root.mainloop()
