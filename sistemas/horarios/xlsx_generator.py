import pandas as pd
from io import BytesIO

def gerar_modelo_excel():
    """
    Gera o modelo padrão de horários na memória (buffer)
    para o usuário baixar.
    """
    output = BytesIO()
    
    df_turmas = pd.DataFrame([
        {'Turma': '6º Ano - Ensino Fundamental', 'Aulas_Semanais': 25},
        {'Turma': '7º Ano - Ensino Fundamental', 'Aulas_Semanais': 25},
        {'Turma': '8º Ano - Ensino Fundamental', 'Aulas_Semanais': 25},
        {'Turma': '9º Ano - Ensino Fundamental', 'Aulas_Semanais': 25},
        {'Turma': '1º Ano - Ensino Médio', 'Aulas_Semanais': 30},
        {'Turma': '2º Ano - Ensino Médio', 'Aulas_Semanais': 30},
        {'Turma': '3º Ano - Ensino Médio', 'Aulas_Semanais': 30},
    ])
    
    df_grade = pd.DataFrame([
        {
            'Professor': 'Beatriz Lima',
            'Materia': 'UC 2',
            'Turmas_Alvo': '1º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Beatriz Lima',
            'Materia': 'Geografia',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental, 1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 2,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Bianca Ferreira',
            'Materia': 'UC 2',
            'Turmas_Alvo': '3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Bianca Ferreira',
            'Materia': 'Química',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Claudia Pavão',
            'Materia': 'Matemática - RA',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Claudia Pavão',
            'Materia': 'Matemática',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental',
            'Aulas_Por_Turma': 3,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Clíssia Fernanda',
            'Materia': 'Matemática - RA',
            'Turmas_Alvo': '8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental, 1º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Clíssia Fernanda',
            'Materia': 'Matemática',
            'Turmas_Alvo': '9º Ano - Ensino Fundamental, 1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 3,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Clíssia Fernanda',
            'Materia': 'UC CNT',
            'Turmas_Alvo': '3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Clíssia Fernanda',
            'Materia': 'UC LGG',
            'Turmas_Alvo': '2º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Clíssia Fernanda',
            'Materia': 'Geometria',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Elessandra Maria',
            'Materia': 'Língua Portuguesa - RA',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Elessandra Maria',
            'Materia': 'Língua Portuguesa',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental, 1º Ano - Ensino Médio',
            'Aulas_Por_Turma': 3,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Gabriel José',
            'Materia': 'UC 4',
            'Turmas_Alvo': '2º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Gabriel José',
            'Materia': 'Língua Inglesa',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental, 1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 2,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Gabriela Fernanda',
            'Materia': 'Artes',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Gabriela Fernanda',
            'Materia': 'UC 2',
            'Turmas_Alvo': '2º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Gabriela Fernanda',
            'Materia': 'Artes',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental',
            'Aulas_Por_Turma': 2,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Gabriely Silva',
            'Materia': 'UC 3',
            'Turmas_Alvo': '3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Gabriely Silva',
            'Materia': 'UC 4',
            'Turmas_Alvo': '3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Gabriely Silva',
            'Materia': 'Física',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 2,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Jaine de Lima',
            'Materia': 'Ciências',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental',
            'Aulas_Por_Turma': 4,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Jaine de Lima',
            'Materia': 'Biologia',
            'Turmas_Alvo': '3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 2,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Janiely Lopes',
            'Materia': 'Educação Física',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Janiely Lopes',
            'Materia': 'UC 3',
            'Turmas_Alvo': '2º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Janiely Lopes',
            'Materia': 'Educação Física',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental',
            'Aulas_Por_Turma': 2,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Pâmela Sabrina',
            'Materia': 'UC 1',
            'Turmas_Alvo': '1º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Pâmela Sabrina',
            'Materia': 'História',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental, 1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 2,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Patrícia da Silva',
            'Materia': 'Leitura e Produção Textual',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Patrícia da Silva',
            'Materia': 'Língua Portuguesa - RA',
            'Turmas_Alvo': '9º Ano - Ensino Fundamental',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Patrícia da Silva',
            'Materia': 'Literatura e Produção Textual',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Patrícia da Silva',
            'Materia': 'Língua Portuguesa - RA LGG',
            'Turmas_Alvo': '2º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Patrícia da Silva',
            'Materia': 'Língua Portuguesa - RA CHS',
            'Turmas_Alvo': '1º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Patrícia da Silva',
            'Materia': 'Língua Portuguesa',
            'Turmas_Alvo': '2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 3,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Patrícia da Silva',
            'Materia': 'UC 4',
            'Turmas_Alvo': '2º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Patrícia da Silva',
            'Materia': 'Língua Portuguesa - RA CNT',
            'Turmas_Alvo': '3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Vanderson dos Santos',
            'Materia': 'Filosofia',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Vanderson dos Santos',
            'Materia': 'Sociologia',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Vanderson dos Santos',
            'Materia': 'UC 3',
            'Turmas_Alvo': '1º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Vanderson dos Santos',
            'Materia': 'UC 4 CHS',
            'Turmas_Alvo': '1º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Viviane Aparecida',
            'Materia': 'UC 1',
            'Turmas_Alvo': '3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Viviane Aparecida',
            'Materia': 'TVT',
            'Turmas_Alvo': '6º Ano - Ensino Fundamental, 7º Ano - Ensino Fundamental, 8º Ano - Ensino Fundamental, 9º Ano - Ensino Fundamental',
            'Aulas_Por_Turma': 2,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Viviane Aparecida',
            'Materia': 'Biologia',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio',
            'Aulas_Por_Turma': 2,
            'Indisponibilidade': ''
        },
        {
            'Professor': 'Viviane Aparecida',
            'Materia': 'TVT',
            'Turmas_Alvo': '1º Ano - Ensino Médio, 2º Ano - Ensino Médio, 3º Ano - Ensino Médio',
            'Aulas_Por_Turma': 1,
            'Indisponibilidade': ''
        },
    ])
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        df_turmas.to_excel(writer, sheet_name='Turmas', index=False)
        worksheet = writer.sheets['Turmas']
        worksheet.set_column('A:A', 35)
        worksheet.set_column('B:B', 15)
        
        df_grade.to_excel(writer, sheet_name='Grade_Curricular', index=False)
        worksheet = writer.sheets['Grade_Curricular']
        worksheet.set_column('A:A', 24)
        worksheet.set_column('B:B', 30)
        worksheet.set_column('C:C', 120)
        worksheet.set_column('D:E', 18)

    return output.getvalue()
