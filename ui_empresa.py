import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import shutil
import os
import json
from datetime import datetime, date, timedelta
from io import BytesIO
import xlsxwriter
import time

from db_utils import (
    list_machinery, delete_machinery, 
    add_fuel_log, get_fuel_logs, get_fuel_status_advanced,
    get_machine_classifications, add_machine_classification,
    get_machinery_report, get_fuel_report, get_critical_fuel_machines,
    get_conn, list_companies, get_unique_company_name, update_company_info_complete,
    add_machinery_with_backup, delete_machinery_with_backup, 
    update_machinery_with_backup, add_fuel_log_with_backup
)

from Maintenance_module import mostrar_mantenimiento, get_maintenance_summary
from controles_module import mostrar_controles, init_controles_db
from db_utils import get_critical_control_alerts
from controles_config import mostrar_configuracion_controles

try:
    from extras_module import mostrar_extras, get_extras_summary
    EXTRAS_MODULE_AVAILABLE = True
except ImportError:
    EXTRAS_MODULE_AVAILABLE = False

try:
    from statistics_ui import mostrar_estadisticas_avanzadas, configurar_pagina_estadisticas
    STATISTICS_MODULE_AVAILABLE = True
except ImportError:
    STATISTICS_MODULE_AVAILABLE = False



try:
    from extras_module import mostrar_extras, get_extras_summary
    EXTRAS_MODULE_AVAILABLE = True
except ImportError:
    EXTRAS_MODULE_AVAILABLE = False
    print("⚠️ Módulo EXTRAS no disponible")


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


