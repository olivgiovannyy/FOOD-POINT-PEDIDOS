# FoodPoint — Pedidos e fechamento

Projeto independente para testar **tela de pedidos + API Python + fechamento do expediente**.
Não está conectado aos repositórios `FaelzXit/FoodPoint` ou `FaelzXit/POO-FoodPoint`.
Nenhum arquivo desses repositórios foi alterado. Esta versão web é separada do exemplo
anterior que funcionava pelo terminal.

## Aparência

Paleta baseada na referência enviada: laranja `#EA5B1D`, fundo pêssego
`#FFEEE6` e cartões brancos. Toda a interface usa Arial, com alternativas
Helvetica e sans-serif quando Arial não estiver instalada.

## Rodar no Windows / VS Code

É necessário Python 3.10 ou superior.

1. Extraia o ZIP e abra a pasta `foodpoint-pedidos` no VS Code.
2. Abra **Terminal > Novo Terminal** nessa pasta.
3. Instale a dependência:

```bash
python -m pip install -r requirements.txt
```

4. Inicie o servidor:

```bash
python app.py
```

5. Abra **http://127.0.0.1:5000** no navegador.

Se `python` não funcionar no Windows, use `py` nos dois comandos. Mantenha o terminal
aberto durante o uso. Para encerrar, pressione Ctrl+C. Não abra o HTML diretamente
nem pelo Live Server: a tela depende do servidor Python.

O banco `foodpoint_demo.db` é criado automaticamente na pasta do projeto. Os pedidos
continuam salvos após reiniciar o servidor. O banco não vem preenchido no ZIP.
Se a porta 5000 estiver ocupada, encerre a outra aplicação ou altere `port=5000`
na última linha de `app.py` e use o novo endereço no navegador.

## Teste em cinco minutos

1. Clique nos favoritos **Hambúrguer**, **Batata** e **Refrigerante**.
2. O carrinho mostra **R$ 45,00**. Você também pode informar qualquer produto,
   quantidade e preço manualmente e clicar em **Adicionar ao pedido**.
3. Clique em **Enviar pedido**. O Python valida e salva os itens. Só após a
   confirmação o carrinho é limpo. O pedido aparece como **Recebido**.
4. Clique em **Avançar → Preparo**, depois **Entrega** e depois **Concluído**.
5. O resumo mostra 1 pedido concluído e valor concluído de R$ 45,00.
6. Clique em **Fechar expediente** e confirme. O fechamento fica salvo.
7. Atualize a página ou reinicie o servidor: o resumo permanece fechado.

Os tempos são medidos de verdade. Se avançar tudo rapidamente, os tempos serão
próximos de zero e pode não aparecer nenhum gargalo. Para experimentar um gargalo,
antes de iniciar um dia de teste, reduza temporariamente `Preparo` em `LIMITES`
no `app.py` para `0.1` (6 segundos), reinicie o servidor e deixe um pedido nessa
etapa por mais de 6 segundos. Restaure o limite quando terminar. Um fechamento já
salvo não muda quando os limites são alterados.

**Depois de fechar hoje, o sistema bloqueia novos pedidos hoje.** Para repetir a
demonstração do zero, pare o servidor e apague **somente `foodpoint_demo.db` desta
pasta**. Isso elimina todos os pedidos e fechamentos desta demonstração. Não há
botão de reabertura nesta versão. Não use o banco do projeto do seu amigo aqui.

## O que cada arquivo faz

| Arquivo | Responsabilidade |
| --- | --- |
| `app.py` | Servidor Flask, validação, SQLite, rotas e cálculo dos indicadores |
| `templates/index.html` | Estrutura da tela |
| `static/style.css` | Aparência e adaptação ao celular |
| `static/app.js` | Carrinho, envio JSON e atualização da tela |
| `test_app.py` | Testes automáticos com banco temporário |
| `requirements.txt` | Dependência Flask |
| `.gitignore` | Evita enviar banco, ambiente e arquivos temporários ao Git |

O código foi organizado em funções pequenas, com nomes em português. Não há
framework de JavaScript nem ferramentas de compilação.

## Regras do expediente

- Pedidos novos recebem a data atual **do computador que executa o Python**.
  O seletor de data consulta pedidos e fechamento; não retroage novos pedidos.
- Horários são gravados em UTC e exibidos no horário do navegador.
- O pedido percorre Recebido → Preparo → Entrega → Concluído, uma etapa por vez.
  Pedidos ainda em andamento também podem ser cancelados.
- Cada transição registra o horário no histórico. Concluídos e cancelados não
  podem ser reabertos nem editados nesta demonstração.
- O total é recalculado no servidor com preços convertidos em centavos inteiros.
  Não existe processamento de pagamento. **Valor concluído não comprova recebimento.**
- O tempo médio de atendimento inclui somente pedidos concluídos: da criação
  à conclusão. Se não houver concluídos, a tela mostra um traço.
- Médias por etapa incluem os trechos já percorridos e o tempo decorrido na etapa
  atual dos pedidos não cancelados. Etapas ainda não iniciadas não entram na média.
- Limites ilustrativos: Recebido 10 min, Preparo 20 min e Entrega 15 min.
- Possível gargalo: média da etapa estritamente maior que seu limite.
- Pedido atrasado: ultrapassou o limite em pelo menos uma etapa. Cada pedido é
  contado uma vez, mesmo que atrase em várias. Não inclui cancelados.
