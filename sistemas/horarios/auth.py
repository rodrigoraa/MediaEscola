import os

import streamlit as st

def converter_para_dict_puro(objeto_streamlit):
    if hasattr(objeto_streamlit, 'items'):
        return {k: converter_para_dict_puro(v) for k, v in objeto_streamlit.items()}
    else:
        return objeto_streamlit

def aplicar_estilo_login():
    st.markdown("""
        <style>
        /* Centraliza o conteúdo verticalmente */
        .block-container {
            padding-top: 3rem;
        }
        
        /* Estiliza a caixa de login para ser sutil */
        div[data-testid="stForm"] {
            border: 1px solid rgba(128, 128, 128, 0.2); /* Borda cinza transparente */
            padding: 30px;
            border-radius: 15px;
            /* Remove o background-color para respeitar o tema do usuário */
        }
        
        /* Remove o espaço extra dos títulos */
        h1, h2, h3 {
            margin-top: 0px;
        }
        </style>
    """, unsafe_allow_html=True)

def verificar_login():
    if os.getenv("HORARIOS_PORTAL_MODE") == "1":
        nome_usuario = st.query_params.get("usuario") or "Portal Escolar"
        return True, nome_usuario, None

    try:
        import streamlit_authenticator as stauth
    except ImportError:
        st.error("Instale streamlit-authenticator ou execute este módulo pelo Portal Escolar.")
        st.stop()

    try:
        config_full = converter_para_dict_puro(st.secrets)
        dict_credentials = config_full['credentials']
        cookie = config_full['cookie']
    except Exception as e:
        st.error(f"Erro no secrets.toml: {e}")
        st.stop()

    authenticator = stauth.Authenticate(
        dict_credentials,
        cookie['name'],
        cookie['key'],
        cookie['expiry_days']
    )

    if st.session_state.get("authentication_status"):
        return True, st.session_state["name"], authenticator

    aplicar_estilo_login()
    
    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:
        st.write("") 
        
        c_img_1, c_img_2, c_img_3 = st.columns([1, 1, 1])
        with c_img_2:
            st.header("🎓") 
            # para usar logo:
            # st.image("sua_logo.png", width=100)

        st.markdown("<h3 style='text-align: center;'>Acesso Restrito</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; opacity: 0.7;'>Sistema Gerador de Horários</p>", unsafe_allow_html=True)

        authenticator.login(location='main', key='login_form')

    if st.session_state["authentication_status"] is False:
        with col2:
            st.error("❌ Usuário ou senha incorretos")
        return False, None, None
        
    elif st.session_state["authentication_status"] is None:
        return False, None, None
        
    elif st.session_state["authentication_status"] is True:
        return True, st.session_state["name"], authenticator
