"""
Arquivo: gui/dialogs/settings_dialog.py
Descrição: Janela de configurações (Toplevel) do LogFácil.
Permite ao usuário ajustar preferências visuais e funcionais, como o tamanho 
da fonte dos logs, modo de aparência e outros parâmetros que são salvos
automaticamente via SettingsManager.
"""
import customtkinter as ctk

class SettingsDialog(ctk.CTkToplevel):
    """Diálogo de configurações do sistema."""
    
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.settings = app.settings
        
        self.title("⚙️ Configurações - LogFácil")
        self.resizable(False, False)
        
        # Build UI first
        self._build_ui()
        
        # Force redraw before showing/grabbing
        self.update()
        
        # Now calculate geometry and center
        w, h = 450, 350
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        
        self.lift()
        self.focus_force()
        
        # Use after to ensure everything is mapped before grabbing focus
        self.after(100, self.grab_set)

    def _build_ui(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=25, pady=25)
        
        ctk.CTkLabel(main, text="⚙️ Preferências", 
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(0, 20))
        
        # --- Seção: Log ---
        ctk.CTkLabel(main, text="Visualização de Logs", 
                     font=ctk.CTkFont(size=14, weight="bold"), text_color="#4CAF50").pack(anchor="w", pady=(10, 5))
        
        font_frame = ctk.CTkFrame(main, fg_color="transparent")
        font_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(font_frame, text="Tamanho da fonte:").pack(side="left")
        
        current_font = self.settings.get("font_size", 13)
        self.font_curr_lbl = ctk.CTkLabel(font_frame, text=str(current_font), 
                                         font=ctk.CTkFont(weight="bold"), width=30)
        self.font_curr_lbl.pack(side="right", padx=5)
        
        self.font_slider = ctk.CTkSlider(font_frame, from_=8, to_=24, number_of_steps=16,
                                         command=self._on_font_change)
        self.font_slider.set(current_font)
        self.font_slider.pack(side="right", fill="x", expand=True, padx=10)
        
        # Separador
        ctk.CTkFrame(main, height=2, fg_color="#333333").pack(fill="x", pady=20)
        
        # Botões
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x")
        
        ctk.CTkButton(btn_frame, text="Salvar e Aplicar", command=self._save,
                      fg_color="#4CAF50", hover_color="#45a049").pack(side="right", padx=5)
        
        ctk.CTkButton(btn_frame, text="Cancelar", command=self.destroy,
                      fg_color="#6c757d", hover_color="#5a6268").pack(side="right", padx=5)

    def _on_font_change(self, value):
        val = int(value)
        self.font_curr_lbl.configure(text=str(val))

    def _save(self):
        new_font = int(self.font_slider.get())
        self.settings.set("font_size", new_font)
        
        # Aplica na aplicação principal se o método existir
        if hasattr(self.app, 'apply_settings'):
            self.app.apply_settings()
            
        self.destroy()
