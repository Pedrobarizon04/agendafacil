"""Conexão com o banco de dados SQLite e carga inicial de dados."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash

PASTA_BASE = Path(__file__).resolve().parent


def get_db():
    """Retorna a conexão do request atual (cria uma se ainda não existir)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row          # permite acessar colunas pelo nome
        g.db.execute("PRAGMA foreign_keys = ON")  # SQLite só aplica FKs com isso ligado
    return g.db


def close_db(_erro=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Cria as tabelas e, se o banco for novo, insere dados de exemplo."""
    caminho = Path(app.config["DATABASE"])
    banco_novo = not caminho.exists()
    caminho.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(caminho)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript((PASTA_BASE / "schema.sql").read_text(encoding="utf-8"))
        if banco_novo:
            _popular_exemplo(conn)
        conn.commit()
    finally:
        conn.close()


def _popular_exemplo(conn):
    conn.execute(
        "INSERT INTO usuario (nome, email, senha_hash) VALUES (?, ?, ?)",
        ("Administrador", "admin@agendafacil.com", generate_password_hash("admin123")),
    )
    conn.executemany(
        "INSERT INTO cliente (nome, telefone, email) VALUES (?, ?, ?)",
        [
            ("João Pereira", "(43) 99911-2233", "joao@email.com"),
            ("Marcos Lima", "(43) 99822-3344", "marcos@email.com"),
            ("Rafael Souza", "(43) 99733-4455", None),
            ("Lucas Almeida", "(43) 99644-5566", "lucas@email.com"),
        ],
    )
    conn.executemany(
        "INSERT INTO profissional (nome, especialidade, telefone) VALUES (?, ?, ?)",
        [
            ("Carlos Barbosa", "Corte e barba", "(43) 98811-0001"),
            ("Ana Ribeiro", "Coloração", "(43) 98822-0002"),
        ],
    )
    conn.executemany(
        "INSERT INTO servico (nome, descricao, preco, duracao_min) VALUES (?, ?, ?, ?)",
        [
            ("Corte masculino", "Corte na tesoura ou máquina", 40.0, 30),
            ("Barba", "Barba com toalha quente", 30.0, 30),
            ("Corte + Barba", "Combo completo", 60.0, 60),
            ("Pigmentação", "Pigmentação de barba ou cabelo", 50.0, 45),
        ],
    )
    hoje = date.today()
    amanha = hoje + timedelta(days=1)
    conn.executemany(
        """INSERT INTO agendamento
           (cliente_id, profissional_id, servico_id, usuario_id, data_hora, status, observacao)
           VALUES (?, ?, ?, 1, ?, ?, ?)""",
        [
            (1, 1, 3, f"{hoje} 09:00", "concluido", None),
            (2, 1, 1, f"{hoje} 14:00", "agendado", "Prefere máquina 2 nas laterais"),
            (3, 2, 4, f"{hoje} 15:30", "agendado", None),
            (4, 1, 2, f"{amanha} 10:00", "agendado", None),
            (1, 2, 1, f"{amanha} 16:00", "cancelado", "Cliente desmarcou"),
        ],
    )
