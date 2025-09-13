import streamlit as st
import pandas as pd
from db_utils import list_companies, add_company, delete_company
from datetime import datetime

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



def pantalla_inicio():
    """Función pantalla_inicio - Fix temporal sin backup"""
    st.set_page_config(page_title="S.A.N.D.I", layout="wide")
    
    # Inicializar variables de sesión necesarias
    if "show_menu" not in st.session_state:
        st.session_state.show_menu = False
    if "empresa_index" not in st.session_state:
        st.session_state["empresa_index"] = 0
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = "Light"
    
    # Estado simple en sidebar (sin backup por ahora)
    st.sidebar.success("🟢 Sistema: Activo")
    st.sidebar.info("☁️ Backup: En desarrollo")
    st.sidebar.caption(f"👤 Usuario: {st.session_state.get('username', 'N/A')}")
    
    # Header de la aplicación
    st.markdown("# 🏢 S.A.N.D.I")
    st.markdown("### Sistema de Administración y Negocios - Dashboard Integral")
    
    # Información del usuario
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"**Bienvenido:** {st.session_state.get('username', 'Usuario')}")
        st.caption(f"🕒 {datetime.now().strftime('%d/%m/%Y - %H:%M')}")
    with col2:
        current_theme = st.session_state.get("theme_mode", "Light")
        theme_icon = "🌙" if current_theme == "Light" else "☀️"
        if st.button(f"{theme_icon} Tema: {current_theme}"):
            st.session_state.theme_mode = "Dark" if current_theme == "Light" else "Light"
            st.success(f"✅ Cambiado a modo {st.session_state.theme_mode}")
            st.rerun()
    with col3:
        if st.button("🚪 Cerrar Sesión", type="secondary"):
            # Confirmar antes de cerrar
            if st.session_state.get("confirm_logout", False):
                # Limpiar session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            else:
                st.session_state["confirm_logout"] = True
                st.warning("⚠️ Clic de nuevo para confirmar")
                st.rerun()
    
    st.divider()
    
    # Tabs principales (sin backup por ahora)
    tab1, tab2, tab3 = st.tabs(["🏠 Dashboard", "🏢 Empresas", "⚙️ Configuración"])
    
    # ===== TAB 1: DASHBOARD PRINCIPAL =====
    with tab1:
        st.header("📊 Dashboard Principal")
        
        # Métricas del sistema
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="📈 Empresas Activas",
                value="0",
                delta="Sin cambios",
                help="Número total de empresas registradas"
            )
        
        with col2:
            st.metric(
                label="💰 Ingresos Total",
                value="$0.00",
                delta="0%",
                help="Ingresos totales del período"
            )
        
        with col3:
            st.metric(
                label="📋 Proyectos Activos",
                value="0",
                delta="0 nuevos",
                help="Proyectos en desarrollo"
            )
        
        with col4:
            st.metric(
                label="☁️ Estado Sistema",
                value="🟢 Online",
                help="Estado general del sistema"
            )
        
        st.divider()
        
        # Sección de accesos rápidos
        st.subheader("🚀 Accesos Rápidos")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🏢 Gestionar Empresas", use_container_width=True, type="primary"):
                st.info("💡 Ve al tab **'🏢 Empresas'** para gestionar tus empresas")
                st.balloons()
        
        with col2:
            if st.button("📊 Generar Reportes", use_container_width=True):
                st.info("📈 **Función de reportes** - Próximamente disponible")
        
        with col3:
            if st.button("⚙️ Configurar Sistema", use_container_width=True):
                st.info("⚙️ Ve al tab **'⚙️ Configuración'** para ajustes")
        
        st.divider()
        
        # Información del sistema y actividad reciente
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("ℹ️ Estado del Sistema")
            st.success("🟢 **Base de datos:** Conectada y operativa")
            st.success("🟢 **Sesión de usuario:** Activa y autenticada")
            st.info(f"🎨 **Tema actual:** {st.session_state.get('theme_mode', 'Light')} Mode")
            st.warning("🟡 **Sistema de backup:** En desarrollo")
            
            # Espacio para métricas adicionales
            if st.checkbox("📈 Mostrar métricas avanzadas"):
                st.metric("🔄 Uptime", "99.9%")
                st.metric("⚡ Rendimiento", "Óptimo")
                st.metric("💾 Uso de memoria", "Normal")
        
        with col_right:
            st.subheader("📅 Actividad Reciente")
            
            # Simulación de actividad reciente
            with st.container():
                st.markdown("**🕒 Última actividad:**")
                st.caption(f"📅 **Fecha:** {datetime.now().strftime('%d/%m/%Y')}")
                st.caption(f"🕐 **Hora:** {datetime.now().strftime('%H:%M:%S')}")
                st.caption(f"👤 **Usuario:** {st.session_state.get('username', 'N/A')}")
                st.caption("🔐 **Acción:** Login exitoso")
                
                st.markdown("---")
                
                # Log de actividades (simulado)
                st.markdown("**📋 Historial reciente:**")
                activities = [
                    "🔐 Inicio de sesión",
                    "🏠 Acceso a dashboard", 
                    "⚙️ Configuración de sistema",
                    "🔄 Actualización de datos"
                ]
                
                for activity in activities:
                    st.caption(f"• {activity}")
    
    # ===== TAB 2: EMPRESAS =====
    with tab2:
        st.header("🏢 Gestión de Empresas")
        
        # Info placeholder
        st.info("📋 **Panel de gestión de empresas** - Aquí aparecerá toda la funcionalidad de empresas")
        
        # Botones principales
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("➕ Crear Nueva Empresa", use_container_width=True, type="primary"):
                st.success("✅ **Función crear empresa** - Implementar según tu lógica actual")
        
        with col2:
            if st.button("📝 Editar Empresa", use_container_width=True):
                st.info("📝 **Función editar empresa** - Seleccionar empresa existente")
        
        with col3:
            if st.button("📊 Ver Estadísticas", use_container_width=True):
                st.info("📊 **Estadísticas de empresas** - Reportes y métricas")
        
        st.divider()
        
        # Placeholder para lista de empresas
        st.subheader("📋 Lista de Empresas")
        st.markdown("""
        **Funcionalidades disponibles:**
        - ➕ **Crear nueva empresa** con información completa
        - 📝 **Editar empresa existente** - modificar datos
        - 🗑️ **Eliminar empresa** - con confirmación
        - 📊 **Ver detalles y métricas** por empresa
        - 🔍 **Buscar y filtrar** empresas
        - 📄 **Generar reportes** individuales
        """)
        
        # Aquí iría tu código actual de empresas cuando lo integres
        
    # ===== TAB 3: CONFIGURACIÓN =====
    with tab3:
        st.header("⚙️ Configuración del Sistema")
        
        # Configuración de apariencia
        st.subheader("🎨 Apariencia y Tema")
        
        col_theme, col_info = st.columns([1, 2])
        
        with col_theme:
            tema_actual = st.session_state.get("theme_mode", "Light")
            nuevo_tema = st.selectbox(
                "Seleccionar tema:",
                ["Light", "Dark"],
                index=0 if tema_actual == "Light" else 1,
                help="Cambia la apariencia de la interfaz"
            )
            
            if nuevo_tema != tema_actual:
                st.session_state.theme_mode = nuevo_tema
                st.success(f"✅ Tema cambiado a **{nuevo_tema} Mode**")
                st.rerun()
        
        with col_info:
            st.info(f"""
            **🎨 Configuración actual:**
            - **Tema activo:** {st.session_state.get('theme_mode', 'Light')} Mode
            - **Sesión:** {st.session_state.get('username', 'N/A')}
            - **Estado:** Conectado
            """)
        
        st.divider()
        
        # Configuración de backup
        st.subheader("💾 Sistema de Backup")
        st.warning("🚧 **En desarrollo** - Sistema de backup automático próximamente")
        
        st.markdown("""
        **🔄 Características planificadas:**
        - ✅ **Backup automático** cada 30 minutos
        - ✅ **Backup manual** con un clic
        - ✅ **Almacenamiento en GitHub** seguro
        - ✅ **Restauración** desde cualquier punto
        - ✅ **Historial** de cambios
        """)
        
        if st.button("🔧 Configurar Backup", disabled=True):
            st.info("⏳ Función en desarrollo...")
        
        st.divider()
        
        # Información del sistema
        st.subheader("🖥️ Información del Sistema")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📱 Aplicación:**")
            st.caption("• Nombre: S.A.N.D.I")
            st.caption("• Versión: 1.0.0")
            st.caption("• Estado: Activo")
            st.caption(f"• Tema: {st.session_state.get('theme_mode', 'Light')}")
        
        with col2:
            st.markdown("**👤 Sesión actual:**")
            st.caption(f"• Usuario: {st.session_state.get('username', 'N/A')}")
            st.caption(f"• Conectado desde: {datetime.now().strftime('%H:%M')}")
            st.caption("• Estado: Autenticado")
            st.caption("• Permisos: Administrador")
        
        # Panel de debug (solo para desarrollo)
        st.divider()
        if st.checkbox("🔍 Modo Debug (Desarrollo)", help="Mostrar información técnica"):
            st.subheader("🔧 Información de Debug")
            
            with st.expander("📱 Session State"):
                st.json(dict(st.session_state))
            
            with st.expander("🖥️ Variables del Sistema"):
                debug_info = {
                    "timestamp": datetime.now().isoformat(),
                    "theme_mode": st.session_state.get('theme_mode'),
                    "logged_in": st.session_state.get('logged_in', False),
                    "username": st.session_state.get('username'),
                }
                st.json(debug_info)
    
    # Modal flotante (tu código original - simplificado)
    if st.session_state.get('show_menu', False):
        
        # Overlay
        st.markdown("""
        <style>
        .modal-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: rgba(0,0,0,0.5);
            z-index: 999;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown("<div class='modal-overlay'></div>", unsafe_allow_html=True)
        
        # Contenido del modal
        with st.container():
            st.markdown("### ⚙️ Menú del Sistema")
            st.info("🔧 **Opciones del sistema** - En desarrollo")
            
            if st.button("✖️ Cerrar Menú", type="secondary"):
                st.session_state.show_menu = False
                st.rerun()
    
    # Botón flotante para abrir menú (opcional)
    if not st.session_state.get('show_menu', False):
        if st.sidebar.button("⚙️ Menú Opciones"):
            st.session_state.show_menu = True
            st.rerun()



