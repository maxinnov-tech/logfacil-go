"""
Arquivo: models/pdv.py
Descrição: Estrutura de Modelos de Dados (Data Models) para representar informações de PDVs.
Este arquivo define as classes em formato Dataclasses ('PDVInfo' e 'LogPDVActivity')
que mapeiam os atributos recebidos tanto do parser de Logs quanto das APIs. Ele facilita a 
passagem orientada a objetos (POO) entre os componentes internos, tipando claramente
os atributos como Código, ID Interno, Nome, Operacionalidade, versão de APP e última atividade
de um PDV de pagamento. Também formata traduções legíveis para seus diversos status.
"""
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
    ip: str = "127.0.0.1"
    
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
