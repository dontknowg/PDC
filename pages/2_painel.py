import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, date, timezone
import requests

# Importando as listas oficiais de forma limpa
from corretores import LISTA_CORRETORES
from alunos import BASE_ALUNOS
from temas import TEMAS_POR_LIVRO

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

    /* No celular: os indicadores viram blocos proporcionais */
    @media (max-width: 640px) {
        [data-testid="stColumn"]:has([data-testid="stMetric"]) {
            flex: 1 1 46% !important;
            min-width: 46% !important;
        }
    }

    /* Tela de login centralizada */
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

# ==========================================================
# VARIÁVEIS DE CORREÇÃO
# ==========================================================
CORRETORES = LISTA_CORRETORES
OPCOES_NOTA = [0, 40, 80, 120, 160, 200]
ORIGEM_MANUAL = "Redacall"   # etiqueta dos registros lançados manualmente
# Lista única de temas (o livro fica oculto e é inferido ao salvar)
TODOS_TEMAS = [tema for temas in TEMAS_POR_LIVRO.values() for tema in temas]
COLUNAS = [
    "id", "data_hora", "ordem_em", "nome", "contato", "turma", "tema",
    "status", "origem", "corretor", "comp1", "comp2", "comp3", "comp4", "comp5", "nota",
]


@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = init_connection()


def _executar(query, tentativas: int = 2):
    ultimo_erro = None
    for _ in range(tentativas):
        try:
            return query.execute()
        except Exception as e:
            ultimo_erro = e
    raise ultimo_erro


def carregar_dados(filtro_status=None) -> pd.DataFrame:
    query = supabase.table(TABELA).select("*")
    if filtro_status == "Aguardando":
        query = query.eq("status", filtro_status).order("ordem_em", desc=False)
    elif filtro_status:
        query = query.eq("status", filtro_status).order("data_hora", desc=False)
    else:
        query = query.order("data_hora", desc=True)

    response = _executar(query)
    if response.data:
        return pd.DataFrame(response.data)
    return pd.DataFrame(columns=COLUNAS)


def chamar_aluno(id_aluno: str, nome_aluno: str, contato_aluno: str) -> bool:
    # 1. Atualiza no Supabase (faz o painel reagir). Se isso falhar, aborta.
    try:
        _executar(
            supabase.table(TABELA).update({
                "chamado": True,
                "chamado_em": datetime.now(timezone.utc).isoformat(),
            }).eq("id", id_aluno)
        )
    except Exception:
        st.toast("Falha ao chamar (banco). Tente novamente.", icon="⚠️")
        return False

    # 2. Dispara o WhatsApp — agora com diagnóstico VISÍVEL.
    try:
        cfg = st.secrets["whatsapp"]
        host = cfg["host"]
        instance_key = cfg["instance_key"]
        token = cfg["token"]
    except Exception:
        st.toast("Aluno chamado, mas o WhatsApp não está configurado (falta o bloco [whatsapp] nos secrets).", icon="⚠️")
        return True

    try:
        telefone_limpo = "".join(filter(str.isdigit, str(contato_aluno)))
        if telefone_limpo and not telefone_limpo.startswith("55"):
            telefone_limpo = f"55{telefone_limpo}"
        if not telefone_limpo:
            st.toast("Aluno chamado, mas ele não tem WhatsApp cadastrado.", icon="⚠️")
            return True

        nome_curto = " ".join(str(nome_aluno).strip().split()[:2]) or "Aluno(a)"
        mensagem = f"Olá, *{nome_curto}*! Chegou a sua vez nas correções. Dirija-se à mesa."

        url_api = f"https://{host}/rest/sendMessage/{instance_key}/text"
        payload = {"messageData": {"to": f"{telefone_limpo}@s.whatsapp.net", "text": mensagem}}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        resp = requests.post(url_api, json=payload, headers=headers, timeout=10)

        if resp.status_code >= 400:
            corpo = (resp.text or "")[:400]
            st.toast(f"WhatsApp falhou [{resp.status_code}]: {corpo}", icon="⚠️")
            print(f"[WhatsApp] {resp.status_code} -> {resp.text}")
        else:
            st.toast(f"Chamado enviado no WhatsApp para {nome_curto}.", icon="✅")
            print(f"[WhatsApp] OK -> {resp.text[:300]}")

    except requests.exceptions.Timeout:
        st.toast("WhatsApp: tempo esgotado (a API não respondeu em 10s).", icon="⚠️")
    except Exception as e:
        st.toast(f"WhatsApp: erro de conexão — {type(e).__name__}: {e}", icon="⚠️")
        print(f"[WhatsApp] Exceção: {e}")

    return True


