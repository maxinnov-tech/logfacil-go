"""
Arquivo: gui/utils/icon_manager.py
Descrição: Gerenciador centralizado de ícones do LogFácil Pro.
Lida com o carregamento de imagens PNG e conversão para CTkImage,
suportando temas claro e escuro.
"""
import os
import sys
from PIL import Image
import customtkinter as ctk
from core.logger import logger

class IconManager:
    _instance = None
    _icons = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IconManager, cls).__new__(cls)
        return cls._instance

    @staticmethod
    def resource_path(relative_path):
        """Retorna o caminho absoluto para o recurso, funcionando para dev e PyInstaller."""
        try:
            # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    @staticmethod
    def get_icon(name, size=(20, 20)):
        """Carrega e retorna um CTkImage para o nome do ícone especificado."""
        if name in IconManager._icons:
            return IconManager._icons[name]
        
        # Caminho resolvido (suporta EXE)
        icon_path = IconManager.resource_path(os.path.join("assets", "icons", f"{name}.png"))
        
        try:
            if not os.path.exists(icon_path):
                logger.warning(f"Ícone não encontrado: {icon_path}")
                return None
            
            pil_img = Image.open(icon_path)
            # CTkImage permite definir imagens diferentes para Light/Dark
            # Por enquanto usando a mesma (PNG transparente com cor fixa)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
            
            IconManager._icons[name] = ctk_img
            return ctk_img
        except Exception as e:
            logger.error(f"Erro ao carregar ícone {name}: {e}")
            return None

# Instância global para facilitar o acesso
icons = IconManager()
