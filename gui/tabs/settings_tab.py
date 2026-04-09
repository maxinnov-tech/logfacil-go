"""
Arquivo: gui/tabs/settings_tab.py
Descrição: Guia (Tab) Pro de Configurações do LogFácil.
Oferece controle centralizado sobre a aparência do sistema, comportamento
de monitoramento e preferências de visualização, tudo salvo permanentemente.
"""
import customtkinter as ctk
from core.logger import logger

class SettingsTab:
    """Painel de Configurações Pro."""
    
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

        # Botão Salvar Geral
        self.save_btn = ctk.CTkButton(container, text="💾 Salvar Todas as Alterações", 
                                      command=self._save_all, height=45, width=280,
                                      font=ctk.CTkFont(size=15, weight="bold"),
                                      fg_color="#2ecc71", hover_color="#27ae60")
        self.save_btn.pack(pady=40, anchor="center")

    def _create_group(self, parent, title):
        frame = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=15)
        frame.pack(fill="x", pady=10, padx=0)
        
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14, weight="bold"), 
                     text_color="#4CAF50").pack(anchor="w", padx=20, pady=(15, 10))
        
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
                                         command=lambda v: self.font_lbl.configure(text=str(int(v))))
        self.font_slider.set(current)
        self.font_slider.pack(side="right")
        return frame

    def _create_theme_switch(self, parent):
        current = self.settings.get("appearance_mode", "dark")
        self.theme_var = ctk.StringVar(value=current)
        return ctk.CTkSegmentedButton(parent, values=["light", "dark"], variable=self.theme_var, width=200)

    def _create_scan_slider(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        current = self.settings.get("scan_interval", 2.0)
        self.scan_lbl = ctk.CTkLabel(frame, text=f"{current}s", width=40)
        self.scan_lbl.pack(side="right", padx=(10, 0))
        
        self.scan_slider = ctk.CTkSlider(frame, from_=0.5, to=10.0, number_of_steps=19, width=200,
                                         command=lambda v: self.scan_lbl.configure(text=f"{round(float(v),1)}s"))
        self.scan_slider.set(current)
        self.scan_slider.pack(side="right")
        return frame

    def _save_all(self):
        try:
            # Coleta valores
            new_font = int(self.font_slider.get())
            new_theme = self.theme_var.get()
            new_scan = round(float(self.scan_slider.get()), 1)
            
            # Salva no manager
            self.settings.set("font_size", new_font)
            self.settings.set("appearance_mode", new_theme)
            self.settings.set("scan_interval", new_scan)
            
            # Aplica mudanças imediatas
            ctk.set_appearance_mode(new_theme)
            self.app.apply_settings()
            
            # Feedback
            self.save_btn.configure(text="✅ Configurações Salvas!", fg_color="#27ae60")
            self.frame.after(2000, lambda: self.save_btn.configure(text="💾 Salvar Todas as Alterações", fg_color="#2ecc71"))
            
            logger.info("Configurações atualizadas pelo usuário.")
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
