# Caixa Jardim do Éden — PDV das lojas Aterrado e Vila Santa Cecília (Streamlit + Google Planilhas)
#
# Organização deste arquivo (um arquivo só de propósito: o app é atualizado subindo arquivos à mão no GitHub,
# e um app.py único evita esquecer um módulo e derrubar o caixa):
#   1. configuração e utilidades      5. venda (frente de caixa)        9. relatórios
#   2. onde os dados ficam (ponte)    6. produtos                      10. caixa (abertura/sangria/fechamento)
#   3. regras de estoque              7. estoque                       11. início (painel do dia)
#   4. acesso: login, papéis, sessão  8. vendas feitas                 12. cabeçalho, menu e main()
#
# Nenhuma senha ou chave fica neste arquivo: tudo vem dos Secrets do Streamlit (veja LEIA-ME.md).
import base64
import hashlib
import json
import hmac
import inspect
import io
import math
import os
import re
import secrets as _sec
import time
import unicodedata
import urllib.parse
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

PASTA = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo("America/Sao_Paulo")
LOJAS = ["Aterrado", "Vila Santa Cecília"]
VENDEDORES = ["Raphael", "Daiane", "Norma", "Outros"]
FORMAS = {"Dinheiro": "dinheiro", "Pix": "pix", "Crédito": "credito", "Débito": "debito"}
NOME_FORMA = {v: k for k, v in FORMAS.items()} | {"nao_informado": "Não informado"}

# Vendas de antes do app estar ligado à planilha (só o total do dia). Entram uma única vez:
# se já existirem na planilha (mesmo canceladas), não são lançadas de novo.
LANCAMENTOS_INICIAIS = [
    {"id": "VANT-20261118-ATE", "data": "2026-11-18 22:00:00", "loja": "Aterrado", "total": 591.50},
    {"id": "VANT-20261118-VIL", "data": "2026-11-18 22:00:00", "loja": "Vila Santa Cecília", "total": 1062.00},
    # vendas de 19/11 feitas enquanto o caixa ainda não gravava na planilha
    {"id": "VANT-20261119-ATE-1", "data": "2026-11-19 12:10:00", "loja": "Aterrado", "total": 50.00, "forma": "pix"},
    {"id": "VANT-20261119-ATE-2", "data": "2026-11-19 12:15:00", "loja": "Aterrado", "total": 59.99, "forma": "debito"},
    {"id": "VANT-20261119-ATE-3", "data": "2026-11-19 12:20:00", "loja": "Aterrado", "total": 74.99, "forma": "debito"},
    # Aterrado 24, 25 e 26/11: vendas anotadas enquanto o caixa estava fora do ar (só o total; pagamento não informado)
    {"id": "VANT-20261124-ATE-1", "data": "2026-11-24 18:01:00", "loja": "Aterrado", "total": 134.99},
    {"id": "VANT-20261124-ATE-2", "data": "2026-11-24 18:02:00", "loja": "Aterrado", "total": 30.00},
    {"id": "VANT-20261124-ATE-3", "data": "2026-11-24 18:03:00", "loja": "Aterrado", "total": 110.00},
    {"id": "VANT-20261125-ATE-1", "data": "2026-11-25 18:01:00", "loja": "Aterrado", "total": 50.00},
    {"id": "VANT-20261125-ATE-2", "data": "2026-11-25 18:02:00", "loja": "Aterrado", "total": 75.00},
    {"id": "VANT-20261125-ATE-3", "data": "2026-11-25 18:03:00", "loja": "Aterrado", "total": 10.00},
    {"id": "VANT-20261125-ATE-4", "data": "2026-11-25 18:04:00", "loja": "Aterrado", "total": 99.00},
    {"id": "VANT-20261126-ATE-1", "data": "2026-11-26 18:01:00", "loja": "Aterrado", "total": 150.00},
    {"id": "VANT-20261126-ATE-2", "data": "2026-11-26 18:02:00", "loja": "Aterrado", "total": 120.00},
    {"id": "VANT-20261126-ATE-3", "data": "2026-11-26 18:03:00", "loja": "Aterrado", "total": 99.99},
    {"id": "VANT-20261126-ATE-4", "data": "2026-11-26 18:04:00", "loja": "Aterrado", "total": 120.00},
    {"id": "VANT-20261126-ATE-5", "data": "2026-11-26 18:05:00", "loja": "Aterrado", "total": 52.00},
    # Vila Santa Cecília 26/11: anotadas no caderno (Norma), com a forma de pagamento
    {"id": "VANT-20261126-VIL-1", "data": "2026-11-26 18:01:00", "loja": "Vila Santa Cecília", "total": 40.00,
     "forma": "pix"},
    {"id": "VANT-20261126-VIL-2", "data": "2026-11-26 18:02:00", "loja": "Vila Santa Cecília", "total": 300.00,
     "forma": "pix"},
    {"id": "VANT-20261126-VIL-3", "data": "2026-11-26 18:03:00", "loja": "Vila Santa Cecília", "total": 80.00,
     "forma": "pix"},
    {"id": "VANT-20261126-VIL-4", "data": "2026-11-26 18:04:00", "loja": "Vila Santa Cecília", "total": 549.94,
     "forma": "credito"},
    {"id": "VANT-20261126-VIL-5", "data": "2026-11-26 18:05:00", "loja": "Vila Santa Cecília", "total": 399.99,
     "forma": "credito"},
    {"id": "VANT-20261126-VIL-6", "data": "2026-11-26 18:06:00", "loja": "Vila Santa Cecília", "total": 740.00,
     "forma": "pix"},
    {"id": "VANT-20261126-VIL-7", "data": "2026-11-26 18:07:00", "loja": "Vila Santa Cecília", "total": 199.99,
     "forma": "credito"},
]

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
M_PROD, M_PAINEL = ":material/sell: Produtos", ":material/monitoring: Relatórios"
M_MAIS = ":material/more_horiz: Mais"
HORAS_LOGIN = 12  # o login vale por um dia de trabalho, mesmo recarregando a página
ESTOQUE_BAIXO = 2  # até quantas peças o produto entra em "estoque baixo"

# Paleta oficial (a mesma do estilo.css)
VERMELHO, PRETO, DOURADO, BORDO, CREME, BRANCO = "#A50924", "#111111", "#C6A15B", "#581525", "#FBF6EC", "#FFFFFF"


def _img64(nome, reserva="logo.png"):
    caminho = os.path.join(PASTA, nome)
    if not os.path.exists(caminho):
        caminho = os.path.join(PASTA, reserva)
    with open(caminho, "rb") as f:
        return base64.b64encode(f.read()).decode()


LOGO64 = _img64("logo.png")
ICONE64 = _img64(os.path.join("marca", "favicon-64.png"))      # símbolo (maçã com carrinho) no cabeçalho
LOGIN64 = _img64(os.path.join("marca", "logo-login.png"))      # logomarca do Caixa
BOUTIQUE64 = _img64(os.path.join("marca", "boutique-640.jpg"))  # logomarca da boutique (assinatura)


