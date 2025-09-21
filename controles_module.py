"""
controles_module
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from db_utils import get_conn
from typing import Dict, List, Tuple
import sqlite3
from db_utils import get_machinery_for_controls
machinery = get_machinery_for_controls

def init_controles_db():
    """Inicializa las tablas necesarias para el sistema de inventario de fluidos - VERSIÓN MEJORADA"""
    try:
        # Configurar WAL ANTES de cualquier transacción
        with get_conn() as conn:
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA busy_timeout=30000;")
                conn.commit()
            except Exception as e:
                print(f"Advertencia configurando WAL: {e}")
        
        # Crear tablas en una sola transacción
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Tabla para tipos de fluidos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fluid_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    unit_type TEXT DEFAULT 'volume',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Tabla para tanques de fluidos por empresa
            cur.execute("""
                CREATE TABLE IF NOT EXISTS company_fluid_tanks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER,
                    fluid_type_id INTEGER,
                    tank_capacity REAL NOT NULL,
                    current_level REAL DEFAULT 0.0,
                    unit TEXT DEFAULT 'galones',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (fluid_type_id) REFERENCES fluid_types(id),
                    UNIQUE(company_id, fluid_type_id)
                );
            """)
            
            # Tabla unificada para movimientos de inventario
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fluid_inventory_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tank_id INTEGER NOT NULL,
                    movement_type TEXT NOT NULL CHECK(movement_type IN ('ENTRADA', 'SALIDA')),
                    quantity REAL NOT NULL,
                    unit_cost REAL,
                    total_cost REAL,
                    machinery_id INTEGER,
                    supplier TEXT,
                    operator TEXT,
                    reference_number TEXT,
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tank_id) REFERENCES company_fluid_tanks(id) ON DELETE CASCADE,
                    FOREIGN KEY (machinery_id) REFERENCES machinery(id)
                );
            """)
            
            # Tabla para configuraciones de empresa
            cur.execute("""
                CREATE TABLE IF NOT EXISTS company_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER,
                    setting_key TEXT NOT NULL,
                    setting_value TEXT NOT NULL,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    UNIQUE(company_id, setting_key)
                );
            """)
            
            # Tabla para configuraciones de alertas globales
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alert_configurations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    config_type TEXT NOT NULL,
                    config_key TEXT NOT NULL,
                    config_value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    UNIQUE(company_id, config_type, config_key)
                );
            """)
            
            # NUEVA: Tabla para configuraciones individuales por tanque
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tank_configurations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tank_id INTEGER NOT NULL,
                    config_key TEXT NOT NULL,
                    config_value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tank_id) REFERENCES company_fluid_tanks(id) ON DELETE CASCADE,
                    UNIQUE(tank_id, config_key)
                )
            """)
            
            # Resto del código de migración existente...
            # Verificar y agregar columna company_id si no existe (migración)
            try:
                cur.execute("PRAGMA table_info(alert_configurations)")
                columns = [col[1] for col in cur.fetchall()]
                if 'company_id' not in columns:
                    cur.execute("ALTER TABLE alert_configurations ADD COLUMN company_id INTEGER")
                    cur.execute("UPDATE alert_configurations SET company_id = 1 WHERE company_id IS NULL")
            except sqlite3.OperationalError:
                pass
            
            # Actualizar tabla machinery para consumo por hora
            try:
                cur.execute("ALTER TABLE machinery ADD COLUMN consumption_per_hour REAL DEFAULT 0.0;")
                cur.execute("ALTER TABLE machinery ADD COLUMN current_odometer REAL DEFAULT 0.0;")
                cur.execute("ALTER TABLE machinery ADD COLUMN maintenance_interval_hours REAL;")
                cur.execute("ALTER TABLE machinery ADD COLUMN maintenance_interval_km REAL;")
                cur.execute("ALTER TABLE machinery ADD COLUMN current_hours REAL DEFAULT 0.0;")
            except sqlite3.OperationalError:
                pass
            
            # Insertar tipos de fluidos por defecto
            default_fluids = [
                ("Combustible", "volume"),
                ("Aceite", "volume"),
                ("Grasa", "volume"),
                ("Coolant", "volume")
            ]
            
            for name, unit_type in default_fluids:
                cur.execute("INSERT OR IGNORE INTO fluid_types (name, unit_type) VALUES (?, ?)", (name, unit_type))
            
            # Crear la vista unificada de maquinaria
            try:
                cur.execute("""
                    CREATE VIEW IF NOT EXISTS machinery_unified AS
                    SELECT 
                        id,
                        name,
                        identifier,
                        classification,
                        status,
                        COALESCE(current_hours, 0) AS current_hours,
                        COALESCE(current_odometer, 0) AS current_km,
                        COALESCE(current_odometer, 0) AS current_odometer,
                        last_maintenance_date,
                        last_maintenance_hours,
                        last_maintenance_km,
                        last_status_change,
                        company_id
                    FROM machinery;
                """)
            except Exception as e:
                print(f"Error creando vista machinery_unified: {e}")

            conn.commit()
            
    except Exception as e:
        print(f"Error inicializando base de datos: {e}")
        raise

def mostrar_controles(empresa_id):
    """Función principal para mostrar el sistema unificado de controles"""
    init_controles_db()
    
    st.header("Sistema de Control de Fluidos")
    
    # Inicializar tanques si no existen
    initialize_company_tanks(empresa_id)
    
    # Obtener configuración de unidades
    unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
    
    # Pestañas principales actualizadas
    tabs = st.tabs(["📊 General", "🛢️ Tanques", "🚛 Despachos", "📋 Historial", "🔧 Configuración"])
    
    with tabs[0]:
        mostrar_dashboard_fluidos(empresa_id, unit_preference)
    
    with tabs[1]:
        mostrar_gestion_tanques(empresa_id, unit_preference)
    
    with tabs[2]:
        mostrar_despachos_maquinaria(empresa_id, unit_preference)
    
    with tabs[3]:
        mostrar_historial_completo(empresa_id, unit_preference)
    
    with tabs[4]:
        try:
            from controles_config import mostrar_configuracion_controles
            mostrar_configuracion_controles(empresa_id)
        except ImportError:
            st.error("Módulo de configuración no encontrado")
        except Exception as e:
            st.error(f"Error en configuración: {str(e)}")

def mostrar_dashboard_fluidos(empresa_id, unit_preference):
    """Dashboard completo modificado con alertas modernas y configuración individual"""
    st.subheader("Estado del Inventario")
    
    tanques = get_company_tanks(empresa_id)
    
    if tanques.empty:
        st.info("🛢️ No hay tanques configurados para esta empresa")
        st.markdown("Vaya a la sección **'Tanques > Crear Tanque'** para configurar sus primeros tanques.")
        
        # Mostrar tipos de fluidos disponibles
        fluidos_disponibles = get_available_fluid_types_for_company(empresa_id)
        if not fluidos_disponibles.empty:
            st.markdown("**Tipos de fluidos disponibles:**")
            for _, fluido in fluidos_disponibles.iterrows():
                st.markdown(f"• {fluido['name']}")
        
        # Mostrar algunas estadísticas básicas aunque no haya tanques
        st.divider()
        st.subheader("📊 Estadísticas de la Empresa")
        
        # Obtener información básica de maquinaria
        maquinas = get_active_machinery(empresa_id)
        if not maquinas.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Máquinas Activas", len(maquinas))
            with col2:
                total_consumption = maquinas['consumption_per_hour'].sum() if 'consumption_per_hour' in maquinas.columns else 0
                st.metric("Consumo Total/Hora", f"{total_consumption:.1f} gal")
            with col3:
                st.metric("Tanques Configurados", "0")
        
        return
    
    # Métricas generales de tanques
    st.markdown("### Resumen de Tanques")
    
    # Calcular métricas totales
    total_capacity = tanques['tank_capacity'].sum()
    total_current = tanques['current_level'].sum()
    avg_percentage = (total_current / total_capacity * 100) if total_capacity > 0 else 0
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Tanques Configurados", 
            len(tanques),
            help="Número total de tanques en esta empresa"
        )
    
    with col2:
        st.metric(
            "Capacidad Total", 
            f"{total_capacity:.0f} {unit_preference}",
            help="Capacidad total de todos los tanques"
        )
    
    with col3:
        st.metric(
            "Inventario Actual", 
            f"{total_current:.1f} {unit_preference}",
            help="Inventario total actual en todos los tanques"
        )
    
    with col4:
        status_color = "🟢" if avg_percentage >= 70 else "🟡" if avg_percentage >= 40 else "🔴"
        st.metric(
            "Nivel Promedio", 
            f"{avg_percentage:.1f}%",
            delta=status_color,
            help="Porcentaje promedio de llenado de todos los tanques"
        )
    
    st.divider()
    
    # Métricas individuales por tanque con configuración individual
    st.markdown("### Estado Individual de Tanques")
    
    # Crear columnas dinámicamente según el número de tanques
    num_tanques = len(tanques)
    if num_tanques <= 4:
        cols = st.columns(num_tanques)
    else:
        cols = st.columns(4)
    
    for i, (_, tank) in enumerate(tanques.iterrows()):
        col_index = i % len(cols)
        with cols[col_index]:
            # Obtener configuración específica del tanque
            thresholds = get_tank_alert_thresholds(tank['id'], empresa_id)
            percentage = calculate_tank_percentage(tank)
            
            # Determinar estado usando configuración individual
            if percentage <= thresholds['critical']:
                emoji = "🔴"
                status_text = "Crítico"
            elif percentage <= thresholds['low']:
                emoji = "🟡"
                status_text = "Bajo"
            else:
                emoji = "🟢"
                status_text = "Normal"
            
            st.metric(
                label=f"{emoji} {tank['fluid_name']}",
                value=f"{tank['current_level']:.1f} {unit_preference}",
                delta=f"{percentage:.1f}% - {status_text}",
                help=f"Umbrales: Crítico ≤{thresholds['critical']}%, Bajo ≤{thresholds['low']}%"
            )
            
            # Barra de progreso visual
            st.progress(
                percentage / 100, 
                text=f"{percentage:.1f}% lleno"
            )
            
            # Botón de configuración individual
            if st.button(f"⚙️ Config", key=f"config_btn_{tank['id']}"):
                st.session_state[f"show_tank_config_{tank['id']}"] = True
            
            # Agregar separación visual cada 4 tanques
            if (i + 1) % 4 == 0 and i + 1 < num_tanques:
                st.markdown("---")
    
    st.divider()

    # ALERTAS MODERNAS (ANTES de movimientos recientes)
    alertas = get_fluid_alerts(empresa_id)
    mostrar_alertas_modernas(alertas)
    
    # Mostrar configuración de tanque si está solicitada
    for _, tank in tanques.iterrows():
        if st.session_state.get(f"show_tank_config_{tank['id']}", False):
            with st.expander(f"⚙️ Configurar Alertas - {tank['fluid_name']}", expanded=True):
                mostrar_configuracion_alertas_tanque(tank['id'], empresa_id)
                if st.button("✖️ Cerrar", key=f"close_config_{tank['id']}"):
                    st.session_state[f"show_tank_config_{tank['id']}"] = False
                    st.rerun()
    
    st.divider()
    
    # Sección de actividad reciente
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Movimientos Recientes")
        mostrar_movimientos_recientes(empresa_id, limit=8)
    
    with col2:
        st.subheader("📊 Resumen del Día")
        mostrar_resumen_despachos_hoy(empresa_id, unit_preference)
    
    # Sección de análisis rápido
    st.divider()
    st.subheader("📈 Análisis Rápido")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Tanque con menor nivel
        if not tanques.empty:
            tanques_con_porcentaje = tanques.copy()
            tanques_con_porcentaje['percentage'] = tanques_con_porcentaje.apply(calculate_tank_percentage, axis=1)
            tanque_menor = tanques_con_porcentaje.loc[tanques_con_porcentaje['percentage'].idxmin()]
            
            st.metric(
                "Tanque con Menor Nivel",
                f"{tanque_menor['fluid_name']}",
                f"{tanque_menor['percentage']:.1f}%"
            )
    
    with col2:
        # Tanque con mayor capacidad disponible
        if not tanques.empty:
            tanques['disponible'] = tanques['tank_capacity'] - tanques['current_level']
            tanque_mayor_disponible = tanques.loc[tanques['disponible'].idxmax()]
            
            st.metric(
                "Mayor Capacidad Disponible",
                f"{tanque_mayor_disponible['fluid_name']}",
                f"{tanque_mayor_disponible['disponible']:.1f} {unit_preference}"
            )
    
    with col3:
        # Número de tanques que necesitan atención
        tanques_atencion = len([a for a in alertas if a['level'] in ['critico', 'advertencia']])
        
        st.metric(
            "Tanques Requieren Atención",
            tanques_atencion,
            "🔴" if tanques_atencion > 0 else "🟢"
        )

