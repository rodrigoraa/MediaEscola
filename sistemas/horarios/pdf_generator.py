from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from io import BytesIO
import pandas as pd

COR_CABECALHO = colors.Color(0.2, 0.2, 0.2)
COR_TEXTO_CABECALHO = colors.white
COR_LINHAS_GRADE = colors.black
COR_FUNDO_HORARIO = colors.Color(0.96, 0.96, 0.96)
COR_INTERVALO = colors.Color(0.9, 0.9, 0.9)
COR_ZEBRA_PAR = colors.white
COR_ZEBRA_IMPAR = colors.Color(0.98, 0.98, 0.98)

def montar_tabela_turma(turma, df_t, dias_semana, styles):
    """
    Função auxiliar que cria a tabela (objeto Flowable) para uma única turma.
    """
    title_style = ParagraphStyle(
        'TurmaTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.black,
        alignment=1,
        spaceAfter=5
    )
    
    elementos_locais = []
    elementos_locais.append(Paragraph(f"<b>Turma: {turma}</b>", title_style))

    max_idx = df_t['aula_idx'].max()
    qtd_slots = max(5, int(max_idx) + 1)
    
    header = ['Horário'] + dias_semana
    data = [header]
    
    row_idx_intervalo = -1 

    for i in range(qtd_slots):
        if i == 3:
            row_intervalo = ["INTERVALO"] * (len(dias_semana) + 1)
            data.append(row_intervalo)
            row_idx_intervalo = len(data) - 1
        
        row = [f"{i+1}ª Aula"]
        for dia_idx, _ in enumerate(dias_semana):
            aula = df_t[(df_t['dia_idx'] == dia_idx) & (df_t['aula_idx'] == i)]
            if not aula.empty:
                materia = aula.iloc[0]['materia']
                prof = aula.iloc[0]['prof']
                texto_celula = f"<font size=9><b>{materia}</b></font><br/><font size=7 color='grey'>{prof}</font>"
            else:
                texto_celula = "-"
            
            cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], alignment=1, leading=8)
            row.append(Paragraph(texto_celula, cell_style))
        
        data.append(row)

    tabela = Table(data, colWidths=[2.2*cm] + [4.8*cm]*len(dias_semana))
    
    estilos_tabela = [
        ('BACKGROUND', (0, 0), (-1, 0), COR_CABECALHO),
        ('TEXTCOLOR', (0, 0), (-1, 0), COR_TEXTO_CABECALHO),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        
        ('GRID', (0, 0), (-1, -1), 0.5, COR_LINHAS_GRADE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        ('BACKGROUND', (0, 1), (0, -1), COR_FUNDO_HORARIO),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('FONTSIZE', (0, 1), (0, -1), 8),
    ]

    for i in range(1, len(data)):
        if i == row_idx_intervalo: continue
        bg_color = COR_ZEBRA_IMPAR if i % 2 == 1 else COR_ZEBRA_PAR
        estilos_tabela.append(('BACKGROUND', (1, i), (-1, i), bg_color))

    if row_idx_intervalo != -1:
        estilos_tabela.append(('SPAN', (0, row_idx_intervalo), (-1, row_idx_intervalo)))
        estilos_tabela.append(('BACKGROUND', (0, row_idx_intervalo), (-1, row_idx_intervalo), COR_INTERVALO))
        estilos_tabela.append(('TEXTCOLOR', (0, row_idx_intervalo), (-1, row_idx_intervalo), colors.black))
        estilos_tabela.append(('FONTNAME', (0, row_idx_intervalo), (-1, row_idx_intervalo), 'Helvetica-Bold'))
        estilos_tabela.append(('ALIGN', (0, row_idx_intervalo), (-1, row_idx_intervalo), 'CENTER'))
        estilos_tabela.append(('FONTSIZE', (0, row_idx_intervalo), (-1, row_idx_intervalo), 8))
        estilos_tabela.append(('TOPPADDING', (0, row_idx_intervalo), (-1, row_idx_intervalo), 2))
        estilos_tabela.append(('BOTTOMPADDING', (0, row_idx_intervalo), (-1, row_idx_intervalo), 2))

    tabela.setStyle(TableStyle(estilos_tabela))
    elementos_locais.append(tabela)
    return elementos_locais

def gerar_pdf_bonito(resultados, turmas_config, dias_semana):
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=0.5*cm,
        leftMargin=0.5*cm,
        topMargin=1*cm,
        bottomMargin=1*cm
    )

    elements = []
    styles = getSampleStyleSheet()
    
    if not resultados:
        return None
    
    df = pd.DataFrame(resultados)
    turmas_ordenadas = sorted(list(turmas_config.keys()))
    
    turmas_validas = [t for t in turmas_ordenadas if t in df['turma'].values]

    for i in range(0, len(turmas_validas), 2):
        
        turma1 = turmas_validas[i]
        df_t1 = df[df['turma'] == turma1]
        objs1 = montar_tabela_turma(turma1, df_t1, dias_semana, styles)
        elements.extend(objs1)
        
        if i + 1 < len(turmas_validas):
            turma2 = turmas_validas[i+1]
            df_t2 = df[df['turma'] == turma2]
            
            elements.append(Spacer(1, 1.5*cm))
            
            objs2 = montar_tabela_turma(turma2, df_t2, dias_semana, styles)
            elements.extend(objs2)
        
        elements.append(PageBreak())

    doc.build(elements)
    buffer.seek(0)
    return buffer