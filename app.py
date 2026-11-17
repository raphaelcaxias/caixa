# Caixa Jardim do Éden — versão Streamlit
# Vendas, estoque e produtos guardados numa planilha do Google (ou em arquivos locais para teste).
import base64
import hashlib
import hmac
import io
import math
import os
import re
import time
import unicodedata
import urllib.parse
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

PASTA = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo("America/Sao_Paulo")
LOJAS = ["Aterrado", "Vila Santa Cecília"]
VENDEDORES = ["Raphael", "Daiane", "Norma", "Outros"]
FORMAS = {"Dinheiro": "dinheiro", "Pix": "pix", "Crédito": "credito", "Débito": "debito"}
NOME_FORMA = {v: k for k, v in FORMAS.items()}

ABAS = {
    "Produtos": ["id", "nome", "codigo", "custo", "preco", "ativo"],
    "Vendas": ["id", "data", "loja", "vendedor", "forma", "subtotal", "desconto", "total",
               "recebido", "troco", "usuario", "status"],
    "Itens": ["venda_id", "data", "loja", "produto_id", "produto", "qtd", "preco", "total"],
    "Entradas": ["id", "data", "loja", "produto_id", "produto", "qtd", "obs", "usuario"],
    "Caixa": ["id", "data", "loja", "tipo", "valor", "obs", "usuario"],
}
NUMEROS = {"custo", "preco", "subtotal", "desconto", "total", "recebido", "troco", "qtd", "valor"}
M_HOJE, M_VENDER, M_CAIXA = ":material/home: Início", ":material/point_of_sale: Vender", ":material/payments: Caixa"
M_EST, M_VENDAS = ":material/inventory_2: Estoque", ":material/receipt_long: Vendas"
M_PROD, M_PAINEL = ":material/sell: Produtos", ":material/monitoring: Painel"
M_MAIS = ":material/more_horiz: Mais"
HORAS_LOGIN = 14  # o login vale por um dia de trabalho, mesmo recarregando a página

st.set_page_config(page_title="Caixa Jardim do Éden", page_icon=os.path.join(PASTA, "logo.png"),
                   layout="wide", initial_sidebar_state="collapsed")

with open(os.path.join(PASTA, "logo.png"), "rb") as _f:
    LOGO64 = base64.b64encode(_f.read()).decode()