def mostrar_gestion_tanques(empresa_id, unit_preference):
    """Gestión simplificada de tanques con enfoque de inventario - CORREGIDA"""
    st.subheader("Gestión de Tanques")
    
    tanques = get_company_tanks(empresa_id)
    
    if tanques.empty:
        st.warning("No hay tanques configurados.")
        return
    
    # Selector de tanque
    tank_options = {}
    for _, tank in tanques.iterrows():
        percentage = calculate_tank_percentage(tank)
        display_name = f"{tank['fluid_name']} ({percentage:.1f}% - {tank['current_level']:.1f}/{tank['tank_capacity']:.0f} {unit_preference})"
        tank_options[display_name] = tank
    
    selected_display = st.selectbox("Seleccionar tanque:", list(tank_options.keys()))
    
    if not selected_display:
        return
    
    selected_tank = tank_options[selected_display]
    
    # Información del tanque seleccionado
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"### {selected_tank['fluid_name']}")
        
        # Indicador circular del nivel
        percentage = calculate_tank_percentage(selected_tank)
        mostrar_indicador_tanque_circular(selected_tank, percentage, unit_preference)
    
    with col2:
        # Métricas del tanque
        st.metric("Nivel Actual", f"{selected_tank['current_level']:.1f} {unit_preference}")
        st.metric("Capacidad Total", f"{selected_tank['tank_capacity']:.0f} {unit_preference}")
        st.metric("Disponible", f"{(selected_tank['tank_capacity'] - selected_tank['current_level']):.1f} {unit_preference}")
        st.metric("Porcentaje", f"{percentage:.1f}%")
    
    st.divider()
    
    # Verificar si el tanque está lleno
    available_capacity = selected_tank['tank_capacity'] - selected_tank['current_level']
    
    if available_capacity <= 0:
        st.warning("⚠️ El tanque está lleno. No se puede agregar más inventario.")
        st.info("💡 Para agregar inventario, considere aumentar la capacidad del tanque o consumir parte del inventario actual.")
    else:
        # Formulario de reabastecimiento (ENTRADA) - SOLO si hay capacidad
        st.subheader("➕ Reabastecimiento (Entrada de Inventario)")
        
        entrada_form_key = f"entrada_inventario_{selected_tank['id']}" if selected_tank is not None and 'id' in selected_tank else "entrada_inventario"
        with st.form(entrada_form_key, clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # Asegurar que max_value sea siempre mayor que min_value
                max_capacity = max(0.1, float(available_capacity))
                
                cantidad_entrada = st.number_input(
                    f"Cantidad a agregar ({unit_preference})",
                    min_value=0.1,
                    max_value=max_capacity,
                    step=0.1,
                    format="%.2f",
                    help=f"Capacidad disponible: {available_capacity:.1f} {unit_preference}"
                )
                
                costo_unitario = st.number_input(
                    f"Costo por {unit_preference} ($)",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f"
                )
            
            with col2:
                proveedor = st.text_input("Proveedor")
                numero_factura = st.text_input("Número de Factura/Referencia")
            
            notas = st.text_area("Notas adicionales")
            
            # Validación adicional en el botón
            entrada_valida = cantidad_entrada > 0 and cantidad_entrada <= available_capacity
            
            if st.form_submit_button("Registrar Entrada", disabled=not entrada_valida):
                if entrada_valida:
                    success, message = procesar_entrada_inventario(
                        selected_tank['id'],
                        cantidad_entrada,
                        costo_unitario,
                        proveedor,
                        numero_factura,
                        notas,
                        st.session_state.get("username", "admin")
                    )
                    
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    if cantidad_entrada > available_capacity:
                        st.error(f"La cantidad ({cantidad_entrada:.1f}) excede la capacidad disponible ({available_capacity:.1f})")
                    else:
                        st.error("La cantidad debe ser mayor a 0")
    
    st.divider()
    
    # Historial de movimientos del tanque (siempre mostrar)
    st.subheader("📋 Historial de Movimientos")
    mostrar_historial_tanque(selected_tank['id'])

def mostrar_despachos_maquinaria(empresa_id, unit_preference):
    """Gestión de despachos a maquinaria (SALIDAS de inventario) - VERSIÓN CON DEBUG"""
    st.subheader("Despachos a Maquinaria")
    
    # Obtener maquinaria activa
    maquinas = get_active_machinery(empresa_id)
    
    if maquinas.empty:
        st.warning("No hay maquinaria activa registrada.")
        st.info("Para registrar despachos, primero debe tener maquinaria con estado 'Activa' en el módulo de Maquinaria.")
        return
    
    # Obtener tanques con fluido disponible - ACTUALIZAR CADA VEZ
    tanques = get_company_tanks(empresa_id)
    tanques_disponibles = tanques[tanques['current_level'] > 0.1]
    
    # DEBUG: Mostrar información de los tanques
    st.write("DEBUG - Información de tanques:")
    st.write(f"Total tanques: {len(tanques)}")
    st.write(f"Tanques disponibles: {len(tanques_disponibles)}")
    if not tanques_disponibles.empty:
        st.write("Columnas disponibles:", tanques_disponibles.columns.tolist())
        st.write("Primeros tanques:", tanques_disponibles[['fluid_name', 'current_level']].head())
        # Verificar si existe columna 'id'
        if 'id' in tanques_disponibles.columns:
            st.write("IDs de tanques:", tanques_disponibles['id'].tolist())
        else:
            st.error("PROBLEMA: No existe columna 'id' en tanques_disponibles")
            st.write("Todas las columnas:", tanques_disponibles.columns.tolist())
    
    if tanques_disponibles.empty:
        st.warning("No hay fluidos disponibles en los tanques.")
        st.info("Para realizar despachos, primero debe tener inventario en los tanques. Vaya a la sección 'Tanques' para reabastecerlos.")
        return
    
    # Sección principal dividida en pestañas
    tab1, tab2 = st.tabs(["Nuevo Despacho", "Historial de Despachos"])
    
    with tab1:
        st.markdown("### Registrar Nuevo Despacho")
        
        # Preparar opciones de máquinas
        machine_options = []
        for idx, (_, machine) in enumerate(maquinas.iterrows()):
            consumption_info = ""
            if 'consumption_per_hour' in machine and machine['consumption_per_hour'] > 0:
                consumption_info = f" ({machine['consumption_per_hour']:.1f} gal/h)"
            
            display_name = f"{machine['name']}"
            if machine.get('identifier'):
                display_name += f" - {machine['identifier']}"
            display_name += consumption_info
            
            machine_options.append(display_name)
        
        # Preparar opciones de tanques
        tank_options = []
        for idx, (_, tank) in enumerate(tanques_disponibles.iterrows()):
            display_name = f"{tank['fluid_name']} (Disponible: {tank['current_level']:.1f} {unit_preference})"
            tank_options.append(display_name)
        
        # Primera fila: Máquina y Fluido
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Seleccionar Máquina:**")
            selected_machine_idx = st.selectbox(
                "Máquina:", 
                range(len(machine_options)),
                format_func=lambda x: machine_options[x],
                help="Seleccione la máquina que recibirá el fluido"
            )
            
            selected_machine = maquinas.iloc[selected_machine_idx]
            
            # Mostrar información adicional de la máquina
            st.info(f"**{selected_machine['name']}**\n"
                   f"• Matrícula: {selected_machine.get('identifier', 'No asignada')}\n"
                   f"• Clasificación: {selected_machine.get('classification', 'No especificada')}")
        
        with col2:
            st.markdown("**Seleccionar Fluido:**")
            selected_tank_idx = st.selectbox(
                "Fluido:", 
                range(len(tank_options)),
                format_func=lambda x: tank_options[x],
                help="Seleccione el tipo de fluido a despachar"
            )
            
            selected_fluid_tank = tanques_disponibles.iloc[selected_tank_idx]
            
            # DEBUG: Mostrar información del tanque seleccionado
            st.write("DEBUG - Tanque seleccionado:")
            st.write(f"Índice seleccionado: {selected_tank_idx}")
            st.write(f"Datos del tanque: {selected_fluid_tank.to_dict()}")
            
            # Verificar si tiene ID
            if 'id' in selected_fluid_tank:
                tank_id = selected_fluid_tank['id']
                st.write(f"Tank ID encontrado: {tank_id}")
            else:
                st.error("PROBLEMA: El tanque seleccionado no tiene columna 'id'")
                # Intentar alternativas
                possible_id_columns = [col for col in selected_fluid_tank.index if 'id' in col.lower()]
                st.write(f"Posibles columnas de ID: {possible_id_columns}")
                if possible_id_columns:
                    tank_id = selected_fluid_tank[possible_id_columns[0]]
                    st.write(f"Usando columna alternativa: {possible_id_columns[0]} = {tank_id}")
                else:
                    st.stop()
            
            # ACTUALIZAR NIVEL EN TIEMPO REAL - Volver a consultar la BD
            try:
                with get_conn() as conn:
                    current_tank_data = pd.read_sql_query("""
                        SELECT current_level, tank_capacity 
                        FROM company_fluid_tanks 
                        WHERE id = ?
                    """, conn, params=(tank_id,))
                    
                    st.write(f"DEBUG - Consulta BD con tank_id={tank_id}")
                    st.write(f"Resultado consulta: {current_tank_data.to_dict() if not current_tank_data.empty else 'VACÍO'}")
                    
                    if not current_tank_data.empty:
                        current_level = current_tank_data.iloc[0]['current_level']
                        tank_capacity = current_tank_data.iloc[0]['tank_capacity']
                        # Actualizar el valor en selected_fluid_tank
                        selected_fluid_tank = selected_fluid_tank.copy()
                        selected_fluid_tank['current_level'] = current_level
                        selected_fluid_tank['tank_capacity'] = tank_capacity
                        st.success(f"Nivel actualizado: {current_level:.1f}/{tank_capacity:.1f}")
                    else:
                        st.error(f"No se encontró tanque con ID {tank_id} en la base de datos")
            except Exception as e:
                st.error(f"Error consultando BD: {str(e)}")
            
            # Mostrar gráfico de nivel del tanque seleccionado - ACTUALIZADO
            percentage = calculate_tank_percentage(selected_fluid_tank)
            st.progress(percentage / 100, text=f"Nivel del tanque: {percentage:.1f}%")
        
        # Segunda fila: Cantidad y detalles operacionales
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown("**Cantidad a Despachar:**")
            max_available = float(selected_fluid_tank['current_level'])
            
            cantidad_despacho = st.number_input(
                f"Cantidad ({unit_preference})",
                min_value=0.1,
                max_value=max_available,
                step=0.1,
                format="%.2f",
                value=min(10.0, max_available),
                help=f"Máximo disponible: {max_available:.1f} {unit_preference}"
            )
            
            # Mostrar consumo estimado si está disponible
            if 'consumption_per_hour' in selected_machine:
                consumption_rate = selected_machine['consumption_per_hour']
                if consumption_rate > 0:
                    horas_estimadas = cantidad_despacho / consumption_rate
                    st.caption(f"Duración estimada: {horas_estimadas:.1f} horas")
        
        with col4:
            st.markdown("**Información Operacional:**")
            operador = st.text_input(
                "Operador", 
                placeholder="Nombre del operador",
                help="Nombre de la persona que opera la máquina"
            )
            
            horas_trabajadas = st.number_input(
                "Horas trabajadas estimadas", 
                min_value=0.0, 
                max_value=24.0,
                step=0.5, 
                format="%.1f",
                help="Horas que se espera trabajar con este combustible"
            )
        
        # Tercera fila: Lecturas de instrumentos
        col5, col6 = st.columns(2)
        
        with col5:
            odometro_actual = st.number_input(
                "Lectura odómetro/horómetro", 
                min_value=0.0, 
                step=0.1, 
                format="%.1f",
                help="Lectura actual del odómetro o horómetro de la máquina"
            )
        
        with col6:
            # Mostrar lectura anterior si está disponible
            current_values = get_machine_current_values(selected_machine['id'])
            last_odometer = current_values.get('current_odometer', 0)
            last_hours = current_values.get('current_hours', 0)
            
            if last_odometer > 0 or last_hours > 0:
                st.info(f"Lecturas anteriores:\n"
                       f"• Odómetro: {last_odometer:.1f}\n" 
                       f"• Horas: {last_hours:.1f}")
                
                # Validar que la nueva lectura sea mayor
                if odometro_actual > 0 and odometro_actual < max(last_odometer, last_hours):
                    st.warning("La nueva lectura es menor que la anterior")
        
        # Cuarta fila: Notas
        notas_despacho = st.text_area(
            "Notas del despacho",
            placeholder="Observaciones, ubicación de trabajo, condiciones especiales, etc.",
            help="Información adicional sobre el despacho"
        )
        
        # Botón de confirmación - SIEMPRE ACTIVO con validación posterior
        col_btn = st.columns([1, 2, 1])[1]
        with col_btn:
            if st.button(
                "Realizar Despacho", 
                type="primary",
                use_container_width=True
            ):
                # DEBUG: Mostrar qué se va a enviar
                st.write("DEBUG - Datos para procesar_salida_inventario:")
                st.write(f"tank_id: {tank_id} (tipo: {type(tank_id)})")
                st.write(f"machine_id: {selected_machine['id']} (tipo: {type(selected_machine['id'])})")
                st.write(f"cantidad: {cantidad_despacho}")
                st.write(f"operador: '{operador}'")
                
                # VALIDACIÓN DESPUÉS de presionar el botón
                errores = []
                
                # Validar campos obligatorios
                if not operador.strip():
                    errores.append("Falta el nombre del operador")
                
                if cantidad_despacho <= 0:
                    errores.append("La cantidad debe ser mayor a 0")
                
                if cantidad_despacho > max_available:
                    errores.append(f"La cantidad ({cantidad_despacho:.1f}) excede lo disponible ({max_available:.1f})")
                
                if selected_machine is None:
                    errores.append("Debe seleccionar una máquina")
                    
                if selected_fluid_tank is None:
                    errores.append("Debe seleccionar un fluido")
                
                # Si hay errores, mostrarlos
                if errores:
                    for error in errores:
                        st.error(f"❌ {error}")
                    st.warning("Corrija los errores antes de continuar")
                else:
                    # Todo válido, procesar el despacho
                    success, message = procesar_salida_inventario(
                        tank_id,  # Usar la variable verificada
                        selected_machine['id'],
                        cantidad_despacho,
                        operador,
                        horas_trabajadas,
                        odometro_actual,
                        notas_despacho,
                        st.session_state.get("username", "admin")
                    )
                    
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                        
                        # Mostrar resumen del despacho
                        st.info(f"**Resumen del despacho:**\n"
                               f"• Máquina: {selected_machine['name']}\n"
                               f"• Fluido: {selected_fluid_tank['fluid_name']}\n" 
                               f"• Cantidad: {cantidad_despacho:.1f} {unit_preference}\n"
                               f"• Operador: {operador}")
                        
                        # Pausa y recarga
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        # Información adicional
        with st.expander("Información sobre despachos"):
            st.markdown("""
            **Campos obligatorios:**
            - Máquina seleccionada
            - Fluido disponible seleccionado  
            - Cantidad mayor a 0 y no exceder disponible
            - Nombre del operador
            
            **Campos opcionales:**
            - Horas trabajadas estimadas
            - Lectura de odómetro/horómetro
            - Notas adicionales
            """)
    
    with tab2:
        st.markdown("### Historial de Despachos")
        
        # Filtros para el historial
        col_filtro1, col_filtro2, col_filtro3 = st.columns(3)
        
        with col_filtro1:
            # Filtro por máquina
            maquinas_para_filtro = ["Todas"] + [f"{m['name']} ({m.get('identifier', 'N/A')})" for _, m in maquinas.iterrows()]
            filtro_maquina = st.selectbox("Filtrar por máquina:", maquinas_para_filtro)
        
        with col_filtro2:
            # Filtro por fluido
            fluidos_para_filtro = ["Todos"] + [tank['fluid_name'] for _, tank in tanques.iterrows()]
            filtro_fluido = st.selectbox("Filtrar por fluido:", fluidos_para_filtro)
        
        with col_filtro3:
            # Filtro por fecha
            dias_historial = st.selectbox("Últimos:", [7, 15, 30, 60, 90], index=1)
        
        # Mostrar historial filtrado
        mostrar_historial_despachos_filtrado(empresa_id, filtro_maquina, filtro_fluido, dias_historial, unit_preference)
    
    st.divider()
    
    # Resumen de despachos del día actual
    st.subheader("Resumen de Despachos Hoy")
    mostrar_resumen_despachos_hoy(empresa_id, unit_preference)

def mostrar_historial_completo(empresa_id, unit_preference):
    """Muestra el historial completo de movimientos con filtros y opción de descarga"""
    st.subheader("Historial Completo de Movimientos")
    
    # Filtros mejorados
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Filtro por tipo de movimiento
        tipo_movimiento = st.selectbox("Tipo de movimiento", ["Todos", "ENTRADA", "SALIDA"])
    
    with col2:
        # Filtro por tipo de fluido
        tanques = get_company_tanks(empresa_id)
        fluidos = ["Todos"] + tanques['fluid_name'].unique().tolist() if not tanques.empty else ["Todos"]
        filtro_fluido = st.selectbox("Filtrar por fluido", fluidos)
    
    with col3:
        # Filtro por rango de fechas
        rango_fechas = st.date_input(
            "Rango de fechas", 
            value=[],
            help="Seleccione fecha inicio y fin"
        )
    
    with col4:
        # Límite de registros
        limite_registros = st.selectbox("Máximo registros", [50, 100, 200, 500], index=1)
    
    # Obtener historial filtrado
    historial = obtener_historial_filtrado(empresa_id, tipo_movimiento, filtro_fluido, rango_fechas, limite_registros)
    
    if not historial.empty:
        # Mostrar estadísticas resumidas
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        with col_stat1:
            st.metric("Total Registros", len(historial))
        
        with col_stat2:
            total_entradas = historial[historial['movement_type'] == 'ENTRADA']['quantity'].sum()
            st.metric("Total Entradas", f"{total_entradas:.1f} {unit_preference}")
        
        with col_stat3:
            total_salidas = historial[historial['movement_type'] == 'SALIDA']['quantity'].sum()
            st.metric("Total Salidas", f"{total_salidas:.1f} {unit_preference}")
        
        with col_stat4:
            balance = total_entradas - total_salidas
            delta_color = "normal" if balance >= 0 else "inverse"
            st.metric("Balance", f"{balance:.1f} {unit_preference}", delta=f"{'➕' if balance >= 0 else '➖'}")
        
        st.divider()
        
        # Tabla de historial con formato mejorado
        historial_display = historial.copy()
        
        # Formatear fecha
        historial_display['Fecha'] = pd.to_datetime(historial_display['created_at']).dt.strftime('%d/%m/%Y %H:%M')
        
        # Formatear tipo con iconos
        historial_display['Tipo'] = historial_display['movement_type'].apply(
            lambda x: "⬆️ ENTRADA" if x == 'ENTRADA' else "⬇️ SALIDA"
        )
        
        # Formatear cantidad con unidad
        historial_display['Cantidad'] = historial_display.apply(
            lambda row: f"{row['quantity']:.1f} {unit_preference}", axis=1
        )
        
        # Seleccionar columnas para mostrar
        columns_to_display = ['Fecha', 'Tipo', 'fluid_name', 'Cantidad', 'machine_name', 'supplier', 'operator']
        column_names = ['Fecha', 'Tipo', 'Fluido', 'Cantidad', 'Máquina', 'Proveedor', 'Operador']
        
        # Crear DataFrame para mostrar
        display_df = historial_display[columns_to_display].copy()
        display_df.columns = column_names
        
        # Reemplazar valores nulos
        display_df = display_df.fillna('-')
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Opción de descarga
        st.divider()
        col_download1, col_download2 = st.columns(2)
        
        with col_download1:
            csv = convert_df_to_csv(historial)
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"historial_movimientos_{date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_download2:
            if st.button("🔄 Actualizar Datos", use_container_width=True):
                st.rerun()
        
        # Análisis por período si hay suficientes datos
        if len(historial) > 10:
            st.divider()
            st.subheader("📈 Análisis por Período")
            
            # Agrupar por fecha
            historial['fecha'] = pd.to_datetime(historial['created_at']).dt.date
            analisis_diario = historial.groupby(['fecha', 'movement_type'])['quantity'].sum().reset_index()
            
            if not analisis_diario.empty:
                import plotly.express as px
                
                fig = px.bar(
                    analisis_diario, 
                    x='fecha', 
                    y='quantity', 
                    color='movement_type',
                    title="Movimientos de Inventario por Día",
                    labels={'quantity': f'Cantidad ({unit_preference})', 'fecha': 'Fecha'},
                    color_discrete_map={'ENTRADA': '#28a745', 'SALIDA': '#dc3545'}
                )
                
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info("No hay movimientos que coincidan con los filtros")
        
        # Sugerencias si no hay datos
        with st.expander("💡 Sugerencias"):
            st.markdown("""
            **No se encontraron movimientos. Intente:**
            - Ampliar el rango de fechas
            - Cambiar filtros de fluido o tipo de movimiento
            - Verificar que hay tanques configurados en la empresa
            - Registrar algunos movimientos primero en la sección 'Tanques'
            """)

def procesar_salida_inventario(tank_id, machine_id, cantidad, operador, horas, odometro, notas, usuario):
    """Procesa una salida de inventario con manejo mejorado de transacciones"""
    try:
        # Usar UNA SOLA conexión para toda la operación
        with get_conn() as conn:
            # Configurar timeout para esta conexión
            conn.execute("PRAGMA busy_timeout=30000")  # 30 segundos
            
            # 1. Validar disponibilidad del tanque
            tank_info = pd.read_sql_query("""
                SELECT id, current_level, unit
                FROM company_fluid_tanks
                WHERE id = ?
            """, conn, params=(tank_id,))
            
            if tank_info.empty:
                return False, "Tanque no encontrado"
            
            tank = tank_info.iloc[0]
            current_level = float(tank['current_level'])

            if current_level < float(cantidad):
                return False, f"Inventario insuficiente. Disponible: {current_level:.1f} {tank['unit']}"
            
            # 2. Iniciar transacción explícita
            conn.execute("BEGIN IMMEDIATE")
            
            try:
                new_level = current_level - float(cantidad)
                
                # 3. Actualizar nivel del tanque
                conn.execute("""
                    UPDATE company_fluid_tanks 
                    SET current_level = ?
                    WHERE id = ?
                """, (new_level, tank_id))
                
                # 4. Registrar movimiento de salida
                conn.execute("""
                    INSERT INTO fluid_inventory_movements 
                    (tank_id, movement_type, quantity, machinery_id, operator, notes, created_by)
                    VALUES (?, 'SALIDA', ?, ?, ?, ?, ?)
                """, (tank_id, cantidad, machine_id, operador, notas, usuario))
                
                # 5. Actualizar odómetro directamente usando la misma lógica que db_utils
                if odometro > 0:
                    # Obtener valor actual y validar
                    cursor = conn.cursor()
                    cursor.execute("SELECT current_odometer FROM machinery WHERE id = ?", (machine_id,))
                    result = cursor.fetchone()
                    
                    if not result:
                        raise Exception(f"Máquina con ID {machine_id} no encontrada")
                    
                    current_odometer = result[0] if result[0] else 0
                    
                    # Validar que el nuevo valor sea mayor o igual
                    if odometro < current_odometer:
                        raise Exception(f"El nuevo odómetro ({odometro}) debe ser mayor o igual al actual ({current_odometer})")
                    
                    # Actualizar odómetro en machinery
                    cursor.execute("""
                        UPDATE machinery 
                        SET current_odometer = ?, last_odometer_update = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (odometro, machine_id))
                    
                    # Registrar en log solo si la tabla existe
                    try:
                        cursor.execute("""
                            INSERT INTO odometer_logs (machinery_id, current_odometer, recorded_by, recorded_at)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """, (machine_id, odometro, usuario))
                    except sqlite3.OperationalError:
                        # La tabla no existe, continuar sin log por ahora
                        pass
                
                # 6. Actualizar horómetro si se proporcionó
                if horas > 0:
                    conn.execute("""
                        UPDATE machinery 
                        SET current_hours = current_hours + ?
                        WHERE id = ?
                    """, (horas, machine_id))
                
                # 7. Commit de toda la transacción
                conn.commit()
                return True, f"Despacho realizado. Nivel restante: {new_level:.1f} {tank['unit']}"
                
            except Exception as e:
                # Rollback en caso de error
                conn.rollback()
                raise e
                
    except Exception as e:
        return False, f"Error al procesar despacho: {str(e)}"

def procesar_entrada_inventario(tank_id, cantidad, costo_unitario, proveedor, referencia, notas, usuario):
    """Procesa una entrada de inventario con manejo mejorado de transacciones"""
    try:
        with get_conn() as conn:
            # Configurar timeout
            conn.execute("PRAGMA busy_timeout=30000")
            
            # Validar que el tanque existe y obtener información
            tank_info = pd.read_sql_query("""
                SELECT id, tank_capacity, current_level, unit
                FROM company_fluid_tanks
                WHERE id = ?
            """, conn, params=(tank_id,))
            
            if tank_info.empty:
                return False, "Tanque no encontrado"
            
            tank = tank_info.iloc[0]
            new_level = float(tank['current_level']) + float(cantidad)
            
            if new_level > float(tank['tank_capacity']):
                available = float(tank['tank_capacity']) - float(tank['current_level'])
                return False, f"Excede la capacidad. Disponible: {available:.1f} {tank['unit']}"
            
            # Iniciar transacción
            conn.execute("BEGIN IMMEDIATE")
            
            try:
                # Actualizar nivel del tanque
                conn.execute("""
                    UPDATE company_fluid_tanks 
                    SET current_level = ?
                    WHERE id = ?
                """, (new_level, tank_id))
                
                # Registrar movimiento de entrada
                total_cost = float(cantidad) * float(costo_unitario) if costo_unitario > 0 else None
                
                conn.execute("""
                    INSERT INTO fluid_inventory_movements 
                    (tank_id, movement_type, quantity, unit_cost, total_cost, supplier, 
                     reference_number, notes, created_by)
                    VALUES (?, 'ENTRADA', ?, ?, ?, ?, ?, ?, ?)
                """, (tank_id, cantidad, costo_unitario if costo_unitario > 0 else None, 
                     total_cost, proveedor, referencia, notas, usuario))
                
                conn.commit()
                return True, f"Entrada registrada. Nuevo nivel: {new_level:.1f} {tank['unit']}"
                
            except Exception as e:
                conn.rollback()
                raise e
                
    except Exception as e:
        return False, f"Error al procesar entrada: {str(e)}"
# Funciones auxiliares

def get_company_tanks(empresa_id):
    """Obtiene tanques de la empresa con información actualizada"""
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT cft.id, cft.tank_capacity, cft.current_level, cft.unit,
                   ft.name as fluid_name, ft.id as fluid_type_id
            FROM company_fluid_tanks cft
            JOIN fluid_types ft ON cft.fluid_type_id = ft.id
            WHERE cft.company_id = ?
            ORDER BY ft.name
        """, conn, params=(empresa_id,))

# En controles_module.py - REEMPLAZA la función get_active_machinery existente

def get_active_machinery(empresa_id):
    """Obtiene maquinaria activa de la empresa con compatibilidad de estados"""
    try:
        # Importar la función compatible desde db_utils
        from db_utils import get_machinery_with_normalized_status
        
        # Obtener maquinaria con estado 'Active' (normalizado)
        return get_machinery_with_normalized_status(empresa_id, 'Active')
        
    except ImportError:
        # Fallback si no está disponible la función nueva
        with get_conn() as conn:
            # Buscar tanto 'Active' como 'Activa' como estados válidos
            return pd.read_sql_query("""
                SELECT id, name, identifier, classification, 
                       COALESCE(consumption_per_hour, 0) as consumption_per_hour
                FROM machinery 
                WHERE company_id = ? 
                AND (status = 'Active' OR status = 'Activa' OR status = 'ACTIVE' OR status = 'activa')
                ORDER BY name
            """, conn, params=(empresa_id,))
    except Exception as e:
        print(f"Error obteniendo maquinaria activa: {e}")
        return pd.DataFrame()

def calculate_tank_percentage(tank):
    """Calcula el porcentaje de llenado de un tanque"""
    if tank['tank_capacity'] <= 0:
        return 0
    return (tank['current_level'] / tank['tank_capacity']) * 100

def get_tank_status_color(percentage):
    """Obtiene color según el porcentaje del tanque - versión mejorada"""
    if percentage >= 70:
        return '#28a745'  # Verde
    elif percentage >= 40:
        return '#ffc107'  # Amarillo  
    elif percentage >= 20:
        return '#fd7e14'  # Naranja
    else:
        return '#dc3545'  # Rojo

def mostrar_indicador_tanque_circular(tank, percentage, unit_preference):
    """Muestra indicador circular del nivel del tanque"""
    import plotly.graph_objects as go
    
    # Determinar colores según el nivel
    if percentage >= 70:
        color_principal = '#28a745'  # Verde
    elif percentage >= 40:
        color_principal = '#ffc107'  # Amarillo
    elif percentage >= 20:
        color_principal = '#fd7e14'  # Naranja
    else:
        color_principal = '#dc3545'  # Rojo
    
    fig = go.Figure(go.Pie(
        values=[percentage, 100 - percentage],
        labels=['Ocupado', 'Disponible'],
        hole=0.6,
        marker_colors=[color_principal, '#e9ecef'],
        textinfo='none',
        showlegend=False,
        hovertemplate=f"<b>{tank['fluid_name']}</b><br>" +
                     f"Nivel: {tank['current_level']:.1f} {unit_preference}<br>" +
                     f"Capacidad: {tank['tank_capacity']:.1f} {unit_preference}<br>" +
                     f"Porcentaje: {percentage:.1f}%<extra></extra>"
    ))
    
    # Configurar layout
    fig.update_layout(
        showlegend=False,
        height=250,
        margin=dict(t=20, b=20, l=20, r=20),
        annotations=[
            dict(
                text=f"<b>{percentage:.1f}%</b><br><span style='font-size:12px'>{tank['current_level']:.1f}/{tank['tank_capacity']:.0f}</span>",
                x=0.5, y=0.5,
                font_size=18,
                showarrow=False,
                font_color=color_principal
            )
        ]
    )
    
    st.plotly_chart(fig, use_container_width=True)

def mostrar_movimientos_recientes(empresa_id, limit=5):
    """Muestra movimientos recientes de inventario con mejor formato"""
    try:
        with get_conn() as conn:
            movimientos = pd.read_sql_query("""
                SELECT fim.movement_type, fim.quantity, fim.created_at,
                       ft.name as fluid_name, m.name as machine_name, 
                       fim.supplier, fim.operator, fim.notes,
                       cft.unit
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                LEFT JOIN machinery m ON fim.machinery_id = m.id
                WHERE cft.company_id = ?
                ORDER BY fim.created_at DESC
                LIMIT ?
            """, conn, params=(empresa_id, limit))
        
        if not movimientos.empty:
            for _, mov in movimientos.iterrows():
                # Formatear fecha
                try:
                    fecha_dt = pd.to_datetime(mov['created_at'])
                    fecha = fecha_dt.strftime('%d/%m %H:%M')
                except:
                    fecha = mov['created_at'][:16] if mov['created_at'] else "N/A"
                
                # Determinar iconos y colores
                if mov['movement_type'] == 'ENTRADA':
                    tipo_icon = "⬆️"
                    color_class = "🟢"
                    origen_destino = mov['supplier'] if mov['supplier'] else "Proveedor N/E"
                else:
                    tipo_icon = "⬇️"
                    color_class = "🔵"
                    origen_destino = mov['machine_name'] if mov['machine_name'] else "Máquina N/E"
                
                # Formato de cantidad
                cantidad_fmt = f"{mov['quantity']:.1f} {mov['unit']}"
                
                # Mostrar movimiento
                st.markdown(
                    f"{color_class} **{fecha}** {tipo_icon} "
                    f"**{mov['fluid_name']}**: {cantidad_fmt} → {origen_destino}"
                )
        else:
            st.info("No hay movimientos registrados")
    except Exception as e:
        st.error(f"Error cargando movimientos: {str(e)}")

def mostrar_historial_tanque(tank_id, limit=10):
    """Muestra historial mejorado de un tanque específico"""
    try:
        with get_conn() as conn:
            historial = pd.read_sql_query("""
                SELECT fim.movement_type, fim.quantity, fim.created_at, fim.supplier, fim.operator,
                       fim.reference_number, fim.notes, fim.total_cost, fim.unit_cost,
                       m.name as machine_name
                FROM fluid_inventory_movements fim
                LEFT JOIN machinery m ON fim.machinery_id = m.id
                WHERE fim.tank_id = ?
                ORDER BY fim.created_at DESC
                LIMIT ?
            """, conn, params=(tank_id, limit))
        
        if not historial.empty:
            st.markdown(f"**📋 Últimos {len(historial)} movimientos:**")
            
            for _, mov in historial.iterrows():
                # Formatear fecha
                try:
                    fecha_dt = pd.to_datetime(mov['created_at'])
                    fecha = fecha_dt.strftime('%d/%m/%Y %H:%M')
                except:
                    fecha = mov['created_at'][:16] if mov['created_at'] else "N/A"
                
                # Determinar detalles según tipo de movimiento
                if mov['movement_type'] == 'ENTRADA':
                    icon = "⬆️"
                    color = "🟢"
                    detalle = mov['supplier'] if mov['supplier'] else "Sin proveedor"
                    cantidad_texto = f"+{mov['quantity']:.1f}"
                    
                    # Agregar información de costo si está disponible
                    if mov['total_cost'] and mov['total_cost'] > 0:
                        costo_info = f" (${mov['total_cost']:.2f})"
                    else:
                        costo_info = ""
                        
                else:  # SALIDA
                    icon = "⬇️"
                    color = "🔵"
                    detalle = mov['machine_name'] if mov['machine_name'] else "Máquina N/E"
                    if mov['operator']:
                        detalle += f" (Op: {mov['operator']})"
                    cantidad_texto = f"-{mov['quantity']:.1f}"
                    costo_info = ""
                
                # Mostrar el movimiento
                st.markdown(
                    f"{color} **{fecha}** {icon} {cantidad_texto}{costo_info} → {detalle}"
                )
                
                # Mostrar notas si existen
                if mov['notes'] and str(mov['notes']).strip():
                    st.markdown(f"    📝 *{mov['notes']}*")
                
                # Mostrar referencia si existe
                if mov['reference_number'] and str(mov['reference_number']).strip():
                    st.markdown(f"    🔗 Ref: {mov['reference_number']}")
        else:
            st.info("📋 No hay historial para este tanque")
            
    except Exception as e:
        st.error(f"Error cargando historial: {str(e)}")


def mostrar_resumen_despachos_hoy(empresa_id, unit_preference):
    """Muestra resumen mejorado de despachos del día actual"""
    try:
        from datetime import date
        hoy = date.today().isoformat()
        
        with get_conn() as conn:
            despachos_hoy = pd.read_sql_query("""
                SELECT ft.name as fluid_name, 
                       SUM(fim.quantity) as total_despachado,
                       COUNT(*) as num_despachos,
                       cft.unit,
                       AVG(fim.quantity) as promedio_despacho
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ? AND fim.movement_type = 'SALIDA' 
                AND DATE(fim.created_at) = ?
                GROUP BY ft.name, cft.unit
                ORDER BY total_despachado DESC
            """, conn, params=(empresa_id, hoy))
        
        if not despachos_hoy.empty:
            for _, despacho in despachos_hoy.iterrows():
                st.metric(
                    label=f"📤 {despacho['fluid_name']}",
                    value=f"{despacho['total_despachado']:.1f} {unit_preference}",
                    delta=f"{int(despacho['num_despachos'])} despachos (prom: {despacho['promedio_despacho']:.1f})",
                    help=f"Total despachado hoy de {despacho['fluid_name']}"
                )
        else:
            st.info("📭 No hay despachos registrados hoy")
            
        # Mostrar también entradas del día
        with get_conn() as conn:
            entradas_hoy = pd.read_sql_query("""
                SELECT ft.name as fluid_name, 
                       SUM(fim.quantity) as total_entrada,
                       COUNT(*) as num_entradas,
                       cft.unit
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ? AND fim.movement_type = 'ENTRADA' 
                AND DATE(fim.created_at) = ?
                GROUP BY ft.name, cft.unit
                ORDER BY total_entrada DESC
            """, conn, params=(empresa_id, hoy))
        
        if not entradas_hoy.empty:
            st.markdown("**📥 Entradas de hoy:**")
            for _, entrada in entradas_hoy.iterrows():
                st.write(f"• {entrada['fluid_name']}: +{entrada['total_entrada']:.1f} {unit_preference} ({int(entrada['num_entradas'])} entradas)")
                
    except Exception as e:
        st.error(f"Error cargando resumen del día: {str(e)}")

def get_fluid_alerts(empresa_id):
    """Obtiene alertas de niveles críticos con información detallada - VERSIÓN MEJORADA"""
    alertas = []
    tanques = get_company_tanks(empresa_id)
    
    for _, tank in tanques.iterrows():
        try:
            # Obtener umbrales específicos para este tanque
            thresholds = get_tank_alert_thresholds(tank['id'], empresa_id)
            percentage = calculate_tank_percentage(tank)
            
            # Crear alerta con información detallada
            alerta_base = {
                'tank_id': tank['id'],
                'fluid_name': tank['fluid_name'],
                'percentage': percentage,
                'current_level': tank['current_level'],
                'capacity': tank['tank_capacity'],
                'unit': tank['unit'],
                'threshold_critical': thresholds['critical'],
                'threshold_low': thresholds['low'],
                'config_source': thresholds['source']
            }
            
            if percentage <= thresholds['critical']:
                alerta_base.update({
                    'level': 'critico',
                    'message': f"🚨 {tank['fluid_name']}: Nivel crítico {percentage:.1f}% (≤{thresholds['critical']}%)"
                })
                alertas.append(alerta_base)
                
            elif percentage <= thresholds['low']:
                alerta_base.update({
                    'level': 'bajo',
                    'message': f"⚠️ {tank['fluid_name']}: Nivel bajo {percentage:.1f}% (≤{thresholds['low']}%)"
                })
                alertas.append(alerta_base)
                
        except Exception as e:
            print(f"Error procesando alerta para tanque {tank.get('fluid_name', 'desconocido')}: {e}")
            continue
    
    return alertas

def initialize_company_tanks(empresa_id):
    """NO inicializa tanques automáticamente - solo verifica si existen"""
    try:
        from db_utils import get_company_tanks
        tanks = get_company_tanks(empresa_id)
        return not tanks.empty
    except Exception:
        return False

def get_company_setting(company_id, key, default_value):
    """Obtiene configuración de empresa"""
    with get_conn() as conn:
        result = pd.read_sql_query("""
            SELECT setting_value FROM company_settings 
            WHERE company_id = ? AND setting_key = ?
        """, conn, params=(company_id, key))
        
        if not result.empty:
            return result.iloc[0]['setting_value']
        return default_value

def set_company_setting(company_id, key, value):
    """Establece configuración de empresa"""
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO company_settings (company_id, setting_key, setting_value)
            VALUES (?, ?, ?)
        """, (company_id, key, str(value)))
        conn.commit()

def obtener_historial_filtrado(empresa_id, tipo_movimiento, filtro_fluido, rango_fechas, limite=100):
    """Obtiene el historial de movimientos filtrado según los parámetros"""
    try:
        with get_conn() as conn:
            query = """
                SELECT fim.movement_type, fim.quantity, fim.created_at,
                       ft.name as fluid_name, m.name as machine_name, 
                       fim.supplier, fim.operator, fim.notes,
                       fim.reference_number, fim.total_cost, fim.unit_cost
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                LEFT JOIN machinery m ON fim.machinery_id = m.id
                WHERE cft.company_id = ?
            """
            params = [empresa_id]
            
            # Filtro por tipo de movimiento
            if tipo_movimiento != "Todos":
                query += " AND fim.movement_type = ?"
                params.append(tipo_movimiento)
            
            # Filtro por fluido
            if filtro_fluido != "Todos":
                query += " AND ft.name = ?"
                params.append(filtro_fluido)
            
            # Filtro por rango de fechas
            if rango_fechas and len(rango_fechas) == 2:
                fecha_inicio = rango_fechas[0]
                fecha_fin = rango_fechas[1]
                query += " AND DATE(fim.created_at) BETWEEN ? AND ?"
                params.extend([fecha_inicio, fecha_fin])
            
            query += " ORDER BY fim.created_at DESC LIMIT ?"
            params.append(limite)
            
            return pd.read_sql_query(query, conn, params=params)
            
    except Exception as e:
        print(f"Error obteniendo historial filtrado: {e}")
        return pd.DataFrame()

def convert_df_to_csv(df):
    """Convierte un DataFrame a CSV en memoria"""
    return df.to_csv(index=False).encode('utf-8')

def convert_df_to_csv(df):
    """Convierte un DataFrame a CSV en memoria"""
    return df.to_csv(index=False).encode('utf-8')

def get_fluid_types():
    """Obtiene todos los tipos de fluidos disponibles"""
    with get_conn() as conn:
        return pd.read_sql_query("SELECT * FROM fluid_types ORDER BY name", conn)

def get_machine_fluid_status(machinery_id, fluid_type_id, unit_preference):
    """Obtiene el estado de un fluido específico para una máquina"""
    try:
        with get_conn() as conn:
            # Obtener información de la máquina
            machine_info = pd.read_sql_query("""
                SELECT consumption_per_hour, current_hours, name, identifier
                FROM machinery WHERE id = ?
            """, conn, params=(machinery_id,))
            
            if machine_info.empty:
                return {"level": "error", "message": "Máquina no encontrada"}
            
            machine = machine_info.iloc[0]
            consumption_per_hour = machine.get('consumption_per_hour', 0) or 0
            
            if consumption_per_hour <= 0:
                return {"level": "sin_datos", "message": "Consumo no definido"}
            
            # Obtener movimientos de este fluido para esta máquina
            movements = pd.read_sql_query("""
                SELECT fim.movement_type, fim.quantity, fim.created_at
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                WHERE fim.machinery_id = ? AND cft.fluid_type_id = ?
                ORDER BY fim.created_at ASC
            """, conn, params=(machinery_id, fluid_type_id))
            
            if movements.empty:
                return {"level": "sin_datos", "message": "No hay registros de este fluido"}
            
            # Calcular totales
            total_added = movements[movements['movement_type'] == 'ENTRADA']['quantity'].sum()
            total_consumed_recorded = movements[movements['movement_type'] == 'SALIDA']['quantity'].sum()
            
            # Calcular consumo estimado por tiempo
            first_date = pd.to_datetime(movements.iloc[0]['created_at'])
            current_date = pd.Timestamp.now()
            hours_elapsed = (current_date - first_date).total_seconds() / 3600
            
            estimated_consumption = consumption_per_hour * hours_elapsed
            remaining = max(0, total_added - max(total_consumed_recorded, estimated_consumption))
            hours_remaining = remaining / consumption_per_hour if consumption_per_hour > 0 else 0
            
            # Determinar nivel
            if remaining <= 0:
                level = "critico"
                message = f"AGOTADO - {machine['name']}"
            elif hours_remaining <= 8:
                level = "critico"
                message = f"CRÍTICO: {hours_remaining:.1f}h restantes"
            elif hours_remaining <= 24:
                level = "malo"
                message = f"BAJO: {hours_remaining:.1f}h restantes"
            elif hours_remaining <= 72:
                level = "regular"
                message = f"REGULAR: {hours_remaining:.1f}h restantes"
            else:
                level = "ok"
                message = f"NORMAL: {hours_remaining:.1f}h restantes"
            
            return {
                "level": level,
                "remaining": remaining,
                "hours_remaining": hours_remaining,
                "total_added": total_added,
                "consumed": max(total_consumed_recorded, estimated_consumption),
                "message": message
            }
            
    except Exception as e:
        return {"level": "error", "message": f"Error: {str(e)}"}

def get_maintenance_status_by_hours_km(machine):
    """Obtiene estado de mantenimiento basado en horas y kilómetros"""
    try:
        current_hours = float(machine.get('current_hours', 0) or 0)
        current_odometer = float(machine.get('current_odometer', 0) or 0)
        interval_hours = machine.get('maintenance_interval_hours')
        interval_km = machine.get('maintenance_interval_km')
        
        # Si no hay intervalos definidos
        if not interval_hours and not interval_km:
            return {"status": "sin_configurar", "message": "Intervalos de mantenimiento no configurados"}
        
        status_by_hours = "ok"
        status_by_km = "ok"
        message_parts = []
        
        # Verificar por horas
        if interval_hours and interval_hours > 0:
            hours_since_last = current_hours  # Simplificado, debería obtener desde último mantenimiento
            if hours_since_last >= interval_hours:
                status_by_hours = "vencido"
                message_parts.append(f"Mantenimiento vencido por horas ({hours_since_last:.0f}/{interval_hours:.0f})")
            elif hours_since_last >= interval_hours * 0.9:
                status_by_hours = "critico"
                message_parts.append(f"Mantenimiento próximo por horas ({hours_since_last:.0f}/{interval_hours:.0f})")
        
        # Verificar por kilómetros
        if interval_km and interval_km > 0:
            km_since_last = current_odometer  # Simplificado
            if km_since_last >= interval_km:
                status_by_km = "vencido"
                message_parts.append(f"Mantenimiento vencido por km ({km_since_last:.0f}/{interval_km:.0f})")
            elif km_since_last >= interval_km * 0.9:
                status_by_km = "critico"
                message_parts.append(f"Mantenimiento próximo por km ({km_since_last:.0f}/{interval_km:.0f})")
        
        # Determinar estado más crítico
        priority = {"vencido": 0, "critico": 1, "advertencia": 2, "ok": 3}
        final_status = min([status_by_hours, status_by_km], key=lambda x: priority.get(x, 10))
        
        return {
            "status": final_status,
            "message": "; ".join(message_parts) if message_parts else "Mantenimiento al día"
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error calculando mantenimiento: {str(e)}"}

# Funciones auxiliares adicionales para compatibilidad

def get_alert_configuration(company_id, config_type, config_key, default_value):
    """Obtiene configuración de alertas - FUNCIÓN CORREGIDA"""
    try:
        with get_conn() as conn:
            result = pd.read_sql_query("""
                SELECT config_value FROM alert_configurations 
                WHERE company_id = ? AND config_type = ? AND config_key = ?
            """, conn, params=(company_id, config_type, config_key))
            
            if not result.empty:
                return result.iloc[0]['config_value']
            else:
                # Si no existe, crear con valor por defecto
                conn.execute("""
                    INSERT OR IGNORE INTO alert_configurations 
                    (company_id, config_type, config_key, config_value)
                    VALUES (?, ?, ?, ?)
                """, (company_id, config_type, config_key, str(default_value)))
                conn.commit()
                return default_value
                
    except Exception as e:
        print(f"Error obteniendo configuración de alerta: {str(e)}")
        return default_value

def set_alert_configuration(company_id, config_type, config_key, config_value):
    """Establece configuración de alertas"""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO alert_configurations 
                (company_id, config_type, config_key, config_value)
                VALUES (?, ?, ?, ?)
            """, (company_id, config_type, config_key, str(config_value)))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error estableciendo configuración de alerta: {str(e)}")
        return False

