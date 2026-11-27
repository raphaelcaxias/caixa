# Caixa Jardim do Éden

Sistema de caixa (PDV) das lojas **Aterrado** e **Vila Santa Cecília**. Roda no navegador (computador e celular) pelo Streamlit Community Cloud e guarda tudo numa **planilha do Google**, por meio de uma "ponte" em Apps Script.

## Arquivos

| Arquivo | O que é |
|---|---|
| `app.py` | O aplicativo, 1ª parte: configuração, planilha, login e venda (seções 1 a 6) |
| `app_telas.py` | O aplicativo, 2ª parte: estoque, vendas, relatórios, caixa, início e menu (seções 7 a 12). Sobe **junto** com o app.py |
| `estilo.css` | Visual: paleta oficial, fontes, celular e tablet |
| `marca/` | Ícone de app (512 e 192), favicon (64 e 32), logo do login e logo horizontal |
| `ponte-apps-script.gs` | Texto da ponte, que fica no Apps Script da planilha |
| `produtos_iniciais.csv` | Os 247 produtos (usados só se a aba Produtos estiver vazia) |
| `logo.png` | Logomarca original (base dos arquivos de `marca/`) |
| `requirements.txt` | Bibliotecas Python |
| `ferramentas/gerar_marca.py` | Gera os arquivos de `marca/` quando chegar a logomarca nova |
| `tests/` | Testes automáticos. **Não sobem para o GitHub.** |

Nenhuma senha, link ou chave fica escrita nos arquivos. Tudo vem dos **Secrets**.

## Quem pode o quê

O login continua por loja: a pessoa toca na loja e digita a senha. **A senha define o papel.** As permissões são conferidas no servidor antes de abrir cada tela e antes de cada gravação, não só escondendo botões.

| | Vendedor(a) | Gerente | Dona |
|---|:-:|:-:|:-:|
| Vender, consultar produtos e estoque | ✓ | ✓ | ✓ |
| Abrir caixa, sangria, reforço e fechar caixa (da própria loja) | ✓ | ✓ | ✓ |
| Ver vendas | hoje e ontem | todo o histórico | todo o histórico |
| Chegou mercadoria, contagem e acerto de estoque | | ✓ | ✓ |
| Relatórios e Excel | | da própria loja | todas as lojas e "tudo junto" |
| Custos, margem, cadastro e preço de produtos | | | ✓ |
| Cancelar venda e lançar o total de um dia | | | ✓ |
| Trocar de loja depois de entrar | | | ✓ |

Use senhas **diferentes** para cada papel. Se duas forem iguais, vale a do papel mais alto.

## Secrets (Streamlit → Manage app → ⋮ → Settings → Secrets)

Apague tudo o que estiver lá e cole o modelo abaixo, trocando os valores entre aspas:

```toml
[ponte]
url = "COLE AQUI O LINK DA PONTE (termina em /exec)"
senha = "UMA SENHA NOVA E LONGA PARA A PONTE"

[acessos]
dona = "SENHA DA DONA"
gerente = "SENHA DA GERENTE"
vendedor = "SENHA DO(A) VENDEDOR(A)"

[app]
chave = "UMA FRASE LONGA QUALQUER, SÓ PARA ASSINAR OS LOGINS"

[planilha]
endereco = "LINK DA PLANILHA (opcional: aparece o botão Abrir a planilha)"
```

- A `senha` da ponte tem que ser **igual** à propriedade `SENHA` do Apps Script (passo 2 abaixo).
- Trocar a senha de um papel desconecta, na hora, todos os aparelhos que estavam logados com ela.
- Trocar a `chave` desconecta todo mundo.

**Compatibilidade:** se a seção `[acessos]` ainda não existir, a senha antiga em `[usuarios] norma` continua entrando, com acesso de dona. Assim o caixa não trava no dia da atualização.

## Atualizar (ordem certa para não parar o caixa)

Faça com as lojas fechadas, para não haver venda no meio da troca.

1. **Trocar a ponte:** na planilha, **Extensões → Apps Script**. Apague tudo, cole o `ponte-apps-script.gs` e salve com **Ctrl+S**.
2. **Senha da ponte:** no Apps Script, clique na engrenagem **Configurações do projeto → Propriedades do script → Adicionar propriedade**. Em Propriedade, escreva `SENHA`; em Valor, a senha nova da ponte. Salve.
3. **Publicar a ponte:** **Implantar → Gerenciar implantações →** lápis ✏️ **→ Versão: Nova versão → Implantar**. O link continua o mesmo. Para testar, abra o link: tem que aparecer *"Ponte do Caixa funcionando"*.
4. **Secrets:** cole o modelo acima, já preenchido, e clique em **Save**.
5. **GitHub (repositório `caixa`):** clique em **Add file → Upload files** e envie `app.py`, `app_telas.py`, `estilo.css`, `requirements.txt`, `LEIA-ME.md`, `produtos_iniciais.csv`, `logo.png`, `favicon-64.png`, `logo-login.png` e `boutique-640.jpg` (as imagens podem ir soltas, sem pasta). Clique em **Commit changes**. **Não envie** a pasta `tests` nem arquivos `.json`.
6. **Streamlit:** **Manage app → ⋮ → Reboot app**.
7. **Conferir:**
   - Entre com cada uma das 3 senhas e veja se o menu muda (o vendedor não vê Relatórios nem Produtos).
   - O cabeçalho mostra **"Planilha conectada"**.
   - Faça uma venda de teste, confira na aba Vendas e cancele com a senha da dona.

Se aparecer **"senha da ponte errada"**, a senha dos Secrets não é igual à propriedade `SENHA` do Apps Script.

## Rodar no computador (teste)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sem `[ponte]` nos Secrets, o app grava na pasta `dados/` e mostra "Modo de teste". Para testar o login no computador, crie o arquivo `.streamlit/secrets.toml` com a seção `[acessos]`.

Testes automáticos (precisam do Node.js para o Google simulado):

```bash
pip install pytest
python -m pytest tests/
```

## Como a venda é gravada

- Cada venda recebe um **número único** na primeira tentativa. Se a internet ou o Google falharem, o carrinho continua na tela e a nova tentativa usa **o mesmo número**: a planilha não aceita duas vezes a mesma venda.
- A ponte grava os itens e a venda **numa única chamada**, com trava (LockService), para as duas lojas não se atropelarem. Se a venda já existir, ela não grava de novo. Itens que já estavam lá também não são repetidos.
- A tela só diz **"Venda concluída"** depois que a planilha confirma.
- **Limite honesto:** o Google Planilhas não tem transação de verdade (tudo ou nada). Se o Google cair exatamente entre gravar os itens e gravar a venda, ficam itens sem venda. Esses itens **não contam** no estoque nem nos relatórios, e a nova tentativa, com o mesmo número, completa a venda.

## A planilha

As cinco abas (Produtos, Vendas, Itens, Entradas e Caixa) e a ordem das colunas **não mudaram**. Não apague e não mude a ordem das colunas. Filtrar e copiar pode à vontade.

O estoque é calculado assim: Entradas (inclusive acertos) menos os Itens das vendas que não foram canceladas. Venda cancelada devolve as peças ao estoque.

## Logomarca nova

Quando chegar a logomarca do app:
1. Troque o `logo.png` por ela (PNG quadrado, de preferência 1024 × 1024).
2. Rode `python ferramentas/gerar_marca.py`.
3. Suba a pasta `marca` de novo.

Os arquivos são reduzidos sem distorcer a imagem.
