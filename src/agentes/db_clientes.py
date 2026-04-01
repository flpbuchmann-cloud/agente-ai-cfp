"""
Base de dados de clientes.

Armazena cadastro centralizado em clientes.json com metadados,
independente das pastas de documentos e relatórios.
"""

import os
import json
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
DB_PATH = os.path.join(DATA_DIR, "clientes.json")


def _carregar_db() -> dict:
    """Carrega a base de clientes."""
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _salvar_db(db: dict):
    """Salva a base de clientes."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def cadastro_padrao() -> dict:
    """Retorna estrutura padrão de cadastro de um cliente."""
    return {
        "nome_completo": "",
        "cpf": "",
        "data_nascimento": "",
        "idade": "",
        "estado_civil": "",
        "regime_de_bens": "",
        "conjuge": "",
        "filhos": "",
        "profissao": "",
        "empresa_principal": "",
        "cidade_uf": "",
        "telefone": "",
        "email": "",
        "perfil_risco": "",
        "horizonte_temporal": "",
        "objetivos_financeiros": "",
        "patrimonio_estimado": "",
        "renda_mensal_estimada": "",
        "observacoes": "",
        "criado_em": "",
        "atualizado_em": "",
    }


def listar_clientes() -> list[dict]:
    """
    Lista todos os clientes com resumo.

    Returns:
        Lista de dicts com: id, nome_completo, cpf, cidade_uf, criado_em, atualizado_em
    """
    db = _carregar_db()
    resultado = []
    for client_id, dados in db.items():
        resultado.append({
            "id": client_id,
            "nome_completo": dados.get("nome_completo", client_id),
            "cpf": dados.get("cpf", ""),
            "cidade_uf": dados.get("cidade_uf", ""),
            "profissao": dados.get("profissao", ""),
            "criado_em": dados.get("criado_em", ""),
            "atualizado_em": dados.get("atualizado_em", ""),
        })
    return sorted(resultado, key=lambda x: x["nome_completo"].lower())


def ids_clientes() -> list[str]:
    """Retorna lista de IDs (nomes de pasta) dos clientes."""
    db = _carregar_db()
    return sorted(db.keys())


def obter_cliente(client_id: str) -> dict:
    """Retorna dados completos de um cliente."""
    db = _carregar_db()
    return db.get(client_id, cadastro_padrao())


def salvar_cliente(client_id: str, dados: dict):
    """Salva/atualiza dados de um cliente."""
    db = _carregar_db()
    dados["atualizado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    if client_id not in db:
        dados["criado_em"] = dados["atualizado_em"]
    else:
        dados["criado_em"] = db[client_id].get("criado_em", dados["atualizado_em"])
    db[client_id] = dados
    _salvar_db(db)


def criar_cliente(nome: str) -> str:
    """
    Cria um novo cliente.

    Returns:
        client_id (slug do nome)
    """
    # Gerar ID a partir do nome
    client_id = nome.strip().replace(" ", "_").lower()
    # Evitar duplicatas
    db = _carregar_db()
    if client_id in db:
        raise ValueError(f"Cliente '{client_id}' já existe.")

    dados = cadastro_padrao()
    dados["nome_completo"] = nome.strip()
    dados["criado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    dados["atualizado_em"] = dados["criado_em"]

    db[client_id] = dados
    _salvar_db(db)
    return client_id


def excluir_cliente(client_id: str):
    """Remove um cliente da base e seus arquivos."""
    import shutil
    db = _carregar_db()
    db.pop(client_id, None)
    _salvar_db(db)

    # Remover pasta de dados
    pasta = os.path.join(DATA_DIR, "clientes", client_id)
    if os.path.isdir(pasta):
        shutil.rmtree(pasta)


def renomear_cliente(client_id_antigo: str, novo_nome: str) -> str:
    """
    Renomeia um cliente.

    Returns:
        novo client_id
    """
    import shutil
    db = _carregar_db()

    novo_id = novo_nome.strip().replace(" ", "_").lower()
    if novo_id in db and novo_id != client_id_antigo:
        raise ValueError(f"Cliente '{novo_id}' já existe.")

    # Copiar dados
    dados = db.pop(client_id_antigo, cadastro_padrao())
    dados["nome_completo"] = novo_nome.strip()
    dados["atualizado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    db[novo_id] = dados
    _salvar_db(db)

    # Renomear pasta
    pasta_antiga = os.path.join(DATA_DIR, "clientes", client_id_antigo)
    pasta_nova = os.path.join(DATA_DIR, "clientes", novo_id)
    if os.path.isdir(pasta_antiga) and not os.path.exists(pasta_nova):
        os.rename(pasta_antiga, pasta_nova)

    return novo_id


def migrar_clientes_existentes():
    """
    Migra clientes que existem só como pasta para a base clientes.json.
    Chamado na inicialização do app.
    """
    pasta_clientes = os.path.join(DATA_DIR, "clientes")
    if not os.path.isdir(pasta_clientes):
        return

    db = _carregar_db()
    for nome_pasta in os.listdir(pasta_clientes):
        caminho = os.path.join(pasta_clientes, nome_pasta)
        if os.path.isdir(caminho) and nome_pasta not in db:
            # Tentar carregar info_qualitativa.json se existir
            info_path = os.path.join(caminho, "info_qualitativa.json")
            if os.path.exists(info_path):
                with open(info_path, "r", encoding="utf-8") as f:
                    dados = json.load(f)
            else:
                dados = cadastro_padrao()

            if not dados.get("nome_completo"):
                dados["nome_completo"] = nome_pasta.replace("_", " ").title()
            dados.setdefault("criado_em", datetime.now().strftime("%Y-%m-%d %H:%M"))
            dados.setdefault("atualizado_em", dados["criado_em"])

            db[nome_pasta] = dados

    _salvar_db(db)
