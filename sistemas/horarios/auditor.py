from collections import Counter, defaultdict


MATERIA_HORA_ATIVIDADE = "Hora Atividade"


def eh_hora_atividade(item):
    if isinstance(item, dict):
        return item.get("materia") == MATERIA_HORA_ATIVIDADE
    return item == MATERIA_HORA_ATIVIDADE


def slots_da_turma(turma, turmas_config, materia=""):
    if materia == MATERIA_HORA_ATIVIDADE:
        return 5
    return 6 if turmas_config.get(turma, 25) > 25 else 5


def _bloqueado(item, dia_idx, aula_idx):
    return dia_idx in item.get("bloqueios_indices", []) or (dia_idx, aula_idx) in item.get("bloqueios_slots", [])


def _formatar_slot(dias_list, dia_idx, aula_idx):
    dia = dias_list[dia_idx] if 0 <= dia_idx < len(dias_list) else f"Dia {dia_idx + 1}"
    return f"{dia}, {aula_idx + 1}ª aula"


def _dia_absoluto(dia_nome, fallback):
    mapa = {"SEG": 0, "TER": 1, "QUA": 2, "QUI": 3, "SEX": 4, "SAB": 5, "DOM": 6}
    return mapa.get(str(dia_nome).upper()[:3], fallback)


def auditoria_pre_solver(grade_aulas, turmas_config, dias_list, itinerarios_lista=None, slots_itinerario_perm=None):
    """
    Verifica se a quantidade de aulas solicitadas cabe na semana antes de chamar o solver.
    Retorna listas de erros impeditivos e avisos.
    """
    erros = []
    avisos = []

    if not dias_list:
        return ["Selecione pelo menos um dia letivo."], []

    itinerarios_lista = set(itinerarios_lista or [])
    slots_itinerario_perm = set(slots_itinerario_perm or [])

    carga_prof = defaultdict(int)
    for item in grade_aulas:
        carga_prof[item["prof"]] += int(item["qtd"])

    max_slots_semana_professor = len(dias_list) * 6
    for prof, qtd in sorted(carga_prof.items()):
        if qtd > max_slots_semana_professor:
            erros.append(
                f"Professor {prof} tem {qtd} aulas atribuídas, mas a semana só tem "
                f"{max_slots_semana_professor} espaços possíveis."
            )

    carga_turma = defaultdict(int)
    for item in grade_aulas:
        if eh_hora_atividade(item):
            continue
        carga_turma[item["turma"]] += int(item["qtd"])

    for turma, qtd in sorted(carga_turma.items()):
        limite_configurado = turmas_config.get(turma, 25)
        limite_semana = len(dias_list) * slots_da_turma(turma, turmas_config)
        if qtd != limite_configurado:
            avisos.append(
                f"A turma {turma} está com {qtd} aulas cadastradas para uma carga configurada de {limite_configurado}."
            )
        if qtd > limite_configurado:
            erros.append(f"Turma {turma} tem {qtd} aulas cadastradas, mas o limite configurado é {limite_configurado}.")
        if qtd > limite_semana:
            erros.append(f"Turma {turma} tem {qtd} aulas cadastradas, mas só há {limite_semana} espaços na semana selecionada.")

    for item in grade_aulas:
        turma = item["turma"]
        materia = item["materia"]
        prof = item["prof"]
        qtd = int(item["qtd"])
        disponiveis = 0

        for dia_pos, dia_nome in enumerate(dias_list):
            dia_abs = _dia_absoluto(dia_nome, dia_pos)
            for aula_idx in range(slots_da_turma(turma, turmas_config, materia)):
                if _bloqueado(item, dia_abs, aula_idx):
                    continue
                if materia in itinerarios_lista and slots_itinerario_perm and aula_idx not in slots_itinerario_perm:
                    continue
                disponiveis += 1

        if qtd > disponiveis:
            erros.append(
                f"{prof} / {materia} / {turma}: precisa de {qtd} aulas, mas só tem "
                f"{disponiveis} horários disponíveis após bloqueios e regras."
            )

    bloqueios_por_prof = defaultdict(set)
    for item in grade_aulas:
        bloqueios_por_prof[item["prof"]].add(
            (tuple(item.get("bloqueios_indices", [])), tuple(item.get("bloqueios_slots", [])))
        )

    for prof, bloqueios in sorted(bloqueios_por_prof.items()):
        if len(bloqueios) > 1:
            avisos.append(
                f"O professor {prof} possui indisponibilidades diferentes em linhas distintas. "
                "A H.A./PL usa a união desses bloqueios."
            )

    return erros, avisos


