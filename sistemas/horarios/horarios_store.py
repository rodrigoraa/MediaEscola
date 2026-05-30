import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("DATABASE_PATH", "database.sqlite3"))
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH


def _conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_banco_horarios():
    with _conectar() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS horarios_gerados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                usuario TEXT,
                status TEXT NOT NULL,
                dados_json TEXT NOT NULL,
                criado_em TEXT NOT NULL
            )
            """
        )


def listar_horarios(limit=20):
    inicializar_banco_horarios()
    with _conectar() as conn:
        rows = conn.execute(
            """
            SELECT id, titulo, usuario, status, criado_em
            FROM horarios_gerados
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def salvar_horario(titulo, usuario, status, dados):
    inicializar_banco_horarios()
    criado_em = datetime.now().strftime("%d/%m/%Y %H:%M")
    payload = json.dumps(dados, ensure_ascii=False)

    with _conectar() as conn:
        cursor = conn.execute(
            """
            INSERT INTO horarios_gerados (titulo, usuario, status, dados_json, criado_em)
            VALUES (?, ?, ?, ?, ?)
            """,
            (titulo, usuario, status, payload, criado_em),
        )
        return cursor.lastrowid


def carregar_horario(horario_id):
    inicializar_banco_horarios()
    with _conectar() as conn:
        row = conn.execute(
            """
            SELECT id, titulo, usuario, status, dados_json, criado_em
            FROM horarios_gerados
            WHERE id = ?
            """,
            (horario_id,),
        ).fetchone()

    if not row:
        return None

    dados = dict(row)
    dados["dados"] = json.loads(dados.pop("dados_json"))
    return dados


def excluir_horario(horario_id):
    inicializar_banco_horarios()
    with _conectar() as conn:
        conn.execute("DELETE FROM horarios_gerados WHERE id = ?", (horario_id,))
