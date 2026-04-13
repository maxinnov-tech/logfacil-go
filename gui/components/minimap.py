"""
Arquivo: gui/components/minimap.py
Descrição: Componente visual de minimapa para navegação rápida em logs.
Sincroniza com um CTkTextbox e destaca áreas com erros ou avisos.
"""
import tkinter as tk
import customtkinter as ctk

class LogMinimap(tk.Canvas):
    def __init__(self, parent, text_widget, width=30, **kwargs):
        # Determina cor de fundo baseada no tema do parent (CTkFrame)
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#1a1a1a" if is_dark else "#dbdbdb"
        
        super().__init__(parent, width=width, highlightthickness=0, bg=bg_color, **kwargs)
        self.text_widget = text_widget
        self.width = width
        
        # Cores (Sincronizadas com LogTab)
        self.colors = {
            "ERROR": "#ff4d4d",
            "WARN": "#ffa500",
            "CUSTOM_HL": "#3498db",
            "slider": "#444" if is_dark else "#bbb"
        }
        
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_click)
        
        # Agendamento de atualização periódica
        self._refresh()

    def _on_click(self, event):
        """Pula para a posição correspondente no texto ao clicar no minimapa."""
        try:
            height = self.winfo_height()
            if height <= 5: return
            fraction = event.y / height
            self.text_widget.yview_moveto(max(0, min(1, fraction)))
        except: pass

    def _refresh(self):
        """Atualiza o desenho do minimapa."""
        if not self.winfo_ismapped():
            self.after(1000, self._refresh)
            return

        try:
            self.delete("all")
            height = self.winfo_height()
            
            # Atualiza cor de fundo se o tema mudar
            is_dark = ctk.get_appearance_mode() == "Dark"
            self.configure(bg="#1a1a1a" if is_dark else "#dbdbdb")

            # 1. Desenha o "Slider" (área visível)
            top, bottom = self.text_widget.yview()
            self.create_rectangle(0, top * height, self.width, bottom * height, 
                                  fill=self.colors["slider"], outline="")

            # 2. Desenha Marks de Erro/Aviso
            total_lines_str = self.text_widget.index("end-1c").split(".")[0]
            total_lines = int(total_lines_str) if total_lines_str.isdigit() else 0
            
            if total_lines > 0:
                self._draw_tag_marks("ERROR", self.colors["ERROR"], total_lines, height)
                self._draw_tag_marks("WARN", self.colors["WARN"], total_lines, height)
                if self.text_widget.tag_ranges("CUSTOM_HL"):
                    self._draw_tag_marks("CUSTOM_HL", self.colors["CUSTOM_HL"], total_lines, height)
                
                # Procura por marcadores customizados conhecidos dinamicamente a partir das tags do widget raiz
                for tag in self.text_widget.tag_names():
                    if tag not in ["ERROR", "WARN", "INFO", "DEBUG", "CUSTOM_HL", "sel"]:
                        # Tenta pegar a cor da tag (fg)
                        try:
                            # tag_cget pode retornar exceção se a opção não existir, mas "foreground" geralmente existe pra essas
                            fg = self.text_widget.tag_cget(tag, "foreground")
                            if fg and self.text_widget.tag_ranges(tag):
                                self._draw_tag_marks(tag, fg, total_lines, height)
                        except: pass
        except Exception as e:
            # Silencioso para não travar a UI
            pass

        self.after(500, self._refresh)

    def _draw_tag_marks(self, tag_name, color, total_lines, canvas_height):
        """Desenha pequenos traços onde a tag existe."""
        pos = "1.0"
        # Limite de segurança para não travar a UI
        count = 0
        while count < 100:
            pos = self.text_widget.tag_nextrange(tag_name, pos)
            if not pos: break
            
            line_num = int(pos[0].split(".")[0])
            y = (line_num / total_lines) * canvas_height
            self.create_line(5, y, self.width - 5, y, fill=color, width=2)
            
            pos = pos[1]
            count += 1
