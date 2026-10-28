import unittest

from sistemas.medias.services.calculos import gerar_analises
from sistemas.medias.services.media_service import (
    calcular_gerador_medias, classificarSituacaoAluno, normalizar_nota,
    preparar_dataframe,
)


def linha(aluno="Ana", disciplina="Matemática", nota="10", final="5", bimestre="1º Bimestre", **extra):
    return dict(nome_aluno=aluno, disciplina=disciplina, nota=nota,
                media_final=final, bimestre=bimestre, situacao="Em curso", **extra)


class CalculosTest(unittest.TestCase):
    def resultado(self, rows, relatorio="media_geral_turma", **filtros):
        return calcular_gerador_medias(rows, dict(relatorio=relatorio, **filtros))

    def test_normalizacao_intervalo_sn_zero_e_invalidos(self):
        for valor in [None, "", "  SN ", "sn", "inválido", "-1", "10,1", "inf", "NaN"]:
            with self.subTest(valor=valor):
                self.assertIsNone(normalizar_nota(valor))
        for valor, esperado in [("0,0", 0), (0, 0), (" 10,0 ", 10), ("5.5", 5.5)]:
            self.assertEqual(normalizar_nota(valor), esperado)

    def test_media_final_num_e_situacao_original(self):
        df = preparar_dataframe([linha()])
        self.assertIn("media_final_num", df.columns)
        self.assertEqual(df.iloc[0]["media_final_num"], 5)
        self.assertEqual(df.iloc[0]["situacao"], "Em curso")

    def test_final_cinco_prevalece_sobre_primeiro_bimestre_dez(self):
        rows = [linha()] + [linha(nota="", bimestre=f"{i}º Bimestre") for i in (2, 3, 4)]
        for rel in ["media_geral_turma", "media_turma_disciplina", "media_geral_aluno", "media_aluno_disciplina"]:
            with self.subTest(rel=rel):
                result = self.resultado(rows, rel)
                self.assertEqual(result["resultados"][0]["media_calculada"], 5)
                self.assertEqual(result["total_notas_validas"], 1)
                self.assertEqual(result["estatisticas"]["media_geral"], 5)

    def test_bimestres_usam_nota_e_ignoram_final(self):
        for rel in ["media_turma_bimestre", "media_turma_disciplina_bimestre", "media_aluno_bimestre", "media_aluno_disciplina_bimestre"]:
            with self.subTest(rel=rel):
                self.assertEqual(self.resultado([linha()], rel)["resultados"][0]["media_calculada"], 10)

    def test_fallback_somente_final_vazia(self):
        rows = [linha(nota="0,0", final=""), linha(nota="10", final=" ", bimestre="2º Bimestre"),
                linha(nota="SN", final="", bimestre="3º Bimestre")]
        self.assertEqual(self.resultado(rows)["resultados"][0]["media_calculada"], 5)
        for final in ["SN", "inválida", "11"]:
            self.assertEqual(self.resultado([linha(final=final)])["resultados"], [])

    def test_anuais_uma_entrada_por_disciplina_sem_peso_por_bimestres(self):
        rows = [linha(final="4", bimestre=f"{i}º Bimestre") for i in (1, 2, 3)]
        rows += [linha(disciplina="Arte", final="10")]
        result = self.resultado(rows)
        self.assertEqual(result["resultados"][0]["media_calculada"], 7)
        self.assertEqual(result["resultados"][0]["quantidade"], 2)

    def test_sn_e_sem_nota_fora_de_filtros_contagens_rankings(self):
        rows = [linha(nota="SN", final="SN", disciplina="RA"),
                linha(nota="", final="", disciplina="Ensino Religioso (Não Frequenta)"),
                linha(nota="0,0", final="0,0", disciplina="Arte")]
        result = self.resultado(rows, "media_aluno_disciplina")
        self.assertEqual(result["opcoes"]["disciplinas"], ["Arte"])
        self.assertEqual(len(result["resultados"]), 1)
        self.assertEqual(result["estatisticas"]["notas_validas"], 1)

    def test_ranking_anual_por_finais(self):
        result = self.resultado([linha(), linha(aluno="Bia", nota="1", final="8")], "ranking_geral")
        self.assertEqual([(r["aluno"], r["media_calculada"], r["ranking"]) for r in result["resultados"]],
                         [("Bia", 8, 1), ("Ana", 5, 2)])

    def test_transferidos_excluidos_tambem_dos_calculos(self):
        rows = [linha(), {**linha(aluno="Saiu"), "situacao": " \tTRANSFERIDA \n"}]
        self.assertEqual(len(self.resultado(rows, "media_geral_aluno")["resultados"]), 1)

    def test_classificacao_nao_declara_resultado_escolar(self):
        self.assertEqual(classificarSituacaoAluno(8), "Acima da média")
        self.assertEqual(classificarSituacaoAluno(5), "Em atenção")
        self.assertEqual(classificarSituacaoAluno(0), "Abaixo da média")

    def test_consistencia_analises_e_gerador_todas_metricas(self):
        rows = [linha(), linha(aluno="Bia", nota="6", final="8"),
                linha(disciplina="Arte", nota="9", final=""),
                linha(disciplina="Arte", nota="4", final="", bimestre="2º Bimestre")]
        analises = gerar_analises(rows)
        self.assertEqual(analises["media_geral_turma"], self.resultado(rows)["resultados"][0]["media_calculada"])
        for key, report, cols in [
            ("media_por_aluno", "media_geral_aluno", ["aluno"]),
            ("media_por_disciplina", "media_turma_disciplina", ["disciplina"]),
            ("media_por_bimestre", "media_turma_bimestre", ["bimestre"]),
            ("media_aluno_por_bimestre", "media_aluno_bimestre", ["aluno", "bimestre"]),
            ("media_aluno_por_disciplina", "media_aluno_disciplina", ["aluno", "disciplina"]),
            ("media_disciplina_por_bimestre", "media_turma_disciplina_bimestre", ["disciplina", "bimestre"]),
        ]:
            with self.subTest(key=key):
                a = {tuple(r[c] for c in cols): (r["media"], r["quantidade"]) for r in analises[key]}
                b = {tuple(r[c] for c in cols): (r["media_calculada"], r["quantidade"]) for r in self.resultado(rows, report)["resultados"]}
                self.assertEqual(a, b)

    def test_final_valida_zero_ponderada_e_descarte_preservados(self):
        for tipo in ["media_simples", "media_ponderada", "descartar_menor"]:
            self.assertEqual(self.resultado([linha(final="0,0")], tipo_calculo=tipo)["resultados"][0]["media_calculada"], 0)
        rows = [linha(nota="2", final="", peso=1), linha(nota="8", final="", peso=3, bimestre="2º Bimestre")]
        self.assertEqual(self.resultado(rows, "media_geral_aluno", tipo_calculo="media_ponderada")["resultados"][0]["media_calculada"], 5)

    def test_vazio_retorna_sem_ranking(self):
        self.assertEqual(self.resultado([])["resultados"], [])
        self.assertEqual(self.resultado([linha(nota="SN", final="SN")])["estatisticas"]["notas_validas"], 0)

    def test_filtro_bimestral_e_estatisticas_periodo(self):
        rows = [linha(), linha(nota="2", bimestre="2º Bimestre")]
        anual = self.resultado(rows, bimestre="2º Bimestre")
        self.assertEqual(anual["resultados"][0]["media_calculada"], 5)
        bim = self.resultado(rows, "media_turma_bimestre", bimestre="2º Bimestre")
        self.assertEqual(bim["resultados"][0]["media_calculada"], 2)
        self.assertEqual(self.resultado(rows, "estatisticas")["estatisticas"]["media_geral"], 5)
        self.assertEqual(self.resultado(rows, "estatisticas", bimestre="2º Bimestre")["estatisticas"]["media_geral"], 2)

    def test_calculos_publicos_bimestrais_ignoram_sn_no_denominador(self):
        from sistemas.medias.services.media_service import (
            calcularMediaAlunoPorBimestre, calcularMediaTurmaPorDisciplinaEBimestre,
            calcularMediaAlunoPorDisciplinaEBimestre,
        )
        df = preparar_dataframe([linha(), linha(nota="SN")])
        for calcular in [calcularMediaAlunoPorBimestre, calcularMediaTurmaPorDisciplinaEBimestre, calcularMediaAlunoPorDisciplinaEBimestre]:
            with self.subTest(calcular=calcular.__name__):
                result = calcular(df)
                self.assertEqual(result[0]["quantidade"], 1)

    def test_graficos_mantem_base_bimestral_e_anual(self):
        result = self.resultado([linha()])
        self.assertEqual(result["graficos"]["bimestres"][0]["media_calculada"], 10)
        self.assertEqual(result["graficos"]["disciplinas"][0]["media_calculada"], 5)

    def test_filtro_bimestre_nao_encurta_base_do_grafico_anual(self):
        rows = [linha(nota="10", final=""), linha(nota="2", final="", bimestre="2º Bimestre")]
        result = self.resultado(rows, "media_turma_bimestre", bimestre="2º Bimestre")
        self.assertEqual(result["resultados"][0]["media_calculada"], 2)
        self.assertEqual(result["graficos"]["disciplinas"][0]["media_calculada"], 6)

    def test_ponderacao_e_descarte_bimestrais_preservados(self):
        rows = [linha(nota="2", peso=1), linha(aluno="Bia", nota="8", peso=3)]
        self.assertEqual(self.resultado(rows, "media_turma_bimestre", tipo_calculo="media_ponderada")["resultados"][0]["media_calculada"], 6.5)
        self.assertEqual(self.resultado(rows, "media_turma_bimestre", tipo_calculo="descartar_menor")["resultados"][0]["media_calculada"], 8)

    def test_conflito_de_finais_e_visivel_no_gerador_e_analise(self):
        rows = [linha(), linha(final="6", bimestre="2º Bimestre")]
        result = self.resultado(rows)
        self.assertEqual(result["resultados"], [])
        self.assertTrue(result.get("avisos"))
        self.assertTrue(gerar_analises(rows).get("avisos"))
