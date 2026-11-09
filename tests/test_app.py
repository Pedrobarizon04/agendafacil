"""Testes automatizados do AgendaFácil.

Rodar com:  python -m unittest -v
"""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import app
from db import init_db


class AgendaFacilTeste(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=str(Path(self.pasta.name) / "teste.db"))
        init_db(app)  # banco novo com dados de exemplo
        self.cliente = app.test_client()
        self.cliente.post("/login", data={"email": "admin@agendafacil.com", "senha": "admin123"})

    def tearDown(self):
        self.pasta.cleanup()

    def test_login_obrigatorio(self):
        anonimo = app.test_client()
        resposta = anonimo.get("/clientes")
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login", resposta.headers["Location"])

    def test_login_com_senha_errada(self):
        anonimo = app.test_client()
        resposta = anonimo.post("/login", data={"email": "admin@agendafacil.com", "senha": "errada"})
        self.assertIn("E-mail ou senha inválidos", resposta.get_data(as_text=True))

    def test_crud_cliente(self):
        # Create
        self.cliente.post("/clientes/novo", data={"nome": "Teste Silva", "telefone": "4399", "email": ""})
        self.assertIn("Teste Silva", self.cliente.get("/clientes").get_data(as_text=True))
        # Update (cliente id 5, pois o banco de exemplo já tem 4)
        self.cliente.post("/clientes/5/editar", data={"nome": "Teste Souza", "telefone": "4399", "email": ""})
        html = self.cliente.get("/clientes?q=Teste").get_data(as_text=True)
        self.assertIn("Teste Souza", html)
        self.assertNotIn("Teste Silva", html)
        # Delete
        self.cliente.post("/clientes/5/excluir")
        self.assertNotIn("Teste Souza", self.cliente.get("/clientes").get_data(as_text=True))

    def test_nao_exclui_cliente_com_agendamento(self):
        resposta = self.cliente.post("/clientes/1/excluir", follow_redirects=True)
        self.assertIn("possui agendamentos vinculados", resposta.get_data(as_text=True))

    def test_crud_servico(self):
        self.cliente.post("/servicos/novo", data={"nome": "Sobrancelha", "descricao": "", "preco": "15", "duracao_min": "15"})
        self.assertIn("Sobrancelha", self.cliente.get("/servicos").get_data(as_text=True))
        self.cliente.post("/servicos/5/editar", data={"nome": "Sobrancelha", "descricao": "", "preco": "20", "duracao_min": "15"})
        self.assertIn("R$ 20,00", self.cliente.get("/servicos").get_data(as_text=True))
        self.cliente.post("/servicos/5/excluir")
        self.assertNotIn("Sobrancelha", self.cliente.get("/servicos").get_data(as_text=True))

    def test_crud_profissional(self):
        self.cliente.post("/profissionais/novo", data={"nome": "Bruno Teste", "especialidade": "", "telefone": "", "ativo": "on"})
        self.assertIn("Bruno Teste", self.cliente.get("/profissionais").get_data(as_text=True))
        self.cliente.post("/profissionais/3/editar", data={"nome": "Bruno Teste", "especialidade": "Barba", "telefone": ""})
        self.assertIn("Inativo", self.cliente.get("/profissionais").get_data(as_text=True))
        self.cliente.post("/profissionais/3/excluir")
        self.assertNotIn("Bruno Teste", self.cliente.get("/profissionais").get_data(as_text=True))

    def test_agendamento_e_conflito_de_horario(self):
        dia = (date.today() + timedelta(days=7)).isoformat()
        dados = {"cliente_id": "1", "profissional_id": "1", "servico_id": "3", "data_hora": f"{dia}T10:00"}
        r = self.cliente.post("/agendamentos/novo", data=dados, follow_redirects=True)
        self.assertIn("Agendamento criado", r.get_data(as_text=True))
        # Mesmo profissional às 10:30 conflita com o combo de 60 min das 10:00
        dados["data_hora"] = f"{dia}T10:30"
        r = self.cliente.post("/agendamentos/novo", data=dados, follow_redirects=True)
        self.assertIn("já tem um atendimento nesse horário", r.get_data(as_text=True))
        # Às 11:00 já está livre
        dados["data_hora"] = f"{dia}T11:00"
        r = self.cliente.post("/agendamentos/novo", data=dados, follow_redirects=True)
        self.assertIn("Agendamento criado", r.get_data(as_text=True))

    def test_nao_agenda_no_passado(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        dados = {"cliente_id": "1", "profissional_id": "1", "servico_id": "1", "data_hora": f"{ontem}T10:00"}
        r = self.cliente.post("/agendamentos/novo", data=dados)
        self.assertIn("já passou", r.get_data(as_text=True))

    def test_paginas_abrem(self):
        for url in ["/", "/agendamentos", "/agendamentos/novo", "/agendamentos/1/editar",
                    "/clientes/novo", "/clientes/1/editar", "/profissionais/novo",
                    "/servicos/novo", "/usuarios/novo"]:
            self.assertEqual(self.cliente.get(url).status_code, 200, url)


if __name__ == "__main__":
    unittest.main()
