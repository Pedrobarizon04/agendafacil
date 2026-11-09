-- AgendaFácil - Esquema do banco de dados (SQLite)

CREATE TABLE IF NOT EXISTS usuario (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS cliente (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    telefone    TEXT    NOT NULL,
    email       TEXT,
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS profissional (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT    NOT NULL,
    especialidade TEXT,
    telefone      TEXT,
    ativo         INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS servico (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nome         TEXT    NOT NULL,
    descricao    TEXT,
    preco        REAL    NOT NULL CHECK (preco >= 0),
    duracao_min  INTEGER NOT NULL CHECK (duracao_min > 0)
);

CREATE TABLE IF NOT EXISTS agendamento (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id       INTEGER NOT NULL REFERENCES cliente(id)      ON DELETE RESTRICT,
    profissional_id  INTEGER NOT NULL REFERENCES profissional(id) ON DELETE RESTRICT,
    servico_id       INTEGER NOT NULL REFERENCES servico(id)      ON DELETE RESTRICT,
    usuario_id       INTEGER          REFERENCES usuario(id)      ON DELETE SET NULL,
    data_hora        TEXT    NOT NULL,
    status           TEXT    NOT NULL DEFAULT 'agendado'
                     CHECK (status IN ('agendado', 'concluido', 'cancelado')),
    observacao       TEXT,
    criado_em        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);