def update_tank_level(company_id, fluid_type_id, amount_change):
    """Actualiza el nivel de un tanque específico"""
    try:
        with get_conn() as conn:
            # Obtener información del tanque
            tank_info = pd.read_sql_query("""
                SELECT id, current_level, tank_capacity, unit
                FROM company_fluid_tanks
                WHERE company_id = ? AND fluid_type_id = ?
            """, conn, params=(company_id, fluid_type_id))
            
            if tank_info.empty:
                return False
            
            tank = tank_info.iloc[0]
            new_level = float(tank['current_level']) + float(amount_change)
            
            # Validar límites
            if new_level < 0:
                new_level = 0
            elif new_level > tank['tank_capacity']:
                new_level = tank['tank_capacity']
            
            # Actualizar
            conn.execute("""
                UPDATE company_fluid_tanks 
                SET current_level = ?
                WHERE id = ?
            """, (new_level, tank['id']))
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Error actualizando nivel de tanque: {str(e)}")
        return False

def migrate_alert_configurations():
    """Migra configuraciones de alertas para agregar company_id faltante"""
    try:
        with get_conn() as conn:
            # Verificar si la columna company_id existe
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(alert_configurations)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'company_id' not in columns:
                # Agregar columna company_id
                cursor.execute("ALTER TABLE alert_configurations ADD COLUMN company_id INTEGER")
                
                # Actualizar registros existentes con company_id = 1 por defecto
                cursor.execute("UPDATE alert_configurations SET company_id = 1 WHERE company_id IS NULL")
                
                # Crear foreign key constraint (recrear tabla si es necesario)
                cursor.execute("""
                    CREATE TABLE alert_configurations_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL,
                        config_type TEXT NOT NULL,
                        config_key TEXT NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                        UNIQUE(company_id, config_type, config_key)
                    )
                """)
                
                # Copiar datos existentes
                cursor.execute("""
                    INSERT INTO alert_configurations_new 
                    SELECT id, company_id, config_type, config_key, config_value, created_at
                    FROM alert_configurations
                """)
                
                # Reemplazar tabla
                cursor.execute("DROP TABLE alert_configurations")
                cursor.execute("ALTER TABLE alert_configurations_new RENAME TO alert_configurations")
                
                conn.commit()
                print("Migración de alert_configurations completada")
                
        return True
    except Exception as e:
        print(f"Error en migración de alert_configurations: {str(e)}")
        return False

