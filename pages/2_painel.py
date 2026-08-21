import time
import requests
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta

FUSO_BR = timezone(timedelta(hours=-3))

# Importando as listas oficiais de forma limpa
from corretores import LISTA_CORRETORES
from alunos import BASE_ALUNOS
from temas import TEMAS_POR_LIVRO

st.set_page_config(page_title="Painel | Projeto de Corre√ß√µes", layout="wide")

st.markdown(
    """
    <style>
    #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* iOS: fonte >= 16px evita o zoom autom√°tico ao focar campos */
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
# VARI√ÅVEIS DE CORRE√á√ÉO
# ==========================================================
CORRETORES = LISTA_CORRETORES
# OBS: 180 n√£o √© um valor padr√£o do ENEM (0/40/80/120/160/200).
# Mantido pendente de confirma√ß√£o ‚Äî remova se n√£o fizer parte da sua rubrica.
OPCOES_NOTA = [0, 40, 80, 120, 160, 180, 200]
ORIGEM_MANUAL = "Redacall"   # etiqueta dos registros lan√ßados manualmente
# Lista √∫nica de temas (o livro fica oculto e √© inferido ao salvar)
TODOS_TEMAS = [tema for temas in TEMAS_POR_LIVRO.values() for tema in temas]
COLUNAS = [
    "id", "data_hora", "ordem_em", "nome", "contato", "turma", "tema",
    "status", "origem", "corretor", "comp1", "comp2", "comp3", "comp4", "comp5", "nota",
    "chamado", "chamado_em",
]


@st.cache_resource
def init_connection() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

supabase = init_connection()


def _executar(query, tentativas: int = 2):
    ultimo_erro = None
    for i in range(tentativas):
        try:
            return query.execute()
        except Exception as e:
            ultimo_erro = e
            if i < tentativas - 1:
                time.sleep(0.4)  # pequeno backoff antes de tentar de novo
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
        df = pd.DataFrame(response.data)
        # Converte as colunas de data do banco (UTC) para o fuso do Brasil
        for col in ["data_hora", "ordem_em", "chamado_em"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True).dt.tz_convert(FUSO_BR).dt.strftime('%Y-%m-%dT%H:%M:%S')
        return df
    return pd.DataFrame(columns=COLUNAS)


def _normalizar_telefone(contato) -> str:
    """Retorna o n√∫mero no formato 55DDDNUMERO (s√≥ d√≠gitos) ou '' se inv√°lido.

    Aceita entradas com ou sem c√≥digo do pa√≠s e com m√°scara
    (par√™nteses, tra√ßos, espa√ßos).
    """
    d = "".join(filter(str.isdigit, str(contato or "")))

    # Remove o c√≥digo do pa√≠s se j√° veio junto (12 ou 13 d√≠gitos = 55 + DDD + n√∫mero)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]

    # Agora esperamos DDD (2) + n√∫mero (8 ou 9) = 10 ou 11 d√≠gitos
    if len(d) < 10 or len(d) > 11:
        return ""
    return f"55{d}"


def chamar_aluno(id_aluno: str, nome_aluno: str, contato_aluno: str) -> bool:
    # 1) L√™ e valida a configura√ß√£o
    try:
        cfg = st.secrets["whatsapp"]
        host = str(cfg["host"]).strip()
        instance_key = str(cfg["instance_key"]).strip()
        token = str(cfg["token"]).strip()
    except Exception:
        st.error("WhatsApp n√£o est√° configurado nos secrets (bloco [whatsapp]).")
        return False

    # Normaliza o host: aceita com/sem protocolo e remove barra final.
    # Ex.: 'https://apinocode01.megaapi.com.br/' -> 'apinocode01.megaapi.com.br'
    host = host.replace("https://", "").replace("http://", "").strip().strip("/")

    # 2) Valida o n√∫mero ANTES de chamar a API
    telefone_limpo = _normalizar_telefone(contato_aluno)
    if not telefone_limpo:
        st.warning(f"N√∫mero inv√°lido para {nome_aluno}: '{contato_aluno}'. Corrija o cadastro.")
        return False

    nome_curto = " ".join(str(nome_aluno).strip().split()[:2]) or "Aluno(a)"
    mensagem = f"Ol√°, *{nome_curto}*! Chegou a sua vez nas corre√ß√µes. Dirija-se √† mesa."

    url_api = f"https://{host}/rest/sendMessage/{instance_key}/text"
    payload = {"messageData": {"to": f"{telefone_limpo}@s.whatsapp.net", "text": mensagem}}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 3) Chamada HTTP, tratando falha de conex√£o separadamente
    try:
        resp = requests.post(url_api, json=payload, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"[chamar_aluno] Falha de conex√£o: {e} | url={url_api}")
        st.error(
            "N√£o foi poss√≠vel falar com a API do WhatsApp. "
            "Confira o 'host' nos secrets ‚Äî deve ser s√≥ o dom√≠nio, "
            "ex.: apinocode01.megaapi.com.br (sem https:// e sem barra no fim)."
        )
        return False

    # 4) Interpreta a resposta com seguran√ßa (JSON de verdade, n√£o busca por texto)
    try:
        data = resp.json()
    except ValueError:
        data = {}

    houve_erro = bool(data.get("error", resp.status_code >= 400))
    if houve_erro:
        motivo = data.get("message") or (resp.text or "")[:200] or f"HTTP {resp.status_code}"
        print(f"[chamar_aluno] API recusou: status={resp.status_code} body={resp.text[:500]}")
        st.error(f"A API recusou o envio: {motivo}")
        return False

    # 5) Envio OK ‚Äî marca como chamado. Se essa etapa falhar (ex.: coluna
    #    inexistente), N√ÉO invalida o envio: s√≥ registra o problema.
    try:
        _executar(
            supabase.table(TABELA).update({
                "chamado": True,
                "chamado_em": datetime.now(timezone.utc).isoformat(),
            }).eq("id", id_aluno)
        )
    except Exception as e:
        print(f"[chamar_aluno] Envio OK, mas falhou ao marcar 'chamado': {e}")

    st.success(f"Chamado enviado para {nome_curto}.")
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
        st.toast("Falha ao pular aluno. Tente novamente.", icon="‚ö†Ô∏è")
        return False


def excluir_aluno(id_aluno: str) -> bool:
    try:
        _executar(supabase.table(TABELA).delete().eq("id", id_aluno))
        return True
    except Exception:
        st.toast("Falha ao excluir aluno. Tente novamente.", icon="‚ö†Ô∏è")
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
        st.toast("Falha ao desfazer. Tente novamente.", icon="‚ö†Ô∏è")
        return False


def registrar_atendimento_manual(dados: dict) -> bool:
    """Insere uma corre√ß√£o que n√£o passou pela fila, j√° conclu√≠da e
    etiquetada com a origem 'Redacall'."""
    try:
        _executar(supabase.table(TABELA).insert(dados))
        return True
    except Exception:
        st.error("N√£o foi poss√≠vel registrar. Verifique a conex√£o e tente novamente.")
        return False


def contar_por_status(dados: pd.DataFrame, status: str) -> int:
    if dados.empty:
        return 0
    return len(dados[dados["status"] == status])


# ---------- AUTENTICA√á√ÉO ----------
if not st.session_state.get("autenticado"):
    st.markdown(
        """
        <div class="login-wrap">
            <h1>Acesso Restrito</h1>
            <p>Insira a senha para acessar o painel de corre√ß√µes.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("form_login"):
        senha = st.text_input("Senha", type="password", label_visibility="collapsed", placeholder="Senha de acesso")
        if st.form_submit_button("Entrar", use_container_width=True):
            senha_correta = st.secrets.get("SENHA_CORRETOR")
            if not senha_correta:
                st.error("Senha n√£o configurada nos secrets (SENHA_CORRETOR). Avise o administrador.")
            elif senha == senha_correta:
                st.session_state["autenticado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()


# ---------- PAINEL DO CORRETOR ----------
col_titulo, col_sair = st.columns([6, 1])
with col_titulo:
    st.title("Painel de Corre√ß√µes")
with col_sair:
    st.write("")
    if st.button("Sair", use_container_width=True):
        st.session_state.clear()
        st.rerun()

try:
    todos_dados = carregar_dados()
except Exception:
    st.error("N√£o foi poss√≠vel conectar ao banco de dados agora. Verifique a conex√£o e atualize a p√°gina.")
    st.stop()

# Ajuste do 'hoje' usando o fuso do Brasil
hoje = datetime.now(FUSO_BR).date().isoformat()
if not todos_dados.empty and "data_hora" in todos_dados.columns:
    # .fillna(False) evita quebra quando algum registro tem data_hora nula
    mask_hoje = todos_dados["data_hora"].astype(str).str.startswith(hoje).fillna(False)
    dados_hoje = todos_dados[mask_hoje]
else:
    dados_hoje = pd.DataFrame()

# Check-ins reais = quem passou pela fila (exclui lan√ßamentos manuais "Redacall")
if not dados_hoje.empty and "origem" in dados_hoje.columns:
    checkins_hoje = int((dados_hoje["origem"] != ORIGEM_MANUAL).sum())
else:
    checkins_hoje = len(dados_hoje)

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Na fila agora", contar_por_status(todos_dados, "Aguardando"))
col_m2.metric("Corrigidos hoje", contar_por_status(dados_hoje, "Conclu√≠do"))
col_m3.metric("Check-ins hoje", checkins_hoje)

st.divider()

aba_fila, aba_dados = st.tabs(["Fila de Atendimento", "Base de Dados"])

with aba_fila:

    # ==========================================
    # MODO FOCO: AVALIA√á√ÉO DE REDA√á√ÉO
    # ==========================================
    if "avaliar_id" in st.session_state:
        st.subheader("üìù Avaliando Reda√ß√£o")
        st.markdown(f"**Aluno:** {st.session_state['avaliar_nome']}")

        with st.container(border=True):
            corretor = st.selectbox("Corretor respons√°vel", CORRETORES, index=None, placeholder="Selecione seu nome...")

            st.markdown("#### Notas das Compet√™ncias")
            st.caption("Selecione os valores. A soma √© autom√°tica.")

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
                        st.error("‚ö†Ô∏è Identifique o corretor antes de salvar.")
                    elif None in [n1, n2, n3, n4, n5]:
                        st.error("‚ö†Ô∏è Preencha a nota de todas as 5 compet√™ncias.")
                    else:
                        payload = {
                            "status": "Conclu√≠do",
                            "corretor": corretor,
                            "comp1": v1, "comp2": v2, "comp3": v3, "comp4": v4, "comp5": v5,
                            "nota": nota_total
                        }
                        try:
                            # Trava otimista: s√≥ conclui se ainda estiver "Aguardando".
                            # Evita que dois corretores concluam o mesmo aluno.
                            resp = _executar(
                                supabase.table(TABELA)
                                .update(payload)
                                .eq("id", st.session_state["avaliar_id"])
                                .eq("status", "Aguardando")
                            )
                            if not resp.data:
                                st.warning(
                                    "Este aluno j√° foi conclu√≠do ou alterado por outro corretor. "
                                    "Nada foi sobrescrito."
                                )
                            del st.session_state["avaliar_id"]
                            del st.session_state["avaliar_nome"]
                            st.rerun()
                        except Exception:
                            st.error("Erro de conex√£o ao salvar. Tente novamente.")

            with col_cancelar:
                if st.button("Cancelar Avalia√ß√£o", use_container_width=True):
                    del st.session_state["avaliar_id"]
                    del st.session_state["avaliar_nome"]
                    st.rerun()

    # ==========================================
    # MODO NORMAL: FILA DE ESPERA
    # ==========================================
    else:
        # Confirma√ß√£o de um registro manual feito no rerun anterior
        _msg_manual = st.session_state.pop("manual_ok", None)
        if _msg_manual:
            st.toast(_msg_manual, icon="‚úÖ")

        # Processa um "Chamar" pedido no clique anterior. Fica FORA do fragmento
        # de auto-refresh: assim a chamada √† API (que leva alguns segundos) nunca
        # √© interrompida pelo tick do run_every, e a mensagem de status permanece
        # na tela at√© a pr√≥xima intera√ß√£o (n√£o some sozinha).
        _req_chamar = st.session_state.pop("chamar_req", None)
        if _req_chamar:
            chamar_aluno(_req_chamar["id"], _req_chamar["nome"], _req_chamar["contato"])

        @st.fragment(run_every=15)
        def exibir_fila():
            try:
                fila_espera = carregar_dados("Aguardando")
            except Exception:
                st.info("Reconectando ao banco de dados... a fila ser√° atualizada em instantes.")
                return

            if fila_espera.empty:
                st.info("Nenhum aluno aguardando no momento.")
                return

            st.caption(
                f"{len(fila_espera)} aluno(s) na fila. Cada corretor pode chamar um aluno "
                "diferente ‚Äî n√£o √© preciso concluir para chamar o pr√≥ximo."
            )

            for ordem, (_, aluno) in enumerate(fila_espera.iterrows(), start=1):
                aid = aluno["id"]
                chamado = bool(aluno.get("chamado", False))
                with st.container(border=True):
                    col_info, col_acoes = st.columns([2, 4])
                    with col_info:
                        marcador = "  ¬∑  üîî Chamado" if chamado else ""
                        st.markdown(f"**{ordem}. {aluno['nome']}**{marcador}")
                        st.caption(f"{aluno['turma']}  |  {aluno['tema']}  |  {aluno['contato']}")
                    with col_acoes:
                        # Agora temos 4 colunas de bot√µes
                        b_chamar, b_concluir, b_pular, b_excluir = st.columns(4)

                        rotulo_chamar = "Chamar de novo" if chamado else "Chamar"

                        if b_chamar.button(rotulo_chamar, key=f"chamar_{aid}", type="primary", use_container_width=True):
                            # N√£o envia aqui dentro do fragmento (evita corrida com o
                            # auto-refresh). Registra o pedido e reprocessa no app.
                            st.session_state["chamar_req"] = {
                                "id": aid, "nome": aluno["nome"], "contato": aluno["contato"],
                            }
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
        st.subheader("Corre√ß√µes Recentes")

        # Deriva das corre√ß√µes j√° carregadas em 'todos_dados' (evita query extra)
        if not todos_dados.empty and "status" in todos_dados.columns:
            _conc = todos_dados[todos_dados["status"] == "Conclu√≠do"].copy()
            recentes = _conc.sort_values("data_hora", ascending=False).head(5)
        else:
            recentes = pd.DataFrame()

        if recentes.empty:
            st.caption("Nenhuma reda√ß√£o corrigida ainda.")
        else:
            for _, row in recentes.iterrows():
                col_info, col_acao = st.columns([4, 1])
                with col_info:
                    nota_txt = f"{int(row['nota'])}" if pd.notna(row.get("nota")) else "‚Äî"
                    corretor_txt = row["corretor"] if row.get("corretor") else "‚Äî"
                    etiqueta = " `Redacall`" if row.get("origem") == ORIGEM_MANUAL else ""
                    st.markdown(f"**{row['nome']}** ‚Äî Nota: {nota_txt} _(Corretor: {corretor_txt})_{etiqueta}")
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
                "Para lan√ßar uma corre√ß√£o que n√£o passou pela fila. O registro entra "
                f"na base j√° como **Conclu√≠do** e com a origem **{ORIGEM_MANUAL}**."
            )

            # Vers√£o dos campos: ao salvar, incrementamos e os widgets nascem limpos.
            _ver = st.session_state.get("manual_ver", 0)

            col_a, col_b = st.columns(2)
            with col_a:
                m_corretor = st.selectbox(
                    "Corretor respons√°vel", CORRETORES, index=None,
                    placeholder="Selecione o corretor...", key=f"m_corretor_{_ver}",
                )
            with col_b:
                m_aluno = st.selectbox(
                    "Aluno", sorted(BASE_ALUNOS.keys()), index=None,
                    placeholder="Selecione o aluno...", key=f"m_aluno_{_ver}",
                )

            # Campo √∫nico de tema (o livro √© descoberto de forma oculta ao salvar)
            m_tema = st.selectbox(
                "Tema da reda√ß√£o", TODOS_TEMAS, index=None,
                placeholder="Selecione o tema...", key=f"m_tema_{_ver}",
            )

            # Turma e WhatsApp v√™m automaticamente da base de alunos
            if m_aluno:
                _dados_aluno = BASE_ALUNOS.get(m_aluno, {})
                st.caption(
                    f"Turma: {_dados_aluno.get('turma', '‚Äî')}  |  "
                    f"WhatsApp: {_dados_aluno.get('contato', '‚Äî')}"
                )

            st.markdown("**Notas por compet√™ncia**")
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
                    st.error("‚ö†Ô∏è Selecione o corretor respons√°vel.")
                elif not m_aluno:
                    st.error("‚ö†Ô∏è Selecione o aluno.")
                elif not m_tema:
                    st.error("‚ö†Ô∏è Selecione o tema da reda√ß√£o.")
                elif None in m_notas:
                    st.error("‚ö†Ô∏è Preencha a nota de todas as 5 compet√™ncias.")
                else:
                    _aluno_info = BASE_ALUNOS.get(m_aluno, {})
                    # Descobre de qual livro √© o tema de forma oculta
                    _livro = next(
                        (livro for livro, temas in TEMAS_POR_LIVRO.items() if m_tema in temas),
                        "Outro",
                    )
                    _payload_manual = {
                        "nome": m_aluno,
                        "contato": _aluno_info.get("contato", ""),
                        "turma": _aluno_info.get("turma", "N√£o identificada"),
                        # Mesmo formato do check-in, para a base ficar consistente
                        "tema": f"{_livro} - {m_tema}",
                        "status": "Conclu√≠do",
                        "origem": ORIGEM_MANUAL,
                        # Grava a data explicitamente para n√£o depender do default do banco
                        "data_hora": datetime.now(timezone.utc).isoformat(),
                        "corretor": m_corretor,
                        "comp1": m_notas[0], "comp2": m_notas[1], "comp3": m_notas[2],
                        "comp4": m_notas[3], "comp5": m_notas[4],
                        "nota": m_total,
                    }
                    # O rerun fica FORA do try para n√£o ser engolido pelo except
                    _ok = registrar_atendimento_manual(_payload_manual)
                    if _ok:
                        st.session_state["manual_ver"] = _ver + 1
                        st.session_state["manual_ok"] = f"{m_aluno} registrado ‚Äî nota {m_total}."
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
            modo_data = st.radio("Filtrar por", ["Dia √∫nico", "Intervalo"], horizontal=True, label_visibility="collapsed")
        with col_data:
            if modo_data == "Dia √∫nico":
                dia_selecionado = st.date_input("Data", value=datetime.now(FUSO_BR).date())
                data_inicio = dia_selecionado
                data_fim = dia_selecionado
            else:
                intervalo = st.date_input("Per√≠odo", value=(datas_disponiveis.min(), datas_disponiveis.max()))
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

        # Remove colunas internas (mec√¢nica da fila) do arquivo de an√°lise
        internas = ["id", "chamado", "chamado_em", "ordem_em"]
        colunas_export = [c for c in dados_filtrados.columns if c not in internas]
        csv = dados_filtrados[colunas_export].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Exportar CSV",
            data=csv,
            file_name=f"correcoes_{datetime.now(FUSO_BR).date().isoformat()}.csv",
            mime="text/csv",
        )
