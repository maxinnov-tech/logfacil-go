"""
Arquivo: gui/tabs/settings_tab.py
Descrição: Guia (Tab) Pro de Configurações do LogFácil.
Implementa o conceito de "Configurações Vivas": qualquer alteração nos sliders
ou seletores é aplicada e salva instantaneamente no disco.
"""
import customtkinter as ctk
from core.logger import logger

class SettingsTab:
    """Painel de Configurações Pro com Auto-Save."""
    
    def __init__(self, app):
        self.app = app
        self.settings = app.settings
        self.frame = ctk.CTkFrame(app.main_container, fg_color="transparent")
        self._build_ui()

    def _build_ui(self):
        # Container Central
        container = ctk.CTkFrame(self.frame, fg_color="transparent")
        container.pack(pady=30, padx=50, fill="both", expand=True)
        
        ctk.CTkLabel(container, text="⚙️ Preferências do Sistema", 
                     font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 20))
        
        # --- Grupo: Visualização ---
        vis_group = self._create_group(container, "🎨 Visualização e Estilo")
        
        # Tamanho da Fonte
        self._add_setting_row(vis_group, "Tamanho da fonte (Logs):", 
                             self._create_font_slider, row=0)
        
        # Tema
        self._add_setting_row(vis_group, "Modo de aparência:", 
                             self._create_theme_switch, row=1)
        
        # --- Grupo: Monitoramento ---
        mon_group = self._create_group(container, "🔍 Comportamento de Monitoramento")
        
        # Intervalo de Scan
        self._add_setting_row(mon_group, "Intervalo de scan (seg):", 
                             self._create_scan_slider, row=0)

        # --- Grupo: Diretório ---
        dir_group = self._create_group(container, "📍 Diretório do Sistema")
        
        # Pasta de Logs
        self._add_setting_row(dir_group, "Pasta raiz de LOGs:", 
                             self._create_folder_selector, row=0)

        # Footer informativo (já que não tem botão de salvar)
        ctk.CTkLabel(container, text="✨ Todas as alterações são salvas e aplicadas automaticamente.",
                     font=ctk.CTkFont(size=12, slant="italic"), text_color="gray").pack(pady=40)

    def _create_group(self, parent, title):
        frame = ctk.CTkFrame(parent, fg_color=("#dbdbdb", "#2b2b2b"), corner_radius=15)
        frame.pack(fill="x", pady=10, padx=0)
        
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14, weight="bold"), 
                     text_color="#3498db").pack(anchor="w", padx=20, pady=(15, 10))
        
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=(0, 15))
        content.grid_columnconfigure(1, weight=1)
        return content

    def _add_setting_row(self, parent, label_text, widget_func, row):
        ctk.CTkLabel(parent, text=label_text).grid(row=row, column=0, sticky="w", pady=10)
        widget = widget_func(parent)
        widget.grid(row=row, column=1, sticky="e", pady=10, padx=(20, 0))

    def _create_font_slider(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        current = self.settings.get("font_size", 13)
        
        self.font_lbl = ctk.CTkLabel(frame, text=str(current), width=30, font=ctk.CTkFont(weight="bold"))
        self.font_lbl.pack(side="right", padx=(10, 0))
        
        self.font_slider = ctk.CTkSlider(frame, from_=8, to=24, number_of_steps=16, width=200,
                                         command=self._on_font_change)
        self.font_slider.set(current)
        self.font_slider.pack(side="right")
        return frame

    def _create_theme_switch(self, parent):
        current = self.settings.get("appearance_mode", "dark")
        self.theme_var = ctk.StringVar(value=current)
        btn = ctk.CTkSegmentedButton(parent, values=["light", "dark"], 
                                     variable=self.theme_var, width=200,
                                     command=self._on_theme_change)
        return btn

    def _create_scan_slider(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        current = self.settings.get("scan_interval", 2.0)
        self.scan_lbl = ctk.CTkLabel(frame, text=f"{current}s", width=40)
        self.scan_lbl.pack(side="right", padx=(10, 0))
        
        self.scan_slider = ctk.CTkSlider(frame, from_=0.5, to=10.0, number_of_steps=19, width=200,
                                         command=self._on_scan_change)
        self.scan_slider.set(current)
        self.scan_slider.pack(side="right")
        return frame

    def _create_folder_selector(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        current = self.settings.get("last_folder") or "Não configurado"
        
        # Label truncada se for muito longa
        display_path = (current[:40] + '...') if len(current) > 40 else current
        self.path_lbl = ctk.CTkLabel(frame, text=display_path, font=ctk.CTkFont(size=11), text_color="gray")
        self.path_lbl.pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(frame, text="Alterar Pasta", width=120, height=30,
                      command=self.app._choose_root).pack(side="right")
        return frame

    # --- Callbacks de Auto-Save ---

    def _on_font_change(self, value):
        val = int(value)
        self.font_lbl.configure(text=str(val))
        self.settings.set("font_size", val)
        self.app.apply_settings()

    def _on_theme_change(self, value):
        self.settings.set("appearance_mode", value)
        ctk.set_appearance_mode(value)
        logger.info(f"Tema alterado para: {value}")

    def _on_scan_change(self, value):
        val = round(float(value), 1)
        self.scan_lbl.configure(text=f"{val}s")
        self.settings.set("scan_interval", val)