def auditoria_pos_solver(resultados, grade_aulas, turmas_config, dias_list, permitir_regras_relaxadas=False):
    erros = []
    avisos = []
    resumo = []

    if not resultados:
        return {
            "erros": ["O solver não devolveu aulas para validar."],
            "avisos": [],
            "resumo": [],
            "ok": False,
        }

    por_turma_slot = Counter((r["turma"], r["dia_idx"], r["aula_idx"]) for r in resultados)
    por_prof_slot = Counter((r["prof"], r["dia_idx"], r["aula_idx"]) for r in resultados)

    conflitos_turma = [k for k, total in por_turma_slot.items() if total > 1]
    conflitos_prof = [k for k, total in por_prof_slot.items() if total > 1]

    for turma, dia_idx, aula_idx in conflitos_turma:
        erros.append(f"A turma {turma} tem mais de uma aula em {_formatar_slot(dias_list, dia_idx, aula_idx)}.")

    for prof, dia_idx, aula_idx in conflitos_prof:
        erros.append(f"O professor {prof} aparece em mais de um lugar em {_formatar_slot(dias_list, dia_idx, aula_idx)}.")

    esperado = defaultdict(int)
    bloqueios_por_item = defaultdict(lambda: {"dias": set(), "slots": set()})
    for item in grade_aulas:
        chave = (item["turma"], item["prof"], item["materia"])
        esperado[chave] += int(item["qtd"])
        bloqueios_por_item[chave]["dias"].update(item.get("bloqueios_indices", []))
        bloqueios_por_item[chave]["slots"].update(tuple(slot) for slot in item.get("bloqueios_slots", []))

    realizado = Counter((r["turma"], r["prof"], r["materia"]) for r in resultados)
    for chave, qtd_esperada in sorted(esperado.items()):
        qtd_realizada = realizado.get(chave, 0)
        if qtd_realizada != qtd_esperada:
            turma, prof, materia = chave
            erros.append(
                f"Carga divergente para {prof} / {materia} / {turma}: "
                f"esperado {qtd_esperada}, gerado {qtd_realizada}."
            )

    for row in resultados:
        chave = (row["turma"], row["prof"], row["materia"])
        bloqueios = bloqueios_por_item[chave]
        dia_idx = row["dia_idx"]
        aula_idx = row["aula_idx"]
        dia_abs = _dia_absoluto(dias_list[dia_idx], dia_idx)
        if dia_abs in bloqueios["dias"] or (dia_abs, aula_idx) in bloqueios["slots"]:
            mensagem = (
                f"{row['prof']} / {row['materia']} foi alocado em horário bloqueado: "
                f"{_formatar_slot(dias_list, dia_idx, aula_idx)}."
            )
            if permitir_regras_relaxadas:
                avisos.append(mensagem)
            else:
                erros.append(mensagem)

    carga_turma = Counter(r["turma"] for r in resultados if not eh_hora_atividade(r))
    for turma, limite in sorted(turmas_config.items()):
        if turma.startswith("H.A. ("):
            continue
        total = carga_turma.get(turma, 0)
        if total != limite:
            avisos.append(f"A turma {turma} terminou com {total} aulas para uma carga configurada de {limite}.")

    total_ha = sum(1 for r in resultados if eh_hora_atividade(r))
    resumo.append(f"Aulas geradas: {len(resultados)}.")
    resumo.append(f"H.A./PL geradas: {total_ha}.")
    resumo.append(f"Conflitos de professor: {len(conflitos_prof)}.")
    resumo.append(f"Conflitos de turma: {len(conflitos_turma)}.")

    return {
        "erros": erros,
        "avisos": avisos,
        "resumo": resumo,
        "ok": not erros,
    }
