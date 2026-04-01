"""
Engine de orquestração dos agentes.

Coordena a execução dos agentes especialistas e do agente master,
gerenciando documentos, prompts e chamadas à API Claude.
"""

import os
import json
import time
from pathlib import Path

import anthropic

from src.prompts.agentes import AGENTES, PROMPT_MASTER
from src.agentes.leitor_documentos import (
    ler_pasta,
    ler_documento,
    formatar_documentos_para_prompt,
)

# Diretório base de dados dos clientes
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "clientes")


def _get_client() -> anthropic.Anthropic:
    """Retorna cliente da API Anthropic."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY não configurada. "
            "Defina a variável de ambiente ou insira no app."
        )
    return anthropic.Anthropic(api_key=api_key)


def pasta_cliente(nome_cliente: str) -> str:
    """Retorna o caminho da pasta do cliente."""
    return os.path.join(DATA_DIR, nome_cliente)


def pasta_agente(nome_cliente: str, agente_id: str) -> str:
    """Retorna o caminho da pasta de documentos de um agente para um cliente."""
    return os.path.join(pasta_cliente(nome_cliente), "documentos", agente_id)


def criar_estrutura_cliente(nome_cliente: str) -> str:
    """Cria a estrutura de pastas para um novo cliente."""
    base = pasta_cliente(nome_cliente)
    os.makedirs(base, exist_ok=True)

    # Pasta de documentos por agente
    for agente_id in AGENTES:
        os.makedirs(os.path.join(base, "documentos", agente_id), exist_ok=True)

    # Pasta de relatórios
    os.makedirs(os.path.join(base, "relatorios"), exist_ok=True)

    # Arquivo de info qualitativa
    info_path = os.path.join(base, "info_qualitativa.json")
    if not os.path.exists(info_path):
        info_padrao = {
            "nome_completo": "",
            "idade": "",
            "estado_civil": "",
            "regime_de_bens": "",
            "filhos": "",
            "profissao": "",
            "cidade_uf": "",
            "objetivos_financeiros": "",
            "horizonte_temporal": "",
            "perfil_risco": "",
            "observacoes": "",
        }
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info_padrao, f, ensure_ascii=False, indent=2)

    return base


def carregar_info_qualitativa(nome_cliente: str) -> dict:
    """Carrega informações qualitativas do cliente."""
    caminho = os.path.join(pasta_cliente(nome_cliente), "info_qualitativa.json")
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_info_qualitativa(nome_cliente: str, info: dict):
    """Salva informações qualitativas do cliente."""
    caminho = os.path.join(pasta_cliente(nome_cliente), "info_qualitativa.json")
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


def formatar_info_qualitativa(info: dict) -> str:
    """Formata info qualitativa para inclusão nos prompts."""
    if not info or all(not v for v in info.values()):
        return "[NENHUMA INFORMAÇÃO QUALITATIVA DISPONÍVEL]"

    labels = {
        "nome_completo": "Nome Completo",
        "idade": "Idade",
        "estado_civil": "Estado Civil",
        "regime_de_bens": "Regime de Bens",
        "filhos": "Filhos/Dependentes",
        "profissao": "Profissão/Atividade",
        "cidade_uf": "Cidade/UF",
        "objetivos_financeiros": "Objetivos Financeiros",
        "horizonte_temporal": "Horizonte Temporal",
        "perfil_risco": "Perfil de Risco",
        "observacoes": "Observações Gerais",
    }

    linhas = []
    for chave, label in labels.items():
        valor = info.get(chave, "")
        if valor:
            linhas.append(f"- **{label}**: {valor}")

    # Campos extras (adicionados pelo usuário)
    for chave, valor in info.items():
        if chave not in labels and valor:
            linhas.append(f"- **{chave}**: {valor}")

    return "\n".join(linhas) if linhas else "[NENHUMA INFORMAÇÃO QUALITATIVA DISPONÍVEL]"


def listar_clientes() -> list[str]:
    """Lista todos os clientes cadastrados."""
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted([
        d for d in os.listdir(DATA_DIR)
        if os.path.isdir(os.path.join(DATA_DIR, d))
    ])


def listar_documentos_agente(nome_cliente: str, agente_id: str) -> list[str]:
    """Lista documentos na pasta de um agente para um cliente."""
    pasta = pasta_agente(nome_cliente, agente_id)
    if not os.path.isdir(pasta):
        return []
    return sorted([
        f for f in os.listdir(pasta)
        if os.path.isfile(os.path.join(pasta, f))
    ])


def salvar_documento(nome_cliente: str, agente_id: str, nome_arquivo: str, conteudo: bytes):
    """Salva um documento na pasta do agente."""
    pasta = pasta_agente(nome_cliente, agente_id)
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome_arquivo)
    with open(caminho, "wb") as f:
        f.write(conteudo)
    return caminho


def importar_de_pasta(nome_cliente: str, agente_id: str, pasta_origem: str) -> list[str]:
    """Importa (copia) documentos de uma pasta externa para a pasta do agente."""
    import shutil
    pasta_destino = pasta_agente(nome_cliente, agente_id)
    os.makedirs(pasta_destino, exist_ok=True)

    importados = []
    if not os.path.isdir(pasta_origem):
        return importados

    for arquivo in os.listdir(pasta_origem):
        origem = os.path.join(pasta_origem, arquivo)
        if os.path.isfile(origem):
            destino = os.path.join(pasta_destino, arquivo)
            shutil.copy2(origem, destino)
            importados.append(arquivo)

    return importados


def executar_agente_especialista(
    nome_cliente: str,
    agente_id: str,
    modelo: str = "claude-sonnet-4-20250514",
    callback=None,
) -> str:
    """
    Executa um agente especialista.

    Args:
        nome_cliente: nome do cliente
        agente_id: ID do agente (chave do dict AGENTES)
        modelo: modelo Claude a usar
        callback: função callback(status_msg) para updates de progresso

    Returns:
        Relatório gerado pelo agente
    """
    agente = AGENTES[agente_id]
    if callback:
        callback(f"Lendo documentos de {agente['nome']}...")

    # Carregar info qualitativa
    info = carregar_info_qualitativa(nome_cliente)
    info_formatada = formatar_info_qualitativa(info)

    # Carregar documentos da pasta do agente
    pasta = pasta_agente(nome_cliente, agente_id)
    documentos = ler_pasta(pasta)
    docs_formatados = formatar_documentos_para_prompt(documentos)

    # Montar prompt
    prompt = agente["prompt"].format(
        info_qualitativa=info_formatada,
        documentos=docs_formatados,
    )

    # Separar imagens dos documentos para envio multimodal
    content_parts = []
    for doc in documentos:
        if doc.get("imagem"):
            content_parts.append(doc["imagem"])

    content_parts.append({"type": "text", "text": prompt})

    if callback:
        callback(f"Executando {agente['nome']}...")

    # Chamar API Claude
    client = _get_client()
    response = client.messages.create(
        model=modelo,
        max_tokens=8192,
        messages=[{"role": "user", "content": content_parts}],
    )

    relatorio = response.content[0].text

    # Salvar relatório
    relatorios_dir = os.path.join(pasta_cliente(nome_cliente), "relatorios")
    os.makedirs(relatorios_dir, exist_ok=True)
    caminho_rel = os.path.join(relatorios_dir, f"{agente_id}.md")
    with open(caminho_rel, "w", encoding="utf-8") as f:
        f.write(f"# {agente['nome']}\n\n{relatorio}")

    if callback:
        callback(f"{agente['nome']} concluído.")

    return relatorio


def executar_master(
    nome_cliente: str,
    relatorios: dict[str, str],
    modelo: str = "claude-sonnet-4-20250514",
    callback=None,
) -> str:
    """
    Executa o agente master com os relatórios dos especialistas.

    Args:
        nome_cliente: nome do cliente
        relatorios: dict {agente_id: relatório}
        modelo: modelo Claude a usar
        callback: função callback

    Returns:
        Parecer integrado do master
    """
    if callback:
        callback("Agente Master analisando relatórios...")

    info = carregar_info_qualitativa(nome_cliente)
    info_formatada = formatar_info_qualitativa(info)

    # Formatar relatórios dos especialistas
    partes_relatorios = []
    for agente_id, relatorio in relatorios.items():
        agente = AGENTES.get(agente_id, {})
        nome = agente.get("nome", agente_id)
        partes_relatorios.append(f"## {nome}\n\n{relatorio}")

    relatorios_formatados = "\n\n---\n\n".join(partes_relatorios)

    prompt = PROMPT_MASTER.format(
        info_qualitativa=info_formatada,
        relatorios_especialistas=relatorios_formatados,
    )

    client = _get_client()
    response = client.messages.create(
        model=modelo,
        max_tokens=16384,
        messages=[{"role": "user", "content": prompt}],
    )

    parecer = response.content[0].text

    # Salvar parecer
    relatorios_dir = os.path.join(pasta_cliente(nome_cliente), "relatorios")
    os.makedirs(relatorios_dir, exist_ok=True)
    caminho = os.path.join(relatorios_dir, "parecer_master.md")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(f"# Parecer Financeiro Integrado\n\n{parecer}")

    if callback:
        callback("Parecer Master concluído.")

    return parecer


def executar_pipeline_completo(
    nome_cliente: str,
    agentes_selecionados: list[str] | None = None,
    modelo: str = "claude-sonnet-4-20250514",
    callback=None,
) -> dict:
    """
    Executa o pipeline completo: todos os agentes especialistas + master.

    Args:
        nome_cliente: nome do cliente
        agentes_selecionados: lista de agente_ids (None = todos)
        modelo: modelo Claude
        callback: função callback(status_msg)

    Returns:
        {
            "especialistas": {agente_id: relatório},
            "master": parecer_integrado,
        }
    """
    if agentes_selecionados is None:
        agentes_selecionados = list(AGENTES.keys())

    relatorios = {}
    total = len(agentes_selecionados)

    for i, agente_id in enumerate(agentes_selecionados):
        if callback:
            callback(f"[{i+1}/{total}] Executando {AGENTES[agente_id]['nome']}...")

        relatorio = executar_agente_especialista(
            nome_cliente, agente_id, modelo, callback
        )
        relatorios[agente_id] = relatorio

        # Pausa entre chamadas para respeitar rate limits
        if i < total - 1:
            time.sleep(1)

    # Executar master
    if callback:
        callback(f"[Master] Consolidando análises...")

    parecer = executar_master(nome_cliente, relatorios, modelo, callback)

    return {
        "especialistas": relatorios,
        "master": parecer,
    }