VINHO, VINHO_E, OURO, OURO_C, CREME, TINTA, LINHA = "#7A1726", "#4A0E18", "#C98A12", "#F2C46B", "#FBF6EC", "#2A1E14", "#EADCC3"
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Nunito+Sans:wght@400;600;700;800;900&display=swap');
html{{font-size:19px}}
html,body,.stApp,button,input,textarea,select,[data-testid="stMarkdownContainer"]{{font-family:'Nunito Sans',system-ui,sans-serif}}
.stApp{{background:radial-gradient(1200px 500px at 10% -10%,#F7E3C4 0%,transparent 60%),linear-gradient(180deg,{CREME} 0%,#F4E8D4 100%)}}
header[data-testid="stHeader"]{{background:transparent;height:0;min-height:0}}
[data-testid="stToolbar"],[data-testid="stDecoration"],#MainMenu,footer{{display:none!important}}
.block-container{{padding-top:1.1rem;padding-bottom:4rem;max-width:1180px}}
h1,h2,h3,h4{{font-family:'Cormorant Garamond',Georgia,serif!important;color:{VINHO_E};letter-spacing:.2px}}
h3{{font-size:2rem!important}} h4{{font-size:1.55rem!important}}
p,li,label,[data-testid="stCaptionContainer"]{{color:#4A3A33}}
/* barra do topo */
.st-key-topo{{background:linear-gradient(120deg,{VINHO_E} 0%,{VINHO} 70%,#93202F 100%);border-radius:22px;padding:12px 16px;box-shadow:0 12px 30px rgba(74,14,24,.28)}}
.st-key-topo [data-baseweb="select"]>div{{background:rgba(255,255,255,.12)!important;border:1px solid rgba(242,196,107,.55)!important;color:#FFF4E2!important;border-radius:14px!important;min-height:3rem}}
.st-key-topo [data-baseweb="select"] *{{color:#FFF4E2!important;fill:#FFF4E2!important;font-weight:800}}
.st-key-topo button{{background:rgba(255,255,255,.12)!important;color:#FFF4E2!important;border:1px solid rgba(242,196,107,.55)!important}}
.marca{{display:flex;align-items:center;gap:14px}}
.marca img{{width:56px;height:56px;border-radius:50%;border:2px solid {OURO};box-shadow:0 0 0 4px rgba(242,196,107,.15)}}
.marca .t1{{font-family:'Cormorant Garamond',serif;font-size:1.75rem;font-weight:700;line-height:1;color:#FFF4E2}}
.marca .t2{{font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;color:{OURO_C};font-weight:900;margin-bottom:3px}}
/* menu */
.st-key-menu [data-testid="stElementContainer"],.st-key-menu [data-testid="stButtonGroup"],.st-key-menu [role="radiogroup"]{{width:100%!important}}
.st-key-submenu [data-testid="stElementContainer"],.st-key-submenu [data-testid="stButtonGroup"],.st-key-submenu [role="radiogroup"]{{width:100%!important}}
.st-key-submenu button{{flex:1 1 0}}
.st-key-menu [data-testid="stButtonGroup"]>div{{width:100%;gap:8px;flex-wrap:wrap}}
.st-key-menu button{{flex:1 1 auto;min-height:3.3rem;border-radius:14px!important;border:1px solid {LINHA}!important;background:#fff!important;color:{TINTA}!important;font-weight:800!important;font-size:1rem!important;box-shadow:0 2px 8px rgba(60,40,10,.05)}}
.st-key-menu button[data-testid="stBaseButton-segmented_controlActive"],.st-key-menu button[aria-checked="true"]{{background:{VINHO}!important;color:#FFF4E2!important;border-color:{VINHO}!important;box-shadow:0 8px 18px rgba(122,23,38,.28)}}
.st-key-menu button[data-testid="stBaseButton-segmented_controlActive"] *,[data-testid="stBaseButton-segmented_controlActive"] *,[data-testid="stBaseButton-pillsActive"] *{{color:#FFF4E2!important}}
.st-key-topo button *,.st-key-topo button{{color:#FFF4E2!important;opacity:1!important}}
[data-testid="stButtonGroup"] button[aria-checked="true"],[data-testid="stButtonGroup"] button[data-selected="true"]{{background:{VINHO}!important;border-color:{VINHO}!important;box-shadow:0 6px 14px rgba(122,23,38,.25)}}
[data-testid="stButtonGroup"] button[aria-checked="true"] *,[data-testid="stButtonGroup"] button[data-selected="true"] *{{color:#FFF4E2!important}}
.st-key-grade button p,.st-key-grade button div{{white-space:normal!important;overflow:visible!important;text-overflow:clip!important}}
/* botões */
.stButton>button,.stFormSubmitButton>button,.stLinkButton>a,.stDownloadButton>button{{border-radius:14px!important;min-height:3.2rem;font-weight:800!important;font-size:1rem;border:1.5px solid {LINHA}!important;background:#fff!important;color:{TINTA}!important;transition:transform .08s,box-shadow .15s}}
.stButton>button:hover,.stFormSubmitButton>button:hover,.stLinkButton>a:hover{{border-color:{OURO}!important;box-shadow:0 6px 16px rgba(201,138,18,.18)}}
.stButton>button:active{{transform:translateY(1px)}}
button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"],a[data-testid="stBaseLinkButton-primary"],button[kind="primary"],button[kind="primaryFormSubmit"]{{background:linear-gradient(135deg,{OURO} 0%,#E3A92A 100%)!important;border:0!important;color:#2A1A00!important;box-shadow:0 8px 20px rgba(201,138,18,.35)!important}}
/* grupos de escolha (vendedor, pagamento…) */
[data-testid="stButtonGroup"] button{{min-height:3rem;font-weight:800;border-radius:12px!important}}
[data-testid="stBaseButton-segmented_controlActive"],[data-testid="stBaseButton-pillsActive"]{{background:{VINHO}!important;color:#FFF4E2!important;border-color:{VINHO}!important}}
/* campos */
[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{{border-radius:14px!important;background:#fff!important;border-color:{LINHA}!important}}
[data-baseweb="input"]:focus-within,[data-baseweb="select"]>div:focus-within{{border-color:{OURO}!important;box-shadow:0 0 0 3px rgba(201,138,18,.18)!important}}
[data-baseweb="input"]>div,[data-baseweb="base-input"],input,textarea{{background:#fff!important}}
input{{font-size:17px!important;font-weight:700!important;color:{TINTA}!important}}
/* cartões de número */
[data-testid="stMetric"]{{background:#fff;border:1px solid {LINHA};border-radius:20px;padding:16px 18px;box-shadow:0 6px 18px rgba(60,40,10,.06)}}
[data-testid="stMetricLabel"] p{{font-weight:800;color:#8A7A65;text-transform:uppercase;font-size:.75rem!important;letter-spacing:.06em}}
[data-testid="stMetricValue"]{{font-weight:900;color:{TINTA};font-size:1.75rem!important}}
/* caixas brancas */
.st-key-carrinho,.st-key-cartao,.st-key-login{{background:#fff;border:1px solid {LINHA};border-radius:24px;padding:20px;box-shadow:0 14px 34px rgba(60,40,10,.10)}}
[data-testid="stForm"]{{background:#fff;border:1px solid {LINHA}!important;border-radius:20px;padding:18px}}
[data-testid="stDataFrame"]{{border-radius:16px;overflow:hidden;border:1px solid {LINHA}}}
/* texto dos botões: grande e sem cortar */
.stButton>button p,.stFormSubmitButton>button p,.stLinkButton>a p,.stDownloadButton>button p,[data-testid="stButtonGroup"] button p{{font-size:1.05rem!important;font-weight:800!important}}
.stButton>button div,.stButton>button p,.stLinkButton>a div,.stLinkButton>a p{{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;line-height:1.2}}
.st-key-menu button p{{font-size:1.05rem!important}}
[class*="st-key-esc_"] .stButton>button p{{font-size:1.15rem!important}}
.st-key-acoes .stButton>button p{{font-size:1.25rem!important}}
.st-key-concluir .stButton>button p{{font-size:1.35rem!important}}
.st-key-grade .stButton>button p{{font-size:.95rem!important;font-weight:700!important}}
/* passos da venda */
.passo{{display:flex;align-items:center;gap:10px;font-weight:900;font-size:1.15rem;color:{VINHO_E};margin:14px 0 8px}}
.passo span{{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;background:{VINHO};color:#FFF4E2;font-size:1rem;flex:none}}
.vazio{{text-align:center;color:#8A7A65;padding:28px 10px;font-size:1.05rem;border:2px dashed {LINHA};border-radius:18px}}
.item-n{{font-weight:900;font-size:1.05rem;color:{TINTA};margin-top:10px;line-height:1.25}}
.item-p{{color:#6A5A45;font-size:.95rem;margin-bottom:4px}}
.qtd{{text-align:center;font-size:1.6rem;font-weight:900;color:{TINTA}}}
.st-key-itens [data-testid="stHorizontalBlock"],[class*="st-key-esc_"] [data-testid="stHorizontalBlock"],.st-key-acoes [data-testid="stHorizontalBlock"]{{flex-wrap:nowrap!important;gap:.5rem!important}}
.st-key-itens [data-testid="stColumn"],[class*="st-key-esc_"] [data-testid="stColumn"],.st-key-acoes [data-testid="stColumn"]{{flex:1 1 0!important;min-width:0!important;width:auto!important}}
.st-key-itens{{border-bottom:1px dashed {LINHA};padding-bottom:10px}}
[class*="st-key-esc_"] .stButton>button{{min-height:3.8rem;font-size:1.1rem!important}}
.st-key-acoes .stButton>button{{min-height:5rem;font-size:1.2rem!important;border-radius:20px!important}}
.total-box{{background:linear-gradient(135deg,#FFF8EA,#FBEFD6);border:1px solid #EBCB8B;border-radius:20px;padding:14px 18px;margin:12px 0 4px;text-align:center}}
.total-l{{font-weight:900;letter-spacing:.2em;color:#8A5F12;font-size:.85rem}}
.total-d{{color:#8A5F12;font-weight:700}}
.troco{{background:#EAF6EC;border:1px solid #9FD3A8;color:#1F5A2A;border-radius:16px;padding:12px 16px;font-size:1.35rem;text-align:center;margin:8px 0}}
.st-key-concluir .stButton>button{{min-height:4.4rem;font-size:1.3rem!important;background:linear-gradient(135deg,#2E7D3A,#3D9A4B)!important;color:#fff!important;box-shadow:0 10px 24px rgba(46,125,58,.35)!important;margin-top:10px}}
.st-key-concluir .stButton>button *{{color:#fff!important}}
.st-key-lista .stButton>button{{justify-content:flex-start;text-align:left;min-height:4rem;white-space:normal}}
.st-key-lista .stButton>button p,.st-key-lista .stButton>button div{{text-align:left;white-space:normal!important}}
.st-key-submenu button{{min-height:2.9rem;border-radius:12px!important}}
.ok-card{{display:flex;gap:18px;align-items:center;background:linear-gradient(135deg,#2E7D3A,#3D9A4B);color:#fff;border-radius:24px;padding:26px 24px;margin:8px 0 16px;box-shadow:0 14px 34px rgba(46,125,58,.3)}}
.ok-ic{{width:70px;height:70px;border-radius:50%;background:rgba(255,255,255,.2);display:grid;place-items:center;font-size:2.4rem;font-weight:900;flex:none}}
.ok-t{{font-family:'Cormorant Garamond',serif;font-size:2.4rem;font-weight:700;line-height:1}}
.ok-s{{font-size:1.2rem;font-weight:700;opacity:.95;margin-top:4px}}
.ok-troco{{font-size:1.5rem;font-weight:900;margin-top:6px;color:#FFF4C8}}
[data-testid="stAlert"] p{{font-size:1.05rem}}
/* busca grande */
.st-key-busca input{{font-size:1.3rem!important;min-height:3.6rem}}
.st-key-login [data-testid="stForm"]{{border:0!important;padding:0;background:transparent}}
.st-key-busca [data-testid="stForm"]{{border:0!important;padding:0;background:transparent}}
/* atalhos de produto */
.st-key-grade .stButton>button{{min-height:5.4rem;white-space:normal;text-align:left;justify-content:flex-start;line-height:1.25;padding:10px 14px;font-size:.92rem}}
.st-key-grade .stButton>button p{{text-align:left}}
.preco{{font-weight:900;color:#8A5F12;font-size:1.15rem}}
.total-grande{{font-size:2.6rem;font-weight:900;color:{VINHO_E};line-height:1.1}}
.sub{{color:#7A6A55;font-size:.9rem}}
.saud{{font-family:'Cormorant Garamond',serif;font-size:2.3rem;font-weight:700;color:{VINHO_E};line-height:1.1;margin:.2rem 0 0}}
.data{{color:#8A7A65;font-weight:700;margin-bottom:.6rem}}
hr{{border-color:{LINHA}!important}}
@media(max-width:640px){{
 html{{font-size:18px}}
 .block-container{{padding-left:.7rem;padding-right:.7rem}}
 .marca img{{width:44px;height:44px}} .marca .t1{{font-size:1.4rem}}
 .st-key-menu [data-testid="stButtonGroup"]>div{{flex-wrap:nowrap!important;gap:4px}}
 .st-key-menu button{{flex:1 1 0!important;min-width:0;min-height:3.6rem;font-size:.72rem!important;padding:4px 2px!important;flex-direction:column}}
 .st-key-menu button [data-testid="stIconMaterial"]{{font-size:1.5rem!important}}
 .st-key-menu button span[data-has-shortcut]{{flex-direction:column!important;gap:2px!important;align-items:center}}
 .st-key-menu button p{{font-size:.72rem!important;white-space:nowrap!important;letter-spacing:-.01em}}
 .st-key-menu button *{{overflow:visible!important;text-overflow:clip!important;max-width:none!important}}
 .st-key-topo [data-testid="stHorizontalBlock"]{{gap:.7rem!important}}
 .marca{{margin-bottom:4px}}
 .st-key-acoes .stButton>button{{min-height:4.4rem}}
 .st-key-acoes .stButton>button p{{font-size:1.05rem!important}}
 [class*="st-key-esc_"] .stButton>button p{{font-size:1.05rem!important}}
 .st-key-grade .stButton>button p{{font-size:.8rem!important}}
 .ok-t{{font-size:1.9rem}} .ok-ic{{width:54px;height:54px;font-size:1.8rem}}
 .st-key-kpis [data-testid="stHorizontalBlock"]{{flex-wrap:wrap!important;gap:.6rem}}
 .st-key-kpis [data-testid="stColumn"]{{flex:1 1 calc(50% - .6rem)!important;min-width:calc(50% - .6rem)!important;width:auto!important}}
 .st-key-acoes [data-testid="stHorizontalBlock"]{{gap:.5rem}}
 .st-key-grade [data-testid="stHorizontalBlock"]{{flex-wrap:nowrap!important;gap:.4rem}}
 .st-key-grade [data-testid="stColumn"]{{flex:1 1 0!important;min-width:0!important;width:auto!important}}
 .st-key-grade .stButton>button{{min-height:5rem;font-size:.78rem;padding:8px}}
 [data-testid="stMetricValue"]{{font-size:1.4rem!important}}
 .total-grande{{font-size:2.1rem}}
}}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- utilidades
def agora():
    return datetime.now(TZ)


def agora_txt():
    return agora().strftime("%Y-%m-%d %H:%M:%S")


def brl(v):
    s = f"{float(v):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def sem_acento(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").upper()


def preco_regra(custo):
    """custo × 5, arredondado para cima até terminar em 9,99 (custo 9 → 49,99)."""
    try:
        c = float(custo)
    except (TypeError, ValueError):
        return 0.0
    if c <= 0:
        return 0.0
    x = round(c * 500)
    return (math.ceil((x + 1) / 1000) * 1000 - 1) / 100


def num(serie):
    return pd.to_numeric(serie.astype(str).str.replace(",", ".", regex=False), errors="coerce").fillna(0)


def novo_id(prefixo=""):
    return prefixo + uuid.uuid4().hex[:8].upper()


# ---------------------------------------------------------------- onde os dados ficam
class BancoLocal:
    """Arquivos CSV numa pasta. Bom para testar no computador."""

    def __init__(self, pasta):
        self.pasta = pasta
        os.makedirs(pasta, exist_ok=True)

    def _arq(self, aba):
        return os.path.join(self.pasta, aba + ".csv")

    def ler(self, aba):
        cols = ABAS[aba]
        if not os.path.exists(self._arq(aba)):
            return pd.DataFrame(columns=cols)
        df = pd.read_csv(self._arq(aba), dtype=str, keep_default_na=False)
        for c in cols:
            if c not in df:
                df[c] = ""
        return df[cols]

    def regravar(self, aba, df):
        df[ABAS[aba]].to_csv(self._arq(aba), index=False)

    def anexar(self, aba, linhas):
        df = pd.concat([self.ler(aba), pd.DataFrame(linhas).astype(str)], ignore_index=True)
        self.regravar(aba, df)

    def mudar(self, aba, chave_col, chave, col, valor):
        df = self.ler(aba)
        df.loc[df[chave_col] == chave, col] = str(valor)
        self.regravar(aba, df)


class BancoSheets:
    """Planilha do Google: as duas lojas gravam no mesmo lugar."""

    def __init__(self, credenciais, planilha):
        import gspread
        self.gspread = gspread
        gc = gspread.service_account_from_dict(dict(credenciais))
        self.sh = gc.open_by_url(planilha) if planilha.startswith("http") else gc.open_by_key(planilha)
        self._ws = {}

    def ws(self, aba):
        if aba not in self._ws:
            try:
                w = self.sh.worksheet(aba)
            except self.gspread.WorksheetNotFound:
                w = self.sh.add_worksheet(title=aba, rows=1000, cols=len(ABAS[aba]))
                w.append_row(ABAS[aba], value_input_option="RAW")
            self._ws[aba] = w
        return self._ws[aba]

    def ler(self, aba):
        cols = ABAS[aba]
        w = self.ws(aba)
        vals = w.get(value_render_option="UNFORMATTED_VALUE")
        if not vals:
            w.append_row(cols, value_input_option="RAW")
            return pd.DataFrame(columns=cols)
        cab = [str(c).strip() for c in vals[0]]
        linhas = [list(r) + [""] * (len(cab) - len(r)) for r in vals[1:] if any(str(x).strip() for x in r)]
        df = pd.DataFrame([r[:len(cab)] for r in linhas], columns=cab).astype(str)
        for c in cols:
            if c not in df:
                df[c] = ""
        return df[cols]

    @staticmethod
    def _valor(c, v):
        if c in NUMEROS:
            try:
                return float(str(v).replace(",", "."))
            except ValueError:
                return 0
        return "" if v is None else str(v)

    def anexar(self, aba, linhas):
        cols = ABAS[aba]
        self.ws(aba).append_rows([[self._valor(c, l.get(c, "")) for c in cols] for l in linhas],
                                 value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1")

    def regravar(self, aba, df):
        cols = ABAS[aba]
        valores = [cols] + [[self._valor(c, v) for c, v in zip(cols, r)] for r in df[cols].values.tolist()]
        self.ws(aba).update(values=valores, range_name="A1", value_input_option="RAW")

    def mudar(self, aba, chave_col, chave, col, valor):
        cols = ABAS[aba]
        w = self.ws(aba)
        coluna = w.col_values(cols.index(chave_col) + 1)
        if chave in coluna:
            w.update_cell(coluna.index(chave) + 1, cols.index(col) + 1, valor)


def segredo(*chaves):
    try:
        v = st.secrets
        for k in chaves:
            v = v[k]
        return v
    except Exception:
        return None


def credenciais():
    cred = segredo("gcp_service_account")
    if not cred and segredo("gcp_json"):
        import json
        cred = json.loads(str(segredo("gcp_json")))  # o arquivo .json do Google colado inteiro
    return dict(cred) if cred else None


@st.cache_resource(show_spinner=False)
def _sheets(planilha, email):
    return BancoSheets(credenciais(), planilha)


@st.cache_resource(show_spinner=False)
def _local():
    return BancoLocal(os.path.join(PASTA, "dados"))


def banco():
    cred, planilha = credenciais(), segredo("planilha", "endereco")
    if cred and planilha:
        return _sheets(str(planilha), cred.get("client_email", ""))
    return _local()


@st.cache_data(ttl=45, show_spinner=False)
def carregar(aba):
    df = banco().ler(aba)
    for c in ABAS[aba]:
        if c in NUMEROS:
            df[c] = num(df[c])
    return df


def gravou():
    carregar.clear()


def preparar_produtos():
    if len(carregar("Produtos")) == 0:
        base = pd.read_csv(os.path.join(PASTA, "produtos_iniciais.csv"), dtype=str, keep_default_na=False)
        banco().regravar("Produtos", base)
        gravou()


# ---------------------------------------------------------------- estoque = entradas − vendas
def estoque():
    ent = carregar("Entradas")
    itens = carregar("Itens")
    vendas = carregar("Vendas")
    canceladas = set(vendas.loc[vendas["status"] == "cancelada", "id"])
    itens = itens[~itens["venda_id"].isin(canceladas)]
    e = ent.groupby(["loja", "produto_id"])["qtd"].sum()
    s = itens.groupby(["loja", "produto_id"])["qtd"].sum()
    return e.sub(s, fill_value=0).to_dict()


def produtos_ativos():
    p = carregar("Produtos")
    return p[p["ativo"].astype(str).isin(["1", "1.0", "True", "true", "sim"])].copy()


# ---------------------------------------------------------------- login
def usuarios():
    u = segredo("usuarios")
    return {str(k).lower(): str(v) for k, v in dict(u).items()} if u else {"norma": "241618"}


def papel(u=None):
    u = u or st.session_state.get("usuario", "")
    p = segredo("papeis", u)
    if p:
        return str(p).lower()
    return "dona" if u == "norma" else "vendedora"


def eh_dona():
    return papel() == "dona"


def _chave():
    k = segredo("app", "chave") or (str(sorted(usuarios().items())) + str(segredo("planilha", "endereco")))
    return hashlib.sha256(str(k).encode()).digest()


def gerar_token(u):
    msg = f"{u}.{int(time.time()) + HORAS_LOGIN * 3600}"
    return msg + "." + hmac.new(_chave(), msg.encode(), hashlib.sha256).hexdigest()[:32]


def ler_token(t):
    try:
        u, exp, sig = str(t).rsplit(".", 2)
        msg = f"{u}.{exp}"
        certo = hmac.new(_chave(), msg.encode(), hashlib.sha256).hexdigest()[:32]
        if hmac.compare_digest(certo, sig) and int(exp) > time.time() and u in usuarios():
            return u
    except Exception:
        pass
    return None


def tela_login():
    _, meio, _ = st.columns([1, 1.25, 1])
    with meio, st.container(key="login"):
        st.markdown(f"""<div style="text-align:center">
          <img src="data:image/png;base64,{LOGO64}" style="width:132px;height:132px;border-radius:50%;
               border:3px solid {OURO};box-shadow:0 12px 30px rgba(74,14,24,.25)">
          <div style="font-size:.75rem;letter-spacing:.2em;text-transform:uppercase;color:{OURO};font-weight:900;margin-top:14px">Caixa</div>
          <div style="font-family:'Cormorant Garamond',serif;font-size:2.4rem;font-weight:700;color:{VINHO_E};line-height:1">Jardim do Éden</div>
          <div style="color:#8A7A65;margin:6px 0 10px">Toque no seu nome e digite a senha</div></div>""",
                    unsafe_allow_html=True)
        nomes = list(usuarios())
        with st.form("login", border=False):
            u = st.pills("Quem está entrando?", nomes, default=nomes[0] if len(nomes) == 1 else None,
                         format_func=lambda n: n.capitalize(), key="login_user")
            s = st.text_input("Senha", type="password", placeholder="••••••")
            ok = st.form_submit_button("Entrar", type="primary", width="stretch", icon=":material/login:")
        if ok and not u:
            st.error("Toque no seu nome.")
            return
        u = (u or "").lower()
        if ok:
            senha = usuarios().get(u)
            if senha is not None and hmac.compare_digest(senha.encode(), s.encode()):
                st.session_state.usuario = u
                st.query_params["k"] = gerar_token(u)
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")


# ---------------------------------------------------------------- VENDER
def buscar(q, prods):
    q = q.strip()
    if not q:
        return "nada", []
    exato = prods[prods["codigo"].astype(str).str.strip() == q]
    if q and len(exato) == 1:
        return "codigo", [exato.iloc[0]]
    m = re.fullmatch(r"(\d{1,4})(?:[.,](\d{1,2}))?", q)
    if m:
        if m.group(2) is not None:
            alvo = float(m.group(1) + "." + m.group(2).ljust(2, "0"))
            achou = prods[(prods["preco"] - alvo).abs() < 0.005]
        else:
            achou = prods[prods["preco"].apply(math.floor) == int(m.group(1))]
        if len(achou):
            return "preco", [r for _, r in achou.sort_values("nome").iterrows()]
    palavras = sem_acento(q).split()
    nomes = prods["nome"].map(sem_acento)
    filtro = nomes.apply(lambda n: all(p in n for p in palavras))
    return "nome", [r for _, r in prods[filtro].sort_values("nome").head(40).iterrows()]


def por_no_carrinho(p):
    cart = st.session_state.carrinho
    for it in cart:
        if it["id"] == p["id"]:
            it["qtd"] += 1
            break
    else:
        cart.append({"id": p["id"], "nome": p["nome"], "preco": float(p["preco"]), "qtd": 1})
    st.session_state.ultima = None
    st.toast(f"Adicionado: {p['nome']}", icon=":material/add_shopping_cart:")


FORMAS_BOTAO = [("Dinheiro", ":material/payments:"), ("Pix", ":material/qr_code_2:"),
                ("Crédito", ":material/credit_card:"), ("Débito", ":material/credit_card:")]


def grade_botoes(opcoes, chave, colunas=2):
    """Botões grandes para escolher (o escolhido fica dourado)."""
    escolhido = st.session_state.get(chave)
    with st.container(key=f"esc_{chave}"):
        cols = st.columns(colunas)
        for n, op in enumerate(opcoes):
            nome, icone = op if isinstance(op, tuple) else (op, None)
            if cols[n % colunas].button(nome, key=f"{chave}_{nome}", width="stretch", icon=icone,
                                        type="primary" if escolhido == nome else "secondary"):
                st.session_state[chave] = nome
                st.rerun()
    return escolhido


def tela_vender(loja):
    st.session_state.setdefault("carrinho", [])
    st.session_state.setdefault("resultados", [])
    cart = st.session_state.carrinho

    # ---- venda acabou de ser feita
    if st.session_state.get("ultima") and not cart:
        u = st.session_state.ultima
        st.markdown(f"""<div class='ok-card'><div class='ok-ic'>✓</div><div>
            <div class='ok-t'>Venda feita!</div>
            <div class='ok-s'>{brl(u['total'])} · {NOME_FORMA[u['forma']]} · {u['vendedor']}</div>
            {f"<div class='ok-troco'>Troco: {brl(u['troco'])}</div>" if u['forma'] == 'dinheiro' and float(u['troco']) > 0 else ""}
            </div></div>""", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("Nova venda", type="primary", width="stretch", icon=":material/add_shopping_cart:"):
            st.session_state.ultima = None
            st.rerun()
        c2.link_button("Mandar comprovante no WhatsApp", link_whats(texto_comprovante(u)), width="stretch",
                       icon=":material/send:")
        return

    if caixa_estado(loja)["situacao"] != "aberto":
        st.info("O caixa está fechado. Pode vender normalmente, mas lembre de **abrir o caixa**.", icon=":material/info:")
    prods = produtos_ativos()
    est = estoque()
    esq, dir_ = st.columns([1.2, 1], gap="large")

    with esq:
        st.markdown("<div class='passo'><span>1</span> O que a cliente vai levar?</div>", unsafe_allow_html=True)
        with st.container(key="busca"), st.form("busca", clear_on_submit=True, border=False):
            c1, c2 = st.columns([3.2, 1.3], vertical_alignment="bottom")
            q = c1.text_input("Procurar", label_visibility="collapsed",
                              placeholder="Nome, código ou preço (ex.: 129)")
            enviar = c2.form_submit_button("Procurar", type="primary", width="stretch", icon=":material/search:")
        focar_busca()
        if enviar:
            tipo, achados = buscar(q, prods)
            if tipo == "codigo" or (tipo == "preco" and len(achados) == 1):
                por_no_carrinho(achados[0])
                st.session_state.resultados = []
                st.rerun()
            elif not achados:
                st.session_state.resultados = []
                if q.strip():
                    st.warning(f"Não achei “{q}”. Tente outra palavra ou só o preço.")
            else:
                st.session_state.resultados = [dict(r) for r in achados]

        res = st.session_state.resultados
        if res:
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            c1.markdown(f"**{len(res)} encontrado(s)** — toque no produto certo:")
            if c2.button("Fechar", width="stretch", icon=":material/close:"):
                st.session_state.resultados = []
                st.rerun()
            with st.container(key="lista"):
                for i, p in enumerate(res):
                    q_est = int(est.get((loja, p["id"]), 0))
                    txt = f"{p['nome']}  \n**{brl(p['preco'])}** · {f'{q_est} em estoque' if q_est > 0 else 'sem estoque'}"
                    if st.button(txt, key=f"add{i}{p['id']}", width="stretch", icon=":material/add_circle:"):
                        por_no_carrinho(p)
                        st.session_state.resultados = []
                        st.rerun()
        elif cart:
            with st.expander("Atalhos de produtos", icon=":material/apps:"):
                atalhos(prods, est, loja)
        else:
            atalhos(prods, est, loja)

    with dir_, st.container(key="carrinho"):
        st.markdown(f"<div class='passo'><span>2</span> Venda · {loja}</div>", unsafe_allow_html=True)
        if not cart:
            st.markdown("<div class='vazio'>Nenhum produto ainda.<br>Procure ao lado ou toque num atalho.</div>",
                        unsafe_allow_html=True)
            return
        with st.container(key="itens"):
            for i, it in enumerate(list(cart)):
                st.markdown(f"<div class='item-n'>{it['nome']}</div>"
                            f"<div class='item-p'>{brl(it['preco'])} cada · <b>{brl(it['preco'] * it['qtd'])}</b></div>",
                            unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([1, 1, 1, 1.3], vertical_alignment="center")
                if c1.button("", key=f"menos{it['id']}", icon=":material/remove:", width="stretch", help="Tirar 1"):
                    if it["qtd"] > 1:
                        it["qtd"] -= 1
                    else:
                        cart.pop(i)
                    st.rerun()
                c2.markdown(f"<div class='qtd'>{it['qtd']}</div>", unsafe_allow_html=True)
                if c3.button("", key=f"mais{it['id']}", icon=":material/add:", width="stretch", help="Pôr mais 1"):
                    it["qtd"] += 1
                    st.rerun()
                if c4.button("Tirar", key=f"rm{it['id']}", icon=":material/delete:", width="stretch"):
                    cart.pop(i)
                    st.rerun()

        subtotal = round(sum(it["preco"] * it["qtd"] for it in cart), 2)
        desconto = 0.0
        if st.toggle("Dar desconto", key="com_desc"):
            d1, d2 = st.columns([1, 1.6], vertical_alignment="bottom")
            tipo_d = d1.segmented_control("Desconto em", ["R$", "%"], default="R$", key="tipo_desc") or "R$"
            vd = d2.number_input("Quanto?", min_value=0.0, value=0.0, step=1.0, format="%.2f", key="desconto")
            desconto = round(subtotal * min(vd, 100) / 100, 2) if tipo_d == "%" else min(vd, subtotal)
        total = round(subtotal - desconto, 2)
        st.markdown(f"<div class='total-box'><div class='total-l'>TOTAL</div><div class='total-grande'>{brl(total)}</div>"
                    + (f"<div class='total-d'>desconto de {brl(desconto)}</div>" if desconto else "") + "</div>",
                    unsafe_allow_html=True)

        st.markdown("<div class='passo'><span>3</span> Quem vendeu?</div>", unsafe_allow_html=True)
        vend = grade_botoes(VENDEDORES, "vendedor")
        st.markdown("<div class='passo'><span>4</span> Como a cliente pagou?</div>", unsafe_allow_html=True)
        forma_n = grade_botoes(FORMAS_BOTAO, "forma")

        recebido, troco = total, 0.0
        if forma_n == "Dinheiro":
            st.markdown("**Quanto a cliente deu?**")
            notas = [n for n in (20, 50, 100, 200) if n >= total][:3]
            ops = ["Valor certo"] + [f"R$ {n}" for n in notas] + ["Outro"]
            if st.session_state.get("deu") not in ops:
                st.session_state.deu = "Valor certo"
            deu = grade_botoes(ops, "deu", colunas=min(len(ops), 3))
            if deu == "Outro":
                recebido = st.number_input("Valor que a cliente deu (R$)", min_value=0.0, value=float(total),
                                           step=10.0, format="%.2f", key=f"rec{total}")
            elif deu and deu.startswith("R$"):
                recebido = float(deu[3:])
            troco = round(recebido - total, 2)
            if troco > 0:
                st.markdown(f"<div class='troco'>Troco: <b>{brl(troco)}</b></div>", unsafe_allow_html=True)

        with st.container(key="concluir"):
            if st.button(f"Concluir venda · {brl(total)}", type="primary", width="stretch", icon=":material/check_circle:"):
                erro = None
                if not vend:
                    erro = "Toque em quem vendeu (passo 3)."
                elif not forma_n:
                    erro = "Toque em como a cliente pagou (passo 4)."
                elif forma_n == "Dinheiro" and recebido < total:
                    erro = "O dinheiro que a cliente deu é menor que o total."
                if erro:
                    st.error(erro, icon=":material/error:")
                else:
                    finalizar(loja, vend, {"Dinheiro": "dinheiro", "Pix": "pix", "Crédito": "credito",
                                           "Débito": "debito"}[forma_n], subtotal, desconto, total, recebido, troco)
        if st.button("Cancelar esta venda", width="stretch", icon=":material/close:"):
            limpar_venda()
            st.rerun()


def focar_busca():
    """Deixa o cursor na busca (no computador), para o leitor de código de barras já funcionar."""
    js = """
    const d = window.parent.document;
    setTimeout(() => {
      const i = d.querySelector('.st-key-busca input');
      const a = d.activeElement;
      if (i && window.parent.innerWidth > 900 && (!a || !['INPUT','TEXTAREA'].includes(a.tagName))) i.focus();
    }, 350); // %s
    """ % time.time()
    try:
        st.html(f"<script>{js}</script>", unsafe_allow_javascript=True)
    except TypeError:  # Streamlit mais antigo
        import streamlit.components.v1 as components
        components.html(f"<script>{js}</script>", height=0)


def atalhos(prods, est, loja):
    """Botões grandes dos produtos que mais saem — é só tocar, sem digitar."""
    it = carregar("Itens")
    v = carregar("Vendas")
    ok = set(v.loc[v["status"] != "cancelada", "id"])
    it = it[it["venda_id"].isin(ok) & it["produto_id"].isin(prods["id"])]
    ids = list(it.groupby("produto_id")["qtd"].sum().sort_values(ascending=False).head(12).index)
    titulo = "Mais vendidos"
    if len(ids) < 4:
        faixa = prods[prods["nome"].str.startswith(("LINGERIE", "PRÓTESE"))].sort_values("preco")
        ids += [i for i in faixa["id"] if i not in ids][:12 - len(ids)]
        titulo = "Atalhos"
    if not ids:
        st.caption("Dica: digite só o valor (ex.: 189) para ver os produtos desse preço.")
        return
    st.markdown(f"**{titulo}** <span class='sub'>· toque para pôr na venda</span>", unsafe_allow_html=True)
    base = prods.set_index("id")
    with st.container(key="grade"):
        cols = st.columns(3)
        for n, pid in enumerate(ids[:12]):
            p = base.loc[pid]
            q_est = int(est.get((loja, pid), 0))
            txt_est = f"{q_est} em est." if q_est > 0 else "sem estoque"
            if cols[n % 3].button(f"{p['nome'][:38]}  \n**{brl(p['preco'])}** · {txt_est}", key=f"at{pid}",
                                  width="stretch"):
                por_no_carrinho(dict(p, id=pid))
                st.rerun()


def limpar_venda():
    st.session_state.carrinho = []
    st.session_state.resultados = []
    for k in [k for k in st.session_state if k in ("desconto", "forma", "tipo_desc", "deu", "com_desc") or str(k).startswith("rec")]:
        st.session_state.pop(k, None)


def finalizar(loja, vend, forma, subtotal, desconto, total, recebido, troco):
    vid = novo_id("V")
    data = agora_txt()
    venda = {"id": vid, "data": data, "loja": loja, "vendedor": vend, "forma": forma,
             "subtotal": subtotal, "desconto": desconto, "total": total, "recebido": recebido,
             "troco": troco, "usuario": st.session_state.usuario, "status": "ok"}
    itens = [{"venda_id": vid, "data": data, "loja": loja, "produto_id": it["id"], "produto": it["nome"],
              "qtd": it["qtd"], "preco": it["preco"], "total": round(it["preco"] * it["qtd"], 2)}
             for it in st.session_state.carrinho]
    try:
        with st.spinner("Salvando a venda na planilha…"):
            banco().anexar("Itens", itens)
            banco().anexar("Vendas", [venda])
    except Exception as e:
        st.error(f"Não consegui salvar a venda. Confira a internet e tente de novo. ({e})")
        return
    gravou()
    st.session_state.ultima = dict(venda, itens=itens)
    limpar_venda()
    st.rerun()


# ---------------------------------------------------------------- PRODUTOS (o custo só aparece aqui)
def tela_produtos():
    prods = carregar("Produtos").copy()
    est = estoque()
    st.markdown("#### Produtos e preços")
    st.caption("Regra da casa: preço = custo × 5, terminando em 9,99. O custo só aparece nesta tela.")

    with st.expander("Cadastrar produto novo", icon=":material/add_box:"):
        with st.form("novo", clear_on_submit=True):
            nome = st.text_input("Nome do produto")
            c1, c2, c3 = st.columns(3)
            codigo = c1.text_input("Código de barras (opcional)")
            custo = c2.number_input("Custo (R$)", min_value=0.0, step=0.5, format="%.2f")
            preco = c3.number_input("Preço de venda (R$) — 0 usa a regra", min_value=0.0, step=1.0, format="%.2f")
            qtd = st.number_input("Quantidade que chegou (opcional)", min_value=0, step=1)
            loja_q = st.selectbox("Em qual loja?", LOJAS)
            if st.form_submit_button("Cadastrar", type="primary"):
                if not nome.strip():
                    st.error("Escreva o nome do produto.")
                elif codigo.strip() and (prods["codigo"].astype(str) == codigo.strip()).any():
                    st.error("Já existe um produto com esse código.")
                else:
                    p_final = preco if preco > 0 else preco_regra(custo)
                    if p_final <= 0:
                        st.error("Informe o custo ou o preço.")
                    else:
                        ids = prods["id"].str.extract(r"P(\d+)")[0].dropna().astype(int)
                        pid = f"P{(ids.max() + 1 if len(ids) else 1):04d}"
                        banco().anexar("Produtos", [{"id": pid, "nome": nome.strip().upper(), "codigo": codigo.strip(),
                                                     "custo": custo, "preco": p_final, "ativo": "1"}])
                        if qtd > 0:
                            banco().anexar("Entradas", [{"id": novo_id("E"), "data": agora_txt(), "loja": loja_q,
                                                         "produto_id": pid, "produto": nome.strip().upper(), "qtd": qtd,
                                                         "obs": "cadastro", "usuario": st.session_state.usuario}])
                        gravou()
                        st.success(f"{nome.strip().upper()} cadastrado por {brl(p_final)}.")

    filtro = st.text_input("Procurar produto", placeholder="nome ou código")
    vis = prods
    if filtro.strip():
        pal = sem_acento(filtro).split()
        vis = prods[prods.apply(lambda r: all(p in sem_acento(r["nome"]) + " " + str(r["codigo"]) for p in pal), axis=1)]
    vis = vis.sort_values("nome").copy()
    vis["ativo"] = vis["ativo"].astype(str).isin(["1", "1.0", "True", "true", "sim"])
    vis["regra"] = vis["custo"].apply(preco_regra)
    for l in LOJAS:
        vis[l] = vis["id"].apply(lambda i: int(est.get((l, i), 0)))
    st.caption(f"{len(vis)} produto(s). Mude o preço, o custo ou o código direto na tabela e clique em Salvar.")
    editado = st.data_editor(
        vis[["id", "nome", "codigo", "custo", "preco", "regra", *LOJAS, "ativo"]],
        hide_index=True, width="stretch", height=480, key="ed_prod",
        disabled=["id", "regra", *LOJAS],
        column_config={
            "id": st.column_config.TextColumn("Nº", width="small"),
            "nome": st.column_config.TextColumn("Produto", width="large"),
            "codigo": st.column_config.TextColumn("Código"),
            "custo": st.column_config.NumberColumn("Custo", format="R$ %.2f", min_value=0),
            "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f", min_value=0),
            "regra": st.column_config.NumberColumn("Pela regra", format="R$ %.2f"),
            "Aterrado": st.column_config.NumberColumn("Est. Aterrado", width="small"),
            "Vila Santa Cecília": st.column_config.NumberColumn("Est. Vila", width="small"),
            "ativo": st.column_config.CheckboxColumn("À venda"),
        })
    c1, c2 = st.columns(2)
    if c1.button("Salvar alterações", type="primary", width="stretch", icon=":material/save:"):
        base = prods.set_index("id")
        mudou = 0
        for _, r in editado.iterrows():
            novo = {"nome": str(r["nome"]).strip(), "codigo": "" if pd.isna(r["codigo"]) else str(r["codigo"]).strip(),
                    "custo": float(r["custo"] or 0), "preco": float(r["preco"] or 0), "ativo": "1" if r["ativo"] else "0"}
            antigo = base.loc[r["id"]]
            if any(str(antigo[k]) != str(v) for k, v in novo.items() if k in ("nome", "codigo", "ativo")) or \
                    abs(float(antigo["custo"]) - novo["custo"]) > 1e-9 or abs(float(antigo["preco"]) - novo["preco"]) > 1e-9:
                for k, v in novo.items():
                    base.at[r["id"], k] = v
                mudou += 1
        if mudou:
            banco().regravar("Produtos", base.reset_index())
            gravou()
            st.success(f"{mudou} produto(s) atualizado(s).")
        else:
            st.info("Nada mudou.")
    with c2.popover("Aplicar a regra em todos", width="stretch"):
        st.write("Recalcula o preço de **todos os produtos com custo** (custo × 5, final 9,99).")
        if st.button("Sim, recalcular", type="primary"):
            p = prods.copy()
            com = p["custo"] > 0
            p.loc[com, "preco"] = p.loc[com, "custo"].apply(preco_regra)
            banco().regravar("Produtos", p)
            gravou()
            st.success(f"{int(com.sum())} preços recalculados.")


# ---------------------------------------------------------------- ESTOQUE
def tela_estoque(loja):
    prods = produtos_ativos().sort_values("nome")
    est = estoque()
    st.markdown(f"#### Estoque · {loja}")
    opcoes = {f"{r['nome']} — {brl(r['preco'])}": r for _, r in prods.iterrows()}
    t1, t2 = st.tabs([":material/local_shipping: Chegou mercadoria", ":material/fact_check: Contagem"])
    with t1, st.form("entrada", clear_on_submit=True):
        esc = st.selectbox("Produto", list(opcoes), index=None, placeholder="Digite para procurar…")
        qtd = st.number_input("Quantidade que chegou", min_value=1, step=1)
        obs = st.text_input("Observação (opcional)", placeholder="ex.: pedido Hot Rio 12/11")
        if st.form_submit_button("Lançar entrada", type="primary"):
            if not esc:
                st.error("Escolha o produto.")
            else:
                p = opcoes[esc]
                banco().anexar("Entradas", [{"id": novo_id("E"), "data": agora_txt(), "loja": loja, "produto_id": p["id"],
                                             "produto": p["nome"], "qtd": qtd, "obs": obs, "usuario": st.session_state.usuario}])
                gravou()
                st.success(f"+{qtd} {p['nome']} em {loja}.")
    if not eh_dona():
        t2.caption("O acerto de estoque é feito pela dona.")
    else:
        with t2, st.form("contagem", clear_on_submit=True):
            esc = st.selectbox("Produto ", list(opcoes), index=None, placeholder="Digite para procurar…")
            contado = st.number_input("Quantas peças tem na prateleira agora?", min_value=0, step=1)
            if st.form_submit_button("Acertar estoque", type="primary"):
                if not esc:
                    st.error("Escolha o produto.")
                else:
                    p = opcoes[esc]
                    dif = int(contado) - int(est.get((loja, p["id"]), 0))
                    if dif == 0:
                        st.info("O estoque já está certo.")
                    else:
                        banco().anexar("Entradas", [{"id": novo_id("E"), "data": agora_txt(), "loja": loja, "produto_id": p["id"],
                                                     "produto": p["nome"], "qtd": dif, "obs": "acerto de contagem",
                                                     "usuario": st.session_state.usuario}])
                        gravou()
                        st.success(f"Estoque de {p['nome']} acertado para {int(contado)}.")
    tab = prods[["id", "nome", "preco"]].copy()
    tab["estoque"] = tab["id"].apply(lambda i: int(est.get((loja, i), 0)))
    so = st.segmented_control("Mostrar", ["Todos", "Acabando (até 2)", "Sem estoque"], default="Todos")
    if so == "Acabando (até 2)":
        tab = tab[(tab["estoque"] > 0) & (tab["estoque"] <= 2)]
    elif so == "Sem estoque":
        tab = tab[tab["estoque"] <= 0]
    st.dataframe(tab[["nome", "preco", "estoque"]], hide_index=True, width="stretch", height=420,
                 column_config={"nome": "Produto", "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                                "estoque": "Em estoque"})


# ---------------------------------------------------------------- período / filtros
def periodo(nome):
    hoje = agora().replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    if nome == "Hoje":
        return hoje, hoje + timedelta(days=1)
    if nome == "Ontem":
        return hoje - timedelta(days=1), hoje
    if nome == "7 dias":
        return hoje - timedelta(days=6), hoje + timedelta(days=1)
    if nome == "30 dias":
        return hoje - timedelta(days=29), hoje + timedelta(days=1)
    if nome == "Este mês":
        return hoje.replace(day=1), hoje + timedelta(days=1)
    return datetime(2000, 1, 1), hoje + timedelta(days=1)


def vendas_periodo(nome, loja):
    v = carregar("Vendas").copy()
    v["dt"] = pd.to_datetime(v["data"], errors="coerce")
    a, b = periodo(nome)
    v = v[(v["dt"] >= a) & (v["dt"] < b)]
    if loja != "Todas":
        v = v[v["loja"] == loja]
    return v, a, b


# ---------------------------------------------------------------- VENDAS FEITAS
def tela_vendas(loja_atual):
    st.markdown("#### Vendas feitas")
    c1, c2 = st.columns(2)
    per = c1.selectbox("Período", ["Hoje", "Ontem", "7 dias", "30 dias", "Este mês", "Tudo"])
    loja = c2.selectbox("Loja", ["Todas", *LOJAS], index=1 + LOJAS.index(loja_atual))
    v, _, _ = vendas_periodo(per, loja)
    v = v.sort_values("dt", ascending=False)
    ok = v[v["status"] != "cancelada"]
    st.caption(f"{len(ok)} venda(s) · {brl(ok['total'].sum())}" + (f" · {len(v) - len(ok)} cancelada(s)" if len(v) > len(ok) else ""))
    if v.empty:
        st.info("Nenhuma venda nesse período.")
        return
    mostra = v.assign(hora=v["dt"].dt.strftime("%d/%m %H:%M"), pagamento=v["forma"].map(NOME_FORMA).fillna(v["forma"]),
                      situacao=v["status"].map({"ok": "ok", "cancelada": "CANCELADA"}))
    st.dataframe(mostra[["id", "hora", "loja", "vendedor", "pagamento", "total", "situacao"]], hide_index=True,
                 width="stretch", height=320,
                 column_config={"id": "Venda", "hora": "Quando", "loja": "Loja", "vendedor": "Vendedor(a)",
                                "pagamento": "Pagamento", "total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                                "situacao": "Situação"})
    escolha = st.selectbox("Ver itens de uma venda", v["id"].tolist(), index=None, placeholder="Escolha a venda…",
                           format_func=lambda i: f"{i} · {brl(v.set_index('id').at[i, 'total'])}")
    if escolha:
        it = carregar("Itens")
        it = it[it["venda_id"] == escolha]
        st.dataframe(it[["produto", "qtd", "preco", "total"]], hide_index=True, width="stretch",
                     column_config={"produto": "Produto", "qtd": "Qtd",
                                    "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                                    "total": st.column_config.NumberColumn("Total", format="R$ %.2f")})
        if v.set_index("id").at[escolha, "status"] != "cancelada" and not eh_dona():
            st.caption("Para cancelar uma venda, peça para a dona.")
        elif v.set_index("id").at[escolha, "status"] != "cancelada":
            with st.popover("Cancelar esta venda"):
                st.write("Os produtos voltam para o estoque e a venda sai do painel.")
                if st.button("Sim, cancelar a venda", type="primary"):
                    banco().mudar("Vendas", "id", escolha, "status", "cancelada")
                    gravou()
                    st.success("Venda cancelada.")
                    st.rerun()


# ---------------------------------------------------------------- PAINEL
def excel(vendas, itens):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        vendas.drop(columns=["dt"], errors="ignore").to_excel(w, sheet_name="Vendas", index=False)
        itens.to_excel(w, sheet_name="Itens", index=False)
    return buf.getvalue()


def tela_painel(loja_atual):
    st.markdown("#### Painel")
    c1, c2 = st.columns(2)
    per = c1.segmented_control("Período", ["Hoje", "Ontem", "7 dias", "30 dias", "Este mês", "Tudo"], default="7 dias") or "7 dias"
    loja = c2.segmented_control("Loja", ["Todas", *LOJAS], default="Todas") or "Todas"
    v, a, b = vendas_periodo(per, loja)
    v = v[v["status"] != "cancelada"]
    it = carregar("Itens")
    it = it[it["venda_id"].isin(v["id"])]

    # comparação com o período anterior do mesmo tamanho
    todas = carregar("Vendas").copy()
    todas["dt"] = pd.to_datetime(todas["data"], errors="coerce")
    ant = todas[(todas["dt"] >= a - (b - a)) & (todas["dt"] < a) & (todas["status"] != "cancelada")]
    if loja != "Todas":
        ant = ant[ant["loja"] == loja]
    tot, n = v["total"].sum(), len(v)
    delta = None if per == "Tudo" or ant.empty else f"{(tot - ant['total'].sum()) / max(ant['total'].sum(), 0.01) * 100:+.0f}% vs. período anterior"
    custos = carregar("Produtos").set_index("id")["custo"]
    com_custo = it[it["produto_id"].map(custos).fillna(0) > 0]
    lucro = (com_custo["total"] - com_custo["qtd"] * com_custo["produto_id"].map(custos)).sum()
    desc_rateio = v["desconto"].sum()
    m1, m2, m3, m4, m5 = st.container(key="kpis").columns(5)
    m1.metric("Total vendido", brl(tot), delta)
    m2.metric("Vendas", n)
    m3.metric("Venda média", brl(tot / n if n else 0))
    m4.metric("Peças vendidas", int(it["qtd"].sum()))
    m5.metric("Lucro bruto estimado", brl(lucro - desc_rateio),
              help="Preço de venda menos o custo atual do produto, já tirando os descontos. "
                   "Produtos sem custo (lingerie e prótese por faixa) ficam de fora.")
    if v.empty:
        st.info("Nenhuma venda nesse período.")
        return

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Por forma de pagamento**")
        f = v.groupby("forma")["total"].sum().rename(index=NOME_FORMA).sort_values(ascending=False)
        st.bar_chart(f, horizontal=True, color="#E0A21B", y_label="", x_label="R$")
    with g2:
        st.markdown("**Por loja**")
        lj = v.groupby("loja")["total"].sum().sort_values(ascending=False)
        st.bar_chart(lj, horizontal=True, color="#7A1726", y_label="", x_label="R$")

    st.markdown("**Por dia**")
    dia = v.groupby(v["dt"].dt.date)["total"].sum()
    dia.index = pd.to_datetime(dia.index)
    st.bar_chart(dia, color="#E0A21B", y_label="R$", x_label="")

    g3, g4 = st.columns(2)
    with g3:
        st.markdown("**Por vendedor(a)**")
        eq = v.groupby("vendedor").agg(total=("total", "sum"), vendas=("id", "count"))
        eq["média"] = eq["total"] / eq["vendas"]
        st.dataframe(eq.sort_values("total", ascending=False), width="stretch",
                     column_config={"total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                                    "média": st.column_config.NumberColumn("Venda média", format="R$ %.2f")})
    with g4:
        st.markdown("**Vendedor(a) × pagamento**")
        cruz = v.pivot_table(index="vendedor", columns="forma", values="total", aggfunc="sum", fill_value=0)
        cruz.columns = [NOME_FORMA.get(c, c) for c in cruz.columns]
        st.dataframe(cruz, width="stretch",
                     column_config={c: st.column_config.NumberColumn(c, format="R$ %.2f") for c in cruz.columns})

    g5, g6 = st.columns(2)
    with g5:
        st.markdown("**Mais vendidos**")
        top = it.groupby("produto").agg(qtd=("qtd", "sum"), total=("total", "sum")).sort_values("qtd", ascending=False).head(10)
        st.dataframe(top, width="stretch",
                     column_config={"qtd": "Peças", "total": st.column_config.NumberColumn("Total", format="R$ %.2f")})
    with g6:
        st.markdown("**Por horário**")
        hora = v.groupby(v["dt"].dt.hour)["total"].sum()
        hora.index = [f"{h:02d}h" for h in hora.index]
        st.bar_chart(hora, color="#7A1726", y_label="R$", x_label="")

    st.download_button("Baixar estas vendas em Excel", icon=":material/download:", data=excel(v, it),
                       file_name=f"vendas-{per.lower().replace(' ', '-')}-{agora():%Y-%m-%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------- WhatsApp
def link_whats(texto):
    return "https://wa.me/?text=" + urllib.parse.quote(texto)


def texto_comprovante(v):
    linhas = [f"*Jardim do Éden* · {v['loja']}", f"Compra nº {v['id']} · {v['data'][8:10]}/{v['data'][5:7]}/{v['data'][:4]} {v['data'][11:16]}", ""]
    for it in v.get("itens", []):
        linhas.append(f"{int(it['qtd'])}x {it['produto']} — {brl(it['total'])}")
    if float(v["desconto"]):
        linhas.append(f"Desconto: -{brl(v['desconto'])}")
    linhas += ["", f"*Total: {brl(v['total'])}* ({NOME_FORMA[v['forma']]})"]
    if v["forma"] == "dinheiro" and float(v["troco"]) > 0:
        linhas.append(f"Recebido {brl(v['recebido'])} · troco {brl(v['troco'])}")
    linhas += ["", "Obrigada pela preferência! 💋"]
    return "\n".join(linhas)


# ---------------------------------------------------------------- CAIXA (abrir, sangria, fechar)
def caixa_estado(loja):
    cx = carregar("Caixa").copy()
    cx["dt"] = pd.to_datetime(cx["data"], errors="coerce")
    cx = cx[cx["loja"] == loja].sort_values("dt")
    ab = cx[cx["tipo"] == "abertura"]
    if ab.empty:
        return {"situacao": "nunca"}
    a = ab.iloc[-1]
    depois = cx[cx["dt"] >= a["dt"]]
    fech = depois[depois["tipo"] == "fechamento"]
    v = carregar("Vendas").copy()
    v["dt"] = pd.to_datetime(v["data"], errors="coerce")
    fim = fech.iloc[0]["dt"] if len(fech) else pd.Timestamp.max
    v = v[(v["loja"] == loja) & (v["status"] != "cancelada") & (v["dt"] >= a["dt"]) & (v["dt"] <= fim)]
    por = v.groupby("forma")["total"].sum().to_dict()
    sang = depois[(depois["tipo"] == "sangria") & (depois["dt"] <= fim)]["valor"].sum()
    refo = depois[(depois["tipo"] == "reforco") & (depois["dt"] <= fim)]["valor"].sum()
    esperado = float(a["valor"]) + por.get("dinheiro", 0) + refo - sang
    est = {"situacao": "fechado" if len(fech) else "aberto", "inicio": a["dt"], "inicial": float(a["valor"]),
           "por": por, "sangria": sang, "reforco": refo, "esperado": round(esperado, 2), "vendas": v,
           "movs": depois[depois["tipo"].isin(["sangria", "reforco"]) & (depois["dt"] <= fim)]}
    if len(fech):
        est["contado"] = float(fech.iloc[0]["valor"])
        est["fim"] = fim
    return est


def texto_resumo(loja, e):
    v = e["vendas"]
    linhas = [f"*Jardim do Éden · {loja}*", f"Caixa de {e['inicio']:%d/%m} das {e['inicio']:%H:%M}"
              + (f" às {e['fim']:%H:%M}" if "fim" in e else ""), "",
              f"Vendas: {len(v)} · *{brl(v['total'].sum())}*"]
    for k, nome in NOME_FORMA.items():
        if e["por"].get(k):
            linhas.append(f"• {nome}: {brl(e['por'][k])}")
    if len(v):
        linhas += ["", "Por vendedor(a):"]
        for nome, val in v.groupby("vendedor")["total"].sum().sort_values(ascending=False).items():
            linhas.append(f"• {nome}: {brl(val)}")
    linhas += ["", f"Dinheiro na gaveta (esperado): {brl(e['esperado'])}"]
    if "contado" in e:
        d = e["contado"] - e["esperado"]
        linhas.append(f"Contado: {brl(e['contado'])} · " + ("conferiu ✅" if abs(d) < 0.005 else
                                                            (f"sobrou {brl(d)}" if d > 0 else f"faltou {brl(-d)}")))
    return "\n".join(linhas)


def mov_caixa(loja, tipo, valor, obs=""):
    banco().anexar("Caixa", [{"id": novo_id("C"), "data": agora_txt(), "loja": loja, "tipo": tipo,
                              "valor": valor, "obs": obs, "usuario": st.session_state.usuario}])
    gravou()


def tela_caixa(loja):
    e = caixa_estado(loja)
    st.markdown(f"#### Caixa · {loja}")
    if e["situacao"] != "aberto":
        if e["situacao"] == "fechado":
            st.caption(f"Último caixa: {e['inicio']:%d/%m %H:%M} até {e['fim']:%H:%M}.")
            st.link_button("Reenviar o resumo desse caixa", link_whats(texto_resumo(loja, e)), icon=":material/send:")
        with st.form("abrir"):
            st.markdown("**Abrir o caixa**")
            ini = st.number_input("Quanto tem de dinheiro na gaveta agora? (troco)", min_value=0.0, step=10.0,
                                  format="%.2f", value=float(e.get("contado", 0.0)))
            if st.form_submit_button("Abrir caixa", type="primary", width="stretch"):
                mov_caixa(loja, "abertura", ini)
                st.rerun()
        return

    v = e["vendas"]
    st.caption(f"Aberto desde {e['inicio']:%d/%m às %H:%M} · começou com {brl(e['inicial'])}")
    if e["inicio"].date() < agora().date():
        st.warning("Este caixa é de outro dia. Feche agora e abra um novo.")
    m1, m2, m3 = st.container(key="kpis").columns(3)
    m1.metric("Vendido no caixa", brl(v["total"].sum()), f"{len(v)} venda(s)", delta_color="off")
    m2.metric("Dinheiro na gaveta", brl(e["esperado"]), help="Troco inicial + vendas em dinheiro + reforços − retiradas")
    m3.metric("Pix + cartões", brl(sum(e["por"].get(k, 0) for k in ("pix", "credito", "debito"))))
    st.dataframe(pd.DataFrame([{"Forma": NOME_FORMA[k], "Total": brl(e["por"].get(k, 0))} for k in NOME_FORMA]),
                 hide_index=True, width="stretch")

    c1, c2 = st.columns(2)
    with c1.form("mov", clear_on_submit=True):
        st.markdown("**Tirar ou colocar dinheiro**")
        tipo = st.segmented_control("O quê?", ["Tirei (sangria)", "Coloquei (reforço)"], default="Tirei (sangria)")
        val = st.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")
        mot = st.text_input("Motivo", placeholder="ex.: pagamento do motoboy")
        if st.form_submit_button("Registrar", width="stretch"):
            if val <= 0:
                st.error("Informe o valor.")
            else:
                mov_caixa(loja, "sangria" if (tipo or "").startswith("Tirei") else "reforco", val, mot)
                st.rerun()
    with c2.form("fechar"):
        st.markdown("**Fechar o caixa**")
        cont = st.number_input("Conte o dinheiro da gaveta. Quanto deu?", min_value=0.0, step=10.0, format="%.2f")
        if st.form_submit_button("Fechar caixa", type="primary", width="stretch"):
            d = round(cont - e["esperado"], 2)
            mov_caixa(loja, "fechamento", cont, f"esperado {e['esperado']:.2f}; diferença {d:+.2f}")
            st.session_state.fechou = True
            st.rerun()
    if len(e["movs"]):
        st.markdown("**Retiradas e reforços**")
        mv = e["movs"].assign(hora=e["movs"]["dt"].dt.strftime("%H:%M"),
                              o_que=e["movs"]["tipo"].map({"sangria": "Tirou", "reforco": "Colocou"}),
                              valor=e["movs"]["valor"].map(brl))
        st.dataframe(mv[["hora", "o_que", "valor", "obs", "usuario"]], hide_index=True, width="stretch",
                     column_config={"hora": "Hora", "o_que": "", "valor": "Valor",
                                    "obs": "Motivo", "usuario": "Quem"})
    st.link_button("Mandar o resumo parcial no WhatsApp", link_whats(texto_resumo(loja, e)), icon=":material/send:")


# ---------------------------------------------------------------- HOJE (tela inicial)
def tela_hoje(loja):
    h = agora()
    saud = "Bom dia" if h.hour < 12 else "Boa tarde" if h.hour < 18 else "Boa noite"
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    st.markdown(f"<div class='saud'>{saud}, {st.session_state.usuario.capitalize()}!</div>"
                f"<div class='data'>{loja} · {dias[h.weekday()]}, {h:%d/%m/%Y}</div>", unsafe_allow_html=True)
    if st.session_state.pop("fechou", False):
        e = caixa_estado(loja)
        if e["situacao"] == "fechado":
            d = e["contado"] - e["esperado"]
            (st.success if abs(d) < 0.005 else st.warning)(
                "Caixa fechado. " + ("O dinheiro conferiu ✅" if abs(d) < 0.005 else
                                     (f"Sobrou {brl(d)}." if d > 0 else f"Faltou {brl(-d)}.")))
            st.link_button("Mandar o resumo do dia no WhatsApp", link_whats(texto_resumo(loja, e)), type="primary",
                           icon=":material/send:")

    vh, _, _ = vendas_periodo("Hoje", loja)
    vh = vh[vh["status"] != "cancelada"]
    vo, _, _ = vendas_periodo("Ontem", loja)
    vo = vo[vo["status"] != "cancelada"]
    t, to = vh["total"].sum(), vo["total"].sum()
    e = caixa_estado(loja)
    with st.container(key="acoes"):
        b1, b2 = st.columns(2)
        if b1.button("Nova venda", type="primary", width="stretch", icon=":material/add_shopping_cart:"):
            st.session_state.ir = M_VENDER
            st.rerun()
        if b2.button("Fechar o caixa" if e["situacao"] == "aberto" else "Abrir o caixa", width="stretch",
                     icon=":material/point_of_sale:"):
            st.session_state.ir = M_CAIXA
            st.rerun()
        b3, b4 = st.columns(2)
        if b3.button("Chegou mercadoria", width="stretch", icon=":material/local_shipping:"):
            st.session_state.ir = M_EST
            st.rerun()
        if b4.button("Vendas de hoje", width="stretch", icon=":material/receipt_long:"):
            st.session_state.ir = M_MAIS
            st.session_state.sub = M_VENDAS
            st.rerun()

    m1, m2, m3, m4 = st.container(key="kpis").columns(4)
    m1.metric("Vendido hoje", brl(t), f"{(t - to) / to * 100:+.0f}% que ontem" if to else None)
    m2.metric("Vendas hoje", len(vh))
    m3.metric("Venda média", brl(t / len(vh) if len(vh) else 0))
    m4.metric("Caixa", {"aberto": "Aberto", "fechado": "Fechado", "nunca": "Fechado"}[e["situacao"]],
              f"desde {e['inicio']:%H:%M}" if e["situacao"] == "aberto" else None, delta_color="off")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Hoje por forma de pagamento**")
        if vh.empty:
            st.caption("Nenhuma venda ainda hoje.")
        else:
            f = vh.groupby("forma")["total"].sum()
            st.dataframe(pd.DataFrame({"Forma": [NOME_FORMA.get(k, k) for k in f.index], "Total": [brl(x) for x in f.values]}),
                         hide_index=True, width="stretch")
            st.markdown("**Hoje por vendedor(a)**")
            eq = vh.groupby("vendedor").agg(Total=("total", "sum"), Vendas=("id", "count")).sort_values("Total", ascending=False)
            eq["Total"] = eq["Total"].map(brl)
            st.dataframe(eq.rename_axis("Vendedor(a)"), width="stretch")
    with c2:
        st.markdown("**Precisa repor**")
        ent = carregar("Entradas")
        ja_teve = set(ent.loc[ent["loja"] == loja, "produto_id"])
        est = estoque()
        p = produtos_ativos()
        p = p[p["id"].isin(ja_teve)].copy()
        p["estoque"] = p["id"].apply(lambda i: int(est.get((loja, i), 0)))
        p = p[p["estoque"] <= 2].sort_values(["estoque", "nome"])
        if p.empty:
            st.caption("Nada acabando. 🎉" if ja_teve else "Lance o estoque em Estoque para ver o que está acabando.")
        else:
            st.dataframe(p[["nome", "estoque"]], hide_index=True, width="stretch", height=min(38 * len(p) + 40, 360),
                         column_config={"nome": "Produto", "estoque": "Restam"})


# ---------------------------------------------------------------- app
def main():
    if "usuario" not in st.session_state:
        u = ler_token(st.query_params.get("k", ""))
        if u:
            st.session_state.usuario = u
        else:
            tela_login()
            return
    try:
        preparar_produtos()
    except Exception as e:
        st.error(f"Não consegui abrir a planilha. Confira a internet e a configuração. ({e})")
        st.stop()

    topo = st.container(key="topo")
    topo1, topo2, topo3 = topo.columns([3, 2, 1.1], vertical_alignment="center")
    topo1.markdown(f"<div class='marca'><img src='data:image/png;base64,{LOGO64}'><div>"
                   f"<div class='t2'>Caixa · {'Dona' if eh_dona() else 'Vendedora'}</div><div class='t1'>Jardim do Éden</div></div></div>",
                   unsafe_allow_html=True)
    if "loja" not in st.session_state:
        q = st.query_params.get("loja", "")
        st.session_state.loja = LOJAS[int(q)] if q.isdigit() and int(q) < len(LOJAS) else LOJAS[0]
    loja = topo2.selectbox("Loja", LOJAS, key="loja", label_visibility="collapsed")
    st.query_params["loja"] = str(LOJAS.index(loja))
    with topo3.popover(st.session_state.usuario.capitalize(), width="stretch", icon=":material/person:"):
        if st.button("Atualizar dados", width="stretch", icon=":material/refresh:"):
            gravou()
            st.rerun()
        if st.button("Sair", width="stretch", icon=":material/logout:"):
            st.session_state.clear()
            st.query_params.pop("k", None)
            st.rerun()
    if isinstance(banco(), BancoLocal):
        falta = [n for n, ok in [("a chave do Google (gcp_json ou gcp_service_account)", credenciais()),
                                 ("o endereço da planilha ([planilha] endereco)", segredo("planilha", "endereco"))] if not ok]
        st.warning("**Modo de teste** — as vendas NÃO estão indo para a planilha. Falta nos Secrets: "
                   + " e ".join(falta) + ". Depois de salvar os Secrets, clique em **Manage app → ⋮ → Reboot app**.",
                   icon=":material/warning:")

    menu = [M_HOJE, M_VENDER, M_CAIXA, M_EST, M_MAIS]
    if "ir" in st.session_state:
        st.session_state.tela = st.session_state.pop("ir")
    if st.session_state.get("tela") not in menu:
        st.session_state.tela = M_HOJE
    with st.container(key="menu"):
        tela = st.segmented_control("Menu", menu, key="tela", label_visibility="collapsed", width="stretch") or M_HOJE
    if tela == M_MAIS:
        sub_menu = [M_VENDAS] + ([M_PROD, M_PAINEL] if eh_dona() else [])
        if st.session_state.get("sub") not in sub_menu:
            st.session_state.sub = M_VENDAS
        with st.container(key="submenu"):
            tela = st.segmented_control("Mais", sub_menu, key="sub", label_visibility="collapsed", width="stretch") or M_VENDAS
    if tela == M_HOJE:
        tela_hoje(loja)
    elif tela == M_CAIXA:
        tela_caixa(loja)
    elif tela == M_VENDER:
        tela_vender(loja)
    elif tela == M_EST:
        tela_estoque(loja)
    elif tela == M_PROD and eh_dona():
        tela_produtos()
    elif tela == M_VENDAS:
        tela_vendas(loja)
    elif tela == M_PAINEL and eh_dona():
        tela_painel(loja)


main()
