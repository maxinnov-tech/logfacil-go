"""
Arquivo: gui/tabs/dashboard_tab.py
Descrição: Tela inicial (Dashboard) do LogFácil Pro.
Fornece um resumo visual da atividade de monitoramento, atalhos rápidos
e estatísticas em tempo real sobre os serviços detectados.
"""
import customtkinter as ctk
from core.config import VERSION
from core.event_bus import event_bus

class DashboardTab:
    """Tela de Dashboard Inicial."""
    
    def __init__(self, app):
        self.app = app
        self.frame = ctk.CTkFrame(app.main_container, fg_color="transparent")
        self._build_ui()
        
        # Inscreve-se em eventos interessantes
        event_bus.subscribe("log_opened", self._on_log_opened)
        event_bus.subscribe("pdv_updated", self._on_pdv_updated)

    def _build_ui(self):
        # Título de Boas-vindas
        welcome_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        welcome_frame.pack(fill="x", padx=40, pady=(40, 20))
        
        ctk.CTkLabel(welcome_frame, text="Bem-vindo ao LogFácil Pro", 
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="#3498db").pack(anchor="w")
        
        ctk.CTkLabel(welcome_frame, text=f"Versão {VERSION} • Monitoramento Centralizado de Serviços", 
                     font=ctk.CTkFont(size=14),
                     text_color="gray").pack(anchor="w")
        
        # Grid de Cartões de Status
        stats_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        stats_frame.pack(fill="x", padx=40, pady=20)
        
        self.card_logs = self._create_stat_card(stats_frame, "Logs Ativos", "0", "#4dabf7")
        self.card_logs.grid(row=0, column=0, padx=(0, 20), sticky="nsew")
        
        self.card_pdvs = self._create_stat_card(stats_frame, "PDVs Detectados", "0", "#da77f2")
        self.card_pdvs.grid(row=0, column=1, padx=20, sticky="nsew")
        
        self.card_status = self._create_stat_card(stats_frame, "Status Sistema", "Operacional", "#51cf66")
        self.card_status.grid(row=0, column=2, padx=20, sticky="nsew")
        
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Atalhos Rápidos
        quick_frame = ctk.CTkFrame(self.frame, fg_color=("#dbdbdb", "#2b2b2b"), corner_radius=15)
        quick_frame.pack(fill="x", padx=40, pady=20)
        
        ctk.CTkLabel(quick_frame, text="Atalhos Rápidos", font=ctk.CTkFont(size=16, weight="bold")).pack(padx=20, pady=(15, 10), anchor="w")
        
        btn_container = ctk.CTkFrame(quick_frame, fg_color="transparent")
        btn_container.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkButton(btn_container, text="📂 Escolher Nova Pasta", command=self.app._choose_root, width=180, height=40).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_container, text="🔄 Reiniciar Todos", command=self.app._restart_all_services, fg_color="#f0ad4e", hover_color="#eea236", width=180, height=40).pack(side="left", padx=10)
        ctk.CTkButton(btn_container, text="⚙️ Configurações", command=lambda: event_bus.emit("navigate", "settings"), fg_color="#555", width=180, height=40).pack(side="left", padx=10)

    def _create_stat_card(self, parent, title, value, color):
        card = ctk.CTkFrame(parent, height=130, corner_radius=15, 
                            border_width=1, border_color=("#dbdbdb", "#333333"),
                            fg_color=("#f8f9fa", "#252525"))
        card.pack_propagate(False)
        
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13), text_color="gray").pack(pady=(15, 0))
        lbl_val = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=32, weight="bold"), text_color=color)
        lbl_val.pack(pady=(5, 15))
        
        # Guardar referência para atualizar depois
        card.val_label = lbl_val
        return card

    def _on_log_opened(self, count):
        self.card_logs.val_label.configure(text=str(count))

    def _on_pdv_updated(self, count):
        self.card_pdvs.val_label.configure(text=str(count))
