"""
Arquivo: gui/components/navigation.py
Descrição: Barra lateral de navegação (Sidebar) do LogFácil v2.
Fornece o controle principal de trocas de seções do sistema (Dashboard, Logs, Configs, etc).
Utiliza ícones e estados visuais para indicar a seção ativa.
"""
import customtkinter as ctk

class Sidebar(ctk.CTkFrame):
    """Barra lateral de navegação personalizada."""
    
    def __init__(self, parent, on_change_callback):
        super().__init__(parent, width=180, corner_radius=0)
        self.on_change = on_change_callback
        self.active_btn = None
        self.buttons = {}
        
        self._build_ui()

    def _build_ui(self):
        # Logo / Título
        logo_label = ctk.CTkLabel(self, text="LogFácil Pro", 
                                  font=ctk.CTkFont(size=20, weight="bold"),
                                  text_color="#4CAF50")
        logo_label.pack(pady=(20, 30))
        
        # Botões de Navegação
        self._add_nav_btn("🏠 Dashboard", "dashboard")
        self._add_nav_btn("📁 Logs", "logs")
        self._add_nav_btn("📊 PDVs", "pdvs")
        
        # Espaçamento vertical (empurra configs para baixo)
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        
        self._add_nav_btn("⚙️ Configurações", "settings")
        
        # Branding / Versão no Rodapé
        version_label = ctk.CTkLabel(self, text="v2.0.0", text_color="gray", font=ctk.CTkFont(size=10))
        version_label.pack(pady=10)

    def _add_nav_btn(self, text, view_id):
        btn = ctk.CTkButton(self, text=text, 
                            height=45,
                            corner_radius=8,
                            fg_color="transparent",
                            hover_color="#333333",
                            anchor="w",
                            font=ctk.CTkFont(size=14),
                            command=lambda v=view_id: self._on_btn_click(v))
        btn.pack(fill="x", padx=10, pady=2)
        self.buttons[view_id] = btn
        
        if not self.active_btn: # Primeiro botão é o padrão
            self._on_btn_click(view_id)

    def _on_btn_click(self, view_id):
        # Reseta o anterior
        if self.active_btn:
            self.buttons[self.active_btn].configure(fg_color="transparent", text_color="white")
        
        # Ativa o novo
        self.active_btn = view_id
        self.buttons[view_id].configure(fg_color="#4CAF50", text_color="black")
        
        # Notifica o app
        if self.on_change:
            self.on_change(view_id)

    def select(self, view_id):
        """Seleciona programaticamente um item (útil para eventos externos)."""
        if view_id in self.buttons:
            self._on_btn_click(view_id)
