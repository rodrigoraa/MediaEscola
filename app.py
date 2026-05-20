import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from services.auth_service import (
    alterar_senha,
    autenticar,
    criar_admin_inicial,
    criar_tabelas_auth,
    criar_usuario,
    listar_usuarios,
    registrar_log,
    tem_permissao,
    atualizar_usuario,
)
from services.calculos import gerar_analises
from services.leitor_pdf import extrair_boletim_pdf
from services.media_service import (
    calcular_gerador_medias,
    exportar_resultados_csv,
    exportar_resultados_excel,
    exportar_resultados_pdf,
)
from services.relatorios import gerar_excel


BASE_DIR = Path(__file__).resolve().parent


def load_env_file(path):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(BASE_DIR / ".env")
logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))


def env_path(name, default):
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else BASE_DIR / value


UPLOAD_DIR = BASE_DIR / "uploads"
EXPORT_DIR = env_path("EXPORT_DIR", "exports")
PENDING_DIR = env_path("PENDING_DIR", "tmp/conferencias")
DB_PATH = env_path("DATABASE_PATH", "database.sqlite3")
ALLOWED_EXTENSIONS = {"pdf"}


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or os.urandom(32)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.permanent_session_lifetime = timedelta(hours=int(os.getenv("SESSION_HOURS", "8")))