def aplicar_estilo():
    """O visual fica no arquivo estilo.css, ao lado deste app.py."""
    try:
        with open(os.path.join(PASTA, "estilo.css"), encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("Falta o arquivo estilo.css no GitHub: o app funciona, mas sem o visual da loja.")


# ---------------------------------------------------------------- utilidades
def agora():
    return datetime.now(TZ)


def agora_txt():
    return agora().strftime("%Y-%m-%d %H:%M:%S")


def brl(v):
    s = f"{float(v):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _br(n, casas=2):
    return f"{n:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl_curto(v):
    """R$ 1,25 Mi / R$ 3,40 Bi / R$ 845,53 Tri para não quebrar o cartão; abaixo de 1 milhão, valor cheio."""
    v = float(v)
    for limite, sufixo in ((1e12, "Tri"), (1e9, "Bi"), (1e6, "Mi")):
        if abs(v) >= limite:
            return f"R$ {_br(v / limite)} {sufixo}"
    return brl(v)


def num_curto(n):
    n = float(n)
    for limite, sufixo in ((1e12, "Tri"), (1e9, "Bi"), (1e6, "Mi")):
        if abs(n) >= limite:
            return f"{_br(n / limite)} {sufixo}"
    return _br(n, 0)


def reais(df, *cols):
    """Tabela com dinheiro no jeito brasileiro (R$ 1.234,56) e que continua ordenando pelo número."""
    numeros = list(df.select_dtypes("number").columns)
    cols = [c for c in (cols or numeros) if c in df.columns]
    outros = [c for c in numeros if c not in cols and c != "Parte do total"]  # a barra de % cuida da dela
    est = df.style.format(brl, subset=cols)
    if outros:  # quantidades: 7 e não 7.000000
        est = est.format(lambda x: _br(x, 0) if float(x).is_integer() else _br(x), subset=outros)
    return est


def metrica(col, rotulo, valor, delta=None, ajuda=None, dinheiro=True, **kw):
    """Cartão de número: mostra o valor abreviado e o exato no (?) quando abreviar."""
    curto = brl_curto(valor) if dinheiro else num_curto(valor)
    exato = brl(valor) if dinheiro else _br(float(valor), 0)
    if curto != exato:
        ajuda = (ajuda + "\n\n" if ajuda else "") + f"Valor exato: {exato}"
    col.metric(rotulo, curto, delta, help=ajuda, **kw)


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
    """Texto da planilha → número (sempre float, mesmo com a coluna vazia)."""
    return pd.to_numeric(serie.astype(str).str.replace(",", ".", regex=False), errors="coerce").fillna(0).astype("float64")


def novo_id(prefixo=""):
    return prefixo + uuid.uuid4().hex[:8].upper()


# ---------------------------------------------------------------- onde os dados ficam
def nao_salvou(e):
    """Marca de erro de gravação. É um atributo e não uma classe nova, porque o banco fica guardado em cache
    entre as execuções do app e a classe seria outra a cada execução (o except não pegaria)."""
    return getattr(e, "nao_salvou", False)


def _protege_gravacao(cls):
    for nome in ("anexar", "regravar", "mudar"):
        original = getattr(cls, nome)

        def envolta(self, aba, *a, _f=original, **k):
            try:
                return _f(self, aba, *a, **k)
            except Exception as e:
                if not nao_salvou(e):
                    e.nao_salvou = f"aba {aba}: {type(e).__name__}: {e}"
                raise
        setattr(cls, nome, envolta)
    return cls


@_protege_gravacao
class BancoLocal:
    """Arquivos CSV numa pasta. Bom para testar no computador."""

    def registrar_venda(self, venda, itens):
        return registrar_venda_generico(self, venda, itens)

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


def _erro_temporario(e):
    """Falhas que costumam passar sozinhas: limite de uso do Google, servidor ocupado, internet oscilando."""
    codigo = getattr(getattr(e, "response", None), "status_code", None)
    return codigo in (408, 429, 500, 502, 503, 504) or isinstance(e, (ConnectionError, TimeoutError)) \
        or any(p in type(e).__name__ for p in ("Connection", "Timeout"))


def tentar(fn, *a, tentativas=3, **k):
    for i in range(tentativas):
        try:
            return fn(*a, **k)
        except Exception as e:
            if i == tentativas - 1 or not _erro_temporario(e):
                raise
            time.sleep(1.5 * (i + 1))


def tabela(vals, cols):
    """Linhas cruas da planilha (1ª linha = cabeçalho) -> tabela com as colunas do app, tudo como texto."""
    if not vals:
        return pd.DataFrame(columns=cols)
    cab = [str(c).strip() for c in vals[0]]
    linhas = [list(r) + [""] * (len(cab) - len(r)) for r in vals[1:] if any(str(x).strip() for x in r)]
    df = pd.DataFrame([r[:len(cab)] for r in linhas], columns=cab).astype(str)
    for c in cols:
        if c not in df:
            df[c] = ""
    return df[cols]


def valor_celula(c, v):
    if c in NUMEROS:
        try:
            return float(str(v).replace(",", "."))
        except ValueError:
            return 0
    return "" if v is None else str(v)


def registrar_venda_generico(b, venda, itens):
    """Venda idempotente para quem não tem a ação 'venda' (arquivos locais, conta de serviço ou ponte antiga):
    relê a planilha na hora, não repete o que já está lá e confere a venda no fim."""
    if venda["id"] in set(b.ler("Vendas")["id"]):
        return "ja_existia"
    it = b.ler("Itens")
    ja = set(it.loc[it["venda_id"] == venda["id"], "produto_id"])
    faltam = [i for i in itens if i["produto_id"] not in ja]
    if faltam:
        b.anexar("Itens", faltam)
    b.anexar("Vendas", [venda])
    if venda["id"] not in set(b.ler("Vendas")["id"]):
        raise RuntimeError("a venda não apareceu na planilha depois de gravar")
    return "gravada"


@_protege_gravacao
class BancoPonte:
    """Planilha do Google pela ponte (Apps Script da própria planilha). Link e senha vêm dos Secrets."""
    na_planilha = True

    def __init__(self, url, senha):
        import requests
        self.url, self.senha, self.s = url, senha, requests.Session()
        self.tem_acao_venda = None  # descobre na 1ª venda se a ponte já é a versão 2

    def _pedir(self, acao, aba, **dados):
        def uma_vez():
            r = self.s.post(self.url, json={"senha": self.senha, "acao": acao, "aba": aba, **dados}, timeout=40)
            if r.status_code in (401, 403, 404):
                raise RuntimeError(
                    f"o Google pediu autorização de novo (erro {r.status_code}). Com a conta dona da planilha, "
                    f"abra este link no navegador e autorize (Revisar permissões → Avançado → Acessar → Permitir) "
                    f"até aparecer \"Ponte do Caixa funcionando\"; depois toque em Tentar de novo: {self.url}")
            r.raise_for_status()  # 429/5xx -> tentar de novo
            try:
                resp = r.json()
            except ValueError:
                raise RuntimeError("a ponte respondeu uma página em vez de dados. Na implantação, "
                                   "'Quem pode acessar' tem que ser 'Qualquer pessoa'.") from None
            if not resp.get("ok"):
                raise RuntimeError(f"a ponte recusou: {resp.get('erro')}")
            return resp.get("dados")
        return tentar(uma_vez)

    def ler(self, aba):
        return tabela(self._pedir("ler", aba), ABAS[aba])

    def registrar_venda(self, venda, itens):
        """Ponte v2: itens + venda numa chamada só, com LockService e sem duplicar (mesmo id = mesma venda)."""
        if self.tem_acao_venda is not False:
            linha_v = [valor_celula(c, venda.get(c, "")) for c in ABAS["Vendas"]]
            linhas_i = [[valor_celula(c, i.get(c, "")) for c in ABAS["Itens"]] for i in itens]
            try:
                r = self._pedir("venda", "Vendas", venda=linha_v, itens=linhas_i)
                self.tem_acao_venda = True
                return r.get("situacao", "gravada")
            except RuntimeError as e:
                if "ação desconhecida" not in str(e):
                    raise
                self.tem_acao_venda = False  # ponte antiga: segue pelo caminho genérico
        return registrar_venda_generico(self, venda, itens)

    def anexar(self, aba, linhas):
        cols = ABAS[aba]
        self._pedir("anexar", aba, linhas=[[valor_celula(c, l.get(c, "")) for c in cols] for l in linhas])

    def regravar(self, aba, df):
        cols = ABAS[aba]
        self._pedir("regravar", aba, linhas=[[valor_celula(c, v) for c, v in zip(cols, r)] for r in df[cols].values.tolist()])

    def mudar(self, aba, chave_col, chave, col, valor):
        self._pedir("mudar", aba, chave_col=chave_col, chave=chave, col=col, valor=valor_celula(col, valor))


@_protege_gravacao
class BancoSheets:
    """Planilha do Google: as duas lojas gravam no mesmo lugar."""
    na_planilha = True

    def registrar_venda(self, venda, itens):
        return registrar_venda_generico(self, venda, itens)

    def __init__(self, credenciais, planilha):
        import gspread
        self.gspread = gspread
        gc = gspread.service_account_from_dict(dict(credenciais))
        self.sh = tentar(gc.open_by_url, planilha) if planilha.startswith("http") else tentar(gc.open_by_key, planilha)
        self._ws = {}

    def ws(self, aba):
        if aba not in self._ws:
            try:
                w = tentar(self.sh.worksheet, aba)
            except self.gspread.WorksheetNotFound:
                w = tentar(self.sh.add_worksheet, title=aba, rows=1000, cols=len(ABAS[aba]))
                tentar(w.append_row, ABAS[aba], value_input_option="RAW")
            self._ws[aba] = w
        return self._ws[aba]

    def ler(self, aba):
        cols = ABAS[aba]
        w = self.ws(aba)
        vals = tentar(w.get, value_render_option="UNFORMATTED_VALUE")
        if not vals:
            tentar(w.append_row, cols, value_input_option="RAW")
        return tabela(vals, cols)

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
        tentar(self.ws(aba).append_rows, [[self._valor(c, l.get(c, "")) for c in cols] for l in linhas],
               value_input_option="RAW", insert_data_option="INSERT_ROWS", table_range="A1")

    def regravar(self, aba, df):
        cols = ABAS[aba]
        valores = [cols] + [[self._valor(c, v) for c, v in zip(cols, r)] for r in df[cols].values.tolist()]
        tentar(self.ws(aba).update, values=valores, range_name="A1", value_input_option="RAW")

    def mudar(self, aba, chave_col, chave, col, valor):
        cols = ABAS[aba]
        w = self.ws(aba)
        coluna = tentar(w.col_values, cols.index(chave_col) + 1)
        if chave in coluna:
            tentar(w.update_cell, coluna.index(chave) + 1, cols.index(col) + 1, valor)


def segredo(*chaves):
    try:
        v = st.secrets
        for k in chaves:
            v = v[k]
        return v
    except Exception:
        return None


# No Streamlit Cloud o app fica em /mount/src. Lá, arquivos locais SOMEM quando o app dorme:
# por isso, na nuvem, o caixa só funciona ligado à planilha do Google.
NA_NUVEM = PASTA.startswith("/mount/src") or os.environ.get("CAIXA_NUVEM") == "1"


def erro_nos_secrets():
    """Devolve o erro de leitura dos Secrets (ex.: texto colado com defeito) ou None se estiver tudo legível."""
    try:
        st.secrets.to_dict()
        return None
    except FileNotFoundError:
        return "não há nenhum Secret salvo"
    except Exception as e:  # erro de digitação no TOML, aspas faltando etc.
        return str(e)


def _credenciais():
    """Devolve (chave do Google, problema). Nunca derruba o app por causa de um Secret mal colado."""
    cred = segredo("gcp_service_account")
    if cred:
        return dict(cred), None
    txt = segredo("gcp_json")
    if not txt:
        return None, None
    txt = str(txt)
    ini, fim = txt.find("{"), txt.rfind("}")  # aceita espaços ou texto sobrando antes/depois
    if ini < 0 or fim < ini:
        return None, ("o gcp_json está sem o conteúdo do arquivo .json (não achei a { do começo e a } do fim). "
                      "Troque as palavras COLE_AQUI_O_JSON pelo conteúdo inteiro do arquivo.")
    try:
        cred = json.loads(txt[ini:fim + 1], strict=False)
    except json.JSONDecodeError as e:  # a mensagem não mostra o conteúdo da chave
        return None, (f"o gcp_json não é um .json válido (linha {e.lineno} do JSON colado: {e.msg}). "
                      "Cole de novo o arquivo inteiro, da { até a }, sem mudar nada.")
    falta = [c for c in ("client_email", "private_key") if not cred.get(c)]
    if falta:
        return None, f"o .json colado não tem {' nem '.join(falta)}: confira se é o arquivo da chave do Google."
    return cred, None


def credenciais():
    return _credenciais()[0]


@st.cache_resource(show_spinner=False)
def _sheets(planilha, email):
    return BancoSheets(credenciais(), planilha)


@st.cache_resource(show_spinner=False)
def _local():
    return BancoLocal(os.path.join(PASTA, "dados"))


def na_planilha():
    """Pelo atributo e não por isinstance: o banco fica em cache e a classe muda a cada execução do app."""
    return getattr(banco(), "na_planilha", False)


def ponte():
    """Link e senha da ponte, só dos Secrets ([ponte] url e senha). Nada fica escrito no código."""
    url = str(segredo("ponte", "url") or "").strip()
    senha = str(segredo("ponte", "senha") or "").strip()
    ok = url.startswith("https://script.google.com/") or url.startswith("http://127.0.0.1:")  # o 2º é só para os testes
    return (url, senha) if ok and senha else None


@st.cache_resource(show_spinner=False)
def _ponte(url, senha):
    return BancoPonte(url, senha)


def banco():
    if ponte():
        return _ponte(*ponte())
    cred, planilha = credenciais(), segredo("planilha", "endereco")
    if cred and planilha:
        return _sheets(str(planilha), cred.get("client_email", ""))
    return _local()


MOVIMENTO = ("Vendas", "Itens", "Entradas", "Caixa")


def _ler(b, aba):
    df = b.ler(aba)
    for c in ABAS[aba]:
        if c in NUMEROS:
            df[c] = num(df[c])
    if "id" in df and aba != "Itens":
        df = df.drop_duplicates("id", keep="first")  # linha repetida na planilha conta uma vez só
    if aba == "Itens":  # o mesmo produto não aparece duas vezes na mesma venda (o carrinho junta as unidades)
        df = df.drop_duplicates(["venda_id", "produto_id"], keep="first")
    return df


@st.cache_data(ttl=600, show_spinner="Carregando produtos…")
def _ler_produtos():
    return _ler(banco(), "Produtos")


@st.cache_data(ttl=120, show_spinner="Carregando…")
def _ler_movimento():
    """As 4 abas de movimento de uma vez, em paralelo: 1 espera em vez de 4."""
    from concurrent.futures import ThreadPoolExecutor
    b = banco()
    with ThreadPoolExecutor(len(MOVIMENTO)) as ex:
        tabelas = list(ex.map(lambda a: _ler(b, a), MOVIMENTO))
    return dict(zip(MOVIMENTO, tabelas))


def carregar(aba):
    """Produtos ficam guardados 10 min; o movimento, 2 min (ou até alguém gravar algo neste app)."""
    return _ler_produtos() if aba == "Produtos" else _ler_movimento()[aba]


def gravou(produtos=False):
    _ler_movimento.clear()
    if produtos:
        _ler_produtos.clear()


def gravou_tudo():
    gravou(produtos=True)


def venda_so_total(vid, data, loja, total, forma="nao_informado", vendedor="Não informado", usuario="lançamento manual"):
    return {"id": vid, "data": data, "loja": loja, "vendedor": vendedor, "forma": forma, "subtotal": total,
            "desconto": 0, "total": total, "recebido": total, "troco": 0, "usuario": usuario, "status": "ok"}


def garantir_lancamentos_iniciais():
    """Lança o que falta e corrige valor/forma/vendedor de um lançamento que já entrou errado."""
    v = carregar("Vendas").set_index("id")
    novos, mudou = [], False
    for l in LANCAMENTOS_INICIAIS:
        certo = venda_so_total(l["id"], l["data"], l["loja"], l["total"], l.get("forma", "nao_informado"),
                               l.get("vendedor", "Não informado"))
        if l["id"] not in v.index:
            novos.append(certo)
            continue
        atual = v.loc[l["id"]]
        if isinstance(atual, pd.DataFrame):
            atual = atual.iloc[0]
        for col in ("total", "subtotal", "recebido", "forma", "vendedor", "loja", "data"):
            if (abs(float(atual[col]) - float(certo[col])) > 0.001) if col in NUMEROS else (str(atual[col]) != str(certo[col])):
                banco().mudar("Vendas", "id", l["id"], col, certo[col])
                mudou = True
    if novos:
        banco().anexar("Vendas", novos)
    if novos or mudou:
        gravou()


@st.cache_resource(show_spinner=False)
def _uma_vez():
    """Trava e marcador do servidor: impede duas abas abertas ao mesmo tempo de lançarem em dobro."""
    import threading
    return {"trava": threading.Lock(), "feito": False}


def preparar_planilha():
    """Produtos iniciais + lançamentos manuais. Roda uma vez quando o app liga, não a cada clique."""
    u = _uma_vez()
    if u["feito"]:
        return
    with u["trava"]:
        if not u["feito"]:
            preparar_produtos()
            gravou()  # relê da planilha na hora, sem cache, antes de conferir os lançamentos
            garantir_lancamentos_iniciais()
            u["feito"] = True


def preparar_produtos():
    if len(carregar("Produtos")) == 0:
        base = pd.read_csv(os.path.join(PASTA, "produtos_iniciais.csv"), dtype=str, keep_default_na=False)
        banco().regravar("Produtos", base)
        gravou(produtos=True)


# ---------------------------------------------------------------- estoque = entradas − vendas
def estoque():
    ent = carregar("Entradas")
    itens = carregar("Itens")
    vendas = carregar("Vendas")
    validas = set(vendas.loc[vendas["status"] != "cancelada", "id"])
    itens = itens[itens["venda_id"].isin(validas)]  # itens sem venda (gravação interrompida) não contam
    e = ent.groupby(["loja", "produto_id"])["qtd"].sum()
    s = itens.groupby(["loja", "produto_id"])["qtd"].sum()
    return e.sub(s, fill_value=0).to_dict()


def produtos_ativos():
    p = carregar("Produtos")
    return p[p["ativo"].astype(str).isin(["1", "1.0", "True", "true", "sim"])].copy()


# ================================================================ 4. ACESSO: login, papéis e sessão
LOGIN_LOJA = {"aterrado": "Aterrado", "vila": "Vila Santa Cecília"}
PAPEIS = ("dona", "gerente", "vendedor")          # do mais alto para o mais baixo
NOME_PAPEL = {"dona": "Dona", "gerente": "Gerente", "vendedor": "Vendedor(a)"}

# O que cada papel pode fazer. É conferido no servidor antes de mostrar a tela e antes de cada gravação.
PERMISSOES = {
    "vender": {"vendedor", "gerente", "dona"},
    "caixa": {"vendedor", "gerente", "dona"},             # abrir, sangria, reforço e fechar o caixa da própria loja
    "estoque_ver": {"vendedor", "gerente", "dona"},
    "estoque_mexer": {"gerente", "dona"},                 # chegou mercadoria, contagem e acerto
    "vendas_ver": {"vendedor", "gerente", "dona"},
    "vendas_historico": {"gerente", "dona"},              # vendedor(a) vê só hoje e ontem
    "vendas_cancelar": {"dona"},
    "lancar_total": {"dona"},                             # lançar o total de um dia sem caixa
    "relatorios": {"gerente", "dona"},
    "relatorios_todas": {"dona"},                         # outras lojas e "tudo junto"
    "custos": {"dona"},                                   # custo, margem e lucro
    "produtos": {"dona"},                                 # cadastro, preço e custo
    "excel": {"gerente", "dona"},
    "trocar_loja": {"dona"},
}


def hash_senha(senha, sal=None, voltas=200_000):
    """Transforma a senha num código que não dá para desfazer (PBKDF2-SHA256)."""
    sal = sal or _sec.token_hex(8)
    cod = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal.encode(), voltas).hex()
    return f"pbkdf2${voltas}${sal}${cod}"


