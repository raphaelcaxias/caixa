# Caixa Jardim do Éden — segunda parte do app (telas 7 a 12).
# NÃO rode este arquivo sozinho: ele é lido pelo app.py, que tem as importações, a planilha e o login.
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
            grafico(hora, "Hora", ordem=list(hora["Hora"]), altura=200)
        st.markdown("<div class='rotulo'>Formas de pagamento · hoje</div>", unsafe_allow_html=True)
        f = vh.groupby("forma")["total"].sum().rename(index=NOME_FORMA).sort_values(ascending=False).reset_index()
        f.columns = ["Forma", "total"]
        grafico(f, "Forma", horizontal=True, ordem=list(f["Forma"]), altura=max(120, 48 * len(f)))
    with c2:
        st.markdown("<div class='rotulo'>Vendas por vendedor(a) · hoje</div>", unsafe_allow_html=True)
        eq = vh.groupby("vendedor")["total"].sum().sort_values(ascending=False).reset_index()
        eq.columns = ["Vendedor", "total"]
        grafico(eq, "Vendedor", horizontal=True, ordem=list(eq["Vendedor"]), altura=max(120, 48 * len(eq)))
        st.markdown("<div class='rotulo'>Produtos mais vendidos · 7 dias</div>", unsafe_allow_html=True)
        v7, _, _ = vendas_periodo("7 dias", loja)
        it = carregar("Itens")
        it = it[it["venda_id"].isin(v7.loc[v7["status"] != "cancelada", "id"])]
        if it.empty:
            st.caption("Sem produtos vendidos pelo caixa nos últimos 7 dias.")
        else:
            top = it.groupby("produto")["qtd"].sum().sort_values(ascending=False).head(5).reset_index()
            top["produto"] = top["produto"].str.title()
            st.dataframe(top, hide_index=True, width="stretch",
                         column_config={"produto": st.column_config.TextColumn("Produto", width="large"),
                                        "qtd": st.column_config.NumberColumn("Peças", width="small")})

    st.markdown("<div class='rotulo'>Alertas de estoque baixo</div>", unsafe_allow_html=True)
    tab = situacao_estoque(loja)
    alerta = tab[tab["situacao"].isin(["Baixo", "Zerado"])].sort_values(["estoque", "nome"])
    if alerta.empty:
        st.caption("Nada acabando. 🎉" if (tab["situacao"] != "Sem lançamento").any()
                   else "Lance o estoque em Estoque para receber alertas do que está acabando.")
    else:
        st.dataframe(alerta[["nome", "estoque", "situacao"]], hide_index=True, width="stretch",
                     height=min(38 * len(alerta) + 40, 320),
                     column_config={"nome": st.column_config.TextColumn("Produto", width="large"), "estoque": "Restam",
                                    "situacao": "Situação"})


# ================================================================ 12. cabeçalho, menu e main()
def bloquear_sem_planilha():
    """Na nuvem, sem a planilha ligada, nada pode ser vendido: tudo se perderia quando o app dormir."""
    if not (NA_NUVEM and not na_planilha()):
        return
    motivo = erro_nos_secrets() or _credenciais()[1]
    st.error("### O caixa está DESLIGADO da planilha\n"
             "Para não perder nenhuma venda, o app está travado até a ligação com a planilha do Google voltar.\n\n"
             "**Falta nos Secrets:** a seção `[ponte]` com `url` (o link da ponte, termina em /exec) e `senha` "
             "(a mesma das Propriedades do script). Veja o LEIA-ME."
             + (f"\n\n**Problema nos Secrets:** {motivo}" if motivo else ""), icon=":material/cloud_off:")
    st.stop()


DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def cabecalho():
    """Logo, nome, loja, quem está conectado, ligação com a planilha, data e hora, conta."""
    loja = st.session_state.loja
    h = agora()
    conectado = na_planilha()
    with st.container(key="topo"):
        c1, c2, c3 = st.columns([1.7, 3.3, 1], vertical_alignment="center")
        c1.markdown(f"<div class='marca'><img src='data:image/png;base64,{ICONE64}' alt=''>"
                    f"<div><div class='t2'>Caixa</div><div class='t1'>Jardim do Éden</div></div></div>",
                    unsafe_allow_html=True)
        with c2:
            st.markdown(
                "<div class='info-topo'>"
                + f"<span class='chip loja'>{loja}</span>"
                + f"<span class='chip'>{NOME_PAPEL.get(papel(), '')}</span>"
                + f"<span class='chip {'ok' if conectado else 'off'}'><i></i>"
                + ("Planilha conectada" if conectado else "Sem planilha (teste)") + "</span>"
                + f"<span class='chip hora'>{DIAS[h.weekday()]}, {h:%d/%m} · {h:%H:%M}</span></div>",
                unsafe_allow_html=True)
        with c3.popover("Conta", width="stretch", icon=":material/person:"):
            st.markdown(f"**{NOME_PAPEL.get(papel(), '')}** · Loja {loja}")
            if pode("trocar_loja"):
                st.selectbox("Trocar de loja", LOJAS, key="loja")
            if conectado:
                st.success("Ligado à planilha do Google", icon=":material/cloud_done:")
                end = segredo("planilha", "endereco")
                if end:
                    st.link_button("Abrir a planilha", str(end), width="stretch", icon=":material/table_view:")
            else:
                st.warning("Sem planilha: modo de teste neste computador.", icon=":material/cloud_off:")
            if st.button("Atualizar dados", width="stretch", icon=":material/refresh:"):
                gravou_tudo()
                st.rerun()
            if st.button("Sair", width="stretch", icon=":material/logout:"):
                sair()
                st.rerun()
    return st.session_state.loja


def main():
    st.set_page_config(page_title="Caixa Jardim do Éden",
                       page_icon=_achar(os.path.join("marca", "favicon-64.png")) or os.path.join(PASTA, "logo.png"),
                       layout="wide", initial_sidebar_state="collapsed")
    aplicar_estilo()
    bloquear_sem_planilha()
    if not papel():
        dados = ler_token(st.query_params.get("k", ""))
        if dados:
            entrar_sessao(*dados)
        else:
            if st.query_params.get("k"):
                st.query_params.clear()  # token vencido ou de senha antiga
            tela_login()
            return
    if st.session_state.get("loja") not in LOJAS or (st.session_state.loja != LOGIN_LOJA[st.session_state.usuario]
                                                     and not pode("trocar_loja")):
        st.session_state.loja = LOGIN_LOJA[st.session_state.usuario]  # vendedor(a)/gerente só na própria loja
    try:
        preparar_planilha()
    except Exception as e:
        st.error(f"Não consegui abrir a planilha. Confira a internet e a configuração. ({e})")
        st.button("Tentar de novo", type="primary", icon=":material/refresh:", on_click=gravou_tudo)
        st.stop()

    loja = cabecalho()
    if not na_planilha():
        st.warning("**Modo de teste:** as vendas NÃO estão indo para a planilha do Google.", icon=":material/warning:")

    menu = [M_HOJE, M_VENDER, M_CAIXA, M_EST, M_MAIS]
    if "ir" in st.session_state:
        st.session_state.tela = st.session_state.pop("ir")
    if st.session_state.get("tela") not in menu:
        st.session_state.tela = M_HOJE
    with st.container(key="menu"):
        tela = st.segmented_control("Menu", menu, key="tela", label_visibility="collapsed", width="stretch") or M_HOJE
    if tela == M_MAIS:
        sub_menu = ([M_PAINEL] if pode("relatorios") else []) + [M_VENDAS] + ([M_PROD] if pode("produtos") else [])
        if st.session_state.get("sub") not in sub_menu:
            st.session_state.sub = sub_menu[0]
        with st.container(key="submenu"):
            tela = st.segmented_control("Mais", sub_menu, key="sub", label_visibility="collapsed", width="stretch") or sub_menu[0]
    telas = {M_HOJE: tela_hoje, M_CAIXA: tela_caixa, M_VENDER: tela_vender, M_EST: tela_estoque,
             M_VENDAS: tela_vendas, M_PAINEL: tela_painel, M_PROD: tela_produtos}
    try:
        telas.get(tela, tela_hoje)(loja)
    except Exception as e:  # st.rerun/st.stop não são Exception: passam direto
        if nao_salvou(e):
            st.error("**Isto NÃO foi salvo na planilha.** A internet ou o Google falhou na hora de gravar. "
                     "Confira a internet e faça de novo.", icon=":material/cloud_off:")
        else:
            st.error("Não consegui carregar esta tela agora. Confira a internet e toque em **Tentar de novo**. "
                     "Se algo foi digitado, confira se foi salvo antes de repetir.", icon=":material/error:")
        st.button("Tentar de novo", type="primary", icon=":material/refresh:", on_click=gravou_tudo)
        with st.expander("Detalhes técnicos (para o suporte)"):
            st.code(nao_salvou(e) or f"{type(e).__name__}: {e}")