ROTAS_PUBLICAS = {"login", "static"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    with get_db() as conn:
        criar_tabelas_auth(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS boletins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_arquivo TEXT NOT NULL,
                caminho_arquivo TEXT NOT NULL,
                criado_em TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                boletim_id INTEGER NOT NULL,
                nome_aluno TEXT NOT NULL,
                disciplina TEXT NOT NULL,
                bimestre TEXT,
                nota TEXT,
                media_final TEXT,
                situacao TEXT,
                FOREIGN KEY (boletim_id) REFERENCES boletins(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
            """
        )
        conn.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('media_minima', '6.0')")
        conn.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('limite_recuperacao', '4.0')")
        _adicionar_coluna(conn, "notas", "turma", "TEXT")
        _adicionar_coluna(conn, "notas", "ano_letivo", "TEXT")
        _adicionar_coluna(conn, "notas", "peso", "REAL DEFAULT 1")
        _adicionar_coluna(conn, "boletins", "turma", "TEXT")
        _adicionar_coluna(conn, "boletins", "ano_letivo", "TEXT")
        _adicionar_coluna(conn, "usuarios", "turmas_permitidas", "TEXT")
        _adicionar_coluna(conn, "usuarios", "disciplinas_permitidas", "TEXT")
        criar_admin_inicial(conn)


def _adicionar_coluna(conn, tabela, coluna, definicao):
    colunas = [row["name"] for row in conn.execute(f"PRAGMA table_info({tabela})").fetchall()]
    if coluna not in colunas:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


@app.before_request
def carregar_usuario_logado():
    g.usuario = session.get("usuario")

    if request.endpoint in ROTAS_PUBLICAS or request.endpoint is None:
        return None

    if not g.usuario:
        return redirect(url_for("login", next=request.path))
    return None


@app.context_processor
def contexto_global():
    return {"usuario_logado": g.get("usuario"), "tem_permissao": tem_permissao}


def exigir_permissao(permissao):
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not tem_permissao(g.usuario, permissao):
                flash("Você não tem permissão para acessar esta área.")
                return redirect(url_for("dashboard"))
            return func(*args, **kwargs)

        return wrapper

    return decorador


def arquivo_permitido(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def buscar_boletins(apenas_arquivos=False):
    where = "WHERE caminho_arquivo IS NOT NULL AND caminho_arquivo <> ''" if apenas_arquivos else ""
    with get_db() as conn:
        return conn.execute(
            f"SELECT id, nome_arquivo, criado_em FROM boletins {where} ORDER BY id DESC"
        ).fetchall()


def definir_boletim_padrao(filtros, boletins):
    # O Gerador de Médias deve trabalhar sempre sobre uma importação específica.
    if not filtros.get("boletim_id") and boletins:
        filtros["boletim_id"] = boletins[0]["id"]
    return filtros


def buscar_notas(boletim_id=None):
    sql = "SELECT * FROM notas"
    params = []

    if boletim_id:
        sql += " WHERE boletim_id = ?"
        params.append(boletim_id)

    usuario = g.get("usuario") if "g" in globals() else None
    if usuario and usuario.get("tipo_usuario") == "professor":
        turmas = _csv_permissoes(usuario.get("turmas_permitidas"))
        disciplinas = _csv_permissoes(usuario.get("disciplinas_permitidas"))
        clausulas = []
        if turmas:
            clausulas.append(f"turma IN ({','.join('?' for _ in turmas)})")
            params.extend(turmas)
        if disciplinas:
            clausulas.append(f"disciplina IN ({','.join('?' for _ in disciplinas)})")
            params.extend(disciplinas)
        if clausulas:
            sql += (" AND " if " WHERE " in sql else " WHERE ") + " AND ".join(clausulas)
        else:
            sql += (" AND " if " WHERE " in sql else " WHERE ") + "1 = 0"

    sql += " ORDER BY nome_aluno, disciplina, bimestre"

    with get_db() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _csv_permissoes(valor):
    return [item.strip() for item in (valor or "").split(",") if item.strip()]


def filtros_medias_da_request():
    config = carregar_configuracoes()
    return {
        "boletim_id": request.values.get("boletim_id", type=int),
        "turma": request.values.get("turma", ""),
        "aluno": request.values.get("aluno", ""),
        "disciplina": request.values.get("disciplina", ""),
        "bimestre": request.values.get("bimestre", ""),
        "ano_letivo": request.values.get("ano_letivo", ""),
        "tipo_calculo": request.values.get("tipo_calculo", "media_simples"),
        "situacao": request.values.get("situacao", "todos"),
        "desempenho": request.values.get("desempenho", ""),
        "ordenacao": request.values.get("ordenacao", ""),
        "relatorio": request.values.get("relatorio", "media_geral_turma"),
        "media_minima": request.values.get("media_minima", config.get("media_minima", "6.0")),
        "limite_recuperacao": request.values.get("limite_recuperacao", config.get("limite_recuperacao", "4.0")),
    }


def carregar_configuracoes():
    with get_db() as conn:
        rows = conn.execute("SELECT chave, valor FROM configuracoes").fetchall()
    return {row["chave"]: row["valor"] for row in rows}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "")
        senha = request.form.get("senha", "")
        lembrar = request.form.get("lembrar") == "1"

        with get_db() as conn:
            usuario = autenticar(conn, email, senha, request.remote_addr)

        if not usuario:
            flash("Email ou senha inválidos.")
            return render_template("auth/login.html", email=email)

        session.permanent = lembrar
        session["usuario"] = {
            "id": usuario["id"],
            "nome": usuario["nome"],
            "email": usuario["email"],
            "tipo_usuario": usuario["tipo_usuario"],
            "turmas_permitidas": usuario.get("turmas_permitidas", ""),
            "disciplinas_permitidas": usuario.get("disciplinas_permitidas", ""),
        }
        return redirect(request.args.get("next") or url_for("dashboard"))

    return render_template("auth/login.html")


@app.route("/logout")
def logout():
    if g.usuario:
        with get_db() as conn:
            registrar_log(conn, g.usuario["id"], g.usuario["email"], "logout", request.remote_addr)
    session.clear()
    flash("Você saiu do sistema.")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


def salvar_conferencia_temporaria(dados):
    token = uuid.uuid4().hex
    caminho = PENDING_DIR / f"{token}.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return token


def carregar_conferencia_temporaria(token):
    if not token:
        return []

    caminho = PENDING_DIR / f"{token}.json"
    if not caminho.exists():
        return []

    return json.loads(caminho.read_text(encoding="utf-8"))


def remover_conferencia_temporaria(token):
    if not token:
        return

    caminho = PENDING_DIR / f"{token}.json"
    if caminho.exists():
        caminho.unlink()


def resumir_linhas(dados):
    alunos = {row.get("nome_aluno", "") for row in dados if row.get("nome_aluno")}
    disciplinas = {row.get("disciplina", "") for row in dados if row.get("disciplina")}
    return {
        "total_registros": len(dados),
        "total_alunos": len(alunos),
        "total_disciplinas": len(disciplinas),
    }


@app.route("/", methods=["GET", "POST"])
@exigir_permissao("upload")
def index():
    if request.method == "POST":
        arquivo = request.files.get("pdf")

        if not arquivo or arquivo.filename == "":
            flash("Selecione um arquivo PDF.")
            return redirect(url_for("index"))

        if not arquivo_permitido(arquivo.filename):
            flash("Envie apenas arquivos PDF.")
            return redirect(url_for("index"))

        nome_seguro = secure_filename(arquivo.filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        nome_final = f"{timestamp}_{nome_seguro}"
        caminho = UPLOAD_DIR / nome_final
        arquivo.save(caminho)

        try:
            dados = extrair_boletim_pdf(caminho)
        except Exception as exc:
            flash(f"Não foi possível ler o PDF: {exc}")
            return redirect(url_for("index"))

        if not dados:
            flash("Nenhum dado de boletim foi encontrado no PDF.")
            return redirect(url_for("index"))

        session["arquivo_pdf"] = {"nome": nome_seguro, "caminho": str(caminho)}
        session["conferencia_token"] = salvar_conferencia_temporaria(dados)
        return redirect(url_for("conferencia"))

    return render_template("index.html", boletins=buscar_boletins())


@app.route("/notas/nova", methods=["GET", "POST"])
@exigir_permissao("upload")
def lancar_nota():
    if request.method == "POST":
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO boletins (nome_arquivo, caminho_arquivo, criado_em, turma, ano_letivo)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "Lançamento manual",
                    "",
                    datetime.now().isoformat(timespec="seconds"),
                    request.form.get("turma", "").strip(),
                    request.form.get("ano_letivo", "").strip(),
                ),
            )
            boletim_id = cursor.lastrowid
            conn.execute(
                """
                INSERT INTO notas
                    (boletim_id, nome_aluno, disciplina, bimestre, nota, media_final, situacao, turma, ano_letivo, peso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    boletim_id,
                    request.form.get("nome_aluno", "").strip(),
                    request.form.get("disciplina", "").strip(),
                    request.form.get("bimestre", "").strip(),
                    request.form.get("nota", "").strip(),
                    request.form.get("media_final", "").strip(),
                    request.form.get("situacao", "").strip(),
                    request.form.get("turma", "").strip(),
                    request.form.get("ano_letivo", "").strip(),
                    request.form.get("peso", "1").replace(",", "."),
                ),
            )
        flash("Nota lançada com sucesso.")
        return redirect(url_for("gerador_medias", boletim_id=boletim_id))

    return render_template("notas/nova.html")


@app.route("/conferencia", methods=["GET", "POST"])
def conferencia():
    token = session.get("conferencia_token")
    dados = carregar_conferencia_temporaria(token)
    arquivo_pdf = session.get("arquivo_pdf")

    if not dados or not arquivo_pdf:
        flash("Envie um PDF antes de conferir os dados.")
        return redirect(url_for("index"))

    if request.method == "POST":
        linhas = []
        total = len(request.form.getlist("nome_aluno"))

        for idx in range(total):
            nomes = request.form.getlist("nome_aluno")
            disciplinas = request.form.getlist("disciplina")
            bimestres = request.form.getlist("bimestre")
            notas_form = request.form.getlist("nota")
            medias_finais = request.form.getlist("media_final")
            situacoes = request.form.getlist("situacao")
            turmas = request.form.getlist("turma")
            anos = request.form.getlist("ano_letivo")
            nome_aluno = nomes[idx].strip()
            disciplina = disciplinas[idx].strip()

            if not nome_aluno or not disciplina:
                continue

            linhas.append(
                {
                    "nome_aluno": nome_aluno,
                    "disciplina": disciplina,
                    "bimestre": bimestres[idx].strip(),
                    "nota": notas_form[idx].strip(),
                    "media_final": medias_finais[idx].strip(),
                    "situacao": situacoes[idx].strip(),
                    "turma": turmas[idx].strip() if idx < len(turmas) else "",
                    "ano_letivo": anos[idx].strip() if idx < len(anos) else "",
                }
            )

        if not linhas:
            flash("Mantenha pelo menos uma linha com aluno e disciplina.")
            return render_template("conferencia.html", dados=dados, resumo=resumir_linhas(dados))

        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO boletins (nome_arquivo, caminho_arquivo, criado_em)
                VALUES (?, ?, ?)
                """,
                (arquivo_pdf["nome"], arquivo_pdf["caminho"], datetime.now().isoformat(timespec="seconds")),
            )
            boletim_id = cursor.lastrowid

            conn.executemany(
                """
                INSERT INTO notas
                    (boletim_id, nome_aluno, disciplina, bimestre, nota, media_final, situacao, turma, ano_letivo, peso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        boletim_id,
                        row["nome_aluno"],
                        row["disciplina"],
                        row["bimestre"],
                        row["nota"],
                        row["media_final"],
                        row["situacao"],
                        row.get("turma", ""),
                        row.get("ano_letivo", ""),
                        1,
                    )
                    for row in linhas
                ],
            )

        remover_conferencia_temporaria(token)
        session.pop("conferencia_token", None)
        session.pop("arquivo_pdf", None)
        flash("Dados salvos com sucesso.")
        return redirect(url_for("analise", boletim_id=boletim_id))

    return render_template("conferencia.html", dados=dados, resumo=resumir_linhas(dados))


