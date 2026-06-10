# exporters.py
import pandas as pd
import io
import xlsxwriter


def _eh_hora_atividade(row):
    return row.get('materia') == 'Hora Atividade' or str(row.get('turma', '')).startswith('H.A. (')


def _escrever_grade(writer, workbook, sheet_name, grade_visual):
    fmt_header = workbook.add_format({
        'bold': True,
        'font_size': 11,
        'bg_color': '#F2F2F2',
        'font_color': '#000000',
        'border': 1,
        'border_color': '#bfbfbf',
        'align': 'center',
        'valign': 'vcenter'
    })

    fmt_index = workbook.add_format({
        'bold': True,
        'font_size': 10,
        'bg_color': '#F2F2F2',
        'border': 1,
        'border_color': '#bfbfbf',
        'align': 'center',
        'valign': 'vcenter'
    })

    fmt_celula = workbook.add_format({
        'font_size': 10,
        'text_wrap': True,
        'align': 'center',
        'valign': 'vcenter',
        'border': 1,
        'border_color': '#bfbfbf'
    })

    grade_visual.to_excel(writer, sheet_name=sheet_name)
    worksheet = writer.sheets[sheet_name]

    for col_num, value in enumerate(grade_visual.columns.values):
        worksheet.write(0, col_num + 1, value, fmt_header)

    for row_num in range(len(grade_visual.index)):
        worksheet.write(row_num + 1, 0, grade_visual.index[row_num], fmt_index)

        for col_num in range(len(grade_visual.columns)):
            conteudo = grade_visual.iloc[row_num, col_num]
            worksheet.write(row_num + 1, col_num + 1, conteudo, fmt_celula)

    worksheet.set_column(0, 0, 15)
    worksheet.set_column(1, len(grade_visual.columns), 25)
    for row_num in range(1, len(grade_visual.index) + 1):
        worksheet.set_row(row_num, 45)


def gerar_excel_colorido(resultados, dias_list):
    """
    Gera um Excel estilo 'Corporativo/Clean':
    - Sem cores de fundo nas matérias.
    - Cabeçalhos em cinza suave.
    - Foco na legibilidade e impressão.
    """
    output = io.BytesIO()
    df_resultados = pd.DataFrame(resultados)

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        mascara_ha = df_resultados.apply(_eh_hora_atividade, axis=1)
        df_aulas = df_resultados[~mascara_ha]
        df_ha = df_resultados[mascara_ha]

        turmas_unicas = sorted(list(set(df_aulas['turma'])))
        
        for turma in turmas_unicas:
            df_t = df_aulas[df_aulas['turma'] == turma]
            
            rows = [f"{i+1}ª Aula" for i in range(6)]
            grade_visual = pd.DataFrame("", index=rows, columns=dias_list)

            for _, row in df_t.iterrows():
                d_idx = row['dia_idx']
                a_idx = row['aula_idx']
                conteudo = f"{row['materia']}\n({row['prof']})"
                grade_visual.iat[a_idx, d_idx] = conteudo

            sheet_name = turma.replace(":", "").replace("/", "").strip()[:30]
            _escrever_grade(writer, workbook, sheet_name, grade_visual)

        if not df_ha.empty:
            registros = []
            for _, row in df_ha.iterrows():
                registros.append({
                    "Professor": row['prof'],
                    "Dia": dias_list[row['dia_idx']],
                    "Aula": f"{row['aula_idx'] + 1}ª Aula",
                    "Atividade": "H.A./PL",
                })
            df_pl = pd.DataFrame(registros).sort_values(["Professor", "Dia", "Aula"])
            df_pl.to_excel(writer, sheet_name="Hora Atividade", index=False)
            worksheet = writer.sheets["Hora Atividade"]
            worksheet.set_column(0, 0, 28)
            worksheet.set_column(1, 3, 18)

    return output.getvalue()
