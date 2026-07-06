import streamlit as st
import pandas as pd
from supabase import create_client, Client
import urllib.parse
from datetime import datetime, date

st.set_page_config(page_title="Painel | Projeto de Correções", layout="wide")

st.markdown(
    """
    <style>
    #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

TABELA = "fila"


@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


supabase = init_connection()


def carregar_dados(filtro_status=None) -> pd.DataFrame:
    query = supabase.table(TABELA).select("*")
    if filtro_status:
        query = query.eq("status", filtro_status).order("data_hora", desc=False)
    else:
        query = query.order("data_hora", desc=True)
    response = query.execute()
    if response.data:
        return pd.DataFrame(response.data)
    return pd.DataFrame(columns=["id", "data_hora", "nome", "contato", "turma", "tema", "status"])


def atualizar_status(id_aluno: str, novo_status: str):
    supabase.table(TABELA).update({"status": novo_status}).eq("id", id_aluno).execute()


def contar_por_status(dados: pd.DataFrame, status: str) -> int:
    if dados.empty:
        return 0
    return len(dados[dados["status"] == status])


def gerar_link_whatsapp(contato: str, nome: str) -> str:
    numero = "".join(filter(str.isdigit, str(contato)))
    texto = f"Olá, {nome}! É a sua vez no Projeto de Correções. Dirija-se à mesa do corretor."
    return f"https://wa.me/55{numero}?text={urllib.parse.quote(texto)}"


# ---------- AUTENTICAÇÃO ----------

if not st.session_state.get("autenticado"):
    col_vazia_e, col_login, col_vazia_d = st.columns([1, 2, 1])
    with col_login:
        st.title("Acesso Restrito")
        st.markdown("Insira a senha para acessar o painel de correções.")
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

todos_dados = carregar_dados()

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
        fila_espera = carregar_dados("Aguardando")

        if fila_espera.empty:
            st.info("Nenhum aluno aguardando no momento.")
            return

        st.dataframe(
            fila_espera[["data_hora", "nome", "contato", "turma", "tema"]],
            column_config={
                "data_hora": st.column_config.DatetimeColumn("Horário", format="HH:mm:ss"),
                "nome": "Nome",
                "contato": "WhatsApp",
                "turma": "Turma",
                "tema": "Tema",
            },
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        proximo = fila_espera.iloc[0]

        st.subheader(f"Chamando: {proximo['nome']}")
        st.caption(f"{proximo['turma']}  |  {proximo['tema']}  |  {proximo['contato']}")

        col_wa, col_concluir, col_ausente = st.columns([1.2, 1, 1])
        with col_wa:
            st.link_button(
                "Chamar no WhatsApp",
                gerar_link_whatsapp(proximo["contato"], proximo["nome"]),
                use_container_width=True,
            )
        with col_concluir:
            if st.button("Concluir Atendimento", use_container_width=True):
                atualizar_status(proximo["id"], "Concluído")
                st.rerun()
        with col_ausente:
            if st.button("Marcar Ausente", use_container_width=True):
                atualizar_status(proximo["id"], "Ausente")
                st.rerun()

    exibir_fila()

    st.divider()
    st.subheader("Ações Recentes")

    recentes_query = (
        supabase.table(TABELA)
        .select("*")
        .in_("status", ["Concluído", "Ausente"])
        .order("data_hora", desc=True)
        .limit(5)
        .execute()
    )
    recentes = pd.DataFrame(recentes_query.data) if recentes_query.data else pd.DataFrame()

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
                    atualizar_status(row["id"], "Aguardando")
                    st.rerun()


with aba_dados:
    st.subheader("Base de Dados Completa")

    if todos_dados.empty:
        st.info("Nenhum dado registrado ainda.")
    else:
        col_filtro_status, col_filtro_turma, col_filtro_data = st.columns(3)
        with col_filtro_status:
            filtro_st = st.multiselect("Status", options=todos_dados["status"].unique().tolist(), default=todos_dados["status"].unique().tolist())
        with col_filtro_turma:
            filtro_turma = st.multiselect("Turma", options=todos_dados["turma"].unique().tolist(), default=todos_dados["turma"].unique().tolist())
        with col_filtro_data:
            datas_disponiveis = pd.to_datetime(todos_dados["data_hora"]).dt.date
            filtro_data = st.date_input("Período", value=(datas_disponiveis.min(), datas_disponiveis.max()))

        dados_filtrados = todos_dados.copy()
        dados_filtrados = dados_filtrados[dados_filtrados["status"].isin(filtro_st)]
        dados_filtrados = dados_filtrados[dados_filtrados["turma"].isin(filtro_turma)]

        if isinstance(filtro_data, tuple) and len(filtro_data) == 2:
            datas_col = pd.to_datetime(dados_filtrados["data_hora"]).dt.date
            dados_filtrados = dados_filtrados[(datas_col >= filtro_data[0]) & (datas_col <= filtro_data[1])]

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
