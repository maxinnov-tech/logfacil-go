from dataclasses import dataclass
from typing import Optional

@dataclass
class PDVInfo:
    codigo: str
    id_interno: str
    nome: str
    tipo: str
    operando: bool
    serial: str
    codigo_estoque: str
    
    @property
    def tipo_descricao(self) -> str:
        tipos = {
            'M': 'PAY (Pagamento)',
            'C': 'Conveniência',
            'P': 'Apresentação/Demo',
            'E': 'Teste',
            '?': 'Desconhecido'
        }
        return tipos.get(self.tipo, 'Desconhecido')


@dataclass
class LogPDVActivity:
    pdv_idq: Optional[str] = None
    pdv_referencia: Optional[str] = None
    funcionario: Optional[str] = None
    ip: Optional[str] = None
    ultima_atividade: Optional[str] = None
    servico: str = "webPostoPayServer"
    versao_app: Optional[str] = None
