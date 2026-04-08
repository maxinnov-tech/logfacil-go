import sys
import threading
from tkinter import messagebox

from core.github_updater import GitHubUpdater
from core.config import GITHUB_REPO, GITHUB_BRANCH, CURRENT_VERSION
from gui.dialogs.update_dialog import UpdateDialog

class AutoUpdateManager:
    """Gerenciador de atualizações automáticas."""
    
    def __init__(self, app):
        self.app = app
        self.updater = GitHubUpdater(GITHUB_REPO, CURRENT_VERSION, GITHUB_BRANCH)
    
    def check_updates_silent(self):
        """Verifica atualizações silenciosamente."""
        # Trava: Não rodar se estiver no modo desenvolvedor (código fonte Python)
        if not getattr(sys, 'frozen', False):
            return
            
        def check():
            tem_update, versao, _ = self.updater.check_for_updates()
            if tem_update:
                self.app.root.after(0, lambda: self._notificar(versao))
        
        threading.Thread(target=check, daemon=True).start()
    
    def _notificar(self, versao: str):
        resposta = messagebox.askyesno(
            "Atualização Disponível",
            f"Uma nova versão do LogFácil está disponível!\n\n"
            f"Versão atual: {CURRENT_VERSION}\n"
            f"Nova versão: {versao}\n\n"
            f"Deseja baixar e instalar agora?"
        )
        if resposta:
            self.show_update_dialog()
    
    def show_update_dialog(self):
        UpdateDialog(self.app.root, self.updater)
    
    def check_and_update(self):
        """Verifica atualizações manualmente."""
        if not getattr(sys, 'frozen', False):
            messagebox.showinfo("Modo Desenvolvedor", "A atualização automática está desativada rodando via código fonte.\nCompile para .exe se quiser testar a atualização.")
            return

        def check():
            tem_update, _, _ = self.updater.check_for_updates()
            if tem_update:
                self.app.root.after(0, self.show_update_dialog)
            else:
                self.app.root.after(0, lambda: messagebox.showinfo(
                    "Atualização",
                    f"✅ Você já está na versão mais recente!\n\nVersão: {CURRENT_VERSION}"
                ))
        
        threading.Thread(target=check, daemon=True).start()