def senha_confere(digitada, guardada):
    """Aceita a senha guardada nos Secrets como código (pbkdf2$...) ou em texto."""
    guardada = str(guardada)
    if guardada.startswith("pbkdf2$"):
        try:
            _, voltas, sal, cod = guardada.split("$")
            return hmac.compare_digest(hash_senha(str(digitada), sal, int(voltas)), guardada)
        except ValueError:
            return False
    return hmac.compare_digest(guardada.encode(), str(digitada).encode())


def senhas_dos_papeis():
    """Senhas dos Secrets: [acessos] dona / gerente / vendedor.
    Compatibilidade: sem [acessos], a senha antiga ([usuarios] norma) continua valendo, com acesso de dona,
    para o caixa não travar no dia da atualização. Nenhuma senha fica escrita no código."""
    ac = {str(k).lower(): str(v) for k, v in dict(segredo("acessos") or {}).items() if str(v).strip()}
    senhas = {p: ac[p] for p in PAPEIS if p in ac}
    if not senhas:
        antigas = {str(k).lower(): str(v) for k, v in dict(segredo("usuarios") or {}).items() if str(v).strip()}
        if antigas.get("norma"):
            senhas["dona"] = antigas["norma"]
    return senhas


def papel_da_senha(digitada):
    """Confere a senha com todos os papéis (do mais alto ao mais baixo) e devolve o papel."""
    achou = None
    for papel, guardada in senhas_dos_papeis().items():
        if senha_confere(digitada, guardada) and achou is None:
            achou = papel
    return achou


@st.cache_resource(show_spinner=False)
def _chave_reserva():
    return _sec.token_bytes(32)  # só sem Secrets (teste no computador): logins valem até o app reiniciar


def _chave(papel):
    """Chave das sessões. Muda se trocar a senha do papel: quem estava logado com a senha antiga sai."""
    base = segredo("app", "chave")
    if not base:
        partes = [str(segredo("ponte", "senha") or "")] + [v for _, v in sorted(senhas_dos_papeis().items())]
        base = "|".join(partes) if any(partes) else None
    material = (str(base).encode() if base else _chave_reserva()) + b"|" + str(senhas_dos_papeis().get(papel, "")).encode()
    return hashlib.sha256(material).digest()


def gerar_token(login, papel, horas=HORAS_LOGIN):
    msg = f"{login}.{papel}.{int(time.time()) + horas * 3600}"
    return msg + "." + hmac.new(_chave(papel), msg.encode(), hashlib.sha256).hexdigest()


def ler_token(t):
    """Devolve (login da loja, papel) se o token for válido, assinado e dentro da validade."""
    try:
        login, papel, exp, sig = str(t).split(".")
        msg = f"{login}.{papel}.{exp}"
        certo = hmac.new(_chave(papel), msg.encode(), hashlib.sha256).hexdigest()
        if (hmac.compare_digest(certo, sig) and int(exp) > time.time() and login in LOGIN_LOJA
                and papel in senhas_dos_papeis()):
            return login, papel
    except Exception:
        pass
    return None


def entrar_sessao(login, papel):
    st.session_state.usuario = login
    st.session_state.papel = papel
    st.session_state.loja = LOGIN_LOJA[login]


def papel():
    return st.session_state.get("papel")


def pode(acao):
    return papel() in PERMISSOES.get(acao, set())


def exigir(acao):
    """Barreira no servidor: sem o papel certo, a tela ou a gravação para aqui."""
    if not pode(acao):
        st.error("Seu acesso não permite fazer isso. Entre com a senha da gerente ou da dona.", icon=":material/lock:")
        st.stop()


def quem():
    """Como a pessoa aparece nos registros: loja e papel (ex.: aterrado · vendedor)."""
    return f"{st.session_state.get('usuario', '?')} · {papel() or '?'}"


def tela_login():
    _, meio, _ = st.columns([1, 1.3, 1])
    with meio:
        with st.container(key="login"):
            _formulario_login()
        st.markdown(f"<div class='login-boutique'><img src='data:image/jpeg;base64,{BOUTIQUE64}' "
                    "alt='Jardim do Éden · Boutique Sensual'></div>", unsafe_allow_html=True)


def _formulario_login():
    """Logo, escolha da loja e senha. A senha define o papel (dona, gerente ou vendedor)."""
    st.markdown(f"<div class='login-topo'><img src='data:image/png;base64,{LOGIN64}' alt='Jardim do Éden'>"
                "<div class='login-dica'>Toque na sua loja e digite a senha</div></div>", unsafe_allow_html=True)
    if not senhas_dos_papeis():
        st.error("As senhas de acesso ainda não foram configuradas. Nos Secrets do Streamlit, crie a seção "
                 "**[acessos]** com as senhas da dona, da gerente e do(a) vendedor(a) (veja o LEIA-ME).",
                 icon=":material/key_off:")
        return
    espera = st.session_state.get("login_bloqueado_ate", 0) - time.time()
    with st.form("login", border=False):
        u = st.pills("Qual loja?", list(LOGIN_LOJA), default=None, format_func=lambda k: f"Loja {LOGIN_LOJA[k]}",
                     key="login_user")
        s = st.text_input("Senha", type="password", placeholder="••••••")
        ok = st.form_submit_button("Entrar", type="primary", width="stretch", icon=":material/login:")
    if not ok:
        return
    if espera > 0:
        st.error(f"Muitas tentativas. Espere {int(espera) + 1} segundos e tente de novo.")
        return
    if not u:
        st.error("Toque na sua loja.")
        return
    p = papel_da_senha(s)
    if not p:
        n = st.session_state.get("login_erros", 0) + 1
        st.session_state.login_erros = n
        if n >= 5:
            st.session_state.login_bloqueado_ate = time.time() + 60
            st.session_state.login_erros = 0
        st.error("Senha incorreta.")
        return
    st.session_state.pop("login_erros", None)
    entrar_sessao(u, p)
    st.query_params["k"] = gerar_token(u, p)
    st.rerun()


def sair():
    st.session_state.clear()
    st.query_params.clear()


# ================================================================ 5. VENDA (frente de caixa)
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
    nomes = prods["nome"].map(sem_acento) + " " + prods["codigo"].astype(str)
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
TEM_ATALHO = "shortcut" in inspect.signature(st.button).parameters


def _escolher(chave, nome):
    st.session_state[chave] = nome


def grade_botoes(opcoes, chave, colunas=2):
    """Botões grandes para escolher (o escolhido fica destacado)."""
    with st.container(key=f"esc_{chave}"):
        cols = st.columns(colunas)
        escolhido = st.session_state.get(chave)
        for n, op in enumerate(opcoes):
            nome, icone = op if isinstance(op, tuple) else (op, None)
            cols[n % colunas].button(nome, key=f"{chave}_{nome}", width="stretch", icon=icone,
                                     type="primary" if escolhido == nome else "secondary",
                                     on_click=_escolher, args=(chave, nome))
    return st.session_state.get(chave)


def calcular_venda(cart, desconto_tipo, desconto_valor):
    """Conta da venda num lugar só (usada na tela e na gravação): subtotal, desconto e total, nunca negativos."""
    subtotal = round(sum(float(it["preco"]) * int(it["qtd"]) for it in cart), 2)
    vd = max(float(desconto_valor or 0), 0.0)
    desconto = round(subtotal * min(vd, 100) / 100, 2) if desconto_tipo == "%" else round(min(vd, subtotal), 2)
    return subtotal, desconto, round(subtotal - desconto, 2)


def calcular_troco(total, recebido):
    return round(float(recebido) - float(total), 2)


