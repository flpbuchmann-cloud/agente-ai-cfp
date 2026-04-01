"""
Engine de orquestração dos agentes.

Coordena a execução dos agentes especialistas e do agente master,
gerenciando documentos, prompts e chamadas às APIs Claude e Gemini.
"""

import os
import json
import time
from pathlib import Path

from src.prompts.agentes import AGENTES, PROMPT_MASTER
from src.agentes.leitor_documentos import (
    ler_pasta,
    ler_documento,
    formatar_documentos_para_prompt,
)

# Diretório base de dados dos clientes
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "clientes")

# ---------------------------------------------------------------------------
# Provedores de IA
# ---------------------------------------------------------------------------

PROVEDORES = {
    "claude": {
        "nome": "Claude (Anthropic)",
        "modelos": [
            "claude-sonnet-4-20250514",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-20250514",
        ],
    },
    "gemini": {
        "nome": "Gemini (Google)",
        "modelos": [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ],
    },
}


def _get_api_key(provedor: str) -> str:
    """Busca API key do provedor (env > streamlit secrets)."""
    env_var = "ANTHROPIC_API_KEY" if provedor == "claude" else "GEMINI_API_KEY"
    api_key = os.environ.get(env_var, "")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get(env_var, "")
        except Exception:
            pass
    return api_key


def _chamar_claude(prompt: str, content_parts: list, modelo: str, max_tokens: int) -> str:
    """Executa chamada à API Claude."""
    import anthropic

    api_key = _get_api_key("claude")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY não configurada.")

    client = anthropic.Anthropic(api_key=api_key)

    # Montar content: imagens + texto
    parts = list(content_parts)  # imagens já estão aqui
    parts.append({"type": "text", "text": prompt})

    response = client.messages.create(
        model=modelo,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": parts}],
    )
    return response.content[0].text


def _chamar_gemini(
    prompt: str,
    content_parts: list,
    modelo: str,
    max_tokens: int,
    gem_id: str | None = None,
) -> str:
    """
    Executa chamada à API Gemini.

    Args:
        prompt: texto do prompt
        content_parts: lista de imagens (dicts base64)
        modelo: ID do modelo Gemini
        max_tokens: máximo de tokens na resposta
        gem_id: ID de um Gem personalizado (opcional)
    """
    import google.generativeai as genai

    api_key = _get_api_key("gemini")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada.")

    genai.configure(api_key=api_key)

    # Configuração de geração
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=max_tokens,
        temperature=0.7,
    )

    # Se tem Gem, usar como system instruction via model tunado
    if gem_id:
        model = genai.GenerativeModel(
            model_name=gem_id,
            generation_config=generation_config,
        )
    else:
        model = genai.GenerativeModel(
            model_name=modelo,
            generation_config=generation_config,
        )

    # Montar conteúdo multimodal
    parts = []

    # Adicionar imagens
    for cp in content_parts:
        if cp.get("type") == "image":
            import base64
            img_data = base64.b64decode(cp["source"]["data"])
            mime = cp["source"]["media_type"]
            parts.append({"mime_type": mime, "data": img_data})

    # Adicionar texto
    parts.append(prompt)

    response = model.generate_content(parts)
    return response.text


def chamar_ia(
    prompt: str,
    content_parts: list | None = None,
    provedor: str = "claude",
    modelo: str = "claude-sonnet-4-20250514",
    max_tokens: int = 8192,
    gem_id: str | None = None,
) -> str:
    """
    Chamada unificada para qualquer provedor de IA.

    Args:
        prompt: texto do prompt
        content_parts: lista de conteúdo multimodal (imagens)
        provedor: "claude" ou "gemini"
        modelo: ID do modelo
        max_tokens: máximo de tokens na resposta
        gem_id: ID de um Gem do Gemini (opcional)

    Returns:
        Texto da resposta
    """
    if content_parts is None:
        content_parts = []

    if provedor == "claude":
        return _chamar_claude(prompt, content_parts, modelo, max_tokens)
    elif provedor == "gemini":
        return _chamar_gemini(prompt, content_parts, modelo, max_tokens, gem_id)
    else:
        raise ValueError(f"Provedor desconhecido: {provedor}")


