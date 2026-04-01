"""
Agente AI - CFP: Planejamento Financeiro Pessoal com Agentes de IA

Streamlit app que coordena múltiplos agentes especialistas de IA para
produzir uma análise financeira completa da vida de um cliente.

Usage:
    streamlit run app.py
"""

import os
import sys
import json

import streamlit as st

# Adicionar raiz do projeto ao path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.prompts.agentes import AGENTES
from src.agentes.engine import (
    criar_estrutura_cliente,
    carregar_info_qualitativa,
    salvar_info_qualitativa,
    listar_clientes,
    listar_documentos_agente,
    salvar_documento,
    importar_de_pasta,
    pasta_agente,
    executar_agente_especialista,
    executar_master,
    executar_pipeline_completo,
    pasta_cliente,
    PROVEDORES,
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

# CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .agent-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid #667eea;
    }
    .doc-count {
        background: #667eea;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.8rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SIDEBAR - Gestão de Clientes
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

        # API Keys
        if provedor == "claude":
            api_key = st.text_input(
                "Anthropic API Key",
                type="password",
                value=os.environ.get("ANTHROPIC_API_KEY", ""),
                help="Necessária para usar Claude",
            )
            if api_key:
                os.environ["ANTHROPIC_API_KEY"] = api_key
        else:
            api_key = st.text_input(
                "Google Gemini API Key",
                type="password",
                value=os.environ.get("GEMINI_API_KEY", ""),
                help="Necessária para usar Gemini",
            )
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key

            # Gem personalizado
            gem_id = st.text_input(
                "Gem ID (opcional)",
                value=st.session_state.get("gem_id", ""),
                help="ID de um Gem personalizado do Gemini. "
                     "Ex: tunedModels/meu-gem-abc123. "
                     "Deixe vazio para usar o modelo padrão.",
                placeholder="tunedModels/...",
            )
            st.session_state["gem_id"] = gem_id if gem_id.strip() else None

        st.markdown("---")

        # Seleção de cliente
        st.markdown("### 👤 Cliente")
        clientes = listar_clientes()

        if clientes:
            cliente_sel = st.selectbox(
                "Selecionar cliente",
                clientes,
                key="sel_cliente",
            )
            st.session_state["cliente_ativo"] = cliente_sel
        else:
            st.info("Nenhum cliente cadastrado.")
            st.session_state["cliente_ativo"] = None

        # Novo cliente
        with st.expander("Novo Cliente", expanded=not clientes):
            novo_nome = st.text_input("Nome do cliente", key="novo_cliente_nome")
            if st.button("Criar", key="btn_criar_cliente"):
                if novo_nome.strip():
                    criar_estrutura_cliente(novo_nome.strip())
                    st.session_state["cliente_ativo"] = novo_nome.strip()
                    st.success(f"Cliente '{novo_nome.strip()}' criado!")
                    st.rerun()
                else:
                    st.warning("Informe o nome do cliente.")

        st.markdown("---")

        # Modelo
        st.markdown("### ⚙️ Configurações")
        provedor_atual = st.session_state.get("provedor", "claude")
        modelos_disponiveis = PROVEDORES[provedor_atual]["modelos"]
        modelo = st.selectbox(
            "Modelo",
            modelos_disponiveis,
            index=0,
            help="Selecione o modelo do provedor escolhido.",
        )
        st.session_state["modelo"] = modelo

        # Info do cliente ativo
        cliente = st.session_state.get("cliente_ativo")
        if cliente:
            st.markdown("---")
            st.markdown(f"**Cliente ativo:** {cliente}")
            total_docs = 0
            for agente_id in AGENTES:
                total_docs += len(listar_documentos_agente(cliente, agente_id))
            st.caption(f"📄 {total_docs} documentos carregados")


# ---------------------------------------------------------------------------
# ABA 1: Informações Qualitativas
# ---------------------------------------------------------------------------
def aba_info_qualitativa():
    cliente = st.session_state.get("cliente_ativo")
    if not cliente:
        st.warning("Selecione ou crie um cliente na barra lateral.")
        return

    st.markdown("### 📋 Informações Qualitativas do Cliente")
    st.caption(
        "Estas informações servem como base de conhecimento para todos os agentes. "
        "Quanto mais detalhado, melhor a análise."
    )

    info = carregar_info_qualitativa(cliente)

    col1, col2 = st.columns(2)

    with col1:
        info["nome_completo"] = st.text_input(
            "Nome completo", value=info.get("nome_completo", ""), key="qi_nome"
        )
        info["idade"] = st.text_input(
            "Idade", value=info.get("idade", ""), key="qi_idade"
        )
        info["estado_civil"] = st.selectbox(
            "Estado civil",
            ["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"],
            index=["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"].index(
                info.get("estado_civil", "")
            ) if info.get("estado_civil", "") in ["", "Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)", "União Estável"] else 0,
            key="qi_estado_civil",
        )
        info["regime_de_bens"] = st.selectbox(
            "Regime de bens",
            ["", "Comunhão Parcial", "Comunhão Universal", "Separação Total", "Participação Final nos Aquestos"],
            index=["", "Comunhão Parcial", "Comunhão Universal", "Separação Total", "Participação Final nos Aquestos"].index(
                info.get("regime_de_bens", "")
            ) if info.get("regime_de_bens", "") in ["", "Comunhão Parcial", "Comunhão Universal", "Separação Total", "Participação Final nos Aquestos"] else 0,
            key="qi_regime",
        )
        info["filhos"] = st.text_area(
            "Filhos/Dependentes (nome, idade, situação)",
            value=info.get("filhos", ""),
            key="qi_filhos",
            height=100,
        )

    with col2:
        info["profissao"] = st.text_input(
            "Profissão/Atividade",
            value=info.get("profissao", ""),
            key="qi_profissao",
        )
        info["cidade_uf"] = st.text_input(
            "Cidade/UF",
            value=info.get("cidade_uf", ""),
            key="qi_cidade",
        )
        info["perfil_risco"] = st.selectbox(
            "Perfil de risco",
            ["", "Conservador", "Moderado", "Arrojado", "Agressivo"],
            index=["", "Conservador", "Moderado", "Arrojado", "Agressivo"].index(
                info.get("perfil_risco", "")
            ) if info.get("perfil_risco", "") in ["", "Conservador", "Moderado", "Arrojado", "Agressivo"] else 0,
            key="qi_perfil",
        )
        info["horizonte_temporal"] = st.text_input(
            "Horizonte temporal (ex: aposentadoria em 15 anos)",
            value=info.get("horizonte_temporal", ""),
            key="qi_horizonte",
        )
        info["objetivos_financeiros"] = st.text_area(
            "Objetivos financeiros",
            value=info.get("objetivos_financeiros", ""),
            key="qi_objetivos",
            height=100,
        )

    info["observacoes"] = st.text_area(
        "Observações gerais (informações extras relevantes para os agentes)",
        value=info.get("observacoes", ""),
        key="qi_obs",
        height=150,
        help="Inclua aqui qualquer contexto adicional: empresas do cliente, estruturas societárias, "
             "situações especiais, preocupações, etc.",
    )

    if st.button("💾 Salvar informações", key="btn_salvar_info", type="primary"):
        salvar_info_qualitativa(cliente, info)
        st.success("Informações salvas com sucesso!")


# ---------------------------------------------------------------------------
# ABA 2: Documentos (por agente)
# ---------------------------------------------------------------------------
def aba_documentos():
    cliente = st.session_state.get("cliente_ativo")
    if not cliente:
        st.warning("Selecione ou crie um cliente na barra lateral.")
        return

    st.markdown("### 📄 Gestão de Documentos")
    st.caption(
        "Cada agente especialista tem sua própria pasta de documentos. "
        "Faça upload ou importe de uma pasta existente."
    )

    for agente_id, agente in AGENTES.items():
        docs = listar_documentos_agente(cliente, agente_id)
        doc_count = len(docs)

        with st.expander(
            f"{agente['icone']} {agente['nome']} — {doc_count} doc(s)",
            expanded=False,
        ):
            st.caption(agente["descricao"])

            # Documentos sugeridos
            st.markdown("**Documentos sugeridos:**")
            for sug in agente["documentos_sugeridos"]:
                st.markdown(f"- {sug}")

            st.markdown("---")

            col_upload, col_pasta = st.columns(2)

            # Upload de arquivos
            with col_upload:
                st.markdown("**Upload de arquivos**")
                uploaded = st.file_uploader(
                    "Arraste ou selecione",
                    accept_multiple_files=True,
                    key=f"upload_{agente_id}",
                    type=["pdf", "docx", "xlsx", "txt", "csv", "png", "jpg", "jpeg"],
                )
                if uploaded:
                    for f in uploaded:
                        salvar_documento(cliente, agente_id, f.name, f.getvalue())
                    st.success(f"{len(uploaded)} arquivo(s) salvo(s)!")
                    st.rerun()

            # Importar de pasta
            with col_pasta:
                st.markdown("**Importar de pasta**")
                pasta_input = st.text_input(
                    "Caminho da pasta",
                    key=f"pasta_{agente_id}",
                    placeholder="C:/Documentos/Cliente/...",
                )
                if st.button("Importar", key=f"btn_import_{agente_id}"):
                    if pasta_input and os.path.isdir(pasta_input):
                        importados = importar_de_pasta(cliente, agente_id, pasta_input)
                        if importados:
                            st.success(f"{len(importados)} arquivo(s) importado(s)!")
                            st.rerun()
                        else:
                            st.warning("Nenhum arquivo encontrado na pasta.")
                    else:
                        st.error("Pasta não encontrada.")

            # Lista de documentos existentes
            if docs:
                st.markdown("**Documentos carregados:**")
                for doc_name in docs:
                    col_doc, col_del = st.columns([5, 1])
                    with col_doc:
                        ext = os.path.splitext(doc_name)[1].lower()
                        icon = {"pdf": "📕", "docx": "📘", "xlsx": "📗", "txt": "📄"}.get(
                            ext.lstrip("."), "📎"
                        )
                        st.markdown(f"{icon} `{doc_name}`")
                    with col_del:
                        if st.button("🗑️", key=f"del_{agente_id}_{doc_name}"):
                            caminho = os.path.join(
                                pasta_agente(cliente, agente_id), doc_name
                            )
                            if os.path.exists(caminho):
                                os.remove(caminho)
                                st.rerun()


# ---------------------------------------------------------------------------
# ABA 3: Executar Agentes
# ---------------------------------------------------------------------------
def aba_executar():
    cliente = st.session_state.get("cliente_ativo")
    if not cliente:
        st.warning("Selecione ou crie um cliente na barra lateral.")
        return

    modelo = st.session_state.get("modelo", "claude-sonnet-4-20250514")
    provedor = st.session_state.get("provedor", "claude")
    gem_id = st.session_state.get("gem_id")

    st.markdown("### 🤖 Executar Agentes")

    # Mostrar provedor ativo
    provedor_nome = PROVEDORES[provedor]["nome"]
    gem_label = f" | Gem: `{gem_id}`" if gem_id else ""
    st.info(f"**Provedor:** {provedor_nome} | **Modelo:** `{modelo}`{gem_label}")

    st.caption(
        "Execute agentes individualmente ou o pipeline completo. "
        "O Agente Master consolida as análises de todos os especialistas."
    )

    # Verificar API key
    env_var = "ANTHROPIC_API_KEY" if provedor == "claude" else "GEMINI_API_KEY"
    if not os.environ.get(env_var):
        st.error(f"Configure a API Key ({env_var}) na barra lateral.")
        return

    # Status dos documentos por agente
    st.markdown("#### Status dos Agentes")
    cols = st.columns(3)
    agentes_com_docs = []

    for i, (agente_id, agente) in enumerate(AGENTES.items()):
        docs = listar_documentos_agente(cliente, agente_id)
        with cols[i % 3]:
            status = "✅" if docs else "⚠️"
            st.markdown(
                f"{status} {agente['icone']} **{agente['nome']}**  \n"
                f"📄 {len(docs)} documento(s)"
            )
            if docs:
                agentes_com_docs.append(agente_id)

    st.markdown("---")

    # Execução individual
    st.markdown("#### Executar Agente Individual")
    col_sel, col_exec = st.columns([3, 1])

    with col_sel:
        opcoes = {f"{AGENTES[a]['icone']} {AGENTES[a]['nome']}": a for a in AGENTES}
        sel = st.selectbox("Selecionar agente", list(opcoes.keys()), key="sel_agente_exec")
        agente_sel = opcoes[sel]

    with col_exec:
        st.markdown("")  # spacer
        st.markdown("")
        if st.button("▶️ Executar", key="btn_exec_individual", type="primary"):
            with st.spinner(f"Executando {AGENTES[agente_sel]['nome']}..."):
                try:
                    relatorio = executar_agente_especialista(
                        cliente, agente_sel, provedor, modelo, gem_id
                    )
                    st.session_state[f"relatorio_{agente_sel}"] = relatorio
                    st.success(f"{AGENTES[agente_sel]['nome']} concluído!")
                except Exception as e:
                    st.error(f"Erro: {e}")

    # Mostrar relatório individual se existir
    if st.session_state.get(f"relatorio_{agente_sel}"):
        with st.expander(f"📊 Relatório: {AGENTES[agente_sel]['nome']}", expanded=True):
            st.markdown(st.session_state[f"relatorio_{agente_sel}"])

    st.markdown("---")

    # Pipeline completo
    st.markdown("#### 🚀 Pipeline Completo (Todos os Agentes + Master)")
    st.caption(
        "Executa todos os agentes especialistas e depois o Agente Master "
        "para consolidar as análises em um parecer integrado."
    )

    # Seleção de quais agentes incluir
    agentes_pipeline = []
    cols_check = st.columns(3)
    for i, (agente_id, agente) in enumerate(AGENTES.items()):
        with cols_check[i % 3]:
            checked = st.checkbox(
                f"{agente['icone']} {agente['nome']}",
                value=True,
                key=f"check_{agente_id}",
            )
            if checked:
                agentes_pipeline.append(agente_id)

    if st.button("🚀 Executar Pipeline Completo", key="btn_pipeline", type="primary"):
        if not agentes_pipeline:
            st.warning("Selecione pelo menos um agente.")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()
        total_steps = len(agentes_pipeline) + 1  # +1 para o master

        relatorios = {}
        for i, agente_id in enumerate(agentes_pipeline):
            status_text.text(f"[{i+1}/{total_steps}] Executando {AGENTES[agente_id]['nome']}...")
            progress_bar.progress((i) / total_steps)

            try:
                relatorio = executar_agente_especialista(
                    cliente, agente_id, provedor, modelo, gem_id
                )
                relatorios[agente_id] = relatorio
                st.session_state[f"relatorio_{agente_id}"] = relatorio
            except Exception as e:
                st.error(f"Erro no {AGENTES[agente_id]['nome']}: {e}")
                relatorios[agente_id] = f"[ERRO: {e}]"

        # Executar Master
        status_text.text(f"[{total_steps}/{total_steps}] Agente Master consolidando...")
        progress_bar.progress((total_steps - 1) / total_steps)

        try:
            parecer = executar_master(cliente, relatorios, provedor, modelo, gem_id)
            st.session_state["parecer_master"] = parecer
        except Exception as e:
            st.error(f"Erro no Master: {e}")
            parecer = None

        progress_bar.progress(1.0)
        status_text.text("Pipeline concluído!")
        st.balloons()


# ---------------------------------------------------------------------------
# ABA 4: Relatórios
# ---------------------------------------------------------------------------
def aba_relatorios():
    cliente = st.session_state.get("cliente_ativo")
    if not cliente:
        st.warning("Selecione ou crie um cliente na barra lateral.")
        return

    st.markdown("### 📊 Relatórios")

    # Carregar relatórios salvos em disco
    relatorios_dir = os.path.join(pasta_cliente(cliente), "relatorios")

    # Parecer Master
    parecer_path = os.path.join(relatorios_dir, "parecer_master.md")
    parecer = st.session_state.get("parecer_master")
    if not parecer and os.path.exists(parecer_path):
        with open(parecer_path, "r", encoding="utf-8") as f:
            parecer = f.read()

    if parecer:
        st.markdown("#### 🧠 Parecer Financeiro Integrado (Master)")
        with st.expander("Ver Parecer Completo", expanded=True):
            st.markdown(parecer)

        # Botão de download
        st.download_button(
            label="📥 Download Parecer (Markdown)",
            data=parecer,
            file_name=f"parecer_{cliente}.md",
            mime="text/markdown",
        )
        st.markdown("---")

    # Relatórios dos especialistas
    st.markdown("#### Relatórios dos Especialistas")

    tem_relatorio = False
    for agente_id, agente in AGENTES.items():
        # Tentar da sessão ou do disco
        relatorio = st.session_state.get(f"relatorio_{agente_id}")
        if not relatorio:
            path = os.path.join(relatorios_dir, f"{agente_id}.md")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    relatorio = f.read()

        if relatorio:
            tem_relatorio = True
            with st.expander(f"{agente['icone']} {agente['nome']}", expanded=False):
                st.markdown(relatorio)
                st.download_button(
                    label=f"📥 Download",
                    data=relatorio,
                    file_name=f"{agente_id}_{cliente}.md",
                    mime="text/markdown",
                    key=f"dl_{agente_id}",
                )

    if not tem_relatorio and not parecer:
        st.info(
            "Nenhum relatório gerado ainda. "
            "Vá para a aba 'Executar Agentes' para gerar as análises."
        )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    sidebar()

    cliente = st.session_state.get("cliente_ativo")

    if not cliente:
        st.markdown('<p class="main-header">🧠 Agente AI - CFP</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="sub-header">Planejamento Financeiro Pessoal com Inteligência Artificial</p>',
            unsafe_allow_html=True,
        )

        st.markdown("""
        ### Como funciona

        1. **Crie um cliente** na barra lateral
        2. **Preencha as informações qualitativas** — dados básicos e objetivos
        3. **Carregue documentos** em cada área especializada
        4. **Execute os agentes** — cada um analisa sua área com profundidade
        5. **O Agente Master** consolida tudo em um parecer financeiro integrado

        ### Agentes Especialistas
        """)

        cols = st.columns(3)
        for i, (agente_id, agente) in enumerate(AGENTES.items()):
            with cols[i % 3]:
                st.markdown(
                    f"**{agente['icone']} {agente['nome']}**  \n"
                    f"{agente['descricao']}"
                )
        return

    # Tabs do cliente
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Informações Qualitativas",
        "📄 Documentos",
        "🤖 Executar Agentes",
        "📊 Relatórios",
    ])

    with tab1:
        aba_info_qualitativa()
    with tab2:
        aba_documentos()
    with tab3:
        aba_executar()
    with tab4:
        aba_relatorios()


if __name__ == "__main__":
    main()