def tela_vender(loja):
    exigir("vender")
    st.session_state.setdefault("carrinho", [])
    st.session_state.setdefault("resultados", [])
    cart = st.session_state.carrinho

    if st.session_state.get("ultima") and not cart:
        venda_concluida()
        return

    if caixa_estado(loja)["situacao"] != "aberto":
        st.info("O caixa desta loja está fechado. Dá para vender, mas lembre de **abrir o caixa**.", icon=":material/info:")
    prods = produtos_ativos()
    est = estoque()
    esq, dir_ = st.columns([1.15, 1], gap="large")

    with esq, st.container(key="pdv_busca"):
        st.markdown("<div class='secao'>Produtos</div>", unsafe_allow_html=True)
        with st.container(key="busca"), st.form("busca", clear_on_submit=True, border=False):
            c1, c2 = st.columns([2.6, 1.4], vertical_alignment="bottom")
            q = c1.text_input("Procurar", label_visibility="collapsed",
                              placeholder="Nome, código de barras ou preço (ex.: 129)")
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
            c1.markdown(f"**{len(res)} encontrado(s)** · toque no produto certo")
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
        else:
            atalhos(prods, est, loja)

    with dir_:
        carrinho(loja)


def venda_concluida():
    u = st.session_state.ultima
    troco = (f"<div class='ok-troco'>Troco: {brl(u['troco'])}</div>"
             if u["forma"] == "dinheiro" and float(u["troco"]) > 0 else "")
    onde = "✓ Confirmada na planilha" if na_planilha() else "✓ Gravada (modo de teste, fora da planilha)"
    aviso = " · já estava gravada (não duplicou)" if u.get("situacao") == "ja_existia" else ""
    st.markdown(f"<div class='ok-card'><div class='ok-ic'>✓</div><div><div class='ok-t'>Venda concluída</div>"
                f"<div class='ok-s'>{brl(u['total'])} · {NOME_FORMA.get(u['forma'], u['forma'])} · {u['vendedor']}</div>"
                f"{troco}<div class='ok-sub'>{onde}{aviso} · nº {u['id']}</div></div></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("Nova venda", type="primary", width="stretch", icon=":material/add_shopping_cart:"):
        st.session_state.ultima = None
        st.rerun()
    c2.link_button("Mandar comprovante no WhatsApp", link_whats(texto_comprovante(u)), width="stretch",
                   icon=":material/send:")


def _mudar_qtd(pid, delta):
    cart = st.session_state.carrinho
    for it in cart:
        if it["id"] == pid:
            it["qtd"] += delta
    st.session_state.carrinho = [it for it in cart if it["qtd"] > 0]


@st.fragment
def carrinho(loja):
    """Lado direito da venda. Roda sozinho: tocar em + − ou nos botões não recarrega a busca."""
    cart = st.session_state.carrinho
    with st.container(key="carrinho"):
        n_pecas = sum(it["qtd"] for it in cart)
        st.markdown(f"<div class='secao'>Venda · {loja}<span class='secao-n'>{n_pecas} peça(s)</span></div>",
                    unsafe_allow_html=True)
        if not cart:
            st.markdown("<div class='vazio'>Nenhum produto ainda.<br>Procure ao lado ou toque num atalho.</div>",
                        unsafe_allow_html=True)
            return
        with st.container(key="itens"):
            for it in cart:
                st.markdown(f"<div class='item-n'>{it['nome']}</div>"
                            f"<div class='item-p'>{brl(it['preco'])} cada · <b>{brl(it['preco'] * it['qtd'])}</b></div>",
                            unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([1, 0.8, 1, 1], vertical_alignment="center")
                c1.button("", key=f"menos{it['id']}", icon=":material/remove:", width="stretch", help="Tirar 1",
                          on_click=_mudar_qtd, args=(it["id"], -1))
                c2.markdown(f"<div class='qtd'>{it['qtd']}</div>", unsafe_allow_html=True)
                c3.button("", key=f"mais{it['id']}", icon=":material/add:", width="stretch", help="Pôr mais 1",
                          on_click=_mudar_qtd, args=(it["id"], 1))
                c4.button("", key=f"rm{it['id']}", icon=":material/delete:", width="stretch",
                          help="Tirar este produto da venda", on_click=_mudar_qtd, args=(it["id"], -it["qtd"]))

        tipo_d, vd = "R$", 0.0
        if st.toggle("Dar desconto", key="com_desc"):
            d1, d2 = st.columns([1, 1.6], vertical_alignment="bottom")
            tipo_d = d1.segmented_control("Desconto em", ["R$", "%"], default="R$", key="tipo_desc") or "R$"
            vd = d2.number_input("Quanto?", min_value=0.0, value=0.0, step=1.0, format="%.2f", key="desconto")
        subtotal, desconto, total = calcular_venda(cart, tipo_d, vd)
        st.markdown(f"<div class='total-box'><div class='total-linha'><span>Subtotal</span><span>{brl(subtotal)}</span></div>"
                    + (f"<div class='total-linha'><span>Desconto</span><span>− {brl(desconto)}</span></div>" if desconto else "")
                    + f"<div class='total-l'>Total</div><div class='total-grande'>{brl(total)}</div></div>",
                    unsafe_allow_html=True)
        # barra fixa no celular: mostra o total e leva até o botão de concluir
        st.markdown(f"<a class='barra-total' href='#fechar-venda'><span>{n_pecas} peça(s)</span>"
                    f"<b>{brl(total)}</b><span>Fechar venda ↓</span></a>", unsafe_allow_html=True)

        st.markdown("<div class='rotulo'>Quem vendeu?</div>", unsafe_allow_html=True)
        vend = grade_botoes(VENDEDORES, "vendedor")
        st.markdown("<div class='rotulo' id='fechar-venda'>Forma de pagamento</div>", unsafe_allow_html=True)
        forma_n = grade_botoes(FORMAS_BOTAO, "forma")

        recebido, troco = total, 0.0
        if forma_n == "Dinheiro":
            st.markdown("<div class='rotulo'>Quanto a cliente deu?</div>", unsafe_allow_html=True)
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
            troco = calcular_troco(total, recebido)
            if troco > 0:
                st.markdown(f"<div class='troco'>Troco: <b>{brl(troco)}</b></div>", unsafe_allow_html=True)

        pend = st.session_state.get("venda_pendente")
        if pend and pend.get("falhou"):
            st.warning("A última tentativa **não foi confirmada** pela planilha. Os produtos continuam aqui. "
                       "Toque em Concluir de novo: a venda tem o mesmo número e **não vai duplicar**.",
                       icon=":material/cloud_off:")
        with st.container(key="concluir"):
            extra = {"shortcut": "Ctrl+Enter"} if TEM_ATALHO else {}
            if st.button(f"Concluir venda · {brl(total)}", type="primary", width="stretch",
                         icon=":material/check_circle:", **extra):
                erro = None
                if not vend:
                    erro = "Toque em quem vendeu."
                elif not forma_n:
                    erro = "Toque na forma de pagamento."
                elif forma_n == "Dinheiro" and recebido < total:
                    erro = "O dinheiro que a cliente deu é menor que o total."
                elif total <= 0:
                    erro = "O total da venda está zerado."
                if erro:
                    st.error(erro, icon=":material/error:")
                else:
                    finalizar(loja, vend, FORMAS[forma_n], tipo_d, vd, recebido)
        if st.button("Cancelar esta venda", width="stretch", icon=":material/close:"):
            limpar_venda()
            st.rerun()


def focar_busca():
    """Deixa o cursor na busca (no computador), para o leitor de código de barras USB já funcionar."""
    js = """
    (() => {
      const d = window.parent.document;
      setTimeout(() => {
        const i = d.querySelector('.st-key-busca input');
        const a = d.activeElement;
        if (i && window.parent.innerWidth > 900 && (!a || !['INPUT','TEXTAREA'].includes(a.tagName))) i.focus();
      }, 350);
    })(); // %s
    """ % time.time()
    try:
        st.html(f"<script>{js}</script>", unsafe_allow_javascript=True)
    except TypeError:  # Streamlit mais antigo
        import streamlit.components.v1 as components
        components.html(f"<script>{js}</script>", height=0)


def mais_vendidos_ids(prods, n=12, loja=None):
    it, v = carregar("Itens"), carregar("Vendas")
    ok = v.loc[v["status"] != "cancelada", "id"]
    it = it[it["venda_id"].isin(ok) & it["produto_id"].isin(prods["id"])]
    if loja:
        it = it[it["loja"] == loja]
    return list(it.groupby("produto_id")["qtd"].sum().sort_values(ascending=False).head(n).index)


def atalhos(prods, est, loja):
    """Botões dos produtos que mais saem: é só tocar, sem digitar."""
    ids = mais_vendidos_ids(prods)
    titulo = "Mais vendidos"
    if len(ids) < 4:
        faixa = prods[prods["nome"].str.startswith(("LINGERIE", "PRÓTESE"))].sort_values("preco")
        ids += [i for i in faixa["id"] if i not in ids][:12 - len(ids)]
        titulo = "Atalhos"
    if not ids:
        st.caption("Dica: digite só o valor (ex.: 189) para ver os produtos desse preço.")
        return
    st.markdown(f"<div class='rotulo'>{titulo} <span class='sub'>· toque para pôr na venda</span></div>",
                unsafe_allow_html=True)
    base = prods.set_index("id")
    with st.container(key="grade"):
        cols = st.columns(3)
        for n, pid in enumerate(ids[:12]):
            p = base.loc[pid]
            q_est = int(est.get((loja, pid), 0))
            txt_est = f"{q_est} em est." if q_est > 0 else "sem estoque"
            if cols[n % 3].button(f"{p['nome'][:40]}  \n**{brl(p['preco'])}** · {txt_est}", key=f"at{pid}",
                                  width="stretch"):
                por_no_carrinho(dict(p, id=pid))
                st.rerun()


def limpar_venda():
    st.session_state.carrinho = []
    st.session_state.resultados = []
    for k in [k for k in st.session_state if k in ("desconto", "forma", "tipo_desc", "deu", "com_desc", "venda_pendente")
              or str(k).startswith("rec")]:
        st.session_state.pop(k, None)


def _digital(loja, cart, total):
    """Impressão digital da venda: muda se o carrinho, a loja ou o total mudarem."""
    base = json.dumps([loja, sorted((it["id"], int(it["qtd"]), float(it["preco"])) for it in cart), total])
    return hashlib.sha256(base.encode()).hexdigest()[:16]


def ids_vendas_na_planilha():
    """Lê a aba Vendas direto da planilha (sem cache) para saber o que já está gravado de verdade."""
    return set(banco().ler("Vendas")["id"])


def finalizar(loja, vend, forma, tipo_d, vd, recebido):
    """Grava a venda e só diz 'concluída' depois que a planilha confirmar.
    - O número da venda é criado na 1ª tentativa e reaproveitado nas próximas (sem duplicar).
    - Se falhar, o carrinho fica como está e a próxima tentativa completa o que faltou.
    - Se o carrinho mudar depois de uma falha, primeiro confere se a venda anterior não chegou a ser gravada."""
    exigir("vender")
    if loja != st.session_state.get("loja"):
        exigir("trocar_loja")
    cart = st.session_state.carrinho
    subtotal, desconto, total = calcular_venda(cart, tipo_d, vd)
    troco = calcular_troco(total, recebido) if forma == "dinheiro" else 0.0
    recebido = recebido if forma == "dinheiro" else total
    dig = _digital(loja, cart, total)
    pend = st.session_state.get("venda_pendente")
    try:
        if pend and pend["digital"] != dig:
            if pend.get("falhou") and pend["venda"]["id"] in ids_vendas_na_planilha():
                st.session_state.ultima = dict(pend["venda"], itens=pend["itens"], situacao="ja_existia")
                limpar_venda()
                gravou()
                st.rerun()
            pend = None
        if not pend:
            pend = {"digital": dig, "id": novo_id("V"), "data": agora_txt()}
        venda = {"id": pend["id"], "data": pend["data"], "loja": loja, "vendedor": vend, "forma": forma,
                 "subtotal": subtotal, "desconto": desconto, "total": total, "recebido": round(recebido, 2),
                 "troco": troco, "usuario": quem(), "status": "ok"}
        itens = [{"venda_id": pend["id"], "data": pend["data"], "loja": loja, "produto_id": it["id"],
                  "produto": it["nome"], "qtd": int(it["qtd"]), "preco": float(it["preco"]),
                  "total": round(float(it["preco"]) * int(it["qtd"]), 2)} for it in cart]
        st.session_state.venda_pendente = dict(pend, venda=venda, itens=itens, falhou=False)
        with st.spinner("Gravando a venda na planilha…"):
            situacao = banco().registrar_venda(venda, itens)
    except Exception as e:
        if "venda_pendente" in st.session_state:
            st.session_state.venda_pendente["falhou"] = True
        st.error("**A venda NÃO foi confirmada.** A internet ou o Google falhou. Os produtos continuam no carrinho: "
                 "confira a internet e toque em **Concluir venda** de novo (não duplica).", icon=":material/cloud_off:")
        with st.expander("Detalhes técnicos"):
            st.code(f"{type(e).__name__}: {e}")
        return
    gravou()
    st.session_state.ultima = dict(venda, itens=itens, situacao=situacao)
    limpar_venda()
    st.rerun()


# ================================================================ 6. PRODUTOS (o custo só aparece aqui)
def tela_produtos(_loja=None):
    exigir("produtos")
    prods = carregar("Produtos").copy()
    est = estoque()
    st.markdown("<div class='titulo-tela'>Produtos e preços</div>", unsafe_allow_html=True)
    st.caption("Regra da casa: preço = custo × 5, terminando em 9,99. O custo só aparece nesta tela.")

    with st.expander("Cadastrar produto novo", icon=":material/add_box:"):
        with st.form("novo", clear_on_submit=True):
            nome = st.text_input("Nome do produto")
            c1, c2, c3 = st.columns(3)
            codigo = c1.text_input("Código de barras (opcional)")
            custo = c2.number_input("Custo (R$)", min_value=0.0, step=0.5, format="%.2f")
            preco = c3.number_input("Preço de venda (R$) · 0 usa a regra", min_value=0.0, step=1.0, format="%.2f")
            qtd = st.number_input("Quantidade que chegou (opcional)", min_value=0, step=1)
            loja_q = st.selectbox("Em qual loja?", LOJAS)
            if st.form_submit_button("Cadastrar", type="primary"):
                exigir("produtos")
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
                                                         "obs": "cadastro", "usuario": quem()}])
                        gravou(produtos=True)
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
        exigir("produtos")
        mudancas = mudancas_produtos(prods, editado)
        if not mudancas:
            st.info("Nada mudou.")
        elif len(mudancas) <= 40:
            # muda só as células alteradas: não reescreve a aba (não perde produto cadastrado ao mesmo tempo)
            for pid, col, valor in mudancas:
                banco().mudar("Produtos", "id", pid, col, valor)
            gravou(produtos=True)
            st.success(f"{len({m[0] for m in mudancas})} produto(s) atualizado(s).")
        else:
            base = prods.set_index("id")
            for pid, col, valor in mudancas:
                base.at[pid, col] = valor
            banco().regravar("Produtos", base.reset_index())
            gravou(produtos=True)
            st.success(f"{len({m[0] for m in mudancas})} produto(s) atualizado(s).")
    with c2.popover("Aplicar a regra em todos", width="stretch"):
        st.write("Recalcula o preço de **todos os produtos com custo** (custo × 5, final 9,99). "
                 "Faça isso com a outra loja sem cadastrar produto no mesmo minuto.")
        if st.button("Sim, recalcular", type="primary"):
            exigir("produtos")
            p = prods.copy()
            com = p["custo"] > 0
            p.loc[com, "preco"] = p.loc[com, "custo"].apply(preco_regra)
            banco().regravar("Produtos", p)
            gravou(produtos=True)
            st.success(f"{int(com.sum())} preços recalculados.")


