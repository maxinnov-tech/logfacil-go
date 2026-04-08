import os
import sys
import threading
import subprocess
from tkinter import messagebox
import customtkinter as ctk

from core.github_updater import GitHubUpdater

class UpdateDialog(ctk.CTkToplevel):
    """Diálogo de atualização."""
    
    def __init__(self, parent, updater: GitHubUpdater):
        super().__init__(parent)
        self.updater = updater
        self.parent = parent
        self.downloaded_file = None
        self.cancelled = False
        
        self.title("Atualização do LogFácil")
        self.geometry("500x450")
        self.resizable(False, False)
        
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.winfo_screenheight() // 2) - (450 // 2)
        self.geometry(f"+{x}+{y}")
        
        self._criar_widgets()
        self.lift()
        self.focus_force()
        self.grab_set()
        
        self.after(100, self._verificar)
    
    def _criar_widgets(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main, text="🔄 Atualização Automática",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 15))
        
        info = ctk.CTkFrame(main)
        info.pack(fill="x", pady=5)
        
        ctk.CTkLabel(info, text=f"📌 Versão instalada: {self.updater.current_version}",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=5)
        
        self.lbl_nova = ctk.CTkLabel(info, text="🔍 Verificando...",
                                      font=ctk.CTkFont(size=12), text_color="#FFA500")
        self.lbl_nova.pack(anchor="w", padx=10, pady=5)
        
        app_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
        ctk.CTkLabel(main, text=f"📁 Pasta: {os.path.dirname(app_path)}",
                     font=ctk.CTkFont(size=11), text_color="#888888").pack(anchor="w", pady=5)
        
        ctk.CTkLabel(main, text="📝 Novidades:",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(15, 5))
        
        self.txt_notas = ctk.CTkTextbox(main, height=120, wrap="word")
        self.txt_notas.pack(fill="both", expand=True, pady=(0, 10))
        self.txt_notas.insert("1.0", "Aguardando verificação...")
        self.txt_notas.configure(state="disabled")
        
        self.progress_frame = ctk.CTkFrame(main, fg_color="transparent")
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=400)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)
        
        self.lbl_progresso = ctk.CTkLabel(self.progress_frame, text="0%", font=ctk.CTkFont(size=11))
        self.lbl_progresso.pack()
        
        self.lbl_status = ctk.CTkLabel(main, text="", font=ctk.CTkFont(size=11), text_color="#888888")
        self.lbl_status.pack(pady=5)
        
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        
        self.btn_cancelar = ctk.CTkButton(btn_frame, text="Cancelar", command=self.cancelar,
                                          fg_color="#6c757d", hover_color="#5a6268", width=100)
        self.btn_cancelar.pack(side="right", padx=5)
        
        self.btn_acao = ctk.CTkButton(btn_frame, text="Verificando...", state="disabled", width=150)
        self.btn_acao.pack(side="right", padx=5)
    
    def _verificar(self):
        def check():
            tem_update, versao, url = self.updater.check_for_updates()
            self.after(0, lambda: self._resultado(tem_update, versao))
        
        threading.Thread(target=check, daemon=True).start()
    
    def _resultado(self, tem_update: bool, versao: str):
        if tem_update:
            self.lbl_nova.configure(text=f"✅ Nova versão disponível: {versao}", text_color="#4CAF50")
            self.txt_notas.configure(state="normal")
            self.txt_notas.delete("1.0", "end")
            self.txt_notas.insert("1.0", self.updater.release_notes or "Sem notas disponíveis.")
            self.txt_notas.configure(state="disabled")
            self.btn_acao.configure(text="⬇️ Baixar Atualização", command=self._baixar, state="normal")
            self.lbl_status.configure(text="Pronto para baixar!")
        else:
            self.lbl_nova.configure(text="✅ Você já está na versão mais recente!", text_color="#4CAF50")
            self.txt_notas.configure(state="normal")
            self.txt_notas.delete("1.0", "end")
            self.txt_notas.insert("1.0", "Seu LogFácil está atualizado.")
            self.txt_notas.configure(state="disabled")
            self.btn_acao.configure(text="OK", command=self.destroy, state="normal")
            self.lbl_status.configure(text="Sistema atualizado!")
    
    def _baixar(self):
        self.btn_acao.configure(state="disabled", text="Baixando...")
        self.progress_frame.pack(fill="x", pady=10)
        
        def progresso(p, b, t):
            self.after(0, lambda: self._atualizar_progresso(p, b, t))
        
        def baixar():
            arquivo = self.updater.download_update(progress_callback=progresso)
            if arquivo and not self.cancelled:
                self.downloaded_file = arquivo
                self.after(0, self._download_ok)
            elif not self.cancelled:
                self.after(0, self._download_erro)
        
        threading.Thread(target=baixar, daemon=True).start()
    
    def _atualizar_progresso(self, percent, baixado, total):
        self.progress_bar.set(percent / 100)
        self.lbl_progresso.configure(text=f"{percent}%")
        if total > 1024 * 1024:
            texto = f"{baixado / (1024*1024):.1f} / {total / (1024*1024):.1f} MB"
        else:
            texto = f"{baixado / 1024:.1f} / {total / 1024:.1f} KB"
        self.lbl_status.configure(text=f"Baixando: {texto}")
    
    def _download_ok(self):
        self.lbl_progresso.configure(text="100% - Download concluído!")
        self.lbl_status.configure(text="✅ Download concluído! Pronto para instalar.")
        self.btn_acao.configure(text="🚀 Instalar Agora", command=self._instalar, state="normal")
        self.btn_cancelar.configure(text="Fechar")
    
    def _download_erro(self):
        self.lbl_status.configure(text="❌ Erro no download. Verifique sua conexão.")
        self.btn_acao.configure(text="⬇️ Tentar Novamente", command=self._baixar, state="normal")
    
    def _instalar(self):
        if not self.downloaded_file:
            messagebox.showerror("Erro", "Arquivo de atualização não encontrado!")
            return
        
        app_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
        
        resposta = messagebox.askyesno(
            "Confirmar Instalação",
            f"A atualização será instalada em:\n\n{os.path.dirname(app_path)}\n\n"
            f"O LogFácil será fechado e reiniciado automaticamente.\n\nDeseja continuar?"
        )
        
        if resposta:
            updater_script = self._criar_script_python(app_path)
            if updater_script:
                try:
                    subprocess.Popen(
                        [sys.executable, updater_script],
                        creationflags=subprocess.DETACHED_PROCESS if os.name == 'nt' else 0,
                        close_fds=True
                    )
                    self.parent.quit()
                except Exception as e:
                    messagebox.showerror("Erro", f"Falha ao iniciar atualização: {e}")

    def _criar_script_python(self, app_path):
        """Cria um script Python temporário para substituir o executável."""
        try:
            import tempfile
            
            script_content = f'''import os
import sys
import time
import shutil
import subprocess

def main():
    app_path = r"{app_path}"
    new_file = r"{self.downloaded_file}"
    app_dir = os.path.dirname(app_path)
    
    # Aguardar o processo principal fechar
    time.sleep(3)
    
    # Forçar encerramento se ainda estiver rodando
    app_name = os.path.basename(app_path)
    try:
        subprocess.run(["taskkill", "/F", "/IM", app_name], capture_output=True, timeout=5)
    except:
        pass
    
    # Desbloquear arquivo baixado (caso venha da internet)
    try:
        subprocess.run(["powershell", "-Command", f"Unblock-File -Path '{{new_file}}'"], 
                       capture_output=True, timeout=10)
    except:
        pass
    
    # Fazer backup
    backup_path = app_path + ".backup"
    if os.path.exists(app_path):
        try:
            shutil.move(app_path, backup_path)
        except Exception as e:
            print(f"Erro ao renomear: {{e}}")
            return
    
    # Copiar novo executável
    try:
        shutil.copy2(new_file, app_path)
    except Exception as e:
        print(f"Erro ao copiar: {{e}}")
        # Restaurar backup
        if os.path.exists(backup_path):
            shutil.move(backup_path, app_path)
        return
    
    # Remover backup e arquivo baixado
    try:
        if os.path.exists(backup_path):
            os.remove(backup_path)
        if os.path.exists(new_file):
            os.remove(new_file)
    except:
        pass
    
    # Iniciar nova versão usando os.startfile (mais confiável que subprocess)
    try:
        os.startfile(app_path)
    except:
        # Fallback
        subprocess.Popen([app_path], cwd=app_dir)
    
    # Remover este script
    try:
        os.remove(__file__)
    except:
        pass

if __name__ == "__main__":
    main()
'''
            # Salvar script temporário
            script_path = os.path.join(tempfile.gettempdir(), f"logfacil_updater_{os.getpid()}.py")
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            return script_path
        except Exception as e:
            print(f"Erro ao criar script Python: {e}")
            return None    
    
    def cancelar(self):
        self.cancelled = True
        self.destroy()
