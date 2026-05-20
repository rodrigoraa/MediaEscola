from datetime import datetime
from pathlib import Path

import pandas as pd


def gerar_excel(pasta_exportacao, notas, analises, boletim_id=None):
    pasta_exportacao = Path(pasta_exportacao)
    pasta_exportacao.mkdir(exist_ok=True)

    sufixo = f"boletim_{boletim_id}" if boletim_id else "todos"
    nome = f"relatorio_{sufixo}_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    caminho = pasta_exportacao / nome

    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        pd.DataFrame(notas).to_excel(writer, sheet_name="Dados extraidos", index=False)
        _aba(writer, "Media por aluno", analises["media_por_aluno"])
        _aba(writer, "Media disciplina", analises["media_por_disciplina"])
        _aba(writer, "Media bimestre", analises["media_por_bimestre"])
        _aba(writer, "Aluno por bimestre", analises["media_aluno_por_bimestre"])
        _aba(writer, "Aluno disciplina", analises["media_aluno_por_disciplina"])
        _aba(writer, "Disciplina bimestre", analises["media_disciplina_por_bimestre"])
        _aba(writer, "Resumo disciplina", analises["resumo_geral_por_disciplina"])
        _aba(writer, "Abaixo da media", analises["alunos_abaixo_media"])
        _aba(writer, "Melhores medias", analises["melhores_medias"])
        _aba(writer, "Menor rendimento", analises["disciplinas_menor_rendimento"])

        pd.DataFrame(
            [{"Indicador": "Média geral da turma", "Valor": analises["media_geral_turma"]}]
        ).to_excel(writer, sheet_name="Resumo", index=False)

    return caminho


def _aba(writer, nome, dados):
    pd.DataFrame(dados).to_excel(writer, sheet_name=nome[:31], index=False)
