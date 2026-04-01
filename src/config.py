"""
Configuração centralizada do Agente AI - CFP.

Define a pasta base onde todos os dados de clientes são armazenados
(cadastros, documentos, relatórios). Pode ser uma pasta no Google Drive
para sincronização automática.
"""

import os
import json

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "config.json"
)

# Pasta padrão dentro do projeto (fallback)
_DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data"
)


def _carregar_config() -> dict:
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _salvar_config(cfg: dict):
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_pasta_base() -> str:
    """
    Retorna a pasta base configurada para dados de clientes.

    Ordem de prioridade:
    1. Variável de ambiente CFP_DATA_DIR
    2. Streamlit secrets cfp_data_dir
    3. config.json salvo pelo app
    4. Pasta padrão dentro do projeto
    """
    # 1. Env var
    env = os.environ.get("CFP_DATA_DIR", "")
    if env and os.path.isdir(env):
        return env

    # 2. Streamlit secrets
    try:
        import streamlit as st
        secret = st.secrets.get("CFP_DATA_DIR", "")
        if secret and os.path.isdir(secret):
            return secret
    except Exception:
        pass

    # 3. Config salva
    cfg = _carregar_config()
    salva = cfg.get("pasta_base", "")
    if salva and os.path.isdir(salva):
        return salva

    # 4. Default
    return _DEFAULT_DATA_DIR


def set_pasta_base(pasta: str):
    """Salva a pasta base no config.json."""
    cfg = _carregar_config()
    cfg["pasta_base"] = pasta
    _salvar_config(cfg)


def get_pasta_clientes() -> str:
    """Retorna pasta onde ficam as subpastas de cada cliente."""
    return os.path.join(get_pasta_base(), "clientes")


def get_db_path() -> str:
    """Retorna caminho do arquivo clientes.json."""
    return os.path.join(get_pasta_base(), "clientes.json")
