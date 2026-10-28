"""Backup consistente e limpeza seletiva. Simulação é o padrão.

Não importa app.py, não cria banco nem altera tabelas ao inspecionar.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sistemas.medias.services.situacao import eh_transferido


def conectar(caminho, modo="ro"):
    caminho = Path(caminho).resolve(strict=True)
    return sqlite3.connect(caminho.as_uri() + f"?mode={modo}", uri=True, timeout=30)


def backup_sqlite(origem, destino):
    origem = Path(origem).resolve(strict=True)
    destino = Path(destino).resolve()
    if destino == origem:
        raise ValueError("O destino do backup deve ser diferente do banco original.")
    # Criação exclusiva: nunca sobrescrever um backup anterior.
    with destino.open("xb"):
        pass
    with closing(conectar(origem)) as fonte, closing(sqlite3.connect(destino)) as copia:
        fonte.backup(copia)
        if copia.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup não passou na verificação de integridade.")
    return str(destino)


def limpar_transferidos(caminho, aplicar=False, backup=None):
    if aplicar and not backup:
        raise ValueError("Para aplicar, informe --backup com um caminho novo.")
    with closing(conectar(caminho, "rw" if aplicar else "ro")) as conn:
        conn.create_function("eh_transferido", 1, eh_transferido, deterministic=True)
        if aplicar:
            conn.execute("PRAGMA foreign_keys=ON")
            # Impede outro escritor entre o backup e a limpeza. O backup usa
            # outra conexão de leitura, antes de qualquer DELETE nesta transação.
            conn.execute("BEGIN IMMEDIATE")
        try:
            total = conn.execute("SELECT count(*) FROM notas WHERE eh_transferido(situacao)").fetchone()[0]
            orfaos = conn.execute("""
                SELECT count(*) FROM boletins b WHERE NOT EXISTS (
                    SELECT 1 FROM notas n WHERE n.boletim_id=b.id AND NOT eh_transferido(n.situacao)
                )
            """).fetchone()[0]
            resultado = {"modo": "aplicar" if aplicar else "simulacao",
                         "notas_transferidas": total, "boletins_orfaos": orfaos}
            if aplicar:
                resultado["backup"] = backup_sqlite(caminho, backup)
                conn.execute("DELETE FROM notas WHERE eh_transferido(situacao)")
                conn.execute("DELETE FROM boletins WHERE NOT EXISTS (SELECT 1 FROM notas WHERE notas.boletim_id=boletins.id)")
                conn.commit()
            return resultado
        except Exception:
            conn.rollback()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    comandos = parser.add_subparsers(dest="comando", required=True)
    copia = comandos.add_parser("backup", help="Criar backup usando a API SQLite, inclusive com WAL ativo")
    copia.add_argument("--db", required=True)
    copia.add_argument("--destino", required=True)
    limpeza = comandos.add_parser("limpar", help="Simular ou aplicar exclusão de notas transferidas e boletins órfãos")
    limpeza.add_argument("--db", required=True)
    limpeza.add_argument("--aplicar", action="store_true")
    limpeza.add_argument("--backup")
    args = parser.parse_args()
    try:
        if args.comando == "backup":
            resultado = {"backup": backup_sqlite(args.db, args.destino)}
        else:
            resultado = limpar_transferidos(args.db, args.aplicar, args.backup)
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    except (OSError, sqlite3.Error, ValueError) as exc:
        parser.exit(1, f"Operação recusada: {exc}\n")


if __name__ == "__main__":
    main()
