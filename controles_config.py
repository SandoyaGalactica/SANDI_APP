import streamlit as st
import pandas as pd
from db_utils import get_conn, get_company_tanks
import sqlite3
import time

def get_fluid_types():
    """Obtiene todos los tipos de fluidos disponibles"""
    with get_conn() as conn:
        return pd.read_sql_query("SELECT * FROM fluid_types ORDER BY name", conn)

def get_company_setting(company_id, key, default_value):
    """Obtiene un valor de configuración para una empresa"""
    with get_conn() as conn:
        result = pd.read_sql_query("""
            SELECT setting_value FROM company_settings 
            WHERE company_id = ? AND setting_key = ?
        """, conn, params=(company_id, key))
        if not result.empty:
            return result.iloc[0]['setting_value']
        return default_value

def set_company_setting(company_id, key, value):
    """Establece un valor de configuración para una empresa"""
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO company_settings (company_id, setting_key, setting_value)
            VALUES (?, ?, ?)
        """, (company_id, key, str(value)))
        conn.commit()

def delete_fluid_type(fluid_id):
    """Elimina un tipo de fluido si no está en uso"""
    with get_conn() as conn:
        # Verificar si el fluido está en uso por algún tanque
        tanque_asociado = pd.read_sql_query("""
            SELECT * FROM company_fluid_tanks 
            WHERE fluid_type_id = ?
        """, conn, params=(fluid_id,))
        
        if not tanque_asociado.empty:
            return False, "No se puede eliminar el tipo de fluido porque está asociado a un tanque"
        
        # Si no está en uso, proceder a eliminar
        conn.execute("DELETE FROM fluid_types WHERE id = ?", (fluid_id,))
        conn.commit()
        return True, "Tipo de fluido eliminado correctamente"

def add_fluid_type(name, unit_type):
    """Añade un nuevo tipo de fluido"""
    with get_conn() as conn:
        try:
            conn.execute("INSERT INTO fluid_types (name, unit_type) VALUES (?, ?)", (name, unit_type))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Ya existe

def setup_company_tank(company_id, fluid_type_id, capacity, unit_type):
    """Configura un tanque para una empresa y tipo de fluido"""
    with get_conn() as conn:
        # Verificar si ya existe un tanque para este tipo de fluido
        existing_tank = pd.read_sql_query("""
            SELECT * FROM company_fluid_tanks 
            WHERE company_id = ? AND fluid_type_id = ?
        """, conn, params=(company_id, fluid_type_id))
        
        if not existing_tank.empty:
            return False  # Ya existe un tanque configurado para este fluido
        
        # Si no existe, proceder a crear el tanque
        conn.execute("""
            INSERT INTO company_fluid_tanks (company_id, fluid_type_id, tank_capacity, current_level, unit)
            VALUES (?, ?, ?, 0.0, ?)
        """, (company_id, fluid_type_id, capacity, unit_type))
        conn.commit()
        return True

def update_tank_capacity(tank_id, new_capacity):
    """Actualiza la capacidad de un tanque"""
    with get_conn() as conn:
        conn.execute("""
            UPDATE company_fluid_tanks 
            SET tank_capacity = ? 
            WHERE id = ?
        """, (new_capacity, tank_id))
        conn.commit()

def get_alert_configuration(company_id, config_type, key, default_value):
    """Obtiene una configuración de alerta - CORREGIDA para manejar todas las estructuras"""
    with get_conn() as conn:
        try:
            # Verificar si la tabla existe
            table_exists = pd.read_sql_query("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='alert_configurations'
            """, conn)
            
            if table_exists.empty:
                # La tabla no existe, crearla con la estructura nueva
                conn.execute("""
                    CREATE TABLE alert_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL DEFAULT 1,
                        config_type TEXT NOT NULL DEFAULT 'system',
                        config_key TEXT NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(company_id, config_type, config_key)
                    )
                """)
                conn.commit()
                return default_value
            
            # Verificar la estructura de la tabla
            table_info = pd.read_sql_query("PRAGMA table_info(alert_configurations)", conn)
            columns = [col['name'] for col in table_info.to_dict('records')]
            
            if 'config_type' in columns and 'company_id' in columns and 'config_key' in columns:
                # Estructura nueva completa
                result = pd.read_sql_query("""
                    SELECT config_value FROM alert_configurations 
                    WHERE company_id = ? AND config_type = ? AND config_key = ?
                """, conn, params=(company_id, config_type, key))
            elif 'config_key' in columns and 'config_value' in columns:
                # Estructura antigua (solo config_key y config_value)
                result = pd.read_sql_query("""
                    SELECT config_value FROM alert_configurations 
                    WHERE config_key = ?
                """, conn, params=(key,))
            else:
                # Estructura desconocida o corrupta, recrear tabla
                conn.execute("DROP TABLE IF EXISTS alert_configurations")
                conn.execute("""
                    CREATE TABLE alert_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL DEFAULT 1,
                        config_type TEXT NOT NULL DEFAULT 'system',
                        config_key TEXT NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(company_id, config_type, config_key)
                    )
                """)
                conn.commit()
                return default_value
                
            if not result.empty:
                return result.iloc[0]['config_value']
            else:
                return default_value
                
        except sqlite3.OperationalError as e:
            # Error en la consulta, recrear tabla
            conn.execute("DROP TABLE IF EXISTS alert_configurations")
            conn.execute("""
                CREATE TABLE alert_configurations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL DEFAULT 1,
                    config_type TEXT NOT NULL DEFAULT 'system',
                    config_key TEXT NOT NULL,
                    config_value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_id, config_type, config_key)
                )
            """)
            conn.commit()
            return default_value