def setup_company_tank(empresa_id, fluid_type_id, capacity, unit='galones'):
    """Configura un tanque específico para una empresa"""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO company_fluid_tanks 
                (company_id, fluid_type_id, tank_capacity, current_level, unit)
                VALUES (?, ?, ?, 0.0, ?)
            """, (empresa_id, fluid_type_id, capacity, unit))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error configurando tanque: {str(e)}")
        return False
    
def init_controles_db():
    """Inicializa las tablas necesarias para el sistema de inventario de fluidos"""
    try:
        # Configurar WAL ANTES de cualquier transacción
        with get_conn() as conn:
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA busy_timeout=30000;")  # 30 segundos timeout
                conn.commit()
            except Exception as e:
                print(f"Advertencia configurando WAL: {e}")
        
        # Ahora crear tablas en una sola transacción
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Tabla para tipos de fluidos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fluid_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    unit_type TEXT DEFAULT 'volume',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Tabla para tanques de fluidos por empresa
            cur.execute("""
                CREATE TABLE IF NOT EXISTS company_fluid_tanks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER,
                    fluid_type_id INTEGER,
                    tank_capacity REAL NOT NULL,
                    current_level REAL DEFAULT 0.0,
                    unit TEXT DEFAULT 'galones',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    FOREIGN KEY (fluid_type_id) REFERENCES fluid_types(id),
                    UNIQUE(company_id, fluid_type_id)
                );
            """)
            
            # Tabla unificada para movimientos de inventario
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fluid_inventory_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tank_id INTEGER NOT NULL,
                    movement_type TEXT NOT NULL CHECK(movement_type IN ('ENTRADA', 'SALIDA')),
                    quantity REAL NOT NULL,
                    unit_cost REAL,
                    total_cost REAL,
                    machinery_id INTEGER,
                    supplier TEXT,
                    operator TEXT,
                    reference_number TEXT,
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tank_id) REFERENCES company_fluid_tanks(id) ON DELETE CASCADE,
                    FOREIGN KEY (machinery_id) REFERENCES machinery(id)
                );
            """)
            
            # Tabla para configuraciones de empresa
            cur.execute("""
                CREATE TABLE IF NOT EXISTS company_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER,
                    setting_key TEXT NOT NULL,
                    setting_value TEXT NOT NULL,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    UNIQUE(company_id, setting_key)
                );
            """)
            
            # Tabla para configuraciones de alertas
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alert_configurations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    config_type TEXT NOT NULL,
                    config_key TEXT NOT NULL,
                    config_value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                    UNIQUE(company_id, config_type, config_key)
                );
            """)
            
            # Recrear tabla odometer_logs con estructura correcta
            try:
                # Primero verificar estructura actual
                cur.execute("PRAGMA table_info(odometer_logs)")
                existing_columns = [col[1] for col in cur.fetchall()]
                
                if existing_columns:
                    # La tabla existe, verificar si tiene la estructura correcta
                    expected_columns = {'machinery_id', 'current_odometer', 'recorded_at', 'recorded_by', 'notes'}
                    current_columns = set(existing_columns)
                    
                    if not expected_columns.issubset(current_columns):
                        print("Recreando tabla odometer_logs con estructura correcta...")
                        # Respaldar datos existentes si los hay
                        cur.execute("CREATE TEMPORARY TABLE odometer_logs_backup AS SELECT * FROM odometer_logs")
                        cur.execute("DROP TABLE odometer_logs")
                
                # Crear tabla con estructura correcta
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS odometer_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machinery_id INTEGER NOT NULL,
                        current_odometer REAL NOT NULL,
                        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        recorded_by TEXT,
                        notes TEXT,
                        FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE
                    )
                """)
                
                print("Tabla odometer_logs creada/actualizada correctamente")
                
            except sqlite3.OperationalError as e:
                print(f"Advertencia con odometer_logs: {e}")
                # Si hay problemas, crear tabla simple sin foreign key
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS odometer_logs_simple (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machinery_id INTEGER NOT NULL,
                        current_odometer REAL NOT NULL,
                        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        recorded_by TEXT,
                        notes TEXT
                    )
                """)
            
            # Migración de columnas en machinery si no existen
            try:
                cur.execute("PRAGMA table_info(machinery)")
                columns = [col[1] for col in cur.fetchall()]
                
                missing_columns = {
                    'consumption_per_hour': 'REAL DEFAULT 0.0',
                    'current_odometer': 'REAL DEFAULT 0.0',
                    'maintenance_interval_hours': 'REAL',
                    'maintenance_interval_km': 'REAL',
                    'current_hours': 'REAL DEFAULT 0.0'
                }
                
                for col_name, col_def in missing_columns.items():
                    if col_name not in columns:
                        cur.execute(f"ALTER TABLE machinery ADD COLUMN {col_name} {col_def};")
                        
            except sqlite3.OperationalError as e:
                print(f"Advertencia en migración machinery: {e}")
            
            # Migración de company_id en alert_configurations
            try:
                cur.execute("PRAGMA table_info(alert_configurations)")
                columns = [col[1] for col in cur.fetchall()]
                if 'company_id' not in columns:
                    cur.execute("ALTER TABLE alert_configurations ADD COLUMN company_id INTEGER")
                    cur.execute("UPDATE alert_configurations SET company_id = 1 WHERE company_id IS NULL")
            except sqlite3.OperationalError as e:
                print(f"Advertencia en migración alert_configurations: {e}")
            
            # Insertar tipos de fluidos por defecto
            default_fluids = [
                ("Combustible", "volume"),
                ("Aceite", "volume"),
                ("Grasa", "volume"),
                ("Coolant", "volume")
            ]
            
            for name, unit_type in default_fluids:
                cur.execute("INSERT OR IGNORE INTO fluid_types (name, unit_type) VALUES (?, ?)", (name, unit_type))
            
            # Crear vista unificada de maquinaria
            try:
                cur.execute("""
                    CREATE VIEW IF NOT EXISTS machinery_unified AS
                    SELECT 
                        id,
                        name,
                        identifier,
                        classification,
                        status,
                        COALESCE(current_hours, 0) AS current_hours,
                        COALESCE(current_odometer, 0) AS current_km,
                        COALESCE(current_odometer, 0) AS current_odometer,
                        last_maintenance_date,
                        last_maintenance_hours,
                        last_maintenance_km,
                        last_status_change,
                        company_id
                    FROM machinery;
                """)
            except Exception as e:
                print(f"Error creando vista machinery_unified: {e}")

            # Commit de toda la transacción
            conn.commit()
            
    except Exception as e:
        print(f"Error inicializando base de datos: {e}")
        raise

def crear_tanque_empresa(empresa_id, fluid_type_id, capacidad, unidad='galones'):
    """Crea un tanque específico para una empresa"""
    try:
        from db_utils import create_company_tank
        return create_company_tank(empresa_id, fluid_type_id, capacidad, unidad)
    except Exception as e:
        return False, f"Error creando tanque: {str(e)}"
    
def eliminar_tanque_empresa(empresa_id, tank_id):
    """Elimina un tanque específico de una empresa"""
    try:
        from db_utils import delete_company_tank
        return delete_company_tank(empresa_id, tank_id)
    except Exception as e:
        return False, f"Error eliminando tanque: {str(e)}"
    
def get_available_fluid_types_for_company(empresa_id):
    """Obtiene tipos de fluidos disponibles para crear"""
    try:
        from db_utils import get_available_fluid_types_for_company as get_available
        return get_available(empresa_id)
    except Exception as e:
        print(f"Error obteniendo tipos disponibles: {e}")
        return pd.DataFrame()
    
def mostrar_historial_despachos_filtrado(empresa_id, filtro_maquina, filtro_fluido, dias, unit_preference):
    """Muestra historial de despachos con filtros aplicados"""
    try:
        from datetime import date, timedelta
        
        fecha_limite = (date.today() - timedelta(days=dias)).isoformat()
        
        with get_conn() as conn:
            # Construir query con filtros
            query = """
                SELECT 
                    fim.created_at as fecha,
                    m.name as maquina,
                    m.identifier as matricula,
                    ft.name as fluido,
                    fim.quantity as cantidad,
                    cft.unit,
                    fim.operator as operador,
                    fim.notes as notas
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                LEFT JOIN machinery m ON fim.machinery_id = m.id
                WHERE cft.company_id = ? 
                AND fim.movement_type = 'SALIDA'
                AND DATE(fim.created_at) >= ?
            """
            params = [empresa_id, fecha_limite]
            
            # Aplicar filtros
            if filtro_maquina != "Todas":
                maquina_nombre = filtro_maquina.split(" (")[0]  # Extraer solo el nombre
                query += " AND m.name = ?"
                params.append(maquina_nombre)
            
            if filtro_fluido != "Todos":
                query += " AND ft.name = ?"
                params.append(filtro_fluido)
            
            query += " ORDER BY fim.created_at DESC LIMIT 50"
            
            historial = pd.read_sql_query(query, conn, params=params)
        
        if not historial.empty:
            # Mostrar como tabla expandible
            with st.expander(f"📋 {len(historial)} despachos encontrados", expanded=True):
                # Formatear datos para mejor visualización
                historial_display = historial.copy()
                historial_display['fecha'] = pd.to_datetime(historial_display['fecha']).dt.strftime('%d/%m/%Y %H:%M')
                historial_display['cantidad_fmt'] = historial_display.apply(
                    lambda row: f"{row['cantidad']:.1f} {row['unit']}", axis=1
                )
                
                # Seleccionar columnas para mostrar
                columns_to_show = ['fecha', 'maquina', 'matricula', 'fluido', 'cantidad_fmt', 'operador']
                display_names = ['Fecha', 'Máquina', 'Matrícula', 'Fluido', 'Cantidad', 'Operador']
                
                historial_clean = historial_display[columns_to_show].copy()
                historial_clean.columns = display_names
                
                st.dataframe(
                    historial_clean, 
                    use_container_width=True,
                    hide_index=True
                )
            
            # Estadísticas rápidas
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_cantidad = historial['cantidad'].sum()
                st.metric("Total Despachado", f"{total_cantidad:.1f} {unit_preference}")
            
            with col2:
                num_maquinas = historial['maquina'].nunique()
                st.metric("Máquinas Atendidas", num_maquinas)
            
            with col3:
                promedio_despacho = historial['cantidad'].mean()
                st.metric("Promedio por Despacho", f"{promedio_despacho:.1f} {unit_preference}")
        
        else:
            st.info("No se encontraron despachos con los filtros aplicados")
            
    except Exception as e:
        st.error(f"Error cargando historial: {str(e)}")

def get_machine_current_values(machinery_id):
    """Obtiene los valores actuales de horas y odómetro de una máquina"""
    try:
        with get_conn() as conn:
            result = pd.read_sql_query("""
                SELECT 
                    COALESCE(current_hours, 0) as current_hours, 
                    COALESCE(current_odometer, 0) as current_odometer
                FROM machinery 
                WHERE id = ?
            """, conn, params=(machinery_id,))
            
            if not result.empty:
                return {
                    'current_hours': float(result.iloc[0]['current_hours']),
                    'current_odometer': float(result.iloc[0]['current_odometer'])
                }
            return {'current_hours': 0, 'current_odometer': 0}
    except Exception as e:
        print(f"Error getting machine values: {e}")
        return {'current_hours': 0, 'current_odometer': 0}
    
def procesar_entrada_inventario(tank_id, cantidad, costo_unitario, proveedor, referencia, notas, usuario):
    """Procesa una entrada de inventario - FUNCIÓN COMPLETA"""
    try:
        with get_conn() as conn:
            # Configurar timeout
            conn.execute("PRAGMA busy_timeout=30000")
            
            # Validar que el tanque existe y obtener información
            tank_info = pd.read_sql_query("""
                SELECT id, tank_capacity, current_level, unit
                FROM company_fluid_tanks
                WHERE id = ?
            """, conn, params=(tank_id,))
            
            if tank_info.empty:
                return False, "Tanque no encontrado"
            
            tank = tank_info.iloc[0]
            new_level = float(tank['current_level']) + float(cantidad)
            
            if new_level > float(tank['tank_capacity']):
                available = float(tank['tank_capacity']) - float(tank['current_level'])
                return False, f"Excede la capacidad. Disponible: {available:.1f} {tank['unit']}"
            
            # Iniciar transacción
            conn.execute("BEGIN IMMEDIATE")
            
            try:
                # Actualizar nivel del tanque
                conn.execute("""
                    UPDATE company_fluid_tanks 
                    SET current_level = ?
                    WHERE id = ?
                """, (new_level, tank_id))
                
                # Registrar movimiento de entrada
                total_cost = float(cantidad) * float(costo_unitario) if costo_unitario > 0 else None
                
                conn.execute("""
                    INSERT INTO fluid_inventory_movements 
                    (tank_id, movement_type, quantity, unit_cost, total_cost, supplier, 
                     reference_number, notes, created_by)
                    VALUES (?, 'ENTRADA', ?, ?, ?, ?, ?, ?, ?)
                """, (tank_id, cantidad, costo_unitario if costo_unitario > 0 else None, 
                     total_cost, proveedor, referencia, notas, usuario))
                
                conn.commit()
                return True, f"Entrada registrada. Nuevo nivel: {new_level:.1f} {tank['unit']}"
                
            except Exception as e:
                conn.rollback()
                raise e
                
    except Exception as e:
        return False, f"Error al procesar entrada: {str(e)}"

# FUNCIÓN ADICIONAL QUE FALTABA
def procesar_salida_inventario(tank_id, machine_id, cantidad, operador, horas, odometro, notas, usuario):
    """Procesa una salida de inventario - FUNCIÓN COMPLETA"""
    try:
        with get_conn() as conn:
            # Configurar timeout para esta conexión
            conn.execute("PRAGMA busy_timeout=30000")
            
            # 1. Validar disponibilidad del tanque
            tank_info = pd.read_sql_query("""
                SELECT id, current_level, unit
                FROM company_fluid_tanks
                WHERE id = ?
            """, conn, params=(tank_id,))
            
            if tank_info.empty:
                return False, "Tanque no encontrado"
            
            tank = tank_info.iloc[0]
            current_level = float(tank['current_level'])

            if current_level < float(cantidad):
                return False, f"Inventario insuficiente. Disponible: {current_level:.1f} {tank['unit']}"
            
            # 2. Iniciar transacción explícita
            conn.execute("BEGIN IMMEDIATE")
            
            try:
                new_level = current_level - float(cantidad)
                
                # 3. Actualizar nivel del tanque
                conn.execute("""
                    UPDATE company_fluid_tanks 
                    SET current_level = ?
                    WHERE id = ?
                """, (new_level, tank_id))
                
                # 4. Registrar movimiento de salida
                conn.execute("""
                    INSERT INTO fluid_inventory_movements 
                    (tank_id, movement_type, quantity, machinery_id, operator, notes, created_by)
                    VALUES (?, 'SALIDA', ?, ?, ?, ?, ?)
                """, (tank_id, cantidad, machine_id, operador, notas, usuario))
                
                # 5. Actualizar odómetro si se proporcionó
                if odometro > 0:
                    # Obtener valor actual y validar
                    cursor = conn.cursor()
                    cursor.execute("SELECT current_odometer FROM machinery WHERE id = ?", (machine_id,))
                    result = cursor.fetchone()
                    
                    if result:
                        current_odometer = result[0] if result[0] else 0
                        
                        # Solo actualizar si el nuevo valor es mayor o igual
                        if odometro >= current_odometer:
                            cursor.execute("""
                                UPDATE machinery 
                                SET current_odometer = ?, last_odometer_update = CURRENT_TIMESTAMP 
                                WHERE id = ?
                            """, (odometro, machine_id))
                            
                            # Registrar en log si la tabla existe
                            try:
                                cursor.execute("""
                                    INSERT INTO odometer_logs (machinery_id, current_odometer, recorded_by, recorded_at)
                                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                                """, (machine_id, odometro, usuario))
                            except:
                                pass  # La tabla puede no existir
                
                # 6. Actualizar horómetro si se proporcionó
                if horas > 0:
                    conn.execute("""
                        UPDATE machinery 
                        SET current_hours = current_hours + ?
                        WHERE id = ?
                    """, (horas, machine_id))
                
                # 7. Commit de toda la transacción
                conn.commit()
                return True, f"Despacho realizado. Nivel restante: {new_level:.1f} {tank['unit']}"
                
            except Exception as e:
                conn.rollback()
                raise e
                
    except Exception as e:
        return False, f"Error al procesar despacho: {str(e)}"
    
def get_machine_fluid_status_enhanced(machinery_id, fluid_type_id, unit_preference, empresa_id):
    """Versión mejorada que usa configuración individual de tanques para alertas"""
    try:
        with get_conn() as conn:
            # Obtener información de la máquina
            machine_info = pd.read_sql_query("""
                SELECT consumption_per_hour, current_hours, name, identifier, company_id
                FROM machinery WHERE id = ?
            """, conn, params=(machinery_id,))
            
            if machine_info.empty:
                return {"level": "error", "message": "Máquina no encontrada"}
            
            machine = machine_info.iloc[0]
            consumption_per_hour = machine.get('consumption_per_hour', 0) or 0
            
            if consumption_per_hour <= 0:
                return {"level": "sin_datos", "message": "Consumo no definido"}
            
            # Obtener tanque de este tipo de fluido para la empresa
            tank_info = pd.read_sql_query("""
                SELECT cft.id as tank_id FROM company_fluid_tanks cft
                WHERE cft.company_id = ? AND cft.fluid_type_id = ?
            """, conn, params=(empresa_id, fluid_type_id))
            
            if tank_info.empty:
                return {"level": "sin_datos", "message": "Tanque no configurado"}
            
            tank_id = tank_info.iloc[0]['tank_id']
            
            # Obtener movimientos de este fluido para esta máquina
            movements = pd.read_sql_query("""
                SELECT fim.movement_type, fim.quantity, fim.created_at
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                WHERE fim.machinery_id = ? AND cft.fluid_type_id = ?
                ORDER BY fim.created_at ASC
            """, conn, params=(machinery_id, fluid_type_id))
            
            if movements.empty:
                return {"level": "sin_datos", "message": "No hay registros de este fluido"}
            
            # Calcular totales
            total_added = movements[movements['movement_type'] == 'ENTRADA']['quantity'].sum()
            total_consumed_recorded = movements[movements['movement_type'] == 'SALIDA']['quantity'].sum()
            
            # Calcular consumo estimado por tiempo
            first_date = pd.to_datetime(movements.iloc[0]['created_at'])
            current_date = pd.Timestamp.now()
            hours_elapsed = (current_date - first_date).total_seconds() / 3600
            
            estimated_consumption = consumption_per_hour * hours_elapsed
            remaining = max(0, total_added - max(total_consumed_recorded, estimated_consumption))
            hours_remaining = remaining / consumption_per_hour if consumption_per_hour > 0 else 0
            
            # Obtener umbrales configurados para este tanque (individual o global)
            thresholds = get_tank_alert_thresholds_safe(tank_id, empresa_id)
            
            # Calcular porcentaje basado en la última recarga
            last_refill = movements[movements['movement_type'] == 'ENTRADA']['quantity'].iloc[-1] if not movements[movements['movement_type'] == 'ENTRADA'].empty else 0
            percentage_remaining = (remaining / last_refill * 100) if last_refill > 0 else 0
            
            # Determinar nivel usando configuración personalizada (solo 3 niveles)
            if remaining <= 0:
                level = "critico"
                message = f"AGOTADO - {machine['name']}"
            elif percentage_remaining <= thresholds['critical']:
                level = "critico"
                message = f"CRÍTICO: {hours_remaining:.1f}h restantes ({percentage_remaining:.1f}%)"
            elif percentage_remaining <= thresholds['low']:
                level = "bajo"
                message = f"BAJO: {hours_remaining:.1f}h restantes ({percentage_remaining:.1f}%)"
            else:
                level = "normal"
                message = f"NORMAL: {hours_remaining:.1f}h restantes ({percentage_remaining:.1f}%)"
            
            return {
                "level": level,
                "remaining": remaining,
                "hours_remaining": hours_remaining,
                "total_added": total_added,
                "consumed": max(total_consumed_recorded, estimated_consumption),
                "message": message,
                "percentage": percentage_remaining,
                "thresholds_used": thresholds
            }
            
    except Exception as e:
        return {"level": "error", "message": f"Error: {str(e)}"}

def get_tank_alert_thresholds_safe(tank_id, empresa_id):
    """Obtiene umbrales de alerta para un tanque con fallback a configuración global"""
    try:
        # Importar función de configuración
        from controles_config import get_tank_alert_thresholds
        return get_tank_alert_thresholds(tank_id, empresa_id)
    except ImportError:
        # Fallback si no está disponible el módulo de configuración
        try:
            # Usar configuración global como fallback
            critico = float(get_alert_configuration(empresa_id, "fuel_levels", "critical_threshold", "10"))
            bajo = float(get_alert_configuration(empresa_id, "fuel_levels", "low_threshold", "25"))
            return {"critical": critico, "low": bajo, "source": "global_fallback"}
        except:
            # Valores por defecto como último recurso
            return {"critical": 10, "low": 25, "source": "default"}

def get_fluid_alerts_enhanced(empresa_id):
    """Versión mejorada de get_fluid_alerts usando configuraciones individuales"""
    alertas = []
    tanques = get_company_tanks(empresa_id)
    
    for _, tank in tanques.iterrows():
        try:
            # Obtener umbrales específicos para este tanque
            thresholds = get_tank_alert_thresholds_safe(tank['id'], empresa_id)
            percentage = calculate_tank_percentage(tank)
            
            # Aplicar lógica de 3 niveles usando configuración individual
            if percentage <= thresholds['critical']:
                alertas.append({
                    'level': 'critico',
                    'message': f"🚨 {tank['fluid_name']}: Nivel crítico {percentage:.1f}% (umbral: {thresholds['critical']}%)",
                    'tank_id': tank['id'],
                    'fluid_name': tank['fluid_name'],
                    'percentage': percentage
                })
            elif percentage <= thresholds['low']:
                alertas.append({
                    'level': 'bajo',
                    'message': f"⚠️ {tank['fluid_name']}: Nivel bajo {percentage:.1f}% (umbral: {thresholds['low']}%)",
                    'tank_id': tank['id'],
                    'fluid_name': tank['fluid_name'],
                    'percentage': percentage
                })
        except Exception as e:
            print(f"Error procesando alerta para tanque {tank.get('fluid_name', 'desconocido')}: {e}")
            continue
    
    return alertas

def mostrar_dashboard_fluidos_enhanced(empresa_id, unit_preference):
    """Dashboard mejorado que usa configuraciones individuales de tanques"""
    st.subheader("Estado del Inventario")
    
    tanques = get_company_tanks(empresa_id)
    
    if tanques.empty:
        st.info("🛢️ No hay tanques configurados para esta empresa")
        st.markdown("Vaya a la sección **'Tanques > Crear Tanque'** para configurar sus primeros tanques.")
        return
    
    # Métricas generales
    st.markdown("### Resumen de Tanques")
    total_capacity = tanques['tank_capacity'].sum()
    total_current = tanques['current_level'].sum()
    avg_percentage = (total_current / total_capacity * 100) if total_capacity > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Tanques Configurados", len(tanques))
    
    with col2:
        st.metric("Capacidad Total", f"{total_capacity:.0f} {unit_preference}")
    
    with col3:
        st.metric("Inventario Actual", f"{total_current:.1f} {unit_preference}")
    
    with col4:
        status_color = "🟢" if avg_percentage >= 70 else "🟡" if avg_percentage >= 40 else "🔴"
        st.metric("Nivel Promedio", f"{avg_percentage:.1f}%", delta=status_color)
    
    st.divider()
    
    # Estado individual de tanques con configuración personalizada
    st.markdown("### Estado Individual de Tanques")
    
    num_tanques = len(tanques)
    if num_tanques <= 4:
        cols = st.columns(num_tanques)
    else:
        cols = st.columns(4)
    
    for i, (_, tank) in enumerate(tanques.iterrows()):
        col_index = i % len(cols)
        with cols[col_index]:
            # Obtener configuración específica del tanque
            thresholds = get_tank_alert_thresholds_safe(tank['id'], empresa_id)
            percentage = calculate_tank_percentage(tank)
            
            # Determinar estado usando configuración individual
            if percentage <= thresholds['critical']:
                emoji = "🔴"
                status_text = "Crítico"
            elif percentage <= thresholds['low']:
                emoji = "🟡"
                status_text = "Bajo"
            else:
                emoji = "🟢"
                status_text = "Normal"
            
            st.metric(
                label=f"{emoji} {tank['fluid_name']}",
                value=f"{tank['current_level']:.1f} {unit_preference}",
                delta=f"{percentage:.1f}% - {status_text}",
                help=f"Umbrales: Crítico ≤{thresholds['critical']}%, Bajo ≤{thresholds['low']}%"
            )
            
            st.progress(percentage / 100, text=f"{percentage:.1f}% lleno")
            
            if (i + 1) % 4 == 0 and i + 1 < num_tanques:
                st.markdown("---")
    
    st.divider()
    
    # Alertas usando configuraciones individuales
    alertas = get_fluid_alerts_enhanced(empresa_id)
    if alertas:
        st.subheader("🚨 Alertas de Inventario")
        
        alertas_criticas = [a for a in alertas if a['level'] == 'critico']
        alertas_bajas = [a for a in alertas if a['level'] == 'bajo']
        
        if alertas_criticas:
            for alerta in alertas_criticas:
                st.error(alerta['message'])
        
        if alertas_bajas:
            for alerta in alertas_bajas:
                st.warning(alerta['message'])
        
        st.divider()
    
    # Resto del dashboard (sin cambios)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Movimientos Recientes")
        mostrar_movimientos_recientes(empresa_id, limit=8)
    
    with col2:
        st.subheader("📊 Resumen del Día")
        mostrar_resumen_despachos_hoy(empresa_id, unit_preference)

def init_controles_db_enhanced():
    """Versión mejorada de init_controles_db que incluye tabla de configuraciones por tanque"""
    # Llamar a la función original
    init_controles_db()
    
    # Agregar tabla de configuraciones por tanque
    try:
        with get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tank_configurations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tank_id INTEGER NOT NULL,
                    config_key TEXT NOT NULL,
                    config_value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tank_id) REFERENCES company_fluid_tanks(id) ON DELETE CASCADE,
                    UNIQUE(tank_id, config_key)
                )
            """)
            conn.commit()
        print("Tabla tank_configurations inicializada")
    except Exception as e:
        print(f"Error inicializando tabla tank_configurations: {e}")