def mudancas_produtos(prods, editado):
    """Lista (id, coluna, valor novo) só do que foi alterado na tabela."""
    base = prods.set_index("id")
    out = []
    for _, r in editado.iterrows():
        antigo = base.loc[r["id"]]
        novo = {"nome": str(r["nome"]).strip(), "codigo": "" if pd.isna(r["codigo"]) else str(r["codigo"]).strip(),
                "custo": float(r["custo"] or 0), "preco": float(r["preco"] or 0), "ativo": "1" if r["ativo"] else "0"}
        ativo_antigo = "1" if str(antigo["ativo"]) in ("1", "1.0", "True", "true", "sim") else "0"
        for col, v in novo.items():
            if col in ("custo", "preco"):
                if abs(float(antigo[col]) - v) > 1e-9:
                    out.append((r["id"], col, v))
            elif col == "ativo":
                if ativo_antigo != v:
                    out.append((r["id"], col, v))
            elif str(antigo[col]) != v:
                out.append((r["id"], col, v))
    return out


# ================================================================ 7. ESTOQUE
def situacao_estoque(loja):
    """Tabela de estoque da loja: produto, preço, peças e situação (disponível, baixo, zerado, sem lançamento)."""
    prods = produtos_ativos().sort_values("nome")
    est = estoque()
    ent = carregar("Entradas")
    com_lancamento = set(ent.loc[ent["loja"] == loja, "produto_id"])
    tab = prods[["id", "nome", "codigo", "preco"]].copy()
    tab["estoque"] = tab["id"].apply(lambda i: int(est.get((loja, i), 0)))

    def sit(r):
        if r["id"] not in com_lancamento:  # nunca teve entrada nesta loja: o número não é confiável
            return "Sem lançamento"
        if r["estoque"] <= 0:
            return "Zerado"
        if r["estoque"] <= ESTOQUE_BAIXO:
            return "Baixo"
        return "Disponível"
    tab["situacao"] = tab.apply(sit, axis=1) if len(tab) else pd.Series(dtype=str)
    return tab


def tela_estoque(loja_atual):
    exigir("estoque_ver")
    st.markdown("<div class='titulo-tela'>Estoque</div>", unsafe_allow_html=True)
    loja = loja_atual
    if pode("trocar_loja"):
        loja = st.segmented_control("Loja", LOJAS, default=loja_atual, key="est_loja") or loja_atual
    tab = situacao_estoque(loja)
    conta = tab["situacao"].value_counts()
    with st.container(key="kpis"):
        m = st.columns(4)
    metrica(m[0], "Produtos ativos", len(tab), dinheiro=False)
    metrica(m[1], "Disponíveis", int(conta.get("Disponível", 0) + conta.get("Baixo", 0)), dinheiro=False)
    metrica(m[2], f"Estoque baixo (≤ {ESTOQUE_BAIXO})", int(conta.get("Baixo", 0)), dinheiro=False)
    metrica(m[3], "Zerados", int(conta.get("Zerado", 0)), dinheiro=False,
            ajuda="Produtos que já tiveram estoque lançado nesta loja e acabaram.")
    if conta.get("Sem lançamento", 0):
        st.caption(f"{int(conta['Sem lançamento'])} produto(s) ainda sem estoque lançado em {loja}: "
                   "use “Chegou mercadoria” ou “Contagem” para começar a controlar.")

    abas = [":material/search: Consultar"]
    if pode("estoque_mexer"):
        abas += [":material/local_shipping: Chegou mercadoria", ":material/fact_check: Contagem"]
    abas += [":material/history: Movimentações"]
    t = dict(zip(abas, st.tabs(abas)))

    with t[":material/search: Consultar"]:
        c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
        filtro = c1.text_input("Procurar", placeholder="nome ou código", key="est_busca")
        so = c2.segmented_control("Mostrar", ["Todos", "Disponível", "Baixo", "Zerado", "Sem lançamento"],
                                  default="Todos", key="est_filtro") or "Todos"
        vis = tab
        if filtro.strip():
            pal = sem_acento(filtro).split()
            vis = vis[vis.apply(lambda r: all(p in sem_acento(r["nome"]) + " " + str(r["codigo"]) for p in pal), axis=1)]
        if so != "Todos":
            vis = vis[vis["situacao"] == so]
        st.dataframe(reais(vis[["nome", "preco", "estoque", "situacao"]], "preco"), hide_index=True, width="stretch",
                     height=min(420, 38 * len(vis) + 40),
                     column_config={"nome": st.column_config.TextColumn("Produto", width="large"), "preco": "Preço",
                                    "estoque": "Em estoque", "situacao": "Situação"})

    if pode("estoque_mexer"):
        prods = produtos_ativos().sort_values("nome")
        opcoes = {f"{r['nome']} · {brl(r['preco'])}": r for _, r in prods.iterrows()}
        with t[":material/local_shipping: Chegou mercadoria"], st.form("entrada", clear_on_submit=True):
            esc = st.selectbox("Produto", list(opcoes), index=None, placeholder="Digite para procurar…")
            qtd = st.number_input("Quantidade que chegou", min_value=1, step=1)
            obs = st.text_input("Observação (opcional)", placeholder="ex.: pedido Hot Rio 12/11")
            if st.form_submit_button("Lançar entrada", type="primary"):
                exigir("estoque_mexer")
                if not esc:
                    st.error("Escolha o produto.")
                else:
                    p = opcoes[esc]
                    banco().anexar("Entradas", [{"id": novo_id("E"), "data": agora_txt(), "loja": loja,
                                                 "produto_id": p["id"], "produto": p["nome"], "qtd": qtd, "obs": obs,
                                                 "usuario": quem()}])
                    gravou()
                    st.success(f"+{qtd} {p['nome']} em {loja}.")
        with t[":material/fact_check: Contagem"], st.form("contagem", clear_on_submit=True):
            esc = st.selectbox("Produto ", list(opcoes), index=None, placeholder="Digite para procurar…")
            contado = st.number_input("Quantas peças tem na prateleira agora?", min_value=0, step=1)
            if st.form_submit_button("Acertar estoque", type="primary"):
                exigir("estoque_mexer")
                if not esc:
                    st.error("Escolha o produto.")
                else:
                    p = opcoes[esc]
                    dif = int(contado) - int(estoque().get((loja, p["id"]), 0))
                    if dif == 0:
                        st.info("O estoque já está certo.")
                    else:
                        banco().anexar("Entradas", [{"id": novo_id("E"), "data": agora_txt(), "loja": loja,
                                                     "produto_id": p["id"], "produto": p["nome"], "qtd": dif,
                                                     "obs": "acerto de contagem", "usuario": quem()}])
                        gravou()
                        st.success(f"Estoque de {p['nome']} acertado para {int(contado)} ({dif:+d}).")

    with t[":material/history: Movimentações"]:
        mov = movimentacoes(loja)
        if mov.empty:
            st.caption("Nenhuma movimentação nesta loja ainda.")
        else:
            st.dataframe(mov.head(300), hide_index=True, width="stretch", height=min(420, 38 * min(len(mov), 300) + 40),
                         column_config={"quando": "Quando", "tipo": "Tipo",
                                        "produto": st.column_config.TextColumn("Produto", width="large"),
                                        "qtd": "Qtd", "obs": "Detalhe"})


