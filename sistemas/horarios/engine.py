from ortools.sat.python import cp_model
from collections import defaultdict

def rodar_solver(turmas_config, grade_aulas, dias_semana, itinerarios_lista=[], slots_itinerario_perm=[], agrupamentos_projetos=[], professores_com_dobradinha=[]):
    
    print(f">>> Iniciando Solver. Professores com Dobradinha Permitida: {professores_com_dobradinha}")
    model = cp_model.CpModel()
    qtd_dias = len(dias_semana)

    horario = {} 
    vars_list = defaultdict(list)
    custo_total = [] 
    mapa_vars = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    def get_slots_da_turma(nome_turma, materia=""):
        if materia == 'Hora Atividade': return 5    
        carga = turmas_config.get(nome_turma, 25)
        return 6 if carga > 25 else 5

    for item in grade_aulas:
        t, p, m = item['turma'], item['prof'], item['materia']
        
        bloqueios_dias = item.get('bloqueios_indices', []) 
        bloqueios_slots = item.get('bloqueios_slots', [])

        slots_desta_turma = get_slots_da_turma(t, m)
        eh_itinerario = (m in itinerarios_lista)

        for d in range(qtd_dias):
            for a in range(slots_desta_turma):
                v = model.NewBoolVar(f"H_{t}_{p}_{m}_{d}_{a}")
                horario[(t, d, a, p, m)] = v
                mapa_vars[t][m][d].append(v)

                if d in bloqueios_dias: 
                    model.Add(v == 0)

                if (d, a) in bloqueios_slots:
                    model.Add(v == 0)

                if eh_itinerario and slots_itinerario_perm and a not in slots_itinerario_perm:
                    model.Add(v == 0)

                vars_list['turma_slot'].append(((t, d, a), v))
                vars_list['prof_slot'].append(((p, d, a), v))
                vars_list['item_total'].append(((t, p, m), v))
                
                vars_list[f'prof_dia_geral_{p}_{d}'].append(v)
                vars_list[f'prof_turma_materia_dia_{p}_{t}_{m}_{d}'].append(v)

    processed_items = set()
    for item in grade_aulas:
        key = (item['turma'], item['prof'], item['materia'])
        if key in processed_items: continue
        processed_items.add(key)
        vars_dessa_materia = [v for (k, v) in vars_list['item_total'] if k == key]
        model.Add(sum(vars_dessa_materia) == item['qtd'])

    for map_key in ['turma_slot', 'prof_slot']:
        slots_map = defaultdict(list)
        for key, v in vars_list[map_key]:
            slots_map[key].append(v)
        for slot_vars in slots_map.values():
            model.Add(sum(slot_vars) <= 1)

    turmas_unicas = set(i['turma'] for i in grade_aulas)
    for t_nome in turmas_unicas:
        slots_calc = 6 if turmas_config.get(t_nome, 25) > 25 else 5
        for d in range(qtd_dias):
            vars_dia = []
            for m in mapa_vars[t_nome]: vars_dia.extend(mapa_vars[t_nome][m][d])
            if not vars_dia: continue
            
            soma = model.NewIntVar(0, slots_calc, f"s_t{t_nome}_{d}")
            model.Add(sum(vars_dia) == soma)
            sq = model.NewIntVar(0, slots_calc**2, f"sq_t{t_nome}_{d}")
            model.AddMultiplicationEquality(sq, [soma, soma])
            custo_total.append(sq * 10) 

    for item in grade_aulas:
        p = item['prof']
        t = item['turma']
        m = item['materia']
        
        pode_dobrar = (p in professores_com_dobradinha)
        
        for d in range(qtd_dias):
            vars_aula = vars_list[f'prof_turma_materia_dia_{p}_{t}_{m}_{d}']
            if not vars_aula: continue

            soma_aulas = model.NewIntVar(0, 6, f"s_aula_{p}_{t}_{m}_{d}")
            model.Add(sum(vars_aula) == soma_aulas)

            if not pode_dobrar:
                tem_dobradinha = model.NewBoolVar(f"dobra_{p}_{t}_{m}_{d}")
                model.Add(soma_aulas > 1).OnlyEnforceIf(tem_dobradinha)
                model.Add(soma_aulas <= 1).OnlyEnforceIf(tem_dobradinha.Not())
                custo_total.append(tem_dobradinha * 100000)
            
    prof_dia_map = defaultdict(lambda: {'normal': [], 'ha': []})
    for (t, d, a, p, m), v in horario.items():
        k = 'ha' if m == 'Hora Atividade' else 'normal'
        prof_dia_map[(p, d)][k].append(v)
            
    for (p, d), g in prof_dia_map.items():
        if not g['ha']: continue
        tem_ha = model.NewBoolVar(f"tha_{p}_{d}")
        model.Add(sum(g['ha']) > 0).OnlyEnforceIf(tem_ha)
        model.Add(sum(g['ha']) == 0).OnlyEnforceIf(tem_ha.Not())
        
        if g['normal']:
            tem_norm = model.NewBoolVar(f"tnorm_{p}_{d}")
            model.Add(sum(g['normal']) > 0).OnlyEnforceIf(tem_norm)
            model.Add(sum(g['normal']) == 0).OnlyEnforceIf(tem_norm.Not())
            model.AddImplication(tem_ha, tem_norm)
        else:
            model.Add(tem_ha == 0)

    profs_unicos = set(i['prof'] for i in grade_aulas)
    profs_ensino_medio = set()
    for item in grade_aulas:
        if turmas_config.get(item['turma'], 25) > 25:
             profs_ensino_medio.add(item['prof'])

    for p in profs_unicos:
        eh_prof_medio = (p in profs_ensino_medio)
        for d in range(qtd_dias):
            vars_p_d = vars_list[f'prof_dia_geral_{p}_{d}']
            if not vars_p_d: continue

            soma_aulas = model.NewIntVar(0, 6, f"soma_prof_{p}_{d}")
            model.Add(sum(vars_p_d) == soma_aulas)

            quadrado_distrib = model.NewIntVar(0, 36, f"sq_dist_{p}_{d}")
            model.AddMultiplicationEquality(quadrado_distrib, [soma_aulas, soma_aulas])
            custo_total.append(quadrado_distrib * 150) 
            
            eh_uma = model.NewBoolVar(f"unica_{p}_{d}")
            model.Add(soma_aulas == 1).OnlyEnforceIf(eh_uma)
            model.Add(soma_aulas != 1).OnlyEnforceIf(eh_uma.Not())
            custo_total.append(eh_uma * 10000)

            if not eh_prof_medio:
                eh_cinco = model.NewBoolVar(f"cinco_{p}_{d}")
                model.Add(soma_aulas == 5).OnlyEnforceIf(eh_cinco)
                model.Add(soma_aulas != 5).OnlyEnforceIf(eh_cinco.Not())
                custo_total.append(eh_cinco * 2000)

            eh_seis = model.NewBoolVar(f"seis_{p}_{d}")
            model.Add(soma_aulas == 6).OnlyEnforceIf(eh_seis)
            model.Add(soma_aulas != 6).OnlyEnforceIf(eh_seis.Not())
            custo_total.append(eh_seis * 5000)

    if agrupamentos_projetos:
        for lista_nomes in agrupamentos_projetos:
            itens = sorted([i for i in grade_aulas if i['materia'] in lista_nomes], key=lambda x: x['qtd'])
            if not itens: continue
            pivo = itens[0]
            for d in range(qtd_dias):
                v_pivo = mapa_vars[pivo['turma']][pivo['materia']][d]
                if not v_pivo: continue
                pivo_on = model.NewBoolVar(f"p_on_{d}_{pivo['id_linha']}")
                model.Add(sum(v_pivo) > 0).OnlyEnforceIf(pivo_on)
                model.Add(sum(v_pivo) == 0).OnlyEnforceIf(pivo_on.Not())
                for sat in itens[1:]:
                    v_sat = mapa_vars[sat['turma']][sat['materia']][d]
                    if not v_sat: continue
                    sat_on = model.NewBoolVar(f"s_on_{d}_{sat['id_linha']}")
                    model.Add(sum(v_sat) > 0).OnlyEnforceIf(sat_on)
                    model.Add(sum(v_sat) == 0).OnlyEnforceIf(sat_on.Not())
                    model.AddImplication(pivo_on, sat_on)
                    if sat['qtd'] == pivo['qtd']: model.Add(pivo_on == sat_on)

    model.Minimize(sum(custo_total))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60
    
    status = solver.Solve(model)
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print(f"Solução Encontrada! Custo: {solver.ObjectiveValue()}")
        res = []
        for (t, d, a, p, m), v in horario.items():
            if solver.Value(v) == 1:
                res.append({'turma': t, 'dia_idx': d, 'aula_idx': a, 'prof': p, 'materia': m})
        return "SUCESSO", res, get_slots_da_turma
    
    return "FALHA", [], get_slots_da_turma