# FUNCIÓN PARA MIGRAR CONFIGURACIONES EXISTENTES
def migrate_to_three_levels(empresa_id):
    """Migra configuraciones existentes de 5 niveles a 3 niveles"""
    try:
        with get_conn() as conn:
            # Obtener configuraciones actuales si existen
            existing_configs = pd.read_sql_query("""
                SELECT config_key, config_value FROM alert_configurations
                WHERE company_id = ? AND config_type = 'fuel_levels'
            """, conn, params=(empresa_id,))
            
            # Mapear valores existentes a los nuevos 3 niveles
            new_critical = 10
            new_low = 25
            
            if not existing_configs.empty:
                config_dict = dict(zip(existing_configs['config_key'], existing_configs['config_value']))
                
                # Si existe configuración anterior, adaptarla
                if 'critical_threshold' in config_dict:
                    new_critical = min(float(config_dict['critical_threshold']), 15)
                
                if 'low_threshold' in config_dict:
                    new_low = min(float(config_dict['low_threshold']), 35)
                elif 'bad_threshold' in config_dict:
                    new_low = min(float(config_dict['bad_threshold']), 35)
            
            # Establecer nuevas configuraciones
            set_alert_configuration(empresa_id, "fuel_levels", "critical_threshold", str(int(new_critical)))
            set_alert_configuration(empresa_id, "fuel_levels", "low_threshold", str(int(new_low)))
            
            # Eliminar configuraciones obsoletas
            obsolete_keys = ['bad_threshold', 'regular_threshold', 'excellent_threshold', 'good_threshold']
            for key in obsolete_keys:
                conn.execute("""
                    DELETE FROM alert_configurations 
                    WHERE company_id = ? AND config_type = 'fuel_levels' AND config_key = ?
                """, (empresa_id, key))
            
            conn.commit()
            
        print(f"Migración a 3 niveles completada para empresa {empresa_id}")
        return True
        
    except Exception as e:
        print(f"Error en migración a 3 niveles: {e}")
        return False

