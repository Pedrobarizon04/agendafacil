"""AgendaFácil - Sistema de agendamento para barbearias.

Para rodar:  python app.py   e abrir http://127.0.0.1:5000
"""
import os
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import close_db, get_db, init_db

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
app.config["DATABASE"] = str(Path(app.instance_path) / "agendafacil.db")
app.teardown_appcontext(close_db)

STATUS = {"agendado": "Agendado", "concluido": "Concluído", "cancelado": "Cancelado"}
FORMATO_DATA_HORA = "%Y-%m-%d %H:%M"


# --------------------------------------------------------------------------- #
# Filtros usados nos templates
# --------------------------------------------------------------------------- #
@app.template_filter("moeda")
def moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@app.template_filter("data_br")
def data_br(texto):
    return datetime.strptime(texto, FORMATO_DATA_HORA).strftime("%d/%m/%Y %H:%M")


@app.context_processor
def variaveis_globais():
    return {"STATUS": STATUS}


# --------------------------------------------------------------------------- #
# UC01 - Autenticar usuário (login, logout e cadastro de usuário)
# --------------------------------------------------------------------------- #
def login_obrigatorio(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.usuario is None:
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


@app.before_request
def carregar_usuario():
    uid = session.get("usuario_id")
    g.usuario = None
    if uid is not None:
        g.usuario = get_db().execute("SELECT * FROM usuario WHERE id = ?", (uid,)).fetchone()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]
        usuario = get_db().execute("SELECT * FROM usuario WHERE email = ?", (email,)).fetchone()
        if usuario and check_password_hash(usuario["senha_hash"], senha):
            session.clear()
            session["usuario_id"] = usuario["id"]
            return redirect(url_for("inicio"))
        flash("E-mail ou senha inválidos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/usuarios/novo", methods=["GET", "POST"])
def usuario_novo():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]
        if not nome or not email or len(senha) < 6:
            flash("Preencha nome, e-mail e uma senha com pelo menos 6 caracteres.", "danger")
        else:
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO usuario (nome, email, senha_hash) VALUES (?, ?, ?)",
                    (nome, email, generate_password_hash(senha)),
                )
                db.commit()
                flash("Usuário cadastrado. Faça login.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Já existe um usuário com esse e-mail.", "danger")
    return render_template("usuario_form.html")


# --------------------------------------------------------------------------- #
# Página inicial: resumo e agenda do dia
# --------------------------------------------------------------------------- #
@app.route("/")
@login_obrigatorio
def inicio():
    db = get_db()
    hoje = date.today().isoformat()
    totais = {
        "clientes": db.execute("SELECT COUNT(*) FROM cliente").fetchone()[0],
        "profissionais": db.execute("SELECT COUNT(*) FROM profissional WHERE ativo = 1").fetchone()[0],
        "servicos": db.execute("SELECT COUNT(*) FROM servico").fetchone()[0],
        "hoje": db.execute(
            "SELECT COUNT(*) FROM agendamento WHERE date(data_hora) = ? AND status != 'cancelado'",
            (hoje,),
        ).fetchone()[0],
    }
    agenda = buscar_agendamentos(data=hoje)
    return render_template("inicio.html", totais=totais, agenda=agenda)


# --------------------------------------------------------------------------- #
# UC02 - Manter clientes (CRUD)
# --------------------------------------------------------------------------- #
@app.route("/clientes")
@login_obrigatorio
def clientes_lista():
    busca = request.args.get("q", "").strip()
    clientes = get_db().execute(
        "SELECT * FROM cliente WHERE nome LIKE ? OR telefone LIKE ? ORDER BY nome",
        (f"%{busca}%", f"%{busca}%"),
    ).fetchall()
    return render_template("clientes/lista.html", clientes=clientes, busca=busca)