- Fechar exige que todos os pedidos da data estejam concluídos ou cancelados.
  O sistema permite fechar um dia sem pedidos. Não permite fechar datas futuras.
- Fechamento salva uma fotografia dos indicadores. Repetir a chamada retorna o
  mesmo fechamento; não cria uma segunda cópia. Mudanças nessa data são bloqueadas.
- Um pedido que atravessa a meia-noite continua ligado à data em que foi criado.
  Ele deve ser encerrado para fechar aquele expediente.
- O painel consulta a API a cada 15 segundos e também após as ações.

## API para integrar depois

A tela já envia e recebe JSON pela API local. **O envio atual é para este próprio
servidor**, não para o site do seu amigo. Não há sincronização automática entre os
projetos. A integração futura deverá buscar estes dados ou encaminhá-los ao backend dele.

| Método | Endpoint | Função |
| --- | --- | --- |
| GET | `/api/config` | Data atual do servidor e limites |
| POST | `/api/pedidos` | Criar pedido |
| GET | `/api/pedidos?data=2026-10-23` | Consultar pedidos da data |
| PATCH | `/api/pedidos/1/etapa` | Avançar ou cancelar pedido |
| GET | `/api/fechamentos/2026-10-23` | Prévia ou fechamento salvo |
| POST | `/api/fechamentos/2026-10-23` | Fechar expediente |

### Enviar um pedido

Corpo de `POST /api/pedidos`, com `Content-Type: application/json`:

```json
{
  "chave": "exemplo-pedido-001",
  "itens": [
    {"nome": "Hambúrguer", "quantidade": 1, "preco": "25.00"},
    {"nome": "Batata", "quantidade": 1, "preco": "12.00"},
    {"nome": "Refrigerante", "quantidade": 1, "preco": "8.00"}
  ]
}
```

O servidor retorna o pedido completo, seu `id`, `data`, `etapa`, `historico`, itens
e `total_centavos: 4500`. Preços enviados usam ponto decimal. A resposta retorna
preços e subtotais em centavos. Quantidade deve ser um inteiro de 1 a 999.

A `chave` deve ser única por pedido, com 8 a 100 caracteres. Reenvie **a mesma chave
e os mesmos itens** se a conexão falhar: o servidor devolve o pedido existente sem
duplicar. Uma chave repetida com outros itens retorna conflito. A interface gera
essa chave automaticamente e a preserva nas tentativas enquanto o carrinho não
for modificado. Não recarregue a página após uma falha sem conferir a lista de pedidos.

Exemplo de consumo em JavaScript, executado na mesma origem da API:

```javascript
const resposta = await fetch('/api/pedidos?data=2026-10-23');
const pedidos = await resposta.json();
console.log(pedidos);
```

Para avançar, envie `{"etapa": "Preparo"}` ao endpoint PATCH. Depois use `Entrega`
e `Concluído`. Para cancelar um pedido pendente, envie `{"etapa": "Cancelado"}`.

Códigos: 201 = criado; 200 = sucesso ou reenvio já registrado; 400 = entrada inválida;
404 = pedido inexistente; 409 = conflito, expediente fechado ou pedidos pendentes;
413 = corpo muito grande. Erros de validação retornam `{"erro": "mensagem"}`.

### O que combinar com seu amigo

1. Onde a API vai rodar e qual endereço o outro backend vai acessar.
2. Como mapear `itens`, quantidades, centavos e etapas para as tabelas dele.
3. Qual sistema será responsável por registrar as mudanças de etapa.
4. Qual data/fuso e limites o grupo adotará.

Python e JavaScript conseguem ler o mesmo JSON. Para chamadas de outro backend
Python, basta uma requisição HTTP ao endereço desta API. Para chamadas de um
navegador hospedado em outra origem, será necessário configurar uma origem CORS
específica ou um proxy no backend. CORS aberto não está habilitado nesta versão.
`127.0.0.1` aponta para a própria máquina, não para o computador do seu amigo.

Esta é uma demonstração **local**, sem login, autorização ou serviço de pagamento.
O servidor só escuta `127.0.0.1`. Antes de publicar para uso real, será necessário
adicionar autenticação, autorização e uma implantação adequada. Não é um site
hospedado pelo GitHub Pages: a parte Python precisa continuar rodando em um servidor.

## Verificar os testes

```bash
python -m unittest -v
```

Os testes verificam valores, entradas inválidas, proteção contra reenvio, sequência
das etapas, tempos, gargalos, cancelamento, filtros por data, persistência do
fechamento e bloqueio de alterações. Usam somente bancos temporários.

## Subir em commits separados

Você pode organizar os arquivos em commits por assunto no mesmo repositório.
Não precisa criar cinco cópias do projeto. Uma sequência possível:

```bash
git init
git add .gitignore requirements.txt
git commit -m "Configura dependencias e arquivos ignorados"
git add app.py
git commit -m "Implementa API de pedidos e fechamento com SQLite"
git add templates/index.html static/style.css
git commit -m "Cria interface de pedidos e resumo do expediente"
git add static/app.js
git commit -m "Conecta interface a API e adiciona carrinho"
git add test_app.py README.md
git commit -m "Adiciona testes e documentacao de uso"
```

Se estiver em um repositório existente, não é necessário executar `git init`.
Essa divisão organiza a entrega pronta; para documentar evolução, registre também
suas mudanças e verificações conforme for estudando e adaptando o projeto.