# ---------------------------------------------------------------------------
# Gestão de clientes e documentos
# ---------------------------------------------------------------------------

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

    for agente_id in AGENTES:
        os.makedirs(os.path.join(base, "documentos", agente_id), exist_ok=True)

    os.makedirs(os.path.join(base, "relatorios"), exist_ok=True)

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


def excluir_cliente(nome_cliente: str):
    """Remove toda a pasta e dados de um cliente."""
    import shutil
    pasta = pasta_cliente(nome_cliente)
    if os.path.isdir(pasta):
        shutil.rmtree(pasta)


def renomear_cliente(nome_atual: str, nome_novo: str):
    """Renomeia a pasta de um cliente."""
    pasta_atual = pasta_cliente(nome_atual)
    pasta_nova = pasta_cliente(nome_novo)
    if os.path.isdir(pasta_atual) and not os.path.exists(pasta_nova):
        os.rename(pasta_atual, pasta_nova)


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


# ---------------------------------------------------------------------------
# Execução dos agentes
# ---------------------------------------------------------------------------

def executar_agente_especialista(
    nome_cliente: str,
    agente_id: str,
    provedor: str = "claude",
    modelo: str = "claude-sonnet-4-20250514",
    gem_id: str | None = None,
    callback=None,
) -> str:
    """Executa um agente especialista."""
    agente = AGENTES[agente_id]
    if callback:
        callback(f"Lendo documentos de {agente['nome']}...")

    info = carregar_info_qualitativa(nome_cliente)
    info_formatada = formatar_info_qualitativa(info)

    pasta = pasta_agente(nome_cliente, agente_id)
    documentos = ler_pasta(pasta)
    docs_formatados = formatar_documentos_para_prompt(documentos)

    prompt = agente["prompt"].format(
        info_qualitativa=info_formatada,
        documentos=docs_formatados,
    )

    # Separar imagens para envio multimodal
    content_parts = [doc["imagem"] for doc in documentos if doc.get("imagem")]

    if callback:
        callback(f"Executando {agente['nome']}...")

    relatorio = chamar_ia(
        prompt=prompt,
        content_parts=content_parts,
        provedor=provedor,
        modelo=modelo,
        max_tokens=8192,
        gem_id=gem_id,
    )

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
    provedor: str = "claude",
    modelo: str = "claude-sonnet-4-20250514",
    gem_id: str | None = None,
    callback=None,
) -> str:
    """Executa o agente master com os relatórios dos especialistas."""
    if callback:
        callback("Agente Master analisando relatórios...")

    info = carregar_info_qualitativa(nome_cliente)
    info_formatada = formatar_info_qualitativa(info)

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

    parecer = chamar_ia(
        prompt=prompt,
        provedor=provedor,
        modelo=modelo,
        max_tokens=16384,
        gem_id=gem_id,
    )

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
    provedor: str = "claude",
    modelo: str = "claude-sonnet-4-20250514",
    gem_id: str | None = None,
    callback=None,
) -> dict:
    """Executa o pipeline completo: todos os agentes especialistas + master."""
    if agentes_selecionados is None:
        agentes_selecionados = list(AGENTES.keys())

    relatorios = {}
    total = len(agentes_selecionados)

    for i, agente_id in enumerate(agentes_selecionados):
        if callback:
            callback(f"[{i+1}/{total}] Executando {AGENTES[agente_id]['nome']}...")

        relatorio = executar_agente_especialista(
            nome_cliente, agente_id, provedor, modelo, gem_id, callback
        )
        relatorios[agente_id] = relatorio

        if i < total - 1:
            time.sleep(1)

    if callback:
        callback("[Master] Consolidando análises...")

    parecer = executar_master(
        nome_cliente, relatorios, provedor, modelo, gem_id, callback
    )

    return {
        "especialistas": relatorios,
        "master": parecer,
    }
