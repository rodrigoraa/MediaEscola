def auditoria_pre_solver(grade_aulas, turmas_config, dias_list):
    """
    Verifica se a quantidade de aulas solicitadas cabe na semana.
    Retorna listas de erros (impeditivos) e avisos (alertas).
    """
    erros = []
    avisos = []

    slots_por_dia = 6
    max_slots_semana = len(dias_list) * slots_por_dia
    
    carga_prof = {}
    for item in grade_aulas:
        p = item['prof']
        carga_prof[p] = carga_prof.get(p, 0) + item['qtd']
    
    for prof, qtd in carga_prof.items():
        if qtd > max_slots_semana:
            erros.append(f"❌ O Prof. **{prof}** tem {qtd} aulas atribuídas, mas a semana só tem {max_slots_semana} espaços possíveis.")

    carga_turma = {}
    for item in grade_aulas:
        t = item['turma']
        carga_turma[t] = carga_turma.get(t, 0) + item['qtd']
        
    for turma, qtd in carga_turma.items():
        limite_turma = turmas_config.get(turma, 25)
        if qtd > limite_turma + 2:
            erros.append(f"❌ A turma **{turma}** tem {qtd} aulas cadastradas, mas o limite configurado é próximo de {limite_turma}.")
            
    return erros, avisos