def pular_aluno(id_aluno: str) -> bool:
    try:
        _executar(
            supabase.table(TABELA).update({
                "ordem_em": datetime.now(timezone.utc).isoformat(),
                "chamado": False,
                "chamado_em": None
            }).eq("id", id_aluno)
        )
        return True
    except Exception:
        st.toast("Falha ao pular aluno. Tente novamente.", icon="⚠️")
        return False


def excluir_aluno(id_aluno: str) -> bool:
    try:
        _executar(supabase.table(TABELA).delete().eq("id", id_aluno))
        return True
    except Exception:
        st.toast("Falha ao excluir aluno. Tente novamente.", icon="⚠️")
        return False


def desfazer_conclusao(id_aluno: str) -> bool:
    payload = {
        "status": "Aguardando",
        "chamado": False,
        "chamado_em": None,
        "ordem_em": datetime.now(timezone.utc).isoformat(),
        "corretor": None,
        "comp1": None, "comp2": None, "comp3": None, "comp4": None, "comp5": None,
        "nota": None
    }
    try:
        _executar(supabase.table(TABELA).update(payload).eq("id", id_aluno))
        return True
    except Exception:
        st.toast("Falha ao desfazer. Tente novamente.", icon="⚠️")
        return False


def registrar_atendimento_manual(dados: dict) -> bool:
    """Insere uma correção que não passou pela fila, já concluída e
    etiquetada com a origem 'Redacall'."""
    try:
        _executar(supabase.table(TABELA).insert(dados))
        return True
    except Exception:
        st.error("Não foi possível registrar. Verifique a conexão e tente novamente.")
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

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Na fila agora", contar_por_status(todos_dados, "Aguardando"))
col_m2.metric("Corrigidos hoje", contar_por_status(dados_hoje, "Concluído"))
col_m3.metric("Total de Check-ins hoje", len(dados_hoje))

st.divider()

aba_fila, aba_dados = st.tabs(["Fila de Atendimento", "Base de Dados"])

