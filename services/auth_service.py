import os
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash


TIPOS_USUARIO = ("administrador", "coordenacao", "professor")


def criar_tabelas_auth(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            tipo_usuario TEXT NOT NULL,
            turmas_permitidas TEXT,
            disciplinas_permitidas TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            ultimo_login TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS logs_acesso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            email TEXT,
            acao TEXT NOT NULL,
            ip TEXT,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
        """
    )


def criar_admin_inicial(conn):
    if os.getenv("BOOTSTRAP_ADMIN_ENABLED", "1") != "1":
        return

    total = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if total:
        return

    admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
    admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    admin_name = os.getenv("BOOTSTRAP_ADMIN_NAME", "Administrador")

    if not admin_email or not admin_password:
        return

    agora = _agora()
    conn.execute(
        """
        INSERT INTO usuarios (nome, email, senha, tipo_usuario, ativo, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, 1, ?, ?)
        """,
        (
            admin_name,
            admin_email.strip().lower(),
            gerar_hash_senha(admin_password),
            "administrador",
            agora,
            agora,
        ),
    )


def gerar_hash_senha(senha):
    return generate_password_hash(senha)


def verificar_senha(hash_senha, senha):
    return check_password_hash(hash_senha, senha)


def autenticar(conn, email, senha, ip=None):
    usuario = conn.execute(
        """
        SELECT id, nome, email, senha, tipo_usuario, turmas_permitidas, disciplinas_permitidas, ativo
        FROM usuarios
        WHERE lower(email) = lower(?)
        """,
        (email.strip(),),
    ).fetchone()

    if not usuario or not usuario["ativo"] or not verificar_senha(usuario["senha"], senha):
        registrar_log(conn, None, email, "login_falhou", ip)
        return None

    agora = _agora()
    conn.execute("UPDATE usuarios SET ultimo_login = ?, atualizado_em = ? WHERE id = ?", (agora, agora, usuario["id"]))
    registrar_log(conn, usuario["id"], usuario["email"], "login", ip)
    return dict(usuario)


def listar_usuarios(conn):
    return conn.execute(
        """
        SELECT id, nome, email, tipo_usuario, turmas_permitidas, disciplinas_permitidas, ativo, ultimo_login, criado_em
        FROM usuarios
        ORDER BY nome
        """
    ).fetchall()


def criar_usuario(conn, nome, email, senha, tipo_usuario, ativo=True, turmas_permitidas="", disciplinas_permitidas=""):
    if tipo_usuario not in TIPOS_USUARIO:
        raise ValueError("Tipo de usuário inválido.")
    if not nome.strip() or not email.strip() or not senha:
        raise ValueError("Nome, email e senha são obrigatórios.")

    agora = _agora()
    conn.execute(
        """
        INSERT INTO usuarios
            (nome, email, senha, tipo_usuario, turmas_permitidas, disciplinas_permitidas, ativo, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            nome.strip(),
            email.strip().lower(),
            gerar_hash_senha(senha),
            tipo_usuario,
            turmas_permitidas.strip(),
            disciplinas_permitidas.strip(),
            1 if ativo else 0,
            agora,
            agora,
        ),
    )


def atualizar_usuario(conn, usuario_id, nome, email, tipo_usuario, ativo, turmas_permitidas="", disciplinas_permitidas=""):
    if tipo_usuario not in TIPOS_USUARIO:
        raise ValueError("Tipo de usuário inválido.")

    conn.execute(
        """
        UPDATE usuarios
        SET nome = ?, email = ?, tipo_usuario = ?, turmas_permitidas = ?, disciplinas_permitidas = ?, ativo = ?, atualizado_em = ?
        WHERE id = ?
        """,
        (
            nome.strip(),
            email.strip().lower(),
            tipo_usuario,
            turmas_permitidas.strip(),
            disciplinas_permitidas.strip(),
            1 if ativo else 0,
            _agora(),
            usuario_id,
        ),
    )


def alterar_senha(conn, usuario_id, nova_senha):
    if len(nova_senha or "") < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")

    conn.execute(
        "UPDATE usuarios SET senha = ?, atualizado_em = ? WHERE id = ?",
        (gerar_hash_senha(nova_senha), _agora(), usuario_id),
    )


def registrar_log(conn, usuario_id, email, acao, ip=None):
    conn.execute(
        """
        INSERT INTO logs_acesso (usuario_id, email, acao, ip, criado_em)
        VALUES (?, ?, ?, ?, ?)
        """,
        (usuario_id, email, acao, ip, _agora()),
    )


def permissoes_para(tipo_usuario):
    if tipo_usuario == "administrador":
        return {"usuarios", "configuracoes", "relatorios", "medias", "upload", "analises", "horarios"}
    if tipo_usuario == "coordenacao":
        return {"relatorios", "medias", "upload", "analises", "horarios"}
    if tipo_usuario == "professor":
        return {"medias", "upload", "analises", "horarios"}
    return set()


def tem_permissao(usuario, permissao):
    if not usuario:
        return False
    return permissao in permissoes_para(usuario.get("tipo_usuario"))


def verificarSessao(usuario):
    return bool(usuario and usuario.get("id"))


def verificarPermissao(usuario, permissao):
    return tem_permissao(usuario, permissao)


def criarUsuario(conn, nome, email, senha, tipo_usuario, ativo=True):
    return criar_usuario(conn, nome, email, senha, tipo_usuario, ativo)


def alterarSenha(conn, usuario_id, nova_senha):
    return alterar_senha(conn, usuario_id, nova_senha)


def recuperarSenha(email):
    # Recuperação por email exige provedor SMTP; o administrador pode redefinir a senha no painel de usuários.
    return {"email": email, "mensagem": "Solicite redefinição de senha ao administrador."}


def _agora():
    return datetime.now().isoformat(timespec="seconds")