@app.route("/analise")
@exigir_permissao("analises")
def analise():
    boletim_id = request.args.get("boletim_id", type=int)
    modo = request.args.get("modo", "nota")
    visao = request.args.get("visao", "sala")
    detalhe = request.args.get("detalhe", "aluno_bimestre")
    bimestre = request.args.get("bimestre", "")
    detalhes_bimestre = {"aluno_bimestre", "turma_bimestre", "turma_disciplina"}
    detalhes_disciplina = {
        "aluno_disciplina",
        "turma_disciplina",
        "geral_disciplina",
        "disciplina_bimestre",
        "menor_rendimento",
    }

    if modo not in {"nota", "porcentagem"}:
        modo = "nota"
    if visao not in {"sala", "aluno", "bimestre", "disciplina"}:
        visao = "sala"
    if visao == "disciplina" and detalhe not in detalhes_disciplina:
        detalhe = "aluno_disciplina"
    elif visao == "bimestre" and detalhe not in detalhes_bimestre:
        detalhe = "aluno_bimestre"
    elif visao not in {"bimestre", "disciplina"}:
        detalhe = "aluno_bimestre"

    notas = buscar_notas(boletim_id)
    analises = gerar_analises(notas)
    bimestres = [row["bimestre"] for row in analises.get("media_por_bimestre", []) if row.get("bimestre")]

    if visao == "bimestre" and bimestre:
        analises = dict(analises)
        analises["media_aluno_por_bimestre"] = [
            row for row in analises["media_aluno_por_bimestre"] if row.get("bimestre") == bimestre
        ]
        analises["media_por_bimestre"] = [
            row for row in analises["media_por_bimestre"] if row.get("bimestre") == bimestre
        ]
        analises["media_disciplina_por_bimestre"] = [
            row for row in analises["media_disciplina_por_bimestre"] if row.get("bimestre") == bimestre
        ]

    return render_template(
        "analise.html",
        boletins=buscar_boletins(),
        boletim_id=boletim_id,
        modo=modo,
        visao=visao,
        detalhe=detalhe,
        bimestre=bimestre,
        bimestres=bimestres,
        analises=analises,
        total_registros=len(notas),
    )


