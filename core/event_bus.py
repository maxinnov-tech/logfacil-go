"""
Arquivo: core/event_bus.py
Descrição: Barramento de Eventos (Event Bus) para desacoplamento de componentes.
Permite que diferentes partes da aplicação se comuniquem através de sinais
sem que precisem se conhecer diretamente, facilitando a manutenção e expansão.
"""
from collections import defaultdict
from core.logger import logger

class EventBus:
    """Implementa o padrão Pub/Sub para comunicação entre componentes."""
    
    def __init__(self):
        self._listeners = defaultdict(list)

    def subscribe(self, event_type: str, callback):
        """Inscreve um callback para um tipo de evento."""
        if callback not in self._listeners[event_type]:
            self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback):
        """Remove a inscrição de um callback."""
        if callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)

    def emit(self, event_type: str, *args, **kwargs):
        """Emite um evento para todos os inscritos."""
        try:
            for callback in self._listeners[event_type]:
                callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Erro ao emitir evento {event_type}: {e}")

# Instância global para facilitar o acesso
event_bus = EventBus()