def movimentacoes(loja):
    """Entradas, acertos e vendas de cada produto na loja, do mais recente para o mais antigo."""
    ent = carregar("Entradas")
    ent = ent[ent["loja"] == loja]
    a = pd.DataFrame({"dt": pd.to_datetime(ent["data"], errors="coerce"),
                      "tipo": ent["obs"].map(lambda o: "Acerto" if "acerto" in str(o) else "Entrada"),
                      "produto": ent["produto"], "qtd": ent["qtd"].astype(int), "obs": ent["obs"]})
    it, v = carregar("Itens"), carregar("Vendas")
    status = v.set_index("id")["status"]
    it = it[(it["loja"] == loja) & it["venda_id"].isin(status.index)]
    b = pd.DataFrame({"dt": pd.to_datetime(it["data"], errors="coerce"),
                      "tipo": it["venda_id"].map(lambda i: "Venda cancelada" if status.get(i) == "cancelada" else "Venda"),
                      "produto": it["produto"], "qtd": -it["qtd"].astype(int),
                      "obs": "venda " + it["venda_id"].astype(str)})
    m = pd.concat([a, b], ignore_index=True).sort_values("dt", ascending=False)
    m["quando"] = m["dt"].dt.strftime("%d/%m/%Y %H:%M")
    return m[["quando", "tipo", "produto", "qtd", "obs"]]


# ================================================================ 8. VENDAS FEITAS
PERIODOS = ["Hoje", "Ontem", "7 dias", "30 dias", "Este mês", "Tudo"]


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


def vendas_periodo(nome, loja, intervalo=None):
    v = carregar("Vendas").copy()
    v["dt"] = pd.to_datetime(v["data"], errors="coerce")
    a, b = intervalo or periodo(nome)
    v = v[(v["dt"] >= a) & (v["dt"] < b)]
    if loja != "Todas":
        v = v[v["loja"] == loja]
    return v, a, b


def tela_vendas(loja_atual):
    exigir("vendas_ver")
    st.markdown("<div class='titulo-tela'>Vendas feitas</div>", unsafe_allow_html=True)
    if pode("lancar_total"):
        lancar_total_do_dia(loja_atual)
    pers = PERIODOS if pode("vendas_historico") else ["Hoje", "Ontem"]
    c1, c2 = st.columns(2)
    per = c1.selectbox("Período", pers, key="vendas_per")
    if pode("relatorios_todas"):
        loja = c2.selectbox("Loja", ["Todas", *LOJAS], index=1 + LOJAS.index(loja_atual), key="vendas_loja")
    else:
        loja = loja_atual
        c2.text_input("Loja", value=loja, disabled=True)
    v, _, _ = vendas_periodo(per, loja)
    v = v.sort_values("dt", ascending=False)
    ok = v[v["status"] != "cancelada"]
    st.caption(f"{len(ok)} venda(s) · {brl(ok['total'].sum())}"
               + (f" · {len(v) - len(ok)} cancelada(s)" if len(v) > len(ok) else ""))
    if v.empty:
        st.info("Nenhuma venda nesse período.")
        return
    mostra = v.assign(hora=v["dt"].dt.strftime("%d/%m %H:%M"), pagamento=v["forma"].map(NOME_FORMA).fillna(v["forma"]),
                      situacao=v["status"].map({"ok": "ok", "cancelada": "CANCELADA"}))
    st.dataframe(reais(mostra[["id", "hora", "loja", "vendedor", "pagamento", "desconto", "total", "situacao"]],
                       "desconto", "total"), hide_index=True, width="stretch", height=320,
                 column_config={"id": "Venda", "hora": "Quando", "loja": "Loja", "vendedor": "Vendedor(a)",
                                "pagamento": "Pagamento", "desconto": "Desconto", "total": "Total",
                                "situacao": "Situação"})
    escolha = st.selectbox("Ver itens de uma venda", v["id"].tolist(), index=None, placeholder="Escolha a venda…",
                           format_func=lambda i: f"{i} · {brl(v.set_index('id').at[i, 'total'])}")
    if escolha:
        it = carregar("Itens")
        it = it[it["venda_id"] == escolha]
        if it.empty:
            st.caption("Venda lançada só pelo total (sem produtos).")
        else:
            st.dataframe(reais(it[["produto", "qtd", "preco", "total"]], "preco", "total"), hide_index=True,
                         width="stretch", column_config={"produto": "Produto", "qtd": "Qtd", "preco": "Preço",
                                                         "total": "Total"})
        cancelada = v.set_index("id").at[escolha, "status"] == "cancelada"
        if not cancelada and not pode("vendas_cancelar"):
            st.caption("Só a dona cancela vendas.")
        elif not cancelada:
            with st.popover("Cancelar esta venda", icon=":material/block:"):
                st.write("Os produtos voltam para o estoque e a venda sai dos relatórios. A linha continua na "
                         "planilha, marcada como cancelada.")
                if st.button("Sim, cancelar a venda", type="primary"):
                    exigir("vendas_cancelar")
                    banco().mudar("Vendas", "id", escolha, "status", "cancelada")
                    gravou()
                    st.success("Venda cancelada.")
                    st.rerun()


def lancar_total_do_dia(loja_atual):
    """Para registrar o total de um dia em que não se usou o app (não mexe no estoque)."""
    with st.expander("Lançar o total de um dia sem caixa", icon=":material/edit_calendar:"):
        with st.form("lanc_total", clear_on_submit=True):
            c1, c2 = st.columns(2)
            dia = c1.date_input("Dia", value=agora().date() - timedelta(days=1), max_value=agora().date(),
                                format="DD/MM/YYYY")
            loja = c2.selectbox("Loja", LOJAS, index=LOJAS.index(loja_atual))
            valor = st.number_input("Total vendido no dia (R$)", min_value=0.0, step=10.0, format="%.2f")
            forma = st.selectbox("Forma de pagamento", ["Não informado", *FORMAS])
            if st.form_submit_button("Lançar", type="primary", width="stretch"):
                exigir("lancar_total")
                if valor <= 0:
                    st.error("Informe o valor.")
                else:
                    banco().anexar("Vendas", [venda_so_total(
                        novo_id("VANT"), f"{dia:%Y-%m-%d} 22:00:00", loja, round(valor, 2),
                        forma="nao_informado" if forma == "Não informado" else FORMAS[forma], usuario=quem())])
                    gravou()
                    st.success(f"Lançado: {brl(valor)} em {dia:%d/%m/%Y} · {loja}.")


# ================================================================ 9. RELATÓRIOS
def excel(vendas, itens):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        vendas.drop(columns=["dt"], errors="ignore").to_excel(w, sheet_name="Vendas", index=False)
        itens.to_excel(w, sheet_name="Itens", index=False)
    return buf.getvalue()


_EIXO_R = ("'R$ ' + replace(datum.value >= 1e6 ? format(datum.value / 1e6, '.1f') + ' Mi' : "
           "datum.value >= 1e3 ? format(datum.value / 1e3, '.1f') + ' mil' : format(datum.value, '.0f'), '.', ',')")


def grafico(df, x, y="total", cor=None, horizontal=False, ordem=None, altura=260):
    """Barras com o valor escrito em cada barra (R$ exato no toque/mouse) e eixo em R$ abreviado."""
    if df.empty:
        st.caption("Sem dados no período.")
        return
    df = df.copy()
    df["Valor"] = df[y].map(brl)
    df["Rotulo"] = df[y].map(lambda v: brl_curto(v).replace("R$ ", ""))
    eixo_cat = alt.Axis(labelAngle=0, labelLimit=170, title=None, labelFontSize=13, labelColor=PRETO)
    eixo_val = alt.Axis(labelExpr=_EIXO_R, title=None, labelFontSize=11, grid=True, tickCount=4, labelColor="#6B6B6B",
                        gridColor="#EFE7D8")
    cat = alt.X(f"{x}:N", sort=ordem, axis=eixo_cat) if not horizontal else alt.Y(f"{x}:N", sort=ordem, axis=eixo_cat)
    folga = alt.Scale(domain=[0, float(df[y].max()) * (1.28 if horizontal else 1.15) or 1])
    val = alt.Y(f"{y}:Q", axis=eixo_val, scale=folga) if not horizontal else alt.X(f"{y}:Q", axis=eixo_val, scale=folga)
    enc = {"x": cat, "y": val} if not horizontal else {"y": cat, "x": val}
    tip = [alt.Tooltip(f"{x}:N", title=""), alt.Tooltip("Valor:N", title="Total")]
    base = alt.Chart(df)
    if cor:
        enc["color"] = alt.Color(f"{cor}:N", scale=alt.Scale(range=[VERMELHO, DOURADO]),
                                 legend=alt.Legend(orient="bottom", title=None, labelFontSize=12))
        enc["xOffset" if not horizontal else "yOffset"] = alt.XOffset(f"{cor}:N") if not horizontal else alt.YOffset(f"{cor}:N")
        tip.insert(1, alt.Tooltip(f"{cor}:N", title="Loja"))
        barras = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    else:
        barras = base.mark_bar(color=VERMELHO if not horizontal else BORDO, cornerRadius=4)
    camadas = barras.encode(**enc, tooltip=tip)
    if not cor:
        txt = (base.mark_text(align="left", dx=4, fontSize=12, fontWeight=700, color=PRETO) if horizontal else
               base.mark_text(baseline="bottom", dy=-3, fontSize=11, fontWeight=700, color=PRETO))
        camadas = camadas + txt.encode(**{k: v for k, v in enc.items()}, text="Rotulo:N")
    graf = camadas.properties(height=altura)
    st.altair_chart(graf.configure(background=BRANCO).configure_view(strokeWidth=0).configure_axis(domain=False),
                    width="stretch")


def destaques(v, it):
    """Frases curtas com o que mais chama atenção no período (calculadas dos dados reais)."""
    real = v[~v["id"].astype(str).str.startswith("VANT")]       # lançamentos só de total não têm hora real
    frases = []
    if len(v):
        por_dia = v.groupby(v["dt"].dt.date)["total"].sum()
        if len(por_dia) > 1:
            d = por_dia.idxmax()
            frases.append(("Melhor dia", f"{d:%d/%m} · {brl_curto(por_dia.max())}"))
        if len(real):
            hora = real.groupby(real["dt"].dt.hour)["total"].sum()
            frases.append(("Horário mais forte", f"{int(hora.idxmax()):02d}h às {int(hora.idxmax()) + 1:02d}h"))
        formas = v.groupby("forma")["total"].sum()
        formas = formas[formas.index != "nao_informado"]
        if len(formas) and formas.sum():
            frases.append(("Forma mais usada", f"{NOME_FORMA.get(formas.idxmax(), formas.idxmax())} · "
                                               f"{formas.max() / formas.sum() * 100:.0f}% do valor"))
        vend = v[v["vendedor"] != "Não informado"].groupby("vendedor")["total"].sum()
        if len(vend):
            frases.append(("Quem mais vendeu", f"{vend.idxmax()} · {brl_curto(vend.max())}"))
    if len(it):
        top = it.groupby("produto")["qtd"].sum()
        frases.append(("Produto campeão", f"{top.idxmax().title()[:40]} · {int(top.max())} peça(s)"))
    if frases:
        st.markdown("<div class='destaques'>" + "".join(
            f"<div class='dest'><span>{t}</span><b>{x}</b></div>" for t, x in frases) + "</div>", unsafe_allow_html=True)


def resumo_periodo(v, it, custos):
    """Números de um período (já sem canceladas): faturamento, vendas, ticket, descontos, peças e margem."""
    def custo_de(ids):  # sempre número, mesmo sem nenhuma venda (coluna vazia)
        return pd.to_numeric(ids.map(custos), errors="coerce").fillna(0).astype("float64")
    tot, n = float(v["total"].sum()), len(v)
    com_custo = it[custo_de(it["produto_id"]) > 0]
    lucro = float((com_custo["total"] - com_custo["qtd"] * custo_de(com_custo["produto_id"])).sum())
    desc_itens = float(v.loc[v["id"].isin(it["venda_id"]), "desconto"].sum())
    return {"faturamento": tot, "vendas": n, "ticket": tot / n if n else 0.0, "descontos": float(v["desconto"].sum()),
            "pecas": float(it["qtd"].sum()), "margem": lucro - desc_itens}


