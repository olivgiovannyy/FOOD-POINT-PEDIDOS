import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# Importa a aplicação com banco temporário: nunca toca nos pedidos do usuário.
IMPORT_DIR = tempfile.TemporaryDirectory()
os.environ['FOODPOINT_DB'] = os.path.join(IMPORT_DIR.name, 'import.db')
import app as sistema


class TesteFoodPoint(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        sistema.app.config.update(TESTING=True, DATABASE=os.path.join(self.pasta.name, 'teste.db'))
        with sistema.app.app_context():
            sistema.criar_tabelas()
        self.cliente = sistema.app.test_client()
        self.data = sistema.dia_atual()

    def tearDown(self):
        self.pasta.cleanup()

    def criar(self, chave='pedido-teste-1', itens=None):
        return self.cliente.post('/api/pedidos', json={'chave': chave, 'itens': itens or [
            {'nome': 'Hambúrguer', 'quantidade': 1, 'preco': '25.00'},
            {'nome': 'Batata', 'quantidade': 1, 'preco': '12.00'},
            {'nome': 'Refri', 'quantidade': 1, 'preco': '8.00'}]})

    def avancar(self, id, etapa):
        return self.cliente.patch(f'/api/pedidos/{id}/etapa', json={'etapa': etapa})

    def test_pedido_total_e_reenvio(self):
        primeiro = self.criar()
        self.assertEqual(primeiro.status_code, 201)
        self.assertEqual(primeiro.json['total_centavos'], 4500)
        segundo = self.criar()
        self.assertEqual(segundo.status_code, 200)
        self.assertEqual(primeiro.json['id'], segundo.json['id'])
        self.assertEqual(len(self.cliente.get('/api/pedidos').json), 1)
        conflito = self.criar(itens=[{'nome': 'Outro', 'quantidade': 1, 'preco': 1}])
        self.assertEqual(conflito.status_code, 409)

    def test_validacao(self):
        for item in [
            {'nome': 'X', 'quantidade': 1, 'preco': '-1'},
            {'nome': 'X', 'quantidade': True, 'preco': 1},
            {'nome': 'X', 'quantidade': 1, 'preco': 'NaN'},
            {'nome': 'X', 'quantidade': 1, 'preco': '1.001'},
            {'nome': ' ', 'quantidade': 1, 'preco': 1},
        ]:
            self.assertEqual(self.criar(itens=[item]).status_code, 400)
        self.assertEqual(self.cliente.post('/api/pedidos', json=[]).status_code, 400)
        self.assertEqual(self.cliente.get('/api/fechamentos/23-10-2026').status_code, 400)

    def test_tempo_gargalo_fechamento_e_bloqueio(self):
        inicio = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
        with patch('app.agora', return_value=inicio):
            id = self.criar().json['id']
        self.assertEqual(self.avancar(id, 'Entrega').status_code, 400)
        self.assertEqual(self.cliente.post('/api/fechamentos/' + self.data).status_code, 409)
        with patch('app.agora', return_value=inicio + timedelta(minutes=5)):
            self.avancar(id, 'Preparo')
        with patch('app.agora', return_value=inicio + timedelta(minutes=35)):
            self.avancar(id, 'Entrega')
        with patch('app.agora', return_value=inicio + timedelta(minutes=45)):
            self.avancar(id, 'Concluído')
        resposta = self.cliente.post('/api/fechamentos/' + self.data)
        self.assertEqual(resposta.status_code, 200)
        resumo = resposta.json
        self.assertEqual(resumo['tempo_medio_minutos'], 45)
        self.assertEqual(resumo['valor_concluido_centavos'], 4500)
        self.assertEqual(resumo['gargalos'], ['Preparo'])
        self.assertEqual(resumo['pedidos_atrasados'], 1)
        self.assertEqual(resumo, self.cliente.post('/api/fechamentos/' + self.data).json)
        self.assertEqual(self.criar('pedido-teste-2').status_code, 409)
        self.assertEqual(self.avancar(id, 'Cancelado').status_code, 409)
        self.assertEqual(self.cliente.get('/api/fechamentos/' + self.data).json, resumo)

    def test_cancelamento_dia_vazio_e_filtro(self):
        id = self.criar().json['id']
        self.assertEqual(self.avancar(id, 'Cancelado').status_code, 200)
        self.assertEqual(self.avancar(id, 'Preparo').status_code, 409)
        resumo = self.cliente.get('/api/fechamentos/' + self.data).json
        self.assertEqual(resumo['cancelados'], 1)
        self.assertEqual(resumo['valor_concluido_centavos'], 0)
        self.assertIsNone(resumo['tempo_medio_minutos'])
        self.assertEqual(self.cliente.get('/api/pedidos?data=2000-01-01').json, [])
        vazio = self.cliente.post('/api/fechamentos/2000-01-01')
        self.assertEqual(vazio.json['total_pedidos'], 0)
        self.assertIsNotNone(vazio.json['fechado_em'])
        self.assertEqual(self.avancar(999, 'Preparo').status_code, 404)

    def test_tela_e_assets(self):
        for caminho in ['/', '/static/style.css', '/static/app.js', '/api/config']:
            resposta = self.cliente.get(caminho)
            self.assertEqual(resposta.status_code, 200)
            resposta.close()


if __name__ == '__main__':
    unittest.main()
