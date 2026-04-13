"""
Arquivo: gui/tabs/pdv_tab.py
Descrição: Guia (Tab) Pro de monitoramento de PDVs.
Mantém o rastreamento em tempo real de terminais logados no webPostoPayServer,
emite eventos de atualização para o Dashboard e gerencia o histórico de sessões.
"""
import threading
import datetime
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from gui.utils.icon_manager import icons
from typing import List, Tuple

from core.pdv_parser import identificar_todos_pdvs_por_log
from core.config import DEFAULT_ROOT
from core.logger import logger
from core.event_bus import event_bus
from models.pdv import PDVInfo

class PDVMonitorTab:
    """Monitor de PDVs Ativos com visual moderno."""
    
    def __init__(self, app):
        self.app = app
        self.pdv_history: List[Tuple[PDVInfo, datetime.datetime]] = []
        self.stop_event = threading.Event()
        self.pdv_monitor_active = True
        self._ultimos_pdvs = {}
        
        self.frame = ctk.CTkFrame(app.main_container, fg_color="transparent")
        self._build_ui()
        self._iniciar_monitoramento()
    
    def _build_ui(self):
        # Header Pro
        self.header = ctk.CTkFrame(self.frame, height=50, corner_radius=10, fg_color=("#dbdbdb", "#2b2b2b"))
        self.header.pack(side="top", fill="x", padx=10, pady=(5, 10))
        self.header.pack_propagate(False)
        
        ctk.CTkLabel(self.header, text="Atividade de PDVs - webPostoPay", compound="left", image=icons.get_icon("bar-chart"),
                     font=ctk.CTkFont(size=14, weight="bold"), text_color="#3498db").pack(side="left", padx=15)
        
        btn_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        btn_frame.pack(side="right", padx=10)
        
        ctk.CTkButton(btn_frame, text="Limpar", compound="left", image=icons.get_icon("trash"), command=self._limpar_historico, height=28, width=80).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Exportar", compound="left", image=icons.get_icon("save"), command=self._exportar_historico, height=28, width=80, fg_color="#3498db").pack(side="left", padx=5)
        
        # Tabela (Treeview)
        table_container = ctk.CTkFrame(self.frame, corner_radius=12)
        table_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        style = ttk.Style()
        style.theme_use('clam')
        # Ajuste adaptativo para o Treeview (Ttk é limitado, usamos cores neutras)
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=32, borderwidth=0)
        style.configure("Treeview.Heading", background="#3c3c3c", foreground="white", font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map('Treeview', background=[('selected', '#3498db')])
        
        self.tree = ttk.Treeview(table_container, columns=("horario", "codigo", "nome", "id_interno", "tipo", "status"),
                                  show="headings")
        
        cols = {"horario": "Horário", "codigo": "Cod", "nome": "Nome Terminal", "id_interno": "ID Interno", "tipo": "Tipo", "status": "Status"}
        for k, v in cols.items():
            self.tree.heading(k, text=v)
            self.tree.column(k, anchor="center", width=100)
        self.tree.column("nome", width=250, anchor="w")
        
        sb = ctk.CTkScrollbar(table_container, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        sb.pack(side="right", fill="y", padx=5, pady=10)
        
        # Footer de Status
        self.status_bar = ctk.CTkFrame(self.frame, height=30, fg_color="transparent")
        self.status_bar.pack(side="bottom", fill="x", padx=15)
        
        self.status_label = ctk.CTkLabel(self.status_bar, text="🟢 Monitorando atividade...", text_color="gray", font=ctk.CTkFont(size=11))
        self.status_label.pack(side="left")
        
        self.stats_label = ctk.CTkLabel(self.status_bar, text="PDVs Ativos: 0", text_color="#3498db", font=ctk.CTkFont(size=11, weight="bold"))
        self.stats_label.pack(side="right")
    
    def _iniciar_monitoramento(self):
        self._identificar_todos_pdvs()
        self._agendar_proxima_verificacao()
    
    def _agendar_proxima_verificacao(self):
        if self.pdv_monitor_active:
            self.frame.after(30000, self._verificar_pdvs_periodicamente)
    
    def _verificar_pdvs_periodicamente(self):
        if self.pdv_monitor_active:
            self._identificar_todos_pdvs()
            self._agendar_proxima_verificacao()
    
    def _identificar_todos_pdvs(self):
        def thread_identify():
            try:
                pasta_log = self.app.settings.get("last_folder") or DEFAULT_ROOT
                if not pasta_log: return
                
                pdvs, _ = identificar_todos_pdvs_por_log(pasta_log)
                hora_atual = datetime.datetime.now()
                
                for pdv in pdvs:
                    chave = f"{pdv.codigo}_{pdv.id_interno}"
                    if chave not in self._ultimos_pdvs:
                        self._ultimos_pdvs[chave] = pdv
                        self.pdv_history.append((pdv, hora_atual))
                        self.frame.after(0, lambda p=pdv, h=hora_atual: self._atualizar_tabela(p, h))
                
                # Emite evento para o Dashboard
                event_bus.emit("pdv_updated", len(pdvs))
                self.frame.after(0, lambda: self.stats_label.configure(text=f"PDVs Ativos: {len(pdvs)}"))
                
            except Exception as e:
                logger.error(f"Erro na identificação de PDVs: {e}")
        
        threading.Thread(target=thread_identify, daemon=True).start()
    
    def _atualizar_tabela(self, pdv: PDVInfo, horario: datetime.datetime):
        horario_str = horario.strftime("%H:%M:%S")
        status = "Ativo"
        tipo_map = {'M': 'Pagamento', 'C': 'Conveniência', 'P': 'Apresentação', 'E': 'Teste'}
        try:
            self.tree.insert("", 0, values=(horario_str, pdv.codigo, pdv.nome, pdv.id_interno, tipo_map.get(pdv.tipo, pdv.tipo), status))
        except: pass
    
    def _limpar_historico(self):
        self.pdv_history.clear()
        self._ultimos_pdvs.clear()
        for item in self.tree.get_children(): self.tree.delete(item)
        self.stats_label.configure(text="PDVs Ativos: 0")
        event_bus.emit("pdv_updated", 0)
    
    def _exportar_historico(self):
        if not self.pdv_history: return
        fn = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if fn:
            try:
                with open(fn, 'w', encoding='utf-8-sig') as f:
                    f.write("Horário;Código;Nome;ID Interno;Tipo;Status\n")
                    for p, h in self.pdv_history:
                        f.write(f"{h.strftime('%H:%M:%S')};{p.codigo};{p.nome};{p.id_interno};{p.tipo};Operando\n")
            except Exception as e:
                logger.error(f"Erro ao exportar: {e}")
    
    def parar_monitoramento(self):
        self.pdv_monitor_active = False
