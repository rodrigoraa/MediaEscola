import streamlit as st
import pandas as pd
import traceback
from xlsx_generator import gerar_modelo_excel
from data_manager import carregar_e_validar_dados
from engine import rodar_solver
from pdf_generator import gerar_pdf_bonito
from ui_renderer import desenhar_grade, exibir_carga_horaria, exibir_pls_professores
from auth import verificar_login
from auditor import auditoria_pre_solver
from exporters import gerar_excel_colorido
from horarios_store import carregar_horario, excluir_horario, listar_horarios, salvar_horario

st.set_page_config(page_title="Gerar Horário Escolar", layout="wide")


def aplicar_estilo_gerador():
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f8fafc 0%, #eef3f7 100%);
            color: #17202b;
        }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #d8e1ea;
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: #20364d;
        }

        .main .block-container {
            max-width: 1480px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3 {
            color: #20364d;
            letter-spacing: 0;
        }

        div[data-testid="stMetric"] {
            padding: 14px 16px;
            border: 1px solid #d8e1ea;
            border-radius: 8px;
            background: #ffffff;
            box-shadow: 0 8px 20px rgba(23, 32, 43, 0.06);
        }

        div[data-testid="stExpander"],
        div[data-testid="stFileUploader"],
        div[data-testid="stDataFrame"] {
            border-radius: 8px;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 8px;
            border: 1px solid #187466;
            background: #187466;
            color: #ffffff;
            font-weight: 700;
            box-shadow: 0 8px 18px rgba(24, 116, 102, 0.16);
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: #0f5f54;
            background: #0f5f54;
            color: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


aplicar_estilo_gerador()

logado, nome_usuario, authenticator = verificar_login()

if not logado:
    st.stop()
    
with st.sidebar:
    st.write(f"Olá, **{nome_usuario}**!")
    if authenticator:
        authenticator.logout('Sair', 'sidebar')
    st.divider()

st.title("🧩 Gerador de Horários")

if 'horario_gerado' not in st.session_state:
    st.session_state['horario_gerado'] = False
    st.session_state['dados_solucao'] = {}

with st.expander("Horários salvos", expanded=False):
    horarios_salvos = listar_horarios()
    if not horarios_salvos:
        st.caption("Nenhum horário salvo ainda. Ao gerar uma grade, ela será salva automaticamente aqui.")
    else:
        for horario in horarios_salvos:
            col_info, col_abrir, col_excluir = st.columns([6, 1.4, 1.4])
            with col_info:
                st.markdown(f"**{horario['titulo']}**")
                st.caption(f"{horario['criado_em']} · {horario['status']} · {horario.get('usuario') or 'Usuário'}")
            with col_abrir:
                if st.button("Abrir", key=f"abrir_horario_{horario['id']}"):
                    salvo = carregar_horario(horario['id'])
                    if salvo:
                        dados = salvo["dados"]
                        st.session_state['horario_gerado'] = True
                        st.session_state['dados_solucao'] = {
                            'resultados': dados.get('resultados', []),
                            'turmas_final': dados.get('turmas_final', {}),
                            'slots_dia': None,
                            'dias_selecionados': dados.get('dias_selecionados', []),
                            'avisos_solver': dados.get('avisos_solver', []),
                            'status_solver': dados.get('status_solver', salvo.get('status', 'SALVO')),
                            'titulo_salvo': salvo.get('titulo')
                        }
                        st.rerun()
            with col_excluir:
                if st.button("Remover", key=f"excluir_horario_{horario['id']}"):
                    excluir_horario(horario['id'])
                    if st.session_state.get('dados_solucao', {}).get('titulo_salvo') == horario['titulo']:
                        st.session_state['horario_gerado'] = False
                        st.session_state['dados_solucao'] = {}
                    st.rerun()

with st.expander("📥 Baixar Modelo de Planilha", expanded=False):
    col_dl1, col_dl2 = st.columns([1, 2])
    
    with col_dl1:
        st.markdown("### 1. Download")
        st.write("Baixe a planilha padrão:")
        
        excel_bytes = gerar_modelo_excel()
        
        st.download_button(
            label="💾 Baixar Modelo.xlsx",
            data=excel_bytes,
            file_name="modelo_horario_escolar.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col_dl2:
        st.markdown("### 2. Instruções Rápidas")
        st.info("""
        **Aba 'Turmas':** Coloque o nome da turma e total de aulas (25 ou 30).
        
        **Aba 'Grade_Curricular':**
        - **Turmas_Alvo:** Separe por vírgula se for para várias salas (Ex: `9A, 9B`).
        - **Indisponibilidade:** Dias que o prof NÃO pode (Ex: `Seg, Qua`) ou as aulas que o professor não pode dar (Ex: Seg:1, Ter:3).
        - **ATENÇÃO:** Mantenha um padrão para os nomes das turmas e dos professores para evitar erros na geração do horário.

        """)

arquivo = st.file_uploader("Upload da Planilha Excel", type=['xlsx'])

if arquivo:
    try:
        turmas_config, grade_aulas, erros, avisos = carregar_e_validar_dados(arquivo)
    except Exception as e:
        st.error(f"❌ Erro Crítico: O arquivo enviado é inválido ou está corrompido.")
        st.error(f"Detalhes: {str(e)}")
        st.stop()
    if erros:
        st.error("❌ Erros encontrados no arquivo:")
        for e in erros: st.write(f"- {e}")
        st.stop()
    if avisos:
        with st.expander("⚠️ Avisos e Ajustes Automáticos (Importante)", expanded=True):
            for a in avisos: st.write(f"- {a}")
        
    st.success("✅ Arquivo processado com sucesso!")

    qtd_professores = len(set([i['prof'] for i in grade_aulas]))
    qtd_disciplinas = len(set([i['materia'] for i in grade_aulas]))
    qtd_total_aulas = sum([i['qtd'] for i in grade_aulas])
    qtd_turmas = len(turmas_config)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    kpi1.metric("👨‍🏫 Professores", qtd_professores)
    kpi2.metric("🏫 Turmas", qtd_turmas)
    kpi3.metric("📚 Disciplinas", qtd_disciplinas)
    kpi4.metric("⏱️ Total de Aulas", qtd_total_aulas)
    
    st.divider()
    
    st.markdown("#### 1. Semana letiva")
    st.caption("Escolha os dias que entram na montagem da grade.")

    col1, col2 = st.columns(2)
    with col1:
        dias = st.multiselect("Dias Letivos", 
                            ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab'], 
                            ['Seg', 'Ter', 'Qua', 'Qui', 'Sex'])
    with col2:
        st.info(f"Turmas detectadas: {len(turmas_config)}")
        
    with st.expander("2. PLs / Hora Atividade", expanded=True):
        st.markdown("Marque os professores que devem receber 1 PL/Hora Atividade semanal.")
        
        lista_professores = sorted(list(set([i['prof'] for i in grade_aulas])))
        
        df_ha_inicial = pd.DataFrame({
            "Professor": lista_professores,
            "tem_ha": [True] * len(lista_professores),
            "qtd_aulas": [1] * len(lista_professores)
        })
        
        editor_ha = st.data_editor(
            df_ha_inicial,
            column_config={
                "tem_ha": st.column_config.CheckboxColumn(
                    "Gerar PL?",
                    help="Marque para gerar 1 PL/Hora Atividade semanal para este professor."
                ),
                "qtd_aulas": st.column_config.NumberColumn(
                    "Qtd semanal",
                    min_value=1,
                    max_value=1,
                    step=1,
                    format="%d PL"
                )
            },
            disabled=["Professor", "qtd_aulas"],
            hide_index=True,
            use_container_width=True)

    with st.expander("3. Itinerários e grupos sincronizados", expanded=False):
        st.markdown("Defina quais matérias são fixas e em quais horários elas devem ocorrer.")
        
        todas_materias = sorted(list(set([i['materia'] for i in grade_aulas])))
        
        itinerarios_selecionados = st.multiselect(
            "Quais disciplinas são Itinerários?", 
            todas_materias
        )
        
        slots_itinerario_user = st.multiselect(
            "Em quais aulas os itinerários ocorrem?",
            options=[1, 2, 3, 4, 5, 6],
            default=[6]
        )
        
        slots_itinerario_idx = [s-1 for s in slots_itinerario_user]
        
        if 'grupos_sincronia' not in st.session_state:
            st.session_state['grupos_sincronia'] = []

        with st.expander("🤝 Sincronia de Dias (Agrupar Matérias)", expanded=False):
            st.markdown("""
            **Como funciona:** Selecione matérias (ex: Robótica). O sistema forçará **TODAS** as turmas dessa matéria a terem aula no mesmo dia.
            *Útil para: Professores que atendem a escola toda no mesmo dia ou Projetos Interdisciplinares.*
            """)
            
            lista_materias = sorted(list(set([i['materia'] for i in grade_aulas])))
            
            selecao_materias = st.multiselect(
                "Quais matérias devem cair no mesmo dia?",
                options=lista_materias,
                placeholder="Ex: Robótica, Xadrez..."
            )
            
            c_btn1, c_btn2 = st.columns([1, 4])
            with c_btn1:
                if st.button("➕ Criar Grupo"):
                    if not selecao_materias:
                        st.warning("Selecione pelo menos 1 matéria.")
                    else:
                        st.session_state['grupos_sincronia'].append(selecao_materias)
                        st.success("Regra adicionada!")

            if st.session_state['grupos_sincronia']:
                st.divider()
                st.markdown("##### 🔗 Grupos Sincronizados:")
                for i, grupo in enumerate(st.session_state['grupos_sincronia']):
                    col_txt, col_del = st.columns([6, 1])
                    with col_txt:
                        st.info(f"**Grupo {i+1}:** {', '.join(grupo)}")
                    with col_del:
                        if st.button("🗑️", key=f"del_g_{i}"):
                            st.session_state['grupos_sincronia'].pop(i)
                            st.rerun()

    st.markdown("#### 4. Exceções")
    st.caption("Use somente quando a grade não fechar. Aulas seguidas do mesmo professor na mesma turma continuam sendo evitadas ao máximo.")
    
    usar_dobradinhas = st.toggle(
        "Permitir exceções de aulas no mesmo dia?",
        value=False,
        help="Ativado: Você pode escolher quem dobra. Desativado: O sistema tenta separar as aulas de TODOS os professores."
    )
    
    lista_todos_profs = sorted(list(set([i['prof'] for i in grade_aulas])))    
    
    if usar_dobradinhas:
        st.info("Selecione apenas os professores que podem ter exceção se a grade não fechar.")
        profs_dobradinha = st.multiselect(
            "Professores com exceção permitida",
            options=lista_todos_profs,
            default=[],
            help="Remova da lista quem você quer que tenha aulas separadas."
        )
    else:
        profs_dobradinha = []

    if st.button("Gerar horário"):
        
        with st.spinner("Preparando resultados. . ."):
            
            turmas_final = turmas_config.copy()
            grade_final = grade_aulas.copy()

            if 'editor_ha' in locals() and editor_ha is not None:
                profs_com_ha = editor_ha[editor_ha["tem_ha"] == True]
                
                for _, row in profs_com_ha.iterrows():
                    prof_nome = row["Professor"]
                    qtd_ha = row["qtd_aulas"]
                    
                    turma_fantasma = f"H.A. ({prof_nome})"
                    turmas_final[turma_fantasma] = 25
                    
                    grade_final.append({
                        'id_linha': 9999,
                        'prof': prof_nome,
                        'materia': 'Hora Atividade',
                        'turma': turma_fantasma,
                        'qtd': int(qtd_ha),
                        'bloqueios_indices': [],
                        'bloqueios_slots': []
                    })

            erros_mat, avisos_mat = auditoria_pre_solver(
                grade_final,
                turmas_final,
                dias,
                itinerarios_selecionados,
                slots_itinerario_idx
            )
            
        if erros_mat:
            st.error("Não foi possível montar a grade com essas cargas e restrições:")
            for em in erros_mat:
                st.write(f"- {em}")
                st.session_state['horario_gerado'] = False
                st.stop()
        if avisos_mat:
            with st.expander("⚠️ Alertas de Capacidade", expanded=True):
                for am in avisos_mat:
                    st.write(f"- {am}")

        with st.spinner("Calculando a melhor solução possível. . ."):
            regras_projeto = st.session_state.get('regras_projetos', [])

            try:
                status, resultados, slots_dia, avisos_solver = rodar_solver(
                    turmas_final,
                    grade_final,
                    dias,
                    itinerarios_selecionados,
                    slots_itinerario_idx,
                    st.session_state['grupos_sincronia'],
                    professores_com_dobradinha=profs_dobradinha
                )
            except Exception:
                st.session_state['horario_gerado'] = False
                st.error("Erro interno ao calcular o horário.")
                st.code(traceback.format_exc(), language="text")
                st.stop()
                
            if status in ["SUCESSO", "AJUSTADO"]:
                st.session_state['horario_gerado'] = True
                st.session_state['dados_solucao'] = {
                    'resultados': resultados,
                    'turmas_final': turmas_final,
                    'slots_dia': slots_dia,
                    'dias_selecionados': dias,
                    'avisos_solver': avisos_solver,
                    'status_solver': status
                }
                titulo_salvo = f"Horário - {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}"
                dados_para_salvar = {
                    'resultados': resultados,
                    'turmas_final': turmas_final,
                    'dias_selecionados': dias,
                    'avisos_solver': avisos_solver,
                    'status_solver': status
                }
                horario_id = salvar_horario(titulo_salvo, nome_usuario, status, dados_para_salvar)
                st.session_state['dados_solucao']['titulo_salvo'] = titulo_salvo
                st.session_state['dados_solucao']['horario_id'] = horario_id
                if status == "SUCESSO" and not avisos_solver:
                    st.success("Horário gerado com sucesso. Todas as restrições principais foram respeitadas.")
                else:
                    st.warning("Horário gerado com ajustes. Veja os avisos abaixo.")
                    for aviso in avisos_solver:
                        st.write(f"- {aviso}")
                st.caption(f"Salvo automaticamente em Horários salvos: {titulo_salvo}.")
            else:
                st.session_state['horario_gerado'] = False
                st.error("❌ Não foi possível gerar o horário com as configurações atuais.")
                st.info(
                    "Revise cargas semanais, quantidade de dias letivos e conflitos simultâneos de professor/turma. "
                    "Quando houver um horário possível, o sistema gera a melhor versão e mostra os ajustes necessários."
                )
    
    if st.session_state['horario_gerado']:
        
        dados = st.session_state['dados_solucao']
        res = dados['resultados']
        turmas_f = dados['turmas_final']
        d_sel = dados['dias_selecionados']
        s_dia = dados['slots_dia']
        avisos_solucao = dados.get('avisos_solver', [])

        if avisos_solucao:
            with st.expander("Avisos sobre restrições ajustadas", expanded=True):
                for aviso in avisos_solucao:
                    st.write(f"- {aviso}")
                
        exibir_pls_professores(res, d_sel)
        exibir_carga_horaria(res, d_sel)
        desenhar_grade(res, d_sel, s_dia)
                
        st.divider()
        st.markdown("### 📥 Baixar Arquivos")
                
        col_pdf, col_xls = st.columns(2)
        
        with col_pdf:
            pdf_bytes = gerar_pdf_bonito(res, turmas_f, d_sel)
            st.download_button(
                label="📄 Baixar Horário em PDF",
                data=pdf_bytes,
                file_name="horario_escolar.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col_xls:
            xls_bytes = gerar_excel_colorido(res, d_sel)
            st.download_button(
                label="📊 Baixar Excel para edição",
                data=xls_bytes,
                file_name="horario_editar.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
if st.session_state['horario_gerado'] and not arquivo:
    dados = st.session_state['dados_solucao']
    res = dados['resultados']
    turmas_f = dados['turmas_final']
    d_sel = dados['dias_selecionados']
    s_dia = dados.get('slots_dia')
    avisos_solucao = dados.get('avisos_solver', [])

    st.markdown("### Horário carregado")
    if dados.get('titulo_salvo'):
        st.caption(dados['titulo_salvo'])

    if avisos_solucao:
        with st.expander("Avisos sobre restrições ajustadas", expanded=True):
            for aviso in avisos_solucao:
                st.write(f"- {aviso}")

    exibir_pls_professores(res, d_sel)
    exibir_carga_horaria(res, d_sel)
    desenhar_grade(res, d_sel, s_dia)

    st.divider()
    st.markdown("### Baixar arquivos")

    col_pdf, col_xls = st.columns(2)
    with col_pdf:
        pdf_bytes = gerar_pdf_bonito(res, turmas_f, d_sel)
        st.download_button(
            label="Baixar horário em PDF",
            data=pdf_bytes,
            file_name="horario_escolar.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    with col_xls:
        xls_bytes = gerar_excel_colorido(res, d_sel)
        st.download_button(
            label="Baixar Excel para edição",
            data=xls_bytes,
            file_name="horario_editar.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
