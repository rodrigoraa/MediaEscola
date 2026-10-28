"""Adaptador legado: regras e agregações pertencem ao serviço de médias."""

from .media_service import (
    LIMITE_RECUPERACAO_PADRAO, MEDIA_MINIMA_PADRAO,
    calcular_gerador_medias, resumir_disciplinas,
)


def gerar_analises(notas, media_minima=MEDIA_MINIMA_PADRAO, limite_recuperacao=LIMITE_RECUPERACAO_PADRAO):
    def calcular(relatorio, **filtros):
        return calcular_gerador_medias(notas, {
            "relatorio": relatorio, "media_minima": media_minima,
            "limite_recuperacao": limite_recuperacao,
            **filtros,
        })

    def linhas(relatorio, colunas, **filtros):
        return [{**{c: r[c] for c in colunas}, "media": r["media_calculada"],
                 "quantidade": r["quantidade"]}
                for r in calcular(relatorio, **filtros)["resultados"]]

    alunos = linhas("media_geral_aluno", ["aluno"])
    disciplinas = linhas("media_turma_disciplina", ["disciplina"])
    resultado_geral = calcular("media_geral_turma")
    geral = resultado_geral["resultados"]
    minimo = resultado_geral["media_minima"]
    return {
        "avisos": resultado_geral["avisos"],
        "media_minima": minimo,
        "media_por_aluno": alunos,
        "media_por_disciplina": disciplinas,
        "media_geral_turma": geral[0]["media_calculada"] if geral else None,
        "media_por_bimestre": linhas("media_turma_bimestre", ["bimestre"]),
        "media_aluno_por_bimestre": linhas("media_aluno_bimestre", ["aluno", "bimestre"]),
        "media_aluno_por_disciplina": linhas("media_aluno_disciplina", ["aluno", "disciplina"]),
        "media_disciplina_por_bimestre": linhas("media_turma_disciplina_bimestre", ["disciplina", "bimestre"]),
        "resumo_geral_por_disciplina": resumir_disciplinas(notas, minimo),
        "alunos_abaixo_media": sorted(linhas("media_geral_aluno", ["aluno"], desempenho="abaixo_media"), key=lambda r: r["media"]),
        "melhores_medias": alunos[:10],
        "disciplinas_menor_rendimento": sorted(disciplinas, key=lambda r: r["media"])[:10],
    }
