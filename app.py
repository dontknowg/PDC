import streamlit as st
import pandas as pd
from supabase import create_client, Client
import uuid
from datetime import datetime

# 1. Configuração da página
st.set_page_config(page_title="Fila - Projeto de Correções", layout="wide")

# 2. Conectando ao Supabase de forma segura
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

# 3. Funções que conversam com o seu Banco de Dados na nuvem
def carregar_dados(filtro_status=None):
    if filtro_status:
        response = supabase.table('fila').select('*').eq('status', filtro_status).order('data_hora', desc=False).execute()
    else:
        response = supabase.table('fila').select('*').order('data_hora', desc=True).execute()
    return pd.DataFrame(response.data)

def atualizar_status(id_aluno, novo_status):
    supabase.table('fila').update({'status': novo_status}).eq('id', id_aluno).execute()

def adicionar_aluno(nome, turma, tema):
    id_unico = str(uuid.uuid4())
    data_atual = datetime.now().isoformat()
    
    dados = {
        'id': id_unico,
        'data_hora': data_atual,
        'aluno': nome,
        'turma': turma,
        'tema': tema,
        'status': 'Aguardando'
    }
    supabase.table('fila').insert(dados).execute()

# ==========================================
# INTERFACE DO USUÁRIO
# ==========================================
st.title("Sistema de Fila - Projeto de Correções")

menu = st.sidebar.radio("Navegação", ["Check-in Aluno", "Área Restrita (Corretores)"])

if menu == "Check-in Aluno":
    st.header("Check-in para Correção")
    
    nome = st.text_input("Qual o seu nome?")
    turma = st.selectbox("Selecione sua Turma", ["", "Turma Presencial Manhã", "Turma Presencial Noite"])
    tema = st.selectbox("Qual tema você escreveu?", ["", "Eixo Temático 01: Saúde", "Eixo Temático 02: Tecnologia"])
    
    if st.button("Entrar na Fila", type="primary"):
        if nome and turma and tema:
            fila_atual = carregar_dados("Aguardando")
            if not fila_atual.empty and nome in fila_atual['aluno'].values:
                st.error("Você já está na fila! Aguarde ser chamado.")
            else:
                adicionar_aluno(nome, turma, tema)
                st.success(f"Pronto, {nome}! Você está na fila.")
        else:
            st.warning("Por favor, preencha todos os campos para entrar na fila.")

elif menu == "Área Restrita (Corretores)":
    st.sidebar.markdown("---")
    senha = st.sidebar.text_input("Senha de Acesso", type="password")
    
    # A senha provisória é corretor123
    if senha == "corretor123":
        aba_fila, aba_metricas = st.tabs(["Painel da Fila", "Banco de Dados e Métricas"])
        
        with aba_fila:
            st.header("Gestão da Fila em Tempo Real")
            fila_espera = carregar_dados("Aguardando")
            
            if fila_espera.empty:
                st.info("Nenhum aluno aguardando no momento. Fila zerada! 🎉")
            else:
                st.dataframe(fila_espera[['data_hora', 'aluno', 'turma', 'tema']], hide_index=True, use_container_width=True)
                
                proximo = fila_espera.iloc[0]
                st.markdown(f"### 📢 Chamar agora: **{proximo['aluno']}**")
                st.caption(f"Tema: {proximo['tema']} | Turma: {proximo['turma']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Concluir Atendimento"):
                        atualizar_status(proximo['id'], 'Concluído')
                        st.rerun()
                with col2:
                    if st.button("❌ Aluno Ausente (Pular)"):
                        atualizar_status(proximo['id'], 'Ausente')
                        st.rerun()
                        
            st.markdown("---")
            if st.button("🔄 Atualizar Fila Manualmente"):
                st.rerun()
                        
        with aba_metricas:
            st.header("Base de Dados Completa")
            todos_dados = carregar_dados()
            if not todos_dados.empty:
                st.dataframe(todos_dados, use_container_width=True)
                csv = todos_dados.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Exportar Dados (CSV)", data=csv, file_name='metricas.csv', mime='text/csv')
            else:
                st.info("Nenhum dado registrado ainda.")
    elif senha != "":
        st.error("Senha incorreta.")
