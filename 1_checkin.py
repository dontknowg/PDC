import streamlit as st
import pandas as pd
from supabase import create_client, Client

st.set_page_config(page_title="Check-in | Projeto de Correções", layout="centered")

TABELA = "fila"


@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


supabase = init_connection()


def aluno_ja_na_fila(contato: str) -> bool:
    resultado = (
        supabase.table(TABELA)
        .select("id")
        .eq("status", "Aguardando")
        .eq("contato", contato)
        .execute()
    )
    return len(resultado.data) > 0


def buscar_posicao(id_aluno: str) -> int | None:
    fila = (
        supabase.table(TABELA)
        .select("id")
        .eq("status", "Aguardando")
        .order("data_hora", desc=False)
        .execute()
    )
    ids = [r["id"] for r in fila.data]
    if id_aluno in ids:
        return ids.index(id_aluno) + 1
    return None


# ---------- TELA DE CHECK-IN ----------

if "meu_id" not in st.session_state:
    st.title("Check-in da Fila")
    st.markdown("Preencha seus dados para entrar na fila de correção.")

    with st.form("form_checkin"):
        nome = st.text_input("Nome completo")
        contato = st.text_input("WhatsApp (ex: 82 99999-9999)")
        turma = st.selectbox("Sua turma", ["", "Turma Presencial Manhã", "Turma Presencial Noite"])
        tema = st.selectbox("Tema da redação", ["", "Eixo Temático 01: Saúde", "Eixo Temático 02: Tecnologia"])

        enviado = st.form_submit_button("Entrar na Fila", use_container_width=True)

    if enviado:
        if not all([nome, contato, turma, tema]):
            st.error("Preencha todos os campos antes de continuar.")
        elif aluno_ja_na_fila(contato):
            st.error("Este número de WhatsApp já está na fila. Aguarde ser chamado.")
        else:
            try:
                resposta = (
                    supabase.table(TABELA)
                    .insert({"nome": nome, "contato": contato, "turma": turma, "tema": tema})
                    .execute()
                )
                st.session_state["meu_id"] = resposta.data[0]["id"]
                st.rerun()
            except Exception:
                st.error("Não foi possível registrar seu check-in. Tente novamente em instantes.")

# ---------- TELA DE ACOMPANHAMENTO ----------

else:
    st.title("Acompanhamento da Fila")

    @st.fragment(run_every=8)
    def painel_posicao():
        posicao = buscar_posicao(st.session_state["meu_id"])

        if posicao is not None:
            st.metric(label="Sua posição atual", value=f"{posicao}o")
            if posicao == 1:
                st.success("Fique atento! Você é o próximo a ser chamado.")
            else:
                st.info(f"{'Há 1 pessoa' if posicao == 2 else f'Há {posicao - 1} pessoas'} na sua frente.")
        else:
            st.success("Chegou a sua vez! Dirija-se à mesa do corretor.")

    painel_posicao()

    st.divider()
    if st.button("Novo check-in"):
        del st.session_state["meu_id"]
        st.rerun()