# FUNCIÓN WRAPPER PARA MANTENER COMPATIBILIDAD
def mostrar_controles_enhanced(empresa_id):
    """Versión mejorada de mostrar_controles con configuraciones individuales"""
    # Inicializar DB con nuevas características
    init_controles_db_enhanced()
    
    # Migrar a 3 niveles si es necesario
    migrate_to_three_levels(empresa_id)
    
    st.header("Sistema de Control de Fluidos")
    
    # Inicializar tanques si no existen
    initialize_company_tanks(empresa_id)
    
    # Obtener configuración de unidades
    unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
    
    # Pestañas principales
    tabs = st.tabs(["📊 General", "🛢️ Tanques", "🚛 Despachos", "📋 Historial", "🔧 Configuración"])
    
    with tabs[0]:
        # Usar dashboard mejorado con configuraciones individuales
        mostrar_dashboard_fluidos_enhanced(empresa_id, unit_preference)
    
    with tabs[1]:
        mostrar_gestion_tanques(empresa_id, unit_preference)
    
    with tabs[2]:
        mostrar_despachos_maquinaria(empresa_id, unit_preference)
    
    with tabs[3]:
        mostrar_historial_completo(empresa_id, unit_preference)
    
    with tabs[4]:
        try:
            from controles_config import mostrar_configuracion_controles
            mostrar_configuracion_controles(empresa_id)
        except ImportError:
            st.error("Módulo de configuración no encontrado")
        except Exception as e:
            st.error(f"Error en configuración: {str(e)}")

