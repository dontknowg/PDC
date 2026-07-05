import streamlit as st
import pandas as pd
from supabase import create_client, Client
import urllib.parse

st.set_page_config(page_title="Painel | Projeto de Correções", layout="wide")

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

# ---------- AUTENTICAÇÃO ----------

if not st.session_state.get("autenticado"):
    st.title("Acesso Restrito")
    senha = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar"):
        if senha == st.secrets.get("SENHA_CORRETOR", "corretor123"):
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()

# ---------- PAINEL DO CORRETOR ----------

st.title("Painel de Correções")

aba_fila, aba_dados = st.tabs(["Fila de Atendimento", "Base de Dados"])

with aba_fila:
    # O fragmento faz a fila atualizar sozinha, sem piscar o resto da tela
    @st.fragment(run_every=10)
    def exibir_fila_dinamica():
        fila_espera = carregar_dados("Aguardando")

        if fila_espera.empty:
            st.info("Nenhum aluno aguardando no momento.")
        else:
            st.dataframe(
                fila_espera[["data_hora", "nome", "contato", "turma", "tema"]],
                hide_index=True,
                use_container_width=True,
            )

            st.divider()
            proximo = fila_espera.iloc[0]
            st.markdown(f"### 🎯 Próximo da fila: **{proximo['nome']}**")
            st.caption(f"Tema: {proximo['tema']} | Turma: {proximo['turma']} | Contato: {proximo['contato']}")

            # Botão Inteligente do WhatsApp
            numero_limpo = ''.join(filter(str.isdigit, str(proximo['contato'])))
            mensagem = f"Olá, {proximo['nome']}! É a sua vez no Projeto de Correções. Dirija-se à mesa."
            link_wa = f"https://wa.me/55{numero_limpo}?text={urllib.parse.quote(mensagem)}"
            
            st.link_button("📲 Chamar no WhatsApp", link_wa, type="primary")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Concluir Atendimento", use_container_width=True):
                    atualizar_status(proximo["id"], "Concluído")
                    st.rerun()
            with col2:
                if st.button("❌ Aluno Ausente", use_container_width=True):
                    atualizar_status(proximo["id"], "Ausente")
                    st.rerun()

    # Chama a função fragmentada para rodar
    exibir_fila_dinamica()

    st.divider()
    st.subheader("Ações Recentes")
    recentes_query = (
        supabase.table(TABELA)
        .select("*")
        .in_("status", ["Concluído", "Ausente"])
        .order("data_hora", desc=True)
        .limit(3)
        .execute()
    )
    recentes = pd.DataFrame(recentes_query.data) if recentes_query.data else pd.DataFrame()

    if not recentes.empty:
        for _, row in recentes.iterrows():
            col_texto, col_botao = st.columns([3, 1])
            col_texto.write(f"**{row['nome']}** — {row['status']}")
            if col_botao.button("Desfazer", key=f"desfazer_{row['id']}"):
                atualizar_status(row["id"], "Aguardando")
                st.rerun()

with aba_dados:
    st.subheader("Base de Dados Completa")
    todos_dados = carregar_dados()
    if not todos_dados.empty:
        st.dataframe(todos_dados, use_container_width=True)
        csv = todos_dados.to_csv(index=False).encode("utf-8")
        st.download_button("Exportar CSV", data=csv, file_name="metricas_correcoes.csv", mime="text/csv")
    else:
        st.info("Nenhum dado registrado ainda.")
