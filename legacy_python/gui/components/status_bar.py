"""
Arquivo: gui/components/status_bar.py
Descrição: Rodapé (Status Bar) informativo e moderno do LogFácil Pro.
Fornece feedback visual sobre o estado global do sistema, contagem de logs
e versão, integrando-se via Event Bus.
"""
import customtkinter as ctk
from core.config import VERSION
from core.event_bus import event_bus

class StatusBar(ctk.CTkFrame):
    """Barra de status fina no rodapé da aplicação."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, height=28, corner_radius=0, fg_color=("#eeeeee", "#1e1e1e"), **kwargs)
        self.pack_propagate(False)
        self._build_ui()
        
        # Inscrições
        event_bus.subscribe("log_opened", self._on_log_count_changed)
        event_bus.subscribe("pdv_updated", self._on_pdvs_changed)

    def _build_ui(self):
        # 1. Status do Sistema (Esquerda)
        self.status_indicator = ctk.CTkFrame(self, width=10, height=10, corner_radius=5, fg_color="#2ecc71")
        self.status_indicator.pack(side="left", padx=(15, 5))
        
        self.status_text = ctk.CTkLabel(self, text="Sistema Operacional", font=ctk.CTkFont(size=11))
        self.status_text.pack(side="left")
        
        # 2. Separador sutil
        ctk.CTkLabel(self, text="|", text_color="gray").pack(side="left", padx=10)
        
        # 3. Contadores
        self.log_count_lbl = ctk.CTkLabel(self, text="0 Logs Ativos", font=ctk.CTkFont(size=11, weight="bold"))
        self.log_count_lbl.pack(side="left", padx=5)
        
        self.pdv_count_lbl = ctk.CTkLabel(self, text="0 PDVs", font=ctk.CTkFont(size=11))
        self.pdv_count_lbl.pack(side="left", padx=10)
        
        # 4. Versão (Direita)
        version_lbl = ctk.CTkLabel(self, text=f"LogFácil Pro v{VERSION}", font=ctk.CTkFont(size=10), text_color="gray")
        version_lbl.pack(side="right", padx=15)

    def _on_log_count_changed(self, count):
        self.log_count_lbl.configure(text=f"{count} Logs Ativos")
        # Se houver logs abertos, muda cor do status para azul (ativa)
        color = "#3498db" if count > 0 else "#2ecc71"
        self.status_indicator.configure(fg_color=color)

    def _on_pdvs_changed(self, count):
        self.pdv_count_lbl.configure(text=f"{count} PDVs")