# FUNCIONES DE COMPATIBILIDAD PARA MANTENER LA FUNCIONALIDAD EXISTENTE

def get_fluid_alerts_compatible(empresa_id):
    """Wrapper que mantiene compatibilidad con la función original"""
    try:
        # Intentar usar la versión mejorada
        return get_fluid_alerts_enhanced(empresa_id)
    except:
        # Fallback a la función original
        return get_fluid_alerts(empresa_id)

def calculate_tank_status_with_config(tank, empresa_id):
    """Calcula el estado de un tanque usando su configuración individual"""
    try:
        percentage = calculate_tank_percentage(tank)
        thresholds = get_tank_alert_thresholds_safe(tank['id'], empresa_id)
        
        if percentage <= thresholds['critical']:
            return "critico"
        elif percentage <= thresholds['low']:
            return "bajo"
        else:
            return "normal"
    except:
        # Fallback a lógica simple
        percentage = calculate_tank_percentage(tank)
        if percentage <= 10:
            return "critico"
        elif percentage <= 25:
            return "bajo"
        else:
            return "normal"
        
def get_tank_alert_thresholds(tank_id, empresa_id):
    """Obtiene umbrales de alerta específicos de un tanque o usa valores predeterminados de la empresa"""
    try:
        # Importar funciones de db_utils
        from db_utils import get_tank_alert_configuration
        
        # Intentar obtener configuración específica del tanque
        critical = get_tank_alert_configuration(tank_id, "critical_threshold", None)
        low = get_tank_alert_configuration(tank_id, "low_threshold", None)
        
        # Si no hay configuración específica, usar valores predeterminados de la empresa
        if critical is None:
            critical = get_alert_configuration(empresa_id, "fuel_levels", "critical_threshold", "10")
        
        if low is None:
            low = get_alert_configuration(empresa_id, "fuel_levels", "low_threshold", "25")
        
        return {
            "critical": float(critical),
            "low": float(low),
            "source": "individual" if critical is not None and low is not None else "empresa_default"
        }
        
    except Exception as e:
        print(f"Error obteniendo umbrales de tanque {tank_id}: {e}")
        # Valores por defecto como último recurso
        return {"critical": 10, "low": 25, "source": "system_default"}

