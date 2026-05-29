import pandas as pd
import math

def carregar_e_validar_dados(arquivo):
    """
    Lê o Excel, processa turmas e TRADUZ as indisponibilidades.
    Agora suporta formato 'DIA' (dia todo) e 'DIA:AULA' (aula específica).
    """
    erros = []
    avisos = []
    
    try:
        df_turmas = pd.read_excel(arquivo, sheet_name='Turmas', dtype=str)
        df_grade = pd.read_excel(arquivo, sheet_name='Grade_Curricular', dtype=str)
    except Exception as e:
        return None, None, [f"Erro ao abrir arquivo Excel: {str(e)}"], []

    turmas_config = {} 
    
    for _, row in df_turmas.iterrows():
        nome = str(row['Turma']).strip()
        carga = row.get('Aulas_Semanais', '25')
        try:
            turmas_config[nome] = int(float(carga))
        except:
            turmas_config[nome] = 25 
            avisos.append(f"Turma '{nome}' com carga inválida. Assumindo 25.")

    def processar_indisponibilidades(texto_bruto):
        """
        Retorna duas listas:
        1. Dias inteiros bloqueados (ex: [0, 4])
        2. Slots específicos bloqueados (ex: [(2, 3)]) -> (Quarta, 4ª aula)
        """
        bloqueios_dias = []
        bloqueios_slots = []
        
        if pd.isna(texto_bruto) or str(texto_bruto).strip() == '':
            return [], []
        
        texto = str(texto_bruto).upper()
        mapa = {'SEG': 0, 'TER': 1, 'QUA': 2, 'QUI': 3, 'SEX': 4, 'SAB': 5, 'DOM': 6}
        
        partes = texto.replace(';', ',').replace(' ', '').split(',')
        
        for p in partes:
            if not p: continue
            
            dia_idx = -1
            for chave, valor in mapa.items():
                if chave in p:
                    dia_idx = valor
                    break
            
            if dia_idx == -1: continue

            if ':' in p:
                try:
                    _, aula_str = p.split(':')
                    aula_idx = int(aula_str) - 1
                    bloqueios_slots.append((dia_idx, aula_idx))
                except:
                    pass
            else:
                bloqueios_dias.append(dia_idx)
        
        return sorted(list(set(bloqueios_dias))), sorted(list(set(bloqueios_slots)))

    grade_aulas = []
    cols_req = {'Professor', 'Materia', 'Turmas_Alvo', 'Aulas_Por_Turma'}
    
    if not cols_req.issubset(df_grade.columns):
        return None, None, [f"Faltam colunas na aba Grade_Curricular: {cols_req}"], []

    print("\n>>> INICIANDO LEITURA DAS INDISPONIBILIDADES (COM SUPORTE A HORÁRIOS):")
    
    for idx, row in df_grade.iterrows():
        prof = str(row['Professor']).strip()
        mat = str(row['Materia']).strip()
        turmas_str = str(row['Turmas_Alvo']).strip()
        qtd_str = str(row['Aulas_Por_Turma']).strip()
        
        bloq_raw = row.get('Indisponibilidade', '')
        
        b_dias, b_slots = processar_indisponibilidades(bloq_raw)

        if not prof or not mat or not turmas_str: continue

        try:
            qtd = int(float(qtd_str))
        except:
            erros.append(f"Linha {idx+2}: Quantidade inválida para {prof}.")
            continue

        lista_turmas = [t.strip() for t in turmas_str.replace(';', ',').split(',')]
        
        for turma in lista_turmas:
            if not turma: continue
            
            if turma not in turmas_config:
                turmas_config[turma] = 25
            
            grade_aulas.append({
                'id_linha': idx,
                'prof': prof,
                'materia': mat,
                'turma': turma,
                'qtd': qtd,
                'bloqueios_indices': b_dias,
                'bloqueios_slots': b_slots 
            })

    print(">>> FIM DA LEITURA.\n")

    demandas = {}
    for item in grade_aulas:
        t = item['turma']
        demandas[t] = demandas.get(t, 0) + item['qtd']
        
    for turma, carga_definida in turmas_config.items():
        carga_necessaria = demandas.get(turma, 0)
        if carga_necessaria > carga_definida:
            avisos.append(f"⚠️ Turma {turma}: Pedidos {carga_necessaria} > Vagas {carga_definida}. Expandindo capacidade...")
            turmas_config[turma] = carga_necessaria 

    return turmas_config, grade_aulas, erros, avisos