@app.route("/clientes/novo", methods=["GET", "POST"])
@app.route("/clientes/<int:id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def cliente_form(id=None):
    db = get_db()
    cliente = db.execute("SELECT * FROM cliente WHERE id = ?", (id,)).fetchone() if id else None
    if id and cliente is None:
        flash("Cliente não encontrado.", "danger")
        return redirect(url_for("clientes_lista"))

    if request.method == "POST":
        nome = request.form["nome"].strip()
        telefone = request.form["telefone"].strip()
        email = request.form["email"].strip() or None
        if not nome or not telefone:
            flash("Nome e telefone são obrigatórios.", "danger")
        else:
            if cliente:
                db.execute(
                    "UPDATE cliente SET nome = ?, telefone = ?, email = ? WHERE id = ?",
                    (nome, telefone, email, id),
                )
                flash("Cliente atualizado.", "success")
            else:
                db.execute(
                    "INSERT INTO cliente (nome, telefone, email) VALUES (?, ?, ?)",
                    (nome, telefone, email),
                )
                flash("Cliente cadastrado.", "success")
            db.commit()
            return redirect(url_for("clientes_lista"))
    return render_template("clientes/form.html", cliente=cliente)


@app.route("/clientes/<int:id>/excluir", methods=["POST"])
@login_obrigatorio
def cliente_excluir(id):
    excluir_registro("cliente", id, "Cliente")
    return redirect(url_for("clientes_lista"))


# --------------------------------------------------------------------------- #
# UC03 - Manter profissionais (CRUD)
# --------------------------------------------------------------------------- #
@app.route("/profissionais")
@login_obrigatorio
def profissionais_lista():
    profissionais = get_db().execute("SELECT * FROM profissional ORDER BY nome").fetchall()
    return render_template("profissionais/lista.html", profissionais=profissionais)


@app.route("/profissionais/novo", methods=["GET", "POST"])
@app.route("/profissionais/<int:id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def profissional_form(id=None):
    db = get_db()
    prof = db.execute("SELECT * FROM profissional WHERE id = ?", (id,)).fetchone() if id else None
    if id and prof is None:
        flash("Profissional não encontrado.", "danger")
        return redirect(url_for("profissionais_lista"))

    if request.method == "POST":
        nome = request.form["nome"].strip()
        especialidade = request.form["especialidade"].strip() or None
        telefone = request.form["telefone"].strip() or None
        ativo = 1 if request.form.get("ativo") else 0
        if not nome:
            flash("O nome é obrigatório.", "danger")
        else:
            if prof:
                db.execute(
                    "UPDATE profissional SET nome = ?, especialidade = ?, telefone = ?, ativo = ? WHERE id = ?",
                    (nome, especialidade, telefone, ativo, id),
                )
                flash("Profissional atualizado.", "success")
            else:
                db.execute(
                    "INSERT INTO profissional (nome, especialidade, telefone, ativo) VALUES (?, ?, ?, ?)",
                    (nome, especialidade, telefone, ativo),
                )
                flash("Profissional cadastrado.", "success")
            db.commit()
            return redirect(url_for("profissionais_lista"))
    return render_template("profissionais/form.html", prof=prof)


@app.route("/profissionais/<int:id>/excluir", methods=["POST"])
@login_obrigatorio
def profissional_excluir(id):
    excluir_registro("profissional", id, "Profissional")
    return redirect(url_for("profissionais_lista"))


# --------------------------------------------------------------------------- #
# UC04 - Manter serviços (CRUD)
# --------------------------------------------------------------------------- #
@app.route("/servicos")
@login_obrigatorio
def servicos_lista():
    servicos = get_db().execute("SELECT * FROM servico ORDER BY nome").fetchall()
    return render_template("servicos/lista.html", servicos=servicos)


@app.route("/servicos/novo", methods=["GET", "POST"])
@app.route("/servicos/<int:id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def servico_form(id=None):
    db = get_db()
    servico = db.execute("SELECT * FROM servico WHERE id = ?", (id,)).fetchone() if id else None
    if id and servico is None:
        flash("Serviço não encontrado.", "danger")
        return redirect(url_for("servicos_lista"))

    if request.method == "POST":
        nome = request.form["nome"].strip()
        descricao = request.form["descricao"].strip() or None
        try:
            preco = float(request.form["preco"].replace(",", "."))
            duracao = int(request.form["duracao_min"])
        except ValueError:
            preco, duracao = -1, 0
        if not nome or preco < 0 or duracao <= 0:
            flash("Informe nome, preço (≥ 0) e duração em minutos (> 0).", "danger")
        else:
            if servico:
                db.execute(
                    "UPDATE servico SET nome = ?, descricao = ?, preco = ?, duracao_min = ? WHERE id = ?",
                    (nome, descricao, preco, duracao, id),
                )
                flash("Serviço atualizado.", "success")
            else:
                db.execute(
                    "INSERT INTO servico (nome, descricao, preco, duracao_min) VALUES (?, ?, ?, ?)",
                    (nome, descricao, preco, duracao),
                )
                flash("Serviço cadastrado.", "success")
            db.commit()
            return redirect(url_for("servicos_lista"))
    return render_template("servicos/form.html", servico=servico)


@app.route("/servicos/<int:id>/excluir", methods=["POST"])
@login_obrigatorio
def servico_excluir(id):
    excluir_registro("servico", id, "Serviço")
    return redirect(url_for("servicos_lista"))


# --------------------------------------------------------------------------- #
# UC05 - Gerenciar agendamentos (CRUD + consulta da agenda)
# --------------------------------------------------------------------------- #
def buscar_agendamentos(data=None, status=None):
    sql = """
        SELECT a.*, c.nome AS cliente, p.nome AS profissional,
               s.nome AS servico, s.preco, s.duracao_min
          FROM agendamento a
          JOIN cliente c      ON c.id = a.cliente_id
          JOIN profissional p ON p.id = a.profissional_id
          JOIN servico s      ON s.id = a.servico_id
         WHERE 1 = 1
    """
    params = []
    if data:
        sql += " AND date(a.data_hora) = ?"
        params.append(data)
    if status:
        sql += " AND a.status = ?"
        params.append(status)
    sql += " ORDER BY a.data_hora"
    return get_db().execute(sql, params).fetchall()


def horario_ocupado(profissional_id, inicio, duracao_min, ignorar_id=None):
    """Regra de negócio: um profissional não pode ter dois atendimentos ao mesmo tempo."""
    fim = inicio + timedelta(minutes=duracao_min)
    outros = get_db().execute(
        """SELECT a.data_hora, s.duracao_min
             FROM agendamento a JOIN servico s ON s.id = a.servico_id
            WHERE a.profissional_id = ? AND a.status != 'cancelado'
              AND date(a.data_hora) = ? AND a.id != ?""",
        (profissional_id, inicio.date().isoformat(), ignorar_id or 0),
    ).fetchall()
    for outro in outros:
        inicio_outro = datetime.strptime(outro["data_hora"], FORMATO_DATA_HORA)
        fim_outro = inicio_outro + timedelta(minutes=outro["duracao_min"])
        if inicio < fim_outro and inicio_outro < fim:
            return True
    return False


@app.route("/agendamentos")
@login_obrigatorio
def agendamentos_lista():
    data = request.args.get("data", "")
    status = request.args.get("status", "")
    agendamentos = buscar_agendamentos(data=data or None, status=status or None)
    return render_template(
        "agendamentos/lista.html", agendamentos=agendamentos, data=data, status=status
    )


@app.route("/agendamentos/novo", methods=["GET", "POST"])
@app.route("/agendamentos/<int:id>/editar", methods=["GET", "POST"])
@login_obrigatorio
def agendamento_form(id=None):
    db = get_db()
    ag = db.execute("SELECT * FROM agendamento WHERE id = ?", (id,)).fetchone() if id else None
    if id and ag is None:
        flash("Agendamento não encontrado.", "danger")
        return redirect(url_for("agendamentos_lista"))

    if request.method == "POST":
        form = request.form
        try:
            cliente_id = int(form["cliente_id"])
            profissional_id = int(form["profissional_id"])
            servico_id = int(form["servico_id"])
            inicio = datetime.strptime(form["data_hora"], "%Y-%m-%dT%H:%M")
        except (KeyError, ValueError):
            flash("Preencha cliente, profissional, serviço, data e hora.", "danger")
            return render_template("agendamentos/form.html", ag=ag, **opcoes_agendamento())

        status = form.get("status", "agendado") if ag else "agendado"
        observacao = form.get("observacao", "").strip() or None
        servico = db.execute("SELECT duracao_min FROM servico WHERE id = ?", (servico_id,)).fetchone()

        erro = None
        if ag is None and inicio < datetime.now():
            erro = "Não é possível agendar em uma data/hora que já passou."
        elif status != "cancelado" and horario_ocupado(
            profissional_id, inicio, servico["duracao_min"], ignorar_id=id
        ):
            erro = "Esse profissional já tem um atendimento nesse horário."

        if erro:
            flash(erro, "danger")
        else:
            data_hora = inicio.strftime(FORMATO_DATA_HORA)
            if ag:
                db.execute(
                    """UPDATE agendamento
                          SET cliente_id = ?, profissional_id = ?, servico_id = ?,
                              data_hora = ?, status = ?, observacao = ?
                        WHERE id = ?""",
                    (cliente_id, profissional_id, servico_id, data_hora, status, observacao, id),
                )
                flash("Agendamento atualizado.", "success")
            else:
                db.execute(
                    """INSERT INTO agendamento
                       (cliente_id, profissional_id, servico_id, usuario_id, data_hora, observacao)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (cliente_id, profissional_id, servico_id, g.usuario["id"], data_hora, observacao),
                )
                flash("Agendamento criado.", "success")
            db.commit()
            return redirect(url_for("agendamentos_lista"))

    return render_template("agendamentos/form.html", ag=ag, **opcoes_agendamento())


def opcoes_agendamento():
    db = get_db()
    return {
        "clientes": db.execute("SELECT id, nome FROM cliente ORDER BY nome").fetchall(),
        "profissionais": db.execute(
            "SELECT id, nome FROM profissional WHERE ativo = 1 ORDER BY nome"
        ).fetchall(),
        "servicos": db.execute(
            "SELECT id, nome, preco, duracao_min FROM servico ORDER BY nome"
        ).fetchall(),
    }


@app.route("/agendamentos/<int:id>/excluir", methods=["POST"])
@login_obrigatorio
def agendamento_excluir(id):
    excluir_registro("agendamento", id, "Agendamento")
    return redirect(url_for("agendamentos_lista"))


# --------------------------------------------------------------------------- #
# Exclusão genérica (com proteção de chave estrangeira)
# --------------------------------------------------------------------------- #
def excluir_registro(tabela, id, rotulo):
    db = get_db()
    try:
        cursor = db.execute(f"DELETE FROM {tabela} WHERE id = ?", (id,))
        db.commit()
        if cursor.rowcount:
            flash(f"{rotulo} excluído.", "success")
        else:
            flash(f"{rotulo} não encontrado.", "danger")
    except sqlite3.IntegrityError:
        flash(
            f"{rotulo} possui agendamentos vinculados e não pode ser excluído.", "danger"
        )


init_db(app)

if __name__ == "__main__":
    app.run(debug=True)
