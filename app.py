# Caixa Jardim do Éden — versão Streamlit
# Vendas, estoque e produtos guardados numa planilha do Google (ou em arquivos locais para teste).
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
    {"id": "VANT-20261119-ATE-1", "data": "2026-11-19 12:10:00", "loja": "Aterrado", "total": 49.99,
     "forma": "pix", "vendedor": "Raphael"},
    {"id": "VANT-20261119-ATE-2", "data": "2026-11-19 12:15:00", "loja": "Aterrado", "total": 74.99, "forma": "debito"},
    {"id": "VANT-20261119-ATE-3", "data": "2026-11-19 12:20:00", "loja": "Aterrado", "total": 59.99, "forma": "pix"},
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
M_HOJE, M_VENDER, M_CAIXA = ":material/home: Hoje", ":material/point_of_sale: Vender", ":material/payments: Caixa"
M_EST, M_VENDAS = ":material/inventory_2: Estoque", ":material/receipt_long: Vendas"
M_PROD, M_PAINEL = ":material/sell: Produtos", ":material/monitoring: Painel"
M_MAIS = ":material/more_horiz: Mais"
M_HOJE = ":material/home: Início"
HORAS_LOGIN = 14  # o login vale por um dia de trabalho, mesmo recarregando a página

with open(os.path.join(PASTA, "logo.png"), "rb") as _f:
    LOGO64 = base64.b64encode(_f.read()).decode()

VINHO, VINHO_E, OURO, OURO_C, CREME, TINTA, LINHA = "#7A1726", "#4A0E18", "#C98A12", "#F2C46B", "#FBF6EC", "#2A1E14", "#EADCC3"
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


@_protege_gravacao
class BancoSheets:
    """Planilha do Google: as duas lojas gravam no mesmo lugar."""
    na_planilha = True

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


def banco():
    cred, planilha = credenciais(), segredo("planilha", "endereco")
    if cred and planilha:
        return _sheets(str(planilha), cred.get("client_email", ""))
    return _local()


def _ler(aba):
    df = banco().ler(aba)
    for c in ABAS[aba]:
        if c in NUMEROS:
            df[c] = num(df[c])
    return df


@st.cache_data(ttl=300, show_spinner="Carregando produtos…")
def _ler_produtos(aba):
    return _ler(aba)


@st.cache_data(ttl=30, show_spinner=False)
def _ler_movimento(aba):
    return _ler(aba)


def carregar(aba):
    """Produtos mudam pouco (guardados 5 min); vendas, estoque e caixa são relidos a cada 30 s."""
    return (_ler_produtos if aba == "Produtos" else _ler_movimento)(aba)


def gravou():
    _ler_produtos.clear()
    _ler_movimento.clear()


def venda_so_total(vid, data, loja, total, forma="nao_informado", vendedor="Não informado", usuario="lançamento manual"):
    return {"id": vid, "data": data, "loja": loja, "vendedor": vendedor, "forma": forma, "subtotal": total,
            "desconto": 0, "total": total, "recebido": total, "troco": 0, "usuario": usuario, "status": "ok"}


def garantir_lancamentos_iniciais():
    ja = set(carregar("Vendas")["id"])
    novos = [venda_so_total(l["id"], l["data"], l["loja"], l["total"], l.get("forma", "nao_informado"),
                            l.get("vendedor", "Não informado")) for l in LANCAMENTOS_INICIAIS if l["id"] not in ja]
    if novos:
        banco().anexar("Vendas", novos)
        gravou()


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
    validas = set(vendas.loc[vendas["status"] != "cancelada", "id"])
    itens = itens[itens["venda_id"].isin(validas)]  # itens sem venda (gravação interrompida) não contam
    e = ent.groupby(["loja", "produto_id"])["qtd"].sum()
    s = itens.groupby(["loja", "produto_id"])["qtd"].sum()
    return e.sub(s, fill_value=0).to_dict()


def produtos_ativos():
    p = carregar("Produtos")
    return p[p["ativo"].astype(str).isin(["1", "1.0", "True", "true", "sim"])].copy()


