from contextlib import contextmanager
from io import BytesIO
import importlib
import os
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import template_rendered
from werkzeug.datastructures import MultiDict

from tests.test_medias import linha


class RotasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.env = patch.dict(os.environ, {"DATABASE_PATH": str(cls.root / "base.sqlite3"),
                                         "PENDING_DIR": str(cls.root / "pending"),
                                         "EXPORT_DIR": str(cls.root / "exports"),
                                         "BOOTSTRAP_ADMIN_ENABLED": "0"})
        cls.env.start()
        cls.mod = importlib.import_module("app")
        cls.paths = patch.multiple(cls.mod, DB_PATH=cls.root / "base.sqlite3",
                                   PENDING_DIR=cls.root / "pending", EXPORT_DIR=cls.root / "exports",
                                   UPLOAD_DIR=cls.root / "uploads")
        cls.paths.start()
        cls.mod.init_db()
        cls.mod.app.config.update(TESTING=True, SECRET_KEY="teste")

    @classmethod
    def tearDownClass(cls):
        cls.paths.stop()
        cls.env.stop()
        cls.temp.cleanup()

    def setUp(self):
        with self.mod.get_db() as conn:
            conn.execute("DELETE FROM notas")
            conn.execute("DELETE FROM boletins")
            conn.execute("UPDATE configuracoes SET valor='6.0' WHERE chave='media_minima'")
        self.client = self.mod.app.test_client()
        with self.client.session_transaction() as session:
            session["usuario"] = {"id": 1, "nome": "Teste", "tipo_usuario": "administrador"}

    def test_conexao_fecha_ao_sair_da_transacao(self):
        with self.mod.get_db() as conn:
            conn.execute("SELECT 1")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    @contextmanager
    def templates(self):
        captured = []
        def receiver(sender, template, context, **extra):
            captured.append(context)
        template_rendered.connect(receiver, self.mod.app)
        try:
            yield captured
        finally:
            template_rendered.disconnect(receiver, self.mod.app)

    def pendente(self, rows):
        token = self.mod.salvar_conferencia_temporaria(rows)
        with self.client.session_transaction() as session:
            session["conferencia_token"] = token
            session["arquivo_pdf"] = {"nome": "teste.pdf", "caminho": "teste.pdf"}

    def formulario(self, rows):
        campos = ["nome_aluno", "disciplina", "bimestre", "nota", "media_final", "situacao", "turma", "ano_letivo"]
        return MultiDict((key, row.get(key, "")) for row in rows for key in campos)

    def test_upload_remove_transferidos_antes_da_conferencia(self):
        rows = [linha(), {**linha(aluno="Saiu"), "situacao": " TRANSFERIDO "}]
        with patch.object(self.mod, "extrair_boletim_pdf", return_value=rows):
            response = self.client.post("/medias/importar", data={"pdf": (BytesIO(b"pdf"), "teste.pdf")})
        self.assertEqual(response.status_code, 302)
        with self.templates() as templates:
            response = self.client.get("/conferencia")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["nome_aluno"] for r in templates[0]["dados"]], ["Ana"])

    def test_get_filtra_conferencias_pendentes_antigas(self):
        self.pendente([linha(), {**linha(aluno="Saiu"), "situacao": "transferida"}])
        with self.templates() as templates:
            self.client.get("/conferencia")
        self.assertEqual(len(templates[0]["dados"]), 1)

    def test_post_remove_transferidos_preserva_aluno_ativo_mesmo_boletim(self):
        for situacao in ["Transferido", "Transferida", " transferido ", " TRANSFERIDA\t"]:
            with self.subTest(situacao=situacao):
                rows = [linha(), {**linha(aluno="Saiu"), "situacao": situacao}]
                self.pendente(rows)
                response = self.client.post("/conferencia", data=self.formulario(rows))
                self.assertEqual(response.status_code, 302)
                with self.mod.get_db() as conn:
                    self.assertEqual(conn.execute("SELECT count(*) FROM notas WHERE nome_aluno='Saiu'").fetchone()[0], 0)
                    self.assertGreater(conn.execute("SELECT count(*) FROM notas WHERE nome_aluno='Ana'").fetchone()[0], 0)

    def test_somente_transferidos_nao_cria_boletim(self):
        rows = [{**linha(), "situacao": "Transferido"}]
        self.pendente(rows)
        self.client.post("/conferencia", data=self.formulario(rows))
        with self.mod.get_db() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM boletins").fetchone()[0], 0)

    def test_post_rejeita_finais_conflitantes_e_preserva_conferencia(self):
        rows = [linha(), linha(final="6", bimestre="2º Bimestre")]
        self.pendente(rows)
        response = self.client.post("/conferencia", data=self.formulario(rows))
        self.assertEqual(response.status_code, 200)
        self.assertIn("conflitantes", response.get_data(as_text=True))
        with self.mod.get_db() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM boletins").fetchone()[0], 0)
        with self.client.session_transaction() as session:
            self.assertIn("conferencia_token", session)

    def salvar(self):
        rows = [linha(), linha(aluno="Bia", nota="7", final="8"),
                linha(disciplina="RA", nota="SN", final="SN")]
        self.pendente(rows)
        self.client.post("/conferencia", data=self.formulario(rows))
        with self.mod.get_db() as conn:
            return conn.execute("SELECT max(id) FROM boletins").fetchone()[0]

    def test_rotas_consistentes_e_configuracao_compartilhada(self):
        boletim_id = self.salvar()
        with self.mod.get_db() as conn:
            conn.execute("UPDATE configuracoes SET valor='9' WHERE chave='media_minima'")
        with self.templates() as analise:
            response = self.client.get(f"/analise?boletim_id={boletim_id}")
            self.assertEqual(response.status_code, 200)
            self.assertTrue("Alunos abaixo de 9,00" in response.get_data(as_text=True))
        with self.templates() as medias:
            self.assertEqual(self.client.get(f"/medias?boletim_id={boletim_id}").status_code, 200)
        self.assertEqual(analise[0]["analises"]["media_geral_turma"], medias[0]["resultado"]["resultados"][0]["media_calculada"])
        self.assertEqual(len(analise[0]["analises"]["alunos_abaixo_media"]), 2)
        self.assertNotIn(b"Aprovado", self.client.get(f"/medias?boletim_id={boletim_id}").data)

    def test_exportacoes_e_relatorio_preservados(self):
        boletim_id = self.salvar()
        for path in [f"/relatorio?boletim_id={boletim_id}", f"/exportar/excel?boletim_id={boletim_id}"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()
        for fmt, marker in [("csv", b"5.0"), ("excel", b"PK"), ("pdf", b"%PDF")]:
            with self.subTest(formato=fmt):
                response = self.client.post(f"/medias/exportar/{fmt}", data={"boletim_id": boletim_id, "relatorio": "media_geral_aluno"})
                self.assertEqual(response.status_code, 200)
                self.assertIn(marker, response.data)
                response.close()

    def test_conflito_legado_visivel_e_exportacao_do_gerador_bloqueada(self):
        boletim_id = self.salvar()
        with self.mod.get_db() as conn:
            conn.execute("""INSERT INTO notas(boletim_id,nome_aluno,disciplina,bimestre,nota,media_final,situacao)
                            VALUES(?, 'Ana', 'Matemática', '2º Bimestre', '10', '6', 'Em curso')""", (boletim_id,))
        for path in ["analise", "medias", "relatorio"]:
            response = self.client.get(f"/{path}?boletim_id={boletim_id}")
            self.assertEqual(response.status_code, 200)
            self.assertIn("conflitantes", response.get_data(as_text=True))
        for formato in ["csv", "excel", "pdf"]:
            with self.subTest(formato=formato):
                response = self.client.post(f"/medias/exportar/{formato}", data={"boletim_id": boletim_id})
                self.assertEqual(response.status_code, 302)