def update_alert_configuration(company_id, config_type, key, value):
    """Actualiza una configuración de alerta - CORREGIDA para manejar todas las estructuras"""
    with get_conn() as conn:
        try:
            # Verificar si la tabla existe
            table_exists = pd.read_sql_query("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='alert_configurations'
            """, conn)
            
            if table_exists.empty:
                # Crear tabla con estructura nueva
                conn.execute("""
                    CREATE TABLE alert_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL DEFAULT 1,
                        config_type TEXT NOT NULL DEFAULT 'system',
                        config_key TEXT NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(company_id, config_type, config_key)
                    )
                """)
                conn.commit()
            
            # Verificar la estructura de la tabla
            table_info = pd.read_sql_query("PRAGMA table_info(alert_configurations)", conn)
            columns = [col['name'] for col in table_info.to_dict('records')]
            
            if 'config_type' in columns and 'company_id' in columns and 'config_key' in columns:
                # Estructura nueva completa
                conn.execute("""
                    INSERT OR REPLACE INTO alert_configurations (company_id, config_type, config_key, config_value)
                    VALUES (?, ?, ?, ?)
                """, (company_id, config_type, key, str(value)))
            elif 'config_key' in columns and 'config_value' in columns:
                # Estructura antigua, usar migración
                migrate_alert_configurations()
                # Después de la migración, usar estructura nueva
                conn.execute("""
                    INSERT OR REPLACE INTO alert_configurations (company_id, config_type, config_key, config_value)
                    VALUES (?, ?, ?, ?)
                """, (company_id, config_type, key, str(value)))
            else:
                # Estructura desconocida, recrear tabla
                conn.execute("DROP TABLE IF EXISTS alert_configurations")
                conn.execute("""
                    CREATE TABLE alert_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL DEFAULT 1,
                        config_type TEXT NOT NULL DEFAULT 'system',
                        config_key TEXT NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(company_id, config_type, config_key)
                    )
                """)
                conn.execute("""
                    INSERT INTO alert_configurations (company_id, config_type, config_key, config_value)
                    VALUES (?, ?, ?, ?)
                """, (company_id, config_type, key, str(value)))
                
            conn.commit()
            
        except sqlite3.OperationalError as e:
            # Si hay cualquier error, recrear la tabla
            conn.execute("DROP TABLE IF EXISTS alert_configurations")
            conn.execute("""
                CREATE TABLE alert_configurations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL DEFAULT 1,
                    config_type TEXT NOT NULL DEFAULT 'system',
                    config_key TEXT NOT NULL,
                    config_value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_id, config_type, config_key)
                )
            """)
            conn.execute("""
                INSERT INTO alert_configurations (company_id, config_type, config_key, config_value)
                VALUES (?, ?, ?, ?)
            """, (company_id, config_type, key, str(value)))
            conn.commit()

def migrate_alert_configurations():
    """Migra la tabla alert_configurations a la nueva estructura - MEJORADA"""
    with get_conn() as conn:
        try:
            # Verificar si la tabla existe
            table_exists = pd.read_sql_query("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='alert_configurations'
            """, conn)
            
            if table_exists.empty:
                # Crear tabla con estructura nueva
                conn.execute("""
                    CREATE TABLE alert_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL DEFAULT 1,
                        config_type TEXT NOT NULL DEFAULT 'system',
                        config_key TEXT NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(company_id, config_type, config_key)
                    )
                """)
                conn.commit()
                return
            
            # Verificar estructura actual
            table_info = pd.read_sql_query("PRAGMA table_info(alert_configurations)", conn)
            columns = [col['name'] for col in table_info.to_dict('records')]
            
            # Si ya tiene la estructura nueva, no hacer nada
            if 'config_type' in columns and 'company_id' in columns and 'config_key' in columns:
                return
            
            # Si tiene estructura antigua, migrar
            if 'config_key' in columns and 'config_value' in columns:
                st.info("Migrando configuraciones de alertas a la nueva estructura...")
                
                # Obtener datos existentes
                existing_data = pd.read_sql_query("SELECT * FROM alert_configurations", conn)
                
                # Crear tabla temporal con nueva estructura
                conn.execute("""
                    CREATE TABLE alert_configurations_temp (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL DEFAULT 1,
                        config_type TEXT NOT NULL DEFAULT 'system',
                        config_key TEXT NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(company_id, config_type, config_key)
                    )
                """)
                
                # Migrar datos existentes
                for _, row in existing_data.iterrows():
                    config_type = 'fuel_status' if any(x in row['config_key'] for x in ['excellent_days', 'ok_days', 'regular_days', 'bad_days', 'critical_days']) else 'system'
                    conn.execute("""
                        INSERT INTO alert_configurations_temp (company_id, config_type, config_key, config_value)
                        VALUES (?, ?, ?, ?)
                    """, (1, config_type, row['config_key'], row['config_value']))
                
                # Reemplazar tabla antigua
                conn.execute("DROP TABLE alert_configurations")
                conn.execute("ALTER TABLE alert_configurations_temp RENAME TO alert_configurations")
                conn.commit()
                
                st.success("Migración completada")
            else:
                # Estructura desconocida, recrear tabla
                conn.execute("DROP TABLE alert_configurations")
                conn.execute("""
                    CREATE TABLE alert_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL DEFAULT 1,
                        config_type TEXT NOT NULL DEFAULT 'system',
                        config_key TEXT NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(company_id, config_type, config_key)
                    )
                """)
                conn.commit()
                
        except sqlite3.OperationalError as e:
            # En caso de cualquier error, recrear tabla limpia
            try:
                conn.execute("DROP TABLE IF EXISTS alert_configurations")
                conn.execute("""
                    CREATE TABLE alert_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL DEFAULT 1,
                        config_type TEXT NOT NULL DEFAULT 'system',
                        config_key TEXT NOT NULL,
                        config_value TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(company_id, config_type, config_key)
                    )
                """)
                conn.commit()
            except Exception as final_error:
                st.error(f"Error crítico al recrear tabla de configuraciones: {final_error}")