def filtros_relatorio(loja_atual):
    with st.container(key="filtros"):
        per = st.segmented_control("Período", [*PERIODOS, "Personalizado"], default="7 dias", key="painel_per") or "7 dias"
        c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
        if pode("relatorios_todas"):
            loja = c1.segmented_control("Loja", [*LOJAS, "Todas"], default=loja_atual, key="painel_loja",
                                        format_func=lambda l: "Tudo junto" if l == "Todas" else l) or loja_atual
        else:
            loja = loja_atual
            c1.markdown(f"<div class='rotulo'>Loja</div><div class='fixo'>{loja}</div>", unsafe_allow_html=True)
        intervalo = None
        if per == "Personalizado":
            hoje = agora().date()
            d1, d2 = st.columns(2)
            ini = d1.date_input("Data inicial", value=hoje - timedelta(days=6), max_value=hoje, format="DD/MM/YYYY",
                                key="painel_ini")
            fim = d2.date_input("Data final", value=hoje, min_value=ini, max_value=hoje, format="DD/MM/YYYY",
                                key="painel_fim")
            intervalo = (datetime.combine(ini, datetime.min.time()), datetime.combine(fim, datetime.min.time()) + timedelta(days=1))
        v, a, b = vendas_periodo(per, loja, intervalo)
        vendedores = sorted(carregar("Vendas")["vendedor"].dropna().unique())
        quem_v = c2.selectbox("Vendedor(a)", ["Todos", *vendedores], key="painel_vend")
    return per, loja, v, a, b, quem_v


def tela_painel(loja_atual):
    exigir("relatorios")
    st.markdown("<div class='titulo-tela'>Relatórios</div>", unsafe_allow_html=True)
    per, loja, v, a, b, quem_v = filtros_relatorio(loja_atual)
    v = v[v["status"] != "cancelada"]
    if quem_v != "Todos":
        v = v[v["vendedor"] == quem_v]
    it = carregar("Itens")
    it = it[it["venda_id"].isin(v["id"])]
    custos = carregar("Produtos").set_index("id")["custo"]

    # mesmo filtro, no período anterior do mesmo tamanho
    todas = carregar("Vendas").copy()
    todas["dt"] = pd.to_datetime(todas["data"], errors="coerce")
    ant = todas[(todas["dt"] >= a - (b - a)) & (todas["dt"] < a) & (todas["status"] != "cancelada")]
    if loja != "Todas":
        ant = ant[ant["loja"] == loja]
    if quem_v != "Todos":
        ant = ant[ant["vendedor"] == quem_v]
    it_ant = carregar("Itens")
    it_ant = it_ant[it_ant["venda_id"].isin(ant["id"])]
    r, r0 = resumo_periodo(v, it, custos), resumo_periodo(ant, it_ant, custos)

    def var(k):
        if per == "Tudo" or not r0[k]:
            return None
        return f"{(r[k] - r0[k]) / abs(r0[k]) * 100:+.0f}% vs. anterior"

    with st.container(key="kpis"):
        cols = st.columns(3) + st.columns(3 if pode("custos") else 2)
    metrica(cols[0], "Faturamento", r["faturamento"], var("faturamento"))
    metrica(cols[1], "Vendas", r["vendas"], var("vendas"), dinheiro=False)
    metrica(cols[2], "Ticket médio", r["ticket"], var("ticket"))
    metrica(cols[3], "Descontos concedidos", r["descontos"])
    metrica(cols[4], "Peças vendidas", r["pecas"], dinheiro=False,
            ajuda="Só conta vendas feitas no caixa (os lançamentos só de total não têm peças).")
    if pode("custos"):
        metrica(cols[5], "Margem bruta estimada", r["margem"],
                ajuda="Preço de venda menos o custo atual do produto, já tirando os descontos. "
                      "Ficam de fora: produtos sem custo (lingerie e prótese por faixa) e lançamentos só de total.")
    if v.empty:
        st.info("Nenhuma venda nesse período.")
        return
    destaques(v, it)

    with st.expander("Comparativo com o período anterior", icon=":material/compare_arrows:", expanded=False):
        linhas = [("Faturamento", "faturamento", True), ("Vendas", "vendas", False), ("Ticket médio", "ticket", True),
                  ("Descontos", "descontos", True), ("Peças", "pecas", False)]
        if pode("custos"):
            linhas.append(("Margem bruta estimada", "margem", True))
        comp = pd.DataFrame([{"Indicador": n, "Este período": (brl(r[k]) if d else _br(r[k], 0)),
                              "Período anterior": (brl(r0[k]) if d else _br(r0[k], 0)),
                              "Variação": (f"{(r[k] - r0[k]) / abs(r0[k]) * 100:+.1f}%" if r0[k] else "—")}
                             for n, k, d in linhas])
        st.caption(f"Este período: {a:%d/%m/%Y} a {(b - timedelta(days=1)):%d/%m/%Y} · "
                   f"anterior: {(a - (b - a)):%d/%m/%Y} a {(a - timedelta(days=1)):%d/%m/%Y}")
        st.dataframe(comp, hide_index=True, width="stretch")

    if loja == "Todas":
        st.markdown("<div class='secao'>Comparativo entre lojas</div>", unsafe_allow_html=True)
        linhas = []
        for l in LOJAS:
            vl = v[v["loja"] == l]
            il = it[it["venda_id"].isin(vl["id"])]
            rl = resumo_periodo(vl, il, custos)
            linha = {"Loja": l, "Faturamento": rl["faturamento"], "Vendas": rl["vendas"], "Ticket médio": rl["ticket"],
                     "Descontos": rl["descontos"], "Peças": int(rl["pecas"]),
                     "Parte do total": rl["faturamento"] / r["faturamento"] if r["faturamento"] else 0}
            if pode("custos"):
                linha["Margem estimada"] = rl["margem"]
            for kf, nome in NOME_FORMA.items():
                linha[nome] = vl.loc[vl["forma"] == kf, "total"].sum()
            linhas.append(linha)
        comp = pd.DataFrame(linhas)
        comp = comp.loc[:, (comp != 0).any(axis=0) | comp.columns.isin(["Loja", "Faturamento", "Vendas"])]
        dinheiro = [c for c in ["Faturamento", "Ticket médio", "Descontos", "Margem estimada", *NOME_FORMA.values()] if c in comp]
        st.dataframe(reais(comp, *dinheiro), hide_index=True, width="stretch",
                     column_config={"Parte do total": st.column_config.ProgressColumn(
                         "Parte do total", format="percent", min_value=0, max_value=1)})
        st.markdown("<div class='rotulo'>Por dia, loja a loja</div>", unsafe_allow_html=True)
        pd_l = v.groupby([v["dt"].dt.date.rename("d"), "loja"])["total"].sum().reset_index()
        ordem = sorted(pd_l["d"].unique())
        pd_l["Dia"] = pd_l["d"].map(lambda d: f"{d:%d/%m}")
        grafico(pd_l, "Dia", cor="loja", ordem=[f"{d:%d/%m}" for d in ordem])

    g1, g2 = st.columns(2, gap="large")
    with g1:
        st.markdown("<div class='rotulo'>Faturamento por dia</div>", unsafe_allow_html=True)
        dia = v.groupby(v["dt"].dt.date.rename("d"))["total"].sum().reset_index()
        dia["Dia"] = dia["d"].map(lambda d: f"{d:%d/%m}")
        grafico(dia, "Dia", ordem=list(dia["Dia"]))
    with g2:
        st.markdown("<div class='rotulo'>Formas de pagamento</div>", unsafe_allow_html=True)
        f = v.groupby("forma")["total"].sum().rename(index=NOME_FORMA).sort_values(ascending=False).reset_index()
        f.columns = ["Forma", "total"]
        grafico(f, "Forma", horizontal=True, ordem=list(f["Forma"]), altura=max(140, 52 * len(f)))

    g3, g4 = st.columns(2, gap="large")
    with g3:
        st.markdown("<div class='rotulo'>Vendas por vendedor(a)</div>", unsafe_allow_html=True)
        eq = v.groupby("vendedor").agg(total=("total", "sum"), vendas=("id", "count"), desconto=("desconto", "sum"))
        eq["ticket"] = eq["total"] / eq["vendas"]
        eq = eq.sort_values("total", ascending=False)
        grafico(eq.reset_index().rename(columns={"vendedor": "Vendedor"}), "Vendedor", horizontal=True,
                ordem=list(eq.index), altura=max(140, 52 * len(eq)))
        st.dataframe(reais(eq.rename_axis("Vendedor(a)"), "total", "ticket", "desconto"), width="stretch",
                     column_config={"total": "Total", "vendas": "Vendas", "desconto": "Descontos",
                                    "ticket": "Ticket médio"})
    with g4:
        st.markdown("<div class='rotulo'>Por horário</div>", unsafe_allow_html=True)
        real = v[~v["id"].astype(str).str.startswith("VANT")]
        if real.empty:
            st.caption("Sem vendas com horário no período (só lançamentos de total).")
        else:
            hora = real.groupby(real["dt"].dt.hour)["total"].sum().reset_index()
            hora.columns = ["h", "total"]
            hora["Hora"] = hora["h"].map(lambda x: f"{int(x):02d}h")
            grafico(hora, "Hora", ordem=list(hora["Hora"]))
        st.markdown("<div class='rotulo'>Vendedor(a) × pagamento</div>", unsafe_allow_html=True)
        cruz = v.pivot_table(index="vendedor", columns="forma", values="total", aggfunc="sum", fill_value=0)
        cruz.columns = [NOME_FORMA.get(c, c) for c in cruz.columns]
        cruz = cruz.loc[cruz.sum(axis=1) > 0, cruz.sum(axis=0) > 0]
        st.dataframe(reais(cruz.rename_axis("Vendedor(a)")), width="stretch")

    st.markdown("<div class='rotulo'>Produtos mais vendidos</div>", unsafe_allow_html=True)
    if it.empty:
        st.caption("Sem peças no período (só lançamentos de total).")
    else:
        top = it.groupby("produto").agg(qtd=("qtd", "sum"), total=("total", "sum")).sort_values("qtd", ascending=False).head(15)
        top = top.reset_index()
        top["produto"] = top["produto"].str.title()
        st.dataframe(reais(top, "total"), hide_index=True, width="stretch", column_order=["qtd", "produto", "total"],
                     column_config={"qtd": st.column_config.NumberColumn("Peças", width="small"),
                                    "produto": st.column_config.TextColumn("Produto", width="large"), "total": "Total"})

    if pode("excel"):
        st.download_button("Baixar estas vendas em Excel", icon=":material/download:", data=excel(v, it),
                           file_name=f"vendas-{per.lower().replace(' ', '-')}-{agora():%Y-%m-%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ================================================================ WhatsApp
def link_whats(texto):
    return "https://wa.me/?text=" + urllib.parse.quote(texto)


def texto_comprovante(v):
    linhas = [f"*Jardim do Éden* · {v['loja']}",
              f"Compra nº {v['id']} · {v['data'][8:10]}/{v['data'][5:7]}/{v['data'][:4]} {v['data'][11:16]}", ""]
    for it in v.get("itens", []):
        linhas.append(f"{int(it['qtd'])}x {it['produto']} — {brl(it['total'])}")
    if float(v["desconto"]):
        linhas.append(f"Desconto: -{brl(v['desconto'])}")
    linhas += ["", f"*Total: {brl(v['total'])}* ({NOME_FORMA.get(v['forma'], v['forma'])})"]
    if v["forma"] == "dinheiro" and float(v["troco"]) > 0:
        linhas.append(f"Recebido {brl(v['recebido'])} · troco {brl(v['troco'])}")
    linhas += ["", "Obrigada pela preferência! 💋"]
    return "\n".join(linhas)


# ================================================================ 10. CAIXA (abrir, sangria, reforço, fechar)
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
           "por": por, "sangria": float(sang), "reforco": float(refo), "esperado": round(esperado, 2), "vendas": v,
           "movs": depois[depois["tipo"].isin(["sangria", "reforco"]) & (depois["dt"] <= fim)]}
    if len(fech):
        est["contado"] = float(fech.iloc[0]["valor"])
        est["fim"] = fim
    return est


