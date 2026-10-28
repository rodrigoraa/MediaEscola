import os
from pathlib import Path
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pdfplumber

from sistemas.medias.services.leitor_pdf import (
    BIMESTRES, _extrair_por_tabelas, _extrair_por_texto, extrair_boletim_pdf,
)


HEADER = ["Disciplina", *BIMESTRES, "Média Anual", "Exame", "Média Final"]
CONTEXT = dict(aluno="Ana", turma="6º EF", ano_letivo="2026", situacao="Em curso")


def pagina(rows):
    return SimpleNamespace(extract_tables=lambda: [rows])


class LeitorPDFTest(unittest.TestCase):
    def test_tabela_preserva_vazios_final_e_nome_multilinha(self):
        rows = _extrair_por_tabelas(pagina([HEADER, [
            "Língua Portuguesa - Literatura e\nProdução Textual", "10", "10", "10", "", "10", "", "5",
        ]]), CONTEXT)
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["nota"] for r in rows], ["10", "10", "10", ""])
        self.assertTrue(all(r["media_final"] == "5" for r in rows))
        self.assertTrue(all(r["disciplina"] == "Língua Portuguesa - Literatura e Produção Textual" for r in rows))

    def test_media_anual_nao_substitui_final_vazia(self):
        rows = _extrair_por_tabelas(pagina([HEADER, ["Arte", "7", "", "", "", "9", "", ""]]), CONTEXT)
        self.assertTrue(all(r["media_final"] == "" for r in rows))

    def test_tabela_rejeita_cabecalho_incompleto_ou_linha_truncada(self):
        for rows in [[HEADER[:-1], ["Arte", "10", "10", "10", "", "10", ""]],
                     [HEADER, ["Arte", "10", "10", "10", "10"]]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                _extrair_por_tabelas(pagina(rows), CONTEXT)

    def test_texto_linear_sem_posicoes_produz_erro(self):
        text = "Nome do Aluno: Ana\n" + " ".join(HEADER) + "\nArte 10 10 10 10 5"
        with self.assertRaisesRegex(ValueError, "colunas"):
            _extrair_por_texto(text)

    def test_texto_delimitado_preserva_colunas_vazias(self):
        text = "Nome do Aluno: Ana\nSituação Atual do Aluno: Em curso\n" + "|".join(HEADER) + "\nArte|10|10|10||10||5"
        rows = _extrair_por_texto(text)
        self.assertEqual([r["nota"] for r in rows], ["10", "10", "10", ""])
        self.assertTrue(all(r["media_final"] == "5" for r in rows))

    def test_transferidos_filtrados_antes_de_retorno(self):
        page = SimpleNamespace(extract_text=lambda **kw: "Nome do Aluno: Saiu\nSituação Atual do Aluno:  TrAnSfErIdA  ",
                               extract_tables=lambda: [[HEADER, ["Arte", "10", "", "", "", "10", "", "5"]]])
        from contextlib import nullcontext
        with patch("sistemas.medias.services.leitor_pdf.pdfplumber.open", return_value=nullcontext(SimpleNamespace(pages=[page]))):
            self.assertEqual(extrair_boletim_pdf("qualquer.pdf"), [])

    def test_multiplos_alunos_na_mesma_pagina_nao_mistura_contextos(self):
        from contextlib import nullcontext
        page = SimpleNamespace(extract_text=lambda **kw: "Nome do Aluno: Ana\nNome do Aluno: Bia\nDisciplina",
                               extract_tables=lambda: [[HEADER, ["Arte", "10", "", "", "", "10", "", "5"]]])
        with patch("sistemas.medias.services.leitor_pdf.pdfplumber.open", return_value=nullcontext(SimpleNamespace(pages=[page]))):
            with self.assertRaises(ValueError):
                extrair_boletim_pdf("multiplos.pdf")


class PDFsReaisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = Path(os.getenv("BOLETINS_PDF_DIR", "tests/fixtures/boletins"))
        if not cls.pasta.is_dir():
            raise unittest.SkipTest("PDFs externos ausentes; configure BOLETINS_PDF_DIR.")

    def conferir_pdf(self, nome):
        path = self.pasta / nome
        self.assertTrue(path.is_file(), f"PDF obrigatório ausente: {nome}")
        esperado = {}
        transferidos = set()
        ativos = set()
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages:
                text = p.extract_text() or ""
                aluno = re.search(r"Nome do Aluno:\s*([^\n]+)", text).group(1).strip()
                status = re.search(r"Situação Atual do Aluno:\s*([^\n]+)", text).group(1).strip()
                if status.casefold() in {"transferido", "transferida"}:
                    transferidos.add(aluno)
                    continue
                ativos.add(aluno)
                grade = [t for t in p.extract_tables() if t and t[0] == HEADER or
                         t and t[0] == ["Componente Curricular", *HEADER[1:]]]
                self.assertEqual(len(grade), 1)
                for cells in grade[0][1:]:
                    if not cells[0] or cells[0].startswith("Número de Faltas"):
                        break
                    self.assertEqual(len(cells), 8)
                    disciplina = " ".join(cells[0].split())
                    for i, bim in enumerate(BIMESTRES, 1):
                        esperado[(aluno, disciplina, bim)] = (cells[i] or "", cells[7] or "", status)
        resultado = extrair_boletim_pdf(path)
        obtido = {(r["nome_aluno"], r["disciplina"], r["bimestre"]):
                  (r["nota"], r["media_final"], r["situacao"]) for r in resultado}
        # Sem expor nomes/notas reais no log de falha.
        self.assertEqual(len(resultado), len(esperado))
        self.assertTrue(obtido == esperado, "Divergência entre células do PDF e registros extraídos")
        self.assertEqual(len({r["nome_aluno"] for r in resultado}), len(ativos))
        # Há um nome presente tanto em página ativa quanto transferida no 6º EF.
        # A situação pertence ao registro; nunca excluir o ativo por nome.
        self.assertFalse(any(r["situacao"].strip().casefold() in {"transferido", "transferida"} for r in resultado))
        from sistemas.medias.services.calculos import gerar_analises
        from sistemas.medias.services.media_service import calcular_gerador_medias
        analise = gerar_analises(resultado)
        gerador = calcular_gerador_medias(resultado, {})
        finais = [float(v[1].replace(",", ".")) for k, v in esperado.items()
                  if k[2] == BIMESTRES[0] and re.fullmatch(r"\d+(?:[,.]\d+)?", v[1])]
        self.assertEqual(analise["media_geral_turma"], round(sum(finais) / len(finais), 2))
        self.assertEqual(analise["media_geral_turma"], gerador["resultados"][0]["media_calculada"])
        self.assertEqual(gerador["total_notas_validas"], len(finais))
        self.assertNotIn("Ensino Religioso (Não Frequenta)", gerador["opcoes"]["disciplinas"])
        self.assertFalse(any(r["nota"] and r["nota"].upper() != "SN" for r in resultado if r["bimestre"] == BIMESTRES[3]))

    def test_6_ef(self): self.conferir_pdf("6º EF.pdf")
    def test_7_ef(self): self.conferir_pdf("7º EF.pdf")
    def test_8_ef(self): self.conferir_pdf("8º EF.pdf")
    def test_9_ef(self): self.conferir_pdf("9º EF.pdf")
    def test_1_em(self): self.conferir_pdf("1º EM.pdf")
    def test_2_em(self): self.conferir_pdf("2º EM.pdf")
    def test_3_em(self): self.conferir_pdf("3º EM.pdf")