# ---------------------------------------------------------------- login
LOGIN_LOJA_PADRAO = {"aterrado": "Aterrado", "vila": "Vila Santa Cecília"}


# Senha padrão das lojas, guardada só como código (hash), nunca escrita aqui.
SENHA_PADRAO = "pbkdf2$200000$jde2026caixa$020f0b4421729cdfcb0d2d94630a97dc3a893f62a1f123a3a369c2d168faee00"


def hash_senha(senha, sal=None, voltas=200_000):
    """Transforma a senha num código que não dá para desfazer (PBKDF2-SHA256)."""
    sal = sal or _sec.token_hex(8)
    cod = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal.encode(), voltas).hex()
    return f"pbkdf2${voltas}${sal}${cod}"


def senha_confere(digitada, guardada):
    """Aceita a senha guardada como código (pbkdf2$...) ou, para quem ainda não trocou, em texto."""
    guardada = str(guardada)
    if guardada.startswith("pbkdf2$"):
        try:
            _, voltas, sal, cod = guardada.split("$")
            return hmac.compare_digest(hash_senha(digitada, sal, int(voltas)), guardada)
        except ValueError:
            return False
    return hmac.compare_digest(guardada.encode(), str(digitada).encode())


def usuarios():
    """Só as lojas entram. Senha de cada loja: a dos Secrets ou, se não tiver, a senha padrão (guardada só como código embaralhado)."""
    u = {str(k).lower(): str(v) for k, v in dict(segredo("usuarios") or {}).items()}
    padrao = u.get("norma") or SENHA_PADRAO
    for login in list(dict(segredo("lojas") or {})) + list(LOGIN_LOJA_PADRAO):
        u.setdefault(str(login).lower(), padrao)
    return {k: v for k, v in u.items() if loja_do_login(k)}


def loja_do_login(u=None):
    """Se o login é de uma loja, devolve o nome da loja; se é da dona, devolve None."""
    u = (u or st.session_state.get("usuario", "")).lower()
    nome = segredo("lojas", u) or LOGIN_LOJA_PADRAO.get(u)
    if not nome:
        for l in LOJAS:
            if sem_acento(l).replace(" ", "") == sem_acento(u).replace(" ", ""):
                nome = l
    return nome if nome in LOJAS else None


def nome_login(u):
    return f"Loja {loja_do_login(u)}"


def eh_dona():
    """Todas as lojas têm acesso completo (produtos, custo, cancelar venda, painel de tudo junto)."""
    return bool(loja_do_login())


def _chave():
    k = segredo("app", "chave") or (str(sorted(usuarios().items())) + str(segredo("planilha", "endereco")))
    return hashlib.sha256(str(k).encode()).digest()


def gerar_token(u):
    msg = f"{u}.{int(time.time()) + HORAS_LOGIN * 3600}"
    return msg + "." + hmac.new(_chave(), msg.encode(), hashlib.sha256).hexdigest()


