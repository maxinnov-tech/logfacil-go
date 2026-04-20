"""
Arquivo: gui/managers/global_search.py
Descrição: Gerenciador de Busca Global.
Permite pesquisar termos em todas as abas de log abertas simultaneamente,
facilitando o rastreamento de erros que cruzam múltiplos serviços.
"""
import customtkinter as ctk
from gui.utils.icon_manager import icons

class GlobalSearch(ctk.CTkToplevel):
    """Diálogo de Busca Global Pro."""
    
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("🔍 Busca Global - LogFácil Pro")
        self.geometry("800x500")
        self.after(10, self.lift)
        self.after(10, self.focus_force)
        
        self._build_ui()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, height=80, fg_color=("#dbdbdb", "#2b2b2b"))
        header.pack(fill="x", padx=15, pady=15)
        header.pack_propagate(False)
        
        self.entry = ctk.CTkEntry(header, placeholder_text="Digite o que deseja buscar em TODOS os logs...", 
                                  width=600, height=35)
        self.entry.pack(side="left", padx=20, pady=20)
        self.entry.bind("<Return>", lambda e: self._do_search())
        
        ctk.CTkButton(header, text="Buscar", compound="left", image=icons.get_icon("search"), width=100, command=self._do_search,
                      fg_color="#3498db", hover_color="#2980b9").pack(side="left", padx=5)

        # Results Area
        self.results_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.results_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.status_lbl = ctk.CTkLabel(self, text="Dica: Pressione Enter para buscar.", text_color="gray")
        self.status_lbl.pack(pady=5)

    def _do_search(self):
        query = self.entry.get().strip()
        if not query: return
        
        # Limpa resultados anteriores
        for child in self.results_frame.winfo_children():
            child.destroy()
            
        hits = 0
        self.status_lbl.configure(text="Buscando...")
        self.update()
        
        for path, tab in self.app.open_tabs.items():
            content = tab.text.get("1.0", "end")
            lines = content.splitlines()
            
            for i, line in enumerate(lines):
                if query.lower() in line.lower():
                    hits += 1
                    self._add_result_row(tab.service_name, i+1, line.strip()[:100], query)
                    if hits >= 50: break # Limite por busca
            if hits >= 50: break

        self.status_lbl.configure(text=f"Fim da busca: {hits} ocorrências encontradas." if hits > 0 else "Nenhum resultado encontrado.")

    def _add_result_row(self, service, line_num, snippet, query):
        row = ctk.CTkFrame(self.results_frame, fg_color=("#ebebeb", "#333333"), corner_radius=8)
        row.pack(fill="x", pady=2, padx=5)
        
        ctk.CTkLabel(row, text=f"[{service}]", font=ctk.CTkFont(weight="bold", size=12), text_color="#3498db", width=120).pack(side="left", padx=10)
        ctk.CTkLabel(row, text=f"Linha {line_num}:", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")
        
        # Snippet com destaque (simplificado)
        ctk.CTkLabel(row, text=snippet, font=ctk.CTkFont(family="Consolas", size=11), anchor="w").pack(side="left", fill="x", expand=True, padx=10)
        
        # Botão para ir até lá
        ctk.CTkButton(row, text="Ir", width=40, height=24, fg_color="#555", 
                      command=lambda s=service, l=line_num: self._go_to(s, l)).pack(side="right", padx=10)

    def _go_to(self, service, line_num):
        # 1. Muda para a aba de logs
        from core.event_bus import event_bus
        event_bus.emit("navigate", "logs")
        
        # 2. Seleciona a aba específica do serviço
        self.app.log_container.set(service)
        
        # 3. Faz scroll até a linha
        tab = None
        for t in self.app.open_tabs.values():
            if t.service_name == service:
                tab = t
                break
        
        if tab:
            tab.text.see(f"{line_num}.0")
            tab.text.tag_add("search_hit", f"{line_num}.0", f"{line_num}.end")
            tab.text.tag_config("search_hit", background="#3498db", foreground="white")
            # Auto-pauza para o usuário ler
            if tab.follow:
                tab.toggle_follow()
        
        self.destroy()
