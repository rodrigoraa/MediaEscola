from collections import defaultdict

from ortools.sat.python import cp_model


def rodar_solver(
    turmas_config,
    grade_aulas,
    dias_semana,
    itinerarios_lista=None,
    slots_itinerario_perm=None,
    agrupamentos_projetos=None,
    professores_com_dobradinha=None,
):
    itinerarios_lista = set(itinerarios_lista or [])
    slots_itinerario_perm = set(slots_itinerario_perm or [])
    agrupamentos_projetos = agrupamentos_projetos or []
    professores_com_dobradinha = set(professores_com_dobradinha or [])

    print(f">>> Iniciando solver. Professores com dobradinha permitida: {sorted(professores_com_dobradinha)}")

    status, resultados, slots_dia = _resolver(
        turmas_config,
        grade_aulas,
        dias_semana,
        itinerarios_lista,
        slots_itinerario_perm,
        agrupamentos_projetos,
        professores_com_dobradinha,
        relaxar_regras=False,
    )

    if status == "SUCESSO":
        avisos = _gerar_avisos(resultados, grade_aulas, dias_semana, itinerarios_lista, slots_itinerario_perm, agrupamentos_projetos, professores_com_dobradinha)
        return "SUCESSO", resultados, slots_dia, avisos

    print(">>> Modo estrito sem solucao. Tentando modo ajustado.")
    status, resultados, slots_dia = _resolver(
        turmas_config,
        grade_aulas,
        dias_semana,
        itinerarios_lista,
        slots_itinerario_perm,
        agrupamentos_projetos,
        professores_com_dobradinha,
        relaxar_regras=True,
    )

    if status == "SUCESSO":
        avisos = _gerar_avisos(resultados, grade_aulas, dias_semana, itinerarios_lista, slots_itinerario_perm, agrupamentos_projetos, professores_com_dobradinha)
        return "AJUSTADO", resultados, slots_dia, avisos

    return "FALHA", [], slots_dia, [
        "Nao foi possivel montar uma grade sem conflito de professor/turma. Revise cargas semanais, quantidade de dias e turmas com excesso de aulas."
    ]


