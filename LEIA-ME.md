# Caixa Jardim do Éden — Streamlit

Sistema de caixa no navegador, com login. As vendas ficam gravadas numa **planilha do Google**, então as duas lojas usam a mesma planilha.

## O que tem no app
- **Login:** toque na loja (Aterrado ou Vila Santa Cecília) e digite a senha. A senha fica nos *Secrets* (ou como código embaralhado no app), nunca escrita às claras.
  O login **continua valendo por 14 horas mesmo se recarregar a página**. Para isso, o app guarda uma chave no endereço da página.
  Dica: entre uma vez em cada loja e salve a página nos favoritos. O favorito já abre na loja certa.
- **Vendedor(a):** escolhido em cada venda (Raphael, Daiane, Norma, Outros). Os indicadores saem por loja e "Tudo junto".
- **🏠 Hoje** (tela inicial): quanto vendeu hoje e a comparação com ontem, a situação do caixa, os botões rápidos, as vendas por forma de pagamento e por vendedor(a), e o que precisa repor.
- **💰 Caixa:** abrir o caixa com o troco, registrar sangria (dinheiro que saiu) e reforço (dinheiro que entrou), e fechar contando a gaveta. O app diz se **sobrou ou faltou dinheiro** e monta o **resumo do dia para mandar no WhatsApp**.
- **Vender:** procure pelo leitor de código de barras, pelo nome ou pelo valor. Por exemplo, digite `189` para ver os produtos de R$ 189,xx; se só houver um, ele já entra na venda. Na hora de fechar, é obrigatório escolher quem vendeu (Raphael, Daiane, Norma, Outros) e a forma de pagamento (Dinheiro com troco, Pix, Crédito, Débito). O desconto pode ser em R$ ou em %. Depois da venda, um botão manda o **comprovante pelo WhatsApp** para a cliente. O **custo não aparece** nessa tela.
- **Estoque:** separado por loja. Tem "Chegou mercadoria" e "Contagem" para acertar o estoque.
- **Produtos:** edite preço, custo e código direto na tabela. Tem o botão "Aplicar a regra" (custo × 5, final 9,99) e o cadastro de produto novo.
- **Vendas:** lista das vendas feitas, com os itens de cada uma e a opção de cancelar.
- **Painel:** período pronto ou **datas escolhidas**, filtro por loja e por vendedor(a), comparação com o período anterior, **Destaques** (melhor dia, horário mais forte, forma mais usada, quem mais vendeu, produto campeão), gráficos com valor exato ao tocar e download em Excel. Valores muito grandes aparecem abreviados (R$ 1,25 Mi) e o valor exato fica no (?) e nas tabelas.
- **Proteções:** sem planilha ligada o app não abre na nuvem; se o Google oscilar ele tenta de novo sozinho; se mesmo assim não gravar, aparece em vermelho "Isto NÃO foi salvo".

## A planilha
O app cria 5 abas na planilha:
| Aba | O que guarda |
|---|---|
| **Produtos** | id, nome, código, custo, preço, ativo |
| **Vendas** | uma linha por venda: data, loja, vendedor, forma, total, troco, status |
| **Itens** | os produtos de cada venda |
| **Entradas** | mercadoria que chegou e acertos de estoque |
| **Caixa** | abertura, sangria, reforço e fechamento de cada loja |

Na primeira vez que o app abrir, a aba Produtos recebe os **247 produtos** automaticamente.
O estoque é a soma das Entradas menos o que foi vendido, e é calculado sozinho.

> Não apague nem mude a ordem das colunas na planilha. Pode filtrar e copiar à vontade.

---

## Passo a passo para colocar online (grátis)

### 1. Criar a planilha
1. Acesse **sheets.google.com** e crie uma planilha em branco chamada `Caixa Jardim do Éden`.
2. Copie o endereço dela na barra do navegador (`https://docs.google.com/spreadsheets/d/.../edit`).

### 2. Criar a "conta de serviço" (é o login que o app usa para gravar na planilha)
1. Acesse **console.cloud.google.com** e crie um projeto, por exemplo `jardim-do-eden`.
2. Em **APIs e serviços → Biblioteca**, ative a **Google Sheets API** e a **Google Drive API**.
3. Em **APIs e serviços → Credenciais**, clique em **Criar credenciais → Conta de serviço**, dê um nome e conclua.
4. Clique na conta criada, vá em **Chaves → Adicionar chave → Criar nova chave → JSON**. Um arquivo `.json` será baixado.
5. Abra o `.json` e copie o e-mail que aparece em `client_email` (termina em `iam.gserviceaccount.com`).
6. Volte à planilha, clique em **Compartilhar**, cole esse e-mail e dê permissão de **Editor**.

### 3. Subir o código no GitHub
1. Crie uma conta em **github.com** e um repositório novo, de preferência **privado**, chamado `caixa-jardim`.
2. Clique em **Add file → Upload files** e envie: `app.py`, `requirements.txt`, `produtos_iniciais.csv`, `logo.png` e a pasta `.streamlit` com o `config.toml`.
   **Não envie** o `secrets.toml` nem o arquivo `.json`.

### 4. Publicar no Streamlit Community Cloud
1. Acesse **share.streamlit.io** e entre com a conta do GitHub.
2. Clique em **Create app**, escolha o repositório `caixa-jardim` e o arquivo `app.py`. Se quiser, escolha um endereço, por exemplo `jardim-do-eden.streamlit.app`.
3. Antes de publicar, abra **Advanced settings → Secrets** e cole o conteúdo de `.streamlit/secrets.toml.exemplo` já preenchido:
   - o endereço da planilha;
   - os campos do arquivo `.json`, um por um. No `private_key`, copie o valor inteiro, com os `\n`.
4. Clique em **Deploy**. Em 1 a 2 minutos o app está no ar.
5. Entre numa loja com a senha, faça uma venda de teste e confira se ela apareceu nas abas **Vendas** e **Itens** da planilha.

### 5. Usar nas lojas
- Abra o endereço do app no computador ou celular de cada loja e escolha a loja no topo da tela.
- Leitor de código de barras USB: clique na caixa de busca e passe o produto. O leitor "digita" o código e aperta Enter sozinho.
- Para cadastrar o código de barras de um produto, vá em **Produtos**, coloque o código na coluna "Código" e clique em **Salvar**.

---

## Bom saber
- **O app "dorme"** se ficar uns dias sem uso. O primeiro acesso depois disso demora cerca de 30 segundos para acordar. Os dados não se perdem, porque estão na planilha.
- **Mais usuários:** em *Secrets*, acrescente linhas em `[usuarios]`, por exemplo `daiane = "senha-dela"`. Quem não estiver em `[papeis]` como `"dona"` entra como vendedora.
- **Sair** apaga o login daquele aparelho. Em computador que outras pessoas usam, clique em **Sair** no fim do dia.
- **Atualizar os dados:** quem está numa loja vê as vendas da outra em até 1 minuto. Para ver na hora, use o menu do usuário → **Atualizar dados**.
- **Testar no computador sem a planilha:** rode `pip install -r requirements.txt` e depois `streamlit run app.py`. Sem os Secrets, o app grava na pasta `dados/` e mostra o aviso "Modo de teste".
