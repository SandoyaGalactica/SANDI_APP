# Configuración de la base de datos al iniciar la app
from db_utils import get_conn

# Configurar la base de datos para concurrencia y bloqueos
with get_conn() as conn:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=3000;")
    conn.commit()

import streamlit as st
from db_utils import auto_migrate, verify_database_tables
from ui_inicio import pantalla_inicio
from ui_empresa import pantalla_empresa
from db_utils import optimize_db_connection

# Al inicio de tu aplicación
optimize_db_connection()

# -------- LOGIN -------- #
def login_screen():
    st.set_page_config(page_title="S.A.N.D.I", layout="wide")

    # CSS para centrar el login
    st.markdown("""
    <style>
    .centered-login {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 80vh;
        flex-direction: column;
    }
    </style>
    """, unsafe_allow_html=True)

    # Encabezado
    st.markdown(
        "<h1 style='text-align:center; margin-top: 50px;'>S.A.N.D.I</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<h4 style='text-align:center; color:gray; margin-bottom: 50px;'>Bienvenido a tu gestor de empresas</h4>",
        unsafe_allow_html=True
    )

    # Login centrado
    st.markdown("<div class='centered-login'>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("### Iniciar Sesión")
        username = st.text_input("Usuario", key="login_user")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Ingresar", use_container_width=True):
            if username == "admin" and password == "123":
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.markdown("</div>", unsafe_allow_html=True)

def main():
    # Inicializar variables de sesión
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    
    # Inicializar theme_mode para evitar errores
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = "Light"
        
    if "show_menu" not in st.session_state:
        st.session_state.show_menu = False
     
    if not st.session_state["logged_in"]:
        login_screen()
    else:
        # Verificar si hay una empresa activa seleccionada
        if "empresa_activa" in st.session_state and "empresa_activa_nombre" in st.session_state:
            pantalla_empresa(st.session_state.empresa_activa, st.session_state.empresa_activa_nombre)
        else:
            pantalla_inicio()

if __name__ == "__main__":

    main()