def _resolver(
    turmas_config,
    grade_aulas,
    dias_semana,
    itinerarios_lista,
    slots_itinerario_perm,
    agrupamentos_projetos,
    professores_com_dobradinha,
    relaxar_regras,
):
    model = cp_model.CpModel()
    custo_total = []
    horario = {}
    item_vars = defaultdict(list)
    turma_slot = defaultdict(list)
    prof_slot = defaultdict(list)
    prof_dia = defaultdict(list)
    prof_turma_materia_dia = defaultdict(list)
    prof_turma_slot = defaultdict(list)
    materia_dia = defaultdict(list)

    def slots_da_turma(nome_turma, materia=""):
        if materia == "Hora Atividade":
            return 5
        carga = turmas_config.get(nome_turma, 25)
        return 6 if carga > 25 else 5

    for item_id, item in enumerate(grade_aulas):
        turma = item["turma"]
        prof = item["prof"]
        materia = item["materia"]
        bloqueios_dias = set(item.get("bloqueios_indices", []))
        bloqueios_slots = set(tuple(slot) for slot in item.get("bloqueios_slots", []))
        slots_turma = slots_da_turma(turma, materia)

        for dia_pos, dia_nome in enumerate(dias_semana):
            dia_abs = _dia_absoluto(dia_nome, dia_pos)
            for aula_idx in range(slots_turma):
                var = model.NewBoolVar(f"h_{item_id}_{dia_pos}_{aula_idx}")
                horario[(item_id, turma, dia_pos, aula_idx, prof, materia)] = var
                item_vars[item_id].append(var)
                turma_slot[(turma, dia_pos, aula_idx)].append(var)
                prof_slot[(prof, dia_pos, aula_idx)].append(var)
                prof_dia[(prof, dia_pos)].append(var)
                prof_turma_materia_dia[(prof, turma, materia, dia_pos)].append(var)
                prof_turma_slot[(prof, turma, dia_pos, aula_idx)].append(var)
                materia_dia[(materia, dia_pos)].append(var)

                viola_dia = dia_abs in bloqueios_dias
                viola_aula = (dia_abs, aula_idx) in bloqueios_slots
                viola_itinerario = materia in itinerarios_lista and slots_itinerario_perm and aula_idx not in slots_itinerario_perm

                if not relaxar_regras:
                    if viola_dia or viola_aula or viola_itinerario:
                        model.Add(var == 0)
                else:
                    if viola_dia:
                        custo_total.append(var * 120000)
                    if viola_aula:
                        custo_total.append(var * 150000)
                    if viola_itinerario:
                        custo_total.append(var * 90000)

    for item_id, item in enumerate(grade_aulas):
        model.Add(sum(item_vars[item_id]) == int(item["qtd"]))

    for vars_slot in turma_slot.values():
        model.Add(sum(vars_slot) <= 1)

    for vars_slot in prof_slot.values():
        model.Add(sum(vars_slot) <= 1)

    for turma in {item["turma"] for item in grade_aulas}:
        slots_calc = 6 if turmas_config.get(turma, 25) > 25 else 5
        for dia_pos in range(len(dias_semana)):
            vars_dia = [
                var
                for (turma_var, dia_var, _), vars_slot in turma_slot.items()
                if turma_var == turma and dia_var == dia_pos
                for var in vars_slot
            ]
            if vars_dia:
                soma = model.NewIntVar(0, slots_calc, f"s_turma_{turma}_{dia_pos}")
                model.Add(sum(vars_dia) == soma)
                quadrado = model.NewIntVar(0, slots_calc**2, f"sq_turma_{turma}_{dia_pos}")
                model.AddMultiplicationEquality(quadrado, [soma, soma])
                custo_total.append(quadrado * 10)

    for (prof, turma, materia, dia_pos), vars_aula in prof_turma_materia_dia.items():
        soma = model.NewIntVar(0, 6, f"soma_{prof}_{turma}_{materia}_{dia_pos}")
        model.Add(sum(vars_aula) == soma)
        if prof not in professores_com_dobradinha:
            tem_dobradinha = model.NewBoolVar(f"dobra_{prof}_{turma}_{materia}_{dia_pos}")
            model.Add(soma > 1).OnlyEnforceIf(tem_dobradinha)
            model.Add(soma <= 1).OnlyEnforceIf(tem_dobradinha.Not())
            custo_total.append(tem_dobradinha * 70000)

    _penalizar_carga_professor(model, custo_total, prof_dia, grade_aulas, turmas_config)
    _penalizar_aulas_seguidas(model, custo_total, prof_turma_slot)
    _restringir_hora_atividade(model, custo_total, horario, relaxar_regras)
    _penalizar_grupos(model, custo_total, materia_dia, agrupamentos_projetos, len(dias_semana))

    model.Minimize(sum(custo_total) if custo_total else 0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)
    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return "FALHA", [], slots_da_turma

    print(f">>> Solucao encontrada. Custo: {solver.ObjectiveValue()}")
    resultados = []
    for (item_id, turma, dia_pos, aula_idx, prof, materia), var in horario.items():
        if solver.Value(var) == 1:
            resultados.append(
                {
                    "item_id": item_id,
                    "turma": turma,
                    "dia_idx": dia_pos,
                    "aula_idx": aula_idx,
                    "prof": prof,
                    "materia": materia,
                }
            )

    resultados.sort(key=lambda row: (row["turma"], row["dia_idx"], row["aula_idx"], row["prof"], row["materia"]))
    return "SUCESSO", resultados, slots_da_turma


def _penalizar_carga_professor(model, custo_total, prof_dia, grade_aulas, turmas_config):
    profs_medio = {item["prof"] for item in grade_aulas if turmas_config.get(item["turma"], 25) > 25}

    for (prof, dia_pos), vars_dia in prof_dia.items():
        soma = model.NewIntVar(0, 6, f"soma_prof_{prof}_{dia_pos}")
        model.Add(sum(vars_dia) == soma)

        quadrado = model.NewIntVar(0, 36, f"sq_prof_{prof}_{dia_pos}")
        model.AddMultiplicationEquality(quadrado, [soma, soma])
        custo_total.append(quadrado * 150)

        uma_aula = model.NewBoolVar(f"uma_aula_{prof}_{dia_pos}")
        model.Add(soma == 1).OnlyEnforceIf(uma_aula)
        model.Add(soma != 1).OnlyEnforceIf(uma_aula.Not())
        custo_total.append(uma_aula * 10000)

        if prof not in profs_medio:
            cinco_aulas = model.NewBoolVar(f"cinco_aulas_{prof}_{dia_pos}")
            model.Add(soma == 5).OnlyEnforceIf(cinco_aulas)
            model.Add(soma != 5).OnlyEnforceIf(cinco_aulas.Not())
            custo_total.append(cinco_aulas * 2000)

        seis_aulas = model.NewBoolVar(f"seis_aulas_{prof}_{dia_pos}")
        model.Add(soma == 6).OnlyEnforceIf(seis_aulas)
        model.Add(soma != 6).OnlyEnforceIf(seis_aulas.Not())
        custo_total.append(seis_aulas * 5000)