def pantalla_empresa(empresa_id, empresa_nombre):
    # Inicializar base de datos de controles
    init_controles_db()
    
    # Estado para controlar las pestañas y confirmaciones
    if "current_tab" not in st.session_state:
        st.session_state.current_tab = "Máquinas"
    if "show_add_machine" not in st.session_state:
        st.session_state.show_add_machine = False
    if "show_delete_machine" not in st.session_state:
        st.session_state.show_delete_machine = False
    if "selected_machine_detail" not in st.session_state:
        st.session_state.selected_machine_detail = None
    if "delete_machinery_step" not in st.session_state:
        st.session_state.delete_machinery_step = 0
    if "machinery_to_delete" not in st.session_state:
        st.session_state.machinery_to_delete = None
    if "show_advanced_options" not in st.session_state:
        st.session_state.show_advanced_options = False
    if "delete_company_step" not in st.session_state:
        st.session_state.delete_company_step = 0
    
    # CSS para la interfaz de empresa (mantener el existente)
    st.markdown("""
    <style>
    .company-header {
        background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
    }
    .machinery-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #f9f9f9;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .machinery-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    .machinery-card-selected {
        border: 2px solid #4a6fa5;
        background-color: #f0f4ff;
    }
    .fuel-alert {
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .fuel-critical {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        color: #c62828;
    }
    .fuel-warning {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
        color: #ef6c00;
    }
    .fuel-excellent {
        background-color: #e8f5e8;
        border-left: 4px solid #4caf50;
        color: #2e7d32;
    }
    .fuel-ok {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        color: #1565c0;
    }
    .fuel-regular {
        background-color: #fffde7;
        border-left: 4px solid #ffeb3b;
        color: #f57f17;
    }
    .fuel-bad {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
        color: #ef6c00;
    }
    .advanced-options {
        border: 2px solid #ff9800;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #fff8e1;
    }
    .maintenance-alert {
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        background-color: #e8f5e8;
        border-left: 4px solid #4caf50;
        color: #2e7d32;
    }
    .maintenance-critical {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        color: #c62828;
    }
    .maintenance-warning {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
        color: #ef6c00;
    }
    .maintenance-overdue {
        background-color: #ffebee;
        border-left: 4px solid #d32f2f;
        color: #b71c1c;
        font-weight: bold;
    }
    .backup-section {
        border: 2px solid #4caf50;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #f1f8e9;
    }
    .danger-section {
        border: 2px solid #f44336;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #ffebee;
    }
    .extras-tab {
        background: linear-gradient(135deg, #ff6b6b 0%, #4ecdc4 100%);
        color: white;
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Encabezado de la empresa
    st.markdown(f"""
    <div class="company-header">
        <h2>{empresa_nombre}</h2>
        <p>Sistema de gestión integral de maquinaria y equipos</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Mostrar alertas críticas de todos los módulos
    mostrar_alertas_generales(empresa_id)
    
    # Barra de navegación con pestañas actualizadas (AGREGANDO EXTRAS)
    tabs = ["Máquinas", "Controles", "Mantenimiento", "Estadísticas", "Reportes", "Configuración", "EXTRAS"]
    cols = st.columns(len(tabs))
    
    for i, tab in enumerate(tabs):
        with cols[i]:
            # Estilo especial para EXTRAS
            if tab == "EXTRAS":
                button_key = f"tab_{i}"
                if st.button("🚀 EXTRAS", key=button_key, use_container_width=True, help="Funcionalidades Alpha"):
                    st.session_state.current_tab = tab
                    # Resetear estados al cambiar de pestaña
                    st.session_state.show_add_machine = False
                    st.session_state.show_delete_machine = False
                    st.session_state.selected_machine_detail = None
                    st.rerun()
            else:
                if st.button(tab, key=f"tab_{i}", use_container_width=True):
                    st.session_state.current_tab = tab
                    # Resetear estados al cambiar de pestaña
                    st.session_state.show_add_machine = False
                    st.session_state.show_delete_machine = False
                    st.session_state.selected_machine_detail = None
                    st.rerun()
    
    # Contenido de cada pestaña
    if st.session_state.current_tab == "Máquinas":
        mostrar_maquinas(empresa_id)
    
    elif st.session_state.current_tab == "Controles":
        mostrar_controles(empresa_id)
    
    elif st.session_state.current_tab == "Mantenimiento":
        mostrar_mantenimiento(empresa_id)
    
    elif st.session_state.current_tab == "Estadísticas":
       mostrar_estadisticas(empresa_id)
    
    elif st.session_state.current_tab == "Reportes":
        mostrar_reportes(empresa_id, empresa_nombre)
    
    elif st.session_state.current_tab == "Configuración":
        mostrar_configuracion(empresa_id, empresa_nombre)
    
    elif st.session_state.current_tab == "EXTRAS":
        mostrar_extras_tab(empresa_id, empresa_nombre)
    
    # Botón para volver a la vista principal
    if st.button("← Volver al listado de empresas"):
        if "empresa_activa" in st.session_state:
            del st.session_state["empresa_activa"]
        if "empresa_activa_nombre" in st.session_state:
            del st.session_state["empresa_activa_nombre"]
        st.rerun()


def mostrar_alertas_generales(empresa_id):
    """Muestra alertas críticas de todos los módulos"""
    
    # Alertas de combustible (mantenemos compatibilidad)
    critical_machines = get_critical_fuel_machines(empresa_id)
    
    if critical_machines:
        for machine in critical_machines:
            if machine['status'] == 'critical':
                st.markdown(f"""
                <div class="fuel-alert fuel-critical">
                    <strong>🚨 COMBUSTIBLE CRÍTICO:</strong> {machine['name']} ({machine.get('identifier', 'Sin matrícula')}) - {machine['message']}
                </div>
                """, unsafe_allow_html=True)
            elif machine['status'] == 'warning':
                st.markdown(f"""
                <div class="fuel-alert fuel-warning">
                    <strong>⚠️ COMBUSTIBLE BAJO:</strong> {machine['name']} ({machine.get('identifier', 'Sin matrícula')}) - {machine['message']}
                </div>
                """, unsafe_allow_html=True)
    
    # Nuevas alertas del módulo de controles
    try:
        control_alerts = get_critical_control_alerts(empresa_id)
        
        if control_alerts:
            for alert in control_alerts:
                alert_class = f"fuel-{alert['level']}"
                icon = get_alert_icon(alert['level'])
                st.markdown(f"""
                <div class="fuel-alert {alert_class}">
                    <strong>{icon} {alert['type'].upper()}:</strong> {alert['machine_name']} ({alert.get('identifier', 'Sin matrícula')}) - {alert['message']}
                </div>
                """, unsafe_allow_html=True)
    except Exception:
        pass  # Módulo de controles no disponible
    
    # Alertas de mantenimiento
    try:
        from Maintenance_module import get_critical_maintenance_alerts
        critical_maintenance = get_critical_maintenance_alerts(empresa_id)
        if critical_maintenance:
            for machine in critical_maintenance:
                if machine['type'] == 'VENCIDO':
                    st.markdown(f"""
                    <div class="fuel-alert fuel-critical">
                        <strong>🔧 MANTENIMIENTO VENCIDO:</strong> {machine['machine_name']} ({machine.get('identifier', 'Sin matrícula')}) - {machine['message']}
                    </div>
                    """, unsafe_allow_html=True)
                elif machine['type'] == 'CRÍTICO':
                    st.markdown(f"""
                    <div class="fuel-alert fuel-warning">
                        <strong>🔧 MANTENIMIENTO CRÍTICO:</strong> {machine['machine_name']} ({machine.get('identifier', 'Sin matrícula')}) - {machine['message']}
                    </div>
                    """, unsafe_allow_html=True)
    except Exception:
        pass  # Módulo de mantenimiento no disponible
    
    # Alertas del módulo EXTRAS (NUEVA FUNCIONALIDAD)
    try:
        from db_utils import get_extras_dashboard_summary
        extras_summary = get_extras_dashboard_summary(empresa_id)
        
        if 'error' not in extras_summary:
            # Mostrar alertas de costos no detallados
            if extras_summary.get('total_detailed_maintenances', 0) == 0:
                from db_utils import get_maintenance_records
                recent_maintenances = get_maintenance_records(empresa_id, limit=5)
                if not recent_maintenances.empty:
                    maintenance_count = len(recent_maintenances)
                    st.markdown(f"""
                    <div class="fuel-alert fuel-warning">
                        <strong>💰 COSTOS SIN DETALLAR:</strong> Tienes {maintenance_count} mantenimientos recientes sin detalles de costo - Ve a EXTRAS > Costos Específicos
                    </div>
                    """, unsafe_allow_html=True)
    except Exception:
        pass  # Módulo EXTRAS no disponible

def get_alert_icon(level):
    """Obtiene el icono apropiado para cada nivel de alerta"""
    icons = {
        "excelente": "✅",
        "ok": "🔵",
        "regular": "🟡", 
        "malo": "🟠",
        "critico": "🚨"
    }
    return icons.get(level, "⚠️")

def mostrar_maquinas(empresa_id):
    st.header("Gestión de Máquinas")
    
    # Botones de acción
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("➕ Añadir Máquina", use_container_width=True):
            st.session_state.show_add_machine = not st.session_state.show_add_machine
            st.session_state.show_delete_machine = False
            st.session_state.selected_machine_detail = None
            st.rerun()
    
    with col2:
        if st.button("🗑️ Eliminar Máquina", use_container_width=True):
            st.session_state.show_delete_machine = not st.session_state.show_delete_machine
            st.session_state.show_add_machine = False
            st.session_state.selected_machine_detail = None
            st.rerun()
    
    # Formulario para añadir máquina
    if st.session_state.show_add_machine:
        mostrar_formulario_anadir_maquina(empresa_id)
    
    # Interfaz para eliminar máquina
    if st.session_state.show_delete_machine:
        mostrar_formulario_eliminar_maquina(empresa_id)
    
    # Lista de máquinas con filtros
    mostrar_lista_maquinas(empresa_id)

def mostrar_formulario_anadir_maquina(empresa_id):
    st.subheader("Añadir Nueva Máquina")
    
    with st.form(f"form_add_machinery_{empresa_id}"):
        # Fila 1
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Nombre de la máquina *", help="Nombre identificativo de la máquina")
            identifier = st.text_input("Matrícula/Identificador *", help="Número de placa o identificador único")
        
        with col2:
            model = st.text_input("Modelo", help="Modelo de la máquina")
            serial_number = st.text_input("Número de serie", help="Número de serie del fabricante")
        
        # Fila 2
        col3, col4 = st.columns(2)
        with col3:
            # Clasificación dinámica
            classifications = get_machine_classifications()
            classification = st.selectbox("Clasificación *", classifications)
            
            # Opción para añadir nueva clasificación
            if st.checkbox("Añadir nueva clasificación"):
                new_classification = st.text_input("Nueva clasificación")
                if new_classification and st.button("Agregar clasificación"):
                    if add_machine_classification(new_classification.strip()):
                        st.success("Clasificación añadida")
                        st.rerun()
                    else:
                        st.error("La clasificación ya existe")
        
        with col4:
            # Consumo actualizado a por hora
            consumption_per_hour = st.number_input(
                "Consumo promedio (gal/hora) *", 
                min_value=0.0, 
                step=0.1, 
                format="%.2f",
                help="Consumo promedio por hora de trabajo"
            )
            status = st.selectbox("Estado", ["Active", "Maintenance", "Inactive"])
        
        # Fila 3 - Información adicional para controles
        col5, col6 = st.columns(2)
        with col5:
            purchase_date = st.date_input("Fecha de compra", help="Fecha de adquisición de la máquina")
            current_hours = st.number_input("Horas actuales", min_value=0.0, step=0.1, format="%.1f", 
                                          help="Horas actuales en el horómetro")
        
        with col6:
            current_odometer = st.number_input("Odómetro actual", min_value=0.0, step=0.1, format="%.1f",
                                             help="Lectura actual del odómetro (para vehículos)")
        
        # Validación
        required_fields = [name, identifier, classification]
        is_valid = all(field.strip() if isinstance(field, str) else field for field in required_fields) and consumption_per_hour >= 0
        
        if st.form_submit_button("Añadir Máquina"):
            if is_valid:
                try:
                    add_machinery_extended(
                    
                        success = add_machinery_with_backup(
                            empresa_id, 
                            name.strip(), 
                            model.strip() if model else None, 
                            serial_number.strip() if serial_number else None,
                            identifier.strip(),
                            classification,
                            consumption_per_hour,
                            purchase_date.isoformat() if purchase_date else None, 
                            status,
                            current_hours,
                            current_odometer
                        )

                    st.success("Máquina añadida correctamente")
                    st.session_state.show_add_machine = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al añadir la máquina: {str(e)}")
            else:
                st.error("Por favor, complete los campos obligatorios (*)")

def mostrar_formulario_eliminar_maquina(empresa_id):
    st.subheader("Eliminar Máquina")
    
    maquinarias = list_machinery(empresa_id)
    if maquinarias.empty:
        st.info("No hay máquinas registradas para esta empresa.")
        return
    
    # Selectbox para elegir máquina
    def format_machine(machine_id):
        machine = maquinarias.loc[maquinarias['id'] == machine_id].iloc[0]
        return f"{machine.get('name', 'Sin nombre')} - {machine.get('identifier', 'Sin matrícula')} ({machine.get('classification', 'Sin clasificar')})"
    
    machine_id = st.selectbox(
        "Seleccionar máquina a eliminar",
        maquinarias['id'].tolist(),
        format_func=format_machine
    )
    
    if machine_id:
        # Mostrar información de la máquina y registros relacionados
        selected_machine = maquinarias.loc[maquinarias['id'] == machine_id].iloc[0]
        fuel_logs = get_fuel_logs(machine_id)
        
        st.warning(f"**Máquina seleccionada:** {selected_machine.get('name', 'Sin nombre')}")
        st.info(f"**Registros de combustible:** {len(fuel_logs)}")
        
        if len(fuel_logs) > 0:
            st.error("⚠️ Esta máquina tiene registros de combustible que también serán eliminados.")
        
        # Proceso de confirmación
        if st.button("🗑️ Proceder con eliminación", type="primary"):
            st.session_state.machinery_to_delete = machine_id
            st.session_state.delete_machinery_step = 1
            st.rerun()
    
    # Confirmación final
    if st.session_state.delete_machinery_step == 1 and st.session_state.machinery_to_delete:
        machine_to_delete = maquinarias.loc[maquinarias['id'] == st.session_state.machinery_to_delete].iloc[0]
        
        st.error(f"**CONFIRMAR ELIMINACIÓN DE:** {machine_to_delete.get('name', 'Sin nombre')}")
        st.error("Esta acción NO SE PUEDE DESHACER")
        
        confirm_text = st.text_input("Escriba 'CONFIRMAR' para proceder:")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Eliminar definitivamente"):
                if confirm_text == "CONFIRMAR":
                    try:
                        result = delete_machinery(
                            
                            result = delete_machinery_with_backup(
                                st.session_state.machinery_to_delete,
                                deleted_by=st.session_state.get("username", "admin")
                            )
                        if result:
                            st.success(f"Máquina eliminada correctamente")
                        else:
                            st.error("Error: La máquina no existe o ya fue eliminada")
                        
                        # Resetear estado
                        st.session_state.delete_machinery_step = 0
                        st.session_state.machinery_to_delete = None
                        st.session_state.show_delete_machine = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {str(e)}")
                else:
                    st.error("Texto de confirmación incorrecto")
        
        with col2:
            if st.button("❌ Cancelar"):
                st.session_state.delete_machinery_step = 0
                st.session_state.machinery_to_delete = None
                st.rerun()

def mostrar_lista_maquinas(empresa_id):
    st.subheader("Lista de Máquinas")
    
    maquinarias = list_machinery(empresa_id)
    if maquinarias.empty:
        st.info("No hay máquinas registradas para esta empresa.")
        return
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtro por clasificación
        all_classifications = ["Todas"] + list(maquinarias['classification'].dropna().unique())
        filtro_clasificacion = st.selectbox("Filtrar por clasificación", all_classifications)
    
    with col2:
        # Filtro por estado
        filtro_estado = st.selectbox("Filtrar por estado", ["Todos", "Active", "Maintenance", "Inactive"])
    
    with col3:
        # Buscador
        buscar = st.text_input("Buscar por nombre o matrícula", placeholder="Escriba para buscar...")
    
    # Aplicar filtros
    df_filtrado = maquinarias.copy()
    
    if filtro_clasificacion != "Todas":
        df_filtrado = df_filtrado[df_filtrado['classification'] == filtro_clasificacion]
    
    if filtro_estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado['status'] == filtro_estado]
    
    if buscar:
        buscar_norm = buscar.strip().lower()
        if buscar_norm:
            mask = (
                df_filtrado['name'].str.lower().str.contains(buscar_norm, na=False) |
                df_filtrado['identifier'].str.lower().str.contains(buscar_norm, na=False)
            )
            df_filtrado = df_filtrado[mask]
    
    if df_filtrado.empty:
        st.warning("No hay máquinas que coincidan con los filtros.")
        return
    
    # Lista desplegable de máquinas
    opciones_maquinas = []
    for _, machine in df_filtrado.iterrows():
        nombre = machine.get('name', 'Sin nombre')
        matricula = machine.get('identifier', 'Sin matrícula')
        clasificacion = machine.get('classification', 'Sin clasificar')
        opciones_maquinas.append(f"{nombre} - {matricula} ({clasificacion})")
    
    maquina_seleccionada = st.selectbox(
        "Seleccione una máquina para ver detalles:",
        options=opciones_maquinas,
        index=0 if opciones_maquinas else None
    )
    
    if maquina_seleccionada:
        # Obtener el ID de la máquina seleccionada
        selected_index = opciones_maquinas.index(maquina_seleccionada)
        selected_machine = df_filtrado.iloc[selected_index]
        
        # Mostrar detalles de la máquina seleccionada
        fuel_status = get_fuel_status_advanced(selected_machine['id'])
        mostrar_detalles_maquina(selected_machine, fuel_status)

def mostrar_detalles_maquina(machine, fuel_status):
    """Muestra detalles completos de una máquina seleccionada"""
    
    with st.container():
        st.markdown("### Detalles de la Máquina")
        
        # Información básica en columnas
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Nombre", machine.get('name', 'Sin nombre'))
            st.metric("Matrícula", machine.get('identifier', 'Sin matrícula'))
            st.metric("Modelo", machine.get('model', 'No especificado'))
            st.metric("Horas Actuales", f"{machine.get('current_hours', 0) or 0:.1f}")
        
        with col2:
            st.metric("Clasificación", machine.get('classification', 'Sin clasificar'))
            st.metric("Estado", machine['status'])
            st.metric("Número de Serie", machine.get('serial_number', 'No especificado'))
            st.metric("Odómetro Actual", f"{machine.get('current_odometer', 0) or 0:.1f}")
        
        with col3:
            # Consumo actualizado
            consumption_hour = machine.get('consumption_per_hour', machine.get('consumption_rate', 0)) or 0
            st.metric("Consumo (gal/hora)", f"{consumption_hour:.2f}")
            
            purchase_date = machine.get('purchase_date', 'No especificada')
            if purchase_date:
                try:
                    formatted_date = pd.to_datetime(purchase_date).strftime('%Y-%m-%d')
                except:
                    formatted_date = purchase_date
            else:
                formatted_date = "No especificada"
            st.metric("Fecha de Compra", formatted_date)
            st.metric("Último Mantenimiento", machine.get('last_maintenance', 'No registrado'))
        
        # Estado del combustible
        st.markdown("#### Estado del Combustible")
        if fuel_status['status'] == 'error':
            st.error(fuel_status['message'])
        else:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Combustible Restante", f"{fuel_status.get('remaining', 0):.1f} gal")
            with col2:
                st.metric("Días Restantes", f"{fuel_status.get('days_remaining', 0):.1f}")
            with col3:
                st.metric("Total Agregado", f"{fuel_status.get('total_added', 0):.1f} gal")
            with col4:
                st.metric("Consumido", f"{fuel_status.get('consumed', 0):.1f} gal")
        
        # Formulario de edición
        with st.expander("Editar información de la máquina"):
            mostrar_formulario_edicion_maquina(machine)

def mostrar_formulario_edicion_maquina(machine):
    """Formulario para editar información de una máquina"""
    
    with st.form(f"edit_machine_{machine['id']}"):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Nombre", value=machine.get('name', ''))
            new_identifier = st.text_input("Matrícula", value=machine.get('identifier', ''))
            new_model = st.text_input("Modelo", value=machine.get('model', '') or '')
            new_consumption = st.number_input(
                "Consumo (gal/hora)", 
                value=float(machine.get('consumption_per_hour', machine.get('consumption_rate', 0)) or 0),
                min_value=0.0,
                step=0.1,
                format="%.2f"
            )
        with col2:
            classifications = get_machine_classifications()
            current_classification = machine.get('classification', '')
            if current_classification in classifications:
                class_index = classifications.index(current_classification)
            else:
                class_index = 0
            new_classification = st.selectbox("Clasificación", classifications, index=class_index)
            # Manejar estados en español e inglés
            status_options = ["Active", "Maintenance", "Inactive"]
            current_status = normalize_status(machine.get('status', 'Active'))
            try:
                status_index = status_options.index(current_status)
            except ValueError:
                status_index = 0
            new_status = st.selectbox(
                "Estado", 
                status_options,
                index=status_index
            )
            new_hours = st.number_input(
                "Horas actuales",
                value=float(machine.get('current_hours', 0) or 0),
                min_value=0.0,
                step=0.1,
                format="%.1f"
            )
            new_odometer = st.number_input(
                "Odómetro actual",
                value=float(machine.get('current_odometer', 0) or 0),
                min_value=0.0,
                step=0.1,
                format="%.1f"
            )
        new_serial = st.text_input("Número de Serie", value=machine.get('serial_number', '') or '')
        new_maintenance = st.date_input("Último Mantenimiento", value=None)
        if st.form_submit_button("Guardar Cambios"):
            try:
                update_data = {
                    'name': new_name.strip() if new_name.strip() else machine.get('name'),
                    'identifier': new_identifier.strip() if new_identifier.strip() else machine.get('identifier'),
                    'model': new_model.strip() if new_model.strip() else None,
                    'classification': new_classification,
                    'consumption_per_hour': new_consumption,
                    'status': new_status,  # Ya está en inglés
                    'serial_number': new_serial.strip() if new_serial.strip() else None,
                    'current_hours': new_hours,
                    'current_odometer': new_odometer
                }
                if new_maintenance:
                    update_data['last_maintenance'] = new_maintenance.isoformat()
                
                update_machinery_with_backup(machine['id'], **update_data)
                st.success("Información actualizada correctamente")
                st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar: {str(e)}")

def normalize_status(status):
    """Normaliza los estados de máquina a inglés para consistencia en la base de datos"""
    status_mapping = {
        'Activo': 'Active',
        'Active': 'Active',
        'Mantenimiento': 'Maintenance', 
        'Maintenance': 'Maintenance',
        'Inactivo': 'Inactive',
        'Inactive': 'Inactive'
    }
    return status_mapping.get(status, 'Active')

def get_localized_status_options():
    """Retorna opciones de estado localizadas"""
    return {
        'Active': 'Activo',
        'Maintenance': 'Mantenimiento',
        'Inactive': 'Inactivo'
    }

def mostrar_estadisticas(empresa_id):
    """Módulo de estadísticas unificado - versión avanzada o básica según disponibilidad"""
    
    # Obtener nombre de empresa
    try:
        empresas = list_companies()
        empresa = empresas[empresas['id'] == empresa_id]
        empresa_nombre = empresa.iloc[0]['name'] if not empresa.empty else f"Empresa {empresa_id}"
    except:
        empresa_nombre = f"Empresa {empresa_id}"
    
    # Verificar disponibilidad del módulo avanzado
    if STATISTICS_MODULE_AVAILABLE:
        try:
            # Usar módulo avanzado
            mostrar_estadisticas_avanzadas(empresa_id, empresa_nombre)
            return
        except Exception as e:
            st.error(f"Error en estadísticas avanzadas: {e}")
            st.warning("Usando versión básica como fallback")
    
    # Versión básica mejorada (FALLBACK)
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 15px; color: white; margin-bottom: 20px;">
        <h1>📊 Estadísticas del Sistema</h1>
        <p>Análisis de maquinaria y operaciones</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not STATISTICS_MODULE_AVAILABLE:
        st.info("💡 Para análisis avanzado: pip install plotly scipy scikit-learn")
    
    maquinarias = list_machinery(empresa_id)
    if maquinarias.empty:
        st.info("No hay máquinas registradas para generar estadísticas.")
        return
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Máquinas", len(maquinarias))
    
    with col2:
        activas = len(maquinarias[maquinarias['status'] == 'Active'])
        st.metric("Máquinas Activas", activas)
    
    with col3:
        en_mantenimiento = len(maquinarias[maquinarias['status'] == 'Maintenance'])
        st.metric("En Mantenimiento", en_mantenimiento)
    
    with col4:
        try:
            critical_machines = get_critical_fuel_machines(empresa_id)
            critical_count = len([m for m in critical_machines if m['status'] == 'critical'])
            st.metric("Combustible Crítico", critical_count)
        except:
            st.metric("Combustible Crítico", "N/A")
    
    # Gráficos básicos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distribución por Estado")
        status_counts = maquinarias['status'].value_counts()
        fig_status = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Estados de Máquinas"
        )
        st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        st.subheader("Distribución por Clasificación")
        if 'classification' in maquinarias.columns:
            class_counts = maquinarias['classification'].value_counts()
            if not class_counts.empty:
                fig_class = px.pie(
                    values=class_counts.values,
                    names=class_counts.index,
                    title="Distribución por Clasificación"
                )
                st.plotly_chart(fig_class, use_container_width=True)
    
    # Análisis de combustible
    st.subheader("Análisis de Combustible")
    
    fuel_analysis = []
    for _, machine in maquinarias.iterrows():
        consumption = machine.get('consumption_per_hour', machine.get('consumption_rate', 0)) or 0
        if consumption > 0:
            fuel_status = get_fuel_status_advanced(machine['id'])
            if fuel_status['status'] != 'error':
                fuel_analysis.append({
                    'Máquina': machine.get('name', 'Sin nombre'),
                    'Matrícula': machine.get('identifier', 'Sin matrícula'),
                    'Combustible Restante': fuel_status.get('remaining', 0),
                    'Días Restantes': fuel_status.get('days_remaining', 0),
                    'Estado': fuel_status['status']
                })
    
    if fuel_analysis:
        df_fuel = pd.DataFrame(fuel_analysis)
        st.dataframe(df_fuel, use_container_width=True)
    else:
        st.info("No hay datos suficientes para el análisis de combustible.")
    
    # Información sobre upgrade
    if not STATISTICS_MODULE_AVAILABLE:
        with st.expander("🚀 Actualizar a Estadísticas Avanzadas"):
            st.markdown("""
            ### Funciones Adicionales Disponibles:
            - 📈 Análisis predictivo con Machine Learning
            - 💰 ROI y análisis financiero detallado  
            - ⚡ Métricas de eficiencia operacional
            - ⛽ Optimización inteligente de consumo
            - 📊 Dashboards interactivos avanzados
            
            **Instalación:** `pip install plotly scipy scikit-learn numpy`
            """)

def mostrar_reportes(empresa_id, empresa_nombre):
    st.header("Reportes y Exportación")
    
    # Reportes de maquinaria
    st.subheader("Reporte de Maquinaria")
    
    machinery_data = get_machinery_report(empresa_id)
    if not machinery_data.empty:
        st.dataframe(machinery_data, use_container_width=True)
        
        # Generar Excel mejorado
        excel_machinery = generate_excel_report(machinery_data, "Reporte_Maquinaria", empresa_nombre)
        st.download_button(
            label="Descargar Reporte de Maquinaria (Excel)",
            data=excel_machinery,
            file_name=f"Reporte_Maquinaria_{empresa_nombre}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No hay datos de maquinaria para reportar.")
    
    st.subheader("Reporte de Combustible")
    
    fuel_data = get_fuel_report(empresa_id)
    if not fuel_data.empty:
        st.dataframe(fuel_data, use_container_width=True)
        
        # Generar Excel mejorado
        excel_fuel = generate_excel_report(fuel_data, "Reporte_Combustible", empresa_nombre)
        st.download_button(
            label="Descargar Reporte de Combustible (Excel)",
            data=excel_fuel,
            file_name=f"Reporte_Combustible_{empresa_nombre}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No hay datos de combustible para reportar.")

def generate_excel_report(data, report_type, company_name):
    """Genera un archivo Excel con formato profesional"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        data.to_excel(writer, sheet_name=report_type, index=False)
        
        workbook = writer.book
        worksheet = writer.sheets[report_type]
        
        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BD',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'top',
            'border': 1
        })
        
        # Aplicar formato al encabezado
        for col_num, value in enumerate(data.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Aplicar formato a las celdas
        for row in range(1, len(data) + 1):
            for col in range(len(data.columns)):
                worksheet.write(row, col, data.iloc[row-1, col], cell_format)
        
        # Ajustar ancho de columnas
        for i, col in enumerate(data.columns):
            max_len = max(data[col].astype(str).str.len().max(), len(col)) + 2
            worksheet.set_column(i, i, min(max_len, 50))
        
        # Añadir información del reporte
        info_sheet = workbook.add_worksheet('Información')
        info_sheet.write('A1', 'Reporte Generado para:', header_format)
        info_sheet.write('B1', company_name)
        info_sheet.write('A2', 'Fecha de Generación:', header_format)
        info_sheet.write('B2', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        info_sheet.write('A3', 'Tipo de Reporte:', header_format)
        info_sheet.write('B3', report_type)
        info_sheet.set_column('A:B', 25)
    
    output.seek(0)
    return output.getvalue()

def mostrar_configuracion(empresa_id, empresa_nombre):
    """Función de configuración actualizada con nuevo sistema de respaldos"""
    st.header("Configuración del Sistema")
    
    # Tabs actualizados para incluir el nuevo sistema de respaldos
    config_tabs = st.tabs(["General", "Respaldo", "Avanzadas", "EXTRAS"])
    
    with config_tabs[0]:
        mostrar_config_general(empresa_id, empresa_nombre)
    
    with config_tabs[1]:
        mostrar_respaldo(empresa_id, empresa_nombre)
    
    with config_tabs[2]:
        mostrar_config_avanzadas(empresa_id, empresa_nombre)
    
    with config_tabs[3]:
        mostrar_config_extras(empresa_id, empresa_nombre)

# Reemplazar la función mostrar_config_general en ui_empresa.py

def mostrar_config_general(empresa_id, empresa_nombre):
    """Configuración general con panel de backup integrado"""
    from db_utils import (
        get_company_info_complete, update_company_info_complete, 
        save_company_logo, delete_company_logo, validate_company_info,
        get_company_logo_base64, get_company_logo_path,
        get_backup_status, manual_backup_now, restore_from_cloud
    )
    
    st.subheader("Configuración General")
    
    # PANEL DE BACKUP INTEGRADO - DESTACADO
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 20px 0;
        color: white;
        box-shadow: 0 4px 12px rgba(40, 167, 69, 0.3);
    ">
        <h4 style="margin: 0 0 10px 0; display: flex; align-items: center;">
            <span style="margin-right: 10px;">☁️</span>
            Sistema de Respaldo
        </h4>
        <p style="margin: 0; opacity: 0.9; font-size: 14px;">
            Mantén tus datos seguros con respaldo automático cada 10 minutos y manual cuando lo necesites
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Estado del backup
    backup_status = get_backup_status()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if backup_status["connected"]:
            st.success("🟢 Conectado")
        else:
            st.error("🔴 Desconectado")
    
    with col2:
        st.metric("Backups", backup_status["total_backups"])
    
    with col3:
        if backup_status["last_backup_time"]:
            # Formatear tiempo desde el formato YYYYMMDD_HHMMSS
            try:
                from datetime import datetime
                time_str = backup_status["last_backup_time"]
                if "_" in time_str:
                    date_part, time_part = time_str.split("_")
                    formatted_time = f"{time_part[:2]}:{time_part[2:4]}"
                    st.metric("Último", formatted_time)
                else:
                    st.metric("Último", "N/A")
            except:
                st.metric("Último", "N/A")
        else:
            st.metric("Último", "Nunca")
    
    with col4:
        st.metric("Auto-backup", "✅ Activo")
    
    # Botones de backup
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Guardar Ahora", type="primary", use_container_width=True):
            with st.spinner("Guardando en la nube..."):
                success, message = manual_backup_now()
                if success:
                    st.success("✅ Guardado exitosamente")
                    st.rerun()
                else:
                    st.error(f"❌ Error: {message}")
    
    with col2:
        if st.button("📥 Restaurar desde Nube", type="secondary", use_container_width=True):
            if "restore_confirm" not in st.session_state:
                st.session_state.restore_confirm = False
            
            if not st.session_state.restore_confirm:
                st.session_state.restore_confirm = True
                st.rerun()
    
    with col3:
        if backup_status["connected"]:
            st.success("🔄 Auto: 10 min")
        else:
            st.error("🔄 Auto: OFF")
    
    # Confirmación de restauración
    if st.session_state.get("restore_confirm", False):
        st.warning("⚠️ **RESTAURAR DESDE LA NUBE**")
        st.warning("Esto reemplazará todos los datos actuales con el último backup.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirmar Restauración"):
                with st.spinner("Restaurando desde la nube..."):
                    success, message = restore_from_cloud()
                    if success:
                        st.success("✅ Restauración exitosa")
                        st.info("La página se recargará automáticamente...")
                        st.session_state.restore_confirm = False
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ Error: {message}")
        with col2:
            if st.button("❌ Cancelar"):
                st.session_state.restore_confirm = False
                st.rerun()
    
    st.divider()
    
    # Información de la empresa (mantener el código existente)
    info_tabs = st.tabs(["📋 Información Básica", "🖼️ Logo y Marca"])
    
    with info_tabs[0]:
        # Tu código existente de información básica aquí...
        company_info = get_company_info_complete(empresa_id)
        if not company_info:
            company_info = {'name': empresa_nombre}
        
        with st.form(f"form_empresa_info_{empresa_id}"):
            st.markdown("#### Datos Generales")
            col1, col2 = st.columns(2)
            
            with col1:
                nombre_empresa = st.text_input(
                    "Nombre de la empresa *", 
                    value=company_info.get('name', ''),
                    help="Nombre oficial de la empresa"
                )
                
                email = st.text_input(
                    "Correo electrónico", 
                    value=company_info.get('email', ''),
                    help="Email principal de contacto"
                )
                
                telefono = st.text_input(
                    "Teléfono", 
                    value=company_info.get('phone', ''),
                    help="Número de teléfono principal"
                )
                
                propietario = st.text_input(
                    "Propietario/Responsable", 
                    value=company_info.get('owner_name', ''),
                    help="Nombre del propietario o responsable principal"
                )
            
            with col2:
                direccion = st.text_area(
                    "Dirección", 
                    value=company_info.get('address', ''),
                    help="Dirección física de la empresa"
                )
                
                website = st.text_input(
                    "Sitio web", 
                    value=company_info.get('website', ''),
                    help="URL del sitio web (opcional)"
                )
                
                industria = st.selectbox(
                    "Industria/Sector",
                    options=[
                        "", "Construcción", "Minería", "Agricultura", 
                        "Transporte", "Manufactura", "Servicios", 
                        "Tecnología", "Energía", "Otro"
                    ],
                    index=0 if not company_info.get('industry') else (
                        ["", "Construcción", "Minería", "Agricultura", 
                         "Transporte", "Manufactura", "Servicios", 
                         "Tecnología", "Energía", "Otro"].index(company_info.get('industry'))
                        if company_info.get('industry') in 
                        ["", "Construcción", "Minería", "Agricultura", 
                         "Transporte", "Manufactura", "Servicios", 
                         "Tecnología", "Energía", "Otro"] else 0
                    )
                )
                
                num_empleados = st.number_input(
                    "Número de empleados", 
                    min_value=0, 
                    value=int(company_info.get('employee_count', 0)),
                    help="Cantidad aproximada de empleados"
                )
            
            st.markdown("#### Información Adicional")
            col3, col4 = st.columns(2)
            
            with col3:
                fecha_fundacion = st.date_input(
                    "Fecha de fundación",
                    value=pd.to_datetime(company_info.get('foundation_date')).date() 
                          if company_info.get('foundation_date') else None,
                    help="Fecha de fundación o inicio de operaciones"
                )
                
                rnc_fiscal = st.text_input(
                    "RNC/ID Fiscal", 
                    value=company_info.get('tax_id', ''),
                    help="Registro Nacional de Contribuyentes o ID fiscal"
                )
            
            with col4:
                descripcion = st.text_area(
                    "Descripción", 
                    value=company_info.get('description', ''),
                    help="Descripción breve de la empresa y sus actividades",
                    height=100
                )
            
            if st.form_submit_button("💾 Guardar Información", type="primary"):
                datos_actualizados = {
                    'name': nombre_empresa.strip(),
                    'email': email.strip(),
                    'phone': telefono.strip(),
                    'address': direccion.strip(),
                    'owner_name': propietario.strip(),
                    'foundation_date': fecha_fundacion.isoformat() if fecha_fundacion else '',
                    'tax_id': rnc_fiscal.strip(),
                    'description': descripcion.strip(),
                    'website': website.strip(),
                    'industry': industria,
                    'employee_count': num_empleados
                }
                
                errores = validate_company_info(datos_actualizados)
                
                if errores:
                    for error in errores:
                        st.error(f"❌ {error}")
                else:
                    success, message = update_company_info_complete(empresa_id, datos_actualizados)
                    
                    if success:
                        st.success("✅ Información actualizada correctamente")
                        # Trigger backup después de actualizar info importante
                        from db_utils import trigger_backup_after_critical_operation
                        trigger_backup_after_critical_operation("actualizar información empresa")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
    
    with info_tabs[1]:
        # Tu código existente de logo aquí...
        st.markdown("#### Logo de la Empresa")
        
        logo_base64 = get_company_logo_base64(empresa_id)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if logo_base64:
                st.markdown("**Logo Actual:**")
                st.markdown(
                    f'<img src="data:image/jpeg;base64,{logo_base64}" style="max-width:200px;border-radius:10px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">',
                    unsafe_allow_html=True
                )
                
                if st.button("🗑️ Eliminar Logo", type="secondary"):
                    success, message = delete_company_logo(empresa_id)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            else:
                st.info("No hay logo configurado")
        
        with col2:
            st.markdown("**Subir Nuevo Logo:**")
            
            uploaded_file = st.file_uploader(
                "Seleccionar archivo de imagen",
                type=['png', 'jpg', 'jpeg'],
                help="Formatos soportados: PNG, JPG, JPEG"
            )
            
            if uploaded_file is not None:
                st.markdown("**Preview:**")
                st.image(uploaded_file, width=150)
                
                if st.button("💾 Guardar Logo", type="primary"):
                    success, result = save_company_logo(empresa_id, uploaded_file)
                    
                    if success:
                        update_company_info_complete(empresa_id, {'logo_filename': result})
                        st.success("✅ Logo guardado correctamente")
                        # Trigger backup después de subir logo
                        from db_utils import trigger_backup_after_critical_operation
                        trigger_backup_after_critical_operation("actualizar logo empresa")
                        st.rerun()
                    else:
                        st.error(f"❌ {result}")

def mostrar_respaldo(empresa_id, empresa_nombre):
    """Pestaña de respaldo actualizada con sistema mejorado"""
    st.subheader("Respaldo y Restauración")
    
    # Información del sistema
    st.info("Sistema de respaldos mejorado - Incluye todos los módulos y datos")
    
    tabs = st.tabs(["Crear Respaldo", "Restaurar", "Validar", "Información"])
    
    with tabs[0]:
        mostrar_crear_respaldo(empresa_id, empresa_nombre)
    
    with tabs[1]:
        mostrar_restaurar_respaldo()
    
    with tabs[2]:
        mostrar_validar_respaldo()
    
    with tabs[3]:
        mostrar_info_respaldos()

def mostrar_config_avanzadas(empresa_id, empresa_nombre):
    st.subheader("Opciones Avanzadas")
    st.warning("⚠️ Las siguientes acciones son irreversibles")
    
    # Reiniciar información del sistema
    st.markdown('<div class="danger-section">', unsafe_allow_html=True)
    st.subheader("🔄 Reiniciar Sistema")
    st.error("⚠️ **PELIGRO:** Esta opción eliminará TODA la información del sistema")
    st.write("- Se eliminarán todas las empresas y sus datos")
    st.write("- Se eliminarán todas las máquinas y registros")
    st.write("- Se mantendrá la estructura de la base de datos")
    st.write("- Se conservará el usuario admin")
    
    if st.button("🔧 Mostrar opciones de reinicio", type="secondary"):
        st.session_state.show_reset_options = not st.session_state.get('show_reset_options', False)
        st.rerun()
    
    if st.session_state.get('show_reset_options', False):
        if st.session_state.get('reset_system_step', 0) == 0:
            if st.button("🗑️ Reiniciar toda la información del sistema", type="primary"):
                st.session_state.reset_system_step = 1
                st.rerun()
                
        elif st.session_state.reset_system_step == 1:
            st.error("⚠️ **ESTA ACCIÓN ELIMINARÁ TODA LA INFORMACIÓN DEL SISTEMA**")
            st.error("⚠️ **ESTA ACCIÓN NO SE PUEDE DESHACER**")
            st.write("Para confirmar, escriba 'REINICIAR SISTEMA' exactamente:")
            
            confirm_text = st.text_input("Confirmación:")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔥 CONFIRMAR REINICIO"):
                    if confirm_text == "REINICIAR SISTEMA":
                        try:
                            resultado = reiniciar_sistema_completo()
                            if resultado:
                                st.success("Sistema reiniciado correctamente")
                                st.info("Regresando a la página principal...")
                                # Limpiar estado y redirigir
                                for key in list(st.session_state.keys()):
                                    if key not in ['logged_in', 'username']:
                                        del st.session_state[key]
                                st.rerun()
                            else:
                                st.error("Error al reiniciar el sistema")
                        except Exception as e:
                            st.error(f"Error inesperado: {str(e)}")
                    else:
                        st.error("Texto de confirmación incorrecto")
            
            with col2:
                if st.button("❌ Cancelar"):
                    st.session_state.reset_system_step = 0
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Eliminar empresa actual
    st.markdown('<div class="danger-section">', unsafe_allow_html=True)
    st.subheader("🗑️ Eliminar Esta Empresa")
    st.error("⚠️ Esta opción eliminará únicamente esta empresa y todos sus datos asociados")
    
    if st.button("Mostrar opciones de eliminación de empresa", type="secondary"):
        st.session_state.show_delete_options = not st.session_state.get('show_delete_options', False)
        st.rerun()
    
    if st.session_state.get('show_delete_options', False):
        # Proceso de eliminación de empresa
        if st.session_state.get('delete_company_step', 0) == 0:
            if st.button("🗑️ Eliminar esta empresa y todos sus datos", type="primary"):
                st.session_state.delete_company_step = 1
                st.rerun()
                
        elif st.session_state.delete_company_step == 1:
            st.error("⚠️ ESTA ACCIÓN ELIMINARÁ LA EMPRESA Y TODOS SUS DATOS ASOCIADOS")
            st.error("⚠️ ESTA ACCIÓN NO SE PUEDE DESHACER")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Sí, continuar con la eliminación"):
                    st.session_state.delete_company_step = 2
                    st.rerun()
            with col2:
                if st.button("❌ Cancelar"):
                    st.session_state.delete_company_step = 0
                    st.rerun()
        
        elif st.session_state.delete_company_step == 2:
            st.error(f"Para confirmar, escriba el nombre exacto de la empresa: **{empresa_nombre}**")
            
            confirm_text = st.text_input("Nombre de la empresa:")
            
            if st.button("🔥 ELIMINAR DEFINITIVAMENTE"):
                if confirm_text == empresa_nombre:
                    try:
                        delete_result = eliminar_empresa(empresa_id)
                        if delete_result:
                            st.success("Empresa y datos asociados eliminados correctamente")
                            
                            # Limpiar estado y volver al inicio
                            for key in list(st.session_state.keys()):
                                if key not in ['logged_in', 'username']:
                                    del st.session_state[key]
                            st.rerun()
                        else:
                            st.error("Error al eliminar la empresa")
                    except Exception as e:
                        st.error(f"Error inesperado: {str(e)}")
                else:
                    st.error("El nombre de la empresa no coincide")
            
            if st.button("🔙 Volver atrás"):
                st.session_state.delete_company_step = 1
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# Funciones auxiliares para el nuevo sistema

def add_machinery_extended(empresa_id, name, model, serial_number, identifier, classification, 
                         consumption_per_hour, purchase_date, status, current_hours, current_odometer):
    """Versión extendida de add_machinery para incluir nuevos campos"""
    
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO machinery (
                company_id, name, model, serial_number, identifier, 
                classification, consumption_per_hour, purchase_date, status,
                current_hours, current_odometer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (empresa_id, name, model, serial_number, identifier, classification, 
              consumption_per_hour, purchase_date, status, current_hours, current_odometer))
        conn.commit()
    return True

def get_critical_control_alerts(empresa_id):
    """Función placeholder para obtener alertas críticas del módulo de controles"""
    # Esta función será implementada en el módulo de controles
    return []

def eliminar_empresa(empresa_id):
    """Elimina una empresa y todos sus datos asociados"""
    try:
        with get_conn() as conn:
            # Obtener todas las máquinas de la empresa
            machines = conn.execute("SELECT id FROM machinery WHERE company_id = ?", (empresa_id,)).fetchall()
            
            # Eliminar registros relacionados de cada máquina
            for machine in machines:
                machine_id = machine[0]
                # Eliminar logs de combustible
                conn.execute("DELETE FROM fuel_logs WHERE machine_id = ?", (machine_id,))
                # Eliminar registros de mantenimiento si existen
                conn.execute("DELETE FROM maintenance_records WHERE machine_id = ?", (machine_id,))
                # Eliminar controles si existen
                conn.execute("DELETE FROM control_records WHERE machine_id = ?", (machine_id,))
            
            # Eliminar las máquinas
            conn.execute("DELETE FROM machinery WHERE company_id = ?", (empresa_id,))
            
            # Finalmente eliminar la empresa
            conn.execute("DELETE FROM companies WHERE id = ?", (empresa_id,))
            
            conn.commit()
        return True
    except Exception as e:
        print(f"Error al eliminar empresa: {e}")
        return False

def crear_respaldo_completo():
    """Crea un respaldo completo de la base de datos en formato JSON"""
    try:
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'version': '1.0',
            'system': 'SANDI',
            'companies': [],
            'machinery': [],
            'fuel_logs': [],
            'maintenance_records': [],
            'control_records': [],
            'machine_classifications': []
        }
        
        with get_conn() as conn:
            # Exportar empresas
            companies = conn.execute("SELECT * FROM companies").fetchall()
            company_columns = [desc[0] for desc in conn.execute("PRAGMA table_info(companies)").fetchall()]
            backup_data['companies'] = [dict(zip(company_columns, company)) for company in companies]
            
            # Exportar máquinas
            machinery = conn.execute("SELECT * FROM machinery").fetchall()
            machinery_columns = [desc[0] for desc in conn.execute("PRAGMA table_info(machinery)").fetchall()]
            backup_data['machinery'] = [dict(zip(machinery_columns, machine)) for machine in machinery]
            
            # Exportar logs de combustible
            fuel_logs = conn.execute("SELECT * FROM fuel_logs").fetchall()
            fuel_columns = [desc[0] for desc in conn.execute("PRAGMA table_info(fuel_logs)").fetchall()]
            backup_data['fuel_logs'] = [dict(zip(fuel_columns, log)) for log in fuel_logs]
            
            # Exportar clasificaciones de máquinas
            try:
                classifications = conn.execute("SELECT * FROM machine_classifications").fetchall()
                class_columns = [desc[0] for desc in conn.execute("PRAGMA table_info(machine_classifications)").fetchall()]
                backup_data['machine_classifications'] = [dict(zip(class_columns, cls)) for cls in classifications]
            except:
                pass  # Tabla no existe
            
            # Exportar mantenimiento si existe
            try:
                maintenance = conn.execute("SELECT * FROM maintenance_records").fetchall()
                maint_columns = [desc[0] for desc in conn.execute("PRAGMA table_info(maintenance_records)").fetchall()]
                backup_data['maintenance_records'] = [dict(zip(maint_columns, record)) for record in maintenance]
            except:
                pass  # Tabla no existe
            
            # Exportar controles si existe
            try:
                controls = conn.execute("SELECT * FROM control_records").fetchall()
                control_columns = [desc[0] for desc in conn.execute("PRAGMA table_info(control_records)").fetchall()]
                backup_data['control_records'] = [dict(zip(control_columns, record)) for record in controls]
            except:
                pass  # Tabla no existe
        
        return json.dumps(backup_data, indent=2, ensure_ascii=False)
        
    except Exception as e:
        raise Exception(f"Error al crear respaldo: {str(e)}")

def restaurar_desde_respaldo(backup_data, backup_type='completo', target_empresa_id=None):
    """Restaura la base de datos desde un archivo de respaldo"""
    try:
        with get_conn() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            
            if backup_type == 'completo':
                # Limpiar todas las tablas (excepto preservar estructura)
                tables_to_clear = [
                    'control_records', 'maintenance_records', 'fuel_logs', 
                    'machinery', 'companies', 'machine_classifications'
                ]
                
                for table in tables_to_clear:
                    try:
                        conn.execute(f"DELETE FROM {table}")
                    except sqlite3.OperationalError:
                        pass  # Tabla no existe
                
                # Restaurar clasificaciones de máquinas
                if 'machine_classifications' in backup_data:
                    for classification in backup_data['machine_classifications']:
                        try:
                            conn.execute(
                                "INSERT INTO machine_classifications (id, name) VALUES (?, ?)",
                                (classification.get('id'), classification.get('name'))
                            )
                        except:
                            pass
                
                # Restaurar empresas
                for company in backup_data.get('companies', []):
                    try:
                        conn.execute(
                            "INSERT INTO companies (id, name, created_at) VALUES (?, ?, ?)",
                            (company.get('id'), company.get('name'), company.get('created_at'))
                        )
                    except Exception as e:
                        print(f"Error restaurando empresa: {e}")
                
                # Restaurar máquinas
                for machine in backup_data.get('machinery', []):
                    try:
                        conn.execute("""
                            INSERT INTO machinery (
                                id, company_id, name, model, serial_number, identifier,
                                classification, consumption_per_hour, purchase_date, status,
                                current_hours, current_odometer, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            machine.get('id'), machine.get('company_id'), machine.get('name'),
                            machine.get('model'), machine.get('serial_number'), machine.get('identifier'),
                            machine.get('classification'), machine.get('consumption_per_hour'),
                            machine.get('purchase_date'), machine.get('status'),
                            machine.get('current_hours'), machine.get('current_odometer'),
                            machine.get('created_at')
                        ))
                    except Exception as e:
                        print(f"Error restaurando máquina: {e}")
                
                # Restaurar logs de combustible
                for fuel_log in backup_data.get('fuel_logs', []):
                    try:
                        conn.execute("""
                            INSERT INTO fuel_logs (
                                id, machine_id, date, fuel_added, hours_worked,
                                odometer_reading, notes, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            fuel_log.get('id'), fuel_log.get('machine_id'), fuel_log.get('date'),
                            fuel_log.get('fuel_added'), fuel_log.get('hours_worked'),
                            fuel_log.get('odometer_reading'), fuel_log.get('notes'),
                            fuel_log.get('created_at')
                        ))
                    except Exception as e:
                        print(f"Error restaurando log de combustible: {e}")
                
                # Restaurar mantenimiento
                for maintenance in backup_data.get('maintenance_records', []):
                    try:
                        conn.execute("""
                            INSERT INTO maintenance_records (
                                id, machine_id, maintenance_type, date_performed, next_due_date,
                                cost, notes, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            maintenance.get('id'), maintenance.get('machine_id'),
                            maintenance.get('maintenance_type'), maintenance.get('date_performed'),
                            maintenance.get('next_due_date'), maintenance.get('cost'),
                            maintenance.get('notes'), maintenance.get('created_at')
                        ))
                    except Exception as e:
                        print(f"Error restaurando mantenimiento: {e}")
                
                # Restaurar controles
                for control in backup_data.get('control_records', []):
                    try:
                        conn.execute("""
                            INSERT INTO control_records (
                                id, machine_id, control_type, date_performed, hours_reading,
                                odometer_reading, result, notes, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            control.get('id'), control.get('machine_id'), control.get('control_type'),
                            control.get('date_performed'), control.get('hours_reading'),
                            control.get('odometer_reading'), control.get('result'),
                            control.get('notes'), control.get('created_at')
                        ))
                    except Exception as e:
                        print(f"Error restaurando control: {e}")
            
            elif backup_type == 'empresa_especifica':
                # =========== RESTAURACIÓN DE EMPRESA ESPECÍFICA ===========
                print("Realizando restauración de empresa específica...")
                
                # Obtener datos de la empresa del respaldo
                empresa_data = backup_data['empresa']['company_info']
                original_name = empresa_data['name']
                
                if target_empresa_id is None:
                    # Crear nueva empresa con nombre único
                    unique_name = get_unique_company_name(original_name)
                    
                    success = add_company(unique_name)
                    if not success:
                        raise Exception("Error creando empresa")
                    
                    # Obtener ID de nueva empresa
                    empresas = list_companies()
                    nueva_empresa = empresas[empresas['name'] == unique_name]
                    if nueva_empresa.empty:
                        raise Exception("Error obteniendo ID de nueva empresa")
                    target_empresa_id = nueva_empresa.iloc[0]['id']
                    
                    print(f"Empresa creada con nombre: {unique_name}")
                else:
                    unique_name = original_name
                
                # Actualizar información completa de la empresa
                company_info = empresa_data.copy()
                company_info['name'] = unique_name
                
                success, message = update_company_info_complete(target_empresa_id, company_info)
                if not success:
                    print(f"Advertencia: No se pudo actualizar info completa: {message}")
                else:
                    print("Información completa de empresa actualizada")
                
                # Eliminar maquinaria existente de la empresa
                conn.execute("DELETE FROM machinery WHERE company_id = ?", (target_empresa_id,))
                
                # Restaurar máquinas de la empresa específica
                machine_id_mapping = {}  # Mapeo de IDs antiguos a nuevos
                
                for machine in backup_data['empresa'].get('machinery', []):
                    try:
                        old_id = machine.get('id')
                        cursor = conn.execute("""
                            INSERT INTO machinery (
                                company_id, name, model, serial_number, identifier,
                                classification, consumption_per_hour, purchase_date, status,
                                current_hours, current_odometer, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            target_empresa_id, machine.get('name'),
                            machine.get('model'), machine.get('serial_number'), machine.get('identifier'),
                            machine.get('classification'), machine.get('consumption_per_hour'),
                            machine.get('purchase_date'), machine.get('status'),
                            machine.get('current_hours'), machine.get('current_odometer'),
                            machine.get('created_at')
                        ))
                        new_id = cursor.lastrowid
                        machine_id_mapping[old_id] = new_id
                    except Exception as e:
                        print(f"Error restaurando máquina: {e}")
                
                # Restaurar logs de combustible
                for fuel_log in backup_data['empresa'].get('fuel_logs', []):
                    try:
                        old_machine_id = fuel_log.get('machine_id')
                        new_machine_id = machine_id_mapping.get(old_machine_id)
                        
                        if new_machine_id:
                            conn.execute("""
                                INSERT INTO fuel_logs (
                                    machine_id, date, fuel_added, hours_worked,
                                    odometer_reading, notes, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                new_machine_id, fuel_log.get('date'),
                                fuel_log.get('fuel_added'), fuel_log.get('hours_worked'),
                                fuel_log.get('odometer_reading'), fuel_log.get('notes'),
                                fuel_log.get('created_at')
                            ))
                    except Exception as e:
                        print(f"Error restaurando log de combustible: {e}")
                
                # Restaurar mantenimiento
                for maintenance in backup_data['empresa'].get('maintenance_records', []):
                    try:
                        old_machine_id = maintenance.get('machine_id')
                        new_machine_id = machine_id_mapping.get(old_machine_id)
                        
                        if new_machine_id:
                            conn.execute("""
                                INSERT INTO maintenance_records (
                                    machine_id, maintenance_type, date_performed, next_due_date,
                                    cost, notes, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                new_machine_id,
                                maintenance.get('maintenance_type'), maintenance.get('date_performed'),
                                maintenance.get('next_due_date'), maintenance.get('cost'),
                                maintenance.get('notes'), maintenance.get('created_at')
                            ))
                    except Exception as e:
                        print(f"Error restaurando mantenimiento: {e}")
                
                # Restaurar controles
                for control in backup_data['empresa'].get('control_records', []):
                    try:
                        old_machine_id = control.get('machine_id')
                        new_machine_id = machine_id_mapping.get(old_machine_id)
                        
                        if new_machine_id:
                            conn.execute("""
                                INSERT INTO control_records (
                                    machine_id, control_type, date_performed, hours_reading,
                                    odometer_reading, result, notes, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                new_machine_id, control.get('control_type'),
                                control.get('date_performed'), control.get('hours_reading'),
                                control.get('odometer_reading'), control.get('result'),
                                control.get('notes'), control.get('created_at')
                            ))
                    except Exception as e:
                        print(f"Error restaurando control: {e}")
            
            # Reactivar foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()
        
        return True
        
    except Exception as e:
        print(f"Error en restauración: {e}")
        return False

def reiniciar_sistema_completo():
    """Reinicia completamente el sistema eliminando todos los datos pero manteniendo la estructura"""
    try:
        with get_conn() as conn:
            # Deshabilitar foreign keys temporalmente
            conn.execute("PRAGMA foreign_keys = OFF")
            
            # Limpiar todas las tablas de datos
            tables_to_clear = [
                'control_records',
                'maintenance_records', 
                'fuel_logs',
                'machinery',
                'companies'
            ]
            
            for table in tables_to_clear:
                try:
                    conn.execute(f"DELETE FROM {table}")
                    # Reiniciar autoincrement
                    conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
                except sqlite3.OperationalError:
                    pass  # Tabla no existe
            
            # Mantener algunas clasificaciones básicas
            try:
                conn.execute("DELETE FROM machine_classifications")
                conn.execute("DELETE FROM sqlite_sequence WHERE name='machine_classifications'")
                
                # Insertar clasificaciones básicas
                basic_classifications = [
                    'Excavadora', 'Bulldozer', 'Camión', 'Grúa', 
                    'Compactadora', 'Cargador', 'Motoniveladora', 'Otros'
                ]
                
                for classification in basic_classifications:
                    conn.execute(
                        "INSERT INTO machine_classifications (name) VALUES (?)", 
                        (classification,)
                    )
            except:
                pass
            
            # Reactivar foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()
        
        return True
        
    except Exception as e:
        print(f"Error al reiniciar sistema: {e}")
        return False

def get_empresa_nombre(empresa_id):
    """Obtiene el nombre de la empresa por ID"""
    try:
        empresas = list_companies()
        empresa = empresas[empresas['id'] == empresa_id]
        if not empresa.empty:
            return empresa.iloc[0]['name']
        return f"Empresa {empresa_id}"
    except:
        return f"Empresa {empresa_id}"

def mostrar_estadisticas_basicas_mejoradas(empresa_id):
    """Versión mejorada de estadísticas básicas con mejor UX"""
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 15px; color: white; margin-bottom: 20px;">
        <h1>📊 Estadísticas del Sistema</h1>
        <p>Análisis básico de maquinaria y operaciones</p>
        <div style="background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px; margin-top: 10px;">
            <small>💡 Para análisis avanzado, instale las dependencias: pip install plotly scipy scikit-learn</small>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    maquinarias = list_machinery(empresa_id)
    if maquinarias.empty:
        st.info("No hay máquinas registradas para generar estadísticas.")
        return
    
    # Métricas principales mejoradas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Máquinas", len(maquinarias))
    
    with col2:
        activas = len(maquinarias[maquinarias['status'] == 'Active'])
        st.metric("Máquinas Activas", activas)
    
    with col3:
        en_mantenimiento = len(maquinarias[maquinarias['status'] == 'Maintenance'])
        st.metric("En Mantenimiento", en_mantenimiento)
    
    with col4:
        try:
            critical_machines = get_critical_fuel_machines(empresa_id)
            critical_count = len([m for m in critical_machines if m['status'] == 'critical'])
            st.metric("Combustible Crítico", critical_count)
        except:
            st.metric("Combustible Crítico", "N/A")
    
    # Gráficos básicos mejorados
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distribución por Estado")
        if not maquinarias.empty:
            status_counts = maquinarias['status'].value_counts()
            fig_status = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="Estados de Máquinas",
                color_discrete_map={
                    'Active': '#28a745',
                    'Maintenance': '#ffc107', 
                    'Inactive': '#dc3545'
                }
            )
            st.plotly_chart(fig_status, use_container_width=True)
    
    with col2:
        st.subheader("Distribución por Clasificación")
        if 'classification' in maquinarias.columns:
            class_counts = maquinarias['classification'].value_counts()
            if not class_counts.empty:
                fig_class = px.bar(
                    x=class_counts.index,
                    y=class_counts.values,
                    title="Máquinas por Tipo",
                    labels={'x': 'Clasificación', 'y': 'Cantidad'}
                )
                fig_class.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_class, use_container_width=True)
    
    # Tabla de máquinas mejorada
    st.subheader("📋 Listado de Máquinas")
    
    display_data = maquinarias[['name', 'classification', 'status', 'identifier']].copy()
    display_data.columns = ['Nombre', 'Clasificación', 'Estado', 'Matrícula']
    
    # Agregar indicadores visuales
    display_data['Estado'] = display_data['Estado'].apply(lambda x: f"🟢 {x}" if x == 'Active' 
                                                         else f"🟡 {x}" if x == 'Maintenance' 
                                                         else f"🔴 {x}")
    
    st.dataframe(display_data, use_container_width=True)
    
    # Información sobre upgrade
    mostrar_info_upgrade_estadisticas()

def mostrar_estadisticas_basicas_fallback(empresa_id):
    """Fallback cuando el módulo avanzado falla"""
    
    st.warning("Error en módulo avanzado - Usando versión básica")
    mostrar_estadisticas_basicas_mejoradas(empresa_id)

def mostrar_info_upgrade_estadisticas():
    """Muestra información sobre cómo acceder a estadísticas avanzadas"""
    
    with st.expander("🚀 Actualizar a Estadísticas Avanzadas", expanded=False):
        st.markdown("""
        ### ¿Qué incluyen las Estadísticas Avanzadas?
        
        **📈 Análisis Predictivo:**
        - Predicción de mantenimientos con Machine Learning
        - Forecasting de consumo de combustible
        - Análisis de tendencias y correlaciones
        
        **💰 Análisis Financiero:**
        - ROI detallado por máquina
        - Análisis de costo total de propiedad (TCO)
        - Proyecciones de rentabilidad
        
        **⚡ Eficiencia Operacional:**
        - Rankings de performance
        - Análisis de productividad por operador
        - Recomendaciones de optimización
        
        **⛽ Consumo Inteligente:**
        - Patrones estacionales
        - Optimización de inventarios
        - Alertas predictivas
        
        ### 🛠️ Instalación
        ```bash
        pip install plotly scipy scikit-learn numpy
        ```
        
        Luego reinicie la aplicación para activar las funciones avanzadas.
        """)

def mostrar_extras_tab(empresa_id, empresa_nombre):
    """Muestra el contenido de la pestaña EXTRAS"""
    try:
        # Intentar importar el módulo EXTRAS
        from extras_module import mostrar_extras
        mostrar_extras(empresa_id)
        
    except ImportError:
        # Si no está disponible, mostrar mensaje de instalación
        st.markdown("""
        <div style="background: linear-gradient(135deg, #ff6b6b 0%, #4ecdc4 100%); 
                    padding: 20px; border-radius: 15px; color: white; margin-bottom: 20px;">
            <h1>🚀 EXTRAS - Funcionalidades Alpha</h1>
            <p>Módulos experimentales y nuevas implementaciones</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.error("❌ Módulo EXTRAS no está disponible")
        
        with st.expander("📦 Instrucciones de Instalación"):
            st.markdown("""
            ### Para activar el módulo EXTRAS:
            
            1. **Crear el archivo `extras_module.py`** en el directorio principal
            2. **Crear el archivo `extras_costos_especificos.py`** en el directorio principal
            3. **Reiniciar la aplicación**
            
            ### Módulos EXTRAS disponibles:
            - **Costos Específicos**: Detalla gastos específicos de mantenimientos
            - Más módulos en desarrollo...
            
            ### Características del sistema EXTRAS:
            - 🔧 Funcionalidades experimentales
            - 📊 Análisis avanzados de costos
            - 🚀 Nuevas implementaciones sin afectar módulos existentes
            - 🔄 Sistema modular independiente
            """)
        
        # Mostrar información de desarrollo
        st.info("Los módulos EXTRAS están diseñados para ser independientes y no afectar la funcionalidad principal del sistema.")
        
    except Exception as e:
        st.error(f"Error cargando módulo EXTRAS: {str(e)}")
        st.info("Verifica que los archivos extras_module.py y extras_costos_especificos.py estén correctamente configurados.")

def verificar_modulo_extras():
    """Verifica si el módulo EXTRAS está disponible"""
    try:
        import extras_module
        import extras_costos_especificos
        return True
    except ImportError:
        return False

def mostrar_estado_extras():
    """Muestra el estado del módulo EXTRAS en el dashboard"""
    if verificar_modulo_extras():
        st.success("🚀 Módulo EXTRAS: Activo")
    else:
        st.warning("🚀 Módulo EXTRAS: No disponible")

def get_extras_alerts_for_dashboard(empresa_id):
    """Obtiene alertas del módulo EXTRAS para mostrar en dashboard principal"""
    try:
        if not verificar_modulo_extras():
            return []
        
        from db_utils import get_extras_dashboard_summary, get_maintenance_records
        
        alerts = []
        
        # Verificar si hay mantenimientos sin detallar
        extras_summary = get_extras_dashboard_summary(empresa_id)
        if 'error' not in extras_summary:
            if extras_summary.get('total_detailed_maintenances', 0) == 0:
                recent_maintenances = get_maintenance_records(empresa_id, limit=10)
                if not recent_maintenances.empty:
                    maintenance_count = len(recent_maintenances)
                    alerts.append({
                        'type': 'COSTOS_SIN_DETALLAR',
                        'level': 'warning',
                        'message': f"Tienes {maintenance_count} mantenimientos sin detalles de costo",
                        'action': "Ve a EXTRAS > Costos Específicos"
                    })
        
        return alerts
        
    except Exception as e:
        return []
    
def mostrar_config_extras(empresa_id, empresa_nombre):
    """Configuración del módulo EXTRAS"""
    
    st.subheader("Configuración del Módulo EXTRAS")
    
    # Verificar estado del módulo
    extras_disponible = verificar_modulo_extras()
    
    if extras_disponible:
        st.success("✅ Módulo EXTRAS activado correctamente")
        
        # Mostrar información del módulo
        try:
            from db_utils import get_extras_dashboard_summary
            summary = get_extras_dashboard_summary(empresa_id)
            
            if 'error' not in summary:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Mantenimientos Detallados", summary.get('total_detailed_maintenances', 0))
                
                with col2:
                    st.metric("Categorías Usadas", summary.get('total_cost_categories_used', 0))
                
                with col3:
                    total_amount = summary.get('total_detailed_amount', 0)
                    st.metric("Total Detallado", f"${total_amount:.2f}")
        except Exception as e:
            st.warning(f"Error obteniendo resumen EXTRAS: {str(e)}")
        
        # Gestión de categorías de costos
        st.subheader("Gestión de Categorías de Costos")
        
        try:
            from db_utils import get_extras_cost_categories, add_extras_cost_category
            
            categories = get_extras_cost_categories()
            
            if not categories.empty:
                st.write("**Categorías activas:**")
                for _, cat in categories.iterrows():
                    st.write(f"• {cat['category_name']} - {cat.get('description', 'Sin descripción')}")
            
            # Agregar nueva categoría
            with st.expander("Agregar Nueva Categoría"):
                new_cat_name = st.text_input("Nombre de la categoría:")
                new_cat_desc = st.text_area("Descripción:")
                
                if st.button("Agregar Categoría"):
                    if new_cat_name.strip():
                        success = add_extras_cost_category(new_cat_name.strip(), new_cat_desc.strip())
                        if success:
                            st.success("Categoría agregada correctamente")
                            st.rerun()
                        else:
                            st.error("Error agregando categoría (puede que ya exista)")
                    else:
                        st.error("El nombre es obligatorio")
        
        except Exception as e:
            st.error(f"Error gestionando categorías: {str(e)}")
        
        # Validación y limpieza
        st.subheader("Mantenimiento del Sistema EXTRAS")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔍 Validar Integridad"):
                try:
                    from db_utils import validate_maintenance_cost_integrity
                    validation = validate_maintenance_cost_integrity(empresa_id)
                    
                    if validation['is_valid']:
                        st.success("✅ Todos los datos están íntegros")
                    else:
                        st.warning("⚠️ Se encontraron inconsistencias:")
                        for issue in validation['issues']:
                            st.write(f"• {issue}")
                except Exception as e:
                    st.error(f"Error en validación: {str(e)}")
        
        with col2:
            if st.button("🧹 Limpiar Datos"):
                try:
                    from db_utils import cleanup_maintenance_cost_data
                    cleanup_result = cleanup_maintenance_cost_data(empresa_id)
                    
                    if 'error' not in cleanup_result:
                        st.success("Limpieza completada:")
                        st.write(f"• Detalles huérfanos eliminados: {cleanup_result.get('orphaned_details_removed', 0)}")
                        st.write(f"• Detalles con categorías inactivas: {cleanup_result.get('inactive_category_details_removed', 0)}")
                    else:
                        st.error(f"Error en limpieza: {cleanup_result['error']}")
                except Exception as e:
                    st.error(f"Error en limpieza: {str(e)}")
        
        # Exportar/Importar configuración
        st.subheader("Respaldo de Datos EXTRAS")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Exportar Datos EXTRAS"):
                try:
                    from db_utils import backup_extras_data
                    backup_data = backup_extras_data(empresa_id)
                    
                    if 'error' not in backup_data:
                        import json
                        backup_json = json.dumps(backup_data, indent=2, ensure_ascii=False)
                        
                        st.download_button(
                            label="💾 Descargar Respaldo EXTRAS",
                            data=backup_json,
                            file_name=f"EXTRAS_Backup_{empresa_nombre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                        st.success("Respaldo generado correctamente")
                    else:
                        st.error(f"Error generando respaldo: {backup_data['error']}")
                except Exception as e:
                    st.error(f"Error en respaldo: {str(e)}")
    
    else:
        # Módulo no disponible - Mostrar instrucciones
        st.error("❌ Módulo EXTRAS no está disponible")
        
        with st.expander("📦 Instrucciones de Instalación", expanded=True):
            st.markdown("""
            ### Para activar el módulo EXTRAS:
            
            1. **Crear `extras_module.py`** en el directorio principal
            2. **Crear `extras_costos_especificos.py`** en el directorio principal  
            3. **Reiniciar la aplicación**
            
            ### Archivos necesarios:
            - `extras_module.py` - Módulo principal de EXTRAS
            - `extras_costos_especificos.py` - Submódulo de costos específicos
            
            ### Funcionalidades incluidas:
            - 💰 Detalles específicos de costos de mantenimiento
            - 📊 Análisis avanzado de gastos por categoría
            - 🏷️ Gestión de categorías de costos
            - 📈 Reportes detallados de costos
            """)
        
        # Verificar dependencias en db_utils
        st.subheader("Estado de Dependencias")
        
        try:
            from db_utils import init_extras_tables
            if st.button("🔧 Inicializar Tablas EXTRAS"):
                success = init_extras_tables()
                if success:
                    st.success("✅ Tablas EXTRAS inicializadas en la base de datos")
                else:
                    st.error("❌ Error inicializando tablas EXTRAS")
        except ImportError:
            st.error("❌ Funciones EXTRAS no disponibles en db_utils.py")
            st.info("Agrega las extensiones necesarias a db_utils.py")

def mostrar_crear_respaldo(empresa_id, empresa_nombre):
    """Interface para crear respaldos"""
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### Respaldo Completo del Sistema")
        st.markdown("""
        **Incluye:**
        - Todas las empresas y su información
        - Toda la maquinaria y datos
        - Módulo de combustible/fluidos
        - Módulo de mantenimiento
        - Módulo de controles
        - Módulo EXTRAS (costos específicos)
        - Logos y archivos adjuntos
        - Configuraciones del sistema
        """)
        
        include_assets_sistema = st.checkbox(
            "Incluir logos y archivos", 
            value=True,
            help="Incluye logos de empresas y otros archivos"
        )
        
        respaldo_description_sistema = st.text_input(
            "Descripción del respaldo (opcional)", 
            placeholder="Ej: Respaldo antes de actualización..."
        )
        
        if st.button("Crear Respaldo Completo", type="primary", use_container_width=True):
            with st.spinner("Creando respaldo completo del sistema..."):
                try:
                    # Importar funciones del nuevo sistema
                    from db_utils import crear_respaldo_completo
                    
                    backup_data = crear_respaldo_completo(include_assets=include_assets_sistema)
                    
                    # Agregar descripción si se proporcionó
                    if respaldo_description_sistema:
                        backup_dict = json.loads(backup_data)
                        backup_dict['backup_info']['user_description'] = respaldo_description_sistema
                        backup_data = json.dumps(backup_dict, indent=2, ensure_ascii=False)
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"SANDI_Sistema_Completo_{timestamp}.json"
                    
                    st.download_button(
                        label="Descargar Respaldo del Sistema",
                        data=backup_data,
                        file_name=filename,
                        mime="application/json",
                        help="Guarda este archivo en un lugar seguro"
                    )
                    st.success("Respaldo del sistema creado correctamente!")
                    
                    # Mostrar estadísticas
                    backup_dict = json.loads(backup_data)
                    stats = backup_dict.get('backup_info', {}).get('statistics', {})
                    if stats:
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Empresas", stats.get('total_companies', 0))
                        with col_b:
                            st.metric("Máquinas", stats.get('total_machines', 0))
                        with col_c:
                            st.metric("Tablas", stats.get('tables_backed_up', 0))
                    
                except Exception as e:
                    st.error(f"Error al crear respaldo: {str(e)}")
    
    with col2:
        st.markdown("### Respaldo de Esta Empresa")
        st.markdown(f"""
        **Respaldo específico de: {empresa_nombre}**
        
        **Incluye:**
        - Información de la empresa
        - Todas las máquinas
        - Registros de combustible
        - Mantenimientos realizados
        - Detalles de costos (EXTRAS)
        - Configuraciones específicas
        - Logo de la empresa
        """)
        
        include_assets_empresa = st.checkbox(
            "Incluir logo de empresa", 
            value=True,
            key="empresa_assets",
            help="Incluye el logo específico de esta empresa"
        )
        
        respaldo_description_empresa = st.text_input(
            "Descripción (opcional)", 
            placeholder="Ej: Antes de cambios importantes...",
            key="empresa_desc"
        )
        
        if st.button("Crear Respaldo de Empresa", type="secondary", use_container_width=True):
            with st.spinner(f"Creando respaldo de {empresa_nombre}..."):
                try:
                    from db_utils import crear_respaldo_empresa
                    
                    backup_data = crear_respaldo_empresa(
                        empresa_id, 
                        include_assets=include_assets_empresa
                    )
                    
                    # Agregar descripción si se proporcionó
                    if respaldo_description_empresa:
                        backup_dict = json.loads(backup_data)
                        backup_dict['backup_info']['user_description'] = respaldo_description_empresa
                        backup_data = json.dumps(backup_dict, indent=2, ensure_ascii=False)
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"SANDI_Empresa_{empresa_nombre}_{timestamp}.json"
                    
                    st.download_button(
                        label="Descargar Respaldo de Empresa",
                        data=backup_data,
                        file_name=filename,
                        mime="application/json",
                        help="Respaldo específico de esta empresa"
                    )
                    st.success(f"Respaldo de {empresa_nombre} creado correctamente!")
                    
                    # Mostrar estadísticas
                    backup_dict = json.loads(backup_data)
                    stats = backup_dict.get('backup_info', {}).get('statistics', {})
                    if stats:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.metric("Máquinas", stats.get('total_machines', 0))
                        with col_b:
                            st.metric("Mantenimientos", stats.get('total_maintenances', 0))
                    
                except Exception as e:
                    st.error(f"Error al crear respaldo de empresa: {str(e)}")

def mostrar_restaurar_respaldo():
    """Interface para restaurar respaldos"""
    
    st.markdown("### Restaurar desde Respaldo")
    st.warning("La restauración reemplazará los datos actuales según el tipo de respaldo")
    
    uploaded_file = st.file_uploader(
        "Seleccionar archivo de respaldo", 
        type=['json'],
        help="Selecciona un archivo .json creado por el sistema de respaldos"
    )
    
    if uploaded_file is not None:
        try:
            # Leer y validar el archivo
            backup_content = json.loads(uploaded_file.read())
            
            # Validar respaldo
            from db_utils import validar_respaldo_antes_restaurar, get_backup_info_summary
            
            validation = validar_respaldo_antes_restaurar(backup_content)
            summary = get_backup_info_summary(backup_content)
            
            # Mostrar información del respaldo
            st.markdown("#### Información del Respaldo")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Versión", summary.get('version', 'Desconocida'))
            with col2:
                st.metric("Tipo", summary.get('type', 'Completo'))
            with col3:
                st.metric("Módulos", len(summary.get('modules', [])))
            
            # Mostrar detalles
            if summary.get('timestamp'):
                st.write(f"**Fecha de creación:** {summary['timestamp'][:19].replace('T', ' ')}")
            
            if summary.get('modules'):
                st.write(f"**Módulos incluidos:** {', '.join(summary['modules'])}")
            
            # Mostrar estadísticas si están disponibles
            if 'total_companies' in summary:
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Empresas", summary.get('total_companies', 0))
                with col_b:
                    st.metric("Máquinas", summary.get('total_machines', 0))
                with col_c:
                    st.metric("Registros", summary.get('total_records', 0))
            
            # Mostrar validación
            if validation['warnings']:
                st.warning("**Advertencias:**")
                for warning in validation['warnings']:
                    st.write(f"• {warning}")
            
            if validation['errors']:
                st.error("**Errores encontrados:**")
                for error in validation['errors']:
                    st.write(f"• {error}")
                st.stop()
            
            # Opciones de restauración
            st.markdown("#### Opciones de Restauración")
            
            backup_type = summary.get('type', 'completo')
            
            if backup_type == 'empresa_especifica':
                st.info("Este es un respaldo de empresa específica")
                
                modo_restauracion = st.radio(
                    "Selecciona el modo de restauración:",
                    [
                        "Crear nueva empresa",
                        "Reemplazar empresa existente"
                    ]
                )
                
                target_empresa_id = None
                if modo_restauracion == "Reemplazar empresa existente":
                    from db_utils import list_companies
                    empresas = list_companies()
                    if not empresas.empty:
                        empresa_options = {}
                        for _, emp in empresas.iterrows():
                            empresa_options[f"{emp['name']} (ID: {emp['id']})"] = emp['id']
                        
                        selected_empresa = st.selectbox(
                            "Seleccionar empresa a reemplazar:",
                            list(empresa_options.keys())
                        )
                        target_empresa_id = empresa_options[selected_empresa]
                        
                        st.warning(f"Todos los datos de la empresa seleccionada serán reemplazados")
                    else:
                        st.error("No hay empresas existentes para reemplazar")
                        st.stop()
            
            else:
                st.info("Este es un respaldo completo del sistema")
                st.error("**TODOS LOS DATOS DEL SISTEMA SERÁN REEMPLAZADOS**")
                modo_restauracion = "completo"
                target_empresa_id = None
            
            # Proceso de confirmación
            if st.button("Iniciar Proceso de Restauración", type="secondary"):
                st.session_state.restore_step = 1
                st.session_state.backup_to_restore = backup_content
                st.session_state.restore_mode = modo_restauracion
                st.session_state.target_empresa_id = target_empresa_id
                st.rerun()
                
        except json.JSONDecodeError:
            st.error("Archivo de respaldo inválido. Selecciona un archivo JSON válido.")
        except Exception as e:
            st.error(f"Error al leer el archivo: {str(e)}")
    
    # Confirmación de restauración
    if st.session_state.get('restore_step') == 1:
        st.markdown("### CONFIRMACIÓN DE RESTAURACIÓN")
        
        modo = st.session_state.get('restore_mode', 'completo')
        
        if modo == "completo":
            st.error("**ESTA ACCIÓN ELIMINARÁ TODOS LOS DATOS DEL SISTEMA**")
            st.error("**ESTA ACCIÓN NO SE PUEDE DESHACER**")
            confirm_text_needed = "RESTAURAR SISTEMA COMPLETO"
        else:
            empresa_name = st.session_state.backup_to_restore.get('backup_info', {}).get('empresa_nombre', 'empresa')
            if st.session_state.get('target_empresa_id'):
                st.error(f"**SE REEMPLAZARÁN TODOS LOS DATOS DE LA EMPRESA SELECCIONADA**")
                confirm_text_needed = "REEMPLAZAR EMPRESA"
            else:
                st.warning(f"**SE CREARÁ UNA NUEVA EMPRESA: {empresa_name}**")
                confirm_text_needed = "CREAR EMPRESA"
        
        st.write(f"Para continuar, escriba exactamente: **{confirm_text_needed}**")
        confirm_text = st.text_input("Confirmación:")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("CONFIRMAR RESTAURACIÓN", type="primary"):
                if confirm_text == confirm_text_needed:
                    with st.spinner("Restaurando datos..."):
                        try:
                            from db_utils import restaurar_desde_respaldo
                            
                            success, result = restaurar_desde_respaldo(
                                st.session_state.backup_to_restore,
                                modo=modo if modo == "completo" else "empresa_especifica",
                                target_empresa_id=st.session_state.get('target_empresa_id')
                            )
                            
                            if success:
                                st.success("Restauración completada exitosamente!")
                                
                                if 'tablas_restauradas' in result:
                                    col_a, col_b = st.columns(2)
                                    with col_a:
                                        st.metric("Tablas restauradas", result['tablas_restauradas'])
                                    with col_b:
                                        st.metric("Registros restaurados", result['registros_restaurados'])
                                
                                if result.get('errores'):
                                    st.warning(f"Se encontraron {len(result['errores'])} errores durante la restauración:")
                                    for error in result['errores'][:5]:  # Mostrar máximo 5 errores
                                        st.write(f"• {error}")
                                
                                st.info("El sistema se recargará automáticamente...")
                                
                                # Limpiar estado
                                for key in list(st.session_state.keys()):
                                    if 'restore' in key or 'backup' in key:
                                        del st.session_state[key]
                                
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"Error durante la restauración: {result.get('error', 'Error desconocido')}")
                                
                        except Exception as e:
                            st.error(f"Error crítico durante la restauración: {str(e)}")
                else:
                    st.error("Texto de confirmación incorrecto")
        
        with col2:
            if st.button("Cancelar Restauración"):
                for key in list(st.session_state.keys()):
                    if 'restore' in key or 'backup' in key:
                        del st.session_state[key]
                st.rerun()

def mostrar_validar_respaldo():
    """Interface para validar respaldos"""
    
    st.markdown("### Validar Respaldo")
    st.info("Verifica la integridad y compatibilidad de un archivo de respaldo sin restaurarlo")
    
    uploaded_file = st.file_uploader(
        "Seleccionar archivo para validar", 
        type=['json'],
        help="Selecciona un archivo de respaldo para validar",
        key="validate_file"
    )
    
    if uploaded_file is not None:
        try:
            backup_content = json.loads(uploaded_file.read())
            
            from db_utils import validar_respaldo_antes_restaurar, get_backup_info_summary
            
            with st.spinner("Validando respaldo..."):
                validation = validar_respaldo_antes_restaurar(backup_content)
                summary = get_backup_info_summary(backup_content)
            
            # Resultado de validación
            if validation['is_valid']:
                st.success("El respaldo es válido y compatible")
            else:
                st.error("Se encontraron problemas en el respaldo")
            
            # Información detallada
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Información General")
                st.write(f"**Versión:** {validation.get('version', 'Desconocida')}")
                st.write(f"**Tipo:** {validation.get('type', 'Completo')}")
                st.write(f"**Tamaño:** {summary.get('size_estimate', 0):,} bytes")
                
                if summary.get('timestamp'):
                    st.write(f"**Creado:** {summary['timestamp'][:19].replace('T', ' ')}")
                
                if summary.get('modules'):
                    st.write(f"**Módulos:** {', '.join(summary['modules'])}")
            
            with col2:
                st.markdown("#### Estadísticas")
                
                if 'total_companies' in summary:
                    st.metric("Empresas", summary.get('total_companies', 0))
                if 'total_machines' in summary:
                    st.metric("Máquinas", summary.get('total_machines', 0))
                if 'total_records' in summary:
                    st.metric("Registros totales", summary.get('total_records', 0))
                if summary.get('has_assets'):
                    st.write("Incluye archivos adjuntos")
                else:
                    st.write("No incluye archivos adjuntos")
            
            # Advertencias y errores
            if validation.get('warnings'):
                st.warning("**Advertencias:**")
                for warning in validation['warnings']:
                    st.write(f"• {warning}")
            
            if validation.get('errors'):
                st.error("**Errores encontrados:**")
                for error in validation['errors']:
                    st.write(f"• {error}")
            
            # Compatibilidad
            st.markdown("#### Compatibilidad")
            version = validation.get('version', '')
            if version in ['2.0']:
                st.success("Compatible con esta versión del sistema")
            elif version in ['1.0']:
                st.warning("Versión antigua - se puede migrar automáticamente")
                if st.button("Migrar a v2.0"):
                    try:
                        from db_utils import migrar_respaldo_v1_a_v2
                        migrated_backup = migrar_respaldo_v1_a_v2(backup_content)
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"SANDI_Migrado_{timestamp}.json"
                        
                        st.download_button(
                            label="Descargar Respaldo Migrado",
                            data=migrated_backup,
                            file_name=filename,
                            mime="application/json"
                        )
                        st.success("Migración completada")
                    except Exception as e:
                        st.error(f"Error en migración: {e}")
            else:
                st.error("Versión no compatible")
                
        except json.JSONDecodeError:
            st.error("El archivo no es un JSON válido")
        except Exception as e:
            st.error(f"Error validando archivo: {str(e)}")

def mostrar_info_respaldos():
    """Muestra información sobre el sistema de respaldos"""
    
    st.markdown("### Información del Sistema de Respaldos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        #### Versión Mejorada
        
        **Mejoras principales:**
        - Respaldo completo de todos los módulos
        - Respaldo específico por empresa
        - Validación antes de restaurar
        - Migración automática desde versiones anteriores
        - Incluye logos y archivos
        - Estadísticas detalladas
        - Múltiples niveles de confirmación
        
        **Módulos incluidos:**
        - Core (empresas, máquinas)
        - Fluidos (combustible, tanques)
        - Mantenimiento (registros, programación)
        - Controles (alertas, configuraciones)
        - EXTRAS (costos específicos)
        """)
    
    with col2:
        st.markdown("""
        #### Recomendaciones
        
        **Frecuencia de respaldos:**
        - **Diario:** Si hay mucha actividad
        - **Semanal:** Para uso normal
        - **Antes de cambios:** Siempre
        
        **Tipos de respaldo:**
        - **Sistema completo:** Para respaldo total
        - **Por empresa:** Para respaldos específicos
        
        **Almacenamiento:**
        - Guarda en múltiples ubicaciones
        - Considera almacenamiento en la nube
        - Mantén respaldos de diferentes fechas
        
        **Verificación:**
        - Valida respaldos periódicamente
        - Prueba restauraciones en entorno de prueba
        """)
    
    # Estado actual del sistema
    st.markdown("#### Estado Actual del Sistema")
    
    try:
        # Obtener estadísticas del sistema actual
        from db_utils import list_companies, list_machinery
        empresas = list_companies()
        total_empresas = len(empresas) if not empresas.empty else 0
        
        total_maquinas = 0
        empresas_con_logo = 0
        
        if not empresas.empty:
            for _, empresa in empresas.iterrows():
                maquinas = list_machinery(empresa['id'])
                total_maquinas += len(maquinas) if not maquinas.empty else 0
                
                # Verificar logo
                try:
                    from db_utils import get_company_logo_base64
                    if get_company_logo_base64(empresa['id']):
                        empresas_con_logo += 1
                except:
                    pass
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Empresas totales", total_empresas)
        with col_b:
            st.metric("Máquinas totales", total_maquinas)
        with col_c:
            st.metric("Empresas con logo", empresas_con_logo)
        
        # Recomendación de respaldo
        if total_empresas > 0:
            st.success("**Recomendación:** Crea un respaldo completo regularmente para proteger toda tu información.")
        else:
            st.info("No hay datos para respaldar en este momento.")
            
    except Exception as e:
        st.error(f"Error obteniendo estadísticas: {e}")

