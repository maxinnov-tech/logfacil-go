"""
Arquivo: gui/tabs/pdv_tab.py
Descrição: Guia (Tab) de monitoria e histórico dedicada ao controle ativo de Pontos de Venda (PDV).
Diferencia-se da Log Tab visual, pois não injeta textos cruéis de debug. Em vez disso,
processa e modela visualmente os relatórios analíticos extraídos de cada terminal PDV da rede.
Utiliza tabelas de árvores (Treeview ttk) exibindo horário exato, identificadores e o Status (Ativo/Inativo) de cada maquininha.
Comporta o laço de execução persistente (daemon thread) que periodicamente atualiza os status das APIs
com as descobertas feitas no Parser, fornecendo a feature popular de "salvar histórico CSV exportado".
"""
import threading
import datetime
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from typing import List, Tuple

from core.pdv_parser import identificar_todos_pdvs_por_log
from core.config import DEFAULT_ROOT
from core.logger import logger
from models.pdv import PDVInfo

class PDVMonitorTab:
    def __init__(self, app: "App"):
        self.app = app
        self.frame = ctk.CTkFrame(app.notebook)
        self.pdv_history: List[Tuple[PDVInfo, datetime.datetime]] = []
        self.stop_event = threading.Event()
        self.pdv_monitor_active = True
        self._ultimos_pdvs = {}
        self._build_ui()
        self._iniciar_monitoramento()
    
    def _build_ui(self):
        main_frame = ctk.CTkFrame(self.frame)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(header_frame, text="📊 Monitor de PDVs - webPostoPayServer",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="#4CAF50").pack(side="left")
        
        btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_frame.pack(side="right")
        
        self.btn_clear = ctk.CTkButton(btn_frame, text="🗑️ Limpar", command=self._limpar_historico, height=35, width=100)
        self.btn_clear.pack(side="left", padx=5)
        
        self.btn_export = ctk.CTkButton(btn_frame, text="💾 Exportar", command=self._exportar_historico, height=35, width=100)
        self.btn_export.pack(side="left", padx=5)
        
        table_frame = ctk.CTkFrame(main_frame)
        table_frame.pack(fill="both", expand=True)
        
        tree_container = ctk.CTkFrame(table_frame)
        tree_container.pack(fill="both", expand=True)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=30)
        style.configure("Treeview.Heading", background="#3c3c3c", foreground="white", font=(None, 11, "bold"))
        style.map('Treeview', background=[('selected', '#4CAF50')])
        
        self.tree = ttk.Treeview(tree_container, columns=("horario", "codigo", "nome", "id_interno", "tipo", "status"),
                                  show="headings", height=15)
        
        self.tree.heading("horario", text="Horário")
        self.tree.heading("codigo", text="Código")
        self.tree.heading("nome", text="Nome")
        self.tree.heading("id_interno", text="ID Interno")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("status", text="Status")
        
        self.tree.column("horario", width=150)
        self.tree.column("codigo", width=80)
        self.tree.column("nome", width=200)
        self.tree.column("id_interno", width=100)
        self.tree.column("tipo", width=100)
        self.tree.column("status", width=80)
        
        v_scrollbar = ctk.CTkScrollbar(tree_container, command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        
        status_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        status_frame.pack(fill="x", pady=(10, 0))
        
        self.status_label = ctk.CTkLabel(status_frame, text="Monitorando PDVs...", text_color="#888888")
        self.status_label.pack(side="left")
        
        self.stats_label = ctk.CTkLabel(status_frame, text="Total: 0", text_color="#888888")
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
                pasta_log = self.app.entry.get().strip() or DEFAULT_ROOT
                pdvs, mensagem = identificar_todos_pdvs_por_log(pasta_log)
                hora_atual = datetime.datetime.now()
                
                for pdv in pdvs:
                    chave = f"{pdv.codigo}_{pdv.id_interno}"
                    if chave not in self._ultimos_pdvs:
                        self._ultimos_pdvs[chave] = pdv
                        self.pdv_history.append((pdv, hora_atual))
                        if len(self.pdv_history) > 200:
                            self.pdv_history.pop(0)
                        self.frame.after(0, lambda p=pdv, h=hora_atual: self._atualizar_tabela(p, h))
                
                if pdvs:
                    self.frame.after(0, lambda: self.status_label.configure(text=f"✅ {len(pdvs)} PDV(s) ativo(s)", text_color="#4CAF50"))
                    self.frame.after(3000, lambda: self.status_label.configure(text="Monitorando PDVs...", text_color="#888888"))
                
                total_pdvs = len(set((p.codigo, p.id_interno) for p, _ in self.pdv_history))
                self.frame.after(0, lambda: self.stats_label.configure(text=f"Total: {total_pdvs}"))
                
            except Exception as e:
                logger.error(f"Erro na identificação de PDVs: {e}")
        
        threading.Thread(target=thread_identify, daemon=True).start()
    
    def _atualizar_tabela(self, pdv: PDVInfo, horario: datetime.datetime):
        horario_str = horario.strftime("%H:%M:%S")
        status = "✅ Ativo" if pdv.operando else "⚠️ Inativo"
        tipo_map = {'M': 'Pagamento', 'C': 'Conveniência', 'P': 'Apresentação', 'E': 'Teste'}
        tipo_str = tipo_map.get(pdv.tipo, pdv.tipo)
        try:
            self.tree.insert("", 0, values=(horario_str, pdv.codigo, pdv.nome, pdv.id_interno, tipo_str, status))
        except Exception:
            pass # Ignora erros de thread em encerramento
    
    def _limpar_historico(self):
        self.pdv_history.clear()
        self._ultimos_pdvs.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.stats_label.configure(text="Total: 0")
    
    def _exportar_historico(self):
        if not self.pdv_history:
            messagebox.showwarning("Aviso", "Nenhum dado para exportar!")
            return
        
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8-sig') as f:
                    f.write("Horário;Código;Nome;ID Interno;Tipo;Status\n")
                    for pdv, horario in self.pdv_history:
                        status = "Ativo" if pdv.operando else "Inativo"
                        f.write(f"{horario.strftime('%H:%M:%S')};{pdv.codigo};{pdv.nome};{pdv.id_interno};{pdv.tipo};{status}\n")
                messagebox.showinfo("Sucesso", f"Exportado para:\n{filename}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao exportar: {e}")
                logger.error(f"Erro ao exportar PDVs: {e}")
    
    def parar_monitoramento(self):
        self.pdv_monitor_active = False
