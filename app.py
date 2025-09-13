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
from controles_module import mostrar_controles_enhanced

# Al inicio de tu aplicación
optimize_db_connection()

# Inicializar sistema de backup
try:
    from db_utils import setup_database_with_backup
    setup_database_with_backup()
except ImportError:
    print("⚠️ Sistema de backup no disponible")
except Exception as e:
    print(f"⚠️ Error inicializando backup: {str(e)}")

def initialize_session_state():
    """Inicializar todas las variables de session_state necesarias"""
    session_vars = {
        "logged_in": False,
        "show_menu": False,
        "empresa_index": 0,
        "theme_mode": "Light",
        "username": "",
        "empresa_activa": None,
        "empresa_activa_nombre": "",
        # Agregar aquí cualquier otra variable que uses en tu aplicación
    }
    
    for key, default_value in session_vars.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

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
    app_name = st.secrets.get("app_config", {}).get("app_name", "S.A.N.D.I")
    st.markdown(
        f"<h1 style='text-align:center; margin-top: 50px;'>{app_name}</h1>",
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
            try:
                # Obtener credenciales SOLO desde secrets
                valid_username = st.secrets["authentication"]["admin_username"]
                valid_password = st.secrets["authentication"]["admin_password"]
                
                if username == valid_username and password == valid_password:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.success("✅ Login exitoso!")
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas")
                    
            except KeyError as e:
                st.error(f"❌ Error de configuración: {str(e)}")
                st.info("💡 Revisa la configuración de secrets en Streamlit Cloud")
                
                # Mostrar qué secrets faltan
                if "authentication" not in st.secrets:
                    st.warning("⚠️ Falta sección [authentication] en secrets")
                else:
                    missing_keys = []
                    if "admin_username" not in st.secrets["authentication"]:
                        missing_keys.append("admin_username")
                    if "admin_password" not in st.secrets["authentication"]:
                        missing_keys.append("admin_password")
                    
                    if missing_keys:
                        st.warning(f"⚠️ Faltan claves en secrets: {', '.join(missing_keys)}")
    
    st.markdown("</div>", unsafe_allow_html=True)

def initialize_backup_system():
    """Inicializar sistema de backup para app familiar"""
    try:
        from github_backup_utils import setup_github_auto_backup, get_github_backups, restore_from_github, test_github_connection
        from db_utils import DB_PATH
        import os
        
        # Verificar conexión
        success, message = test_github_connection()
        if not success:
            print(f"⚠️ GitHub backup no disponible: {message}")
            return False
        
        # Si no existe DB local, intentar restaurar desde GitHub
        if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
            backups = get_github_backups()
            if backups:
                print("🔄 Restaurando último backup al iniciar...")
                restore_success, restore_msg = restore_from_github(backups[0], DB_PATH)
                if restore_success:
                    print("✅ Base de datos restaurada desde GitHub")
                else:
                    print(f"⚠️ Error restaurando: {restore_msg}")
        
        # Configurar auto-backup cada 10 minutos
        setup_github_auto_backup(DB_PATH, interval_minutes=10)
        
        print("✅ Sistema de backup inicializado")
        return True
        
    except Exception as e:
        print(f"⚠️ Error inicializando backup: {e}")
        return False

def main():
    # Inicializar session_state como primera acción
    initialize_session_state()
    
    # Inicializar sistema de backup
    initialize_backup_system()

    if not st.session_state["logged_in"]:
        login_screen()
    else:
        # Verificar si hay una empresa activa seleccionada
        if ("empresa_activa" in st.session_state and 
            st.session_state["empresa_activa"] is not None and
            "empresa_activa_nombre" in st.session_state and
            st.session_state["empresa_activa_nombre"]):
            pantalla_empresa(st.session_state.empresa_activa, st.session_state.empresa_activa_nombre)
        else:
            pantalla_inicio()

if __name__ == "__main__":
    main()


