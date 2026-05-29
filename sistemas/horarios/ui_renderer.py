import streamlit as st
import pandas as pd

def desenhar_grade(resultados, dias_semana, _ignored=None):
    if not resultados:
        st.warning("Sem resultados para exibir.")
        return

    df = pd.DataFrame(resultados)
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