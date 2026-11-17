# Caixa Jardim do Éden — versão Streamlit
# Vendas, estoque e produtos guardados numa planilha do Google (ou em arquivos locais para teste).
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
HORAS_LOGIN = 14  # o login vale por um dia de trabalho, mesmo recarregando a página

st.set_page_config(page_title="Caixa Jardim do Éden", page_icon=os.path.join(PASTA, "logo.png"),
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.block-container{padding-top:3.2rem;padding-bottom:3rem;max-width:1200px}
div[data-testid="stMetricValue"]{font-size:1.6rem}
.preco{font-weight:800;color:#8A5F12;font-size:1.1rem}
.total-grande{font-size:2.2rem;font-weight:900;color:#2A1E14}
.sub{color:#7A6A55;font-size:.9rem}
.stButton>button,.stFormSubmitButton>button{min-height:3rem;font-weight:700}
input{font-size:16px!important}
@media(max-width:640px){.block-container{padding-left:.8rem;padding-right:.8rem}}
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


@st.cache_resource
def banco():
    cred, planilha = segredo("gcp_service_account"), segredo("planilha", "endereco")
    if not cred and segredo("gcp_json"):
        import json
        cred = json.loads(str(segredo("gcp_json")))  # o arquivo .json do Google colado inteiro
    if cred and planilha:
        return BancoSheets(cred, str(planilha))
    return BancoLocal(os.path.join(PASTA, "dados"))


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
    _, meio, _ = st.columns([1, 1.3, 1])
    with meio:
        st.image(os.path.join(PASTA, "logo.png"), width=150)
        st.markdown("### Caixa Jardim do Éden")
        st.caption("Digite seu usuário e senha.")
        with st.form("login"):
            u = st.text_input("Usuário", placeholder="ex.: norma").strip().lower()
            s = st.text_input("Senha", type="password")
            ok = st.form_submit_button("Entrar", type="primary", width="stretch")
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
    st.toast(f"➕ {p['nome']}")


def tela_vender(loja):
    st.session_state.setdefault("carrinho", [])
    st.session_state.setdefault("resultados", [])
    if st.session_state.get("ultima"):
        u = st.session_state.ultima
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.success(f"✅ Venda {u['id']} registrada: {brl(u['total'])} · {NOME_FORMA[u['forma']]} · {u['vendedor']}")
        c2.link_button("📲 Comprovante no WhatsApp", link_whats(texto_comprovante(u)), width="stretch")
    if caixa_estado(loja)["situacao"] != "aberto":
        st.info("O caixa desta loja está fechado. Dá para vender, mas abra o caixa em **💰 Caixa** "
                "para conferir o dinheiro no fim do dia.", icon="💡")
    prods = produtos_ativos()
    est = estoque()
    esq, dir_ = st.columns([1.35, 1], gap="large")

    with esq:
        with st.form("busca", clear_on_submit=True, border=False):
            c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
            q = c1.text_input("Código de barras, nome ou valor",
                              placeholder="Passe o leitor, digite o nome ou o valor (ex.: 129)")
            enviar = c2.form_submit_button("Buscar", width="stretch")
        if enviar:
            tipo, achados = buscar(q, prods)
            if tipo == "codigo" or (tipo == "preco" and len(achados) == 1):
                por_no_carrinho(achados[0])
                st.session_state.resultados = []
            elif not achados:
                st.session_state.resultados = []
                if q.strip():
                    st.warning(f"Nada encontrado para “{q}”.")
            else:
                st.session_state.resultados = [dict(r) for r in achados]
                if tipo == "preco":
                    st.info(f"{len(achados)} produtos com esse valor — toque no que a cliente levou.")

        res = st.session_state.resultados
        if res:
            st.caption(f"{len(res)} resultado(s)")
            for i, p in enumerate(res):
                c1, c2, c3 = st.columns([3, 1.2, 1.1], vertical_alignment="center")
                q_est = int(est.get((loja, p["id"]), 0))
                c1.markdown(f"**{p['nome']}**  \n<span class='sub'>{q_est} em estoque</span>",
                            unsafe_allow_html=True)
                c2.markdown(f"<span class='preco'>{brl(p['preco'])}</span>", unsafe_allow_html=True)
                if c3.button("Adicionar", key=f"add{i}{p['id']}", width="stretch"):
                    por_no_carrinho(p)
                    st.session_state.resultados = []
                    st.rerun()
        elif not st.session_state.carrinho:
            st.caption("Dica: digite só o valor (ex.: 189) para ver os produtos desse preço. "
                       "Se só existir um, ele já entra na venda.")

    with dir_:
        with st.container(border=True):
            cart = st.session_state.carrinho
            st.markdown(f"#### Venda · {loja}")
            if not cart:
                st.caption("Nenhum item ainda.")
            for i, it in enumerate(list(cart)):
                c1, c2, c3 = st.columns([2.6, 1.1, .6], vertical_alignment="center")
                c1.markdown(f"**{it['nome']}**  \n<span class='sub'>{brl(it['preco'])} cada</span>",
                            unsafe_allow_html=True)
                nq = c2.number_input("Qtd", min_value=1, max_value=999, value=int(it["qtd"]), step=1,
                                     key=f"q{it['id']}_{it['qtd']}", label_visibility="collapsed")
                if nq != it["qtd"]:
                    it["qtd"] = int(nq)
                    st.rerun()
                if c3.button("✕", key=f"rm{it['id']}", help="Tirar da venda"):
                    cart.pop(i)
                    st.rerun()
            subtotal = round(sum(it["preco"] * it["qtd"] for it in cart), 2)
            desconto = 0.0
            if cart:
                d1, d2 = st.columns([1, 2], vertical_alignment="bottom")
                tipo_d = d1.segmented_control("Desconto em", ["R$", "%"], default="R$", key="tipo_desc") or "R$"
                vd = d2.number_input("Desconto", min_value=0.0, value=0.0, step=1.0, format="%.2f", key="desconto",
                                     label_visibility="collapsed")
                desconto = round(subtotal * min(vd, 100) / 100, 2) if tipo_d == "%" else min(vd, subtotal)
                if desconto:
                    st.caption(f"Desconto: {brl(desconto)}")
            total = round(subtotal - desconto, 2)
            st.markdown(f"<div class='sub'>Total</div><div class='total-grande'>{brl(total)}</div>",
                        unsafe_allow_html=True)

            if cart:
                vend = st.segmented_control("Quem vendeu?", VENDEDORES, key="vendedor")
                forma_n = st.segmented_control("Forma de pagamento", list(FORMAS), key="forma")
                recebido, troco = total, 0.0
                if forma_n == "Dinheiro":
                    recebido = st.number_input("Valor recebido (R$)", min_value=0.0, value=float(total),
                                               step=5.0, format="%.2f", key=f"rec{total}")
                    troco = round(recebido - total, 2)
                    if troco > 0:
                        st.success(f"Troco: **{brl(troco)}**")
                if st.button("Finalizar venda", type="primary", width="stretch"):
                    erro = None
                    if not vend:
                        erro = "Escolha quem vendeu."
                    elif not forma_n:
                        erro = "Escolha a forma de pagamento."
                    elif forma_n == "Dinheiro" and recebido < total:
                        erro = "O valor recebido é menor que o total."
                    if erro:
                        st.error(erro)
                    else:
                        finalizar(loja, vend, FORMAS[forma_n], subtotal, desconto, total, recebido, troco)
                if st.button("Limpar venda", width="stretch"):
                    limpar_venda()
                    st.rerun()


def limpar_venda():
    st.session_state.carrinho = []
    st.session_state.resultados = []
    for k in [k for k in st.session_state if k in ("desconto", "forma", "vendedor", "tipo_desc") or str(k).startswith("rec")]:
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

    with st.expander("➕ Cadastrar produto novo"):
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
    if c1.button("💾 Salvar alterações", type="primary", width="stretch"):
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
    t1, t2 = st.tabs(["📦 Chegou mercadoria", "🔢 Contagem (acertar estoque)"] if eh_dona() else
                     ["📦 Chegou mercadoria", "🔢 Contagem (só a dona)"])
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
    m1, m2, m3, m4, m5 = st.columns(5)
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

    st.download_button("⬇️ Baixar estas vendas em Excel", excel(v, it),
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
            st.link_button("📲 Reenviar o resumo desse caixa", link_whats(texto_resumo(loja, e)))
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
    m1, m2, m3 = st.columns(3)
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
    st.link_button("📲 Mandar o resumo parcial no WhatsApp", link_whats(texto_resumo(loja, e)))


# ---------------------------------------------------------------- HOJE (tela inicial)
def tela_hoje(loja):
    h = agora()
    saud = "Bom dia" if h.hour < 12 else "Boa tarde" if h.hour < 18 else "Boa noite"
    st.markdown(f"### {saud}, {st.session_state.usuario.capitalize()}! 👋")
    st.caption(f"{loja} · {h:%d/%m/%Y}")
    if st.session_state.pop("fechou", False):
        e = caixa_estado(loja)
        if e["situacao"] == "fechado":
            d = e["contado"] - e["esperado"]
            (st.success if abs(d) < 0.005 else st.warning)(
                "Caixa fechado. " + ("O dinheiro conferiu ✅" if abs(d) < 0.005 else
                                     (f"Sobrou {brl(d)}." if d > 0 else f"Faltou {brl(-d)}.")))
            st.link_button("📲 Mandar o resumo do dia no WhatsApp", link_whats(texto_resumo(loja, e)), type="primary")

    vh, _, _ = vendas_periodo("Hoje", loja)
    vh = vh[vh["status"] != "cancelada"]
    vo, _, _ = vendas_periodo("Ontem", loja)
    vo = vo[vo["status"] != "cancelada"]
    t, to = vh["total"].sum(), vo["total"].sum()
    e = caixa_estado(loja)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vendido hoje", brl(t), f"{(t - to) / to * 100:+.0f}% vs. ontem" if to else None)
    m2.metric("Vendas hoje", len(vh))
    m3.metric("Venda média", brl(t / len(vh) if len(vh) else 0))
    m4.metric("Caixa", {"aberto": "Aberto", "fechado": "Fechado", "nunca": "Fechado"}[e["situacao"]],
              f"desde {e['inicio']:%H:%M}" if e["situacao"] == "aberto" else None, delta_color="off")

    b1, b2, b3 = st.columns(3)
    if b1.button("🛒 Nova venda", type="primary", width="stretch"):
        st.session_state.ir = "🛒 Vender"
        st.rerun()
    if b2.button("💰 " + ("Fechar o caixa" if e["situacao"] == "aberto" else "Abrir o caixa"), width="stretch"):
        st.session_state.ir = "💰 Caixa"
        st.rerun()
    if b3.button("📦 Chegou mercadoria", width="stretch"):
        st.session_state.ir = "📦 Estoque"
        st.rerun()

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
            st.caption("Nada acabando. 🎉" if ja_teve else "Lance o estoque em 📦 Estoque para ver o que está acabando.")
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

    topo1, topo2, topo3 = st.columns([3, 2, 1], vertical_alignment="center")
    with topo1:
        a, b = st.columns([1, 6], vertical_alignment="center")
        a.image(os.path.join(PASTA, "logo.png"), width=52)
        b.markdown("**Jardim do Éden** · caixa")
    if "loja" not in st.session_state:
        q = st.query_params.get("loja", "")
        st.session_state.loja = LOJAS[int(q)] if q.isdigit() and int(q) < len(LOJAS) else LOJAS[0]
    loja = topo2.selectbox("Loja", LOJAS, key="loja", label_visibility="collapsed")
    st.query_params["loja"] = str(LOJAS.index(loja))
    with topo3.popover(f"👤 {st.session_state.usuario}", width="stretch"):
        if st.button("🔄 Atualizar dados", width="stretch"):
            gravou()
            st.rerun()
        if st.button("Sair", width="stretch"):
            st.session_state.clear()
            st.query_params.pop("k", None)
            st.rerun()
    if isinstance(banco(), BancoLocal):
        st.warning("Modo de teste: os dados estão em arquivos nesta máquina. "
                   "Para usar online nas duas lojas, ligue a planilha do Google (veja o LEIA-ME).", icon="⚠️")

    menu = ["🏠 Hoje", "🛒 Vender", "💰 Caixa", "📦 Estoque", "🧾 Vendas"]
    if eh_dona():
        menu += ["🏷️ Produtos", "📊 Painel"]
    if "ir" in st.session_state:
        st.session_state.tela = st.session_state.pop("ir")
    if st.session_state.get("tela") not in menu:
        st.session_state.tela = "🏠 Hoje"
    tela = st.segmented_control("Menu", menu, key="tela", label_visibility="collapsed") or "🏠 Hoje"
    st.divider()
    if tela == "🏠 Hoje":
        tela_hoje(loja)
    elif tela == "💰 Caixa":
        tela_caixa(loja)
    elif tela == "🛒 Vender":
        tela_vender(loja)
    elif tela == "📦 Estoque":
        tela_estoque(loja)
    elif tela == "🏷️ Produtos" and eh_dona():
        tela_produtos()
    elif tela == "🧾 Vendas":
        tela_vendas(loja)
    elif eh_dona():
        tela_painel(loja)


main()
