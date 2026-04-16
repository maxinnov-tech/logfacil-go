"""
Arquivo: gui/tabs/export_tab.py
Descrição: Guia (Tab) para exportação de logs selecionados para um arquivo ZIP.
"""
import os
import zipfile
import datetime
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk
from gui.utils.icon_manager import icons
from core.config import DEFAULT_ROOT
from core.logger import logger
from gui.components.spinner import LoadingSpinner

class ExportLogsTab:
    """Aba de Exportação de Logs."""
    
    def __init__(self, app):
        self.app = app
        self.frame = ctk.CTkFrame(app.main_container, fg_color="transparent")
        self.selected_folders = {}
        
        self._build_ui()
        self._load_folders()

    def _build_ui(self):
        # Header
        self.header = ctk.CTkFrame(self.frame, height=60, corner_radius=10, fg_color=("#dbdbdb", "#2b2b2b"))
        self.header.pack(side="top", fill="x", padx=10, pady=(5, 10))
        self.header.pack_propagate(False)
        
        ctk.CTkLabel(self.header, text=" Ferramenta de Exportação de Logs", compound="left", 
                     image=icons.get_icon("save"), font=ctk.CTkFont(size=14, weight="bold"), 
                     text_color="#3498db").pack(side="left", padx=15)

        # Instruções
        instr = ctk.CTkLabel(self.frame, text="Selecione as pastas e o período que deseja exportar. O sistema irá gerar um arquivo comprimido (.zip).", 
                             font=ctk.CTkFont(size=12), text_color="gray")
        instr.pack(side="top", anchor="w", padx=15, pady=(0, 10))

        # Layout Principal: Esquerda (Pastas) | Direita (Opções/Ação)
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=10)

        # 1. Lista de Pastas (Scrollable)
        folder_frame = ctk.CTkFrame(content, corner_radius=12)
        folder_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(folder_frame, text="Pastas de Logs (C:\\Quality\\LOG)", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        self.scroll_list = ctk.CTkScrollableFrame(folder_frame, fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True, padx=5, pady=5)

        # 2. Opções de Exportação
        options_frame = ctk.CTkFrame(content, width=300, corner_radius=12)
        options_frame.pack(side="right", fill="y", padx=(5, 0))
        options_frame.pack_propagate(False)

        ctk.CTkLabel(options_frame, text="Período", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))
        
        self.periodo_var = ctk.StringVar(value="7")
        periods = [("Hoje", "0"), ("7 dias", "7"), ("15 dias", "15"), ("30 dias", "30"), ("Tudo", "all"), ("Outro", "custom")]
        
        for text, val in periods:
            ctk.CTkRadioButton(options_frame, text=text, variable=self.periodo_var, value=val, 
                               command=self._on_period_change).pack(anchor="w", padx=30, pady=5)
        
        # Container de Datas Customizadas (Oculto por padrão)
        self.custom_date_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        
        ctk.CTkLabel(self.custom_date_frame, text="De:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10)
        self.entry_date_start = ctk.CTkEntry(self.custom_date_frame, placeholder_text="DD/MM/AAAA", width=180)
        self.entry_date_start.pack(padx=10, pady=(0, 5))
        
        ctk.CTkLabel(self.custom_date_frame, text="Até:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10)
        self.entry_date_end = ctk.CTkEntry(self.custom_date_frame, placeholder_text="DD/MM/AAAA", width=180)
        self.entry_date_end.pack(padx=10, pady=(0, 10))

        # Botão Exportar
        self.btn_export = ctk.CTkButton(options_frame, text="Exportar Logs", height=45, 
                                        compound="left", image=icons.get_icon("save"),
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        command=self._start_export, fg_color="#2ecc71", hover_color="#27ae60")
        self.btn_export.pack(side="bottom", fill="x", padx=20, pady=25)

    def _on_period_change(self):
        if self.periodo_var.get() == "custom":
            self.custom_date_frame.pack(padx=20, pady=10, before=self.btn_export)
            # Preenche com hoje se estiver vazio
            today = datetime.datetime.now().strftime("%d/%m/%Y")
            if not self.entry_date_start.get(): self.entry_date_start.insert(0, today)
            if not self.entry_date_end.get(): self.entry_date_end.insert(0, today)
        else:
            self.custom_date_frame.pack_forget()

    def _load_folders(self):
        root = self.app.settings.get("last_folder") or DEFAULT_ROOT
        if not os.path.isdir(root):
            return

        # Limpa lista atual
        for widget in self.scroll_list.winfo_children():
            widget.destroy()
        
        try:
            folders = sorted([f for f in os.listdir(root) if os.path.isdir(os.path.join(root, f))])
            for f in folders:
                var = ctk.BooleanVar(value=False)
                cb = ctk.CTkCheckBox(self.scroll_list, text=f, variable=var)
                cb.pack(anchor="w", padx=10, pady=5)
                self.selected_folders[f] = var
        except Exception as e:
            logger.error(f"Erro ao carregar pastas para exportar: {e}")

    def _start_export(self):
        folders_to_export = [f for f, var in self.selected_folders.items() if var.get()]
        if not folders_to_export:
            messagebox.showwarning("Aviso", "Selecione pelo menos uma pasta para exportar.")
            return

        # Perguntar destino
        dest_file = filedialog.asksaveasfilename(
            title="Salvar logs exportados",
            defaultextension=".zip",
            filetypes=[("Arquivo ZIP", "*.zip")],
            initialfile=f"Logs_Exportados_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        )
        
        if not dest_file:
            return

        # Lógica de Intervalo de Datas
        limit_start = None
        limit_end = None
        period = self.periodo_var.get()
        today = datetime.datetime.now()

        if period == "custom":
            # Captura e valida as datas manuais
            date_start_str = self.entry_date_start.get().strip()
            date_end_str = self.entry_date_end.get().strip()
            try:
                if date_start_str:
                    limit_start = datetime.datetime.strptime(date_start_str, "%d/%m/%Y")
                    limit_start = limit_start.replace(hour=0, minute=0, second=0)
                if date_end_str:
                    limit_end = datetime.datetime.strptime(date_end_str, "%d/%m/%Y")
                    limit_end = limit_end.replace(hour=23, minute=59, second=59)
            except ValueError:
                messagebox.showerror("Erro", "Formato de data inválido. Use DD/MM/AAAA")
                return
        elif period == "all":
            limit_start = None
            limit_end = None
        else:
            # Atalhos rápidos (Hoje, 7d, 15d, 30d)
            days = int(period)
            limit_start = today - datetime.timedelta(days=days)
            limit_start = limit_start.replace(hour=0, minute=0, second=0)
            limit_end = today.replace(hour=23, minute=59, second=59)

        spinner = LoadingSpinner(self.frame, "Processando exportação...")
        spinner.show()
        
        def run():
            try:
                success, count = self._do_export(folders_to_export, limit_start, limit_end, dest_file)
                if success:
                    msg = f"Exportação concluída!\n{count} arquivos compactados em:\n{dest_file}"
                    self.frame.after(0, lambda: messagebox.showinfo("Sucesso", msg))
                    os.startfile(os.path.dirname(dest_file))
                else:
                    self.frame.after(0, lambda: messagebox.showwarning("Aviso", "Nenhum arquivo encontrado para exportar."))
            except Exception as e:
                logger.error(f"Erro na exportação: {e}")
                self.frame.after(0, lambda: messagebox.showerror("Erro", f"Falha ao exportar logs: {e}"))
            finally:
                self.frame.after(0, spinner.hide)

        threading.Thread(target=run, daemon=True).start()

    def _do_export(self, folders, limit_start, limit_end, dest_path):
        root_path = self.app.settings.get("last_folder") or DEFAULT_ROOT
        
        # Primeiro passo: Listar arquivos que batem com o critério
        files_to_zip = []
        all_available_files = [] # Para o fallback silencioso
        
        for folder in folders:
            folder_full_path = os.path.join(root_path, folder)
            if not os.path.exists(folder_full_path): continue
            
            for root, _, files in os.walk(folder_full_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        mtime_ts = os.path.getmtime(file_path)
                        mtime = datetime.datetime.fromtimestamp(mtime_ts)
                        
                        all_available_files.append((file_path, mtime))
                        
                        # Filtro de data
                        if limit_start and mtime < limit_start:
                            continue
                        if limit_end and mtime > limit_end:
                            continue
                        
                        files_to_zip.append(file_path)
                    except: continue

        # Lógica de Fallback Silencioso:
        # Se um filtro de início foi definido mas a lista resultou vazia, 
        # e existem arquivos disponíveis nestas pastas, ignoramos o filtro de data.
        if not files_to_zip and limit_start and all_available_files:
            files_to_zip = [f[0] for f in all_available_files]
        
        if not files_to_zip:
            return False, 0

        # Segundo passo: Criar o ZIP
        with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files_to_zip:
                try:
                    arcname = os.path.relpath(file_path, root_path)
                    zipf.write(file_path, arcname)
                except: continue
        
        return True, len(files_to_zip)