def mostrar_configuracion_controles(empresa_id):
    """Muestra la configuración avanzada de controles - VERSION CORREGIDA"""
    st.subheader("Configuración de Controles")
    
    # Ejecutar migración ANTES de mostrar cualquier configuración
    try:
        migrate_alert_configurations()
        # Inicializar tabla de configuraciones por tanque
        from db_utils import init_tank_configurations_table
        init_tank_configurations_table()
    except Exception as e:
        st.error(f"Error en inicialización: {e}")
    
    # Tabs de configuración ACTUALIZADOS
    config_tabs = st.tabs(["Unidades", "Tipos de Fluidos", "Tanques", "Alertas Empresa", "Alertas Individuales"])
    
    with config_tabs[0]:
        try:
            mostrar_config_unidades(empresa_id)
        except Exception as e:
            st.error(f"Error en configuración de unidades: {e}")
    
    with config_tabs[1]:
        try:
            mostrar_config_fluidos()
        except Exception as e:
            st.error(f"Error en configuración de fluidos: {e}")
    
    with config_tabs[2]:
        try:
            mostrar_config_tanques(empresa_id)
        except Exception as e:
            st.error(f"Error en configuración de tanques: {e}")
    
    with config_tabs[3]:
        try:
            mostrar_config_alertas_nuevas(empresa_id)  # Nueva función
        except Exception as e:
            st.error(f"Error en configuración de alertas empresa: {e}")
    
    with config_tabs[4]:  # Nueva pestaña
        try:
            mostrar_config_alertas_individuales(empresa_id)  # Nueva función
        except Exception as e:
            st.error(f"Error en configuración de alertas individuales: {e}")

