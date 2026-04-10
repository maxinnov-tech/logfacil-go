"""
Arquivo: gui/components/navigation.py
Descrição: Barra lateral de navegação (Sidebar) do LogFácil Pro v2.
Sidebar fixa no modo ícones com tooltip elegante ao passar o mouse.
"""
import tkinter as tk
import customtkinter as ctk
from gui.utils.icon_manager import icons
from core.config import VERSION

SIDEBAR_WIDTH = 60


class Tooltip:
    """Tooltip flutuante que aparece ao lado do widget alvo."""

    def __init__(self):
        self._window = None

    def show(self, widget: tk.Widget, text: str):
        """Exibe o tooltip ao lado direito do widget."""
        self.hide()

        # Posição: à direita do widget, verticalmente centralizado
        x = widget.winfo_rootx() + widget.winfo_width() + 6
        y = widget.winfo_rooty() + (widget.winfo_height() // 2) - 16

        self._window = tk.Toplevel()
        self._window.wm_overrideredirect(True)         # Sem borda / decoração
        self._window.wm_attributes("-topmost", True)   # Sempre no topo
        self._window.wm_geometry(f"+{x}+{y}")

        lbl = tk.Label(
            self._window,
            text=f"  {text}  ",
            bg="#3498db",
            fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=8, pady=6,
            relief="flat",
            bd=0,
        )
        lbl.pack()

    def hide(self):
        """Destrói o tooltip se estiver visível."""
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None


class Sidebar(ctk.CTkFrame):
    """Barra lateral fixa (modo ícones) com tooltips ao passar o mouse."""

    def __init__(self, parent, on_change_callback):
        super().__init__(parent, width=SIDEBAR_WIDTH, corner_radius=0)
        self.pack_propagate(False)   # Respeita a largura fixa

        self.on_change  = on_change_callback
        self.active_btn = None
        self.buttons    = {}
        self._tooltip   = Tooltip()

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  Construção da UI                                                    #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # Espaço superior para alinhar com a altura do header da App
        ctk.CTkFrame(self, height=10, fg_color="transparent").pack(fill="x")

        # Botões de Navegação principais
        self._add_nav_btn("DASHBOARD", "dashboard", icon_name="dashboard")
        self._add_nav_btn("LOGS",      "logs",      icon_name="logs")
        self._add_nav_btn("PDVs",      "pdvs",      icon_name="pdv")

        # Espaçamento flexível (empurra Configurações para baixo)
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # Botão de Configurações no rodapé
        self._add_nav_btn("Configurações", "settings", icon_name="settings")


    def _add_nav_btn(self, label: str, view_id: str, icon_name: str = None):
        icon_obj = icons.get_icon(icon_name) if icon_name else None

        btn = ctk.CTkButton(
            self,
            text="",                    # Apenas ícone — sem texto
            image=icon_obj,
            width=SIDEBAR_WIDTH - 10,
            height=44,
            corner_radius=10,
            fg_color="transparent",
            hover_color=("#e5e5e5", "#2d2d2d"),
            text_color=("#444444", "#cccccc"),
            command=lambda v=view_id: self._on_btn_click(v),
        )
        btn.pack(pady=3, padx=5)
        self.buttons[view_id] = btn

        # Tooltip ao passar o mouse
        btn.bind("<Enter>", lambda e, w=btn, t=label: self._tooltip.show(w, t))
        btn.bind("<Leave>", lambda e: self._tooltip.hide())

        # Seleciona "logs" como ativo por padrão
        if not self.active_btn and view_id == "logs":
            self._on_btn_click(view_id)

    # ------------------------------------------------------------------ #
    #  Navegação                                                           #
    # ------------------------------------------------------------------ #

    def _on_btn_click(self, view_id: str):
        self._tooltip.hide()  # Fecha tooltip ao clicar

        if self.active_btn and self.active_btn in self.buttons:
            self.buttons[self.active_btn].configure(
                fg_color="transparent", text_color=("black", "white")
            )
        self.active_btn = view_id
        self.buttons[view_id].configure(
            fg_color=("#dce8f5", "#1e3a5f"), text_color=("#3498db", "#3498db")
        )
        if self.on_change:
            self.on_change(view_id)

    def select(self, view_id: str):
        if view_id in self.buttons:
            self._on_btn_click(view_id)
