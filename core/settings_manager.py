"""
Arquivo: core/settings_manager.py
Descrição: Gerenciador de persistência de configurações do LogFácil.
Este módulo é responsável por carregar, salvar e fornecer acesso às configurações
do usuário através de um arquivo JSON local (settings.json), permitindo personalização
contínua da interface e do funcionamento da aplicação.
"""
import os
import json
from core.logger import logger

class SettingsManager:
    """Gerencia as configurações do usuário em um arquivo JSON."""
    
    def __init__(self, filename="settings.json"):
        # Localiza o arquivo na mesma pasta do executável/script (portabilidade)
        self.filepath = os.path.join(os.getcwd(), filename)
        self.settings = self._get_default_settings()
        self.load()

    def _get_default_settings(self):
        """Retorna o dicionário de configurações padrão."""
        return {
            "font_size": 13,
            "appearance_mode": "dark",
            "ui_theme": "blue"
        }

    def load(self):
        """Carrega as configurações do disco."""
        if not os.path.exists(self.filepath):
            logger.info("Arquivo de configurações não encontrado. Usando padrões.")
            self.save() # Cria o arquivo inicial
            return

        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                # Faz o merge com os padrões para garantir que novas chaves existam
                self.settings.update(loaded_settings)
                logger.info(f"Configurações carregadas de {self.filepath}")
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")

    def save(self):
        """Salva as configurações atuais no disco."""
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            logger.info("Configurações salvas com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")

    def get(self, key, default=None):
        """Busca um valor de configuração."""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Define um valor de configuração."""
        self.settings[key] = value
        self.save()
