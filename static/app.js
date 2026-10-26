// A tela conversa com o Python usando fetch e JSON.
const $ = id => document.getElementById(id);
const dinheiro = centavos => (centavos / 100).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
let carrinho = [];
let chave = null;
let enviando = false;
let carregamento = 0;
let diaServidor = '';

function mensagem(texto, erro = false) {
  $('mensagem').textContent = texto;
  $('mensagem').className = erro ? 'erro' : '';
}
function elemento(tag, texto, classe) {
  const el = document.createElement(tag);
  if (texto !== undefined) el.textContent = texto;
  if (classe) el.className = classe;
  return el;
}
async function api(url, metodo = 'GET', dados) {
  const resposta = await fetch(url, {
    method: metodo,
    headers: {'Content-Type': 'application/json'},
    body: dados === undefined ? undefined : JSON.stringify(dados)
  });
  const conteudo = await resposta.json();
  if (!resposta.ok) throw new Error(conteudo.erro || 'Não foi possível completar a operação.');
  return conteudo;
}
function desenharCarrinho() {
  $('carrinho').replaceChildren();
  if (!carrinho.length) $('carrinho').append(elemento('p', 'Seu pedido começa aqui. Adicione um produto acima.', 'vazio'));
  carrinho.forEach((item, indice) => {
    const linha = elemento('div', undefined, 'item');
    const info = elemento('div');
    info.append(elemento('strong', item.nome), elemento('small', `${item.quantidade} × ${dinheiro(item.centavos)}`));
    const remover = elemento('button', 'Remover', 'remover');
    remover.type = 'button';
    remover.disabled = enviando;
    remover.onclick = () => {carrinho.splice(indice, 1); chave = null; desenharCarrinho();};
    linha.append(info, elemento('b', dinheiro(item.centavos * item.quantidade)), remover);
    $('carrinho').append(linha);
  });
  $('total').textContent = dinheiro(carrinho.reduce((soma, item) => soma + item.centavos * item.quantidade, 0));
  $('enviar').disabled = enviando || !carrinho.length;
}
function adicionar(nome, quantidade, centavos) {
  if (enviando) return;
  if (carrinho.length >= 100) return mensagem('Limite de 100 itens por pedido.', true);
  carrinho.push({nome, quantidade, centavos});
  chave = null;
  desenharCarrinho();
}
$('item-form').onsubmit = evento => {
  evento.preventDefault();
  const nome = $('nome').value.trim();
  const quantidade = Number($('quantidade').value);
  const preco = Number($('preco').value);
  if (!nome || !Number.isInteger(quantidade) || quantidade < 1 || quantidade > 999 || !Number.isFinite(preco) || preco <= 0 || preco > 99999.99) {
    return mensagem('Confira o nome, a quantidade e o preço.', true);
  }
  adicionar(nome, quantidade, Math.round(preco * 100));
  $('item-form').reset();
  $('nome').focus();
};
document.querySelectorAll('[data-nome]').forEach(botao => {
  botao.onclick = () => adicionar(botao.dataset.nome, 1, Math.round(Number(botao.dataset.preco) * 100));
});
$('enviar').onclick = async () => {
  if (enviando || !carrinho.length) return;
  enviando = true;
  chave = chave || crypto.randomUUID();
  document.querySelectorAll('#item-form input, #item-form button, .favoritos button').forEach(el => el.disabled = true);
  desenharCarrinho();
  $('enviar').textContent = 'Enviando…';
  try {
    const pedido = await api('/api/pedidos', 'POST', {
      chave,
      itens: carrinho.map(item => ({nome: item.nome, quantidade: item.quantidade, preco: (item.centavos / 100).toFixed(2)}))
    });
    carrinho = [];
    chave = null;
    $('item-form').reset();
    $('dia').value = pedido.data;
    mensagem(`Pedido #${pedido.id} recebido! Total: ${dinheiro(pedido.total_centavos)}.`);
    await atualizar();
  } catch (erro) {
    mensagem(`${erro.message} O pedido foi mantido na tela; tente enviar novamente.`, true);
  } finally {
    enviando = false;
    document.querySelectorAll('#item-form input, #item-form button, .favoritos button').forEach(el => el.disabled = false);
    $('enviar').textContent = 'Enviar pedido →';
    desenharCarrinho();
  }
};
async function alterar(id, etapa, botao) {
  if (etapa === 'Cancelado' && !confirm(`Cancelar o pedido #${id}?`)) return;
  botao.disabled = true;
  try {
    await api(`/api/pedidos/${id}/etapa`, 'PATCH', {etapa});
    mensagem(`Pedido #${id}: ${etapa}.`);
    await atualizar();
  } catch (erro) {mensagem(erro.message, true);}
  finally {botao.disabled = false;}
}
function desenharPedidos(pedidos, fechado) {
  $('pedidos').replaceChildren();
  if (!pedidos.length) $('pedidos').append(elemento('div', 'Nenhum pedido nesta data. Envie o primeiro pedido pelo formulário.', 'vazio'));
  const proximas = {Recebido: 'Preparo', Preparo: 'Entrega', Entrega: 'Concluído'};
  pedidos.forEach(pedido => {
    const card = elemento('article', undefined, 'pedido');
    const topo = elemento('div', undefined, 'pedido-topo');
    topo.append(elemento('strong', `#${pedido.id} · ${dinheiro(pedido.total_centavos)}`), elemento('span', pedido.etapa, 'badge'));
    card.append(topo, elemento('p', pedido.itens.map(i => `${i.quantidade}× ${i.nome}`).join(' · ')));
    const hora = new Date(pedido.criado_em).toLocaleTimeString('pt-BR');
    card.append(elemento('p', `Recebido às ${hora}`));
    if (proximas[pedido.etapa] && !fechado) {
      const acoes = elemento('div', undefined, 'acoes');
      const avancar = elemento('button', `Avançar → ${proximas[pedido.etapa]}`);
      avancar.onclick = () => alterar(pedido.id, proximas[pedido.etapa], avancar);
      const cancelar = elemento('button', 'Cancelar', 'cancelar');
      cancelar.onclick = () => alterar(pedido.id, 'Cancelado', cancelar);
      acoes.append(avancar, cancelar);
      card.append(acoes);
    }
    $('pedidos').append(card);
  });
}
function desenharResumo(resumo) {
  $('situacao').textContent = resumo.fechado_em ? `Fechado em ${new Date(resumo.fechado_em).toLocaleString('pt-BR')}` : 'Expediente aberto · prévia atualizada a cada 15 segundos';
  $('indicadores').replaceChildren();
  const itens = [
    ['Pedidos do dia', resumo.total_pedidos], ['Concluídos', resumo.concluidos],
    ['Valor concluído', dinheiro(resumo.valor_concluido_centavos)], ['Pendentes', resumo.pendentes],
    ['Cancelados', resumo.cancelados], ['Tempo médio', resumo.tempo_medio_minutos === null ? '—' : `${resumo.tempo_medio_minutos} min`]
  ];
  itens.forEach(([nome, valor]) => {
    const card = elemento('div', undefined, 'indicador');
    card.append(elemento('span', nome), elemento('strong', valor));
    $('indicadores').append(card);
  });
  $('etapas').replaceChildren();
  resumo.etapas.forEach(etapa => {
    const linha = elemento('div', undefined, 'etapa');
    const media = etapa.media_minutos === null ? 'Sem dados' : `${etapa.media_minutos} min`;
    linha.append(elemento('span', etapa.etapa), elemento('span', `${media} · limite ${etapa.limite_minutos} min`));
    $('etapas').append(linha);
  });
  $('gargalos').textContent = `${resumo.pedidos_atrasados} pedido(s) ultrapassaram o limite de alguma etapa. Possíveis gargalos: ${resumo.gargalos.join(', ') || 'nenhum'}.`;
  $('fechar').disabled = Boolean(resumo.fechado_em) || resumo.pendentes > 0;
  $('fechar').textContent = resumo.fechado_em ? 'Expediente fechado ✓' : 'Fechar expediente';
}
async function atualizar() {
  const numero = ++carregamento;
  const data = $('dia').value;
  if (!data) return;
  try {
    const [pedidos, resumo] = await Promise.all([api(`/api/pedidos?data=${data}`), api(`/api/fechamentos/${data}`)]);
    if (numero !== carregamento) return;
    desenharPedidos(pedidos, Boolean(resumo.fechado_em));
    desenharResumo(resumo);
  } catch (erro) {
    if (numero !== carregamento) return;
    $('fechar').disabled = true;
    mensagem(`Não foi possível atualizar os dados: ${erro.message}`, true);
  }
}
$('fechar').onclick = async () => {
  const data = $('dia').value;
  if (!confirm(`Fechar o expediente de ${data}? O resumo ficará salvo e os pedidos dessa data não poderão ser alterados.`)) return;
  $('fechar').disabled = true;
  try {
    await api(`/api/fechamentos/${data}`, 'POST');
    mensagem(`Expediente de ${data} fechado e salvo.`);
    await atualizar();
  } catch (erro) {mensagem(erro.message, true); await atualizar();}
};
$('dia').onchange = atualizar;
$('atualizar').onclick = atualizar;
async function iniciar() {
  desenharCarrinho();
  try {
    const config = await api('/api/config');
    diaServidor = config.data_atual;
    $('dia').value = diaServidor;
    $('dia').max = diaServidor;
    await atualizar();
    setInterval(atualizar, 15000);
  } catch (erro) {mensagem(`Não foi possível conectar ao servidor: ${erro.message}`, true);}
}
iniciar();