@app.route("/relatorio")
@exigir_permissao("relatorios")
def relatorio():
    boletim_id = request.args.get("boletim_id", type=int)
    modo = request.args.get("modo", "nota")
    if modo not in {"nota", "porcentagem"}:
        modo = "nota"
    notas = buscar_notas(boletim_id)
    analises = gerar_analises(notas)

    return render_template(
        "relatorio.html",
        analises=analises,
        boletim_id=boletim_id,
        modo=modo,
        gerado_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )


@app.route("/exportar/excel")
@exigir_permissao("relatorios")
def exportar_excel():
    boletim_id = request.args.get("boletim_id", type=int)
    notas = buscar_notas(boletim_id)

    if not notas:
        flash("Não há dados para exportar.")
        return redirect(url_for("analise"))

    analises = gerar_analises(notas)
    caminho = gerar_excel(EXPORT_DIR, notas, analises, boletim_id)
    return send_file(caminho, as_attachment=True, download_name=Path(caminho).name)


@app.route("/medias", methods=["GET", "POST"])
@exigir_permissao("medias")
def gerador_medias():
    filtros = filtros_medias_da_request()
    boletins = buscar_boletins(apenas_arquivos=True)
    filtros = definir_boletim_padrao(filtros, boletins)
    notas = buscar_notas(filtros.get("boletim_id"))
    resultado = calcular_gerador_medias(notas, filtros)
    filtros["relatorio"] = resultado["relatorio"]
    return render_template("medias/index.html", filtros=filtros, resultado=resultado, boletins=boletins)