# AGREGA esta nueva función a controles_module.py:

def mostrar_alertas_modernas(alertas):
    """Muestra alertas con diseño moderno usando componentes de Streamlit"""
    if not alertas:
        # Mostrar estado positivo cuando no hay alertas
        st.success("✅ Todos los tanques están en niveles normales")
        return
    
    st.subheader("🚨 Centro de Alertas")
    
    # Separar alertas por nivel
    alertas_criticas = [a for a in alertas if a['level'] == 'critico']
    alertas_bajas = [a for a in alertas if a['level'] == 'bajo']
    
    # Contenedor principal con estilo
    with st.container():
        # Alertas críticas con diseño destacado
        if alertas_criticas:
            st.markdown("### 🔴 Alertas Críticas")
            for alerta in alertas_criticas:
                with st.container():
                    col1, col2, col3 = st.columns([1, 6, 1])
                    
                    with col1:
                        st.markdown("🚨")
                    
                    with col2:
                        st.error(f"**{alerta['fluid_name']}**: {alerta['percentage']:.1f}% restante")
                        
                    with col3:
                        # Botón para configurar este tanque específico
                        if st.button("⚙️", key=f"config_critical_{alerta.get('tank_id', '')}"):
                            st.session_state[f"show_tank_config_{alerta['tank_id']}"] = True
        
        # Separador visual
        if alertas_criticas and alertas_bajas:
            st.divider()
        
        # Alertas de nivel bajo con diseño menos intrusivo
        if alertas_bajas:
            st.markdown("### 🟡 Alertas de Nivel Bajo")
            for alerta in alertas_bajas:
                with st.container():
                    col1, col2, col3 = st.columns([1, 6, 1])
                    
                    with col1:
                        st.markdown("⚠️")
                    
                    with col2:
                        st.warning(f"**{alerta['fluid_name']}**: {alerta['percentage']:.1f}% restante")
                        
                    
                    with col3:
                        # Botón para configurar este tanque específico
                        if st.button("⚙️", key=f"config_low_{alerta.get('tank_id', '')}"):
                            st.session_state[f"show_tank_config_{alerta['tank_id']}"] = True
    
def mostrar_configuracion_alertas_tanque(tank_id, empresa_id):
    """Muestra interfaz para configurar alertas específicas de un tanque"""
    try:
        # Obtener información del tanque
        from db_utils import get_tank_with_fluid_info
        tank_info = get_tank_with_fluid_info(tank_id)
        
        if tank_info.empty:
            st.error("Tanque no encontrado")
            return
        
        tank = tank_info.iloc[0]
        
        st.subheader(f"⚙️ Configuración de Alertas - {tank['fluid_name']}")
        
        # Obtener configuración actual
        current_thresholds = get_tank_alert_thresholds(tank_id, empresa_id)
        
        # Mostrar origen de la configuración actual
        if current_thresholds['source'] == 'individual':
            st.info("🎯 Este tanque tiene configuración personalizada")
        else:
            st.info("📋 Este tanque usa la configuración predeterminada de la empresa")
        
        with st.form(f"config_tank_{tank_id}"):
            st.markdown("### Umbrales de Alerta")
            
            col1, col2 = st.columns(2)
            
            with col1:
                critical_threshold = st.slider(
                    "🔴 Umbral Crítico (%)",
                    min_value=1,
                    max_value=30,
                    value=int(current_thresholds['critical']),
                    help="Porcentaje por debajo del cual se considera crítico"
                )
            
            with col2:
                low_threshold = st.slider(
                    "🟡 Umbral Bajo (%)",
                    min_value=critical_threshold + 1,
                    max_value=50,
                    value=int(current_thresholds['low']),
                    help="Porcentaje por debajo del cual se considera bajo"
                )
            
            # Vista previa
            st.markdown("### Vista Previa")
            current_percentage = calculate_tank_percentage(tank)
            
            col_preview1, col_preview2, col_preview3 = st.columns(3)
            
            with col_preview1:
                if current_percentage <= critical_threshold:
                    st.error(f"🚨 CRÍTICO: {current_percentage:.1f}%")
                elif current_percentage <= low_threshold:
                    st.warning(f"⚠️ BAJO: {current_percentage:.1f}%")
                else:
                    st.success(f"✅ NORMAL: {current_percentage:.1f}%")
            
            with col_preview2:
                st.metric("Nivel Actual", f"{tank['current_level']:.1f} {tank['unit']}")
            
            with col_preview3:
                st.metric("Capacidad", f"{tank['tank_capacity']:.1f} {tank['unit']}")
            
            # Botones de acción
            col_save, col_reset = st.columns(2)
            
            with col_save:
                if st.form_submit_button("💾 Guardar Configuración", type="primary"):
                    try:
                        from db_utils import set_tank_alert_configuration
                        
                        # Guardar configuración específica del tanque
                        success1 = set_tank_alert_configuration(tank_id, "critical_threshold", str(critical_threshold))
                        success2 = set_tank_alert_configuration(tank_id, "low_threshold", str(low_threshold))
                        
                        if success1 and success2:
                            st.success("✅ Configuración guardada correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar configuración")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            
            with col_reset:
                if st.form_submit_button("🔄 Usar Predeterminado"):
                    try:
                        # Eliminar configuración específica para usar la predeterminada
                        with get_conn() as conn:
                            conn.execute("""
                                DELETE FROM tank_configurations 
                                WHERE tank_id = ? AND config_key IN ('critical_threshold', 'low_threshold')
                            """, (tank_id,))
                            conn.commit()
                        
                        st.success("✅ Configuración restablecida a valores predeterminados")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        
        # Mostrar configuración predeterminada de la empresa
        st.divider()
        with st.expander("📋 Ver Configuración Predeterminada de la Empresa"):
            default_critical = get_alert_configuration(empresa_id, "fuel_levels", "critical_threshold", "10")
            default_low = get_alert_configuration(empresa_id, "fuel_levels", "low_threshold", "25")
            
            col_def1, col_def2 = st.columns(2)
            with col_def1:
                st.metric("Crítico Predeterminado", f"{default_critical}%")
            with col_def2:
                st.metric("Bajo Predeterminado", f"{default_low}%")
                
    except Exception as e:

        st.error(f"Error mostrando configuración: {str(e)}")



