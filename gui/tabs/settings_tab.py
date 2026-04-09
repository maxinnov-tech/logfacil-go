"""
Arquivo: gui/tabs/settings_tab.py
Descrição: Guia (Tab) de Configurações integrada ao Notebook principal.
Substitui o antigo diálogo Toplevel para garantir máxima compatibilidade e 
visibilidade dos controles de personalização, como o tamanho da fonte.
"""
import customtkinter as ctk
from core.logger import logger

class SettingsTab:
    """Aba de configurações do sistema integrada ao notebook."""
    
    def __init__(self, app):
        self.app = app
        self.settings = app.settings
        self.frame = ctk.CTkFrame(app.notebook)
        self._build_ui()

    def _build_ui(self):
        # Container centralizado para não ficar muito espalhado em telas grandes
        container = ctk.CTkFrame(self.frame, fg_color="transparent", width=600)
        container.pack(pady=40, padx=40, fill="y")
        
        ctk.CTkLabel(container, text="⚙️ Configurações do Sistema", 
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(0, 30))
        
        # --- Seção: Log ---
        section_log = ctk.CTkFrame(container, fg_color="transparent")
        section_log.pack(fill="x", pady=10)
        
        ctk.CTkLabel(section_log, text="Visualização de Logs", 
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="#4CAF50").pack(anchor="w", pady=(0, 10))
        
        # Grid para os controles da fonte
        font_ctrl = ctk.CTkFrame(section_log, fg_color="#2b2b2b", corner_radius=10)
        font_ctrl.pack(fill="x", padx=2, pady=5)
        
        ctk.CTkLabel(font_ctrl, text="Tamanho da fonte dos logs:", 
                     font=ctk.CTkFont(size=14)).grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        current_font = self.settings.get("font_size", 13)
        
        self.font_slider = ctk.CTkSlider(font_ctrl, from_=8, to=24, number_of_steps=16,
                                         command=self._on_font_change, width=250)
        self.font_slider.set(current_font)
        self.font_slider.grid(row=0, column=1, padx=10, pady=20)
        
        self.font_curr_lbl = ctk.CTkLabel(font_ctrl, text=str(current_font), 
                                         font=ctk.CTkFont(size=16, weight="bold"), width=40)
        self.font_curr_lbl.grid(row=0, column=2, padx=20, pady=20)
        
        # --- Botão Salvar ---
        save_btn = ctk.CTkButton(container, text="💾 Salvar e Aplicar Agora", 
                                 command=self._save, height=45, width=250,
                                 font=ctk.CTkFont(size=15, weight="bold"),
                                 fg_color="#28a745", hover_color="#218838")
        save_btn.pack(pady=40)
        
        # Mensagem de ajuda
        ctk.CTkLabel(container, text="As alterações serão aplicadas em todas as abas de log abertas.",
                     text_color="gray", font=ctk.CTkFont(size=12)).pack()

    def _on_font_change(self, value):
        val = int(value)
        self.font_curr_lbl.configure(text=str(val))

    def _save(self):
        new_font = int(self.font_slider.get())
        self.settings.set("font_size", new_font)
        
        # Aplica na aplicação principal
        self.app.apply_settings()
        logger.info(f"Configurações salvas: fonte {new_font}")
        
        # Feedback visual simples (opcional)
        original_text = self.font_curr_lbl.cget("text")
        self.font_curr_lbl.configure(text_color="green")
        self.frame.after(1000, lambda: self.font_curr_lbl.configure(text_color="white"))
