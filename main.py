import os
from tkinter import messagebox

from core.os_services import is_admin, run_as_admin
from core.config import VERSION
from gui.app import App

def main():
    if os.name == "nt" and not is_admin():
        import tkinter as tk
        root = tk.Tk()
        root.withdraw() # hide root
        resposta = messagebox.askyesno(
            "Privilégios de Administrador",
            "Este programa precisa de privilégios de administrador para:\n"
            "• Reiniciar serviços Windows\n"
            "• Finalizar processos\n\n"
            "Deseja reiniciar como Administrador?"
        )
        root.destroy()
        
        if resposta:
            run_as_admin()
        else:
            app = App()
            app.root.title(f"LogFácil v{VERSION} [MODO RESTRITO]")
            app.run()
    else:
        App().run()


if __name__ == "__main__":
    main()
