"""
Agente AI - CFP: Planejamento Financeiro Pessoal com Agentes de IA

Usage:
    streamlit run app.py
"""

import os
import sys
import json

import streamlit as st

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.prompts.agentes import AGENTES
from src.agentes.engine import (
    criar_estrutura_cliente,
    listar_documentos_agente,
    salvar_documento,
    importar_de_pasta,
    pasta_agente,
    executar_agente_especialista,
    executar_master,
    pasta_cliente,
    PROVEDORES,
)
from src.agentes.db_clientes import (
    listar_clientes as db_listar_clientes,
    ids_clientes,
    obter_cliente,
    salvar_cliente,
    criar_cliente,
    excluir_cliente as db_excluir_cliente,
    renomear_cliente as db_renomear_cliente,
    migrar_clientes_existentes,
)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Agente AI - CFP",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1rem; color: #666; margin-bottom: 2rem; }
    .client-card {
        background: #f8f9fa; border-radius: 10px; padding: 1rem;
        margin-bottom: 0.5rem; border-left: 4px solid #667eea;
    }
</style>
""", unsafe_allow_html=True)

# Migrar clientes antigos (só pastas) para a base
migrar_clientes_existentes()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _k(base: str) -> str:
    """Gera widget key com prefixo do cliente ativo para evitar conflito."""
    cid = st.session_state.get("cliente_ativo", "none")
    return f"{cid}__{base}"


def _limpar_estado_cliente():
    """Remove dados de sessão do cliente anterior ao trocar."""
    keys_to_remove = [k for k in st.session_state if k.startswith("relatorio_")]
    keys_to_remove += [k for k in st.session_state if k == "parecer_master"]
    for k in keys_to_remove:
        del st.session_state[k]


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
def sidebar():
    with st.sidebar:
        st.markdown("### 🧠 Agente AI - CFP")
        st.caption("Planejamento Financeiro com IA")
        st.markdown("---")

        # Provedor de IA
        st.markdown("### 🔑 Provedor de IA")
        provedor = st.selectbox(
            "Provedor",
            list(PROVEDORES.keys()),
            format_func=lambda x: PROVEDORES[x]["nome"],
            key="sel_provedor",
        )
        st.session_state["provedor"] = provedor

        if provedor == "claude":
            api_key = st.text_input(
                "Anthropic API Key", type="password",
                value=os.environ.get("ANTHROPIC_API_KEY", ""),
            )
            if api_key:
                os.environ["ANTHROPIC_API_KEY"] = api_key
        else:
            api_key = st.text_input(
                "Google Gemini API Key", type="password",
                value=os.environ.get("GEMINI_API_KEY", ""),
            )
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key
            gem_id = st.text_input(
                "Gem ID (opcional)", value=st.session_state.get("gem_id", ""),
                placeholder="tunedModels/...",
            )
            st.session_state["gem_id"] = gem_id.strip() if gem_id.strip() else None

        st.markdown("---")

        # Modelo
        st.markdown("### ⚙️ Configurações")
        modelos = PROVEDORES[provedor]["modelos"]
        modelo = st.selectbox("Modelo", modelos, index=0)
        st.session_state["modelo"] = modelo

        st.markdown("---")

        # Navegação
        st.markdown("### 📍 Navegação")
        tela = st.radio(
            "Ir para:",
            ["🏠 Painel de Clientes", "👤 Ficha do Cliente"],
            key="nav_tela",
            label_visibility="collapsed",
        )
        st.session_state["tela"] = tela

        # Resumo do cliente ativo
        cid = st.session_state.get("cliente_ativo")
        if cid:
            dados = obter_cliente(cid)
            st.markdown("---")
            st.markdown(f"**Cliente ativo:**  \n{dados.get('nome_completo', cid)}")
            total_docs = sum(
                len(listar_documentos_agente(cid, a)) for a in AGENTES
            )
            st.caption(f"📄 {total_docs} documentos")


# ---------------------------------------------------------------------------
# TELA 1: Painel de Clientes
# ---------------------------------------------------------------------------
def tela_painel_clientes():
    st.markdown('<p class="main-header">🧠 Agente AI - CFP</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Planejamento Financeiro Pessoal com Inteligência Artificial</p>',
        unsafe_allow_html=True,
    )

    # Novo cliente
    st.markdown("### ➕ Novo Cliente")
    col_novo, col_btn = st.columns([3, 1])
    with col_novo:
        novo_nome = st.text_input("Nome do cliente", key="novo_cliente_nome", label_visibility="collapsed",
                                   placeholder="Nome completo do cliente")
    with col_btn:
        if st.button("Criar Cliente", key="btn_criar", type="primary"):
            if novo_nome.strip():
                try:
                    cid = criar_cliente(novo_nome.strip())
                    criar_estrutura_cliente(cid)
                    st.session_state["cliente_ativo"] = cid
                    st.session_state["tela"] = "👤 Ficha do Cliente"
                    st.success(f"Cliente '{novo_nome.strip()}' criado!")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            else:
                st.warning("Informe o nome.")

    st.markdown("---")

    # Lista de clientes
    clientes = db_listar_clientes()

    if not clientes:
        st.info("Nenhum cliente cadastrado. Crie o primeiro acima.")
        return

    st.markdown(f"### 👥 Clientes Cadastrados ({len(clientes)})")

    # Busca
    busca = st.text_input("🔍 Buscar cliente", key="busca_cliente", placeholder="Nome, CPF ou cidade...")
    if busca:
        busca_lower = busca.lower()
        clientes = [c for c in clientes if
                    busca_lower in c["nome_completo"].lower() or
                    busca_lower in c.get("cpf", "") or
                    busca_lower in c.get("cidade_uf", "").lower()]

    # Tabela de clientes
    for c in clientes:
        col_info, col_acoes = st.columns([5, 2])

        with col_info:
            nome = c["nome_completo"] or c["id"]
            cpf = f" | CPF: {c['cpf']}" if c.get("cpf") else ""
            cidade = f" | {c['cidade_uf']}" if c.get("cidade_uf") else ""
            profissao = f" | {c['profissao']}" if c.get("profissao") else ""
            atualizado = f" | Atualizado: {c['atualizado_em']}" if c.get("atualizado_em") else ""

            st.markdown(f"**{nome}**{cpf}{cidade}{profissao}{atualizado}")

        with col_acoes:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Abrir", key=f"abrir_{c['id']}", type="primary"):
                    _limpar_estado_cliente()
                    st.session_state["cliente_ativo"] = c["id"]
                    st.session_state["tela"] = "👤 Ficha do Cliente"
                    st.rerun()
            with col_b:
                if st.button("🗑️", key=f"del_{c['id']}"):
                    st.session_state["confirmar_exclusao"] = c["id"]
                    st.rerun()

        # Confirmação de exclusão
        if st.session_state.get("confirmar_exclusao") == c["id"]:
            st.warning(f"Tem certeza que deseja excluir **{c['nome_completo']}** e todos os seus dados?")
            col_sim, col_nao = st.columns(2)
            with col_sim:
                if st.button("Sim, excluir", key=f"confirma_del_{c['id']}", type="primary"):
                    db_excluir_cliente(c["id"])
                    if st.session_state.get("cliente_ativo") == c["id"]:
                        st.session_state["cliente_ativo"] = None
                    st.session_state.pop("confirmar_exclusao", None)
                    st.success(f"'{c['nome_completo']}' excluído.")
                    st.rerun()
            with col_nao:
                if st.button("Cancelar", key=f"cancela_del_{c['id']}"):
                    st.session_state.pop("confirmar_exclusao", None)
                    st.rerun()

        st.markdown("---")


# ---------------------------------------------------------------------------
# TELA 2: Ficha do Cliente (tabs)
# ---------------------------------------------------------------------------
def tela_ficha_cliente():
    cid = st.session_state.get("cliente_ativo")
    if not cid:
        st.warning("Nenhum cliente selecionado. Volte ao Painel de Clientes.")
        if st.button("← Voltar ao Painel"):
            st.session_state["tela"] = "🏠 Painel de Clientes"
            st.rerun()
        return

    dados = obter_cliente(cid)
    nome = dados.get("nome_completo", cid)

    # Header
    col_titulo, col_voltar = st.columns([5, 1])
    with col_titulo:
        st.markdown(f"## 👤 {nome}")
        if dados.get("cpf"):
            st.caption(f"CPF: {dados['cpf']} | Cadastro: {dados.get('criado_em', '')} | Atualizado: {dados.get('atualizado_em', '')}")
    with col_voltar:
        if st.button("← Painel", key="btn_voltar_painel"):
            _limpar_estado_cliente()
            st.session_state["tela"] = "🏠 Painel de Clientes"
            st.rerun()

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Cadastro",
        "📄 Documentos",
        "🤖 Executar Agentes",
        "📊 Relatórios",
    ])

    with tab1:
        _aba_cadastro(cid)
    with tab2:
        _aba_documentos(cid)
    with tab3:
        _aba_executar(cid)
    with tab4:
        _aba_relatorios(cid)


# ---------------------------------------------------------------------------
# ABA: Cadastro
# ---------------------------------------------------------------------------
def _aba_cadastro(cid: str):
    dados = obter_cliente(cid)

    st.markdown("### Dados Pessoais e Objetivos")
    st.caption("Estas informações servem como base de conhecimento para todos os agentes.")

    col1, col2 = st.columns(2)

    with col1:
        dados["nome_completo"] = st.text_input(
            "Nome completo", value=dados.get("nome_completo", ""), key=_k("nome")
        )
        dados["cpf"] = st.text_input(
            "CPF", value=dados.get("cpf", ""), key=_k("cpf")
        )
        dados["data_nascimento"] = st.text_input(
            "Data de nascimento", value=dados.get("data_nascimento", ""),
            key=_k("nasc"), placeholder="DD/MM/AAAA"
        )
        dados["idade"] = st.text_input(
            "Idade", value=dados.get("idade", ""), key=_k("idade")
        )
        opcoes_ec = ["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"]
        dados["estado_civil"] = st.selectbox(
            "Estado civil", opcoes_ec,
            index=opcoes_ec.index(dados.get("estado_civil", "")) if dados.get("estado_civil", "") in opcoes_ec else 0,
            key=_k("ec"),
        )
        opcoes_rb = ["", "Comunhão Parcial", "Comunhão Universal", "Separação Total", "Participação Final nos Aquestos"]
        dados["regime_de_bens"] = st.selectbox(
            "Regime de bens", opcoes_rb,
            index=opcoes_rb.index(dados.get("regime_de_bens", "")) if dados.get("regime_de_bens", "") in opcoes_rb else 0,
            key=_k("rb"),
        )
        dados["conjuge"] = st.text_input(
            "Cônjuge/Companheiro(a)", value=dados.get("conjuge", ""), key=_k("conj")
        )
        dados["filhos"] = st.text_area(
            "Filhos/Dependentes (nome, idade, situação)",
            value=dados.get("filhos", ""), key=_k("filhos"), height=100,
        )

    with col2:
        dados["profissao"] = st.text_input(
            "Profissão/Atividade", value=dados.get("profissao", ""), key=_k("prof")
        )
        dados["empresa_principal"] = st.text_input(
            "Empresa principal", value=dados.get("empresa_principal", ""), key=_k("emp")
        )
        dados["cidade_uf"] = st.text_input(
            "Cidade/UF", value=dados.get("cidade_uf", ""), key=_k("cidade")
        )
        dados["telefone"] = st.text_input(
            "Telefone", value=dados.get("telefone", ""), key=_k("tel")
        )
        dados["email"] = st.text_input(
            "E-mail", value=dados.get("email", ""), key=_k("email")
        )
        opcoes_pr = ["", "Conservador", "Moderado", "Arrojado", "Agressivo"]
        dados["perfil_risco"] = st.selectbox(
            "Perfil de risco", opcoes_pr,
            index=opcoes_pr.index(dados.get("perfil_risco", "")) if dados.get("perfil_risco", "") in opcoes_pr else 0,
            key=_k("pr"),
        )
        dados["horizonte_temporal"] = st.text_input(
            "Horizonte temporal", value=dados.get("horizonte_temporal", ""),
            key=_k("horiz"), placeholder="Ex: aposentadoria em 15 anos"
        )
        dados["patrimonio_estimado"] = st.text_input(
            "Patrimônio estimado", value=dados.get("patrimonio_estimado", ""),
            key=_k("patrim"), placeholder="Ex: R$ 5.000.000"
        )
        dados["renda_mensal_estimada"] = st.text_input(
            "Renda mensal estimada", value=dados.get("renda_mensal_estimada", ""),
            key=_k("renda"), placeholder="Ex: R$ 50.000"
        )

    dados["objetivos_financeiros"] = st.text_area(
        "Objetivos financeiros",
        value=dados.get("objetivos_financeiros", ""),
        key=_k("obj"), height=100,
    )

    dados["observacoes"] = st.text_area(
        "Observações gerais (contexto adicional para os agentes)",
        value=dados.get("observacoes", ""),
        key=_k("obs"), height=150,
        help="Empresas, estruturas societárias, situações especiais, preocupações...",
    )

    col_salvar, col_renomear = st.columns([1, 1])

    with col_salvar:
        if st.button("💾 Salvar cadastro", key=_k("btn_salvar"), type="primary"):
            salvar_cliente(cid, dados)
            st.success("Cadastro salvo!")

    with col_renomear:
        with st.popover("✏️ Renomear cliente"):
            novo_nome = st.text_input("Novo nome:", value=dados.get("nome_completo", ""), key=_k("ren"))
            if st.button("Confirmar", key=_k("btn_ren")):
                if novo_nome.strip() and novo_nome.strip() != dados.get("nome_completo", ""):
                    try:
                        novo_id = db_renomear_cliente(cid, novo_nome.strip())
                        _limpar_estado_cliente()
                        st.session_state["cliente_ativo"] = novo_id
                        st.success(f"Renomeado para '{novo_nome.strip()}'!")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))


# ---------------------------------------------------------------------------
# ABA: Documentos
# ---------------------------------------------------------------------------
def _aba_documentos(cid: str):
    st.markdown("### 📄 Gestão de Documentos")
    st.caption("Cada agente especialista tem sua própria pasta de documentos.")

    for agente_id, agente in AGENTES.items():
        docs = listar_documentos_agente(cid, agente_id)

        with st.expander(
            f"{agente['icone']} {agente['nome']} — {len(docs)} doc(s)",
            expanded=False,
        ):
            st.caption(agente["descricao"])
            st.markdown("**Documentos sugeridos:** " + ", ".join(agente["documentos_sugeridos"]))
            st.markdown("---")

            col_upload, col_pasta = st.columns(2)

            with col_upload:
                st.markdown("**Upload de arquivos**")
                uploaded = st.file_uploader(
                    "Arraste ou selecione", accept_multiple_files=True,
                    key=_k(f"upload_{agente_id}"),
                    type=["pdf", "docx", "xlsx", "txt", "csv", "png", "jpg", "jpeg"],
                )
                if uploaded:
                    for f in uploaded:
                        salvar_documento(cid, agente_id, f.name, f.getvalue())
                    st.success(f"{len(uploaded)} arquivo(s) salvo(s)!")
                    st.rerun()

            with col_pasta:
                st.markdown("**Importar de pasta**")
                pasta_input = st.text_input(
                    "Caminho da pasta", key=_k(f"pasta_{agente_id}"),
                    placeholder="C:/Documentos/...",
                )
                if st.button("Importar", key=_k(f"btn_imp_{agente_id}")):
                    if pasta_input and os.path.isdir(pasta_input):
                        importados = importar_de_pasta(cid, agente_id, pasta_input)
                        if importados:
                            st.success(f"{len(importados)} arquivo(s) importado(s)!")
                            st.rerun()
                        else:
                            st.warning("Nenhum arquivo encontrado.")
                    else:
                        st.error("Pasta não encontrada.")

            if docs:
                st.markdown("**Documentos carregados:**")
                for doc_name in docs:
                    col_doc, col_del = st.columns([5, 1])
                    ext = os.path.splitext(doc_name)[1].lower()
                    icon = {".pdf": "📕", ".docx": "📘", ".xlsx": "📗"}.get(ext, "📎")
                    with col_doc:
                        st.markdown(f"{icon} `{doc_name}`")
                    with col_del:
                        if st.button("🗑️", key=_k(f"deldoc_{agente_id}_{doc_name}")):
                            os.remove(os.path.join(pasta_agente(cid, agente_id), doc_name))
                            st.rerun()


# ---------------------------------------------------------------------------
# ABA: Executar Agentes
# ---------------------------------------------------------------------------
def _aba_executar(cid: str):
    modelo = st.session_state.get("modelo", "claude-sonnet-4-20250514")
    provedor = st.session_state.get("provedor", "claude")
    gem_id = st.session_state.get("gem_id")

    st.markdown("### 🤖 Executar Agentes")

    provedor_nome = PROVEDORES[provedor]["nome"]
    gem_label = f" | Gem: `{gem_id}`" if gem_id else ""
    st.info(f"**Provedor:** {provedor_nome} | **Modelo:** `{modelo}`{gem_label}")

    env_var = "ANTHROPIC_API_KEY" if provedor == "claude" else "GEMINI_API_KEY"
    if not os.environ.get(env_var):
        st.error(f"Configure a API Key ({env_var}) na barra lateral.")
        return

    # Status
    st.markdown("#### Status dos Agentes")
    cols = st.columns(3)
    for i, (agente_id, agente) in enumerate(AGENTES.items()):
        docs = listar_documentos_agente(cid, agente_id)
        with cols[i % 3]:
            status = "✅" if docs else "⚠️"
            st.markdown(f"{status} {agente['icone']} **{agente['nome']}**  \n📄 {len(docs)} doc(s)")

    st.markdown("---")

    # Individual
    st.markdown("#### Executar Agente Individual")
    col_sel, col_exec = st.columns([3, 1])
    with col_sel:
        opcoes = {f"{AGENTES[a]['icone']} {AGENTES[a]['nome']}": a for a in AGENTES}
        sel = st.selectbox("Selecionar agente", list(opcoes.keys()), key=_k("sel_agente"))
        agente_sel = opcoes[sel]
    with col_exec:
        st.markdown(""); st.markdown("")
        if st.button("▶️ Executar", key=_k("btn_exec"), type="primary"):
            with st.spinner(f"Executando {AGENTES[agente_sel]['nome']}..."):
                try:
                    relatorio = executar_agente_especialista(
                        cid, agente_sel, provedor, modelo, gem_id
                    )
                    st.session_state[f"relatorio_{agente_sel}"] = relatorio
                    st.success(f"{AGENTES[agente_sel]['nome']} concluído!")
                except Exception as e:
                    st.error(f"Erro: {e}")

    if st.session_state.get(f"relatorio_{agente_sel}"):
        with st.expander(f"📊 Relatório: {AGENTES[agente_sel]['nome']}", expanded=True):
            st.markdown(st.session_state[f"relatorio_{agente_sel}"])

    st.markdown("---")

    # Pipeline
    st.markdown("#### 🚀 Pipeline Completo")
    agentes_pipeline = []
    cols_check = st.columns(3)
    for i, (agente_id, agente) in enumerate(AGENTES.items()):
        with cols_check[i % 3]:
            if st.checkbox(f"{agente['icone']} {agente['nome']}", value=True, key=_k(f"chk_{agente_id}")):
                agentes_pipeline.append(agente_id)

    if st.button("🚀 Executar Pipeline Completo", key=_k("btn_pipeline"), type="primary"):
        if not agentes_pipeline:
            st.warning("Selecione pelo menos um agente.")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(agentes_pipeline) + 1

        relatorios = {}
        for i, agente_id in enumerate(agentes_pipeline):
            status_text.text(f"[{i+1}/{total}] {AGENTES[agente_id]['nome']}...")
            progress_bar.progress(i / total)
            try:
                rel = executar_agente_especialista(cid, agente_id, provedor, modelo, gem_id)
                relatorios[agente_id] = rel
                st.session_state[f"relatorio_{agente_id}"] = rel
            except Exception as e:
                st.error(f"Erro: {AGENTES[agente_id]['nome']}: {e}")
                relatorios[agente_id] = f"[ERRO: {e}]"

        status_text.text(f"[{total}/{total}] Agente Master...")
        progress_bar.progress((total - 1) / total)
        try:
            parecer = executar_master(cid, relatorios, provedor, modelo, gem_id)
            st.session_state["parecer_master"] = parecer
        except Exception as e:
            st.error(f"Erro Master: {e}")

        progress_bar.progress(1.0)
        status_text.text("Pipeline concluído!")
        st.balloons()


# ---------------------------------------------------------------------------
# ABA: Relatórios
# ---------------------------------------------------------------------------
def _aba_relatorios(cid: str):
    st.markdown("### 📊 Relatórios")

    relatorios_dir = os.path.join(pasta_cliente(cid), "relatorios")

    # Master
    parecer = st.session_state.get("parecer_master")
    parecer_path = os.path.join(relatorios_dir, "parecer_master.md")
    if not parecer and os.path.exists(parecer_path):
        with open(parecer_path, "r", encoding="utf-8") as f:
            parecer = f.read()

    if parecer:
        st.markdown("#### 🧠 Parecer Financeiro Integrado")
        with st.expander("Ver Parecer", expanded=True):
            st.markdown(parecer)
        st.download_button("📥 Download Parecer", data=parecer,
                           file_name=f"parecer_{cid}.md", mime="text/markdown")
        st.markdown("---")

    # Especialistas
    st.markdown("#### Relatórios dos Especialistas")
    tem = False
    for agente_id, agente in AGENTES.items():
        rel = st.session_state.get(f"relatorio_{agente_id}")
        if not rel:
            path = os.path.join(relatorios_dir, f"{agente_id}.md")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    rel = f.read()
        if rel:
            tem = True
            with st.expander(f"{agente['icone']} {agente['nome']}", expanded=False):
                st.markdown(rel)
                st.download_button(f"📥 Download", data=rel,
                                   file_name=f"{agente_id}_{cid}.md",
                                   mime="text/markdown", key=_k(f"dl_{agente_id}"))

    if not tem and not parecer:
        st.info("Nenhum relatório gerado. Vá para 'Executar Agentes'.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    sidebar()

    tela = st.session_state.get("tela", "🏠 Painel de Clientes")

    if tela == "🏠 Painel de Clientes":
        tela_painel_clientes()
    else:
        tela_ficha_cliente()


if __name__ == "__main__":
    main()
