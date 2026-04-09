"""
Arquivo: core/logger.py
Descrição: Configuração global para registro (logging) de eventos da aplicação.
Este arquivo define um logger configurado para gravar eventos de erro, alertas e informações
importantes do sistema em arquivos de texto rotativos e também de exibi-los no console.
Os logs do próprio LogFácil são armazenados em um subdiretório na pasta temporária do sistema
(ex. C:\\temp\\LogFacil) e seguem um controle de tamanho máximo, guardando o histórico das
últimas execuções. Isso é crucial para diagnóstico e rastreabilidade de falhas internas da ferramenta.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging() -> logging.Logger:
    """Configura o sistema de logging da aplicação."""
    temp_dir = os.environ.get('TEMP', os.environ.get('TMP', r'C:\temp'))
    log_dir = os.path.join(temp_dir, "LogFacil")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"logfacil_{datetime.now().strftime('%Y%m%d')}.log")
    
    logger = logging.getLogger('LogFacil')
    
    # Previne que múltiplos handlers sejam adicionados se for chamado mais de uma vez
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler de arquivo rotativo (máximo 5MB, rotaciona até 5 vezes)
        try:
            file_handler = RotatingFileHandler(
                log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Não foi possível configurar Rotate File Logging: {e}")
            
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

# Instância global do logger
logger = setup_logging()
