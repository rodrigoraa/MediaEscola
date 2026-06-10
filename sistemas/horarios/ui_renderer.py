import streamlit as st
import pandas as pd


def eh_hora_atividade(row):
    return row.get('materia') == 'Hora Atividade' or str(row.get('turma', '')).startswith('H.A. (')


def desenhar_grade(resultados, dias_semana, _ignored=None):
    if not resultados:
        st.warning("Sem resultados para exibir.")
        return

    df = pd.DataFrame(resultados)
    df = df[~df.apply(eh_hora_atividade, axis=1)]
    if df.empty:
        return

    turmas = sorted(df['turma'].unique())

    for turma in turmas:
        st.markdown(f"### 🏫 Turma: {turma}")
        
        df_t = df[df['turma'] == turma]
        

        max_aula_idx = df_t['aula_idx'].max()
        
        qtd_aulas_visual = max(5, int(max_aula_idx) + 1)
        
        grid = {d: ["---"] * qtd_aulas_visual for d in dias_semana}
        
        for _, row in df_t.iterrows():
            d_nome = dias_semana[row['dia_idx']]
            a_idx = row['aula_idx']
            texto = f"{row['materia']}\n({row['prof']})"
            
            if a_idx < qtd_aulas_visual:
                grid[d_nome][a_idx] = texto
                
        df_visual = pd.DataFrame(grid)
        df_visual.index = [f"{i+1}ª Aula" for i in range(qtd_aulas_visual)]
        st.table(df_visual)
        st.markdown("---")


def desenhar_hora_atividade(resultados, dias_semana):
    if not resultados:
        return

    df = pd.DataFrame(resultados)
    df = df[df.apply(eh_hora_atividade, axis=1)]
    if df.empty:
        return

    st.markdown("### 🕒 H.A./PL por Professor")

    for prof in sorted(df['prof'].unique()):
        st.markdown(f"#### {prof}")
        df_p = df[df['prof'] == prof]
        max_aula_idx = df_p['aula_idx'].max()
        qtd_aulas_visual = max(5, int(max_aula_idx) + 1)
        grid = {d: ["---"] * qtd_aulas_visual for d in dias_semana}

        for _, row in df_p.iterrows():
            d_nome = dias_semana[row['dia_idx']]
            a_idx = row['aula_idx']
            if a_idx < qtd_aulas_visual:
                grid[d_nome][a_idx] = "H.A./PL"

        df_visual = pd.DataFrame(grid)
        df_visual.index = [f"{i+1}ª Aula" for i in range(qtd_aulas_visual)]
        st.table(df_visual)


def exibir_carga_horaria(resultados, dias_semana):
    """
    Exibe tabela com contagem de aulas (Heatmap) e Total Semanal.
    """
    if not resultados:
        return

    st.markdown("### 📊 Carga Horária e Distribuição")

    df = pd.DataFrame(resultados)
    
    df_pivot = df.pivot_table(
        index='prof', 
        columns='dia_idx', 
        values='turma', 
        aggfunc='count', 
        fill_value=0
    )

    todos_indices = range(len(dias_semana))
    df_pivot = df_pivot.reindex(columns=todos_indices, fill_value=0)

    mapa_dias = {i: nome for i, nome in enumerate(dias_semana)}
    df_pivot.rename(columns=mapa_dias, inplace=True)

    df_pivot['TOTAL'] = df_pivot.sum(axis=1)

    st.dataframe(
        df_pivot.style
        .background_gradient(cmap='Reds', subset=dias_semana)
        .background_gradient(cmap='Blues', subset=['TOTAL'])
        .format("{:.0f}"),
        use_container_width=True
    )
def exibir_pls_professores(resultados, dias_semana):
    if not resultados:
        return

    df = pd.DataFrame(resultados)
    df_pl = df[df['materia'] == 'Hora Atividade'].copy()

    st.markdown("### PLs / Hora Atividade por professor")

    if df_pl.empty:
        st.info("Nenhuma PL/Hora Atividade foi adicionada para os professores.")
        return

    df_pl['Dia'] = df_pl['dia_idx'].apply(lambda idx: dias_semana[idx])
    df_pl['Aula'] = df_pl['aula_idx'].apply(lambda idx: f"{idx + 1}ª aula")

    tabela = (
        df_pl[['prof', 'Dia', 'Aula']]
        .rename(columns={'prof': 'Professor'})
        .sort_values(['Professor', 'Dia', 'Aula'])
        .reset_index(drop=True)
    )

    st.dataframe(tabela, use_container_width=True, hide_index=True)
