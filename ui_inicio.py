import streamlit as st
import pandas as pd
from db_utils import list_companies, add_company, delete_company

# Agregar al inicio de ui_inicio.py:
from backup_ui import mostrar_panel_backup_simple, mostrar_estado_backup_sidebar

# En tu función pantalla_inicio(), agregar esto donde quieras mostrar el panel:




st.markdown("""
<style>
/* Estilos mejorados para tarjetas de empresa */
.company-card {
    transition: all 0.3s ease;
    cursor: pointer;
    border-radius: 15px;
    padding: 20px;
    margin: 10px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    backdrop-filter: blur(10px);
    position: relative;
    overflow: hidden;
}

.company-card:hover {
    transform: translateY(-5px) scale(1.02);
    box-shadow: 0 8px 25px rgba(0,0,0,0.2);
}

.company-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
}

/* Contenedor de logos */
.logo-container {
    position: relative;
    display: inline-block;
    margin: 10px 0;
}

.logo-container img {
    border-radius: 50%;
    border: 3px solid rgba(255,255,255,0.3);
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    transition: all 0.3s ease;
}

.logo-container:hover img {
    transform: scale(1.1);
    box-shadow: 0 6px 12px rgba(0,0,0,0.3);
}

/* Indicadores de estado */
.status-indicator {
    position: absolute;
    top: 10px;
    right: 10px;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: bold;
    color: white;
    animation: pulse 2s infinite;
}

.status-indicator.complete {
    background: linear-gradient(135deg, #28a745, #20c997);
}

.status-indicator.partial {
    background: linear-gradient(135deg, #ffc107, #fd7e14);
}

@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.7); }
    70% { box-shadow: 0 0 0 10px rgba(40, 167, 69, 0); }
    100% { box-shadow: 0 0 0 0 rgba(40, 167, 69, 0); }
}

/* Modal mejorado */
.modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 90%;
    max-width: 600px;
    max-height: 80vh;
    overflow-y: auto;
    background: white;
    border-radius: 15px;
    padding: 30px;
    z-index: 1000;
    box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    backdrop-filter: blur(10px);
}

.dark .modal {
    background: #2d3e50;
    color: white;
}

.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.6);
    z-index: 999;
    backdrop-filter: blur(5px);
}

/* Formularios de configuración */
.config-section {
    border: 1px solid #e9ecef;
    border-radius: 10px;
    padding: 20px;
    margin: 15px 0;
    background: #f8f9fa;
}

.dark .config-section {
    border-color: #495057;
    background: #3a4b5c;
}

/* Métricas mejoradas */
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    margin: 10px 0;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

/* Animaciones para upload de archivos */
.upload-area {
    border: 2px dashed #dee2e6;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    transition: all 0.3s ease;
}

.upload-area:hover {
    border-color: #667eea;
    background: rgba(102, 126, 234, 0.05);
}

/* Botones mejorados */
.stButton > button {
    border-radius: 8px !important;
    transition: all 0.3s ease !important;
    font-weight: 500 !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 12px rgba(0,0,0,0.15) !important;
}

/* Indicadores de progreso */
.progress-indicator {
    width: 100%;
    height: 4px;
    background: #e9ecef;
    border-radius: 2px;
    overflow: hidden;
}

.progress-indicator::after {
    content: '';
    display: block;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    animation: progress-animation 2s ease-in-out infinite;
}

@keyframes progress-animation {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

/* Alertas y notificaciones */
.success-alert {
    background: linear-gradient(135deg, #28a745, #20c997);
    color: white;
    padding: 15px;
    border-radius: 8px;
    margin: 10px 0;
    animation: slideIn 0.3s ease-out;
}

.error-alert {
    background: linear-gradient(135deg, #dc3545, #e74c3c);
    color: white;
    padding: 15px;
    border-radius: 8px;
    margin: 10px 0;
    animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Navegación de empresas */
.nav-arrow {
    font-size: 2.5rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 50%;
    width: 60px;
    height: 60px;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
}

.nav-arrow:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 12px rgba(0,0,0,0.2);
}

.nav-arrow:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    transform: none;
}

/* Responsive design */
@media (max-width: 768px) {
    .company-card {
        margin: 5px;
        padding: 15px;
    }
    
    .modal {
        width: 95%;
        padding: 20px;
    }
    
    .nav-arrow {
        width: 50px;
        height: 50px;
        font-size: 2rem;
    }
}

/* Efectos de carga */
.loading-spinner {
    border: 3px solid rgba(102, 126, 234, 0.1);
    border-top: 3px solid #667eea;
    border-radius: 50%;
    width: 30px;
    height: 30px;
    animation: spin 1s linear infinite;
    margin: 0 auto;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Tarjetas de información */
.info-card {
    background: white;
    border-radius: 10px;
    padding: 20px;
    margin: 10px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    border-left: 4px solid #667eea;
    transition: all 0.3s ease;
}

.info-card:hover {
    transform: translateX(5px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.dark .info-card {
    background: #3a4b5c;
    color: white;
}

/* Badges de estado */
.status-badge {
    display: inline-block;
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
}

.status-badge.active {
    background: #d4edda;
    color: #155724;
}

.status-badge.maintenance {
    background: #fff3cd;
    color: #856404;
}

.status-badge.inactive {
    background: #f8d7da;
    color: #721c24;
}

/* Secciones de configuración */
.config-form-section {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 20px;
    margin: 15px 0;
    backdrop-filter: blur(10px);
}

/* Animaciones de entrada */
@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.fade-in-up {
    animation: fadeInUp 0.6s ease-out;
}

/* Gradientes personalizados */
.gradient-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.gradient-success {
    background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
}

.gradient-warning {
    background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%);
}

.gradient-danger {
    background: linear-gradient(135deg, #dc3545 0%, #e74c3c 100%);
}

/* Efectos de hover para botones */
.hover-lift {
    transition: all 0.3s ease;
}

.hover-lift:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.15);
}

/* Separadores elegantes */
.elegant-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, #667eea 50%, transparent 100%);
    margin: 30px 0;
}

/* Tooltips personalizados */
.custom-tooltip {
    position: relative;
    cursor: help;
}

.custom-tooltip::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.8);
    color: white;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 12px;
    white-space: nowrap;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
    z-index: 1000;
}

.custom-tooltip:hover::after {
    opacity: 1;
    visibility: visible;
}

/* Efectos para drag and drop */
.dropzone {
    border: 2px dashed #ccc;
    border-radius: 10px;
    padding: 40px;
    text-align: center;
    color: #666;
    transition: all 0.3s ease;
    cursor: pointer;
}

.dropzone:hover,
.dropzone.dragover {
    border-color: #667eea;
    background: rgba(102, 126, 234, 0.1);
    color: #667eea;
}

/* Mejoras para formularios */
.form-group {
    margin-bottom: 20px;
}

.form-label {
    font-weight: 600;
    margin-bottom: 8px;
    color: #495057;
}

.dark .form-label {
    color: #e9ecef;
}

/* Efectos de foco para inputs */
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
.stSelectbox > div > div > div > div:focus {
    border-color: #667eea !important;
    box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.25) !important;
}
</style>
""", unsafe_allow_html=True)