def ler_token(t):
    try:
        u, exp, sig = str(t).rsplit(".", 2)
        msg = f"{u}.{exp}"
        certo = hmac.new(_chave(), msg.encode(), hashlib.sha256).hexdigest()
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
          <div style="color:#8A7A65;margin:6px 0 10px">Toque na sua loja e digite a senha</div></div>""",
                    unsafe_allow_html=True)
        nomes = sorted(usuarios(), key=lambda n: LOJAS.index(loja_do_login(n)))
        with st.form("login", border=False):
            u = st.pills("Qual loja?", nomes, default=nomes[0] if len(nomes) == 1 else None,
                         format_func=nome_login, key="login_user")
            s = st.text_input("Senha", type="password", placeholder="••••••")
            ok = st.form_submit_button("Entrar", type="primary", width="stretch", icon=":material/login:")
        if ok and not u:
            st.error("Toque na sua loja.")
            return
        u = (u or "").lower()
        if ok:
            senha = usuarios().get(u)
            if senha is not None and senha_confere(s, senha):
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


TEM_ATALHO = "shortcut" in inspect.signature(st.button).parameters


def _escolher(chave, nome):
    st.session_state[chave] = nome


def grade_botoes(opcoes, chave, colunas=2):
    """Botões grandes para escolher (o escolhido fica dourado)."""
    with st.container(key=f"esc_{chave}"):
        cols = st.columns(colunas)
        escolhido = st.session_state.get(chave)
        for n, op in enumerate(opcoes):
            nome, icone = op if isinstance(op, tuple) else (op, None)
            cols[n % colunas].button(nome, key=f"{chave}_{nome}", width="stretch", icon=icone,
                                     type="primary" if escolhido == nome else "secondary",
                                     on_click=_escolher, args=(chave, nome))
    return st.session_state.get(chave)


def tela_vender(loja):
    st.session_state.setdefault("carrinho", [])
    st.session_state.setdefault("resultados", [])
    cart = st.session_state.carrinho

    # ---- venda acabou de ser feita
    if st.session_state.get("ultima") and not cart:
        u = st.session_state.ultima
        # HTML numa linha só: linha em branco + recuo viraria "bloco de código" e mostraria </div> na tela
        troco = (f"<div class='ok-troco'>Troco: {brl(u['troco'])}</div>"
                 if u["forma"] == "dinheiro" and float(u["troco"]) > 0 else "")
        salvo = ("<div class='ok-s' style='font-size:.95rem;opacity:.85'>✓ Guardada na planilha</div>"
                 if na_planilha() else "")
        st.markdown(f"<div class='ok-card'><div class='ok-ic'>✓</div><div><div class='ok-t'>Venda feita!</div>"
                    f"<div class='ok-s'>{brl(u['total'])} · {NOME_FORMA.get(u['forma'], u['forma'])} · {u['vendedor']}</div>"
                    f"{troco}{salvo}</div></div>", unsafe_allow_html=True)
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
            c1, c2 = st.columns([2.6, 1.4], vertical_alignment="bottom")
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

    with dir_:
        carrinho(loja)


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
        st.markdown(f"<div class='passo'><span>2</span> Venda · {loja}</div>", unsafe_allow_html=True)
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
            extra = {"shortcut": "Ctrl+Enter"} if TEM_ATALHO else {}
            if st.button(f"Concluir venda · {brl(total)}", type="primary", width="stretch",
                         icon=":material/check_circle:", **extra):
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
    st.dataframe(reais(tab[["nome", "preco", "estoque"]], "preco"), hide_index=True, width="stretch", height=420,
                 column_config={"nome": "Produto", "preco": "Preço",
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


def vendas_periodo(nome, loja, intervalo=None):
    v = carregar("Vendas").copy()
    v["dt"] = pd.to_datetime(v["data"], errors="coerce")
    a, b = intervalo or periodo(nome)
    v = v[(v["dt"] >= a) & (v["dt"] < b)]
    if loja != "Todas":
        v = v[v["loja"] == loja]
    return v, a, b


# ---------------------------------------------------------------- VENDAS FEITAS
def tela_vendas(loja_atual):
    st.markdown("#### Vendas feitas")
    lancar_total_do_dia(loja_atual)
    if eh_dona():
        c1, c2 = st.columns(2)
        per = c1.selectbox("Período", ["Hoje", "Ontem", "7 dias", "30 dias", "Este mês", "Tudo"])
        loja = c2.selectbox("Loja", ["Todas", *LOJAS], index=1 + LOJAS.index(loja_atual))
    else:
        per = st.selectbox("Período", ["Hoje", "Ontem", "7 dias", "30 dias", "Este mês", "Tudo"])
        loja = loja_atual
    v, _, _ = vendas_periodo(per, loja)
    v = v.sort_values("dt", ascending=False)
    ok = v[v["status"] != "cancelada"]
    st.caption(f"{len(ok)} venda(s) · {brl(ok['total'].sum())}" + (f" · {len(v) - len(ok)} cancelada(s)" if len(v) > len(ok) else ""))
    if v.empty:
        st.info("Nenhuma venda nesse período.")
        return
    mostra = v.assign(hora=v["dt"].dt.strftime("%d/%m %H:%M"), pagamento=v["forma"].map(NOME_FORMA).fillna(v["forma"]),
                      situacao=v["status"].map({"ok": "ok", "cancelada": "CANCELADA"}))
    st.dataframe(reais(mostra[["id", "hora", "loja", "vendedor", "pagamento", "total", "situacao"]], "total"), hide_index=True,
                 width="stretch", height=320,
                 column_config={"id": "Venda", "hora": "Quando", "loja": "Loja", "vendedor": "Vendedor(a)",
                                "pagamento": "Pagamento", "total": "Total",
                                "situacao": "Situação"})
    escolha = st.selectbox("Ver itens de uma venda", v["id"].tolist(), index=None, placeholder="Escolha a venda…",
                           format_func=lambda i: f"{i} · {brl(v.set_index('id').at[i, 'total'])}")
    if escolha:
        it = carregar("Itens")
        it = it[it["venda_id"] == escolha]
        st.dataframe(reais(it[["produto", "qtd", "preco", "total"]], "preco", "total"), hide_index=True, width="stretch",
                     column_config={"produto": "Produto", "qtd": "Qtd",
                                    "preco": "Preço",
                                    "total": "Total"})
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




def lancar_total_do_dia(loja_atual):
    """Para registrar o total de um dia em que não se usou o app (não mexe no estoque)."""
    with st.expander("Lançar o total de um dia passado", icon=":material/edit_calendar:"):
        with st.form("lanc_total", clear_on_submit=True):
            c1, c2 = st.columns(2)
            dia = c1.date_input("Dia", value=agora().date() - timedelta(days=1), max_value=agora().date(), format="DD/MM/YYYY")
            loja = c2.selectbox("Loja", LOJAS, index=LOJAS.index(loja_atual)) if eh_dona() else loja_atual
            valor = st.number_input("Total vendido no dia (R$)", min_value=0.0, step=10.0, format="%.2f")
            forma = st.selectbox("Forma de pagamento", ["Não informado", *FORMAS])
            if st.form_submit_button("Lançar", type="primary", width="stretch"):
                if valor <= 0:
                    st.error("Informe o valor.")
                else:
                    banco().anexar("Vendas", [venda_so_total(
                        novo_id("VANT"), f"{dia:%Y-%m-%d} 22:00:00", loja, round(valor, 2),
                        forma="nao_informado" if forma == "Não informado" else FORMAS[forma],
                        usuario=st.session_state.usuario)])
                    gravou()
                    st.success(f"Lançado: {brl(valor)} em {dia:%d/%m/%Y} · {loja}.")
# ---------------------------------------------------------------- PAINEL
def excel(vendas, itens):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        vendas.drop(columns=["dt"], errors="ignore").to_excel(w, sheet_name="Vendas", index=False)
        itens.to_excel(w, sheet_name="Itens", index=False)
    return buf.getvalue()


VINHO_G, OURO_G = "#7A1726", "#E0A21B"
_EIXO_R = ("'R$ ' + replace(datum.value >= 1e6 ? format(datum.value / 1e6, '.1f') + ' Mi' : "
           "datum.value >= 1e3 ? format(datum.value / 1e3, '.1f') + ' mil' : format(datum.value, '.0f'), '.', ',')")


def grafico(df, x, y="total", cor=None, horizontal=False, ordem=None, altura=260):
    """Barras com eixo em R$ abreviado e valor exato ao passar o dedo/mouse."""
    df = df.copy()
    df["Valor"] = df[y].map(brl)
    eixo_cat = alt.Axis(labelAngle=0, labelLimit=160, title=None, labelFontSize=13)
    eixo_val = alt.Axis(labelExpr=_EIXO_R, title=None, labelFontSize=12, grid=True, tickCount=5)
    cat = alt.X(f"{x}:N", sort=ordem, axis=eixo_cat) if not horizontal else alt.Y(f"{x}:N", sort=ordem, axis=eixo_cat)
    val = alt.Y(f"{y}:Q", axis=eixo_val) if not horizontal else alt.X(f"{y}:Q", axis=eixo_val)
    enc = {"x": cat, "y": val} if not horizontal else {"y": cat, "x": val}
    tip = [alt.Tooltip(f"{x}:N", title=""), alt.Tooltip("Valor:N", title="Total")]
    if cor:
        enc["color"] = alt.Color(f"{cor}:N", scale=alt.Scale(range=[VINHO_G, OURO_G]), legend=alt.Legend(orient="bottom", title=None))
        enc["xOffset" if not horizontal else "yOffset"] = alt.XOffset(f"{cor}:N") if not horizontal else alt.YOffset(f"{cor}:N")
        tip.insert(1, alt.Tooltip(f"{cor}:N", title="Loja"))
        marca = alt.Chart(df).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
    else:
        marca = alt.Chart(df).mark_bar(color=VINHO_G if not horizontal else OURO_G, cornerRadius=5)
    graf = marca.encode(**enc, tooltip=tip).properties(height=altura)
    st.altair_chart(graf.configure(background="#FFFFFF").configure_view(strokeWidth=0).configure_axis(domain=False),
                    width="stretch")


def destaques(v, it):
    """Frases curtas com o que mais chama atenção no período."""
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


def tela_painel(loja_atual):
    dona = True  # todas as lojas veem os próprios números e o total das duas
    st.markdown("#### Indicadores")
    loja = st.segmented_control("Ver", [*LOJAS, "Todas"], default=loja_atual, key="painel_loja",
                                format_func=lambda l: "Tudo junto" if l == "Todas" else l) or loja_atual
    per = st.segmented_control("Período", ["Hoje", "Ontem", "7 dias", "30 dias", "Este mês", "Tudo", "Escolher datas"],
                               default="7 dias", key="painel_per") or "7 dias"
    intervalo = None
    if per == "Escolher datas":
        hoje = agora().date()
        sel = st.date_input("De / até", value=(hoje - timedelta(days=6), hoje), max_value=hoje,
                            format="DD/MM/YYYY", key="painel_datas")
        ini_d, fim_d = (sel if isinstance(sel, (tuple, list)) and len(sel) == 2 else (sel[0] if isinstance(sel, (tuple, list)) else sel,) * 2)
        intervalo = (datetime.combine(ini_d, datetime.min.time()), datetime.combine(fim_d, datetime.min.time()) + timedelta(days=1))
    v, a, b = vendas_periodo(per, loja, intervalo)
    v = v[v["status"] != "cancelada"]
    vendedores = sorted(v["vendedor"].dropna().unique())
    if len(vendedores) > 1:
        quem = st.selectbox("Vendedor(a)", ["Todos", *vendedores], key="painel_vend")
        if quem != "Todos":
            v = v[v["vendedor"] == quem]
    it = carregar("Itens")
    it = it[it["venda_id"].isin(v["id"])]

    # comparação com o período anterior do mesmo tamanho
    todas = carregar("Vendas").copy()
    todas["dt"] = pd.to_datetime(todas["data"], errors="coerce")
    ant = todas[(todas["dt"] >= a - (b - a)) & (todas["dt"] < a) & (todas["status"] != "cancelada")]
    if loja != "Todas":
        ant = ant[ant["loja"] == loja]
    if st.session_state.get("painel_vend", "Todos") != "Todos":
        ant = ant[ant["vendedor"] == st.session_state["painel_vend"]]
    tot, n = v["total"].sum(), len(v)
    delta = None if per == "Tudo" or ant.empty else f"{(tot - ant['total'].sum()) / max(ant['total'].sum(), 0.01) * 100:+.0f}% vs. período anterior"
    custos = carregar("Produtos").set_index("id")["custo"]

    def custo_de(ids):  # sempre número, mesmo sem nenhuma venda (coluna vazia)
        return pd.to_numeric(ids.map(custos), errors="coerce").fillna(0).astype("float64")

    com_custo = it[custo_de(it["produto_id"]) > 0]
    lucro = (com_custo["total"] - com_custo["qtd"] * custo_de(com_custo["produto_id"])).sum()
    desc_rateio = v.loc[v["id"].isin(it["venda_id"]), "desconto"].sum()
    k = st.container(key="kpis")
    cols = k.columns(3) + k.columns(2 if dona else 1)
    metrica(cols[0], "Total vendido", tot, delta)
    metrica(cols[1], "Vendas", n, dinheiro=False)
    metrica(cols[2], "Venda média", tot / n if n else 0)
    metrica(cols[3], "Peças vendidas", it["qtd"].sum(), dinheiro=False,
            ajuda="Só conta vendas feitas no caixa (os lançamentos só de total não têm peças).")
    if dona:
        metrica(cols[4], "Lucro bruto estimado", lucro - desc_rateio,
                ajuda="Preço de venda menos o custo atual do produto, já tirando os descontos. "
                      "Ficam de fora: produtos sem custo (lingerie e prótese por faixa) e lançamentos só de total.")
    if v.empty:
        st.info("Nenhuma venda nesse período.")
        return
    destaques(v, it)

    if dona and loja == "Todas":
        st.markdown("**Comparativo das lojas**")
        linhas = []
        for l in LOJAS:
            vl = v[v["loja"] == l]
            il = it[it["venda_id"].isin(vl["id"])]
            cl = il[custo_de(il["produto_id"]) > 0]
            luc = (cl["total"] - cl["qtd"] * custo_de(cl["produto_id"])).sum() - vl.loc[vl["id"].isin(il["venda_id"]), "desconto"].sum()
            linha = {"Loja": l, "Total": vl["total"].sum(), "Vendas": len(vl),
                     "Venda média": vl["total"].sum() / len(vl) if len(vl) else 0, "Peças": int(il["qtd"].sum()),
                     "Lucro estimado": luc, "Parte do total": vl["total"].sum() / tot if tot else 0}
            for kf, nome in NOME_FORMA.items():
                linha[nome] = vl.loc[vl["forma"] == kf, "total"].sum()
            linhas.append(linha)
        comp = pd.DataFrame(linhas)
        comp = comp.loc[:, (comp != 0).any(axis=0) | comp.columns.isin(["Loja", "Total", "Vendas"])]
        dinheiro = [c for c in ["Total", "Venda média", "Lucro estimado", *NOME_FORMA.values()] if c in comp]
        st.dataframe(reais(comp, *dinheiro), hide_index=True, width="stretch",
                     column_config={"Parte do total": st.column_config.ProgressColumn(
                         "Parte do total", format="percent", min_value=0, max_value=1)})
        st.markdown("**Por dia, loja a loja**")
        pd_l = v.groupby([v["dt"].dt.date.rename("d"), "loja"])["total"].sum().reset_index()
        ordem = sorted(pd_l["d"].unique())
        pd_l["Dia"] = pd_l["d"].map(lambda d: f"{d:%d/%m}")
        grafico(pd_l, "Dia", cor="loja", ordem=[f"{d:%d/%m}" for d in ordem])

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Por forma de pagamento**")
        f = v.groupby("forma")["total"].sum().rename(index=NOME_FORMA).sort_values(ascending=False).reset_index()
        f.columns = ["Forma", "total"]
        grafico(f, "Forma", horizontal=True, ordem=list(f["Forma"]), altura=max(140, 52 * len(f)))
    with g2:
        st.markdown("**Por dia**")
        dia = v.groupby(v["dt"].dt.date.rename("d"))["total"].sum().reset_index()
        dia["Dia"] = dia["d"].map(lambda d: f"{d:%d/%m}")
        grafico(dia, "Dia", ordem=list(dia["Dia"]))

    g3, g4 = st.columns(2)
    with g3:
        st.markdown("**Por vendedor(a)**")
        eq = v.groupby("vendedor").agg(total=("total", "sum"), vendas=("id", "count"))
        eq["média"] = eq["total"] / eq["vendas"]
        st.dataframe(reais(eq.sort_values("total", ascending=False).rename_axis("Vendedor(a)"), "total", "média"), width="stretch",
                     column_config={"total": "Total",
                                    "vendas": "Vendas",
                                    "média": "Venda média"})
    with g4:
        st.markdown("**Vendedor(a) × pagamento**")
        cruz = v.pivot_table(index="vendedor", columns="forma", values="total", aggfunc="sum", fill_value=0)
        cruz.columns = [NOME_FORMA.get(c, c) for c in cruz.columns]
        cruz = cruz.loc[cruz.sum(axis=1) > 0, cruz.sum(axis=0) > 0]
        st.dataframe(reais(cruz.rename_axis("Vendedor(a)")), width="stretch")

    g5, g6 = st.columns(2)
    with g5:
        st.markdown("**Mais vendidos**")
        if it.empty:
            st.caption("Sem peças no período (só lançamentos de total).")
        else:
            top = it.groupby("produto").agg(qtd=("qtd", "sum"), total=("total", "sum")).sort_values("qtd", ascending=False).head(10)
            top = top.reset_index()
            top["produto"] = top["produto"].str.title()
            st.dataframe(reais(top, "total"), hide_index=True, width="stretch", column_order=["qtd", "produto", "total"],
                         column_config={"qtd": st.column_config.NumberColumn("Peças", width="small"),
                                        "produto": st.column_config.TextColumn("Produto", width="medium"), "total": "Total"})
    with g6:
        st.markdown("**Por horário**")
        real = v[~v["id"].astype(str).str.startswith("VANT")]
        if real.empty:
            st.caption("Sem vendas com horário no período.")
        else:
            hora = real.groupby(real["dt"].dt.hour)["total"].sum().reset_index()
            hora.columns = ["h", "total"]
            hora["Hora"] = hora["h"].map(lambda x: f"{int(x):02d}h")
            grafico(hora, "Hora", ordem=list(hora["Hora"]))

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
    metrica(m1, "Vendido no caixa", v["total"].sum(), f"{len(v)} venda(s)", delta_color="off")
    metrica(m2, "Dinheiro na gaveta", e["esperado"], ajuda="Troco inicial + vendas em dinheiro + reforços − retiradas")
    metrica(m3, "Pix + cartões", sum(e["por"].get(k, 0) for k in ("pix", "credito", "debito")))
    st.dataframe(pd.DataFrame([{"Forma": NOME_FORMA[k], "Total": brl(e["por"].get(k, 0))} for k in FORMAS.values()]),
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
    quem = "" if loja_do_login() else f", {st.session_state.usuario.capitalize()}"
    st.markdown(f"<div class='saud'>{saud}{quem}!</div>"
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
    if not len(vh) and to:
        st.caption(f"Ontem esta loja vendeu {brl(to)} em {len(vo)} venda(s). Os números de hoje começam do zero.")
    metrica(m1, "Vendido hoje", t, f"{(t - to) / to * 100:+.0f}% que ontem" if to else None)
    metrica(m2, "Vendas hoje", len(vh), dinheiro=False)
    metrica(m3, "Venda média", t / len(vh) if len(vh) else 0)
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
def bloquear_sem_planilha():
    """Na nuvem, sem a planilha ligada, nada pode ser vendido: tudo se perderia quando o app dormir."""
    if not (NA_NUVEM and not na_planilha()):
        return
    motivo = erro_nos_secrets() or _credenciais()[1]
    falta = []
    if not credenciais() and not _credenciais()[1]:
        falta.append("a chave do Google (gcp_service_account ou gcp_json)")
    if not segredo("planilha", "endereco"):
        falta.append("o endereço da planilha ([planilha] endereco)")
    st.error("### O caixa está DESLIGADO da planilha\n"
             "Para não perder nenhuma venda, o app está travado até a ligação com a planilha do Google voltar.\n\n"
             + (f"**Problema nos Secrets:** {motivo}\n\n" if motivo else "")
             + (f"**Falta nos Secrets:** {' e '.join(falta)}.\n\n" if falta else "")
             + "**Como resolver:** Manage app → ⋮ → Settings → Secrets → conferir/colar de novo → Save → "
               "depois Manage app → ⋮ → Reboot app.", icon=":material/cloud_off:")
    st.stop()


def main():
    st.set_page_config(page_title="Caixa Jardim do Éden", page_icon=os.path.join(PASTA, "logo.png"),
                       layout="wide", initial_sidebar_state="collapsed")
    aplicar_estilo()
    bloquear_sem_planilha()
    if "usuario" not in st.session_state:
        u = ler_token(st.query_params.get("k", ""))
        if u:
            st.session_state.usuario = u
        else:
            tela_login()
            return
    try:
        preparar_produtos()
        garantir_lancamentos_iniciais()
    except Exception as e:
        st.error(f"Não consegui abrir a planilha. Confira a internet e a configuração. ({e})")
        st.stop()

    topo = st.container(key="topo")
    topo1, topo2, topo3 = topo.columns([3, 2, 1.1], vertical_alignment="center")
    topo1.markdown(f"<div class='marca'><img src='data:image/png;base64,{LOGO64}'><div>"
                   f"<div class='t2'>Loja {loja_do_login() or ''}</div><div class='t1'>Jardim do Éden</div></div></div>",
                   unsafe_allow_html=True)
    fixa = loja_do_login()
    if fixa:
        loja = fixa
    else:
        if "loja" not in st.session_state:
            q = st.query_params.get("loja", "")
            st.session_state.loja = LOJAS[int(q)] if q.isdigit() and int(q) < len(LOJAS) else LOJAS[0]
        loja = topo2.selectbox("Loja", LOJAS, key="loja", label_visibility="collapsed")
        st.query_params["loja"] = str(LOJAS.index(loja))
    with topo3.popover("Conta", width="stretch", icon=":material/person:"):
        if na_planilha():
            n_v = len(carregar("Vendas"))
            st.success(f"Ligado à planilha do Google · {n_v} venda(s) guardada(s)", icon=":material/cloud_done:")
            st.link_button("Abrir a planilha", str(segredo("planilha", "endereco")), width="stretch",
                           icon=":material/table_view:")
        else:
            st.warning("Sem planilha: modo de teste neste computador.", icon=":material/cloud_off:")
        if st.button("Atualizar dados", width="stretch", icon=":material/refresh:"):
            gravou()
            st.rerun()
        if st.button("Sair", width="stretch", icon=":material/logout:"):
            st.session_state.clear()
            st.query_params.pop("k", None)
            st.rerun()
    if not na_planilha():
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
        sub_menu = [M_PAINEL, M_VENDAS] + ([M_PROD] if eh_dona() else [])
        if st.session_state.get("sub") not in sub_menu:
            st.session_state.sub = M_PAINEL
        with st.container(key="submenu"):
            tela = st.segmented_control("Mais", sub_menu, key="sub", label_visibility="collapsed", width="stretch") or M_PAINEL
    telas = {M_HOJE: tela_hoje, M_CAIXA: tela_caixa, M_VENDER: tela_vender, M_EST: tela_estoque,
             M_VENDAS: tela_vendas, M_PAINEL: tela_painel, M_PROD: lambda _l: tela_produtos()}
    try:
        telas.get(tela, tela_hoje)(loja)
    except Exception as e:  # st.rerun/st.stop não são Exception: passam direto
        if nao_salvou(e):
            st.error("**Isto NÃO foi salvo na planilha.** A internet ou o Google falhou na hora de gravar. "
                     "Confira a internet e faça de novo.", icon=":material/cloud_off:")
        else:
            st.error("Não consegui carregar esta tela agora. Confira a internet e toque em **Tentar de novo**. "
                     "Se algo foi digitado, confira se foi salvo antes de repetir.", icon=":material/error:")
        st.button("Tentar de novo", type="primary", icon=":material/refresh:", on_click=gravou)
        with st.expander("Detalhes técnicos (para o suporte)"):
            st.code(nao_salvou(e) or f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
