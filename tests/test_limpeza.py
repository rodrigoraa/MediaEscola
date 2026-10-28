from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "manutencao_medias.py"


class LimpezaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "base.sqlite3"
        self.backup = Path(self.temp.name) / "backup.sqlite3"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.executescript("""
                CREATE TABLE boletins(id INTEGER PRIMARY KEY, caminho_arquivo TEXT);
                CREATE TABLE notas(id INTEGER PRIMARY KEY, boletim_id INTEGER, nome_aluno TEXT, situacao TEXT,
                                   nota TEXT, FOREIGN KEY(boletim_id) REFERENCES boletins(id));
                CREATE TABLE horarios_gerados(id INTEGER PRIMARY KEY, dados_json TEXT);
                INSERT INTO boletins VALUES(1, 'ativo.pdf'), (2, 'transferido.pdf'), (3, 'orfao.pdf');
                INSERT INTO notas VALUES(1,1,'Ativo','Em curso','8'), (2,1,'Saiu',' Transferido ','5'),
                    (3,2,'Saiu 2','TRANSFERIDA','6'), (4,1,'Ativo 2','Em curso','0,0'),
                    (5,1,'Ativo 3','Não Transferido','7'), (6,1,'Saiu 3', char(9)||'transferida'||char(10),'9');
                INSERT INTO horarios_gerados VALUES(1, '{"preservar": true}');
            """)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--db", str(self.db)], capture_output=True, text=True)

    def conteudo(self, path=None):
        with closing(sqlite3.connect(path or self.db)) as conn:
            return [conn.execute(f"SELECT * FROM {t} ORDER BY id").fetchall()
                    for t in ("boletins", "notas", "horarios_gerados")]

    def test_simulacao_nao_modifica_dados(self):
        antes = self.conteudo()
        result = self.run_cli("limpar")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"notas_transferidas": 3', result.stdout)
        self.assertEqual(self.conteudo(), antes)
        self.assertFalse(self.backup.exists())

    def test_backup_precede_exclusao_preserva_ativos_e_horarios(self):
        antes = self.conteudo()
        result = self.run_cli("limpar", "--aplicar", "--backup", str(self.backup))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.conteudo(self.backup), antes)
        boletins, notas, horarios = self.conteudo()
        self.assertEqual([r[0] for r in boletins], [1])
        self.assertEqual([r[0] for r in notas], [1, 4, 5])
        self.assertEqual(horarios, antes[2])
        # Segunda execução segura e idempotente.
        second = self.run_cli("limpar", "--aplicar", "--backup", str(self.backup.with_name("backup2.sqlite3")))
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn('"notas_transferidas": 0', second.stdout)

    def test_aplicar_sem_backup_ou_backup_existente_recusa(self):
        antes = self.conteudo()
        self.assertNotEqual(self.run_cli("limpar", "--aplicar").returncode, 0)
        self.backup.write_text("preservar", encoding="utf-8")
        self.assertNotEqual(self.run_cli("limpar", "--aplicar", "--backup", str(self.backup)).returncode, 0)
        self.assertEqual(self.backup.read_text(encoding="utf-8"), "preservar")
        self.assertEqual(self.conteudo(), antes)

    def test_backup_separado_e_banco_inexistente(self):
        result = self.run_cli("backup", "--destino", str(self.backup))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.conteudo(self.backup), self.conteudo())
        absent = Path(self.temp.name) / "inexistente.sqlite3"
        result = subprocess.run([sys.executable, str(SCRIPT), "limpar", "--db", str(absent)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(absent.exists())

    def test_backup_mesmo_banco_recusa(self):
        antes = self.conteudo()
        self.assertNotEqual(self.run_cli("limpar", "--aplicar", "--backup", str(self.db)).returncode, 0)
        self.assertEqual(self.conteudo(), antes)

    def test_backup_inclui_commits_no_wal_e_nao_apaga_pdf(self):
        pdf = Path(self.temp.name) / "ativo.pdf"
        pdf.write_bytes(b"preservar pdf original")
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("INSERT INTO notas VALUES(7,1,'Ativo WAL','Em curso','10')")
            conn.commit()
            antes = self.conteudo()
            result = self.run_cli("limpar", "--aplicar", "--backup", str(self.backup))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.conteudo(self.backup), antes)
        self.assertEqual(pdf.read_bytes(), b"preservar pdf original")

    def test_falha_no_delete_faz_rollback(self):
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("CREATE TRIGGER impedir BEFORE DELETE ON boletins BEGIN SELECT RAISE(ABORT, 'teste rollback'); END")
        antes = self.conteudo()
        result = self.run_cli("limpar", "--aplicar", "--backup", str(self.backup))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.conteudo(), antes)
        self.assertEqual(self.conteudo(self.backup), antes)
