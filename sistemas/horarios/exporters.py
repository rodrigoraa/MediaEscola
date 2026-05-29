# exporters.py
import pandas as pd
import io
import xlsxwriter

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

        turmas_unicas = sorted(list(set(df_resultados['turma'])))
        
        for turma in turmas_unicas:
            df_t = df_resultados[df_resultados['turma'] == turma]
            
            rows = [f"{i+1}ª Aula" for i in range(6)]
            grade_visual = pd.DataFrame("", index=rows, columns=dias_list)

            for _, row in df_t.iterrows():
                d_idx = row['dia_idx']
                a_idx = row['aula_idx']
                conteudo = f"{row['materia']}\n({row['prof']})"
                grade_visual.iat[a_idx, d_idx] = conteudo

            sheet_name = turma.replace(":", "").replace("/", "").strip()[:30]
            
            grade_visual.to_excel(writer, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
                        
            for col_num, value in enumerate(grade_visual.columns.values):
                worksheet.write(0, col_num + 1, value, fmt_header)
                
            for row_num in range(len(rows)):
                worksheet.write(row_num + 1, 0, rows[row_num], fmt_index)
                
                for col_num in range(len(dias_list)):
                    conteudo = grade_visual.iloc[row_num, col_num]
                    worksheet.write(row_num + 1, col_num + 1, conteudo, fmt_celula)

            worksheet.set_column(0, 0, 15)
            worksheet.set_column(1, len(dias_list), 25)
            for row_num in range(1, len(rows) + 1):
                worksheet.set_row(row_num, 45)

    return output.getvalue()