with aba_fila:

    # ==========================================
    # MODO FOCO: AVALIAÇÃO DE REDAÇÃO
    # ==========================================
    if "avaliar_id" in st.session_state:
        st.subheader("📝 Avaliando Redação")
        st.markdown(f"**Aluno:** {st.session_state['avaliar_nome']}")

        with st.container(border=True):
            corretor = st.selectbox("Corretor responsável", CORRETORES, index=None, placeholder="Selecione seu nome...")

            st.markdown("#### Notas das Competências")
            st.caption("Selecione os valores. A soma é automática.")

            c_cols = st.columns(5)
            with c_cols[0]: n1 = st.selectbox("C1", OPCOES_NOTA, index=None, placeholder="Nota")
            with c_cols[1]: n2 = st.selectbox("C2", OPCOES_NOTA, index=None, placeholder="Nota")
            with c_cols[2]: n3 = st.selectbox("C3", OPCOES_NOTA, index=None, placeholder="Nota")
            with c_cols[3]: n4 = st.selectbox("C4", OPCOES_NOTA, index=None, placeholder="Nota")
            with c_cols[4]: n5 = st.selectbox("C5", OPCOES_NOTA, index=None, placeholder="Nota")

            v1 = n1 if n1 is not None else 0
            v2 = n2 if n2 is not None else 0
            v3 = n3 if n3 is not None else 0
            v4 = n4 if n4 is not None else 0
            v5 = n5 if n5 is not None else 0

            nota_total = v1 + v2 + v3 + v4 + v5

            st.metric("Nota Total Mapeada", f"{nota_total} / 1000")
            st.markdown("<br>", unsafe_allow_html=True)

            col_salvar, col_cancelar = st.columns(2)
            with col_salvar:
                if st.button("Salvar e Concluir Atendimento", type="primary", use_container_width=True):
                    if not corretor:
                        st.error("⚠️ Identifique o corretor antes de salvar.")
                    elif None in [n1, n2, n3, n4, n5]:
                        st.error("⚠️ Preencha a nota de todas as 5 competências.")
                    else:
                        payload = {
                            "status": "Concluído",
                            "corretor": corretor,
                            "comp1": v1, "comp2": v2, "comp3": v3, "comp4": v4, "comp5": v5,
                            "nota": nota_total
                        }
                        try:
                            _executar(supabase.table(TABELA).update(payload).eq("id", st.session_state["avaliar_id"]))
                            del st.session_state["avaliar_id"]
                            del st.session_state["avaliar_nome"]
                            st.rerun()
                        except Exception:
                            st.error("Erro de conexão ao salvar. Tente novamente.")

            with col_cancelar:
                if st.button("Cancelar Avaliação", use_container_width=True):
                    del st.session_state["avaliar_id"]
                    del st.session_state["avaliar_nome"]
                    st.rerun()

    # ==========================================
    # MODO NORMAL: FILA DE ESPERA
    # ==========================================
    else:
        # Confirmação de um registro manual feito no rerun anterior
        _msg_manual = st.session_state.pop("manual_ok", None)
        if _msg_manual:
            st.toast(_msg_manual, icon="✅")

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

            for ordem, (_, aluno) in enumerate(fila_espera.iterrows(), start=1):
                aid = aluno["id"]
                chamado = bool(aluno.get("chamado", False))
                with st.container(border=True):
                    col_info, col_acoes = st.columns([2, 4])
                    with col_info:
                        marcador = "  ·  🔔 Chamado" if chamado else ""
                        st.markdown(f"**{ordem}. {aluno['nome']}**{marcador}")
                        st.caption(f"{aluno['turma']}  |  {aluno['tema']}  |  {aluno['contato']}")
                    with col_acoes:
                        # Agora temos 4 colunas de botões
                        b_chamar, b_concluir, b_pular, b_excluir = st.columns(4)

                        rotulo_chamar = "Chamar de novo" if chamado else "Chamar"

                        if b_chamar.button(rotulo_chamar, key=f"chamar_{aid}", type="primary", use_container_width=True):
                            if chamar_aluno(aid, aluno['nome'], aluno['contato']):
                                st.rerun()

                        if b_concluir.button("Concluir", key=f"concluir_{aid}", use_container_width=True):
                            st.session_state["avaliar_id"] = aid
                            st.session_state["avaliar_nome"] = aluno['nome']
                            st.rerun()

                        if b_pular.button("Pular", key=f"pular_{aid}", use_container_width=True):
                            if pular_aluno(aid):
                                st.rerun()

                        if b_excluir.button("Excluir", key=f"excluir_{aid}", use_container_width=True):
                            if excluir_aluno(aid):
                                st.rerun()

        exibir_fila()

        st.divider()
        st.subheader("Correções Recentes")

        try:
            recentes_query = _executar(
                supabase.table(TABELA)
                .select("*")
                .eq("status", "Concluído")
                .order("data_hora", desc=True)
                .limit(5)
            )
            recentes = pd.DataFrame(recentes_query.data) if recentes_query.data else pd.DataFrame()
        except Exception:
            recentes = pd.DataFrame()

        if recentes.empty:
            st.caption("Nenhuma redação corrigida ainda.")
        else:
            for _, row in recentes.iterrows():
                col_info, col_acao = st.columns([4, 1])
                with col_info:
                    nota_txt = f"{int(row['nota'])}" if pd.notna(row.get("nota")) else "—"
                    corretor_txt = row["corretor"] if row.get("corretor") else "—"
                    etiqueta = " `Redacall`" if row.get("origem") == ORIGEM_MANUAL else ""
                    st.markdown(f"**{row['nome']}** — Nota: {nota_txt} _(Corretor: {corretor_txt})_{etiqueta}")
                with col_acao:
                    if st.button("Desfazer", key=f"desfazer_{row['id']}", use_container_width=True):
                        if desfazer_conclusao(row["id"]):
                            st.rerun()

        # ==========================================
        # REGISTRO MANUAL (etiqueta "Redacall")
        # ==========================================
        st.divider()
        with st.expander("Registrar atendimento manual (Redacall)", expanded=False):
            st.caption(
                "Para lançar uma correção que não passou pela fila. O registro entra "
                f"na base já como **Concluído** e com a origem **{ORIGEM_MANUAL}**."
            )

            # Versão dos campos: ao salvar, incrementamos e os widgets nascem limpos.
            _ver = st.session_state.get("manual_ver", 0)

            col_a, col_b = st.columns(2)
            with col_a:
                m_corretor = st.selectbox(
                    "Corretor responsável", CORRETORES, index=None,
                    placeholder="Selecione o corretor...", key=f"m_corretor_{_ver}",
                )
            with col_b:
                m_aluno = st.selectbox(
                    "Aluno", sorted(BASE_ALUNOS.keys()), index=None,
                    placeholder="Selecione o aluno...", key=f"m_aluno_{_ver}",
                )

            # Campo único de tema (o livro é descoberto de forma oculta ao salvar)
            m_tema = st.selectbox(
                "Tema da redação", TODOS_TEMAS, index=None,
                placeholder="Selecione o tema...", key=f"m_tema_{_ver}",
            )

            # Turma e WhatsApp vêm automaticamente da base de alunos
            if m_aluno:
                _dados_aluno = BASE_ALUNOS.get(m_aluno, {})
                st.caption(
                    f"Turma: {_dados_aluno.get('turma', '—')}  |  "
                    f"WhatsApp: {_dados_aluno.get('contato', '—')}"
                )

            st.markdown("**Notas por competência**")
            m_cols = st.columns(5)
            m_notas = []
            for _i in range(5):
                with m_cols[_i]:
                    m_notas.append(
                        st.selectbox(
                            f"C{_i + 1}", OPCOES_NOTA, index=None,
                            placeholder="Nota", key=f"m_c{_i + 1}_{_ver}",
                        )
                    )

            m_total = sum(n for n in m_notas if n is not None)
            st.metric("Nota Total", f"{m_total} / 1000")

            if st.button("Registrar atendimento", type="primary",
                         use_container_width=True, key=f"m_salvar_{_ver}"):
                if not m_corretor:
                    st.error("⚠️ Selecione o corretor responsável.")
                elif not m_aluno:
                    st.error("⚠️ Selecione o aluno.")
                elif not m_tema:
                    st.error("⚠️ Selecione o tema da redação.")
                elif None in m_notas:
                    st.error("⚠️ Preencha a nota de todas as 5 competências.")
                else:
                    _aluno_info = BASE_ALUNOS.get(m_aluno, {})
                    # Descobre de qual livro é o tema de forma oculta
                    _livro = next(
                        (livro for livro, temas in TEMAS_POR_LIVRO.items() if m_tema in temas),
                        "Outro",
                    )
                    _payload_manual = {
                        "nome": m_aluno,
                        "contato": _aluno_info.get("contato", ""),
                        "turma": _aluno_info.get("turma", "Não identificada"),
                        # Mesmo formato do check-in, para a base ficar consistente
                        "tema": f"{_livro} - {m_tema}",
                        "status": "Concluído",
                        "origem": ORIGEM_MANUAL,
                        "corretor": m_corretor,
                        "comp1": m_notas[0], "comp2": m_notas[1], "comp3": m_notas[2],
                        "comp4": m_notas[3], "comp5": m_notas[4],
                        "nota": m_total,
                    }
                    # O rerun fica FORA do try para não ser engolido pelo except
                    _ok = registrar_atendimento_manual(_payload_manual)
                    if _ok:
                        st.session_state["manual_ver"] = _ver + 1
                        st.session_state["manual_ok"] = f"{m_aluno} registrado — nota {m_total}."
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
                "ordem_em": None,
                "chamado": None,
                "chamado_em": None,
                "data_hora": st.column_config.DatetimeColumn("Chegada", format="DD/MM/YYYY HH:mm"),
                "nome": "Nome",
                "contato": "WhatsApp",
                "turma": "Turma",
                "tema": "Tema",
                "status": "Status",
                "origem": "Origem",
                "corretor": "Corretor",
                "comp1": "C1",
                "comp2": "C2",
                "comp3": "C3",
                "comp4": "C4",
                "comp5": "C5",
                "nota": "Nota Final",
            },
            hide_index=True,
            use_container_width=True,
        )

        # Remove colunas internas (mecânica da fila) do arquivo de análise
        internas = ["id", "chamado", "chamado_em", "ordem_em"]
        colunas_export = [c for c in dados_filtrados.columns if c not in internas]
        csv = dados_filtrados[colunas_export].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Exportar CSV",
            data=csv,
            file_name=f"correcoes_{date.today().isoformat()}.csv",
            mime="text/csv",
        )