def _penalizar_aulas_seguidas(model, custo_total, prof_turma_slot):
    grupos = defaultdict(dict)
    for (prof, turma, dia_pos, aula_idx), vars_slot in prof_turma_slot.items():
        tem_aula = model.NewBoolVar(f"tem_{prof}_{turma}_{dia_pos}_{aula_idx}")
        model.AddMaxEquality(tem_aula, vars_slot)
        grupos[(prof, turma, dia_pos)][aula_idx] = tem_aula

    for (prof, turma, dia_pos), aulas in grupos.items():
        for aula_idx in sorted(aulas):
            if aula_idx + 1 not in aulas:
                continue

            atual = aulas[aula_idx]
            proxima = aulas[aula_idx + 1]
            seguida = model.NewBoolVar(f"seguida_{prof}_{turma}_{dia_pos}_{aula_idx}")
            model.AddBoolAnd([atual, proxima]).OnlyEnforceIf(seguida)
            model.AddBoolOr([atual.Not(), proxima.Not()]).OnlyEnforceIf(seguida.Not())
            custo_total.append(seguida * 180000)


def _restringir_hora_atividade(model, custo_total, horario, relaxar_regras):
    prof_dia = defaultdict(lambda: {"normal": [], "ha": []})
    for (_item_id, _turma, dia_pos, _aula_idx, prof, materia), var in horario.items():
        chave = "ha" if materia == "Hora Atividade" else "normal"
        prof_dia[(prof, dia_pos)][chave].append(var)

    for (prof, dia_pos), grupos in prof_dia.items():
        if not grupos["ha"]:
            continue

        tem_ha = model.NewBoolVar(f"tem_ha_{prof}_{dia_pos}")
        model.Add(sum(grupos["ha"]) > 0).OnlyEnforceIf(tem_ha)
        model.Add(sum(grupos["ha"]) == 0).OnlyEnforceIf(tem_ha.Not())

        if not grupos["normal"]:
            if relaxar_regras:
                custo_total.append(tem_ha * 50000)
            else:
                model.Add(tem_ha == 0)
            continue

        tem_normal = model.NewBoolVar(f"tem_normal_{prof}_{dia_pos}")
        model.Add(sum(grupos["normal"]) > 0).OnlyEnforceIf(tem_normal)
        model.Add(sum(grupos["normal"]) == 0).OnlyEnforceIf(tem_normal.Not())

        if relaxar_regras:
            viola_ha = model.NewBoolVar(f"viola_ha_{prof}_{dia_pos}")
            model.AddBoolAnd([tem_ha, tem_normal.Not()]).OnlyEnforceIf(viola_ha)
            model.AddBoolOr([tem_ha.Not(), tem_normal]).OnlyEnforceIf(viola_ha.Not())
            custo_total.append(viola_ha * 50000)
        else:
            model.AddImplication(tem_ha, tem_normal)


def _penalizar_grupos(model, custo_total, materia_dia, agrupamentos_projetos, qtd_dias):
    for grupo_idx, grupo in enumerate(agrupamentos_projetos or []):
        materias = [materia for materia in grupo if materia in {key[0] for key in materia_dia.keys()}]
        if len(materias) < 2:
            continue

        for dia_pos in range(qtd_dias):
            indicadores = []
            for materia in materias:
                vars_materia = materia_dia.get((materia, dia_pos), [])
                if not vars_materia:
                    continue
                ativa = model.NewBoolVar(f"grupo_{grupo_idx}_{materia}_{dia_pos}")
                model.Add(sum(vars_materia) > 0).OnlyEnforceIf(ativa)
                model.Add(sum(vars_materia) == 0).OnlyEnforceIf(ativa.Not())
                indicadores.append(ativa)

            if len(indicadores) < 2:
                continue

            minimo = model.NewBoolVar(f"grupo_min_{grupo_idx}_{dia_pos}")
            maximo = model.NewBoolVar(f"grupo_max_{grupo_idx}_{dia_pos}")
            model.AddMinEquality(minimo, indicadores)
            model.AddMaxEquality(maximo, indicadores)
            diferenca = model.NewBoolVar(f"grupo_diff_{grupo_idx}_{dia_pos}")
            model.Add(maximo - minimo == diferenca)
            custo_total.append(diferenca * 30000)