# Estado inicial
if "empresa_index" not in st.session_state:
    st.session_state.empresa_index = 0
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Light"
if "show_menu" not in st.session_state:
    st.session_state.show_menu = False
if "delete_confirmation_step" not in st.session_state:
    st.session_state.delete_confirmation_step = 0
if "empresa_to_delete" not in st.session_state:
    st.session_state.empresa_to_delete = None

# 🎨 CSS personalizado
st.markdown("""
<style>
/* Tarjetas de empresa con efecto hover */
.company-card {
    transition: all 0.3s ease;
    cursor: pointer;
    border-radius: 12px;
    padding: 20px;
    margin: 10px;
    text-align: center;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
.company-card:hover {
    transform: scale(1.05);
    box-shadow: 0 8px 16px rgba(0,0,0,0.2);
}

/* Contenedor horizontal para las tarjetas */
.cards-container {
    display: flex;
    flex-wrap: nowrap;
    overflow-x: auto;
    justify-content: center;
    padding: 20px 0;
    gap: 20px;
}

/* Flechas de navegación */
.nav-arrow {
    font-size: 2.5rem;
    background: transparent;
    border: none;
    cursor: pointer;
    transition: all 0.3s ease;
}
.nav-arrow:hover {
    transform: scale(1.2);
}

/* Modal flotante */
.modal {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 80%;
    max-width: 500px;
    background: white;
    border-radius: 12px;
    padding: 25px;
    z-index: 1000;
    box-shadow: 0 8px 30px rgba(0,0,0,0.3);
}
.dark .modal {
    background: #2d3e50;
    color: white;
}

/* Overlay para el modal */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
    z-index: 999;
}

/* Botones de confirmación */
.confirm-button {
    margin: 5px;
    padding: 10px 20px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    font-weight: bold;
}
.confirm-yes {
    background-color: #ff4b4b;
    color: white;
}
.confirm-no {
    background-color: #f0f2f6;
    color: #333;
}
</style>
""", unsafe_allow_html=True)

