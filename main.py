"""
Arquivo: main.py
Descrição: Ponto de entrada (entry point) da aplicação LogFácil.
Este arquivo é responsável por iniciar a aplicação, garantindo que o programa 
tenha os privilégios de administrador necessários (no ambiente Windows) para
gerenciar processos e serviços de sistema. Caso os privilégios não estejam
presentes, ele exibe uma caixa de diálogo solicitando reinicialização com elevação de privilégios.
Uma vez com as permissões corretas (ou caso o usuário opte por continuar sem elas),
ele inicializa e executa a interface gráfica (GUI) principal (App).
"""
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
