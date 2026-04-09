"""
Arquivo: core/pdv_parser.py
Descrição: Processador e extrator de informações de PDVs a partir de arquivos de log.
Este arquivo concentra toda a lógica de negócio responsável por ler nativamente os
arquivos de log (especialmente do serviço webPostoPayServer) em busca de atividades
e detalhes dos PDVs (Ponto de Venda). Ele usa expressões regulares (Regex) para varrer
os logs extraindo IDQ, nome, versão, IP e última atividade de cada PDV contido ali.
Além disso, ele cruza os dados encontrados na leitura textual dos Logs com os
dados oficiais da API do concentrador (webPostoLocal), criando um relatório consolidado.
"""
import re
import os
import xml.etree.ElementTree as ET
import requests
from typing import List, Optional, Tuple

from core.logger import logger
from models.pdv import PDVInfo, LogPDVActivity

def extrair_todos_pdvs_do_log(caminho_log: str) -> List[LogPDVActivity]:
    if not caminho_log or not os.path.exists(caminho_log):
        return []
    
    atividades = []
    try:
        with open(caminho_log, 'r', encoding='utf-8', errors='ignore') as f:
            linhas = f.readlines()
            # Limita a busca às últimas 5000 linhas
            if len(linhas) > 5000:
                linhas = linhas[-5000:]
        
        padrao_pdv_idq = r'pdv_idq:\[(\d+)\]'
        padrao_pdv_ref = r'pdv_referencia:\[(\d+)\]'
        padrao_func = r'funcionario:\[(\d+)\]'
        padrao_ip = r'host:\[([0-9.]+):\d+\]'
        padrao_versao = r'app_version:\[([0-9.]+)\]'
        
        pdvs_encontrados = {}
        
        for linha in linhas:
            match_idq = re.search(padrao_pdv_idq, linha)
            if match_idq:
                idq = match_idq.group(1)
                
                if idq in pdvs_encontrados:
                    atividade = pdvs_encontrados[idq]
                else:
                    atividade = LogPDVActivity()
                    atividade.pdv_idq = idq
                    pdvs_encontrados[idq] = atividade
                
                match_ref = re.search(padrao_pdv_ref, linha)
                if match_ref and not atividade.pdv_referencia:
                    atividade.pdv_referencia = match_ref.group(1)
                
                match_func = re.search(padrao_func, linha)
                if match_func and not atividade.funcionario:
                    atividade.funcionario = match_func.group(1)
                
                match_ip = re.search(padrao_ip, linha)
                if match_ip and not atividade.ip:
                    atividade.ip = match_ip.group(1)
                
                match_versao = re.search(padrao_versao, linha)
                if match_versao and not atividade.versao_app:
                    atividade.versao_app = match_versao.group(1)
                
                match_hora = re.search(r'(\d{2}:\d{2}:\d{2})', linha)
                if match_hora:
                    atividade.ultima_atividade = match_hora.group(1)
        
        atividades = list(pdvs_encontrados.values())
        return atividades
        
    except Exception as e:
        logger.error(f"Erro ao analisar log ({caminho_log}): {e}")
        return []

def encontrar_log_webPostoPayServer(pasta_log: str) -> Optional[str]:
    if not pasta_log or not os.path.exists(pasta_log):
        return None
    
    webposto_path = os.path.join(pasta_log, "webPostoPayServer")
    if not os.path.exists(webposto_path):
        return None
    
    latest_file = None
    latest_mtime = 0
    
    try:
        for root, _, files in os.walk(webposto_path):
            for file in files:
                if file.lower().endswith('.log'):
                    filepath = os.path.join(root, file)
                    try:
                        mtime = os.path.getmtime(filepath)
                        if mtime > latest_mtime:
                            latest_mtime = mtime
                            latest_file = filepath
                    except OSError:
                        continue
    except Exception as e:
        logger.error(f"Erro ao procurar log do webPostoPayServer: {e}")
        
    return latest_file

def consultar_todos_pdvs_via_api(base_url: str = "http://localhost:8080") -> List[PDVInfo]:
    headers_padrao = {
        "pdv_idq": "38545",
        "pdv_referencia": "002",
        "funcionario": "00001",
        "Content-Type": "application/xml",
        "Accept": "application/xml"
    }
    
    pdvs = []
    url = f"{base_url}/pdv"
    
    try:
        response = requests.get(url, headers=headers_padrao, timeout=5)
        
        if response.status_code == 200:
            try:
                root = ET.fromstring(response.text)
                for item in root.findall('.//item'):
                    pdv = PDVInfo(
                        codigo=item.findtext('cd_pdv', ''),
                        id_interno=item.findtext('idq_pdv', ''),
                        nome=item.findtext('nome_pdv', ''),
                        tipo=item.findtext('tipo', 'M'),
                        operando=item.findtext('operando', 'N') == 'S',
                        serial=item.findtext('posSerial', 'N/A'),
                        codigo_estoque=item.findtext('codigoEstoque', '')
                    )
                    if pdv.codigo or pdv.id_interno:
                        pdvs.append(pdv)
            except ET.ParseError as e:
                logger.error(f"Erro ao parsear XML da API de PDV: {e}")
            except Exception as e:
                logger.error(f"Erro inesperado no parser XML: {e}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Erro na comunicação com a API em {base_url}: {e}")
    
    return pdvs

def identificar_todos_pdvs_por_log(pasta_log: str) -> Tuple[List[PDVInfo], str]:
    todos_pdvs = consultar_todos_pdvs_via_api()
    log_path = encontrar_log_webPostoPayServer(pasta_log)
    atividades_log = extrair_todos_pdvs_do_log(log_path) if log_path else []
    
    pdvs_encontrados = []
    mensagens = []
    pdvs_por_id = {pdv.id_interno: pdv for pdv in todos_pdvs}
    
    for atividade in atividades_log:
        if atividade.pdv_idq:
            if atividade.pdv_idq in pdvs_por_id:
                pdv_encontrado = pdvs_por_id[atividade.pdv_idq]
                pdvs_encontrados.append(pdv_encontrado)
                mensagens.append(f"PDV {pdv_encontrado.codigo} - {pdv_encontrado.nome}")
            else:
                pdv_temp = PDVInfo(
                    codigo=atividade.pdv_referencia or f"PDV_{atividade.pdv_idq}",
                    id_interno=atividade.pdv_idq,
                    nome=f"PDV {atividade.pdv_referencia or atividade.pdv_idq}",
                    tipo='M', operando=True, serial='N/A', codigo_estoque=''
                )
                pdvs_encontrados.append(pdv_temp)
                mensagens.append(f"PDV não cadastrado - IDQ: {atividade.pdv_idq}")
    
    if not pdvs_encontrados and todos_pdvs:
        pdvs_pay_ativos = [p for p in todos_pdvs if p.tipo == 'M' and p.operando]
        for pdv in pdvs_pay_ativos:
            pdvs_encontrados.append(pdv)
            mensagens.append(f"PDV PAY: {pdv.codigo} - {pdv.nome}")
    
    if pdvs_encontrados:
        return pdvs_encontrados, f"Total: {len(pdvs_encontrados)}\n" + "\n".join(mensagens)
    return [], "Nenhum PDV identificado"