# Reemplazar la función pantalla_inicio en ui_inicio.py

# Reemplazar la función pantalla_inicio en ui_inicio.py

# Reemplazar la función pantalla_inicio en ui_inicio.py - VERSION LIMPIA

def pantalla_inicio():
    st.set_page_config(page_title="S.A.N.D.I", layout="wide")
    
    # Inicializar variables de sesión necesarias
    if "show_menu" not in st.session_state:
        st.session_state.show_menu = False
    if "empresa_index" not in st.session_state:
        st.session_state["empresa_index"] = 0
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = "Light"
    
    # Mostrar estado de backup en sidebar si está disponible
    if BACKUP_UI_AVAILABLE:
        mostrar_estado_backup_sidebar()
    
    # Header de la aplicación
    st.markdown("# 🏢 S.A.N.D.I")
    st.markdown("### Sistema de Administración y Negocios - Dashboard Integral")
    
    # Información del usuario
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"**Bienvenido:** {st.session_state.get('username', 'Usuario')}")
    with col2:
        if st.button("🌓 Cambiar Tema"):
            st.session_state.theme_mode = "Dark" if st.session_state.theme_mode == "Light" else "Light"
            st.rerun()
    with col3:
        if st.button("🚪 Cerrar Sesión"):
            # Limpiar session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    st.divider()
    
    # Crear tabs para organizar la interfaz
    if BACKUP_UI_AVAILABLE:
        tab1, tab2, tab3, tab4 = st.tabs(["🏠 Dashboard", "🏢 Empresas", "🔄 Backups", "⚙️ Configuración"])
    else:
        tab1, tab2, tab4 = st.tabs(["🏠 Dashboard", "🏢 Empresas", "⚙️ Configuración"])
        tab3 = None
    
    # TAB 1: DASHBOARD PRINCIPAL
    with tab1:
        st.header("📊 Dashboard Principal")
        
        # Métricas del sistema
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="📈 Empresas Activas",
                value="0",  # Aquí conectarías con tu DB
                delta="0"
            )
        
        with col2:
            st.metric(
                label="💰 Total Ingresos",
                value="$0",  # Aquí conectarías con tu DB
                delta="0%"
            )
        
        with col3:
            st.metric(
                label="📋 Proyectos",
                value="0",  # Aquí conectarías con tu DB
                delta="0"
            )
        
        with col4:
            backup_status = "🟢 Activo" if BACKUP_UI_AVAILABLE else "🔴 Inactivo"
            st.metric(
                label="☁️ Backup",
                value=backup_status
            )
        
        st.divider()
        
        # Accesos rápidos
        st.subheader("🚀 Accesos Rápidos")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🏢 Gestionar Empresas", use_container_width=True):
                st.info("💡 Ve al tab 'Empresas' para gestionar tus empresas")
        
        with col2:
            if st.button("📊 Ver Reportes", use_container_width=True):
                st.info("📈 Función de reportes - próximamente")
        
        with col3:
            if st.button("⚙️ Configuración", use_container_width=True):
                st.info("⚙️ Ve al tab 'Configuración' para ajustes del sistema")
        
        # Información del sistema
        st.divider()
        st.subheader("ℹ️ Información del Sistema")
        
        info_col1, info_col2 = st.columns(2)
        
        with info_col1:
            st.info(f"""
            **Estado del Sistema:**
            - 🟢 Base de datos: Conectada
            - 🟢 Sesión: Activa
            - 🟢 Tema: {st.session_state.theme_mode}
            """)
        
        with info_col2:
            st.info(f"""
            **Última actividad:**
            - 📅 Fecha: {datetime.now().strftime('%d/%m/%Y')}
            - 🕒 Hora: {datetime.now().strftime('%H:%M:%S')}
            - 👤 Usuario: {st.session_state.get('username', 'N/A')}
            """)
    
    # TAB 2: EMPRESAS
    with tab2:
        st.header("🏢 Gestión de Empresas")
        
        # Aquí iría tu contenido actual de empresas
        st.info("📋 Aquí aparecerá la lista y gestión de empresas")
        st.markdown("**Funcionalidades disponibles:**")
        st.markdown("- ➕ Crear nueva empresa")
        st.markdown("- 📝 Editar empresa existente")  
        st.markdown("- 🗑️ Eliminar empresa")
        st.markdown("- 📊 Ver detalles y métricas")
        
        # Botón placeholder para crear empresa
        if st.button("➕ Crear Nueva Empresa"):
            st.success("✅ Función de crear empresa - implementar según tu lógica actual")
    
    # TAB 3: BACKUPS (solo si está disponible)
    if tab3 and BACKUP_UI_AVAILABLE:
        with tab3:
            mostrar_panel_backup_simple()
    
    # TAB 4: CONFIGURACIÓN
    with tab4:
        st.header("⚙️ Configuración del Sistema")
        
        # Configuración de tema
        st.subheader("🎨 Apariencia")
        tema_actual = st.session_state.get("theme_mode", "Light")
        nuevo_tema = st.selectbox(
            "Seleccionar tema:",
            ["Light", "Dark"],
            index=0 if tema_actual == "Light" else 1
        )
        
        if nuevo_tema != tema_actual:
            st.session_state.theme_mode = nuevo_tema
            st.success(f"✅ Tema cambiado a {nuevo_tema}")
            st.rerun()
        
        st.divider()
        
        # Configuración de backup
        st.subheader("💾 Configuración de Backup")
        if BACKUP_UI_AVAILABLE:
            st.success("✅ Sistema de backup disponible y configurado")
            
            # Mostrar configuración actual
            try:
                backup_interval = st.secrets.get("app_config", {}).get("backup_interval_minutes", 30)
                st.info(f"🕒 Intervalo de auto-backup: {backup_interval} minutos")
                
                max_backups = st.secrets.get("app_config", {}).get("max_auto_backups", 10)
                st.info(f"📁 Máximo backups automáticos: {max_backups}")
                
            except Exception as e:
                st.warning(f"⚠️ No se pudo leer configuración de backup: {str(e)}")
        else:
            st.warning("⚠️ Sistema de backup no disponible")
            st.info("💡 Para habilitar backup, configura los secrets de GitHub")
        
        st.divider()
        
        # Información de debug (solo para desarrollo)
        if st.checkbox("🔍 Mostrar información de debug"):
            st.subheader("🔧 Debug Info")
            
            # Session state
            with st.expander("📱 Session State"):
                st.json(dict(st.session_state))
            
            # Secrets (cuidado con información sensible)
            with st.expander("🔐 Secrets Configuration"):
                try:
                    secrets_safe = {}
                    for key, value in st.secrets.items():
                        if isinstance(value, dict):
                            secrets_safe[key] = {k: "***" if "token" in k.lower() or "password" in k.lower() else v for k, v in value.items()}
                        else:
                            secrets_safe[key] = "***" if "token" in str(key).lower() or "password" in str(key).lower() else value
                    st.json(secrets_safe)
                except Exception as e:
                    st.error(f"Error mostrando secrets: {str(e)}")
            
            # Variables del sistema
            with st.expander("🖥️ System Info"):
                st.write(f"**BACKUP_UI_AVAILABLE:** {BACKUP_UI_AVAILABLE}")
                st.write(f"**Current time:** {datetime.now()}")
    
    # Modal flotante para opciones (tu código original)
    if st.session_state.get('show_menu', False):
        st.markdown("<div class='modal-overlay'></div>", unsafe_allow_html=True)
        
        bg = "#2d3e50" if st.session_state.theme_mode == "Dark" else "#ffffff"
        text_color = "#ffffff" if st.session_state.theme_mode == "Dark" else "#000000"
        
        st.markdown(f"""
        <div class='modal-content' style='background-color: {bg}; color: {text_color};'>
            <h3>Opciones del Sistema</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Botón para cerrar modal
        if st.button("✖️ Cerrar"):
            st.session_state.show_menu = False
            st.rerun()