def mostrar_config_unidades(empresa_id):
    """Configuración de unidades de medida"""
    st.subheader("Unidades de Medida")
    
    current_unit = get_company_setting(empresa_id, "unit_preference", "galones")
    
    new_unit = st.radio(
        "Unidad preferida para fluidos",
        ["galones", "litros"],
        index=0 if current_unit == "galones" else 1,
        help="Esta configuración afecta cómo se muestran todas las medidas de fluidos"
    )
    
    if st.button("Actualizar Unidades"):
        set_company_setting(empresa_id, "unit_preference", new_unit)
        st.success(f"Unidad actualizada a {new_unit}")
        time.sleep(1)
        st.rerun()
    
    # Mostrar factor de conversión actual
    st.info("Factor de conversión: 1 galón = 3.78541 litros")

def mostrar_config_fluidos():
    """Configuración de tipos de fluidos"""
    st.subheader("Tipos de Fluidos")
    
    # Mostrar fluidos existentes
    fluid_types = get_fluid_types()
    
    if not fluid_types.empty:
        st.markdown("**Tipos de fluidos configurados:**")
        
        for _, fluid in fluid_types.iterrows():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"• {fluid['name']} ({fluid['unit_type']})")
            
            with col2:
                if st.button(f"Eliminar", key=f"delete_fluid_{fluid['id']}"):
                    success, message = delete_fluid_type(fluid['id'])
                    if success:
                        st.success(message)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(message)
    
    # Formulario para nuevo fluido
    st.markdown("**Añadir nuevo tipo de fluido:**")
    
    with st.form("nuevo_fluido"):
        col1, col2 = st.columns(2)
        
        with col1:
            nuevo_nombre = st.text_input("Nombre del fluido")
        
        with col2:
            tipo_unidad = st.selectbox("Tipo de unidad", ["volume", "weight"])
        
        if st.form_submit_button("Añadir Fluido"):
            if nuevo_nombre.strip():
                if add_fluid_type(nuevo_nombre.strip(), tipo_unidad):
                    st.success("Tipo de fluido añadido correctamente")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Este tipo de fluido ya existe")
            else:
                st.error("El nombre del fluido es obligatorio")

