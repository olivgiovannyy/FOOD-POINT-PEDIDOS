"""Aplicação local independente: pedidos, API JSON e fechamento."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)
app.config['DATABASE'] = os.environ.get('FOODPOINT_DB', str(Path(__file__).with_name('foodpoint_demo.db')))
app.config['MAX_CONTENT_LENGTH'] = 100_000
ETAPAS = ['Recebido', 'Preparo', 'Entrega', 'Concluído']
LIMITES = {'Recebido': 10, 'Preparo': 20, 'Entrega': 15}


def agora():
    return datetime.now(timezone.utc)


def dia_atual():
    # O expediente segue o calendário local da máquina que executa o servidor.
    return datetime.now().date().isoformat()


def banco():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def desconectar(erro):
    if 'db' in g:
        g.pop('db').close()


def criar_tabelas():
    banco().executescript('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL, data TEXT NOT NULL,
            itens TEXT NOT NULL, total_centavos INTEGER NOT NULL,
            etapa TEXT NOT NULL, criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL, historico TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fechamentos (
            data TEXT PRIMARY KEY, resumo TEXT NOT NULL
        );
    ''')


def validar_data(valor):
    try:
        data = datetime.strptime(valor, '%Y-%m-%d').date().isoformat()
        if data != valor:
            raise ValueError()
        return data
    except (ValueError, TypeError):
        raise ValueError('Informe a data no formato AAAA-MM-DD.')


def dados_json():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise ValueError('Envie um objeto JSON válido.')
    return dados


def validar_itens(itens):
    if not isinstance(itens, list) or not 1 <= len(itens) <= 100:
        raise ValueError('Envie de 1 a 100 itens.')
    resultado = []
    for item in itens:
        if not isinstance(item, dict):
            raise ValueError('Item inválido.')
        nome = item.get('nome', '')
        quantidade = item.get('quantidade')
        if not isinstance(nome, str) or not 1 <= len(nome.strip()) <= 80:
            raise ValueError('O produto deve ter um nome de até 80 caracteres.')
        if type(quantidade) is not int or not 1 <= quantidade <= 999:
            raise ValueError('Quantidade deve ser um inteiro de 1 a 999.')
        try:
            preco = Decimal(str(item.get('preco', '')))
            if not preco.is_finite() or not Decimal('0.01') <= preco <= Decimal('99999.99'):
                raise ValueError()
            if preco * 100 != (preco * 100).to_integral_value():
                raise ValueError()
        except (InvalidOperation, ValueError):
            raise ValueError('Preço deve ser positivo e ter no máximo duas casas decimais.')
        centavos = int(preco * 100)
        resultado.append({'nome': nome.strip(), 'quantidade': quantidade,
                          'preco_centavos': centavos, 'subtotal_centavos': centavos * quantidade})
    return resultado


def pedido_json(linha):
    pedido = dict(linha)
    pedido['itens'] = json.loads(pedido['itens'])
    pedido['historico'] = json.loads(pedido['historico'])
    return pedido


def calcular_resumo(data):
    pedidos = [pedido_json(p) for p in banco().execute('SELECT * FROM pedidos WHERE data = ? ORDER BY id', (data,))]
    amostras = {etapa: [] for etapa in LIMITES}
    atrasados = set()
    concluidos = []
    instante = agora()
    for pedido in pedidos:
        if pedido['etapa'] == 'Cancelado':
            continue
        historico = pedido['historico']
        for indice, evento in enumerate(historico):
            etapa = evento['etapa']
            if etapa not in LIMITES:
                continue
            inicio = datetime.fromisoformat(evento['em'])
            fim = datetime.fromisoformat(historico[indice + 1]['em']) if indice + 1 < len(historico) else instante
            minutos = max(0, (fim - inicio).total_seconds() / 60)
            amostras[etapa].append(minutos)
            if minutos > LIMITES[etapa]:
                atrasados.add(pedido['id'])
        if pedido['etapa'] == 'Concluído':
            duracao = (datetime.fromisoformat(pedido['atualizado_em']) - datetime.fromisoformat(pedido['criado_em'])).total_seconds() / 60
            concluidos.append(max(0, duracao))
    etapas = []
    for etapa, tempos in amostras.items():
        media = sum(tempos) / len(tempos) if tempos else None
        etapas.append({'etapa': etapa, 'amostras': len(tempos),
                       'media_minutos': round(media, 2) if media is not None else None,
                       'limite_minutos': LIMITES[etapa],
                       'gargalo': media is not None and media > LIMITES[etapa]})
    return {'data': data, 'fechado_em': None, 'total_pedidos': len(pedidos),
            'concluidos': len(concluidos),
            'cancelados': sum(p['etapa'] == 'Cancelado' for p in pedidos),
            'pendentes': sum(p['etapa'] not in ('Concluído', 'Cancelado') for p in pedidos),
            'valor_concluido_centavos': sum(p['total_centavos'] for p in pedidos if p['etapa'] == 'Concluído'),
            'valor_pendente_centavos': sum(p['total_centavos'] for p in pedidos if p['etapa'] not in ('Concluído', 'Cancelado')),
            'tempo_medio_minutos': round(sum(concluidos) / len(concluidos), 2) if concluidos else None,
            'pedidos_atrasados': len(atrasados), 'ids_atrasados': sorted(atrasados),
            'etapas': etapas, 'gargalos': [e['etapa'] for e in etapas if e['gargalo']]}


@app.errorhandler(ValueError)
def erro_validacao(erro):
    return jsonify(erro=str(erro)), 400


@app.errorhandler(413)
def erro_tamanho(erro):
    return jsonify(erro='Pedido muito grande.'), 413


@app.get('/')
def inicio():
    return render_template('index.html')


@app.get('/api/config')
def configuracao():
    return jsonify(data_atual=dia_atual(), limites=LIMITES)


@app.get('/api/pedidos')
def listar_pedidos():
    data = validar_data(request.args.get('data', dia_atual()))
    pedidos = banco().execute('SELECT * FROM pedidos WHERE data = ? ORDER BY id DESC', (data,)).fetchall()
    return jsonify([pedido_json(p) for p in pedidos])


@app.post('/api/pedidos')
def enviar_pedido():
    dados = dados_json()
    itens = validar_itens(dados.get('itens'))
    chave = dados.get('chave')
    if not isinstance(chave, str) or not 8 <= len(chave) <= 100:
        raise ValueError('Envie uma chave única de 8 a 100 caracteres para evitar pedidos duplicados.')
    db = banco()
    with db:
        db.execute('BEGIN IMMEDIATE')
        anterior = db.execute('SELECT * FROM pedidos WHERE chave = ?', (chave,)).fetchone()
        if anterior:
            if json.loads(anterior['itens']) != itens:
                return jsonify(erro='Esta chave já foi usada em outro pedido.'), 409
            return jsonify(pedido_json(anterior)), 200
        data = dia_atual()
        if db.execute('SELECT 1 FROM fechamentos WHERE data = ?', (data,)).fetchone():
            return jsonify(erro='O expediente de hoje já foi fechado.'), 409
        horario = agora().isoformat()
        historico = [{'etapa': 'Recebido', 'em': horario}]
        cursor = db.execute('''INSERT INTO pedidos
            (chave, data, itens, total_centavos, etapa, criado_em, atualizado_em, historico)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (chave, data, json.dumps(itens, ensure_ascii=False), sum(i['subtotal_centavos'] for i in itens),
             'Recebido', horario, horario, json.dumps(historico)))
        pedido = db.execute('SELECT * FROM pedidos WHERE id = ?', (cursor.lastrowid,)).fetchone()
    return jsonify(pedido_json(pedido)), 201


@app.patch('/api/pedidos/<int:id_pedido>/etapa')
def mudar_etapa(id_pedido):
    dados = dados_json()
    nova = dados.get('etapa')
    db = banco()
    with db:
        db.execute('BEGIN IMMEDIATE')
        linha = db.execute('SELECT * FROM pedidos WHERE id = ?', (id_pedido,)).fetchone()
        if not linha:
            return jsonify(erro='Pedido não encontrado.'), 404
        pedido = pedido_json(linha)
        if db.execute('SELECT 1 FROM fechamentos WHERE data = ?', (pedido['data'],)).fetchone():
            return jsonify(erro='Expediente fechado: pedido não pode ser alterado.'), 409
        if nova == pedido['etapa']:
            return jsonify(pedido)
        if pedido['etapa'] in ('Concluído', 'Cancelado'):
            return jsonify(erro='O pedido já foi encerrado.'), 409
        proxima = ETAPAS[ETAPAS.index(pedido['etapa']) + 1]
        if nova not in (proxima, 'Cancelado'):
            raise ValueError('Avance uma etapa por vez ou cancele o pedido.')
        horario = agora().isoformat()
        pedido['historico'].append({'etapa': nova, 'em': horario})
        db.execute('UPDATE pedidos SET etapa = ?, atualizado_em = ?, historico = ? WHERE id = ?',
                   (nova, horario, json.dumps(pedido['historico'], ensure_ascii=False), id_pedido))
        pedido = pedido_json(db.execute('SELECT * FROM pedidos WHERE id = ?', (id_pedido,)).fetchone())
    return jsonify(pedido)


@app.route('/api/fechamentos/<data>', methods=['GET', 'POST'])
def fechamento(data):
    data = validar_data(data)
    if data > dia_atual():
        raise ValueError('Não é possível consultar ou fechar um expediente futuro.')
    db = banco()
    with db:
        db.execute('BEGIN IMMEDIATE')
        salvo = db.execute('SELECT resumo FROM fechamentos WHERE data = ?', (data,)).fetchone()
        if salvo:
            return jsonify(json.loads(salvo['resumo']))
        resumo = calcular_resumo(data)
        if request.method == 'POST':
            if resumo['pendentes']:
                return jsonify(erro='Conclua ou cancele os pedidos pendentes antes de fechar.'), 409
            resumo['fechado_em'] = agora().isoformat()
            db.execute('INSERT INTO fechamentos (data, resumo) VALUES (?, ?)',
                       (data, json.dumps(resumo, ensure_ascii=False)))
    return jsonify(resumo)


with app.app_context():
    criar_tabelas()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