def diferenca_caixa(contado, esperado):
    """('certo' | 'sobrando' | 'faltando', diferença)."""
    d = round(float(contado) - float(esperado), 2)
    return ("certo" if abs(d) < 0.005 else "sobrando" if d > 0 else "faltando"), d


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
        sit, d = diferenca_caixa(e["contado"], e["esperado"])
        linhas.append(f"Contado: {brl(e['contado'])} · " + {"certo": "conferiu ✅", "sobrando": f"sobrou {brl(d)}",
                                                            "faltando": f"faltou {brl(-d)}"}[sit])
    return "\n".join(linhas)


def mov_caixa(loja, tipo, valor, obs=""):
    exigir("caixa")
    if loja != st.session_state.get("loja"):
        exigir("trocar_loja")
    gravou()  # confere o estado atual da planilha (outra pessoa pode ter aberto/fechado agora)
    sit = caixa_estado(loja)["situacao"]
    if tipo == "abertura" and sit == "aberto":
        raise ValueError("O caixa desta loja já foi aberto.")
    if tipo != "abertura" and sit != "aberto":
        raise ValueError("O caixa desta loja não está aberto.")
    banco().anexar("Caixa", [{"id": novo_id("C"), "data": agora_txt(), "loja": loja, "tipo": tipo,
                              "valor": round(float(valor), 2), "obs": obs, "usuario": quem()}])
    gravou()


def cartoes_caixa(itens):
    """Cartões do caixa: [(rótulo, valor, classe)] lado a lado."""
    st.markdown("<div class='cx-grade'>" + "".join(
        f"<div class='cx {cls}'><span>{r}</span><b>{brl(v)}</b></div>" for r, v, cls in itens) + "</div>",
        unsafe_allow_html=True)


def tela_caixa(loja):
    exigir("caixa")
    e = caixa_estado(loja)
    st.markdown(f"<div class='titulo-tela'>Caixa · {loja}</div>", unsafe_allow_html=True)
    if e["situacao"] != "aberto":
        if e["situacao"] == "fechado":
            sit, d = diferenca_caixa(e["contado"], e["esperado"])
            st.caption(f"Último caixa: {e['inicio']:%d/%m %H:%M} até {e['fim']:%H:%M} · "
                       + {"certo": "conferiu", "sobrando": f"sobrou {brl(d)}", "faltando": f"faltou {brl(-d)}"}[sit])
            st.link_button("Reenviar o resumo desse caixa", link_whats(texto_resumo(loja, e)), icon=":material/send:")
        with st.form("abrir"):
            st.markdown("<div class='secao'>Abrir o caixa</div>", unsafe_allow_html=True)
            ini = st.number_input("Quanto tem de dinheiro na gaveta agora? (troco)", min_value=0.0, step=10.0,
                                  format="%.2f", value=float(e.get("contado", 0.0)))
            if st.form_submit_button("Abrir caixa", type="primary", width="stretch", icon=":material/lock_open:"):
                try:
                    mov_caixa(loja, "abertura", ini)
                    st.rerun()
                except ValueError as erro:
                    st.warning(str(erro))
        return

    v = e["vendas"]
    st.caption(f"Aberto desde {e['inicio']:%d/%m às %H:%M} · {len(v)} venda(s) · {brl(v['total'].sum())} vendidos")
    if e["inicio"].date() < agora().date():
        st.warning("Este caixa é de outro dia. Feche agora e abra um novo.")
    cartoes_caixa([("Saldo inicial", e["inicial"], ""), ("Vendas em dinheiro", e["por"].get("dinheiro", 0), ""),
                   ("Reforços", e["reforco"], "mais"), ("Sangrias", e["sangria"], "menos"),
                   ("Saldo esperado na gaveta", e["esperado"], "destaque")])
    st.caption("Pix, crédito e débito não entram na gaveta: "
               + " · ".join(f"{NOME_FORMA[k]} {brl(e['por'].get(k, 0))}" for k in ("pix", "credito", "debito")))

    c1, c2 = st.columns(2, gap="large")
    with c1.form("mov", clear_on_submit=True):
        st.markdown("<div class='secao'>Sangria ou reforço</div>", unsafe_allow_html=True)
        tipo = st.segmented_control("O quê?", ["Tirei (sangria)", "Coloquei (reforço)"], default="Tirei (sangria)")
        val = st.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")
        mot = st.text_input("Motivo", placeholder="ex.: pagamento do motoboy")
        if st.form_submit_button("Registrar", width="stretch"):
            if val <= 0:
                st.error("Informe o valor.")
            else:
                try:
                    mov_caixa(loja, "sangria" if (tipo or "").startswith("Tirei") else "reforco", val, mot)
                    st.rerun()
                except ValueError as erro:
                    st.warning(str(erro))
    with c2:
        fechamento(loja, e)

    if len(e["movs"]):
        st.markdown("<div class='rotulo'>Sangrias e reforços deste caixa</div>", unsafe_allow_html=True)
        mv = e["movs"].assign(hora=e["movs"]["dt"].dt.strftime("%H:%M"),
                              o_que=e["movs"]["tipo"].map({"sangria": "Sangria", "reforco": "Reforço"}),
                              valor=e["movs"]["valor"].map(brl))
        st.dataframe(mv[["hora", "o_que", "valor", "obs", "usuario"]], hide_index=True, width="stretch",
                     column_config={"hora": "Hora", "o_que": "Tipo", "valor": "Valor", "obs": "Motivo", "usuario": "Quem"})
    st.link_button("Mandar o resumo parcial no WhatsApp", link_whats(texto_resumo(loja, e)), icon=":material/send:")


def fechamento(loja, e):
    """Fechar em dois passos: contar e conferir; depois confirmar. Não fecha por engano."""
    with st.container(key="fechar_cx", border=True):
        st.markdown("<div class='secao'>Fechar o caixa</div>", unsafe_allow_html=True)
        conf = st.session_state.get("conferencia")
        if not conf:
            cont = st.number_input("Conte o dinheiro da gaveta. Quanto deu?", min_value=0.0, step=10.0, format="%.2f",
                                   key="contado_cx")
            if st.button("Conferir", width="stretch", icon=":material/calculate:"):
                st.session_state.conferencia = {"contado": float(cont), "esperado": e["esperado"]}
                st.rerun()
            return
        sit, d = diferenca_caixa(conf["contado"], e["esperado"])
        cartoes_caixa([("Saldo esperado", e["esperado"], ""), ("Valor contado", conf["contado"], ""),
                       ("Diferença", d, {"certo": "certo", "sobrando": "mais", "faltando": "menos"}[sit])])
        texto = {"certo": "Caixa correto: o dinheiro conferiu.", "sobrando": f"Dinheiro sobrando: {brl(d)} a mais.",
                 "faltando": f"Dinheiro faltando: {brl(-d)} a menos."}[sit]
        (st.success if sit == "certo" else st.warning)(texto)
        certeza = st.checkbox("Contei de novo e confirmo o valor", key="confirma_cx")
        b1, b2 = st.columns(2)
        if b1.button("Voltar", width="stretch"):
            st.session_state.pop("conferencia", None)
            st.rerun()
        if b2.button("Confirmar fechamento", type="primary", width="stretch", disabled=not certeza,
                     icon=":material/lock:"):
            try:
                mov_caixa(loja, "fechamento", conf["contado"], f"esperado {e['esperado']:.2f}; diferença {d:+.2f}")
            except ValueError as erro:
                st.warning(str(erro))
                return
            st.session_state.pop("conferencia", None)
            st.session_state.pop("confirma_cx", None)
            st.session_state.fechou = True
            st.session_state.ir = M_HOJE
            st.rerun()


# ================================================================ 11. INÍCIO (painel do dia)
def tela_hoje(loja):
    h = agora()
    saud = "Bom dia" if h.hour < 12 else "Boa tarde" if h.hour < 18 else "Boa noite"
    st.markdown(f"<div class='saud'>{saud}!</div>", unsafe_allow_html=True)
    if st.session_state.pop("fechou", False):
        e = caixa_estado(loja)
        if e["situacao"] == "fechado":
            sit, d = diferenca_caixa(e["contado"], e["esperado"])
            (st.success if sit == "certo" else st.warning)(
                "Caixa fechado. " + {"certo": "O dinheiro conferiu ✅", "sobrando": f"Sobrou {brl(d)}.",
                                     "faltando": f"Faltou {brl(-d)}."}[sit])
            st.link_button("Mandar o resumo do dia no WhatsApp", link_whats(texto_resumo(loja, e)), type="primary",
                           icon=":material/send:")

    vh, _, _ = vendas_periodo("Hoje", loja)
    vh = vh[vh["status"] != "cancelada"]
    vo, _, _ = vendas_periodo("Ontem", loja)
    vo = vo[vo["status"] != "cancelada"]
    t, to = float(vh["total"].sum()), float(vo["total"].sum())
    e = caixa_estado(loja)

    with st.container(key="kpis"):
        m = st.columns(5)
    metrica(m[0], "Faturamento hoje", t)
    metrica(m[1], "Vendas hoje", len(vh), dinheiro=False)
    metrica(m[2], "Ticket médio", t / len(vh) if len(vh) else 0)
    m[3].metric("Caixa", {"aberto": "Aberto", "fechado": "Fechado", "nunca": "Fechado"}[e["situacao"]],
                f"desde {e['inicio']:%H:%M}" if e["situacao"] == "aberto" else None, delta_color="off")
    m[4].metric("Vs. ontem", f"{(t - to) / to * 100:+.0f}%" if to else "—",
                f"ontem {brl(to)}", delta_color="off",
                help="Faturamento de hoje até agora comparado com o dia inteiro de ontem.")

    with st.container(key="acoes"):
        b = st.columns(4)
        if b[0].button("Nova venda", type="primary", width="stretch", icon=":material/add_shopping_cart:"):
            st.session_state.ir = M_VENDER
            st.rerun()
        if b[1].button("Abrir caixa", width="stretch", icon=":material/lock_open:", disabled=e["situacao"] == "aberto"):
            st.session_state.ir = M_CAIXA
            st.rerun()
        if b[2].button("Fechar caixa", width="stretch", icon=":material/lock:", disabled=e["situacao"] != "aberto"):
            st.session_state.ir = M_CAIXA
            st.rerun()
        if b[3].button("Consultar estoque", width="stretch", icon=":material/inventory_2:"):
            st.session_state.ir = M_EST
            st.rerun()

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("<div class='rotulo'>Vendas por horário · hoje</div>", unsafe_allow_html=True)
        real = vh[~vh["id"].astype(str).str.startswith("VANT")]
        if real.empty:
            st.caption("Nenhuma venda pelo caixa ainda hoje.")
        else:
            hora = real.groupby(real["dt"].dt.hour)["total"].sum().reset_index()
            hora.columns = ["h", "total"]
            hora["Hora"] = hora["h"].map(lambda x: f"{int(x):02d}h")
            grafico(hora, "Ho