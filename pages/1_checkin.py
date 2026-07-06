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
        --bt-accent:  #b026ff;
        --bt-accent2: #e0219a;
        --bt-green:   #25d366;
    }

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

    h1, h2, h3 {
        font-family: 'Baloo 2', cursive !important;
        font-weight: 800 !important;
        letter-spacing: 0.3px;
        color: var(--bt-text) !important;
    }
    h1 { font-size: 2.4rem !important; }

    p, label, .stMarkdown { color: var(--bt-text); }

    label, .stTextInput label, .stSelectbox label {
        font-family: 'Baloo 2', cursive !important;
        font-weight: 600 !important;
        color: var(--bt-muted) !important;
        font-size: 0.95rem !important;
    }

    .stTextInput input {
        background: var(--bt-surface) !important;
        color: var(--bt-text) !important;
        border: 1px solid var(--bt-border) !important;
        border-radius: 14px !important;
        padding: 12px 14px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.35) !important;
        font-size: 1rem !important;
    }

    .stSelectbox div[data-baseweb="select"] > div {
        background: var(--bt-surface) !important;
        color: var(--bt-text) !important;
        border: 1px solid var(--bt-border) !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.35) !important;
    }

    .stTextInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within {
        border-color: var(--bt-accent) !important;
        box-shadow: 0 0 0 3px rgba(176,38,255,0.25) !important;
    }

    .stTextInput input::placeholder { color: #6b6b6b; }

    div[data-baseweb="popover"] div {
        background: var(--bt-surface) !important;
        color: var(--bt-text) !important;
    }

    /* Item destacado/selecionado do dropdown (visível no toque) */
    div[data-baseweb="popover"] li:hover,
    div[data-baseweb="popover"] li[aria-selected="true"] {
        background: rgba(176,38,255,0.22) !important;
    }

    /* CORREÇÃO MOBILE: limita a altura da lista para rolar por dentro
       em vez de estourar o topo da tela (barra de status) no celular */
    div[data-baseweb="popover"] [role="listbox"],
    div[data-baseweb="popover"] ul {
        max-height: 40vh !important;
        overflow-y: auto !important;
    }

    /* CORREÇÃO iOS: fonte >= 16px evita o zoom automático do Safari */
    .stTextInput input,
    div[data-baseweb="select"] input {
        font-size: 16px !important;
    }

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
    /* Elevação só em aparelhos com mouse — evita botão "preso" no toque */
    @media (hover: hover) {
        .stButton > button:hover,
        .stFormSubmitButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 30px rgba(176,38,255,0.5) !important;
            color: #ffffff !important;
        }
    }
    .stButton > button:active,
    .stFormSubmitButton > button:active {
        transform: scale(0.99);
    }

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

    .bt-card {
        background: var(--bt-surface);
        border: 1px solid var(--bt-border);
        border-radius: 22px;
        padding: 2rem 1.8rem;
        box-shadow: 0 18px 50px rgba(0,0,0,0.6);
        margin-bottom: 1.2rem;
    }

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

    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(176,38,255,0.18), rgba(224,33,154,0.10));
        border: 1px solid rgba(176,38,255,0.35);
        border-radius: 22px;
        padding: 1.6rem 1.2rem;
        text-align: center;
        box-shadow: 0 14px 40px rgba(176,38,255,0.18);
    }
    [data-testid="stMetricLabel"] { justify-content: center; }
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

    .stAlert {
        border-radius: 16px !important;
        border: none !important;
        font-family: 'Nunito', sans-serif;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }
    div[data-baseweb="notification"] { border-radius: 16px !important; }

    hr { border-color: var(--bt-border) !important; }

    #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* Ajustes finos para telas pequenas (celular) */
    @media (max-width: 480px) {
        .block-container {
            padding-top: 2rem;
            padding-left: 1.1rem;
            padding-right: 1.1rem;
        }
        h1 { font-size: 2rem !important; }
        .bt-brandname { font-size: 1.05rem; letter-spacing: 1px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- BLOCO DE MARCA (reutilizável) ----------

LOGO_URL = st.secrets.get(
    "LOGO_URL",
    "https://gfaffmlrhubbwcyxaewl.supabase.co/storage/v1/object/public/assets/logo_400px.png",
)

def cabecalho_marca():
    st.markdown(
        f"""
        <div class="bt-brand">
            <img src="{LOGO_URL}" style="width: 48px; height: 48px; border-radius: 50%; object-fit: cover; box-shadow: 0 4px 14px rgba(255,255,255,0.15);">
            <div>
                <div class="bt-brandname">PROJETO DE CORREÇÕES</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
#  MOTOR — LÓGICA DA FILA
# ============================================================

@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


supabase = init_connection()


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


def aluno_ja_na_fila(contato: str) -> bool:
    resultado = _executar(
        supabase.table(TABELA)
        .select("id")
        .eq("status", "Aguardando")
        .eq("contato", contato)
    )
    return len(resultado.data) > 0


def buscar_posicao(id_aluno: str) -> int | None:
    fila = _executar(
        supabase.table(TABELA)
        .select("id")
        .eq("status", "Aguardando")
        .order("data_hora", desc=False)
    )
    ids = [r["id"] for r in fila.data]
    if id_aluno in ids:
        return ids.index(id_aluno) + 1
    return None


# ---------- PREPARAÇÃO DOS TEMAS ----------
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
        "Nome completo",
        LISTA_NOMES,
        index=None,
        placeholder="Selecione ou digite seu nome..."
    )

    # 2. Lógica invisível do aluno
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

    # 3. Campo único de tema
    tema_selecionado = st.selectbox(
        "Tema da redação",
        TODOS_TEMAS,
        index=None,
        placeholder="Selecione o tema..."
    )

    enviado = st.button("Entrar na Fila", use_container_width=True)

    if enviado:
        if not all([nome, contato, turma, tema_selecionado]):
            st.error("Preencha todos os dados antes de continuar.")
        else:
            resultado = None  # "duplicado" | "erro" | novo id (str)
            try:
                with st.spinner("Registrando seu check-in..."):
                    if aluno_ja_na_fila(contato):
                        resultado = "duplicado"
                    else:
                        livro_do_tema = next((livro for livro, temas in TEMAS_POR_LIVRO.items() if tema_selecionado in temas), "Outro")
                        tema_final = f"{livro_do_tema} - {tema_selecionado}"

                        resposta = _executar(
                            supabase.table(TABELA)
                            .insert({"nome": nome, "contato": contato, "turma": turma, "tema": tema_final})
                        )
                        resultado = resposta.data[0]["id"]
            except Exception:
                resultado = "erro"

            # Fora do try: rerun/erros não são "engolidos" pelo except
            if resultado == "duplicado":
                st.error("Você já está na fila de espera. Aguarde ser chamado.")
            elif resultado == "erro":
                st.error("Não foi possível registrar seu check-in. Tente novamente em instantes.")
            else:
                st.session_state["meu_id"] = resultado
                st.rerun()

# ---------- TELA DE ACOMPANHAMENTO ----------

else:
    with st.container():
        cabecalho_marca()
        st.title("Acompanhamento da Fila")

    @st.fragment(run_every=8)
    def painel_posicao():
        try:
            posicao = buscar_posicao(st.session_state["meu_id"])
        except Exception:
            st.info("Atualizando sua posição... (reconectando)")
            return

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
