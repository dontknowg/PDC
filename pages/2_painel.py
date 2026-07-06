import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, date

st.set_page_config(page_title="Painel | Projeto de Correções", layout="wide")

st.markdown(
    """
    <style>
    #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* iOS: fonte >= 16px evita o zoom automático ao focar campos */
    .stTextInput input,
    div[data-baseweb="select"] input {
        font-size: 16px !important;
    }

    /* No celular: os 4 indicadores viram 2x2 (dashboard compacto) */
    @media (max-width: 640px) {
        [data-testid="stColumn"]:has([data-testid="stMetric"]) {
            flex: 1 1 46% !important;
            min-width: 46% !important;
        }
    }

    /* Tela de login centralizada (funciona em notebook e celular) */
    .login-wrap {
        max-width: 420px;
        margin: 8vh auto 0.5rem auto;
    }
    .login-wrap h1 { font-size: 2rem; margin-bottom: 0.2rem; }
    .login-wrap p { color: #9a9a9a; margin-bottom: 0; }
    [data-testid="stForm"] {
        max-width: 420px;
        margin: 0 auto;
        border: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

TABELA = "fila"


@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


supabase = init_connection()


COLUNAS = ["id", "data_hora", "nome", "contato", "turma", "tema", "status"]


def _executar(query, tentativas: int = 2):
    """Executa uma query do Supabase com nova tentativa em falhas transitórias
    de rede (timeouts/conexão), comuns em conexões móveis."""
    ultimo_erro = None
    for _ in range(tentativas):
        try:
            return query.execute()
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
    raise ultimo_erro


def carregar_dados(filtro_status=None) -> pd.DataFrame:
    query = supabase.table(TABELA).select("*")
    if filtro_status:
        query = query.eq("status", filtro_status).order("data_hora", desc=False)
    else:
        query = query.order("data_hora", desc=True)
    response = _executar(query)
    if response.data:
        return pd.DataFrame(response.data)
    return pd.DataFrame(columns=COLUNAS)


def atualizar_status(id_aluno: str, novo_status: str) -> bool:
    payload = {"status": novo_status}
    # Ao voltar para a fila (desfazer), zera o "chamado" para não reabrir
    # o alerta antigo de "é a sua vez" na tela do aluno.
    if novo_status == "Aguardando":
        payload["chamado"] = False
    try:
        _executar(supabase.table(TABELA).update(payload).eq("id", id_aluno))
        return True
    except Exception:
        st.toast("Falha ao atualizar. Tente novamente.", icon="⚠️")
        return False


def chamar_aluno(id_aluno: str) -> bool:
    """Marca o aluno como chamado — a tela dele exibirá 'É A SUA VEZ'."""
    try:
        _executar(supabase.table(TABELA).update({"chamado": True}).eq("id", id_aluno))
        return True
    except Exception:
        st.toast("Falha ao chamar. Tente novamente.", icon="⚠️")
        return False


def contar_por_status(dados: pd.DataFrame, status: str) -> int:
    if dados.empty:
        return 0
    return len(dados[dados["status"] == status])


# ---------- AUTENTICAÇÃO ----------

if not st.session_state.get("autenticado"):
    st.markdown(
        """
        <div class="login-wrap">
            <h1>Acesso Restrito</h1>
            <p>Insira a senha para acessar o painel de correções.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("form_login"):
        senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Senha de acesso")
        if st.form_submit_button("Entrar", use_container_width=True):
            if senha == st.secrets.get("SENHA_CORRETOR", "corretor123"):
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()


# ---------- PAINEL DO CORRETOR ----------

st.title("Painel de Correções")

try:
    todos_dados = carregar_dados()
except Exception:
    st.error("Não foi possível conectar ao banco de dados agora. Verifique a conexão e atualize a página.")
    st.stop()

hoje = date.today().isoformat()
dados_hoje = todos_dados[todos_dados["data_hora"].str.startswith(hoje)] if not todos_dados.empty else pd.DataFrame()

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Na fila agora", contar_por_status(todos_dados, "Aguardando"))
col_m2.metric("Corrigidos hoje", contar_por_status(dados_hoje, "Concluído"))
col_m3.metric("Ausentes hoje", contar_por_status(dados_hoje, "Ausente"))
col_m4.metric("Total hoje", len(dados_hoje))

st.divider()

aba_fila, aba_dados = st.tabs(["Fila de Atendimento", "Base de Dados"])

with aba_fila:

    @st.fragment(run_every=10)
    def exibir_fila():
        try:
            fila_espera = carregar_dados("Aguardando")
        except Exception:
            st.info("Reconectando ao banco de dados... a fila será atualizada em instantes.")
            return

        if fila_espera.empty:
            st.info("Nenhum aluno aguardando no momento.")
            return

        st.caption(
            f"{len(fila_espera)} aluno(s) na fila. Cada corretor pode chamar um aluno "
            "diferente — não é preciso concluir para chamar o próximo."
        )

        # Lista ordenada por chegada. Cada aluno tem os próprios botões, então
        # vários corretores chamam/atendem em paralelo.
        for ordem, (_, aluno) in enumerate(fila_espera.iterrows(), start=1):
            aid = aluno["id"]
            chamado = bool(aluno.get("chamado", False))
            with st.container(border=True):
                col_info, col_acoes = st.columns([2, 3])
                with col_info:
                    marcador = "  ·  🔔 Chamado" if chamado else ""
                    st.markdown(f"**{ordem}. {aluno['nome']}**{marcador}")
                    st.caption(f"{aluno['turma']}  |  {aluno['tema']}  |  {aluno['contato']}")
                with col_acoes:
                    b_chamar, b_concluir, b_ausente = st.columns(3)
                    if b_chamar.button("Chamar", key=f"chamar_{aid}", type="primary",
                                       disabled=chamado, use_container_width=True):
                        if chamar_aluno(aid):
                            st.rerun()
                    if b_concluir.button("Concluir", key=f"concluir_{aid}", use_container_width=True):
                        if atualizar_status(aid, "Concluído"):
                            st.rerun()
                    if b_ausente.button("Ausente", key=f"ausente_{aid}", use_container_width=True):
                        if atualizar_status(aid, "Ausente"):
                            st.rerun()

    exibir_fila()

    st.divider()
    st.subheader("Ações Recentes")

    try:
        recentes_query = _executar(
            supabase.table(TABELA)
            .select("*")
            .in_("status", ["Concluído", "Ausente"])
            .order("data_hora", desc=True)
            .limit(5)
        )
        recentes = pd.DataFrame(recentes_query.data) if recentes_query.data else pd.DataFrame()
    except Exception:
        recentes = pd.DataFrame()

    if recentes.empty:
        st.caption("Nenhuma ação registrada ainda.")
    else:
        for _, row in recentes.iterrows():
            col_info, col_acao = st.columns([4, 1])
            with col_info:
                rotulo = "Concluído" if row["status"] == "Concluído" else "Ausente"
                st.markdown(f"**{row['nome']}** — {rotulo}")
            with col_acao:
                if st.button("Desfazer", key=f"desfazer_{row['id']}", use_container_width=True):
                    if atualizar_status(row["id"], "Aguardando"):
                        st.rerun()


with aba_dados:
    st.subheader("Base de Dados Completa")

    if todos_dados.empty:
        st.info("Nenhum dado registrado ainda.")
    else:
        col_filtro_status, col_filtro_turma = st.columns(2)
        with col_filtro_status:
            filtro_st = st.multiselect("Status", options=todos_dados["status"].unique().tolist(), default=todos_dados["status"].unique().tolist())
        with col_filtro_turma:
            filtro_turma = st.multiselect("Turma", options=todos_dados["turma"].unique().tolist(), default=todos_dados["turma"].unique().tolist())

        datas_disponiveis = pd.to_datetime(todos_dados["data_hora"]).dt.date
        col_modo, col_data = st.columns([1, 2])
        with col_modo:
            modo_data = st.radio("Filtrar por", ["Dia único", "Intervalo"], horizontal=True, label_visibility="collapsed")
        with col_data:
            if modo_data == "Dia único":
                dia_selecionado = st.date_input("Data", value=date.today())
                data_inicio = dia_selecionado
                data_fim = dia_selecionado
            else:
                intervalo = st.date_input("Período", value=(datas_disponiveis.min(), datas_disponiveis.max()))
                if isinstance(intervalo, tuple) and len(intervalo) == 2:
                    data_inicio, data_fim = intervalo
                else:
                    data_inicio = intervalo if not isinstance(intervalo, tuple) else intervalo[0]
                    data_fim = data_inicio

        dados_filtrados = todos_dados.copy()
        dados_filtrados = dados_filtrados[dados_filtrados["status"].isin(filtro_st)]
        dados_filtrados = dados_filtrados[dados_filtrados["turma"].isin(filtro_turma)]

        datas_col = pd.to_datetime(dados_filtrados["data_hora"]).dt.date
        dados_filtrados = dados_filtrados[(datas_col >= data_inicio) & (datas_col <= data_fim)]

        st.caption(f"{len(dados_filtrados)} registro(s) encontrado(s)")

        st.dataframe(
            dados_filtrados,
            column_config={
                "id": None,
                "data_hora": st.column_config.DatetimeColumn("Data/Hora", format="DD/MM/YYYY HH:mm"),
                "nome": "Nome",
                "contato": "WhatsApp",
                "turma": "Turma",
                "tema": "Tema",
                "status": "Status",
            },
            hide_index=True,
            use_container_width=True,
        )

        csv = dados_filtrados.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Exportar CSV",
            data=csv,
            file_name=f"correcoes_{date.today().isoformat()}.csv",
            mime="text/csv",
        )