def _gerar_avisos(resultados, grade_aulas, dias_semana, itinerarios_lista, slots_itinerario_perm, agrupamentos_projetos, professores_com_dobradinha):
    avisos = []
    por_item = {idx: item for idx, item in enumerate(grade_aulas)}
    professores_com_dobradinha = set(professores_com_dobradinha or [])

    for row in resultados:
        item = por_item.get(row.get("item_id"))
        if not item:
            continue

        dia_nome = dias_semana[row["dia_idx"]]
        aula_nome = f"{row['aula_idx'] + 1}a aula"
        dia_abs = _dia_absoluto(dia_nome, row["dia_idx"])
        bloqueios_dias = set(item.get("bloqueios_indices", []))
        bloqueios_slots = set(tuple(slot) for slot in item.get("bloqueios_slots", []))

        if dia_abs in bloqueios_dias:
            avisos.append(f"{row['prof']} foi alocado em {dia_nome}, mesmo com esse dia marcado como indisponivel.")

        if (dia_abs, row["aula_idx"]) in bloqueios_slots:
            avisos.append(f"{row['prof']} foi alocado em {dia_nome}, {aula_nome}, mesmo com esse horario indisponivel.")

        if row["materia"] in itinerarios_lista and slots_itinerario_perm and row["aula_idx"] not in slots_itinerario_perm:
            permitidas = ", ".join(f"{slot + 1}a" for slot in sorted(slots_itinerario_perm))
            avisos.append(f"{row['materia']} ficou em {dia_nome}, {aula_nome}, fora das aulas permitidas ({permitidas}).")

    por_prof_materia_dia = defaultdict(int)
    for row in resultados:
        chave = (row["prof"], row["turma"], row["materia"], row["dia_idx"])
        por_prof_materia_dia[chave] += 1

    for (prof, turma, materia, dia_pos), qtd in por_prof_materia_dia.items():
        if qtd > 1 and prof not in professores_com_dobradinha:
            avisos.append(f"{prof} teve mais de uma aula de {materia} na turma {turma} em {dias_semana[dia_pos]} para viabilizar a grade.")

    _avisar_hora_atividade(resultados, dias_semana, avisos)
    _avisar_aulas_seguidas(resultados, dias_semana, avisos)
    _avisar_grupos(resultados, dias_semana, agrupamentos_projetos, avisos)
    return _avisos_unicos(avisos)


def _avisar_hora_atividade(resultados, dias_semana, avisos):
    prof_dia = defaultdict(lambda: {"normal": 0, "ha": 0})
    for row in resultados:
        chave = (row["prof"], row["dia_idx"])
        if row["materia"] == "Hora Atividade":
            prof_dia[chave]["ha"] += 1
        else:
            prof_dia[chave]["normal"] += 1

    for (prof, dia_pos), contagem in prof_dia.items():
        if contagem["ha"] and not contagem["normal"]:
            avisos.append(f"Hora Atividade de {prof} ficou em {dias_semana[dia_pos]} sem outra aula do professor nesse dia.")


def _avisar_aulas_seguidas(resultados, dias_semana, avisos):
    aulas = defaultdict(set)
    for row in resultados:
        if row["materia"] == "Hora Atividade":
            continue
        aulas[(row["prof"], row["turma"], row["dia_idx"])].add(row["aula_idx"])

    for (prof, turma, dia_pos), indices in aulas.items():
        for aula_idx in sorted(indices):
            if aula_idx + 1 in indices:
                avisos.append(
                    f"{prof} ficou com aulas seguidas na turma {turma} em {dias_semana[dia_pos]} "
                    f"({aula_idx + 1}a e {aula_idx + 2}a aula)."
                )


def _avisar_grupos(resultados, dias_semana, agrupamentos_projetos, avisos):
    dias_por_materia = defaultdict(set)
    for row in resultados:
        dias_por_materia[row["materia"]].add(row["dia_idx"])

    for grupo in agrupamentos_projetos or []:
        materias = [materia for materia in grupo if materia in dias_por_materia]
        if len(materias) < 2:
            continue
        conjuntos = [dias_por_materia[materia] for materia in materias]
        if any(conjunto != conjuntos[0] for conjunto in conjuntos[1:]):
            nome_grupo = ", ".join(materias)
            avisos.append(f"Grupo de sincronia ({nome_grupo}) nao ficou exatamente nos mesmos dias.")


def _avisos_unicos(avisos):
    unicos = []
    vistos = set()
    for aviso in avisos:
        if aviso not in vistos:
            vistos.add(aviso)
            unicos.append(aviso)
    return unicos


def _dia_absoluto(dia_nome, fallback):
    mapa = {"SEG": 0, "TER": 1, "QUA": 2, "QUI": 3, "SEX": 4, "SAB": 5, "DOM": 6}
    return mapa.get(str(dia_nome).upper()[:3], fallback)
