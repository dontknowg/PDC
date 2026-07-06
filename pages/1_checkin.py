import streamlit as st
import pandas as pd
from supabase import create_client, Client
from alunos import BASE_ALUNOS
from temas import TEMAS_POR_LIVRO

st.set_page_config(page_title="Check-in | Projeto de Correções", layout="centered")

TABELA = "fila"

st.markdown(
    """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&family=Nunito:wght@400;600;700&display=swap" rel="stylesheet">

    <style>
    :root {
        --bt-bg:      #000000;
        --bt-surface: #141414;
        --bt-surface2:#1e1e1e;
        --bt-border:  rgba(255,255,255,0.08);
        --bt-text:    #ffffff;
        --bt-muted:   #a9a9a9;
        --bt-accent:  #b026ff;   /* magenta/roxo da marca */
        --bt-accent2: #e0219a;
        --bt-green:   #25d366;   /* WhatsApp */
    }

    /* ---- Fundo geral ---- */
    .stApp {
        background: var(--bt-bg);
        color: var(--bt-text);
        font-family: 'Nunito', sans-serif;
    }
    .block-container {
        padding-top: 3.5rem;
        padding-bottom: 4rem;
        max-width: 640px;
    }

    /* ---- Tipografia pesada arredondada ---- */
    h1, h2, h3 {
        font-family: 'Baloo 2', cursive !important;
        font-weight: 800 !important;
        letter-spacing: 0.3px;
        color: var(--bt-text) !important;
    }
    h1 { font-size: 2.4rem !important; }

    p, label, .stMarkdown { color: var(--bt-text); }

    /* ---- Labels dos campos ---- */
    label, .stTextInput label, .stSelectbox label {
        font-family: 'Baloo 2', cursive !important;
        font-weight: 600 !important;
        color: var(--bt-muted) !important;
        font-size: 0.95rem !important;
    }
    
    /* ---- Inputs ---- */
    
    /* Regra apenas para o campo de texto digitável (WhatsApp) */
    .stTextInput input {
        background: var(--bt-surface) !important;
        color: var(--bt-text) !important;
        border: 1px solid var(--bt-border) !important;
        border-radius: 14px !important;
        padding: 12px 14px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.35) !important;
        font-size: 1rem !important;
    }

    /* Regra apenas para as caixas de seleção (Nome, Turma e Tema) */
    .stSelectbox div[data-baseweb="select"] > div {
        background: var(--bt-surface) !important;
        color: var(--bt-text) !important;
        border: 1px solid var(--bt-border) !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.35) !important;
    }

    /* Efeitos de brilho ao clicar */
    .stTextInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within {
        border-color: var(--bt-accent) !important;
        box-shadow: 0 0 0 3px rgba(176,38,255,0.25) !important;
    }
    
    .stTextInput input::placeholder { color: #6b6b6b; }

    /* dropdown popover */
    div[data-baseweb="popover"] div {
        background: var(--bt-surface) !important;
        color: var(--bt-text) !important;
    }

    /* ---- Botões largos, arredondados, com sombra suave ---- */
    .stButton > button,
    .stFormSubmitButton > button {
        width: 100%;
        background: linear-gradient(135deg, var(--bt-accent) 0%, var(--bt-accent2) 100%) !important;
        color: #ffffff !important;
        font-family: 'Baloo 2', cursive !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        border: none !important;
        border-radius: 16px !important;
        padding: 0.85rem 1rem !important;
        box-shadow: 0 8px 24px rgba(176,38,255,0.35) !important;
        transition: transform .12s ease, box-shadow .12s ease !important;
    }
    .stButton > button:hover,
    .stFormSubmitButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 30px rgba(176,38,255,0.5) !important;
        color: #ffffff !important;
    }

    /* botão secundário "Novo check-in" — contorno */
    .secondary-btn .stButton > button {
        background: transparent !important;
        border: 1.5px solid var(--bt-border) !important;
        box-shadow: none !important;
        color: var(--bt-muted) !important;
    }
    .secondary-btn .stButton > button:hover {
        border-color: var(--bt-accent) !important;
        color: #ffffff !important;
        box-shadow: 0 6px 18px rgba(176,38,255,0.25) !important;
    }

    /* ---- Cartão / container ---- */
    .bt-card {
        background: var(--bt-surface);
        border: 1px solid var(--bt-border);
        border-radius: 22px;
        padding: 2rem 1.8rem;
        box-shadow: 0 18px 50px rgba(0,0,0,0.6);
        margin-bottom: 1.2rem;
    }

    /* ---- Cabeçalho da marca ---- */
    .bt-brand {
        display: flex; align-items: center; gap: 12px;
        margin-bottom: 0.4rem;
    }
    .bt-logo {
        width: 46px; height: 46px; border-radius: 50%;
        background: #ffffff; color: #000;
        display: flex; align-items: center; justify-content: center;
        font-family: 'Baloo 2', cursive; font-weight: 800; font-size: 1.5rem;
        box-shadow: 0 4px 14px rgba(255,255,255,0.15);
    }
    .bt-brandname {
        font-family: 'Baloo 2', cursive; font-weight: 800;
        font-size: 1.35rem; letter-spacing: 2px; color:#fff;
    }
    .bt-brandsub {
        font-size: 0.62rem; letter-spacing: 4px; color: var(--bt-muted);
        margin-top: -4px;
    }

    /* ---- Métrica de posição ---- */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(176,38,255,0.18), rgba(224,33,154,0.10));
        border: 1px solid rgba(176,38,255,0.35);
        border-radius: 22px;
        padding: 1.6rem 1.2rem;
        text-align: center;
        box-shadow: 0 14px 40px rgba(176,38,255,0.18);
    }
    [data-testid="stMetricLabel"] {
        justify-content: center;
    }
    [data-testid="stMetricLabel"] p {
        font-family: 'Baloo 2', cursive !important;
        font-weight: 600 !important;
        color: var(--bt-muted) !important;
        font-size: 1rem !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'Baloo 2', cursive !important;
        font-weight: 800 !important;
        font-size: 3.4rem !important;
        color: #fff !important;
        justify-content: center;
    }

    /* ---- Alertas (success/info/error) ---- */
    .stAlert {
        border-radius: 16px !important;
        border: none !important;
        font-family: 'Nunito', sans-serif;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }
    div[data-baseweb="notification"] { border-radius: 16px !important; }

    /* ---- Divisor ---- */
    hr { border-color: var(--bt-border) !important; }

    /* Esconde o menu/rodapé padrão do Streamlit */
    #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- BLOCO DE MARCA (reutilizável) ----------

def cabecalho_marca():
    # Substitua a URL abaixo pelo link direto da logo oficial do Batinga
    url_logo = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png" 
    
    st.markdown(
        f"""
        <div class="bt-brand">
            <img src="{url_logo}" style="width: 48px; height: 48px; border-radius: 50%; object-fit: cover; box-shadow: 0 4px 14px rgba(255,255,255,0.15);">
            <div>
                <div class="bt-brandname">BATINGA</div>
                <div class="bt-brandsub">PROJETO DE CORREÇÕES</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
#  MOTOR — LOGICA DA FILA
# ============================================================

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


# ---------- PREPARAÇÃO DOS TEMAS ----------
# Junta todos os temas de todos os livros em uma única lista plana para o aluno
TODOS_TEMAS = [tema for temas in TEMAS_POR_LIVRO.values() for tema in temas]

# ---------- TELA DE CHECK-IN ----------

if "meu_id" not in st.session_state:
    with st.container():
        cabecalho_marca()
        st.title("Check-in da Fila")
        st.markdown("Preencha seus dados para entrar na fila de correção.")

    # 1. Pesquisa do Aluno
    LISTA_NOMES = list(BASE_ALUNOS.keys()) + ["Outro (Não encontrei meu nome)"]
    
    nome_selecionado = st.selectbox(
        "Nome completo (Comece a digitar para buscar)", 
        LISTA_NOMES,
        index=None,
        placeholder="Selecione ou digite seu nome..."
    )
    
    # 2. A lógica invisível do aluno
    if nome_selecionado == "Outro (Não encontrei meu nome)":
        nome = st.text_input("Digite seu nome completo")
        contato = st.text_input("WhatsApp (apenas números com DDD)")
        turma = st.selectbox(
            "Sua turma", 
            [
                "SEMI PRO", "TERÇA-TARDE", "TERÇA-NOITE", "QUARTA-PRO", 
                "QUARTA-TARDE", "QUARTA-ONLINE", "ARAPIRACA", 
                "SEXTA-MANHÃ", "SEXTA-TARDE", "CONSULTORIA"
            ],
            index=None,
            placeholder="Selecione sua turma..."
        )
    elif nome_selecionado is not None:
        nome = nome_selecionado
        dados_aluno = BASE_ALUNOS.get(nome, {})
        contato = dados_aluno.get("contato", "")
        turma = dados_aluno.get("turma", "Não identificada")
    else:
        nome = ""
        contato = ""
        turma = ""

    # 3. Campo Único de Tema para o Aluno (puxando todos os temas do arquivo novo)
    tema_selecionado = st.selectbox(
        "Tema da redação (Comece a digitar para buscar)", 
        TODOS_TEMAS,
        index=None,
        placeholder="Selecione o tema..."
    )

    enviado = st.button("Entrar na Fila", use_container_width=True)

    if enviado:
        if not all([nome, contato, turma, tema_selecionado]):
            st.error("Preencha todos os dados antes de continuar.")
        elif aluno_ja_na_fila(contato):
            st.error("Você já está na fila de espera. Aguarde ser chamado.")
        else:
            try:
                # 4. A mágica invisível: Descobrimos de qual livro é esse tema
                livro_do_tema = next((livro for livro, temas in TEMAS_POR_LIVRO.items() if tema_selecionado in temas), "Outro")
                
                # Montamos o texto perfeito para salvar no seu banco de dados
                tema_final = f"{livro_do_tema} - {tema_selecionado}"
                
                resposta = (
                    supabase.table(TABELA)
                    .insert({"nome": nome, "contato": contato, "turma": turma, "tema": tema_final})
                    .execute()
                )
                st.session_state["meu_id"] = resposta.data[0]["id"]
                st.rerun()
            except Exception:
                st.error("Não foi possível registrar seu check-in. Tente novamente em instantes.")

# ---------- TELA DE ACOMPANHAMENTO ----------

else:
    with st.container():
        cabecalho_marca()
        st.title("Acompanhamento da Fila")

    @st.fragment(run_every=8)
    def painel_posicao():
        posicao = buscar_posicao(st.session_state["meu_id"])

        if posicao is not None:
            st.metric(label="Sua posição atual", value=f"{posicao}º")
            if posicao == 1:
                st.success("Fique atento! Você é o próximo a ser chamado.")
            else:
                st.info(f"{'Há 1 pessoa' if posicao == 2 else f'Há {posicao - 1} pessoas'} na sua frente.")
        else:
            st.success("Chegou a sua vez! Dirija-se à mesa do corretor.")

    painel_posicao()

    st.divider()
    st.markdown('<div class="secondary-btn">', unsafe_allow_html=True)
    if st.button("Novo check-in"):
        del st.session_state["meu_id"]
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
