import streamlit as st
import pandas as pd
from db_utils import list_companies, add_company, delete_company

# Agregar al inicio de ui_inicio.py:
from backup_ui import mostrar_panel_backup_simple, mostrar_estado_backup_sidebar

# En tu función pantalla_inicio(), agregar esto donde quieras mostrar el panel:

def pantalla_inicio():
    # ... tu código existente ...
    
    # Mostrar estado en sidebar
    mostrar_estado_backup_sidebar()
    
    # Agregar tabs para organizar mejor
    tab1, tab2, tab3 = st.tabs(["🏠 Inicio", "🔄 Backups", "⚙️ Configuración"])
    
    with tab1:
        # Tu contenido actual de inicio aquí
        pass
    
    with tab2:
        mostrar_panel_backup_simple()
    
    with tab3:
        # Otras configuraciones
        st.info("Panel de configuraciones - próximamente")
    
    # ... resto de tu código ...


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
    from db_utils import (
        get_companies_with_logos, get_company_logo_base64, 
        get_company_info_complete
    )
    
    # Encabezado simple y limpio
    col1, col2, col3 = st.columns([8,1,1])
    with col1:
        st.title("Sistema de Gestión Empresarial")
    with col2:
        if st.button("🌙" if st.session_state.theme_mode=="Light" else "🌞", 
                    help="Cambiar tema"):
            st.session_state.theme_mode = "Dark" if st.session_state.theme_mode=="Light" else "Light"
            st.rerun()
    with col3:
        if st.button("⋮", help="Opciones del sistema"):
            st.session_state.show_menu = not st.session_state.show_menu
            st.rerun()

    # Modal flotante para opciones
    if st.session_state.show_menu:
        st.markdown("<div class='modal-overlay'></div>", unsafe_allow_html=True)
        
        bg = "#2d3e50" if st.session_state.theme_mode=="Dark" else "#ffffff"
        fg = "white" if st.session_state.theme_mode=="Dark" else "black"

        st.markdown(
            f"""
            <div class="modal" style="background:{bg}; color:{fg};">
                <h3>Opciones del Sistema</h3>
            </div>
            """, unsafe_allow_html=True
        )

        if st.button("Cerrar", key="close_modal"):
            st.session_state.show_menu = False
            st.session_state.delete_confirmation_step = 0
            st.session_state.empresa_to_delete = None
            st.rerun()

        st.markdown("#### Agregar Nueva Empresa")
        with st.form("form_add_empresa"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre de la empresa")
            with col2:
                descripcion = st.text_input("Descripción breve (opcional)")
            
            if st.form_submit_button("Crear Empresa", type="primary"):
                if nombre.strip():
                    from db_utils import add_company, update_company_info_complete
                    
                    if add_company(nombre.strip()):
                        if descripcion.strip():
                            empresas = list_companies()
                            nueva_empresa = empresas[empresas['name'] == nombre.strip()]
                            if not nueva_empresa.empty:
                                empresa_id = nueva_empresa.iloc[0]['id']
                                update_company_info_complete(empresa_id, {
                                    'name': nombre.strip(),
                                    'description': descripcion.strip()
                                })
                        
                        st.success("Empresa creada correctamente")
                        st.session_state.show_menu = False
                        st.rerun()
                    else:
                        st.error("Error al crear la empresa")
                else:
                    st.error("El nombre es obligatorio")

        empresas = list_companies()
        if not empresas.empty:
            st.markdown("#### Eliminar Empresa")
            empresa_sel = st.selectbox(
                "Seleccionar empresa:", 
                empresas["name"],
                key="empresa_delete_selector"
            )
            
            if st.session_state.delete_confirmation_step == 0:
                if st.button("Eliminar empresa seleccionada", type="secondary"):
                    st.session_state.empresa_to_delete = empresa_sel
                    st.session_state.delete_confirmation_step = 1
                    st.rerun()
            
            elif st.session_state.delete_confirmation_step == 1:
                st.error(f"¿Eliminar '{empresa_sel}'?")
                st.error("Esta acción eliminará TODOS los datos asociados y no se puede deshacer.")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Sí, eliminar", type="primary"):
                        st.session_state.delete_confirmation_step = 2
                        st.rerun()
                with col2:
                    if st.button("Cancelar"):
                        st.session_state.delete_confirmation_step = 0
                        st.session_state.empresa_to_delete = None
                        st.rerun()
            
            elif st.session_state.delete_confirmation_step == 2:
                st.error("CONFIRMACIÓN FINAL")
                st.error(f"Escriba 'CONFIRMAR' para eliminar '{empresa_sel}':")
                
                confirm_text = st.text_input("Confirmación:", key="confirm_delete_input")
                
                if st.button("ELIMINAR DEFINITIVAMENTE"):
                    if confirm_text == "CONFIRMAR":
                        empresa_id = empresas[empresas["name"]==empresa_sel]["id"].values[0]
                        
                        try:
                            from db_utils import delete_company_logo
                            delete_company_logo(int(empresa_id))
                        except:
                            pass
                        
                        delete_company(int(empresa_id), deleted_by=st.session_state.get("username", "admin"))
                        st.success(f"Empresa '{empresa_sel}' eliminada correctamente")
                        
                        st.session_state.show_menu = False
                        st.session_state.delete_confirmation_step = 0
                        st.session_state.empresa_to_delete = None
                        st.rerun()
                    else:
                        st.error("Texto de confirmación incorrecto")
                
                if st.button("Volver atrás"):
                    st.session_state.delete_confirmation_step = 1
                    st.rerun()

    # Obtener empresas
    empresas = get_companies_with_logos()
    if empresas.empty:
        st.markdown("""
        <div style='text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin: 20px 0;'>
            <h2>Bienvenido al Sistema</h2>
            <p style='font-size: 18px; margin: 20px 0;'>Comience creando su primera empresa para gestionar maquinaria, fluidos y mantenimiento</p>
            <p style='font-size: 14px; opacity: 0.8;'>Use el botón "⋮" en la esquina superior derecha para agregar una nueva empresa</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # TÍTULO COMPACTO - sin márgenes excesivos
    st.markdown("<h3 style='text-align:center; margin: 20px 0 10px 0;'>¿Con qué empresa trabajaremos hoy?</h3>", unsafe_allow_html=True)

    # Navegación de empresas
    start_idx = st.session_state.empresa_index
    end_idx = min(start_idx + 3, len(empresas))
    empresas_mostrar = empresas.iloc[start_idx:end_idx]
    
    # NAVEGACIÓN SIN CONTENEDORES VACÍOS
    col1, col2, col3 = st.columns([1, 8, 1])
    
    with col1:
        if start_idx > 0:
            if st.button("◀", key="left_arrow", help="Empresas anteriores"):
                st.session_state.empresa_index = max(0, start_idx - 3)
                st.rerun()
    
    # TARJETAS DE EMPRESAS - SIN CONTENEDORES VACÍOS
    with col2:
        cols = st.columns(len(empresas_mostrar))
        
        for idx, (_, row) in enumerate(empresas_mostrar.iterrows()):
            with cols[idx]:
                company_info = get_company_info_complete(row['id'])
                logo_base64 = get_company_logo_base64(row['id'])
                
                bg_color = "#2d3e50" if st.session_state.theme_mode == "Dark" else "#f8f9fa"
                text_color = "white" if st.session_state.theme_mode == "Dark" else "#333"
                border_color = "#4a6fa5" if st.session_state.theme_mode == "Dark" else "#dee2e6"
                
                # Tarjeta base
                st.markdown(
                    f"""
                    <div style="
                        background: {bg_color}; 
                        color: {text_color}; 
                        border: 2px solid {border_color};
                        border-radius: 15px;
                        padding: 20px;
                        text-align: center;
                        margin: 10px 0;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                        transition: all 0.3s ease;
                    ">
                    """, 
                    unsafe_allow_html=True
                )
                
                # Logo
                if logo_base64:
                    st.markdown(
                        f"""
                        <div style="display: flex; justify-content: center; margin: 15px 0;">
                            <img src="data:image/jpeg;base64,{logo_base64}" 
                                 style="width: 80px; height: 80px; object-fit: cover; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        """
                        <div style="display: flex; justify-content: center; margin: 15px 0;">
                            <div style="
                                width: 80px; 
                                height: 80px; 
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                border-radius: 10px;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                font-size: 35px;
                                color: white;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                            ">🏢</div>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                
                # Nombre
                st.markdown(
                    f"""
                    <h4 style="
                        margin: 10px 0; 
                        font-weight: bold; 
                        font-size: 18px;
                        color: {text_color};
                        text-align: center;
                    ">{row['name']}</h4>
                    """, 
                    unsafe_allow_html=True
                )
                
                # Fecha
                st.markdown(
                    f"""
                    <div style="
                        text-align: center; 
                        padding: 10px; 
                        background: rgba(0,0,0,0.05); 
                        margin: 10px -20px -20px -20px;
                        border-radius: 0 0 13px 13px;
                    ">
                        <small style="opacity: 0.6;">Registrada: {row['created_at'][:10]}</small>
                    </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
                # Botón
                if st.button(f"Acceder", key=f"btn_{row['id']}", use_container_width=True, type="primary"):
                    st.session_state["empresa_activa"] = row["id"]
                    st.session_state["empresa_activa_nombre"] = row["name"]
                    st.success(f"Accediendo a {row['name']}")
    
    with col3:
        if end_idx < len(empresas):
            if st.button("▶", key="right_arrow", help="Más empresas"):
                st.session_state.empresa_index = min(len(empresas) - 3, start_idx + 3)
                st.rerun()

