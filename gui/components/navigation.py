"""
Arquivo: gui/components/navigation.py
Descrição: Barra lateral de navegação (Sidebar) do LogFácil v2.
"""
import customtkinter as ctk
from gui.utils.icon_manager import icons
from core.config import VERSION

class Sidebar(ctk.CTkFrame):
    """Barra lateral de navegação personalizada."""
    
    def __init__(self, parent, on_change_callback):
        super().__init__(parent, width=200, corner_radius=0)
        self.on_change = on_change_callback
        self.active_btn = None
        self.buttons = {}
        
        self._build_ui()

    def _build_ui(self):
        # Logo / Título
        self.logo_label = ctk.CTkLabel(self, text="LogFácil Pro", 
                                      font=ctk.CTkFont(size=20, weight="bold"),
                                      text_color="#3498db")
        self.logo_label.pack(pady=(25, 30))
        
        # Botões de Navegação
        self._add_nav_btn("DASHBOARD", "dashboard", icon_name="dashboard")
        self._add_nav_btn("LOGS", "logs", icon_name="logs")
        self._add_nav_btn("PDVs", "pdvs", icon_name="pdv")
        
        # Espaçamento vertical
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        
        # Botão Settings no rodapé
        self._add_nav_btn("Configurações", "settings", icon_name="settings")
        
        # Versão dinâmica
        self.version_label = ctk.CTkLabel(self, text=f"v{VERSION}", text_color="gray", font=ctk.CTkFont(size=10))
        self.version_label.pack(pady=10)

    def _add_nav_btn(self, text, view_id, icon_name=None):
        icon_obj = icons.get_icon(icon_name) if icon_name else None
        
        btn = ctk.CTkButton(self, text=f"  {text}", 
                            image=icon_obj,
                            height=45,
                            corner_radius=10,
                            fg_color="transparent",
                            hover_color=("#e5e5e5", "#2d2d2d"),
                            text_color=("#444444", "#cccccc"),
                            anchor="w",
                            font=ctk.CTkFont(size=14),
                            command=lambda v=view_id: self._on_btn_click(v))
        btn.pack(fill="x", padx=10, pady=2)
        self.buttons[view_id] = btn
        
        if not self.active_btn and view_id == "logs":
            self._on_btn_click(view_id)

    def _on_btn_click(self, view_id):
        if self.active_btn:
            self.buttons[self.active_btn].configure(fg_color="transparent", text_color=("black", "white"))
        
        self.active_btn = view_id
        self.buttons[view_id].configure(fg_color=("#dbdbdb", "#3d3d3d"), text_color=("#3498db", "#3498db"))
        
        if self.on_change:
            self.on_change(view_id)

    def select(self, view_id):
        if view_id in self.buttons:
            self._on_btn_click(view_id)