@app.route("/medias/exportar/<formato>", methods=["POST"])
@exigir_permissao("medias")
def exportar_medias(formato):
    filtros = filtros_medias_da_request()
    boletins = buscar_boletins(apenas_arquivos=True)
    filtros = definir_boletim_padrao(filtros, boletins)
    if not filtros.get("boletim_id"):
        flash("Envie um PDF antes de exportar resultados do Gerador de Médias.")
        return redirect(url_for("gerador_medias"))

    notas = buscar_notas(filtros.get("boletim_id"))
    resultado = calcular_gerador_medias(notas, filtros)

    if formato == "csv":
        caminho = exportar_resultados_csv(EXPORT_DIR, resultado["resultados"])
        mimetype = "text/csv"
    elif formato == "excel":
        caminho = exportar_resultados_excel(EXPORT_DIR, resultado["resultados"], resultado["estatisticas"])
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif formato == "pdf":
        caminho = exportar_resultados_pdf(EXPORT_DIR, resultado["resultados"], resultado["estatisticas"])
        mimetype = "application/pdf"
    else:
        flash("Formato de exportação inválido.")
        return redirect(url_for("gerador_medias"))

    return send_file(caminho, as_attachment=True, download_name=Path(caminho).name, mimetype=mimetype)


@app.route("/usuarios", methods=["GET", "POST"])
@exigir_permissao("usuarios")
def usuarios():
    if request.method == "POST":
        try:
            with get_db() as conn:
                criar_usuario(
                    conn,
                    request.form.get("nome", ""),
                    request.form.get("email", ""),
                    request.form.get("senha", ""),
                    request.form.get("tipo_usuario", ""),
                    request.form.get("ativo") == "1",
                    request.form.get("turmas_permitidas", ""),
                    request.form.get("disciplinas_permitidas", ""),
                )
            flash("Usuário criado com sucesso.")
        except sqlite3.IntegrityError:
            flash("Já existe um usuário com este email.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("usuarios"))

    with get_db() as conn:
        lista = listar_usuarios(conn)
    return render_template("auth/usuarios.html", usuarios=lista)


@app.route("/configuracoes", methods=["GET", "POST"])
@exigir_permissao("configuracoes")
def configuracoes():
    if request.method == "POST":
        with get_db() as conn:
            conn.execute(
                "INSERT INTO configuracoes (chave, valor) VALUES ('media_minima', ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                (request.form.get("media_minima", "6.0"),),
            )
            conn.execute(
                "INSERT INTO configuracoes (chave, valor) VALUES ('limite_recuperacao', ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                (request.form.get("limite_recuperacao", "4.0"),),
            )
        flash("Configurações salvas.")
        return redirect(url_for("configuracoes"))

    return render_template("configuracoes.html", config=carregar_configuracoes())


@app.route("/usuarios/<int:usuario_id>/editar", methods=["POST"])
@exigir_permissao("usuarios")
def editar_usuario(usuario_id):
    try:
        with get_db() as conn:
            atualizar_usuario(
                conn,
                usuario_id,
                request.form.get("nome", ""),
                request.form.get("email", ""),
                request.form.get("tipo_usuario", ""),
                request.form.get("ativo") == "1",
                request.form.get("turmas_permitidas", ""),
                request.form.get("disciplinas_permitidas", ""),
            )
        flash("Usuário atualizado.")
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for("usuarios"))


@app.route("/alterar-senha", methods=["GET", "POST"])
def alterar_senha_view():
    if request.method == "POST":
        try:
            with get_db() as conn:
                alterar_senha(conn, g.usuario["id"], request.form.get("nova_senha", ""))
            flash("Senha alterada com sucesso.")
            return redirect(url_for("dashboard"))
        except ValueError as exc:
            flash(str(exc))
    return render_template("auth/alterar_senha.html")


@app.template_filter("json_attr")
def json_attr(value):
    return json.dumps(value, ensure_ascii=False)


@app.template_filter("media")
def media(value, modo="nota"):
    if value is None:
        return "-"

    numero = float(value)
    if modo == "porcentagem":
        return f"{numero * 10:.1f}%".replace(".", ",")

    return f"{numero:.2f}".replace(".", ",")


init_db()


if __name__ == "__main__":
    app.run(
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG") == "1",
    )