def mostrar_config_tanques(empresa_id):
    """Configuración de tanques por empresa"""
    st.subheader("Configuración de Tanques")
    
    # Obtener fluidos disponibles
    fluid_types = get_fluid_types()
    unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
    
    if fluid_types.empty:
        st.warning("Primero debe configurar tipos de fluidos")
        return
    
    # Mostrar tanques configurados
    tanques_configurados = get_company_tanks(empresa_id)
    
    if not tanques_configurados.empty:
        st.markdown("**Tanques configurados:**")
        
        for _, tank in tanques_configurados.iterrows():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            
            with col1:
                st.write(f"• {tank['fluid_name']}")
            
            with col2:
                st.write(f"Capacidad: {tank['tank_capacity']:.1f} {tank['unit']}")
            
            with col3:
                percentage = (tank['current_level'] / tank['tank_capacity']) * 100 if tank['tank_capacity'] > 0 else 0
                st.write(f"Actual: {tank['current_level']:.1f} {tank['unit']} ({percentage:.1f}%)")
            
            with col4:
                # Usar el ID correcto del tanque
                tank_id = tank.get('id') or tank.get('tank_id')
                if st.button("Editar", key=f"edit_tank_{tank_id}"):
                    st.session_state[f"editing_tank_{tank_id}"] = True
            
            # Formulario de edición
            if st.session_state.get(f"editing_tank_{tank_id}", False):
                with st.form(f"edit_tank_form_{tank_id}"):
                    nueva_capacidad = st.number_input(
                        "Nueva capacidad",
                        min_value=0.0,
                        value=float(tank['tank_capacity']),
                        step=10.0,
                        format="%.1f",
                        key=f"capacity_{tank_id}"
                    )
                    
                    if st.form_submit_button("Guardar"):
                        update_tank_capacity(tank_id, nueva_capacidad)
                        st.session_state[f"editing_tank_{tank_id}"] = False
                        st.success("Capacidad actualizada")
                        time.sleep(1)
                        st.rerun()
                    
                    if st.form_submit_button("Cancelar"):
                        st.session_state[f"editing_tank_{tank_id}"] = False
                        st.rerun()
        
        st.divider()
    
    # Configurar nuevos tanques
    st.markdown("**Configurar nuevo tanque:**")
    
    with st.form("nuevo_tanque"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Filtrar fluidos que no tienen tanque configurado
            fluidos_sin_tanque = []
            fluidos_con_tanque = tanques_configurados['fluid_type_id'].tolist() if not tanques_configurados.empty else []
            
            for _, fluid in fluid_types.iterrows():
                if fluid['id'] not in fluidos_con_tanque:
                    fluidos_sin_tanque.append((fluid['id'], fluid['name']))
            
            if not fluidos_sin_tanque:
                st.info("Todos los tipos de fluidos ya tienen tanques configurados")
                fluido_seleccionado = None
            else:
                fluido_options = {name: id for id, name in fluidos_sin_tanque}
                fluido_nombre = st.selectbox(
                    "Tipo de fluido",
                    list(fluido_options.keys())
                )
                fluido_seleccionado = fluido_options[fluido_nombre] if fluido_nombre else None
        
        with col2:
            capacidad_tanque = st.number_input(
                f"Capacidad ({unit_preference})",
                min_value=0.0,
                step=50.0,
                format="%.1f"
            )
        
        if st.form_submit_button("Configurar Tanque"):
            if fluido_seleccionado and capacidad_tanque > 0:
                if setup_company_tank(empresa_id, fluido_seleccionado, capacidad_tanque, unit_preference):
                    st.success("Tanque configurado correctamente")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Error al configurar el tanque o ya existe un tanque para este fluido")
            else:
                st.error("Seleccione un fluido y especifique una capacidad válida")

def mostrar_config_alertas(empresa_id):
    """Configuración de alertas y umbrales - SOLO COMBUSTIBLE"""
    st.subheader("Configuración de Alertas")
    
    # Ejecutar migración para asegurar estructura correcta
    migrate_alert_configurations()
    
    # Alertas de combustible
    st.markdown("**Alertas de Nivel de Combustible**")
    st.caption("Configure los umbrales de días restantes para cada nivel de alerta")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        excellent_days = st.number_input(
            "Excelente (días)",
            min_value=1,
            value=int(get_alert_configuration(empresa_id, "fuel_status", "excellent_days", "20")),
            step=1,
            help="Días restantes para considerar estado excelente"
        )
    
    with col2:
        ok_days = st.number_input(
            "OK (días)",
            min_value=1,
            value=int(get_alert_configuration(empresa_id, "fuel_status", "ok_days", "10")),
            step=1
        )
    
    with col3:
        regular_days = st.number_input(
            "Regular (días)",
            min_value=1,
            value=int(get_alert_configuration(empresa_id, "fuel_status", "regular_days", "7")),
            step=1
        )
    
    with col4:
        bad_days = st.number_input(
            "Malo (días)",
            min_value=1,
            value=int(get_alert_configuration(empresa_id, "fuel_status", "bad_days", "3")),
            step=1
        )
    
    with col5:
        critical_days = st.number_input(
            "Crítico (días)",
            min_value=0,
            value=int(get_alert_configuration(empresa_id, "fuel_status", "critical_days", "1")),
            step=1
        )
    
    if st.button("Guardar Configuración de Combustible"):
        update_alert_configuration(empresa_id, "fuel_status", "excellent_days", excellent_days)
        update_alert_configuration(empresa_id, "fuel_status", "ok_days", ok_days)
        update_alert_configuration(empresa_id, "fuel_status", "regular_days", regular_days)
        update_alert_configuration(empresa_id, "fuel_status", "bad_days", bad_days)
        update_alert_configuration(empresa_id, "fuel_status", "critical_days", critical_days)
        st.success("Configuración de alertas actualizada")

# AGREGA al final de tu controles_config.py:

def mostrar_config_alertas_individuales(empresa_id):
    """Nueva pestaña para configuración individual de alertas por tanque"""
    st.markdown("### Configuración Individual por Tanque")
    st.info("Configure umbrales de alerta específicos para cada tanque. Si no se configura, se usarán los valores predeterminados de la empresa.")
    
    # Obtener tanques de la empresa
    tanques = get_company_tanks(empresa_id)
    
    if tanques.empty:
        st.warning("No hay tanques configurados para esta empresa.")
        return
    
    # Selector de tanque
    tank_options = {}
    for _, tank in tanques.iterrows():
        percentage = (tank['current_level'] / tank['tank_capacity']) * 100 if tank['tank_capacity'] > 0 else 0
        display_name = f"{tank['fluid_name']} ({percentage:.1f}% - {tank['current_level']:.1f}/{tank['tank_capacity']:.0f} {tank['unit']})"
        tank_options[display_name] = tank
    
    selected_display = st.selectbox("Seleccionar tanque para configurar:", list(tank_options.keys()))
    
    if selected_display:
        selected_tank = tank_options[selected_display]
        tank_id = selected_tank['id']
        
        # Mostrar configuración actual
        from controles_module import get_tank_alert_thresholds
        current_config = get_tank_alert_thresholds(tank_id, empresa_id)
        
        col_info1, col_info2 = st.columns(2)
        
        with col_info1:
            if current_config['source'] == 'individual':
                st.success("Este tanque tiene configuración personalizada")
            else:
                st.info("Este tanque usa configuración predeterminada")
        
        with col_info2:
            st.metric("Configuración Actual", f"Crítico: {current_config['critical']}% | Bajo: {current_config['low']}%")
        
        # Formulario de configuración
        with st.form(f"individual_alert_config_{tank_id}"):
            st.markdown("#### Configurar Umbrales Específicos")
            
            col1, col2 = st.columns(2)
            with col1:
                critical_threshold = st.slider(
                    "🔴 Umbral Crítico (%)",
                    min_value=1,
                    max_value=30,
                    value=int(current_config['critical']),
                    help="Porcentaje por debajo del cual se considera crítico"
                )
            
            with col2:
                low_threshold = st.slider(
                    "🟡 Umbral Bajo (%)",
                    min_value=critical_threshold + 1,
                    max_value=50,
                    value=int(current_config['low']),
                    help="Porcentaje por debajo del cual se considera bajo"
                )
            
            # Vista previa del estado actual
            st.markdown("#### Vista Previa del Estado Actual")
            current_percentage = (selected_tank['current_level'] / selected_tank['tank_capacity']) * 100
            
            col_preview1, col_preview2, col_preview3 = st.columns(3)
            
            with col_preview1:
                if current_percentage <= critical_threshold:
                    st.error(f"🚨 CRÍTICO: {current_percentage:.1f}%")
                elif current_percentage <= low_threshold:
                    st.warning(f"⚠️ BAJO: {current_percentage:.1f}%")
                else:
                    st.success(f"✅ NORMAL: {current_percentage:.1f}%")
            
            with col_preview2:
                st.metric("Nivel Actual", f"{selected_tank['current_level']:.1f} {selected_tank['unit']}")
            
            with col_preview3:
                st.metric("Capacidad", f"{selected_tank['tank_capacity']:.1f} {selected_tank['unit']}")
            
            # Botones de acción
            col_save, col_reset, col_preview = st.columns(3)
            
            with col_save:
                if st.form_submit_button("💾 Guardar Configuración Individual", type="primary"):
                    try:
                        from db_utils import set_tank_alert_configuration
                        
                        success1 = set_tank_alert_configuration(tank_id, "critical_threshold", str(critical_threshold))
                        success2 = set_tank_alert_configuration(tank_id, "low_threshold", str(low_threshold))
                        
                        if success1 and success2:
                            st.success("✅ Configuración individual guardada correctamente")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar configuración")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            
            with col_reset:
                if st.form_submit_button("🔄 Usar Predeterminado Empresa"):
                    try:
                        with get_conn() as conn:
                            conn.execute("""
                                DELETE FROM tank_configurations 
                                WHERE tank_id = ? AND config_key IN ('critical_threshold', 'low_threshold')
                            """, (tank_id,))
                            conn.commit()
                        
                        st.success("✅ Configuración restablecida a valores predeterminados")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            
            with col_preview:
                st.caption("Los cambios se aplicarán inmediatamente en el dashboard")
        
        # Información adicional
        st.divider()
        with st.expander("📋 Información de Configuración"):
            # Mostrar configuración predeterminada de la empresa
            default_critical = get_alert_configuration(empresa_id, "fuel_levels", "critical_threshold", "10")
            default_low = get_alert_configuration(empresa_id, "fuel_levels", "low_threshold", "25")
            
            col_def1, col_def2 = st.columns(2)
            with col_def1:
                st.metric("Empresa - Crítico", f"{default_critical}%")
            with col_def2:
                st.metric("Empresa - Bajo", f"{default_low}%")
            
            st.info("Si no se configura individualmente, el tanque usará los valores predeterminados de la empresa mostrados arriba.")

def mostrar_config_alertas_nuevas(empresa_id):
    """Nueva configuración de alertas simplificada (3 niveles)"""
    st.markdown("### Configuración de Alertas de Inventario")
    st.info("Configure los umbrales predeterminados para todos los tanques de la empresa")
    
    # Migrar configuraciones existentes si es necesario
    migrate_alert_configurations()
    
    with st.form("config_alertas_inventario"):
        st.markdown("#### Umbrales Predeterminados de la Empresa")
        st.caption("Estos valores se aplicarán a todos los tanques que no tengan configuración individual")
        
        col1, col2 = st.columns(2)
        
        with col1:
            critical_threshold = st.slider(
                "🔴 Umbral Crítico (%)",
                min_value=1,
                max_value=20,
                value=int(get_alert_configuration(empresa_id, "fuel_levels", "critical_threshold", "10")),
                help="Porcentaje de inventario por debajo del cual se considera crítico"
            )
        
        with col2:
            low_threshold = st.slider(
                "🟡 Umbral Bajo (%)",
                min_value=critical_threshold + 1,
                max_value=50,
                value=int(get_alert_configuration(empresa_id, "fuel_levels", "low_threshold", "25")),
                help="Porcentaje de inventario por debajo del cual se considera bajo"
            )
        
        # Vista previa de los niveles
        st.markdown("#### Vista Previa de Niveles")
        col_prev1, col_prev2, col_prev3 = st.columns(3)
        
        with col_prev1:
            st.error(f"🚨 CRÍTICO: ≤ {critical_threshold}%")
        
        with col_prev2:
            st.warning(f"⚠️ BAJO: {critical_threshold + 1}% - {low_threshold}%")
        
        with col_prev3:
            st.success(f"✅ NORMAL: > {low_threshold}%")
        
        if st.form_submit_button("💾 Guardar Configuración Predeterminada", type="primary"):
            try:
                update_alert_configuration(empresa_id, "fuel_levels", "critical_threshold", critical_threshold)
                update_alert_configuration(empresa_id, "fuel_levels", "low_threshold", low_threshold)
                
                st.success("✅ Configuración de alertas guardada correctamente")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar: {str(e)}")
    
    st.divider()
    
    # Estadísticas de configuración
    st.markdown("#### Resumen de Configuración")
    
    # Mostrar cuántos tanques usan configuración individual vs predeterminada
    tanques = get_company_tanks(empresa_id)
    if not tanques.empty:
        tanques_individuales = 0
        tanques_predeterminados = 0
        
        for _, tank in tanques.iterrows():
            from controles_module import get_tank_alert_thresholds
            config = get_tank_alert_thresholds(tank['id'], empresa_id)
            if config['source'] == 'individual':
                tanques_individuales += 1
            else:
                tanques_predeterminados += 1
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        
        with col_stat1:
            st.metric("Total Tanques", len(tanques))
        
        with col_stat2:
            st.metric("Config. Individual", tanques_individuales)
        
        with col_stat3:
            st.metric("Config. Predeterminada", tanques_predeterminados)