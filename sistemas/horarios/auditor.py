def auditoria_pre_solver(grade_aulas, turmas_config, dias_list, itinerarios_lista=None, slots_itinerario_perm=None):
    """
    Verifica se a quantidade de aulas solicitadas cabe na semana antes de chamar o solver.
    Retorna listas de erros impeditivos e avisos.
    """
    erros = []
    avisos = []
    itinerarios_lista = set(itinerarios_lista or [])
    slots_itinerario_perm = set(slots_itinerario_perm or [])
    mapa_dias = {'SEG': 0, 'TER': 1, 'QUA': 2, 'QUI': 3, 'SEX': 4, 'SAB': 5, 'DOM': 6}
    dias_indices = [mapa_dias.get(str(dia).upper()[:3], idx) for idx, dia in enumerate(dias_list)]

    def slots_da_turma(nome_turma, materia=""):
        if materia == 'Hora Atividade':
            return 5
        carga = turmas_config.get(nome_turma, 25)
        return 6 if carga > 25 else 5

    max_slots_semana_professor = len(dias_list) * 6

    carga_prof = {}
    for item in grade_aulas:
        prof = item['prof']
        carga_prof[prof] = carga_prof.get(prof, 0) + item['qtd']

    for prof, qtd in carga_prof.items():
        if qtd > max_slots_semana_professor:
            erros.append(
                f"Professor {prof} tem {qtd} aulas atribuídas, mas a semana só tem "
                f"{max_slots_semana_professor} espaços possíveis."
            )

    carga_turma = {}
    for item in grade_aulas:
        turma = item['turma']
        carga_turma[turma] = carga_turma.get(turma, 0) + item['qtd']

    for turma, qtd in carga_turma.items():
        limite_turma = len(dias_list) * slots_da_turma(turma)
        if qtd > limite_turma:
            erros.append(
                f"Turma {turma} tem {qtd} aulas cadastradas, mas só há "
                f"{limite_turma} espaços na semana selecionada."
            )

    for item in grade_aulas:
        turma = item['turma']
        materia = item['materia']
        prof = item['prof']
        qtd = item['qtd']
        slots_por_dia = slots_da_turma(turma, materia)
        bloqueios_dias = set(item.get('bloqueios_indices', []))
        bloqueios_slots = set(tuple(slot) for slot in item.get('bloqueios_slots', []))

        disponiveis = 0
        for dia_idx in dias_indices:
            if dia_idx in bloqueios_dias:
                continue
            for aula_idx in range(slots_por_dia):
                if (dia_idx, aula_idx) in bloqueios_slots:
                    continue
                if materia in itinerarios_lista and slots_itinerario_perm and aula_idx not in slots_itinerario_perm:
                    continue
                disponiveis += 1

        if qtd > disponiveis:
            erros.append(
                f"{prof} / {materia} / {turma}: precisa de {qtd} aulas, mas só tem "
                f"{disponiveis} horários disponíveis após bloqueios e regras."
            )

    return erros, avisos
