"maintenance_module.py"
import db_utils
from db_utils import get_conn, update_machine_hours, update_machine_km, get_machine_current_values, update_machine_odometer

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from db_utils import get_machinery_for_maintenance, get_localized_status_display 
machinery = get_machinery_for_maintenance

import sqlite3
import io

def verify_and_setup_maintenance_tables():
    """Verifica y configura las tablas necesarias de forma segura"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Verificar si la tabla machinery existe
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='machinery'")
            if not cur.fetchone():
                st.error("La tabla 'machinery' no existe. Debe ser creada primero en el sistema principal.")
                return False
                
            # Obtener información de la tabla machinery
            cur.execute("PRAGMA table_info(machinery)")
            machinery_columns = {row[1]: row[2] for row in cur.fetchall()}
            
            # Columnas requeridas para el módulo de mantenimiento
            required_columns = {
                "current_hours": "REAL DEFAULT 0.0",
                "current_odometer": "REAL DEFAULT 0.0", 
                "status": "TEXT DEFAULT 'Activa'",
                "last_status_change": "TEXT",
                "last_maintenance_date": "TEXT",
                "last_maintenance_hours": "REAL",
                "last_maintenance_km": "REAL"
            }
            
            # Agregar columnas faltantes de forma segura
            for column_name, column_def in required_columns.items():
                if column_name not in machinery_columns:
                    try:
                        cur.execute(f"ALTER TABLE machinery ADD COLUMN {column_name} {column_def}")
                        st.info(f"Columna '{column_name}' agregada a la tabla machinery")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" not in str(e).lower():
                            st.warning(f"No se pudo agregar la columna {column_name}: {e}")
            
            # Crear tablas específicas del módulo de mantenimiento
            maintenance_tables = {
                "maintenance_types": """
                    CREATE TABLE IF NOT EXISTS maintenance_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        default_hours_interval REAL DEFAULT 5000,
                        default_km_interval REAL DEFAULT 5000,
                        is_preventive INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "maintenance_intervals": """
                    CREATE TABLE IF NOT EXISTS maintenance_intervals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machinery_id INTEGER,
                        maintenance_type_id INTEGER,
                        hours_interval REAL NOT NULL,
                        km_interval REAL NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(machinery_id, maintenance_type_id),
                        FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
                        FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types(id)
                    )
                """,
                "maintenance_schedules": """
                    CREATE TABLE IF NOT EXISTS maintenance_schedules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machinery_id INTEGER,
                        maintenance_type_id INTEGER,
                        scheduled_start_date TEXT,
                        scheduled_end_date TEXT,
                        estimated_hours REAL,
                        description TEXT,
                        responsible_person TEXT,
                        priority TEXT DEFAULT 'NORMAL',
                        status TEXT DEFAULT 'PROGRAMADO',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
                        FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types(id)
                    )
                """,
                "maintenance_records": """
                    CREATE TABLE IF NOT EXISTS maintenance_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machinery_id INTEGER,
                        maintenance_type_id INTEGER,
                        start_date TEXT,
                        end_date TEXT,
                        performed_by TEXT,
                        odometer_start REAL,
                        odometer_end REAL,
                        hour_meter_start REAL,
                        hour_meter_end REAL,
                        cost REAL,
                        description TEXT,
                        parts_used TEXT,
                        notes TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
                        FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types(id)
                    )
                """,
                "status_change_reasons": """
                    CREATE TABLE IF NOT EXISTS status_change_reasons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        applies_to TEXT DEFAULT 'ALL',
                        is_active INTEGER DEFAULT 1
                    )
                """,
                "status_history": """
                    CREATE TABLE IF NOT EXISTS status_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machinery_id INTEGER,
                        previous_status TEXT,
                        new_status TEXT,
                        changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        changed_by TEXT,
                        reason_id INTEGER,
                        notes TEXT,
                        duration_in_previous_status INTEGER,
                        FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
                        FOREIGN KEY (reason_id) REFERENCES status_change_reasons(id)
                    )
                """,
                "alert_configurations": """
                    CREATE TABLE IF NOT EXISTS alert_configurations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        config_name TEXT NOT NULL,
                        warning_threshold INTEGER DEFAULT 200,
                        alert_threshold INTEGER DEFAULT 100,
                        critical_threshold INTEGER DEFAULT 50,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """
            }
            
            # Crear tablas del módulo de mantenimiento
            for table_name, create_sql in maintenance_tables.items():
                try:
                    cur.execute(create_sql)
                except sqlite3.Error as e:
                    st.error(f"Error al crear la tabla {table_name}: {e}")
                    return False
            
            # Insertar datos por defecto solo si no existen
            insert_default_data(cur)
            
            conn.commit()
            return True
            
    except sqlite3.Error as e:
        st.error(f"Error de base de datos: {e}")
        return False
    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return False

def insert_default_data(cur):
    """Inserta datos por defecto de forma segura"""
    try:
        # Verificar si ya existen tipos de mantenimiento
        cur.execute("SELECT COUNT(*) FROM maintenance_types")
        if cur.fetchone()[0] == 0:
            default_maintenance_types = [
                ("Mantenimiento Preventivo", "Mantenimiento rutinario programado", 5000, 5000, 1),
                ("Cambio de Aceite Motor", "Cambio de aceite del motor y filtros", 2000, 10000, 1),
                ("Inspección de Frenos", "Revisión y mantenimiento del sistema de frenos", 3000, 15000, 1),
                ("Cambio de Filtros", "Reemplazo de filtros de aire, combustible, hidráulico", 1500, 8000, 1),
                ("Inspección General", "Revisión completa de sistemas", 2500, 12000, 1),
                ("Servicio de Transmisión", "Mantenimiento de sistema de transmisión", 8000, 40000, 1),
                ("Servicio Hidráulico", "Mantenimiento de sistema hidráulico", 4000, 20000, 1),
                ("Inspección Eléctrica", "Revisión de sistema eléctrico", 6000, 25000, 1),
                ("Reparación Correctiva", "Reparación de fallas o daños", 0, 0, 0),
                ("Revisión de Seguridad", "Verificación de sistemas de seguridad", 1000, 5000, 1),
            ]
            
            for name, description, hours_interval, km_interval, is_preventive in default_maintenance_types:
                cur.execute("""
                    INSERT OR IGNORE INTO maintenance_types 
                    (name, description, default_hours_interval, default_km_interval, is_preventive) 
                    VALUES (?, ?, ?, ?, ?)
                """, (name, description, hours_interval, km_interval, is_preventive))
        
        # Verificar si ya existen causas de cambio de estado
        cur.execute("SELECT COUNT(*) FROM status_change_reasons")
        if cur.fetchone()[0] == 0:
            default_reasons = [
                ("Mantenimiento Programado", "Cambio a estado de mantenimiento por programación", "Mantenimiento"),
                ("Reparación Necesaria", "Cambio por necesidad de reparación", "Mantenimiento"),
                ("Mantenimiento Completado", "Vuelta a servicio tras mantenimiento", "Activa"),
                ("Avería Mecánica", "Máquina fuera de servicio por avería", "Inactiva"),
                ("Fin de Jornada Laboral", "Cambio por finalización de trabajo diario", "Inactiva"),
                ("Inicio de Jornada Laboral", "Activación para inicio de trabajo", "Activa"),
                ("Falta de Combustible", "Inactiva por falta de combustible", "Inactiva"),
                ("Condiciones Climáticas Adversas", "Inactiva por condiciones meteorológicas", "Inactiva"),
                ("Inspección Rutinaria", "Revisión periódica programada", "Mantenimiento"),
                ("Otras Causas", "Otras causas no especificadas", "ALL")
            ]
            
            for name, description, applies_to in default_reasons:
                cur.execute("""
                    INSERT OR IGNORE INTO status_change_reasons (name, description, applies_to) 
                    VALUES (?, ?, ?)
                """, (name, description, applies_to))
        
        # Verificar si ya existen configuraciones de alerta
        cur.execute("SELECT COUNT(*) FROM alert_configurations")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT OR IGNORE INTO alert_configurations 
                (config_name, warning_threshold, alert_threshold, critical_threshold, is_active) 
                VALUES ('hours_before_maintenance', 200, 100, 50, 1)
            """)
            cur.execute("""
                INSERT OR IGNORE INTO alert_configurations 
                (config_name, warning_threshold, alert_threshold, critical_threshold, is_active) 
                VALUES ('km_before_maintenance', 500, 300, 100, 1)
            """)
            
    except sqlite3.Error as e:
        st.warning(f"Advertencia al insertar datos por defecto: {e}")

def get_maintenance_status_for_machine(machinery_id, maintenance_type_id, current_hours, current_km):
    """Calcula el estado de mantenimiento para una máquina y tipo específico"""
    try:
        with get_conn() as conn:
            # Obtener intervalos configurados para esta máquina y tipo
            interval_query = """
                SELECT hours_interval, km_interval 
                FROM maintenance_intervals 
                WHERE machinery_id = ? AND maintenance_type_id = ? AND is_active = 1
            """
            interval_result = conn.execute(interval_query, (machinery_id, maintenance_type_id)).fetchone()
            
            if not interval_result:
                # Si no hay intervalos específicos, usar los por defecto del tipo
                default_query = """
                    SELECT default_hours_interval, default_km_interval 
                    FROM maintenance_types 
                    WHERE id = ?
                """
                default_result = conn.execute(default_query, (maintenance_type_id,)).fetchone()
                if default_result:
                    hours_interval, km_interval = default_result
                else:
                    hours_interval, km_interval = 5000, 5000  # Fallback
            else:
                hours_interval, km_interval = interval_result
            
            # Obtener el último mantenimiento de este tipo para esta máquina
            last_maint_query = """
                SELECT hour_meter_end, odometer_end, created_at
                FROM maintenance_records 
                WHERE machinery_id = ? AND maintenance_type_id = ?
                ORDER BY created_at DESC 
                LIMIT 1
            """
            last_maint = conn.execute(last_maint_query, (machinery_id, maintenance_type_id)).fetchone()
            
            if last_maint:
                last_hours = float(last_maint[0] or 0)
                last_km = float(last_maint[1] or 0)
                last_date = last_maint[2]
            else:
                # Si no hay mantenimiento previo, usar 0 como base
                last_hours = 0
                last_km = 0
                last_date = None
            
            # Calcular próximo mantenimiento
            next_maint_hours = last_hours + hours_interval
            next_maint_km = last_km + km_interval
            
            # Calcular cuánto falta
            hours_remaining = next_maint_hours - current_hours
            km_remaining = next_maint_km - current_km
            
            # Obtener umbrales de alertas
            alert_config = get_alert_thresholds()
            
            # Determinar estado basado en lo que esté más cerca
            hours_status = get_alert_level(hours_remaining, alert_config['hours'])
            km_status = get_alert_level(km_remaining, alert_config['km'])
            
            # El estado general es el más crítico de los dos
            if hours_status == 'CRITICAL' or km_status == 'CRITICAL':
                overall_status = 'CRITICAL'
            elif hours_status == 'WARNING' or km_status == 'WARNING':
                overall_status = 'WARNING'
            elif hours_status == 'ALERT' or km_status == 'ALERT':
                overall_status = 'ALERT'
            else:
                overall_status = 'NORMAL'
            
            return {
                'hours_interval': hours_interval,
                'km_interval': km_interval,
                'last_maint_hours': last_hours,
                'last_maint_km': last_km,
                'last_maint_date': last_date,
                'next_maint_hours': next_maint_hours,
                'next_maint_km': next_maint_km,
                'hours_remaining': hours_remaining,
                'km_remaining': km_remaining,
                'hours_status': hours_status,
                'km_status': km_status,
                'overall_status': overall_status
            }
            
    except Exception as e:
        st.error(f"Error calculando estado de mantenimiento: {e}")
        return None

def get_alert_thresholds():
    """Obtiene los umbrales de alertas configurados - CORREGIDA para estructura real de tabla"""
    try:
        with get_conn() as conn:
            # Usar config_key en lugar de name
            hours_config = conn.execute("""
                SELECT warning_threshold, alert_threshold, critical_threshold 
                FROM alert_configurations 
                WHERE config_key = 'hours_before_maintenance' AND is_active = 1
            """).fetchone()
            
            km_config = conn.execute("""
                SELECT warning_threshold, alert_threshold, critical_threshold 
                FROM alert_configurations 
                WHERE config_key = 'km_before_maintenance' AND is_active = 1
            """).fetchone()
            
            return {
                'hours': {
                    'warning': hours_config[0] if hours_config else 200,
                    'alert': hours_config[1] if hours_config else 100,
                    'critical': hours_config[2] if hours_config else 50
                },
                'km': {
                    'warning': km_config[0] if km_config else 500,
                    'alert': km_config[1] if km_config else 300,
                    'critical': km_config[2] if km_config else 100
                }
            }
    except Exception:
        return {
            'hours': {'warning': 200, 'alert': 100, 'critical': 50},
            'km': {'warning': 500, 'alert': 300, 'critical': 100}
        }

def get_alert_level(remaining, thresholds):
    """Determina el nivel de alerta basado en lo que queda hasta el mantenimiento"""
    if remaining <= thresholds['critical']:
        return 'CRITICAL'
    elif remaining <= thresholds['alert']:
        return 'ALERT'
    elif remaining <= thresholds['warning']:
        return 'WARNING'
    else:
        return 'NORMAL'

def safe_get_machinery_data(empresa_id):
    """Obtiene datos de maquinaria de forma segura verificando la estructura"""
    try:
        with get_conn() as conn:
            # Verificar que la tabla machinery existe y tiene las columnas necesarias
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(machinery)")
            columns = [row[1] for row in cur.fetchall()]
            
            if not columns:
                st.error("La tabla 'machinery' no existe. Debe ser creada primero en el sistema principal.")
                return pd.DataFrame()
            
            # Construir SELECT dinámico basado en las columnas disponibles
            base_columns = ['id', 'name']
            optional_columns = {
                'identifier': 'identifier',
                'classification': 'classification', 
                'status': 'status',
                'current_hours': 'current_hours',
                'current_odometer': 'current_odometer',
                'last_maintenance_date': 'last_maintenance_date',
                'last_maintenance_hours': 'last_maintenance_hours',
                'last_maintenance_km': 'last_maintenance_km',
                'last_status_change': 'last_status_change'
            }
            
            # Construir SELECT dinámico
            select_parts = base_columns.copy()
            for alias, column in optional_columns.items():
                if column in columns:
                    select_parts.append(f"COALESCE({column}, '') as {alias}" if column in ['identifier', 'classification', 'status'] 
                                      else f"COALESCE({column}, 0) as {alias}" if 'hours' in column or 'km' in column
                                      else f"{column} as {alias}")
                else:
                    # Valores por defecto para columnas faltantes
                    if 'hours' in alias or 'km' in alias:
                        select_parts.append(f"0.0 as {alias}")
                    elif alias == 'status':
                        select_parts.append("'Activa' as status")
                    else:
                        select_parts.append(f"'' as {alias}")
            
            query = f"""
                SELECT {', '.join(select_parts)}
                FROM machinery 
                WHERE company_id = ?
                ORDER BY name
            """
            
            return pd.read_sql_query(query, conn, params=(empresa_id,))
            
    except sqlite3.Error as e:
        st.error(f"Error al obtener datos de maquinaria: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return pd.DataFrame()

def setup_maintenance_intervals_for_machine(machinery_id):
    """Configura intervalos de mantenimiento por defecto para una máquina nueva"""
    try:
        with get_conn() as conn:
            # Obtener todos los tipos de mantenimiento preventivo
            types_query = """
                SELECT id, default_hours_interval, default_km_interval 
                FROM maintenance_types 
                WHERE is_preventive = 1
            """
            types_df = pd.read_sql_query(types_query, conn)
            
            for _, maint_type in types_df.iterrows():
                # Verificar si ya existe configuración para esta máquina y tipo
                existing = conn.execute("""
                    SELECT id FROM maintenance_intervals 
                    WHERE machinery_id = ? AND maintenance_type_id = ?
                """, (machinery_id, maint_type['id'])).fetchone()
                
                if not existing:
                    # Crear configuración por defecto
                    conn.execute("""
                        INSERT INTO maintenance_intervals 
                        (machinery_id, maintenance_type_id, hours_interval, km_interval) 
                        VALUES (?, ?, ?, ?)
                    """, (machinery_id, maint_type['id'], 
                          maint_type['default_hours_interval'], 
                          maint_type['default_km_interval']))
            
            conn.commit()
            
    except Exception as e:
        st.error(f"Error configurando intervalos: {e}")

# Resto de funciones existentes sin cambios...
def safe_get_machinery_data(empresa_id):
    """Obtiene datos de maquinaria de forma segura verificando la estructura"""
    try:
        with get_conn() as conn:
            # Verificar que la tabla machinery existe y tiene las columnas necesarias
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(machinery)")
            columns = [row[1] for row in cur.fetchall()]
            
            if not columns:
                st.error("La tabla 'machinery' no existe. Debe ser creada primero en el sistema principal.")
                return pd.DataFrame()
            
            # Construir SELECT dinámico basado en las columnas disponibles
            base_columns = ['id', 'name']
            optional_columns = {
                'identifier': 'identifier',
                'classification': 'classification', 
                'status': 'status',
                'current_hours': 'current_hours',
                'current_odometer': 'current_odometer',
                'last_maintenance_date': 'last_maintenance_date',
                'last_maintenance_hours': 'last_maintenance_hours',
                'last_maintenance_km': 'last_maintenance_km',
                'last_status_change': 'last_status_change'
            }
            
            # Construir SELECT dinámico
            select_parts = base_columns.copy()
            for alias, column in optional_columns.items():
                if column in columns:
                    select_parts.append(f"COALESCE({column}, '') as {alias}" if column in ['identifier', 'classification', 'status'] 
                                      else f"COALESCE({column}, 0) as {alias}" if 'hours' in column or 'km' in column
                                      else f"{column} as {alias}")
                else:
                    # Valores por defecto para columnas faltantes
                    if 'hours' in alias or 'km' in alias:
                        select_parts.append(f"0.0 as {alias}")
                    elif alias == 'status':
                        select_parts.append("'Activa' as status")
                    else:
                        select_parts.append(f"'' as {alias}")
            
            query = f"""
                SELECT {', '.join(select_parts)}
                FROM machinery 
                WHERE company_id = ?
                ORDER BY name
            """
            
            return pd.read_sql_query(query, conn, params=(empresa_id,))
            
    except sqlite3.Error as e:
        st.error(f"Error al obtener datos de maquinaria: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return pd.DataFrame()

def mostrar_mantenimiento(empresa_id):
    """Función principal mejorada con manejo de errores"""
    # Verificar e inicializar tablas de forma segura
    if not verify_and_setup_maintenance_tables():
        st.error("No se pudo inicializar el módulo de mantenimiento. Contacte al administrador.")
        return

    st.header("Sistema de Gestión de Mantenimiento Vehicular")

    # Verificar que hay maquinaria registrada
    machinery_df = safe_get_machinery_data(empresa_id)
    if machinery_df.empty:
        st.warning("""
        **No hay vehículos registrados para esta empresa.**
        
        Para usar el módulo de mantenimiento, primero debe:
        1. Registrar vehículos en el módulo de maquinaria
        2. Asegurarse de que estén asociados a la empresa correcta
        """)
        return

    # Configurar intervalos por defecto para máquinas que no los tengan
    for _, machine in machinery_df.iterrows():
        setup_maintenance_intervals_for_machine(machine['id'])

    # Tabs principales del sistema - AGREGA "Diagnóstico" temporalmente
    main_tabs = st.tabs([
        "Diagnóstico",  # ← NUEVO
        "Dashboard General", 
        "Estado de Mantenimientos",
        "Gestión de Estados", 
        "Gestión de Mantenimiento", 
        "Historial y Reportes", 
        "Configuración del Sistema"
    ])

    try:
        with main_tabs[0]:  # ← CAMBIADO
            mostrar_diagnostico_sqlite_compatible()  # ← Cambiado aquí
        
        with main_tabs[1]:  # Los índices se corrieron
            mostrar_modulo_general_safe(empresa_id, machinery_df)
        
        with main_tabs[2]:
            mostrar_estado_mantenimientos_mejorado(empresa_id, machinery_df)
        
        with main_tabs[3]:
            mostrar_modulo_estados_safe(empresa_id, machinery_df)
        
        with main_tabs[4]:
            mostrar_modulo_mantenimiento_safe(empresa_id, machinery_df)
        
        with main_tabs[5]:
            mostrar_modulo_historial_safe(empresa_id)
        
        with main_tabs[6]:
            mostrar_modulo_configuracion_mejorado(empresa_id)
            
    except Exception as e:
        st.error(f"Error en el módulo de mantenimiento: {e}")
        st.info("Si el problema persiste, contacte al administrador del sistema.")

def mostrar_estado_mantenimientos_mejorado(empresa_id, machinery_df):
    """Muestra el estado de mantenimientos con colores más legibles"""
    st.subheader("Estado de Mantenimientos por Tipo")
    
    try:
        with get_conn() as conn:
            # Obtener tipos de mantenimiento preventivo
            tipos_df = pd.read_sql_query("""
                SELECT id, name, default_hours_interval, default_km_interval 
                FROM maintenance_types 
                WHERE is_preventive = 1 
                ORDER BY name
            """, conn)
            
            if tipos_df.empty:
                st.warning("No hay tipos de mantenimiento preventivo configurados.")
                return
            
            # Selector de tipo de mantenimiento
            selected_type_id = st.selectbox(
                "Seleccionar Tipo de Mantenimiento",
                tipos_df['id'].tolist(),
                format_func=lambda x: tipos_df[tipos_df['id']==x].iloc[0]['name'],
                key="select_maint_type_status"
            )
            
            # Crear tabla de estado para el tipo seleccionado
            status_data = []
            
            for _, machine in machinery_df.iterrows():
                current_hours = float(machine.get('current_hours', 0))
                current_km = float(machine.get('current_odometer', 0))
                
                status = get_maintenance_status_for_machine(
                    machine['id'], selected_type_id, current_hours, current_km
                )
                
                if status:
                    status_data.append({
                        'machine_id': machine['id'],
                        'Vehículo': machine['name'],
                        'Matrícula': machine.get('identifier', 'N/A'),
                        'Horómetro Actual': current_hours,
                        'Odómetro Actual (km)': current_km,
                        'Último Mant. Horas': status['last_maint_hours'],
                        'Último Mant. Km': status['last_maint_km'],
                        'Próximo Mant. Horas': status['next_maint_hours'],
                        'Próximo Mant. Km': status['next_maint_km'],
                        'Horas Restantes': status['hours_remaining'],
                        'Km Restantes': status['km_remaining'],
                        'Estado Horas': status['hours_status'],
                        'Estado Km': status['km_status'],
                        'Estado General': status['overall_status'],
                        'Intervalo Horas': status['hours_interval'],
                        'Intervalo Km': status['km_interval']
                    })
            
            if status_data:
                status_df = pd.DataFrame(status_data)
                
                # Función de colores mejorada con mayor contraste y legibilidad
                def style_status_row_improved(row):
                    if row['Estado General'] == 'CRITICAL':
                        # Rojo claro con texto negro para mejor contraste
                        return ['background-color: #ffe6e6; color: #800000; font-weight: bold'] * len(row)
                    elif row['Estado General'] == 'WARNING':
                        # Naranja claro con texto oscuro
                        return ['background-color: #fff2e6; color: #cc6600; font-weight: bold'] * len(row)
                    elif row['Estado General'] == 'ALERT':
                        # Amarillo claro con texto oscuro
                        return ['background-color: #fffacd; color: #b8860b; font-weight: bold'] * len(row)
                    else:
                        # Normal sin color especial
                        return [''] * len(row)
                
                # Columnas para mostrar
                display_cols = ['Vehículo', 'Matrícula', 'Horómetro Actual', 'Odómetro Actual (km)',
                               'Horas Restantes', 'Km Restantes', 'Estado General']
                
                # Mostrar tabla con colores mejorados
                styled_df = status_df[display_cols].style.apply(style_status_row_improved, axis=1)
                
                st.dataframe(styled_df, use_container_width=True)
                
                # Leyenda de colores
                st.write("**Leyenda de Estados:**")
                col_legend1, col_legend2, col_legend3, col_legend4 = st.columns(4)
                with col_legend1:
                    st.markdown("🔴 **CRÍTICO** - Mantenimiento urgente")
                with col_legend2:
                    st.markdown("🟠 **ADVERTENCIA** - Programar pronto")
                with col_legend3:
                    st.markdown("🟡 **ALERTA** - Monitorear")
                with col_legend4:
                    st.markdown("🟢 **NORMAL** - En rango")
                
                # Mostrar alertas críticas
                critical_machines = status_df[status_df['Estado General'].isin(['CRITICAL', 'WARNING'])]
                
                if not critical_machines.empty:
                    st.subheader("Vehículos que Requieren Atención Inmediata")
                    
                    for _, machine in critical_machines.iterrows():
                        if machine['Estado General'] == 'CRITICAL':
                            alert_type = "🔴 CRÍTICO"
                            alert_color = "error"
                        else:
                            alert_type = "🟡 ADVERTENCIA"
                            alert_color = "warning"
                        
                        # Usar el color correspondiente
                        with st.container():
                            if alert_color == "error":
                                st.error(f"""
                                **{alert_type}: {machine['Vehículo']}** ({machine['Matrícula']})
                                - Horas restantes para mantenimiento: {machine['Horas Restantes']:.1f}
                                - Km restantes para mantenimiento: {machine['Km Restantes']:.1f}
                                """)
                            else:
                                st.warning(f"""
                                **{alert_type}: {machine['Vehículo']}** ({machine['Matrícula']})
                                - Horas restantes para mantenimiento: {machine['Horas Restantes']:.1f}
                                - Km restantes para mantenimiento: {machine['Km Restantes']:.1f}
                                """)
                        
                        if st.button(f"Registrar Mantenimiento para {machine['Vehículo']}", 
                                   key=f"maint_btn_{machine['machine_id']}_{selected_type_id}"):
                            st.session_state[f'quick_maint_{machine["machine_id"]}_{selected_type_id}'] = True
                            st.rerun()
                
                # Mostrar información del tipo seleccionado
                selected_type_info = tipos_df[tipos_df['id'] == selected_type_id].iloc[0]
                st.info(f"""
                **Información del Mantenimiento: {selected_type_info['name']}**
                - Intervalo por defecto: {selected_type_info['default_hours_interval']:.0f} horas / {selected_type_info['default_km_interval']:.0f} km
                """)
                
                # Mostrar tabla detallada opcional
                if st.checkbox("Mostrar información detallada", key="show_detailed_maint"):
                    detailed_cols = ['Vehículo', 'Matrícula', 'Último Mant. Horas', 'Último Mant. Km',
                                   'Próximo Mant. Horas', 'Próximo Mant. Km', 'Intervalo Horas', 'Intervalo Km']
                    
                    st.write("#### Información Detallada de Intervalos")
                    st.dataframe(status_df[detailed_cols], use_container_width=True)
            
            else:
                st.info("No hay datos disponibles para mostrar.")
                
    except Exception as e:
        st.error(f"Error mostrando estado de mantenimientos: {e}")

def mostrar_modulo_configuracion_mejorado(empresa_id):
    """Módulo de configuración mejorado con gestión de intervalos"""
    st.subheader("Configuración del Sistema")
    config_tabs = st.tabs([
        "Tipos de Mantenimiento e Intervalos",
        "Intervalos por Vehículo", 
        "Umbrales de Alertas",
        "Causas de Cambio de Estado",
        "Actualizar Instrumentos"
    ])

    with config_tabs[0]:
        gestionar_tipos_e_intervalos_mantenimiento()
    
    with config_tabs[1]:
        gestionar_intervalos_por_vehiculo(empresa_id)
    
    with config_tabs[2]:
        configuracion_umbrales_alertas()
    
    with config_tabs[3]:
        gestion_causas_cambio_estado_safe()
    
    with config_tabs[4]:
        actualizar_horas_km_safe(empresa_id)

def gestionar_tipos_e_intervalos_mantenimiento():
    """Gestión completa de tipos de mantenimiento con interfaz mejorada"""
    st.subheader("Gestión de Tipos de Mantenimiento e Intervalos")
    
    try:
        with get_conn() as conn:
            # Obtener todos los tipos existentes
            tipos_df = pd.read_sql_query("""
                SELECT id, name, description, default_hours_interval, default_km_interval, is_preventive
                FROM maintenance_types 
                ORDER BY is_preventive DESC, name
            """, conn)
            
            # Pestañas para diferentes acciones
            tab_ver, tab_agregar, tab_editar, tab_eliminar = st.tabs([
                "Ver Tipos", "Agregar Nuevo", "Modificar", "Eliminar"
            ])
            
            # ===== TAB 1: VER TIPOS =====
            with tab_ver:
                if not tipos_df.empty:
                    st.write("### Tipos de Mantenimiento Configurados")
                    
                    # Filtros para visualización
                    col_filter1, col_filter2 = st.columns(2)
                    with col_filter1:
                        show_preventive = st.checkbox("Mostrar Preventivos", value=True, key="show_prev")
                    with col_filter2:
                        show_corrective = st.checkbox("Mostrar Correctivos", value=True, key="show_corr")
                    
                    # Filtrar según selección
                    filtered_df = tipos_df.copy()
                    if not show_preventive:
                        filtered_df = filtered_df[filtered_df['is_preventive'] == 0]
                    if not show_corrective:
                        filtered_df = filtered_df[filtered_df['is_preventive'] == 1]
                    
                    if not filtered_df.empty:
                        # Formatear para mostrar
                        display_df = filtered_df.copy()
                        display_df['Tipo'] = display_df['is_preventive'].apply(
                            lambda x: "Preventivo" if x else "Correctivo"
                        )
                        display_df['Intervalo Horas'] = display_df['default_hours_interval'].apply(
                            lambda x: f"{x:.0f}" if x > 0 else "N/A"
                        )
                        display_df['Intervalo Km'] = display_df['default_km_interval'].apply(
                            lambda x: f"{x:.0f}" if x > 0 else "N/A"
                        )
                        
                        # Mostrar tabla
                        st.dataframe(
                            display_df[['name', 'description', 'Tipo', 'Intervalo Horas', 'Intervalo Km']].rename(columns={
                                'name': 'Nombre',
                                'description': 'Descripción'
                            }),
                            use_container_width=True
                        )
                        
                        # Estadísticas
                        col_stat1, col_stat2, col_stat3 = st.columns(3)
                        with col_stat1:
                            total_tipos = len(tipos_df)
                            st.metric("Total de Tipos", total_tipos)
                        with col_stat2:
                            preventivos = len(tipos_df[tipos_df['is_preventive'] == 1])
                            st.metric("Preventivos", preventivos)
                        with col_stat3:
                            correctivos = len(tipos_df[tipos_df['is_preventive'] == 0])
                            st.metric("Correctivos", correctivos)
                    else:
                        st.info("No hay tipos que coincidan con los filtros seleccionados.")
                else:
                    st.info("No hay tipos de mantenimiento configurados.")
            
            # ===== TAB 2: AGREGAR NUEVO =====
            with tab_agregar:
                st.write("### Crear Nuevo Tipo de Mantenimiento")
                
                with st.form("nuevo_tipo_form"):
                    col_new1, col_new2 = st.columns(2)
                    
                    with col_new1:
                        new_name = st.text_input(
                            "Nombre del Tipo *",
                            placeholder="Ej: Cambio de Aceite",
                            key="new_type_name"
                        )
                        
                        new_description = st.text_area(
                            "Descripción",
                            placeholder="Descripción detallada del tipo de mantenimiento...",
                            key="new_type_desc"
                        )
                        
                        is_preventive = st.radio(
                            "Tipo de Mantenimiento",
                            options=[True, False],
                            format_func=lambda x: "Preventivo" if x else "Correctivo",
                            key="new_type_preventive"
                        )
                    
                    with col_new2:
                        # Intervalos solo para preventivos
                        if is_preventive:
                            st.write("**Intervalos por Defecto**")
                            default_hours = st.number_input(
                                "Intervalo Horas",
                                min_value=1.0,
                                value=5000.0,
                                step=100.0,
                                key="new_type_hours"
                            )
                            
                            default_km = st.number_input(
                                "Intervalo Kilómetros",
                                min_value=1.0,
                                value=5000.0,
                                step=500.0,
                                key="new_type_km"
                            )
                        else:
                            st.info("Los mantenimientos correctivos no requieren intervalos.")
                            default_hours = 0.0
                            default_km = 0.0
                        
                        # Preview del tipo a crear
                        if new_name:
                            st.write("**Vista Previa:**")
                            st.write(f"Nombre: {new_name}")
                            st.write(f"Tipo: {'Preventivo' if is_preventive else 'Correctivo'}")
                            if is_preventive:
                                st.write(f"Intervalos: {default_hours:.0f}h / {default_km:.0f}km")
                    
                    if st.form_submit_button("Crear Tipo de Mantenimiento", type="primary"):
                        if new_name.strip():
                            try:
                                conn.execute("""
                                    INSERT INTO maintenance_types 
                                    (name, description, default_hours_interval, default_km_interval, is_preventive)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (new_name.strip(), new_description.strip(), 
                                      default_hours, default_km, 1 if is_preventive else 0))
                                conn.commit()
                                st.success(f"Tipo '{new_name}' creado exitosamente")
                                st.rerun()
                            except sqlite3.IntegrityError:
                                st.error("Ya existe un tipo de mantenimiento con ese nombre")
                            except Exception as e:
                                st.error(f"Error al crear: {e}")
                        else:
                            st.error("El nombre es obligatorio")
            
            # ===== TAB 3: MODIFICAR =====
            with tab_editar:
                if not tipos_df.empty:
                    st.write("### Modificar Tipo Existente")
                    
                    # Selector de tipo a editar
                    selected_type_id = st.selectbox(
                        "Seleccionar Tipo para Modificar",
                        tipos_df['id'].tolist(),
                        format_func=lambda x: f"{tipos_df[tipos_df['id']==x].iloc[0]['name']} ({'Preventivo' if tipos_df[tipos_df['id']==x].iloc[0]['is_preventive'] else 'Correctivo'})",
                        key="edit_type_select"
                    )
                    
                    if selected_type_id:
                        type_data = tipos_df[tipos_df['id'] == selected_type_id].iloc[0]
                        
                        # Mostrar información actual
                        with st.expander(f"Información Actual: {type_data['name']}", expanded=True):
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.write(f"**Nombre:** {type_data['name']}")
                                st.write(f"**Descripción:** {type_data['description'] or 'Sin descripción'}")
                                st.write(f"**Tipo:** {'Preventivo' if type_data['is_preventive'] else 'Correctivo'}")
                            with col_info2:
                                if type_data['is_preventive']:
                                    st.write(f"**Intervalo Horas:** {type_data['default_hours_interval']:.0f}")
                                    st.write(f"**Intervalo Km:** {type_data['default_km_interval']:.0f}")
                                else:
                                    st.write("**Intervalos:** No aplica (Correctivo)")
                        
                        # Formulario de edición
                        with st.form(f"edit_type_form_{selected_type_id}"):
                            st.write("**Nuevos Valores:**")
                            col_edit1, col_edit2 = st.columns(2)
                            
                            with col_edit1:
                                edit_name = st.text_input(
                                    "Nombre",
                                    value=type_data['name'],
                                    key=f"edit_name_{selected_type_id}"
                                )
                                
                                edit_description = st.text_area(
                                    "Descripción",
                                    value=type_data['description'] or "",
                                    key=f"edit_desc_{selected_type_id}"
                                )
                            
                            with col_edit2:
                                if type_data['is_preventive']:
                                    edit_hours = st.number_input(
                                        "Intervalo Horas",
                                        min_value=1.0,
                                        value=float(type_data['default_hours_interval']),
                                        step=100.0,
                                        key=f"edit_hours_{selected_type_id}"
                                    )
                                    
                                    edit_km = st.number_input(
                                        "Intervalo Kilómetros",
                                        min_value=1.0,
                                        value=float(type_data['default_km_interval']),
                                        step=500.0,
                                        key=f"edit_km_{selected_type_id}"
                                    )
                                else:
                                    edit_hours = 0.0
                                    edit_km = 0.0
                                    st.info("Tipo correctivo - No requiere intervalos")
                            
                            col_btn1, col_btn2 = st.columns(2)
                            with col_btn1:
                                if st.form_submit_button("Guardar Cambios", type="primary"):
                                    if edit_name.strip():
                                        try:
                                            conn.execute("""
                                                UPDATE maintenance_types 
                                                SET name = ?, description = ?, default_hours_interval = ?, default_km_interval = ?
                                                WHERE id = ?
                                            """, (edit_name.strip(), edit_description.strip(), 
                                                  edit_hours, edit_km, selected_type_id))
                                            conn.commit()
                                            st.success("Tipo actualizado exitosamente")
                                            st.rerun()
                                        except sqlite3.IntegrityError:
                                            st.error("Ya existe un tipo con ese nombre")
                                        except Exception as e:
                                            st.error(f"Error al actualizar: {e}")
                                    else:
                                        st.error("El nombre no puede estar vacío")
                            
                            with col_btn2:
                                if st.form_submit_button("Resetear a Valores Originales"):
                                    st.rerun()
                else:
                    st.info("No hay tipos de mantenimiento para modificar.")
            
            # ===== TAB 4: ELIMINAR =====
            with tab_eliminar:
                if not tipos_df.empty:
                    st.write("### Eliminar Tipo de Mantenimiento")
                    st.warning("**Advertencia:** Esta acción no se puede deshacer. Asegúrese de que el tipo no esté siendo utilizado.")
                    
                    # Selector de tipo a eliminar
                    delete_type_id = st.selectbox(
                        "Seleccionar Tipo para Eliminar",
                        [None] + tipos_df['id'].tolist(),
                        format_func=lambda x: "-- Seleccionar --" if x is None else f"{tipos_df[tipos_df['id']==x].iloc[0]['name']} ({'Preventivo' if tipos_df[tipos_df['id']==x].iloc[0]['is_preventive'] else 'Correctivo'})",
                        key="delete_type_select"
                    )
                    
                    if delete_type_id:
                        delete_type_data = tipos_df[tipos_df['id'] == delete_type_id].iloc[0]
                        
                        # Mostrar información del tipo a eliminar
                        st.error(f"""
                        **Tipo a Eliminar:**
                        - Nombre: {delete_type_data['name']}
                        - Descripción: {delete_type_data['description'] or 'Sin descripción'}
                        - Tipo: {'Preventivo' if delete_type_data['is_preventive'] else 'Correctivo'}
                        """)
                        
                        # Verificar si está en uso
                        try:
                            # Verificar en maintenance_records
                            records_count = conn.execute("""
                                SELECT COUNT(*) FROM maintenance_records WHERE maintenance_type_id = ?
                            """, (delete_type_id,)).fetchone()[0]
                            
                            # Verificar en maintenance_intervals
                            intervals_count = conn.execute("""
                                SELECT COUNT(*) FROM maintenance_intervals WHERE maintenance_type_id = ?
                            """, (delete_type_id,)).fetchone()[0]
                            
                            # Verificar en maintenance_schedules
                            schedules_count = conn.execute("""
                                SELECT COUNT(*) FROM maintenance_schedules WHERE maintenance_type_id = ?
                            """, (delete_type_id,)).fetchone()[0]
                            
                            total_usage = records_count + intervals_count + schedules_count
                            
                            if total_usage > 0:
                                # Mostrar detalles de uso
                                st.error(f"""
                                **Este tipo está siendo utilizado:**
                                - Registros de mantenimiento: {records_count}
                                - Intervalos configurados: {intervals_count}
                                - Mantenimientos programados: {schedules_count}
                                """)
                                
                                # Opciones para manejar la eliminación
                                if records_count > 0 or schedules_count > 0:
                                    st.error("No se puede eliminar porque tiene registros de mantenimiento o programaciones activas.")
                                else:
                                    # Solo tiene intervalos configurados - permitir eliminación forzada
                                    st.warning("Solo tiene intervalos configurados (sin registros históricos).")
                                    
                                    force_delete = st.checkbox(
                                        "Eliminar automáticamente todos los intervalos y el tipo",
                                        key="force_delete_checkbox"
                                    )
                                    
                                    if force_delete:
                                        confirm_force = st.checkbox(
                                            f"Confirmo que quiero eliminar '{delete_type_data['name']}' y TODOS sus intervalos configurados",
                                            key="confirm_force_delete"
                                        )
                                        
                                        if confirm_force:
                                            if st.button("ELIMINAR TIPO E INTERVALOS", type="primary", key="force_delete_btn"):
                                                try:
                                                    # Eliminar intervalos primero
                                                    conn.execute("DELETE FROM maintenance_intervals WHERE maintenance_type_id = ?", (delete_type_id,))
                                                    # Luego eliminar el tipo
                                                    conn.execute("DELETE FROM maintenance_types WHERE id = ?", (delete_type_id,))
                                                    conn.commit()
                                                    st.success(f"Tipo '{delete_type_data['name']}' y sus {intervals_count} intervalos eliminados exitosamente")
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Error al eliminar: {e}")
                            else:
                                st.success("Este tipo no está siendo utilizado y se puede eliminar con seguridad.")
                                
                                # Confirmación de eliminación normal
                                confirm_delete = st.checkbox(
                                    f"Confirmo que quiero eliminar permanentemente el tipo '{delete_type_data['name']}'",
                                    key="confirm_delete_checkbox"
                                )
                                
                                if confirm_delete:
                                    if st.button("ELIMINAR PERMANENTEMENTE", type="primary", key="final_delete_btn"):
                                        try:
                                            conn.execute("DELETE FROM maintenance_types WHERE id = ?", (delete_type_id,))
                                            conn.commit()
                                            st.success(f"Tipo '{delete_type_data['name']}' eliminado exitosamente")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error al eliminar: {e}")
                        
                        except Exception as e:
                            st.error(f"Error verificando uso del tipo: {e}")
                else:
                    st.info("No hay tipos de mantenimiento para eliminar.")
                    
    except Exception as e:
        st.error(f"Error en gestión de tipos: {e}")
        st.write("Detalles del error:", str(e))

def gestionar_intervalos_por_vehiculo(empresa_id):
    """Permite configurar intervalos específicos por vehículo"""
    st.subheader("Intervalos de Mantenimiento por Vehículo")
    
    try:
        machinery_df = safe_get_machinery_data(empresa_id)
        if machinery_df.empty:
            st.info("No hay vehículos registrados.")
            return
        
        with get_conn() as conn:
            # Selector de vehículo
            selected_machine = st.selectbox(
                "Seleccionar Vehículo",
                machinery_df['id'].tolist(),
                format_func=lambda x: f"{machinery_df[machinery_df['id']==x].iloc[0]['name']} ({machinery_df[machinery_df['id']==x].iloc[0].get('identifier', 'N/A')})",
                key="select_machine_intervals"
            )
            
            if selected_machine:
                # Obtener intervalos actuales para este vehículo
                intervals_query = """
                    SELECT mi.*, mt.name as type_name, mt.default_hours_interval, mt.default_km_interval
                    FROM maintenance_intervals mi
                    JOIN maintenance_types mt ON mi.maintenance_type_id = mt.id
                    WHERE mi.machinery_id = ? AND mt.is_preventive = 1
                    ORDER BY mt.name
                """
                intervals_df = pd.read_sql_query(intervals_query, conn, params=(selected_machine,))
                
                # Obtener tipos que no tienen intervalos configurados
                missing_types_query = """
                    SELECT mt.id, mt.name, mt.default_hours_interval, mt.default_km_interval
                    FROM maintenance_types mt
                    WHERE mt.is_preventive = 1 
                    AND mt.id NOT IN (
                        SELECT maintenance_type_id 
                        FROM maintenance_intervals 
                        WHERE machinery_id = ?
                    )
                """
                missing_df = pd.read_sql_query(missing_types_query, conn, params=(selected_machine,))
                
                # Agregar intervalos faltantes con valores por defecto
                if not missing_df.empty:
                    for _, missing_type in missing_df.iterrows():
                        conn.execute("""
                            INSERT INTO maintenance_intervals 
                            (machinery_id, maintenance_type_id, hours_interval, km_interval)
                            VALUES (?, ?, ?, ?)
                        """, (selected_machine, missing_type['id'], 
                              missing_type['default_hours_interval'],
                              missing_type['default_km_interval']))
                    conn.commit()
                    st.rerun()
                
                # Recargar intervalos después de agregar los faltantes
                intervals_df = pd.read_sql_query(intervals_query, conn, params=(selected_machine,))
                
                if not intervals_df.empty:
                    st.write(f"### Configuración de Intervalos")
                    
                    # Mostrar y permitir editar cada intervalo
                    for _, interval in intervals_df.iterrows():
                        with st.expander(f"{interval['type_name']}", expanded=False):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Intervalo Actual (horas)", f"{interval['hours_interval']:.0f}")
                                st.metric("Por Defecto (horas)", f"{interval['default_hours_interval']:.0f}")
                            
                            with col2:
                                st.metric("Intervalo Actual (km)", f"{interval['km_interval']:.0f}")
                                st.metric("Por Defecto (km)", f"{interval['default_km_interval']:.0f}")
                            
                            with col3:
                                st.metric("Estado", "Activo" if interval['is_active'] else "Inactivo")
                            
                            # Formulario para editar
                            with st.form(f"edit_interval_{interval['id']}"):
                                col_a, col_b = st.columns(2)
                                
                                with col_a:
                                    new_hours = st.number_input(
                                        "Nuevo intervalo (horas)",
                                        min_value=0.0,
                                        value=float(interval['hours_interval']),
                                        step=100.0,
                                        key=f"hours_{interval['id']}"
                                    )
                                
                                with col_b:
                                    new_km = st.number_input(
                                        "Nuevo intervalo (km)",
                                        min_value=0.0,
                                        value=float(interval['km_interval']),
                                        step=500.0,
                                        key=f"km_{interval['id']}"
                                    )
                                
                                col_x, col_y, col_z = st.columns(3)
                                
                                with col_x:
                                    if st.form_submit_button("Actualizar"):
                                        conn.execute("""
                                            UPDATE maintenance_intervals 
                                            SET hours_interval = ?, km_interval = ?, updated_at = CURRENT_TIMESTAMP
                                            WHERE id = ?
                                        """, (new_hours, new_km, interval['id']))
                                        conn.commit()
                                        st.success("Intervalo actualizado")
                                        st.rerun()
                                
                                with col_y:
                                    if st.form_submit_button("Usar Valores por Defecto"):
                                        conn.execute("""
                                            UPDATE maintenance_intervals 
                                            SET hours_interval = ?, km_interval = ?, updated_at = CURRENT_TIMESTAMP
                                            WHERE id = ?
                                        """, (interval['default_hours_interval'], 
                                              interval['default_km_interval'], 
                                              interval['id']))
                                        conn.commit()
                                        st.success("Valores por defecto aplicados")
                                        st.rerun()
                                
                                with col_z:
                                    new_status = not interval['is_active']
                                    action_text = "Activar" if new_status else "Desactivar"
                                    if st.form_submit_button(action_text):
                                        conn.execute("""
                                            UPDATE maintenance_intervals 
                                            SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                                            WHERE id = ?
                                        """, (1 if new_status else 0, interval['id']))
                                        conn.commit()
                                        st.success(f"Intervalo {action_text.lower()}do")
                                        st.rerun()
                else:
                    st.info("No hay intervalos configurados para este vehículo.")
                    
    except Exception as e:
        st.error(f"Error gestionando intervalos por vehículo: {e}")

def configuracion_umbrales_alertas():
    """Configuración de umbrales de alertas - CORREGIDA para la estructura real de la tabla"""
    st.subheader("Configuración de Umbrales de Alertas")
    
    try:
        with get_conn() as conn:
            # Obtener todas las configuraciones
            config_df = pd.read_sql_query("""
                SELECT id, config_type, config_key, config_value, warning_threshold, alert_threshold, critical_threshold, is_active
                FROM alert_configurations
                WHERE config_type = 'maintenance_alerts'
                ORDER BY config_key
            """, conn)
            
            if config_df.empty:
                # Crear configuraciones por defecto usando la estructura real
                conn.execute("""
                    INSERT INTO alert_configurations 
                    (config_type, config_key, config_value, warning_threshold, alert_threshold, critical_threshold, is_active)
                    VALUES ('maintenance_alerts', 'hours_before_maintenance', 'Alertas de horómetro', 200, 100, 50, 1)
                """)
                conn.execute("""
                    INSERT INTO alert_configurations 
                    (config_type, config_key, config_value, warning_threshold, alert_threshold, critical_threshold, is_active)
                    VALUES ('maintenance_alerts', 'km_before_maintenance', 'Alertas de odómetro', 500, 300, 100, 1)
                """)
                conn.commit()
                st.success("Configuraciones por defecto creadas")
                st.rerun()
            
            st.write("""
            ### Configuración de Umbrales
            
            Los umbrales determinan cuándo mostrar alertas antes de que se cumpla el intervalo de mantenimiento:
            - **Advertencia**: Primera notificación (ej: 500 km antes)
            - **Alerta**: Notificación más visible (ej: 300 km antes)  
            - **Crítico**: Alerta urgente (ej: 100 km antes)
            """)
            
            # Configurar horas
            hours_config = config_df[config_df['config_key'] == 'hours_before_maintenance']
            if not hours_config.empty:
                hours_row = hours_config.iloc[0]
                
                st.write("#### Umbrales para Horómetro")
                with st.form("config_hours_thresholds"):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        warning_h = st.number_input(
                            "Advertencia (horas antes)",
                            min_value=1,
                            value=int(hours_row['warning_threshold']),
                            step=10,
                            key="warning_hours_thresh"
                        )
                    
                    with col2:
                        alert_h = st.number_input(
                            "Alerta (horas antes)",
                            min_value=1,
                            value=int(hours_row['alert_threshold']),
                            step=10,
                            key="alert_hours_thresh"
                        )
                    
                    with col3:
                        critical_h = st.number_input(
                            "Crítico (horas antes)",
                            min_value=1,
                            value=int(hours_row['critical_threshold']),
                            step=10,
                            key="critical_hours_thresh"
                        )
                    
                    with col4:
                        active_h = st.checkbox(
                            "Alertas activas",
                            value=bool(hours_row['is_active']),
                            key="active_hours_thresh"
                        )
                    
                    if st.form_submit_button("Actualizar Umbrales de Horómetro"):
                        if warning_h > alert_h > critical_h:
                            conn.execute("""
                                UPDATE alert_configurations 
                                SET warning_threshold = ?, alert_threshold = ?, critical_threshold = ?, is_active = ?
                                WHERE id = ?
                            """, (warning_h, alert_h, critical_h, 1 if active_h else 0, hours_row['id']))
                            conn.commit()
                            st.success("Umbrales de horómetro actualizados")
                            st.rerun()
                        else:
                            st.error("Los umbrales deben ser: Advertencia > Alerta > Crítico")
            else:
                # Si no existe, crear la configuración para horas
                st.write("#### Crear Configuración para Horómetro")
                with st.form("create_hours_config"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        new_warning_h = st.number_input("Advertencia (horas)", value=200, step=10, key="new_warning_h")
                    with col2:
                        new_alert_h = st.number_input("Alerta (horas)", value=100, step=10, key="new_alert_h")
                    with col3:
                        new_critical_h = st.number_input("Crítico (horas)", value=50, step=10, key="new_critical_h")
                    
                    if st.form_submit_button("Crear Configuración de Horómetro"):
                        conn.execute("""
                            INSERT INTO alert_configurations 
                            (config_type, config_key, config_value, warning_threshold, alert_threshold, critical_threshold, is_active)
                            VALUES ('maintenance_alerts', 'hours_before_maintenance', 'Alertas de horómetro', ?, ?, ?, 1)
                        """, (new_warning_h, new_alert_h, new_critical_h))
                        conn.commit()
                        st.success("Configuración de horómetro creada")
                        st.rerun()
            
            # Configurar kilómetros
            km_config = config_df[config_df['config_key'] == 'km_before_maintenance']
            if not km_config.empty:
                km_row = km_config.iloc[0]
                
                st.write("#### Umbrales para Odómetro")
                with st.form("config_km_thresholds"):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        warning_k = st.number_input(
                            "Advertencia (km antes)",
                            min_value=1,
                            value=int(km_row['warning_threshold']),
                            step=50,
                            key="warning_km_thresh"
                        )
                    
                    with col2:
                        alert_k = st.number_input(
                            "Alerta (km antes)",
                            min_value=1,
                            value=int(km_row['alert_threshold']),
                            step=50,
                            key="alert_km_thresh"
                        )
                    
                    with col3:
                        critical_k = st.number_input(
                            "Crítico (km antes)",
                            min_value=1,
                            value=int(km_row['critical_threshold']),
                            step=10,
                            key="critical_km_thresh"
                        )
                    
                    with col4:
                        active_k = st.checkbox(
                            "Alertas activas",
                            value=bool(km_row['is_active']),
                            key="active_km_thresh"
                        )
                    
                    if st.form_submit_button("Actualizar Umbrales de Odómetro"):
                        if warning_k > alert_k > critical_k:
                            conn.execute("""
                                UPDATE alert_configurations 
                                SET warning_threshold = ?, alert_threshold = ?, critical_threshold = ?, is_active = ?
                                WHERE id = ?
                            """, (warning_k, alert_k, critical_k, 1 if active_k else 0, km_row['id']))
                            conn.commit()
                            st.success("Umbrales de odómetro actualizados")
                            st.rerun()
                        else:
                            st.error("Los umbrales deben ser: Advertencia > Alerta > Crítico")
            else:
                # Si no existe, crear la configuración para km
                st.write("#### Crear Configuración para Odómetro")
                with st.form("create_km_config"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        new_warning_k = st.number_input("Advertencia (km)", value=500, step=50, key="new_warning_k")
                    with col2:
                        new_alert_k = st.number_input("Alerta (km)", value=300, step=50, key="new_alert_k")
                    with col3:
                        new_critical_k = st.number_input("Crítico (km)", value=100, step=10, key="new_critical_k")
                    
                    if st.form_submit_button("Crear Configuración de Odómetro"):
                        conn.execute("""
                            INSERT INTO alert_configurations 
                            (config_type, config_key, config_value, warning_threshold, alert_threshold, critical_threshold, is_active)
                            VALUES ('maintenance_alerts', 'km_before_maintenance', 'Alertas de odómetro', ?, ?, ?, 1)
                        """, (new_warning_k, new_alert_k, new_critical_k))
                        conn.commit()
                        st.success("Configuración de odómetro creada")
                        st.rerun()
            
            # Mostrar configuraciones actuales
            if not config_df.empty:
                st.write("#### Configuraciones Actuales")
                display_df = config_df[['config_key', 'config_value', 'warning_threshold', 'alert_threshold', 'critical_threshold', 'is_active']].copy()
                display_df = display_df.rename(columns={
                    'config_key': 'Tipo',
                    'config_value': 'Descripción',
                    'warning_threshold': 'Advertencia',
                    'alert_threshold': 'Alerta',
                    'critical_threshold': 'Crítico',
                    'is_active': 'Activo'
                })
                st.dataframe(display_df, use_container_width=True)
            
            # Mostrar ejemplo
            st.write("#### Ejemplo de Funcionamiento")
            st.info("""
            **Ejemplo con intervalo de 5000 km y umbrales configurados:**
            - Si el último mantenimiento fue a los 10000 km
            - El próximo mantenimiento será a los 15000 km
            - Con umbral de advertencia de 500 km: alerta a los 14500 km
            - Con umbral de alerta de 300 km: alerta a los 14700 km
            - Con umbral crítico de 100 km: alerta a los 14900 km
            """)
            
    except Exception as e:
        st.error(f"Error en configuración de umbrales: {e}")
        # Mostrar información de debug
        with get_conn() as conn:
            try:
                cur = conn.cursor()
                cur.execute("PRAGMA table_info(alert_configurations)")
                columns = [row[1] for row in cur.fetchall()]
                st.error(f"Columnas disponibles en alert_configurations: {columns}")
                
                # Mostrar contenido actual de la tabla
                cur.execute("SELECT * FROM alert_configurations LIMIT 5")
                data = cur.fetchall()
                if data:
                    st.write("Contenido actual de la tabla:")
                    for row in data:
                        st.write(row)
            except Exception as debug_e:
                st.error(f"No se pudo obtener información de la tabla: {debug_e}")
                
def gestion_causas_cambio_estado_safe():
    """Gestión de causas de cambio de estado - versión segura"""
    st.subheader("Gestión de Causas de Cambio de Estado")
    try:
        with get_conn() as conn:
            causas_df = pd.read_sql_query("""
                SELECT id, name, description, applies_to, is_active 
                FROM status_change_reasons 
                ORDER BY applies_to, name
            """, conn)
            
            if not causas_df.empty:
                # Interfaz compacta con expander
                with st.expander("Ver y Gestionar Causas Existentes", expanded=False):
                    
                    # Agrupar por applies_to para mejor organización
                    for applies_to in causas_df['applies_to'].unique():
                        st.write(f"**Causas para Estado: {applies_to}**")
                        
                        causas_grupo = causas_df[causas_df['applies_to'] == applies_to]
                        
                        for _, causa in causas_grupo.iterrows():
                            col1, col2, col3 = st.columns([4, 1, 1])
                            
                            with col1:
                                status_indicator = "🟢" if causa['is_active'] else "🔴"
                                st.write(f"{status_indicator} **{causa['name']}** - {causa['description']}")
                            
                            with col2:
                                new_status = 0 if causa['is_active'] else 1
                                action = "Desactivar" if causa['is_active'] else "Activar"
                                
                                if st.button(action, key=f"toggle_causa_{causa['id']}", help=f"{action} esta causa"):
                                    conn.execute("UPDATE status_change_reasons SET is_active = ? WHERE id = ?", 
                                               (new_status, causa['id']))
                                    conn.commit()
                                    st.rerun()
                            
                            with col3:
                                if st.button("🗑️", key=f"del_causa_{causa['id']}", help="Eliminar causa"):
                                    try:
                                        conn.execute("DELETE FROM status_change_reasons WHERE id = ?", (causa['id'],))
                                        conn.commit()
                                        st.rerun()
                                    except sqlite3.IntegrityError:
                                        st.error("No se puede eliminar: está siendo utilizada")
                            
                            st.divider()
            
            # Formulario para nueva causa
            st.subheader("Agregar Nueva Causa")
            
            with st.form("nueva_causa_safe"):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("Nombre de la Causa", key="new_cause_name")
                    new_description = st.text_area("Descripción", key="new_cause_desc")
                with col2:
                    applies_to_options = ["ALL", "Activa", "Mantenimiento", "Inactiva"]
                    new_applies_to = st.selectbox("Aplica al Estado", applies_to_options, key="new_cause_applies")
                
                if st.form_submit_button("Agregar Causa"):
                    if new_name.strip():
                        try:
                            conn.execute("""
                                INSERT INTO status_change_reasons (name, description, applies_to) 
                                VALUES (?, ?, ?)
                            """, (new_name.strip(), new_description.strip(), new_applies_to))
                            conn.commit()
                            st.success("Causa agregada correctamente")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Esta causa ya existe")
                        except Exception as e:
                            st.error(f"Error al agregar: {str(e)}")
                    else:
                        st.error("El nombre es obligatorio")
                        
    except Exception as e:
        st.error(f"Error en gestión de causas: {e}")

def actualizar_horas_km_safe(empresa_id):
    """Actualización de lecturas de instrumentos - versión segura corregida"""
    st.subheader("Actualización de Instrumentos de Medición")
    machinery_df = safe_get_machinery_data(empresa_id)
    if machinery_df.empty:
        st.info("No hay vehículos registrados.")
        return

    try:
        # Selector de vehículo
        selected_machine_id = st.selectbox(
            "Seleccionar Vehículo",
            machinery_df['id'].tolist(),
            format_func=lambda x: f"{machinery_df[machinery_df['id']==x].iloc[0]['name']} ({machinery_df[machinery_df['id']==x].iloc[0].get('identifier', 'N/A')})",
            key="select_machine_update_safe"
        )
        
        if selected_machine_id:
            machine_data = machinery_df[machinery_df['id'] == selected_machine_id].iloc[0]
            
            # Obtener valores actuales de forma segura
            try:
                from db_utils import get_machine_current_values
                current_values = get_machine_current_values(selected_machine_id)
                
                # Manejar caso donde no existan las claves
                current_hours = current_values.get('current_hours', 0.0)
                
                # CORRECCIÓN: Manejar diferentes nombres de clave posibles para odómetro
                current_km = current_values.get('current_odometer', 0.0)
                if current_km == 0:  # Si no existe, probar nombres alternativos
                    current_km = current_values.get('odometer', 0.0)
                
                # Si aún no hay valores, usar los de machinery_df como fallback
                if current_hours == 0.0:
                    current_hours = float(machine_data.get('current_hours', 0.0))
                if current_km == 0.0:
                    current_km = float(machine_data.get('current_odometer', 0.0) or 0.0)
                
            except Exception as e:
                st.warning(f"Error obteniendo valores actuales: {e}")
                # Usar valores del DataFrame como fallback
                current_hours = float(machine_data.get('current_hours', 0.0))
                current_km = float(machine_data.get('current_odometer', 0.0) or 0.0)
            
            # Mostrar valores actuales
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Horómetro Actual", f"{current_hours:.1f} horas")
            
            with col2:
                st.metric("Odómetro Actual", f"{current_km:.1f} km")
            
            with col3:
                st.metric("Estado Operacional", machine_data.get('status', 'N/A'))
            
            # Formulario de actualización
            with st.form("actualizar_instrumentos_safe"):
                st.subheader("Nuevas Lecturas de Instrumentos")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    new_hours = st.number_input(
                        "Nueva Lectura del Horómetro",
                        min_value=current_hours,
                        value=current_hours,
                        step=0.1,
                        format="%.1f",
                        help="El horómetro solo puede incrementar",
                        key="new_hours_input"
                    )
                
                with col2:
                    new_km = st.number_input(
                        "Nueva Lectura del Odómetro (km)",
                        min_value=current_km,
                        value=current_km,
                        step=0.1,
                        format="%.1f",
                        help="El odómetro solo puede incrementar",
                        key="new_km_input"
                    )
                
                notes = st.text_area(
                    "Observaciones sobre la Actualización",
                    placeholder="Motivo de la actualización, observaciones técnicas...",
                    key="update_notes"
                )
                
                recorded_by = st.text_input(
                    "Registrado por",
                    value=st.session_state.get("username", "admin"),
                    key="recorded_by_input"
                )
                
                if st.form_submit_button("Actualizar Lecturas"):
                    try:
                        # Validar que los valores sean mayores o iguales
                        if new_hours < current_hours:
                            st.error("El horómetro no puede retroceder")
                            return
                        
                        if new_km < current_km:
                            st.error("El odómetro no puede retroceder")
                            return
                        
                        with get_conn() as conn:
                            # Actualizar tabla machinery
                            conn.execute("""
                                UPDATE machinery 
                                SET current_hours = ?, current_odometer = ?
                                WHERE id = ?
                            """, (new_hours, new_km, selected_machine_id))
                            
                            # Registrar en log de horómetro si cambió
                            if new_hours != current_hours:
                                # Crear tabla de logs si no existe
                                conn.execute("""
                                    CREATE TABLE IF NOT EXISTS hour_meter_logs (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        machinery_id INTEGER,
                                        current_hours REAL NOT NULL,
                                        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                        recorded_by TEXT,
                                        notes TEXT,
                                        FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE
                                    )
                                """)
                                
                                conn.execute("""
                                    INSERT INTO hour_meter_logs 
                                    (machinery_id, current_hours, recorded_by, notes)
                                    VALUES (?, ?, ?, ?)
                                """, (selected_machine_id, new_hours, recorded_by, notes))
                            
                            # Registrar en log de odómetro si cambió
                            if new_km != current_km:
                                # Crear tabla de logs si no existe
                                conn.execute("""
                                    CREATE TABLE IF NOT EXISTS odometer_logs (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        machinery_id INTEGER,
                                        current_km REAL NOT NULL,
                                        recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                        recorded_by TEXT,
                                        notes TEXT,
                                        FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE
                                    )
                                """)
                                
                                conn.execute("""
                                    INSERT INTO odometer_logs 
                                    (machinery_id, current_km, recorded_by, notes)
                                    VALUES (?, ?, ?, ?)
                                """, (selected_machine_id, new_km, recorded_by, notes))
                            
                            conn.commit()
                            st.success("Lecturas actualizadas correctamente")
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error al actualizar: {str(e)}")
                        
    except Exception as e:
        st.error(f"Error en actualización de instrumentos: {e}")
# Funciones adicionales necesarias para el funcionamiento completo

def mostrar_modulo_general_safe(empresa_id, machinery_df):
    """Dashboard general del sistema con alertas de mantenimientos programados - CORREGIDO"""
    st.subheader("Dashboard General del Sistema")
    if machinery_df.empty:
        st.info("No hay vehículos registrados en el sistema.")
        return

    try:
        # Asegurar que existe la tabla de compliance
        from db_utils import create_maintenance_compliance_table
        create_maintenance_compliance_table()
        
        # Normalizar estados
        def safe_normalize_status(status):
            if pd.isna(status):
                return 'Active'
            status_map = {
                'Activo': 'Active', 'Activa': 'Active', 'Active': 'Active',
                'Mantenimiento': 'Maintenance', 'Maintenance': 'Maintenance',
                'Inactivo': 'Inactive', 'Inactiva': 'Inactive', 'Inactive': 'Inactive'
            }
            return status_map.get(str(status).strip(), 'Active')
        
        machinery_df['status_norm'] = machinery_df['status'].apply(safe_normalize_status)
        
        # Tarjetas de resumen
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            active_count = len(machinery_df[machinery_df['status_norm'] == 'Active'])
            st.metric("Vehículos Operativos", active_count)
        
        with col2:
            maintenance_count = len(machinery_df[machinery_df['status_norm'] == 'Maintenance'])
            st.metric("En Mantenimiento", maintenance_count)
        
        with col3:
            inactive_count = len(machinery_df[machinery_df['status_norm'] == 'Inactive'])
            st.metric("Fuera de Servicio", inactive_count)
        
        with col4:
            total_count = len(machinery_df)
            st.metric("Total de Vehículos", total_count)
        
        # NUEVA SECCIÓN: Alertas de Mantenimientos Programados
        st.subheader("Alertas de Mantenimientos Programados")
        
        from db_utils import get_upcoming_scheduled_maintenances, get_overdue_scheduled_maintenances
        
        # Obtener mantenimientos próximos y vencidos
        upcoming_df = get_upcoming_scheduled_maintenances(empresa_id, days_ahead=7)
        overdue_df = get_overdue_scheduled_maintenances(empresa_id)
        
        col_alert1, col_alert2 = st.columns(2)
        
        with col_alert1:
            if not overdue_df.empty:
                st.error(f"🚨 {len(overdue_df)} Mantenimientos Vencidos")
                for _, maint in overdue_df.head(3).iterrows():
                    dias_vencido = int(maint['dias_vencido'])
                    st.error(f"""
                    **{maint['vehiculo']}** - {maint['tipo_mantenimiento']}
                    Vencido hace {dias_vencido} día{'s' if dias_vencido != 1 else ''}
                    """)
                
                if len(overdue_df) > 3:
                    st.error(f"... y {len(overdue_df) - 3} más. Ve a 'Mantenimientos Programados' para ver todos.")
            else:
                st.success("✅ No hay mantenimientos vencidos")
        
        with col_alert2:
            if not upcoming_df.empty:
                st.warning(f"⚠️ {len(upcoming_df)} Mantenimientos Próximos (7 días)")
                for _, maint in upcoming_df.head(3).iterrows():
                    dias_restantes = int(maint['dias_restantes'])
                    if dias_restantes <= 0:
                        fecha_text = "Hoy"
                    elif dias_restantes == 1:
                        fecha_text = "Mañana"
                    else:
                        fecha_text = f"En {dias_restantes} días"
                    
                    st.warning(f"""
                    **{maint['vehiculo']}** - {maint['tipo_mantenimiento']}
                    {fecha_text} ({maint['scheduled_start_date']})
                    """)
                
                if len(upcoming_df) > 3:
                    st.warning(f"... y {len(upcoming_df) - 3} más.")
            else:
                st.info("ℹ️ No hay mantenimientos próximos")
        
        # Alertas de mantenimiento preventivo (si existe la función)
        try:
            with get_conn() as conn:
                preventive_types = pd.read_sql_query("""
                    SELECT id FROM maintenance_types WHERE is_preventive = 1 LIMIT 1
                """, conn)
                
                if not preventive_types.empty and 'get_maintenance_status_for_machine' in globals():
                    main_type_id = preventive_types.iloc[0]['id']
                    
                    alerts = []
                    for _, machine in machinery_df.iterrows():
                        current_hours = float(machine.get('current_hours', 0))
                        current_km = float(machine.get('current_odometer', 0))
                        
                        status = get_maintenance_status_for_machine(
                            machine['id'], main_type_id, current_hours, current_km
                        )
                        
                        if status and status['overall_status'] in ['CRITICAL', 'WARNING']:
                            alerts.append({
                                'name': machine['name'],
                                'identifier': machine.get('identifier', 'N/A'),
                                'status': status['overall_status'],
                                'hours_remaining': status['hours_remaining'],
                                'km_remaining': status['km_remaining']
                            })
                    
                    if alerts:
                        st.subheader("Alertas de Mantenimiento Preventivo")
                        for alert in alerts:
                            alert_color = "error" if alert['status'] == 'CRITICAL' else "warning"
                            getattr(st, alert_color)(f"""
                            **{alert['name']}** ({alert['identifier']}) - {alert['status']}
                            - Horas restantes: {alert['hours_remaining']:.1f}
                            - Km restantes: {alert['km_remaining']:.1f}
                            """)
        except Exception as e:
            # Si hay error con las alertas preventivas, solo mostrar mensaje de debug
            st.info("Alertas preventivas no disponibles (función get_maintenance_status_for_machine no encontrada)")
        
        # Tabla de estado actual
        st.subheader("Estado Actual de la Flota")
        
        display_columns = {
            'name': 'Vehículo',
            'identifier': 'Matrícula', 
            'classification': 'Clasificación',
            'status': 'Estado',
            'current_hours': 'Horas',
            'current_odometer': 'Kilómetros'
        }
        
        available_columns = [col for col in display_columns.keys() if col in machinery_df.columns]
        display_df = machinery_df[available_columns].copy()
        
        for col in ['current_hours', 'current_odometer']:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce').fillna(0).round(1)
        
        display_df = display_df.rename(columns={k: v for k, v in display_columns.items() if k in available_columns})
        
        def highlight_status(row):
            if row.get('Estado', '') == 'Mantenimiento':
                return ['background-color: #fff8e1'] * len(row)
            elif row.get('Estado', '') == 'Inactiva':
                return ['background-color: #f3e5f5'] * len(row)
            else:
                return [''] * len(row)
        
        st.dataframe(
            display_df.style.apply(highlight_status, axis=1),
            use_container_width=True
        )
        
        # Gráfico de distribución de estados
        if 'status' in machinery_df.columns:
            st.subheader("Distribución de Estados")
            status_counts = machinery_df['status'].value_counts()
            
            fig = go.Figure(data=[
                go.Bar(
                    y=status_counts.index,
                    x=status_counts.values,
                    orientation='h',
                    marker_color=['#4CAF50' if status == 'Activa' 
                                 else '#FF9800' if status == 'Mantenimiento'
                                 else '#9E9E9E' for status in status_counts.index],
                    text=status_counts.values,
                    textposition='auto',
                    hoverinfo='x+y',
                    hovertemplate='<b>%{y}</b>: %{x} vehículos<extra></extra>'
                )
            ])
            
            fig.update_layout(
                title="Distribución de Estados Operacionales",
                xaxis_title="Cantidad de Vehículos",
                yaxis_title="Estado",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"Error al mostrar dashboard: {e}")


def mostrar_modulo_estados_safe(empresa_id, machinery_df):
    """Versión segura del módulo de estados con registro automático de mantenimiento mejorado"""
    st.subheader("Gestión de Estados Operacionales")
    if machinery_df.empty:
        st.info("No hay vehículos registrados.")
        return

    try:
        # Selector de vehículo
        machine_options = [(row['id'], f"{row['name']} ({row.get('identifier', 'N/A')})") 
                          for _, row in machinery_df.iterrows()]
        
        if not machine_options:
            st.warning("No se pudieron cargar los vehículos.")
            return
        
        selected_id = st.selectbox(
            "Seleccionar Vehículo",
            options=[opt[0] for opt in machine_options],
            format_func=lambda x: next((opt[1] for opt in machine_options if opt[0] == x), "N/A"),
            key="select_machine_status_safe"
        )
        
        if selected_id:
            machine_data = machinery_df[machinery_df['id'] == selected_id].iloc[0]
            
            # Obtener lecturas actuales para validación - CORREGIDO
            from db_utils import get_machine_current_values
            current_values = get_machine_current_values(selected_id)
            
            # Manejar diferentes nombres de claves de forma segura
            current_hours = current_values.get('current_hours', 0.0)
            current_km = (current_values.get('current_odometer', 0.0) or 
                         current_values.get('current_km', 0.0) or 
                         current_values.get('odometer', 0.0))
            
            # Si aún no tiene valores, usar los de machinery_df como fallback
            if current_hours == 0.0:
                current_hours = float(machine_data.get('current_hours', 0.0))
            if current_km == 0.0:
                current_km = float(machine_data.get('current_odometer', 0.0) or 
                                 machine_data.get('current_km', 0.0))
            
            # Información actual
            col1, col2, col3 = st.columns(3)
            with col1:
                current_status = machine_data.get('status', 'Activa')
                st.metric("Estado Actual", current_status)
            
            with col2:
                last_change = machine_data.get('last_status_change')
                if last_change and str(last_change).strip():
                    try:
                        change_dt = datetime.fromisoformat(str(last_change))
                        time_diff = datetime.now() - change_dt
                        days = time_diff.days
                        hours = time_diff.seconds // 3600
                        st.metric("Tiempo en Estado", f"{days}d {hours}h")
                    except (ValueError, TypeError):
                        st.metric("Tiempo en Estado", "N/A")
                else:
                    st.metric("Tiempo en Estado", "N/A")
            
            with col3:
                try:
                    with get_conn() as conn:
                        prev_duration_query = """
                        SELECT duration_in_previous_status 
                        FROM status_history 
                        WHERE machinery_id = ? 
                        ORDER BY changed_at DESC 
                        LIMIT 1
                        """
                        prev_duration_result = conn.execute(prev_duration_query, (selected_id,)).fetchone()
                        
                        if prev_duration_result and prev_duration_result[0]:
                            prev_duration_hours = prev_duration_result[0] / 3600
                            st.metric("Duración Estado Anterior", f"{prev_duration_hours:.1f}h")
                        else:
                            st.metric("Duración Estado Anterior", "N/A")
                except sqlite3.Error:
                    st.metric("Duración Estado Anterior", "N/A")
            
            # Mostrar lecturas actuales
            st.subheader("Lecturas Actuales de Instrumentos")
            col_inst1, col_inst2 = st.columns(2)
            with col_inst1:
                st.metric("Horómetro Actual", f"{current_hours:.1f} horas")
            with col_inst2:
                st.metric("Odómetro Actual", f"{current_km:.1f} km")
            
            # Mostrar aviso especial si está en mantenimiento
            if current_status.lower() in ['mantenimiento', 'maintenance']:
                st.info("Nota: Al cambiar de 'Mantenimiento' a 'Activa', se registrará automáticamente un mantenimiento realizado.")
            
            # CLAVE DEL CAMBIO: Seleccionar estado fuera del formulario para poder actualizar las causas
            st.subheader("Cambio de Estado Operacional")
            
            # Seleccionar nuevo estado fuera del formulario
            new_status = st.selectbox(
                "Nuevo Estado",
                ["Activa", "Mantenimiento", "Inactiva"],
                index=["Activa", "Mantenimiento", "Inactiva"].index(current_status) 
                      if current_status in ["Activa", "Mantenimiento", "Inactiva"] else 0,
                key="new_status_safe"
            )
            
            # Cargar causas basadas en el nuevo estado seleccionado
            selected_reason = None
            try:
                with get_conn() as conn:
                    reasons_query = """
                        SELECT id, name, description FROM status_change_reasons 
                        WHERE is_active = 1 AND (applies_to = ? OR applies_to = 'ALL')
                        ORDER BY name
                    """
                    reasons_df = pd.read_sql_query(reasons_query, conn, params=(new_status,))
                    
                    if not reasons_df.empty:
                        selected_reason = st.selectbox(
                            "Causa del Cambio",
                            reasons_df['id'].tolist(),
                            format_func=lambda x: reasons_df[reasons_df['id']==x].iloc[0]['name'],
                            key="reason_select_safe"
                        )
                    else:
                        st.warning(f"No hay causas configuradas para el estado '{new_status}'")
            except sqlite3.Error:
                st.warning("No se pudieron cargar las causas de cambio")
            
            # Ahora el formulario solo contiene campos que no necesitan actualizarse en tiempo real
            with st.form("cambio_estado_safe"):
                notes = st.text_area("Observaciones", placeholder="Información adicional sobre el cambio de estado...")
                changed_by = st.text_input("Responsable del Cambio", value=st.session_state.get("username", "admin"))
                
                # Campos adicionales OBLIGATORIOS si va de Mantenimiento a Activa
                maintenance_cost = None
                maintenance_parts = None
                maintenance_description = None
                final_hours = current_hours
                final_km = current_km
                selected_maintenance_type = None
                
                if (current_status.lower() in ['mantenimiento', 'maintenance'] and 
                    new_status.lower() in ['activa', 'active']):
                    
                    st.subheader("Información del Mantenimiento Realizado (OBLIGATORIO)")
                    st.write("Complete la información del mantenimiento que se registrará automáticamente:")
                    
                    # Lecturas de instrumentos OBLIGATORIAS
                    st.write("#### Lecturas Finales de Instrumentos")
                    col_readings1, col_readings2 = st.columns(2)
                    
                    with col_readings1:
                        final_hours = st.number_input(
                            f"Horómetro Final (mín: {current_hours:.1f})",
                            min_value=current_hours,
                            value=current_hours,
                            step=0.1,
                            format="%.1f",
                            help=f"Debe ser mayor o igual que el valor actual: {current_hours:.1f} horas",
                            key="final_hours_auto"
                        )
                    
                    with col_readings2:
                        final_km = st.number_input(
                            f"Odómetro Final (mín: {current_km:.1f})",
                            min_value=current_km,
                            value=current_km,
                            step=0.1,
                            format="%.1f", 
                            help=f"Debe ser mayor o igual que el valor actual: {current_km:.1f} km",
                            key="final_km_auto"
                        )
                    
                    # Información del mantenimiento
                    st.write("#### Detalles del Mantenimiento")
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        maintenance_cost = st.number_input(
                            "Costo del Mantenimiento ($)",
                            min_value=0.0,
                            step=10.0,
                            format="%.2f",
                            key="maint_cost_auto"
                        )
                        
                        # Selector de tipo de mantenimiento
                        try:
                            with get_conn() as conn:
                                types_df = pd.read_sql_query("""
                                    SELECT id, name FROM maintenance_types 
                                    ORDER BY name
                                """, conn)
                                
                                if not types_df.empty:
                                    selected_maintenance_type = st.selectbox(
                                        "Tipo de Mantenimiento *",
                                        types_df['id'].tolist(),
                                        format_func=lambda x: types_df[types_df['id']==x].iloc[0]['name'],
                                        key="maint_type_auto"
                                    )
                                else:
                                    st.warning("No hay tipos de mantenimiento configurados")
                        except:
                            pass
                    
                    with col_b:
                        maintenance_parts = st.text_area(
                            "Repuestos y Materiales Utilizados",
                            placeholder="Lista de partes reemplazadas, materiales usados...",
                            key="maint_parts_auto"
                        )
                    
                    maintenance_description = st.text_area(
                        "Descripción Detallada del Trabajo Realizado *",
                        placeholder="Detalle específico de las actividades de mantenimiento realizadas...",
                        key="maint_desc_auto"
                    )
                    
                    # Validación visual
                    if not maintenance_description or not selected_maintenance_type:
                        st.warning("Los campos marcados con * son obligatorios para registrar el mantenimiento.")
                
                if st.form_submit_button("Confirmar Cambio de Estado"):
                    # Validación especial para mantenimiento
                    validation_passed = True
                    
                    if (current_status.lower() in ['mantenimiento', 'maintenance'] and 
                        new_status.lower() in ['activa', 'active']):
                        
                        if not maintenance_description:
                            st.error("La descripción del mantenimiento es obligatoria")
                            validation_passed = False
                        
                        if not selected_maintenance_type:
                            st.error("Debe seleccionar un tipo de mantenimiento")
                            validation_passed = False
                        
                        if final_hours < current_hours:
                            st.error(f"El horómetro final ({final_hours:.1f}) no puede ser menor que el actual ({current_hours:.1f})")
                            validation_passed = False
                        
                        if final_km < current_km:
                            st.error(f"El odómetro final ({final_km:.1f}) no puede ser menor que el actual ({current_km:.1f})")
                            validation_passed = False
                    
                    if new_status != current_status and selected_reason and validation_passed:
                        try:
                            with get_conn() as conn:
                                # Calcular duración en estado anterior
                                duration_seconds = 0
                                last_change = machine_data.get('last_status_change')
                                if last_change and str(last_change).strip():
                                    try:
                                        last_change_dt = datetime.fromisoformat(str(last_change))
                                        current_time = datetime.now()
                                        if last_change_dt <= current_time:
                                            duration_seconds = int((current_time - last_change_dt).total_seconds())
                                    except (ValueError, TypeError):
                                        duration_seconds = 0
                                
                                # NUEVA FUNCIONALIDAD MEJORADA: Si cambia de Mantenimiento a Activa, registrar mantenimiento
                                maintenance_record_created = False
                                if (current_status.lower() in ['mantenimiento', 'maintenance'] and 
                                    new_status.lower() in ['activa', 'active']):
                                    try:
                                        # Calcular fechas de inicio y fin del mantenimiento
                                        end_date = datetime.now()
                                        if duration_seconds > 0:
                                            start_date = end_date - timedelta(seconds=duration_seconds)
                                        else:
                                            start_date = end_date
                                        
                                        # Preparar notas completas
                                        full_notes = f"Duración en mantenimiento: {duration_seconds/3600:.1f} horas."
                                        if notes:
                                            full_notes += f" Observaciones: {notes}"
                                        
                                        # Registrar el mantenimiento realizado
                                        conn.execute("""
                                            INSERT INTO maintenance_records
                                            (machinery_id, maintenance_type_id, start_date, end_date, performed_by,
                                             odometer_start, odometer_end, hour_meter_start, hour_meter_end,
                                             cost, description, parts_used, notes)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        """, (
                                            selected_id, 
                                            selected_maintenance_type,
                                            start_date.isoformat(),
                                            end_date.isoformat(),
                                            changed_by,
                                            current_km,      # odometer_start (valor al inicio del mantenimiento)
                                            final_km,        # odometer_end (valor final ingresado)
                                            current_hours,   # hour_meter_start (valor al inicio del mantenimiento)
                                            final_hours,     # hour_meter_end (valor final ingresado)
                                            maintenance_cost if maintenance_cost and maintenance_cost > 0 else None,
                                            maintenance_description,
                                            maintenance_parts if maintenance_parts else None,
                                            full_notes
                                        ))
                                        
                                        # Actualizar lecturas de la máquina con los valores finales
                                        conn.execute("""
                                            UPDATE machinery 
                                            SET current_hours = ?, current_odometer = ?,
                                                last_maintenance_date = ?, last_maintenance_hours = ?, last_maintenance_km = ?
                                            WHERE id = ?
                                        """, (final_hours, final_km, end_date.date().isoformat(), 
                                              final_hours, final_km, selected_id))
                                        
                                        maintenance_record_created = True
                                        
                                        st.success(f"""
                                        Mantenimiento registrado automáticamente:
                                        - Duración: {duration_seconds/3600:.1f} horas
                                        - Horómetro: {current_hours:.1f}h → {final_hours:.1f}h
                                        - Odómetro: {current_km:.1f}km → {final_km:.1f}km
                                        - Costo: {"$" + str(maintenance_cost) if maintenance_cost else "No especificado"}
                                        """)
                                        
                                    except Exception as maint_error:
                                        st.warning(f"Estado cambiado exitosamente, pero no se pudo registrar el mantenimiento automático: {maint_error}")
                                
                                # Registrar el cambio de estado en el historial (funcionalidad original)
                                conn.execute("""
                                    INSERT INTO status_history 
                                    (machinery_id, previous_status, new_status, changed_by, reason_id, notes, duration_in_previous_status)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (selected_id, current_status, new_status, 
                                      changed_by, selected_reason, notes, duration_seconds))
                                
                                # Actualizar estado de la máquina (funcionalidad original)
                                conn.execute("""
                                    UPDATE machinery 
                                    SET status = ?, last_status_change = ?
                                    WHERE id = ?
                                """, (new_status, datetime.now().isoformat(), selected_id))
                                
                                conn.commit()
                                
                                # Mensaje de éxito mejorado
                                success_message = f"Estado cambiado exitosamente a: {new_status}"
                                if maintenance_record_created:
                                    success_message += "\nRegistro de mantenimiento creado automáticamente"
                                
                                st.success(success_message)
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"Error al cambiar estado: {str(e)}")
                    elif new_status == current_status:
                        st.warning("El nuevo estado es igual al estado actual")
                    elif not selected_reason:
                        st.error("Debe seleccionar una causa válida para el cambio")
            
    except Exception as e:
        st.error(f"Error en módulo de estados: {e}")

def mostrar_modulo_mantenimiento_safe(empresa_id, machinery_df):
    """Versión segura del módulo de mantenimiento"""
    st.subheader("Gestión de Mantenimiento")
    
    if machinery_df.empty:
        st.warning("No hay vehículos registrados para gestionar.")
        return
        
    maint_tabs = st.tabs([
        "Programar Mantenimiento", 
        "Registrar Mantenimiento Realizado", 
        "Mantenimientos Programados"
    ])
    
    with maint_tabs[0]:
        mostrar_programacion_mantenimiento_safe(empresa_id, machinery_df)
    
    with maint_tabs[1]:
        mostrar_registro_mantenimiento_mejorado(empresa_id, machinery_df)
    
    with maint_tabs[2]:
        mostrar_mantenimientos_programados_safe(empresa_id)

def mostrar_programacion_mantenimiento_safe(empresa_id, machinery_df):
    """Programación de mantenimientos futuros - versión segura"""
    st.subheader("Programación de Mantenimiento Futuro")
    try:
        with get_conn() as conn:
            tipos_df = pd.read_sql_query("SELECT id, name, description FROM maintenance_types ORDER BY name", conn)
            
            if machinery_df.empty:
                st.info("No hay vehículos registrados.")
                return
            
            with st.form("programar_mantenimiento_safe"):
                st.subheader("Detalles del Mantenimiento Programado")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_machine = st.selectbox(
                        "Vehículo a Programar",
                        machinery_df['id'].tolist(),
                        format_func=lambda x: f"{machinery_df[machinery_df['id']==x].iloc[0]['name']} ({machinery_df[machinery_df['id']==x].iloc[0].get('identifier', 'N/A')})",
                        key="select_machine_program"
                    )
                    
                    selected_type = st.selectbox(
                        "Tipo de Mantenimiento",
                        tipos_df['id'].tolist(),
                        format_func=lambda x: tipos_df[tipos_df['id']==x].iloc[0]['name'],
                        key="select_maint_type"
                    )
                    
                    priority = st.selectbox(
                        "Prioridad",
                        ["NORMAL", "ALTA", "CRÍTICA"],
                        index=0,
                        key="select_priority"
                    )
                
                with col2:
                    start_date = st.date_input(
                        "Fecha de Inicio Programada",
                        value=date.today() + timedelta(days=1),
                        min_value=date.today(),
                        key="start_date_input"
                    )
                    
                    end_date = st.date_input(
                        "Fecha de Finalización Estimada",
                        value=date.today() + timedelta(days=2),
                        min_value=start_date,
                        key="end_date_input"
                    )
                    
                    estimated_hours = st.number_input(
                        "Horas Estimadas de Trabajo",
                        min_value=0.5,
                        value=8.0,
                        step=0.5,
                        format="%.1f",
                        key="estimated_hours_input"
                    )
                
                responsible_person = st.text_input(
                    "Responsable del Mantenimiento",
                    value=st.session_state.get("username", "admin"),
                    key="responsible_person_input"
                )
                
                description = st.text_area(
                    "Descripción del Trabajo a Realizar",
                    placeholder="Detalle específico de las actividades de mantenimiento programadas...",
                    key="description_input"
                )
                
                if st.form_submit_button("Programar Mantenimiento"):
                    try:
                        conn.execute("""
                            INSERT INTO maintenance_schedules
                            (machinery_id, maintenance_type_id, scheduled_start_date, scheduled_end_date,
                             estimated_hours, description, responsible_person, priority)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (selected_machine, selected_type, start_date.isoformat(), end_date.isoformat(),
                             estimated_hours, description, responsible_person, priority))
                        
                        conn.commit()
                        st.success("Mantenimiento programado correctamente")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error al programar mantenimiento: {str(e)}")
                        
    except Exception as e:
        st.error(f"Error en programación de mantenimiento: {e}")

def mostrar_registro_mantenimiento_mejorado(empresa_id, machinery_df):
    """Registro de mantenimientos realizados con el nuevo sistema de intervalos"""
    st.subheader("Registro de Mantenimiento Realizado")
    
    try:
        with get_conn() as conn:
            tipos_df = pd.read_sql_query("SELECT id, name, description FROM maintenance_types ORDER BY name", conn)
            
            if machinery_df.empty:
                st.info("No hay vehículos registrados.")
                return
            
            with st.form("registro_mantenimiento_mejorado"):
                st.subheader("Información del Mantenimiento Realizado")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_machine_id = st.selectbox(
                        "Vehículo",
                        machinery_df['id'].tolist(),
                        format_func=lambda x: f"{machinery_df[machinery_df['id']==x].iloc[0]['name']} ({machinery_df[machinery_df['id']==x].iloc[0].get('identifier', 'N/A')})",
                        key="reg_mant_machine"
                    )
                    
                    selected_type = st.selectbox(
                        "Tipo de Mantenimiento",
                        tipos_df['id'].tolist(), 
                        format_func=lambda x: tipos_df[tipos_df['id']==x].iloc[0]['name'],
                        key="reg_mant_type"
                    )
                    
                    performed_by = st.text_input(
                        "Realizado por",
                        value=st.session_state.get("username", "admin"),
                        key="performed_by"
                    )
                
                with col2:
                    # Mostrar información del intervalo actual
                    current_status = get_maintenance_status_for_machine(
                        selected_machine_id, selected_type, 
                        float(machinery_df[machinery_df['id']==selected_machine_id].iloc[0].get('current_hours', 0)),
                        float(machinery_df[machinery_df['id']==selected_machine_id].iloc[0].get('current_odometer', 0))
                    )
                    
                    if current_status:
                        st.info(f"Intervalo actual: {current_status['hours_interval']:.0f} horas / {current_status['km_interval']:.0f} km")
                        st.info(f"Próximo mant.: {current_status['next_maint_hours']:.1f}h / {current_status['next_maint_km']:.1f}km")
                
                # Fecha de realización
                maintenance_date = st.date_input(
                    "Fecha de Realización",
                    value=date.today(),
                    max_value=date.today(),
                    key="maint_date"
                )
                
                # Información de Horómetro y Odómetro
                st.subheader("Lecturas de Instrumentos al Realizar Mantenimiento")
                
                col3, col4 = st.columns(2)
                
                machine_data = machinery_df[machinery_df['id'] == selected_machine_id].iloc[0]
                current_hours = float(machine_data.get('current_hours', 0))
                current_km = float(machine_data.get('current_odometer', 0))
                
                with col3:
                    hour_meter = st.number_input(
                        "Horómetro al Mantenimiento",
                        min_value=0.0,
                        value=current_hours,
                        step=0.1,
                        format="%.1f",
                        key="hour_meter"
                    )
                
                with col4:
                    odometer = st.number_input(
                        "Odómetro al Mantenimiento (km)",
                        min_value=0.0,
                        value=current_km,
                        step=0.1,
                        format="%.1f",
                        key="odometer"
                    )
                
                # Información adicional del mantenimiento
                st.subheader("Detalles del Trabajo Realizado")
                
                col5, col6 = st.columns(2)
                
                with col5:
                    cost = st.number_input(
                        "Costo Total ($)",
                        min_value=0.0,
                        step=10.0,
                        format="%.2f",
                        key="cost_input"
                    )
                
                with col6:
                    # Configurar nuevo intervalo si es diferente
                    if current_status:
                        new_hours_interval = st.number_input(
                            "Nuevo intervalo (horas)",
                            min_value=1.0,
                            value=current_status['hours_interval'],
                            step=100.0,
                            key="new_interval_hours"
                        )
                        
                        new_km_interval = st.number_input(
                            "Nuevo intervalo (km)",
                            min_value=1.0,
                            value=current_status['km_interval'],
                            step=500.0,
                            key="new_interval_km"
                        )
                
                description = st.text_area(
                    "Descripción Detallada",
                    placeholder="Detalle específico de las actividades realizadas...",
                    key="desc_input"
                )
                
                parts_used = st.text_area(
                    "Repuestos y Materiales",
                    placeholder="Lista de partes y materiales utilizados...",
                    key="parts_input"
                )
                
                notes = st.text_area(
                    "Observaciones Técnicas",
                    placeholder="Notas adicionales, hallazgos o recomendaciones...",
                    key="notes_input"
                )
                
                if st.form_submit_button("Registrar Mantenimiento"):
                    try:
                        # Registrar el mantenimiento
                        conn.execute("""
                            INSERT INTO maintenance_records
                            (machinery_id, maintenance_type_id, start_date, end_date, performed_by,
                             odometer_start, odometer_end, hour_meter_start, hour_meter_end,
                             cost, description, parts_used, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (selected_machine_id, selected_type, maintenance_date.isoformat(), 
                             maintenance_date.isoformat(), performed_by, odometer, odometer, 
                             hour_meter, hour_meter, cost if cost > 0 else None, 
                             description, parts_used, notes))
                        
                        # Actualizar intervalos si cambiaron
                        if current_status and (new_hours_interval != current_status['hours_interval'] or 
                                              new_km_interval != current_status['km_interval']):
                            conn.execute("""
                                UPDATE maintenance_intervals
                                SET hours_interval = ?, km_interval = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE machinery_id = ? AND maintenance_type_id = ?
                            """, (new_hours_interval, new_km_interval, selected_machine_id, selected_type))
                        
                        # Actualizar lecturas de la máquina
                        new_hours = max(current_hours, hour_meter)
                        new_km = max(current_km, odometer)
                        
                        conn.execute("""
                            UPDATE machinery 
                            SET current_hours = ?, current_odometer = ?,
                                last_maintenance_date = ?, last_maintenance_hours = ?, last_maintenance_km = ?
                            WHERE id = ?
                        """, (new_hours, new_km, maintenance_date.isoformat(), 
                              hour_meter, odometer, selected_machine_id))
                        
                        conn.commit()
                        st.success("Mantenimiento registrado exitosamente")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error al registrar mantenimiento: {str(e)}")
                        
    except Exception as e:
        st.error(f"Error en registro de mantenimiento: {e}")

def mostrar_mantenimientos_programados_safe(empresa_id):
    """Muestra los mantenimientos programados con opciones de compliance - CORREGIDO"""
    st.subheader("Gestión de Mantenimientos Programados")
    
    try:
        from db_utils import (get_upcoming_scheduled_maintenances, get_overdue_scheduled_maintenances, 
                             log_maintenance_compliance, update_scheduled_maintenance_status)
        
        with get_conn() as conn:
            # Tabs para organizar la vista
            tab_todos, tab_proximos, tab_vencidos, tab_compliance = st.tabs([
                "Todos los Programados", "Próximos (7 días)", "Vencidos", "Log de Cumplimiento"
            ])
            
            with tab_todos:
                st.write("### Todos los Mantenimientos Programados")
                
                schedules_query = """
                SELECT 
                    ms.id,
                    m.name as machine_name,
                    COALESCE(m.identifier, 'N/A') as identifier,
                    mt.name as maintenance_type,
                    ms.scheduled_start_date,
                    ms.scheduled_end_date,
                    COALESCE(ms.estimated_hours, 8) as estimated_hours,
                    COALESCE(ms.priority, 'NORMAL') as priority,
                    ms.status,
                    COALESCE(ms.responsible_person, 'No asignado') as responsible_person,
                    COALESCE(ms.description, '') as description,
                    CASE 
                        WHEN date(ms.scheduled_start_date) < date('now') THEN 'VENCIDO'
                        WHEN date(ms.scheduled_start_date) <= date('now', '+7 days') THEN 'PROXIMO'
                        ELSE 'FUTURO'
                    END as estado_temporal
                FROM maintenance_schedules ms
                JOIN machinery m ON ms.machinery_id = m.id
                JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
                WHERE m.company_id = ? AND ms.status = 'PROGRAMADO'
                ORDER BY ms.scheduled_start_date ASC
                """
                
                schedules_df = pd.read_sql_query(schedules_query, conn, params=(empresa_id,))
                
                if not schedules_df.empty:
                    for _, schedule in schedules_df.iterrows():
                        # Color según estado temporal
                        if schedule['estado_temporal'] == 'VENCIDO':
                            container_func = st.error
                            status_icon = "🚨"
                        elif schedule['estado_temporal'] == 'PROXIMO':
                            container_func = st.warning
                            status_icon = "⚠️"
                        else:
                            container_func = st.info
                            status_icon = "📅"
                        
                        with container_func(""):
                            col1, col2, col3 = st.columns([3, 2, 2])
                            
                            with col1:
                                st.write(f"{status_icon} **{schedule['machine_name']}** ({schedule['identifier']})")
                                st.write(f"Tipo: {schedule['maintenance_type']}")
                                st.write(f"Responsable: {schedule['responsible_person']}")
                                if schedule['description']:
                                    st.caption(f"Descripción: {schedule['description']}")
                            
                            with col2:
                                st.write(f"**Programado:** {schedule['scheduled_start_date']}")
                                st.write(f"**Fin estimado:** {schedule['scheduled_end_date']}")
                                st.write(f"**Duración:** {schedule['estimated_hours']} horas")
                                st.write(f"**Prioridad:** {schedule['priority']}")
                            
                            with col3:
                                # Botones de acción
                                if st.button("✅ Realizado", key=f"done_{schedule['id']}", use_container_width=True):
                                    st.session_state[f'mark_done_{schedule["id"]}'] = True
                                    st.rerun()
                                
                                if st.button("❌ No Realizado", key=f"skip_{schedule['id']}", use_container_width=True):
                                    st.session_state[f'mark_skip_{schedule["id"]}'] = True
                                    st.rerun()
                                
                                if st.button("📅 Reprogramar", key=f"reschedule_{schedule['id']}", use_container_width=True):
                                    st.session_state[f'reschedule_{schedule["id"]}'] = True
                                    st.rerun()
                
                else:
                    st.info("No hay mantenimientos programados.")
            
            with tab_proximos:
                st.write("### Mantenimientos Próximos (7 días)")
                upcoming_df = get_upcoming_scheduled_maintenances(empresa_id, 7)
                
                if not upcoming_df.empty:
                    st.dataframe(upcoming_df[['vehiculo', 'tipo_mantenimiento', 'scheduled_start_date', 
                                            'responsible_person', 'priority', 'dias_restantes']], 
                               use_container_width=True)
                else:
                    st.success("No hay mantenimientos próximos en los siguientes 7 días.")
            
            with tab_vencidos:
                st.write("### Mantenimientos Vencidos")
                overdue_df = get_overdue_scheduled_maintenances(empresa_id)
                
                if not overdue_df.empty:
                    st.error(f"Hay {len(overdue_df)} mantenimientos vencidos que requieren atención.")
                    st.dataframe(overdue_df[['vehiculo', 'tipo_mantenimiento', 'scheduled_start_date', 
                                           'responsible_person', 'priority', 'dias_vencido']], 
                               use_container_width=True)
                else:
                    st.success("No hay mantenimientos vencidos.")
            
            with tab_compliance:
                st.write("### Log de Cumplimiento")
                mostrar_compliance_log(empresa_id)
        
        # Manejar las acciones pendientes
        manejar_acciones_mantenimiento_programado(empresa_id)
        
    except Exception as e:
        st.error(f"Error al cargar mantenimientos programados: {e}")

def mostrar_modulo_historial_safe(empresa_id):
    """Sistema completo de reportes de mantenimiento con descarga Excel - CORREGIDO"""
    st.subheader("Sistema de Reportes y Análisis")
    
    # Organizar reportes por categorías
    categorias_reportes = {
        "Operacionales": {
            "duracion_mantenimientos": "Duración de Mantenimientos",
            "movimientos_estados": "Movimientos y Cambios de Estado", 
            "utilizacion_vehiculos": "Utilización de Vehículos",
            "disponibilidad_flota": "Disponibilidad de Flota"
        },
        "Financieros": {
            "costos_mantenimiento": "Costos de Mantenimiento",
            "repuestos_materiales": "Repuestos y Materiales",
            "rentabilidad_vehiculo": "Rentabilidad por Vehículo",
            "consumibles": "Análisis de Consumibles"
        },
        "Técnicos": {
            "cumplimiento_preventivos": "Cumplimiento de Mantenimientos Preventivos",
            "historial_fallas": "Historial de Fallas",
            "efficiency_mantenimiento": "Eficiencia de Mantenimiento",
            "cumplimiento_legal": "Cumplimiento Legal y Normativas"
        }
    }
    
    # Selectores principales
    col_cat, col_rep = st.columns(2)
    
    with col_cat:
        categoria_seleccionada = st.selectbox(
            "Categoría de Reporte",
            list(categorias_reportes.keys()),
            key="categoria_reporte"
        )
    
    with col_rep:
        reportes_categoria = categorias_reportes[categoria_seleccionada]
        reporte_seleccionado = st.selectbox(
            "Tipo de Reporte",
            list(reportes_categoria.keys()),
            format_func=lambda x: reportes_categoria[x],
            key="tipo_reporte"
        )
    
    # Filtros comunes
    with st.expander("Filtros de Período y Vehículos", expanded=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            fecha_inicio = st.date_input(
                "Fecha Inicio",
                value=date.today() - timedelta(days=30),
                key="fecha_inicio_reporte"
            )
        
        with col_f2:
            fecha_fin = st.date_input(
                "Fecha Fin", 
                value=date.today(),
                key="fecha_fin_reporte"
            )
        
        with col_f3:
            # Obtener vehículos disponibles - CORREGIDO
            try:
                with get_conn() as conn:
                    vehiculos_df = pd.read_sql_query("""
                        SELECT id, name, identifier FROM machinery 
                        WHERE company_id = ? 
                        ORDER BY name
                    """, conn, params=(empresa_id,))
                    
                    vehiculos_options = ["Todos"] + [f"{row['name']} ({row.get('identifier', 'N/A')})" 
                                                   for _, row in vehiculos_df.iterrows()]
                    vehiculo_seleccionado = st.selectbox(
                        "Vehículo",
                        vehiculos_options,
                        key="vehiculo_reporte"
                    )
            except Exception as e:
                st.error(f"Error cargando vehículos: {e}")
                vehiculo_seleccionado = "Todos"
                vehiculos_df = pd.DataFrame()
    
    # Generar el reporte seleccionado
    st.divider()
    
    if reporte_seleccionado == "duracion_mantenimientos":
        generar_reporte_duracion_mantenimientos(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df)
    
    elif reporte_seleccionado == "movimientos_estados":
        generar_reporte_movimientos_estados(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df)
    
    elif reporte_seleccionado == "costos_mantenimiento":
        generar_reporte_costos_mantenimiento(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df)
    
    elif reporte_seleccionado == "cumplimiento_preventivos":
        generar_reporte_cumplimiento_preventivos(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df)
    
    elif reporte_seleccionado == "utilizacion_vehiculos":
        generar_reporte_utilizacion_vehiculos(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df)
    
    elif reporte_seleccionado == "disponibilidad_flota":
        generar_reporte_disponibilidad_flota(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df)
    
    else:
        # Para reportes aún no implementados
        st.info(f"Reporte '{reportes_categoria[reporte_seleccionado]}' en desarrollo. Próximamente disponible.")
        mostrar_preview_reporte(reporte_seleccionado, reportes_categoria[reporte_seleccionado])

def obtener_vehiculo_id_seguro(vehiculo_seleccionado, vehiculos_df):
    """Función auxiliar para obtener ID de vehículo de forma segura"""
    if vehiculo_seleccionado == "Todos" or vehiculos_df.empty:
        return None
    
    try:
        # Buscar el vehículo que coincida con la selección
        for _, row in vehiculos_df.iterrows():
            vehiculo_display = f"{row['name']} ({row.get('identifier', 'N/A')})"
            if vehiculo_display == vehiculo_seleccionado:
                return row['id']
        return None
    except Exception:
        return None

def crear_excel_formateado_corregido(dataframes_dict, titulo_reporte, fecha_inicio, fecha_fin):
    """Crea un archivo Excel con formato profesional - CORREGIDA"""
    import io
    
    output = io.BytesIO()
    
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Hoja de resumen
            crear_hoja_resumen_corregida(writer, titulo_reporte, fecha_inicio, fecha_fin, dataframes_dict)
            
            # Hojas de datos
            for nombre_hoja, df in dataframes_dict.items():
                if not df.empty:
                    # Limpiar nombre de hoja (Excel tiene limitaciones)
                    nombre_limpio = nombre_hoja.replace('/', '_').replace('\\', '_')[:31]
                    
                    # Mejorar formato de fechas y datos numéricos
                    df_copy = df.copy()
                    
                    # Mejorar formato de columnas específicas
                    for col in df_copy.columns:
                        # Formatear columnas de horas como decimales con 1 decimal
                        if 'hora' in col.lower() or 'hour' in col.lower() or 'duracion' in col.lower():
                            try:
                                df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
                                df_copy[col] = df_copy[col].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "")
                            except:
                                pass
                        
                        # Formatear columnas de costos con símbolo de moneda
                        elif 'cost' in col.lower() or 'costo' in col.lower():
                            try:
                                df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
                                df_copy[col] = df_copy[col].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "")
                            except:
                                pass
                        
                        # Formatear fechas en formato legible
                        elif 'fecha' in col.lower() or 'date' in col.lower():
                            try:
                                df_copy[col] = pd.to_datetime(df_copy[col], errors='coerce')
                                df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d %H:%M')
                            except:
                                pass
                    
                    # Escribir DataFrame con formato mejorado
                    df_copy.to_excel(writer, sheet_name=nombre_limpio, index=False, startrow=2)
                    
                    # Formatear hoja con manejo mejorado de errores
                    try:
                        formatear_hoja_excel_segura(writer, nombre_limpio, df_copy, nombre_hoja)
                    except Exception as format_error:
                        # Si falla el formato, intentar un formato básico
                        try:
                            aplicar_formato_basico(writer, nombre_limpio, df_copy)
                        except:
                            # Si todo falla, al menos el Excel se generará sin formato
                            pass
        
        return output.getvalue()
    
    except Exception as e:
        # Error silencioso para no interrumpir la generación del Excel
        print(f"Error creando Excel: {e}")
        return None

def crear_hoja_resumen_corregida(writer, titulo, fecha_inicio, fecha_fin, dataframes_dict):
    """Crea hoja de resumen del reporte - CORREGIDA"""
    try:
        resumen_data = {
            'Información del Reporte': ['Título', 'Período', 'Fecha Generación', 'Total Registros'],
            'Detalles': [
                titulo,
                f"{fecha_inicio} al {fecha_fin}",
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                sum(len(df) for df in dataframes_dict.values() if not df.empty)
            ]
        }
        
        resumen_df = pd.DataFrame(resumen_data)
        resumen_df.to_excel(writer, sheet_name='Resumen', index=False)
        
    except Exception as e:
        st.warning(f"Error creando hoja resumen: {e}")

def formatear_hoja_excel_corregida(writer, nombre_hoja, df, titulo_original):
    """Aplica formato a una hoja de Excel - CORREGIDA para manejar MergedCell"""
    try:
        from openpyxl.styles import Font, PatternFill, Alignment
        
        workbook = writer.book
        worksheet = writer.sheets[nombre_hoja]
        
        # Título en la primera fila
        worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
        title_cell = worksheet.cell(row=1, column=1)
        title_cell.value = titulo_original
        title_cell.font = Font(bold=True, size=14)
        title_cell.alignment = Alignment(horizontal='center')
        
        # Formatear encabezados
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        
        for col_num, value in enumerate(df.columns, 1):
            cell = worksheet.cell(row=3, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        
        # Ajustar ancho de columnas - CORREGIDO para manejar celdas combinadas
        for i, col in enumerate(df.columns, 1):
            try:
                # Obtener el objeto de columna de forma segura
                col_letter = worksheet.cell(row=3, column=i).column_letter
                
                # Calcular ancho máximo
                max_length = max(
                    df.iloc[:, i-1].astype(str).str.len().max() if not df.empty else 10,
                    len(str(col))
                )
                
                # Establecer ancho de columna
                worksheet.column_dimensions[col_letter].width = min(max_length + 2, 50)
            except Exception as col_err:
                # Si hay error, usar un ancho predeterminado
                try:
                    col_letter = worksheet.cell(row=3, column=i).column_letter
                    worksheet.column_dimensions[col_letter].width = 15
                except:
                    # Si aún falla, simplemente continuamos
                    pass
                
    except Exception as e:
        # No usar st.warning aquí para evitar errores en la generación del Excel
        print(f"Error formateando hoja: {e}")

def generar_reporte_duracion_mantenimientos(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df):
    """Reporte de duración de mantenimientos - CORREGIDO con información más clara"""
    st.subheader("Reporte de Duración de Mantenimientos")
    
    try:
        with get_conn() as conn:
            # Obtener ID de vehículo de forma segura
            vehiculo_id = obtener_vehiculo_id_seguro(vehiculo_seleccionado, vehiculos_df)
            
            # Construir filtro
            vehiculo_filter = ""
            params = [empresa_id, fecha_inicio, fecha_fin]
            
            if vehiculo_id:
                vehiculo_filter = "AND m.id = ?"
                params.append(vehiculo_id)
            
            # Query principal MEJORADA con cálculo de duración más preciso
            query = f"""
            SELECT 
                m.name as vehiculo,
                COALESCE(m.identifier, 'N/A') as identifier,
                mt.name as tipo_mantenimiento,
                mr.start_date as fecha_inicio,
                mr.end_date as fecha_fin,
                COALESCE(mr.performed_by, 'No especificado') as realizado_por,
                COALESCE(mr.cost, 0) as costo,
                CASE 
                    WHEN mr.start_date IS NOT NULL AND mr.end_date IS NOT NULL 
                    THEN ROUND((julianday(mr.end_date) - julianday(mr.start_date)) * 24, 1)
                    ELSE 0 
                END as duracion_horas,
                COALESCE(mr.hour_meter_start, 0) as horometro_inicial,
                COALESCE(mr.hour_meter_end, 0) as horometro_final,
                COALESCE(mr.odometer_start, 0) as odometro_inicial,
                COALESCE(mr.odometer_end, 0) as odometro_final,
                COALESCE(mr.description, '') as descripcion,
                COALESCE(mr.parts_used, '') as repuestos
            FROM maintenance_records mr
            JOIN machinery m ON mr.machinery_id = m.id
            JOIN maintenance_types mt ON mr.maintenance_type_id = mt.id
            WHERE m.company_id = ? 
            AND date(COALESCE(mr.start_date, mr.created_at)) >= ? 
            AND date(COALESCE(mr.end_date, mr.created_at)) <= ?
            {vehiculo_filter}
            ORDER BY mr.start_date DESC
            """
            
            df_mantenimientos = pd.read_sql_query(query, conn, params=params)
            
            if not df_mantenimientos.empty:
                # MODIFICACIÓN: Destacar duración y fechas en la vista principal
                # Preparar versión para mostrar en la UI (más completa)
                display_df = df_mantenimientos[['vehiculo', 'identifier', 'tipo_mantenimiento', 
                                               'fecha_inicio', 'fecha_fin', 'duracion_horas', 
                                               'costo', 'realizado_por']].copy()
                
                # Formatear para mejor visualización
                display_df['fecha_inicio'] = pd.to_datetime(display_df['fecha_inicio']).dt.strftime('%Y-%m-%d %H:%M')
                display_df['fecha_fin'] = pd.to_datetime(display_df['fecha_fin']).dt.strftime('%Y-%m-%d %H:%M')
                display_df['costo'] = display_df['costo'].apply(lambda x: f"${x:.2f}" if x > 0 else "N/A")
                # Destacar la duración con formato
                display_df['duracion_horas'] = display_df['duracion_horas'].apply(lambda x: f"{x:.1f}")
                
                # Renombrar columnas para la vista
                display_df = display_df.rename(columns={
                    'vehiculo': 'Vehículo', 
                    'identifier': 'Matrícula',
                    'tipo_mantenimiento': 'Tipo', 
                    'fecha_inicio': 'Fecha Inicio', 
                    'fecha_fin': 'Fecha Fin',
                    'duracion_horas': 'Duración (h)', 
                    'costo': 'Costo', 
                    'realizado_por': 'Realizado por'
                })
                
                # Mostrar tabla con información destacada
                st.write("### Duración de Mantenimientos")
                st.info("Esta tabla muestra la duración de cada mantenimiento calculada entre la fecha de inicio y fin.")
                st.dataframe(display_df, use_container_width=True)
                
                # Estadísticas
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    promedio_duracion = df_mantenimientos['duracion_horas'].mean()
                    st.metric("Duración Promedio", f"{promedio_duracion:.1f} horas")
                
                with col_stat2:
                    total_horas = df_mantenimientos['duracion_horas'].sum()
                    st.metric("Total Horas Mantenimiento", f"{total_horas:.1f}")
                
                with col_stat3:
                    total_registros = len(df_mantenimientos)
                    st.metric("Total Mantenimientos", total_registros)
                
                # Gráfico específico de duración
                fig_duracion = px.bar(display_df, x='Vehículo', y='Duración (h)', 
                                    title='Duración de Mantenimientos por Vehículo',
                                    color='Duración (h)', 
                                    hover_data=['Fecha Inicio', 'Fecha Fin', 'Tipo', 'Costo'])
                st.plotly_chart(fig_duracion, use_container_width=True)
                
                # Estadísticas por tipo
                tipo_stats = df_mantenimientos.groupby('tipo_mantenimiento').agg({
                    'duracion_horas': ['mean', 'sum', 'count']
                }).round(2)
                
                tipo_stats.columns = ['Promedio_Horas', 'Total_Horas', 'Cantidad']
                tipo_stats = tipo_stats.reset_index()
                
                # Gráfico por tipo
                if len(tipo_stats) > 0:
                    fig = px.bar(tipo_stats, x='tipo_mantenimiento', y='Promedio_Horas',
                               title='Duración Promedio por Tipo de Mantenimiento')
                    st.plotly_chart(fig, use_container_width=True)
                
                # MEJORA para Excel: Preparar DataFrames que destacan la duración
                
                # Vista detallada de registros para Excel con formato de duración claro
                detalle_completo = df_mantenimientos.copy()
                
                # Renombrar columnas para Excel de forma más descriptiva
                detalle_completo = detalle_completo.rename(columns={
                    'vehiculo': 'Vehículo', 
                    'identifier': 'Matrícula',
                    'tipo_mantenimiento': 'Tipo de Mantenimiento', 
                    'fecha_inicio': 'Fecha Inicio', 
                    'fecha_fin': 'Fecha Fin',
                    'duracion_horas': 'Duración (horas)', 
                    'costo': 'Costo ($)', 
                    'realizado_por': 'Realizado por',
                    'horometro_inicial': 'Horómetro Inicial',
                    'horometro_final': 'Horómetro Final',
                    'odometro_inicial': 'Odómetro Inicial (km)',
                    'odometro_final': 'Odómetro Final (km)',
                    'descripcion': 'Descripción',
                    'repuestos': 'Repuestos Utilizados'
                })
                
                # 1. Vista por vehículo
                vehiculo_stats = df_mantenimientos.groupby(['vehiculo', 'identifier']).agg({
                    'duracion_horas': ['mean', 'sum', 'count'],
                    'costo': 'sum'
                }).round(2)
                
                vehiculo_stats.columns = ['Promedio_Horas', 'Total_Horas', 'Cantidad', 'Costo_Total']
                vehiculo_stats = vehiculo_stats.reset_index()
                vehiculo_stats = vehiculo_stats.rename(columns={
                    'vehiculo': 'Vehículo',
                    'identifier': 'Matrícula',
                    'Promedio_Horas': 'Duración Promedio (h)',
                    'Total_Horas': 'Horas Totales Mantenimiento',
                    'Cantidad': 'Cantidad Mantenimientos',
                    'Costo_Total': 'Costo Total ($)'
                })
                
                # Reordenar columnas para mejor visualización en Excel
                cols_order = ['Vehículo', 'Matrícula', 'Fecha Inicio', 'Fecha Fin', 
                              'Duración (horas)', 'Realizado por', 'Tipo de Mantenimiento',
                              'Costo ($)', 'Horómetro Inicial', 'Horómetro Final', 
                              'Odómetro Inicial (km)', 'Odómetro Final (km)',
                              'Descripción', 'Repuestos Utilizados']
                
                detalle_completo = detalle_completo[cols_order]
                
                # Botón de descarga con formato mejorado
                dataframes_excel = {
                    'Registros_Detallados': detalle_completo,
                    'Resumen_por_Vehículo': vehiculo_stats,
                    'Estadísticas_por_Tipo': tipo_stats
                }
                
                excel_data = crear_excel_formateado_corregido(
                    dataframes_excel, 
                    "Reporte de Duración de Mantenimientos",
                    fecha_inicio, 
                    fecha_fin
                )
                
                if excel_data:
                    st.download_button(
                        label="Descargar Reporte en Excel",
                        data=excel_data,
                        file_name=f"duracion_mantenimientos_{fecha_inicio}_{fecha_fin}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            else:
                st.info("No hay datos de mantenimientos en el período seleccionado.")
                
    except Exception as e:
        st.error(f"Error generando reporte: {e}")

def generar_reporte_movimientos_estados(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df):
    """Reporte de movimientos y cambios de estado - CORREGIDO"""
    st.subheader("Reporte de Movimientos y Cambios de Estado")
    
    try:
        with get_conn() as conn:
            vehiculo_id = obtener_vehiculo_id_seguro(vehiculo_seleccionado, vehiculos_df)
            
            vehiculo_filter = ""
            params = [empresa_id, fecha_inicio, fecha_fin]
            
            if vehiculo_id:
                vehiculo_filter = "AND m.id = ?"
                params.append(vehiculo_id)
            
            query = f"""
            SELECT 
                m.name as vehiculo,
                COALESCE(m.identifier, 'N/A') as identifier,
                sh.previous_status as estado_anterior,
                sh.new_status as estado_nuevo,
                sh.changed_at as fecha_cambio,
                COALESCE(sh.changed_by, 'No especificado') as responsable,
                COALESCE(scr.name, 'Sin especificar') as causa,
                ROUND(COALESCE(sh.duration_in_previous_status, 0) / 3600.0, 2) as horas_en_estado_anterior
            FROM status_history sh
            JOIN machinery m ON sh.machinery_id = m.id
            LEFT JOIN status_change_reasons scr ON sh.reason_id = scr.id
            WHERE m.company_id = ? 
            AND date(sh.changed_at) >= ? 
            AND date(sh.changed_at) <= ?
            {vehiculo_filter}
            ORDER BY sh.changed_at DESC
            """
            
            df_estados = pd.read_sql_query(query, conn, params=params)
            
            if not df_estados.empty:
                # Mostrar datos
                st.dataframe(df_estados, use_container_width=True)
                
                # Estadísticas por vehículo
                vehiculo_stats = df_estados.groupby('vehiculo').agg({
                    'fecha_cambio': 'count',
                    'horas_en_estado_anterior': 'sum'
                }).rename(columns={
                    'fecha_cambio': 'total_cambios',
                    'horas_en_estado_anterior': 'total_horas'
                }).round(2).reset_index()
                
                # Estadísticas por estado
                estado_stats = df_estados.groupby('estado_nuevo').agg({
                    'fecha_cambio': 'count',
                    'horas_en_estado_anterior': 'mean'
                }).rename(columns={
                    'fecha_cambio': 'frecuencia',
                    'horas_en_estado_anterior': 'duracion_promedio'
                }).round(2).reset_index()
                
                # Gráficos
                col_chart1, col_chart2 = st.columns(2)
                
                with col_chart1:
                    if len(vehiculo_stats) > 0:
                        fig1 = px.bar(vehiculo_stats, x='vehiculo', y='total_cambios',
                                    title='Frecuencia de Cambios por Vehículo')
                        st.plotly_chart(fig1, use_container_width=True)
                
                with col_chart2:
                    if len(estado_stats) > 0:
                        fig2 = px.pie(estado_stats, values='frecuencia', names='estado_nuevo',
                                    title='Distribución de Estados')
                        st.plotly_chart(fig2, use_container_width=True)
                
                # Botón de descarga
                dataframes_excel = {
                    'Historial_Estados': df_estados,
                    'Stats_por_Vehiculo': vehiculo_stats,
                    'Stats_por_Estado': estado_stats
                }
                
                excel_data = crear_excel_formateado_corregido(
                    dataframes_excel,
                    "Reporte de Movimientos y Estados",
                    fecha_inicio,
                    fecha_fin
                )
                
                if excel_data:
                    st.download_button(
                        label="Descargar Reporte en Excel",
                        data=excel_data,
                        file_name=f"movimientos_estados_{fecha_inicio}_{fecha_fin}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            else:
                st.info("No hay datos de cambios de estado en el período seleccionado.")
                
    except Exception as e:
        st.error(f"Error generando reporte: {e}")

def generar_reporte_costos_mantenimiento(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df):
    """Reporte de costos de mantenimiento - CORREGIDO"""
    st.subheader("Reporte de Costos de Mantenimiento")
    
    try:
        with get_conn() as conn:
            vehiculo_id = obtener_vehiculo_id_seguro(vehiculo_seleccionado, vehiculos_df)
            
            vehiculo_filter = ""
            params = [empresa_id, fecha_inicio, fecha_fin]
            
            if vehiculo_id:
                vehiculo_filter = "AND m.id = ?"
                params.append(vehiculo_id)
            
            query = f"""
            SELECT 
                m.name as vehiculo,
                COALESCE(m.identifier, 'N/A') as identifier,
                mt.name as tipo_mantenimiento,
                COALESCE(mr.start_date, mr.created_at) as fecha,
                COALESCE(mr.cost, 0) as costo,
                COALESCE(mr.parts_used, 'No especificado') as repuestos,
                COALESCE(mr.performed_by, 'No especificado') as realizado_por
            FROM maintenance_records mr
            JOIN machinery m ON mr.machinery_id = m.id
            JOIN maintenance_types mt ON mr.maintenance_type_id = mt.id
            WHERE m.company_id = ? 
            AND date(COALESCE(mr.start_date, mr.created_at)) >= ? 
            AND date(COALESCE(mr.start_date, mr.created_at)) <= ?
            {vehiculo_filter}
            ORDER BY fecha DESC
            """
            
            df_costos = pd.read_sql_query(query, conn, params=params)
            
            if not df_costos.empty:
                # Mostrar datos
                st.dataframe(df_costos, use_container_width=True)
                
                # Métricas principales
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                
                with col_m1:
                    costo_total = df_costos['costo'].sum()
                    st.metric("Costo Total", f"${costo_total:,.2f}")
                
                with col_m2:
                    costo_promedio = df_costos['costo'].mean()
                    st.metric("Costo Promedio", f"${costo_promedio:,.2f}")
                
                with col_m3:
                    total_mantenimientos = len(df_costos)
                    st.metric("Total Mantenimientos", total_mantenimientos)
                
                with col_m4:
                    mantenimientos_con_costo = len(df_costos[df_costos['costo'] > 0])
                    st.metric("Con Costo Registrado", mantenimientos_con_costo)
                
                # Análisis por vehículo y tipo
                costos_vehiculo = df_costos.groupby('vehiculo')['costo'].sum().sort_values(ascending=False).reset_index()
                costos_tipo = df_costos.groupby('tipo_mantenimiento')['costo'].sum().sort_values(ascending=False).reset_index()
                
                # Gráficos
                col_chart1, col_chart2 = st.columns(2)
                
                with col_chart1:
                    if len(costos_vehiculo) > 0:
                        fig1 = px.bar(costos_vehiculo, x='vehiculo', y='costo',
                                    title='Costos por Vehículo')
                        st.plotly_chart(fig1, use_container_width=True)
                
                with col_chart2:
                    if len(costos_tipo) > 0:
                        fig2 = px.bar(costos_tipo, x='tipo_mantenimiento', y='costo',
                                    title='Costos por Tipo de Mantenimiento')
                        st.plotly_chart(fig2, use_container_width=True)
                
                # Botón de descarga
                dataframes_excel = {
                    'Detalle_Costos': df_costos,
                    'Costos_por_Vehiculo': costos_vehiculo,
                    'Costos_por_Tipo': costos_tipo
                }
                
                excel_data = crear_excel_formateado_corregido(
                    dataframes_excel,
                    "Reporte de Costos de Mantenimiento",
                    fecha_inicio,
                    fecha_fin
                )
                
                if excel_data:
                    st.download_button(
                        label="Descargar Reporte en Excel",
                        data=excel_data,
                        file_name=f"costos_mantenimiento_{fecha_inicio}_{fecha_fin}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            else:
                st.info("No hay datos de costos en el período seleccionado.")
                
    except Exception as e:
        st.error(f"Error generando reporte: {e}")

def mostrar_preview_reporte(reporte_key, titulo_reporte):
    """Muestra preview para reportes en desarrollo"""
    st.subheader(f"Preview: {titulo_reporte}")
    
    previews = {
        "cumplimiento_preventivos": "Análisis de cumplimiento de mantenimientos programados vs realizados",
        "utilizacion_vehiculos": "Horas de operación y kilómetros recorridos por vehículo",
        "disponibilidad_flota": "Porcentaje de tiempo operativo vs mantenimiento/inactivo",
        "repuestos_materiales": "Análisis de repuestos más utilizados y sus costos",
        "rentabilidad_vehiculo": "Análisis costo-beneficio por unidad",
        "consumibles": "Consumo de combustible, aceites y otros consumibles",
        "historial_fallas": "Registro y análisis de fallas por vehículo y tipo",
        "efficiency_mantenimiento": "Indicadores MTBF, MTTR y eficiencia general",
        "cumplimiento_legal": "Seguimiento de vencimientos y obligaciones legales"
    }
    
    descripcion = previews.get(reporte_key, "Descripción no disponible")
    st.info(f"Descripción: {descripcion}")
    st.write("Este reporte incluirá:")
    st.write("- Datos detallados y filtros avanzados")
    st.write("- Gráficos interactivos") 
    st.write("- Exportación a Excel con formato profesional")
    st.write("- Métricas y KPIs relevantes")

# Funciones stub para reportes no implementados
def generar_reporte_cumplimiento_preventivos(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df):
    st.info("Reporte de Cumplimiento de Preventivos - En desarrollo")

def generar_reporte_utilizacion_vehiculos(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df):
    st.info("Reporte de Utilización de Vehículos - En desarrollo")

def generar_reporte_disponibilidad_flota(empresa_id, fecha_inicio, fecha_fin, vehiculo_seleccionado, vehiculos_df):
    st.info("Reporte de Disponibilidad de Flota - En desarrollo")

def mostrar_historial_mantenimientos_simple(empresa_id):
    """Historial de mantenimientos simplificado"""
    try:
        with get_conn() as conn:
            maintenance_query = """
            SELECT 
                m.name as machine_name,
                m.identifier,
                mt.name as maintenance_type,
                mr.created_at,
                mr.performed_by,
                mr.hour_meter_end,
                mr.odometer_end,
                mr.cost
            FROM maintenance_records mr
            JOIN machinery m ON mr.machinery_id = m.id
            JOIN maintenance_types mt ON mr.maintenance_type_id = mt.id
            WHERE m.company_id = ?
            ORDER BY mr.created_at DESC
            LIMIT 50
            """
            
            maintenance_df = pd.read_sql_query(maintenance_query, conn, params=(empresa_id,))
            
            if not maintenance_df.empty:
                display_df = maintenance_df.copy()
                display_df['created_at'] = pd.to_datetime(display_df['created_at']).dt.strftime('%Y-%m-%d')
                display_df['cost'] = display_df['cost'].fillna(0).apply(lambda x: f"${x:.2f}" if x > 0 else "No especificado")
                
                display_df = display_df.rename(columns={
                    'machine_name': 'Vehículo',
                    'identifier': 'Matrícula',
                    'maintenance_type': 'Tipo',
                    'created_at': 'Fecha',
                    'performed_by': 'Realizado por',
                    'hour_meter_end': 'Horómetro',
                    'odometer_end': 'Odómetro (km)',
                    'cost': 'Costo'
                })
                
                st.dataframe(display_df, use_container_width=True)
                
                # Estadísticas resumidas
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Mantenimientos", len(display_df))
                with col2:
                    total_cost = maintenance_df['cost'].fillna(0).sum()
                    st.metric("Costo Total", f"${total_cost:.2f}")
                with col3:
                    avg_cost = maintenance_df['cost'].fillna(0).mean() if len(maintenance_df) > 0 else 0
                    st.metric("Costo Promedio", f"${avg_cost:.2f}")
            else:
                st.info("No hay mantenimientos registrados.")
                
    except Exception as e:
        st.error(f"Error al cargar historial de mantenimientos: {e}")

# Funciones de compatibilidad para mantener la interfaz existente
def get_maintenance_summary_safe(empresa_id):
    """Obtiene resumen de mantenimiento de forma segura"""
    try:
        machinery_df = safe_get_machinery_data(empresa_id)
        if machinery_df.empty:
            return {'total': 0, 'active': 0, 'maintenance': 0, 'inactive': 0}
        
        def safe_status_count(status_value):
            return len(machinery_df[machinery_df['status'].str.contains(status_value, case=False, na=False)])
        
        return {
            'total': len(machinery_df),
            'active': safe_status_count('Activ'),
            'maintenance': safe_status_count('Mantenimiento'),
            'inactive': safe_status_count('Inactiv'),
        }
    except Exception:
        return {'total': 0, 'active': 0, 'maintenance': 0, 'inactive': 0}

def get_critical_maintenance_alerts_safe(empresa_id):
    """Obtiene alertas críticas de forma segura"""
    try:
        machinery_df = safe_get_machinery_data(empresa_id)
        alerts = []
        
        with get_conn() as conn:
            # Obtener el primer tipo de mantenimiento preventivo
            preventive_types = pd.read_sql_query("""
                SELECT id FROM maintenance_types WHERE is_preventive = 1 LIMIT 1
            """, conn)
            
            if not preventive_types.empty:
                main_type_id = preventive_types.iloc[0]['id']
                
                for _, machine in machinery_df.iterrows():
                    current_hours = float(machine.get('current_hours', 0))
                    current_km = float(machine.get('current_odometer', 0))
                    
                    status = get_maintenance_status_for_machine(
                        machine['id'], main_type_id, current_hours, current_km
                    )
                    
                    if status and status['overall_status'] in ['CRITICAL', 'WARNING']:
                        alerts.append({
                            'machine_id': machine['id'],
                            'machine_name': machine.get('name', 'Sin nombre'),
                            'identifier': machine.get('identifier', 'N/A'),
                            'message': f"Mantenimiento {status['overall_status']} - H: {status['hours_remaining']:.1f}, Km: {status['km_remaining']:.1f}",
                            'type': status['overall_status']
                        })
        
        return alerts
    except Exception:
        return []

# Funciones de compatibilidad
def get_maintenance_summary(empresa_id):
    """Función de compatibilidad"""
    return get_maintenance_summary_safe(empresa_id)

def normalize_status(status):
    """Normaliza los estados de máquina para consistencia"""
    status_mapping = {
        'Activo': 'Active', 'Activa': 'Active', 'Active': 'Active',
        'Mantenimiento': 'Maintenance', 'Maintenance': 'Maintenance',
        'Inactivo': 'Inactive', 'Inactiva': 'Inactive', 'Inactive': 'Inactive'
    }
    return status_mapping.get(status, 'Active')

def get_localized_status(status):
    """Convierte estados a español para la interfaz"""
    status_mapping = {
        'Active': 'Activa',
        'Maintenance': 'Mantenimiento',
        'Inactive': 'Inactiva'
    }
    return status_mapping.get(status, 'Activa')

def debug_and_fix_maintenance_types_table():
    """Función específica para diagnosticar y reparar la tabla maintenance_types"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            st.write("### 🔧 Diagnóstico de Tabla maintenance_types")
            
            # Verificar si la tabla existe
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_types'")
            table_exists = cur.fetchone() is not None
            
            st.write(f"**Tabla existe:** {table_exists}")
            
            if table_exists:
                # Verificar estructura actual
                cur.execute("PRAGMA table_info(maintenance_types)")
                columns_info = cur.fetchall()
                current_columns = [col[1] for col in columns_info]
                
                st.write("**Columnas actuales:**")
                for col in current_columns:
                    st.write(f"- {col}")
                
                # Verificar cuántos registros hay
                cur.execute("SELECT COUNT(*) FROM maintenance_types")
                record_count = cur.fetchone()[0]
                st.write(f"**Número de registros:** {record_count}")
                
                # Columnas que necesitamos
                required_columns = ['default_hours_interval', 'default_km_interval', 'is_preventive']
                missing_columns = [col for col in required_columns if col not in current_columns]
                
                if missing_columns:
                    st.warning(f"**Columnas faltantes:** {missing_columns}")
                    
                    if st.button("🔨 Reparar Tabla Automáticamente"):
                        try:
                            # Agregar columnas faltantes
                            for col in missing_columns:
                                if col == 'default_hours_interval':
                                    cur.execute("ALTER TABLE maintenance_types ADD COLUMN default_hours_interval REAL DEFAULT 5000")
                                elif col == 'default_km_interval':
                                    cur.execute("ALTER TABLE maintenance_types ADD COLUMN default_km_interval REAL DEFAULT 5000")
                                elif col == 'is_preventive':
                                    cur.execute("ALTER TABLE maintenance_types ADD COLUMN is_preventive INTEGER DEFAULT 1")
                                
                                st.success(f"✅ Columna {col} agregada")
                            
                            # Actualizar registros existentes
                            cur.execute("""
                                UPDATE maintenance_types 
                                SET default_hours_interval = CASE 
                                    WHEN name = 'Reparación Correctiva' THEN 0 
                                    ELSE 5000 
                                END,
                                default_km_interval = CASE 
                                    WHEN name = 'Reparación Correctiva' THEN 0 
                                    ELSE 5000 
                                END,
                                is_preventive = CASE 
                                    WHEN name = 'Reparación Correctiva' THEN 0 
                                    ELSE 1 
                                END
                                WHERE default_hours_interval IS NULL OR default_km_interval IS NULL OR is_preventive IS NULL
                            """)
                            
                            conn.commit()
                            st.success("🎉 Tabla reparada exitosamente!")
                            st.info("Recarga la página para ver los cambios")
                            
                        except Exception as e:
                            st.error(f"Error reparando tabla: {e}")
                            
                            # Opción nuclear: recrear tabla
                            st.warning("**Opción alternativa: Recrear tabla completa**")
                            if st.button("⚠️ Recrear Tabla (Perderás datos existentes)"):
                                try:
                                    # Respaldar datos existentes
                                    cur.execute("SELECT id, name, description FROM maintenance_types")
                                    backup_data = cur.fetchall()
                                    
                                    # Eliminar tabla existente
                                    cur.execute("DROP TABLE maintenance_types")
                                    
                                    # Crear tabla nueva
                                    cur.execute("""
                                        CREATE TABLE maintenance_types (
                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                            name TEXT UNIQUE NOT NULL,
                                            description TEXT,
                                            default_hours_interval REAL DEFAULT 5000,
                                            default_km_interval REAL DEFAULT 5000,
                                            is_preventive INTEGER DEFAULT 1,
                                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                                        )
                                    """)
                                    
                                    # Restaurar datos con valores por defecto
                                    for old_id, name, description in backup_data:
                                        is_preventive = 0 if 'correctiva' in name.lower() or 'reparación' in name.lower() else 1
                                        hours_interval = 0 if is_preventive == 0 else 5000
                                        km_interval = 0 if is_preventive == 0 else 5000
                                        
                                        cur.execute("""
                                            INSERT INTO maintenance_types 
                                            (name, description, default_hours_interval, default_km_interval, is_preventive)
                                            VALUES (?, ?, ?, ?, ?)
                                        """, (name, description, hours_interval, km_interval, is_preventive))
                                    
                                    conn.commit()
                                    st.success("🎉 Tabla recreada exitosamente!")
                                    
                                except Exception as e2:
                                    st.error(f"Error recreando tabla: {e2}")
                else:
                    st.success("✅ Tabla maintenance_types tiene todas las columnas necesarias")
                    
                    # Mostrar contenido actual
                    cur.execute("SELECT name, default_hours_interval, default_km_interval, is_preventive FROM maintenance_types")
                    data = cur.fetchall()
                    
                    st.write("**Contenido actual:**")
                    for name, hours, km, is_prev in data:
                        prev_text = "Preventivo" if is_prev else "Correctivo"
                        st.write(f"- {name}: {hours}h / {km}km ({prev_text})")
            
            else:
                st.error("La tabla maintenance_types no existe")
                if st.button("🔨 Crear Tabla maintenance_types"):
                    try:
                        cur.execute("""
                            CREATE TABLE maintenance_types (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT UNIQUE NOT NULL,
                                description TEXT,
                                default_hours_interval REAL DEFAULT 5000,
                                default_km_interval REAL DEFAULT 5000,
                                is_preventive INTEGER DEFAULT 1,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Insertar datos por defecto
                        default_types = [
                            ("Mantenimiento Preventivo", "Mantenimiento rutinario programado", 5000, 5000, 1),
                            ("Cambio de Aceite Motor", "Cambio de aceite del motor y filtros", 2000, 10000, 1),
                            ("Reparación Correctiva", "Reparación de fallas o daños", 0, 0, 0)
                        ]
                        
                        for name, desc, hours, km, is_prev in default_types:
                            cur.execute("""
                                INSERT INTO maintenance_types 
                                (name, description, default_hours_interval, default_km_interval, is_preventive)
                                VALUES (?, ?, ?, ?, ?)
                            """, (name, desc, hours, km, is_prev))
                        
                        conn.commit()
                        st.success("✅ Tabla creada con datos por defecto")
                        
                    except Exception as e:
                        st.error(f"Error creando tabla: {e}")
                        
    except Exception as e:
        st.error(f"Error en diagnóstico: {e}")

def fix_setup_maintenance_intervals_for_machine(machinery_id):
    """Versión corregida que maneja el error de columnas faltantes"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Primero verificar que la tabla maintenance_types tiene las columnas necesarias
            cur.execute("PRAGMA table_info(maintenance_types)")
            columns = [row[1] for row in cur.fetchall()]
            
            if 'default_hours_interval' not in columns:
                st.warning(f"⚠️ Tabla maintenance_types necesita migración. Usa el diagnóstico para repararla.")
                return False
            
            # Si las columnas existen, proceder normalmente
            types_query = """
                SELECT id, default_hours_interval, default_km_interval 
                FROM maintenance_types 
                WHERE is_preventive = 1
            """
            
            cur.execute(types_query)
            types_data = cur.fetchall()
            
            for type_id, hours_interval, km_interval in types_data:
                # Verificar si ya existe configuración
                existing = cur.execute("""
                    SELECT id FROM maintenance_intervals 
                    WHERE machinery_id = ? AND maintenance_type_id = ?
                """, (machinery_id, type_id)).fetchone()
                
                if not existing:
                    # Crear configuración por defecto
                    cur.execute("""
                        INSERT OR IGNORE INTO maintenance_intervals 
                        (machinery_id, maintenance_type_id, hours_interval, km_interval) 
                        VALUES (?, ?, ?, ?)
                    """, (machinery_id, type_id, hours_interval, km_interval))
            
            conn.commit()
            return True
            
    except sqlite3.Error as e:
        st.error(f"Error SQL configurando intervalos: {e}")
        return False
    except Exception as e:
        st.error(f"Error configurando intervalos: {e}")
        return False
    
def mostrar_diagnostico_tablas():
    """Función temporal para diagnosticar y reparar tablas"""
    st.subheader("Diagnóstico y Reparación de Base de Datos")
    
    debug_and_fix_maintenance_types_table()

def debug_and_fix_maintenance_intervals_table():
    """Función específica para diagnosticar y reparar la tabla maintenance_intervals"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            st.write("### 🔧 Diagnóstico de Tabla maintenance_intervals")
            
            # Verificar si la tabla existe
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_intervals'")
            table_exists = cur.fetchone() is not None
            
            st.write(f"**Tabla existe:** {table_exists}")
            
            if table_exists:
                # Verificar estructura actual
                cur.execute("PRAGMA table_info(maintenance_intervals)")
                columns_info = cur.fetchall()
                current_columns = [col[1] for col in columns_info]
                
                st.write("**Columnas actuales:**")
                for col in current_columns:
                    st.write(f"- {col}")
                
                # Verificar cuántos registros hay
                cur.execute("SELECT COUNT(*) FROM maintenance_intervals")
                record_count = cur.fetchone()[0]
                st.write(f"**Número de registros:** {record_count}")
                
                # Columnas que necesitamos
                required_columns = ['is_active', 'updated_at']
                missing_columns = [col for col in required_columns if col not in current_columns]
                
                if missing_columns:
                    st.warning(f"**Columnas faltantes:** {missing_columns}")
                    
                    if st.button("🔨 Reparar Tabla maintenance_intervals"):
                        try:
                            # Agregar columnas faltantes
                            for col in missing_columns:
                                if col == 'is_active':
                                    cur.execute("ALTER TABLE maintenance_intervals ADD COLUMN is_active INTEGER DEFAULT 1")
                                elif col == 'updated_at':
                                    cur.execute("ALTER TABLE maintenance_intervals ADD COLUMN updated_at TEXT DEFAULT CURRENT_TIMESTAMP")
                                
                                st.success(f"✅ Columna {col} agregada")
                            
                            # Actualizar registros existentes con valores por defecto
                            cur.execute("""
                                UPDATE maintenance_intervals 
                                SET is_active = 1
                                WHERE is_active IS NULL
                            """)
                            
                            cur.execute("""
                                UPDATE maintenance_intervals 
                                SET updated_at = CURRENT_TIMESTAMP
                                WHERE updated_at IS NULL
                            """)
                            
                            conn.commit()
                            st.success("🎉 Tabla maintenance_intervals reparada exitosamente!")
                            
                        except Exception as e:
                            st.error(f"Error reparando tabla: {e}")
                else:
                    st.success("✅ Tabla maintenance_intervals tiene todas las columnas necesarias")
            
            else:
                st.error("La tabla maintenance_intervals no existe")
                if st.button("🔨 Crear Tabla maintenance_intervals"):
                    try:
                        cur.execute("""
                            CREATE TABLE maintenance_intervals (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                machinery_id INTEGER,
                                maintenance_type_id INTEGER,
                                hours_interval REAL NOT NULL,
                                km_interval REAL NOT NULL,
                                is_active INTEGER DEFAULT 1,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                UNIQUE(machinery_id, maintenance_type_id),
                                FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
                                FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types(id)
                            )
                        """)
                        
                        conn.commit()
                        st.success("✅ Tabla maintenance_intervals creada")
                        
                    except Exception as e:
                        st.error(f"Error creando tabla: {e}")
                        
    except Exception as e:
        st.error(f"Error en diagnóstico de maintenance_intervals: {e}")

def get_maintenance_status_for_machine_safe(machinery_id, maintenance_type_id, current_hours, current_km):
    """Versión segura que maneja columnas faltantes"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Verificar columnas de maintenance_intervals
            cur.execute("PRAGMA table_info(maintenance_intervals)")
            columns = [row[1] for row in cur.fetchall()]
            
            # Construir query dinámicamente basado en columnas disponibles
            if 'is_active' in columns:
                interval_query = """
                    SELECT hours_interval, km_interval 
                    FROM maintenance_intervals 
                    WHERE machinery_id = ? AND maintenance_type_id = ? AND is_active = 1
                """
            else:
                interval_query = """
                    SELECT hours_interval, km_interval 
                    FROM maintenance_intervals 
                    WHERE machinery_id = ? AND maintenance_type_id = ?
                """
            
            interval_result = conn.execute(interval_query, (machinery_id, maintenance_type_id)).fetchone()
            
            if not interval_result:
                # Si no hay intervalos específicos, usar los por defecto del tipo
                default_query = """
                    SELECT default_hours_interval, default_km_interval 
                    FROM maintenance_types 
                    WHERE id = ?
                """
                default_result = conn.execute(default_query, (maintenance_type_id,)).fetchone()
                if default_result:
                    hours_interval, km_interval = default_result
                else:
                    hours_interval, km_interval = 5000, 5000  # Fallback
            else:
                hours_interval, km_interval = interval_result
            
            # Obtener el último mantenimiento de este tipo para esta máquina
            last_maint_query = """
                SELECT hour_meter_end, odometer_end, created_at
                FROM maintenance_records 
                WHERE machinery_id = ? AND maintenance_type_id = ?
                ORDER BY created_at DESC 
                LIMIT 1
            """
            last_maint = conn.execute(last_maint_query, (machinery_id, maintenance_type_id)).fetchone()
            
            if last_maint:
                last_hours = float(last_maint[0] or 0)
                last_km = float(last_maint[1] or 0)
                last_date = last_maint[2]
            else:
                # Si no hay mantenimiento previo, usar 0 como base
                last_hours = 0
                last_km = 0
                last_date = None
            
            # Calcular próximo mantenimiento
            next_maint_hours = last_hours + hours_interval
            next_maint_km = last_km + km_interval
            
            # Calcular cuánto falta
            hours_remaining = next_maint_hours - current_hours
            km_remaining = next_maint_km - current_km
            
            # Obtener umbrales de alertas
            alert_config = get_alert_thresholds_safe()
            
            # Determinar estado basado en lo que esté más cerca
            hours_status = get_alert_level(hours_remaining, alert_config['hours'])
            km_status = get_alert_level(km_remaining, alert_config['km'])
            
            # El estado general es el más crítico de los dos
            if hours_status == 'CRITICAL' or km_status == 'CRITICAL':
                overall_status = 'CRITICAL'
            elif hours_status == 'WARNING' or km_status == 'WARNING':
                overall_status = 'WARNING'
            elif hours_status == 'ALERT' or km_status == 'ALERT':
                overall_status = 'ALERT'
            else:
                overall_status = 'NORMAL'
            
            return {
                'hours_interval': hours_interval,
                'km_interval': km_interval,
                'last_maint_hours': last_hours,
                'last_maint_km': last_km,
                'last_maint_date': last_date,
                'next_maint_hours': next_maint_hours,
                'next_maint_km': next_maint_km,
                'hours_remaining': hours_remaining,
                'km_remaining': km_remaining,
                'hours_status': hours_status,
                'km_status': km_status,
                'overall_status': overall_status
            }
            
    except Exception as e:
        st.error(f"Error calculando estado de mantenimiento: {e}")
        return None

def get_alert_thresholds_safe():
    """Versión segura de get_alert_thresholds que maneja errores"""
    try:
        with get_conn() as conn:
            # Verificar si la tabla alert_configurations existe
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alert_configurations'")
            if not cur.fetchone():
                # Tabla no existe, usar valores por defecto
                return {
                    'hours': {'warning': 200, 'alert': 100, 'critical': 50},
                    'km': {'warning': 500, 'alert': 300, 'critical': 100}
                }
            
            hours_config = conn.execute("""
                SELECT warning_threshold, alert_threshold, critical_threshold 
                FROM alert_configurations 
                WHERE config_name = 'hours_before_maintenance' AND is_active = 1
            """).fetchone()
            
            km_config = conn.execute("""
                SELECT warning_threshold, alert_threshold, critical_threshold 
                FROM alert_configurations 
                WHERE config_name = 'km_before_maintenance' AND is_active = 1
            """).fetchone()
            
            return {
                'hours': {
                    'warning': hours_config[0] if hours_config else 200,
                    'alert': hours_config[1] if hours_config else 100,
                    'critical': hours_config[2] if hours_config else 50
                },
                'km': {
                    'warning': km_config[0] if km_config else 500,
                    'alert': km_config[1] if km_config else 300,
                    'critical': km_config[2] if km_config else 100
                }
            }
    except Exception:
        return {
            'hours': {'warning': 200, 'alert': 100, 'critical': 50},
            'km': {'warning': 500, 'alert': 300, 'critical': 100}
        }

def mostrar_diagnostico_completo():
    """Función temporal para diagnosticar todas las tablas"""
    st.subheader("Diagnóstico Completo de Base de Datos")
    
    tab1, tab2 = st.tabs(["maintenance_types", "maintenance_intervals"])
    
    with tab1:
        debug_and_fix_maintenance_types_table()
    
    with tab2:
        debug_and_fix_maintenance_intervals_table()

def debug_and_fix_maintenance_records_table():
    """Función específica para diagnosticar y reparar la tabla maintenance_records"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            st.write("### 🔧 Diagnóstico de Tabla maintenance_records")
            
            # Verificar si la tabla existe
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_records'")
            table_exists = cur.fetchone() is not None
            
            st.write(f"**Tabla existe:** {table_exists}")
            
            if table_exists:
                # Verificar estructura actual
                cur.execute("PRAGMA table_info(maintenance_records)")
                columns_info = cur.fetchall()
                current_columns = [col[1] for col in columns_info]
                
                st.write("**Columnas actuales:**")
                for col in current_columns:
                    st.write(f"- {col}")
                
                # Verificar cuántos registros hay
                cur.execute("SELECT COUNT(*) FROM maintenance_records")
                record_count = cur.fetchone()[0]
                st.write(f"**Número de registros:** {record_count}")
                
                # Columnas que necesitamos
                required_columns = [
                    'hour_meter_start', 'hour_meter_end', 
                    'odometer_start', 'odometer_end',
                    'start_date', 'end_date'
                ]
                missing_columns = [col for col in required_columns if col not in current_columns]
                
                if missing_columns:
                    st.warning(f"**Columnas faltantes:** {missing_columns}")
                    
                    if st.button("🔨 Reparar Tabla maintenance_records"):
                        try:
                            # Agregar columnas faltantes
                            for col in missing_columns:
                                if col in ['hour_meter_start', 'hour_meter_end', 'odometer_start', 'odometer_end']:
                                    cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} REAL")
                                elif col in ['start_date', 'end_date']:
                                    cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} TEXT")
                                
                                st.success(f"✅ Columna {col} agregada")
                            
                            # Si hay registros existentes, intentar migrar datos
                            if record_count > 0:
                                st.info("Migrando datos existentes...")
                                
                                # Si existe created_at pero no start_date, copiar el valor
                                if 'created_at' in current_columns and 'start_date' in missing_columns:
                                    cur.execute("UPDATE maintenance_records SET start_date = created_at WHERE start_date IS NULL")
                                    cur.execute("UPDATE maintenance_records SET end_date = created_at WHERE end_date IS NULL")
                                
                                # Valores por defecto para campos numéricos
                                for col in ['hour_meter_start', 'hour_meter_end', 'odometer_start', 'odometer_end']:
                                    if col in missing_columns:
                                        cur.execute(f"UPDATE maintenance_records SET {col} = 0 WHERE {col} IS NULL")
                            
                            conn.commit()
                            st.success("🎉 Tabla maintenance_records reparada exitosamente!")
                            
                        except Exception as e:
                            st.error(f"Error reparando tabla: {e}")
                else:
                    st.success("✅ Tabla maintenance_records tiene todas las columnas necesarias")
                    
                    # Mostrar algunos registros de ejemplo
                    if record_count > 0:
                        cur.execute("""
                            SELECT m.name, mt.name, mr.created_at, 
                                   COALESCE(mr.hour_meter_end, 0) as hours,
                                   COALESCE(mr.odometer_end, 0) as km
                            FROM maintenance_records mr
                            JOIN machinery m ON mr.machinery_id = m.id
                            JOIN maintenance_types mt ON mr.maintenance_type_id = mt.id
                            ORDER BY mr.created_at DESC
                            LIMIT 5
                        """)
                        records = cur.fetchall()
                        
                        st.write("**Registros recientes:**")
                        for machine, maint_type, date, hours, km in records:
                            st.write(f"- {machine}: {maint_type} ({date}) - {hours}h, {km}km")
            
            else:
                st.error("La tabla maintenance_records no existe")
                if st.button("🔨 Crear Tabla maintenance_records"):
                    try:
                        cur.execute("""
                            CREATE TABLE maintenance_records (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                machinery_id INTEGER,
                                maintenance_type_id INTEGER,
                                start_date TEXT,
                                end_date TEXT,
                                performed_by TEXT,
                                odometer_start REAL,
                                odometer_end REAL,
                                hour_meter_start REAL,
                                hour_meter_end REAL,
                                cost REAL,
                                description TEXT,
                                parts_used TEXT,
                                notes TEXT,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
                                FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types(id)
                            )
                        """)
                        
                        conn.commit()
                        st.success("✅ Tabla maintenance_records creada")
                        
                    except Exception as e:
                        st.error(f"Error creando tabla: {e}")
                        
    except Exception as e:
        st.error(f"Error en diagnóstico de maintenance_records: {e}")

def get_maintenance_status_for_machine_final_safe(machinery_id, maintenance_type_id, current_hours, current_km):
    """Versión final super segura que maneja TODAS las posibles columnas faltantes"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Verificar columnas de maintenance_intervals
            cur.execute("PRAGMA table_info(maintenance_intervals)")
            mi_columns = [row[1] for row in cur.fetchall()]
            
            # Verificar columnas de maintenance_records
            cur.execute("PRAGMA table_info(maintenance_records)")
            mr_columns = [row[1] for row in cur.fetchall()]
            
            # Construir query de intervalos dinámicamente
            if 'is_active' in mi_columns:
                interval_query = """
                    SELECT hours_interval, km_interval 
                    FROM maintenance_intervals 
                    WHERE machinery_id = ? AND maintenance_type_id = ? AND is_active = 1
                """
            else:
                interval_query = """
                    SELECT hours_interval, km_interval 
                    FROM maintenance_intervals 
                    WHERE machinery_id = ? AND maintenance_type_id = ?
                """
            
            interval_result = conn.execute(interval_query, (machinery_id, maintenance_type_id)).fetchone()
            
            if not interval_result:
                # Usar valores por defecto del tipo
                default_query = """
                    SELECT default_hours_interval, default_km_interval 
                    FROM maintenance_types 
                    WHERE id = ?
                """
                default_result = conn.execute(default_query, (maintenance_type_id,)).fetchone()
                if default_result:
                    hours_interval, km_interval = default_result
                else:
                    hours_interval, km_interval = 5000, 5000
            else:
                hours_interval, km_interval = interval_result
            
            # Verificar si hay registros de mantenimiento Y qué columnas usar
            if not mr_columns:
                # Tabla no existe o no tiene columnas
                last_hours, last_km, last_date = 0, 0, None
            else:
                # Determinar qué columnas usar para cada campo
                hour_field = None
                if 'hour_meter_end' in mr_columns:
                    hour_field = 'hour_meter_end'
                elif 'current_hours' in mr_columns:
                    hour_field = 'current_hours'
                
                odo_field = None
                if 'odometer_end' in mr_columns:
                    odo_field = 'odometer_end'
                elif 'current_odometer' in mr_columns:
                    odo_field = 'current_odometer'
                
                date_field = None
                if 'created_at' in mr_columns:
                    date_field = 'created_at'
                elif 'start_date' in mr_columns:
                    date_field = 'start_date'
                elif 'date' in mr_columns:
                    date_field = 'date'
                
                # Si tenemos al menos un campo de fecha, hacer la consulta
                if date_field:
                    select_parts = []
                    if hour_field:
                        select_parts.append(f"COALESCE({hour_field}, 0) as hours")
                    else:
                        select_parts.append("0 as hours")
                    
                    if odo_field:
                        select_parts.append(f"COALESCE({odo_field}, 0) as km")
                    else:
                        select_parts.append("0 as km")
                    
                    select_parts.append(f"{date_field} as date")
                    
                    last_maint_query = f"""
                        SELECT {', '.join(select_parts)}
                        FROM maintenance_records 
                        WHERE machinery_id = ? AND maintenance_type_id = ?
                        ORDER BY {date_field} DESC 
                        LIMIT 1
                    """
                    
                    try:
                        last_maint = conn.execute(last_maint_query, (machinery_id, maintenance_type_id)).fetchone()
                        
                        if last_maint:
                            last_hours = float(last_maint[0] or 0)
                            last_km = float(last_maint[1] or 0)
                            last_date = last_maint[2]
                        else:
                            last_hours, last_km, last_date = 0, 0, None
                    except Exception:
                        # Si falla la consulta, usar valores por defecto
                        last_hours, last_km, last_date = 0, 0, None
                else:
                    # No hay campos de fecha utilizables
                    last_hours, last_km, last_date = 0, 0, None
            
            # Calcular próximo mantenimiento
            next_maint_hours = last_hours + hours_interval
            next_maint_km = last_km + km_interval
            
            # Calcular cuánto falta
            hours_remaining = next_maint_hours - current_hours
            km_remaining = next_maint_km - current_km
            
            # Obtener umbrales de alertas
            alert_config = get_alert_thresholds_safe()
            
            # Determinar estado basado en lo que esté más cerca
            hours_status = get_alert_level(hours_remaining, alert_config['hours'])
            km_status = get_alert_level(km_remaining, alert_config['km'])
            
            # Estado general es el más crítico
            if hours_status == 'CRITICAL' or km_status == 'CRITICAL':
                overall_status = 'CRITICAL'
            elif hours_status == 'WARNING' or km_status == 'WARNING':
                overall_status = 'WARNING'
            elif hours_status == 'ALERT' or km_status == 'ALERT':
                overall_status = 'ALERT'
            else:
                overall_status = 'NORMAL'
            
            return {
                'hours_interval': hours_interval,
                'km_interval': km_interval,
                'last_maint_hours': last_hours,
                'last_maint_km': last_km,
                'last_maint_date': last_date,
                'next_maint_hours': next_maint_hours,
                'next_maint_km': next_maint_km,
                'hours_remaining': hours_remaining,
                'km_remaining': km_remaining,
                'hours_status': hours_status,
                'km_status': km_status,
                'overall_status': overall_status
            }
            
    except Exception as e:
        st.error(f"Error calculando estado de mantenimiento: {e}")
        # Retornar estructura segura en caso de cualquier error
        return {
            'hours_interval': 5000,
            'km_interval': 5000,
            'last_maint_hours': 0,
            'last_maint_km': 0,
            'last_maint_date': None,
            'next_maint_hours': 5000,
            'next_maint_km': 5000,
            'hours_remaining': max(0, 5000 - current_hours),
            'km_remaining': max(0, 5000 - current_km),
            'hours_status': 'NORMAL',
            'km_status': 'NORMAL',
            'overall_status': 'NORMAL'
        }

def debug_and_fix_maintenance_records_table_v2():
    """Versión mejorada para diagnosticar maintenance_records con created_at"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            st.write("### 🔧 Diagnóstico de Tabla maintenance_records (v2)")
            
            # Verificar si la tabla existe
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_records'")
            table_exists = cur.fetchone() is not None
            
            st.write(f"**Tabla existe:** {table_exists}")
            
            if table_exists:
                # Verificar estructura actual
                cur.execute("PRAGMA table_info(maintenance_records)")
                columns_info = cur.fetchall()
                current_columns = [col[1] for col in columns_info]
                
                st.write("**Columnas actuales:**")
                for col in current_columns:
                    st.write(f"- {col}")
                
                # Verificar cuántos registros hay
                cur.execute("SELECT COUNT(*) FROM maintenance_records")
                record_count = cur.fetchone()[0]
                st.write(f"**Número de registros:** {record_count}")
                
                # Todas las columnas que el sistema espera
                expected_columns = [
                    'created_at', 'start_date', 'end_date',
                    'hour_meter_start', 'hour_meter_end', 
                    'odometer_start', 'odometer_end',
                    'cost', 'description', 'parts_used', 'notes',
                    'performed_by'
                ]
                
                missing_columns = [col for col in expected_columns if col not in current_columns]
                
                if missing_columns:
                    st.warning(f"**Columnas faltantes:** {missing_columns}")
                    
                    if st.button("🔨 Agregar Todas las Columnas Faltantes"):
                        try:
                            # Agregar columnas faltantes
                            for col in missing_columns:
                                if col == 'created_at':
                                    cur.execute("ALTER TABLE maintenance_records ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP")
                                elif col in ['start_date', 'end_date']:
                                    cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} TEXT")
                                elif col in ['hour_meter_start', 'hour_meter_end', 'odometer_start', 'odometer_end', 'cost']:
                                    cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} REAL")
                                elif col in ['description', 'parts_used', 'notes', 'performed_by']:
                                    cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} TEXT")
                                
                                st.success(f"✅ Columna {col} agregada")
                            
                            # Actualizar registros existentes con valores por defecto
                            if record_count > 0:
                                # Si no hay created_at, usar fecha actual
                                cur.execute("UPDATE maintenance_records SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
                                
                                # Si hay created_at pero no start_date/end_date, copiar
                                if 'created_at' in current_columns or 'created_at' in missing_columns:
                                    cur.execute("UPDATE maintenance_records SET start_date = created_at WHERE start_date IS NULL")
                                    cur.execute("UPDATE maintenance_records SET end_date = created_at WHERE end_date IS NULL")
                                
                                # Valores numéricos por defecto
                                for col in ['hour_meter_start', 'hour_meter_end', 'odometer_start', 'odometer_end']:
                                    cur.execute(f"UPDATE maintenance_records SET {col} = 0 WHERE {col} IS NULL")
                                
                                cur.execute("UPDATE maintenance_records SET performed_by = 'admin' WHERE performed_by IS NULL")
                            
                            conn.commit()
                            st.success("🎉 Todas las columnas agregadas exitosamente!")
                            
                        except Exception as e:
                            st.error(f"Error agregando columnas: {e}")
                else:
                    st.success("✅ Tabla maintenance_records tiene todas las columnas necesarias")
            
            else:
                st.error("La tabla maintenance_records no existe")
                if st.button("🔨 Crear Tabla maintenance_records Completa"):
                    try:
                        cur.execute("""
                            CREATE TABLE maintenance_records (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                machinery_id INTEGER,
                                maintenance_type_id INTEGER,
                                start_date TEXT,
                                end_date TEXT,
                                performed_by TEXT,
                                odometer_start REAL,
                                odometer_end REAL,
                                hour_meter_start REAL,
                                hour_meter_end REAL,
                                cost REAL,
                                description TEXT,
                                parts_used TEXT,
                                notes TEXT,
                                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
                                FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types(id)
                            )
                        """)
                        
                        conn.commit()
                        st.success("✅ Tabla maintenance_records creada completamente")
                        
                    except Exception as e:
                        st.error(f"Error creando tabla: {e}")
                        
    except Exception as e:
        st.error(f"Error en diagnóstico de maintenance_records: {e}")

def mostrar_diagnostico_final():
    """Diagnóstico final con todas las tablas"""
    st.subheader("Diagnóstico Final de Base de Datos")
    
    st.info("Esta es la versión final del diagnóstico. Repara todas las tablas aquí y luego podrás quitar esta pestaña.")
    
    tab1, tab2, tab3 = st.tabs(["maintenance_types", "maintenance_intervals", "maintenance_records"])
    
    with tab1:
        debug_and_fix_maintenance_types_table()
    
    with tab2:
        debug_and_fix_maintenance_intervals_table()
    
    with tab3:
        debug_and_fix_maintenance_records_table_v2()

def debug_and_fix_maintenance_records_table_v3():
    """Versión corregida para SQLite que maneja el error de DEFAULT no-constante"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            st.write("### 🔧 Diagnóstico de Tabla maintenance_records (v3 - Compatible SQLite)")
            
            # Verificar si la tabla existe
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_records'")
            table_exists = cur.fetchone() is not None
            
            st.write(f"**Tabla existe:** {table_exists}")
            
            if table_exists:
                # Verificar estructura actual
                cur.execute("PRAGMA table_info(maintenance_records)")
                columns_info = cur.fetchall()
                current_columns = [col[1] for col in columns_info]
                
                st.write("**Columnas actuales:**")
                for col in current_columns:
                    st.write(f"- {col}")
                
                # Verificar cuántos registros hay
                cur.execute("SELECT COUNT(*) FROM maintenance_records")
                record_count = cur.fetchone()[0]
                st.write(f"**Número de registros:** {record_count}")
                
                # Columnas críticas que necesitamos
                critical_columns = {
                    'created_at': 'TEXT',
                    'start_date': 'TEXT',
                    'end_date': 'TEXT',
                    'hour_meter_start': 'REAL',
                    'hour_meter_end': 'REAL', 
                    'odometer_start': 'REAL',
                    'odometer_end': 'REAL',
                    'performed_by': 'TEXT'
                }
                
                missing_columns = [col for col in critical_columns.keys() if col not in current_columns]
                
                if missing_columns:
                    st.warning(f"**Columnas críticas faltantes:** {missing_columns}")
                    
                    # Opción 1: Agregar columnas una por una (SQLite compatible)
                    if st.button("🔨 Agregar Columnas Críticas (Método Seguro)"):
                        try:
                            for col in missing_columns:
                                col_type = critical_columns[col]
                                
                                if col == 'created_at':
                                    # Para created_at, agregar sin DEFAULT y luego actualizar
                                    cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} {col_type}")
                                    # Actualizar con fecha actual para registros existentes
                                    cur.execute(f"UPDATE maintenance_records SET {col} = datetime('now') WHERE {col} IS NULL")
                                else:
                                    # Para otras columnas, usar valores constantes por defecto
                                    if col_type == 'TEXT':
                                        if col == 'performed_by':
                                            cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} {col_type} DEFAULT 'admin'")
                                        else:
                                            cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} {col_type}")
                                    else:  # REAL
                                        cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col} {col_type} DEFAULT 0")
                                
                                st.success(f"✅ Columna {col} agregada")
                            
                            # Actualizar registros existentes
                            if record_count > 0:
                                # Si hay created_at, copiar a start_date y end_date
                                if 'start_date' in missing_columns and 'created_at' not in missing_columns:
                                    cur.execute("UPDATE maintenance_records SET start_date = created_at WHERE start_date IS NULL")
                                    cur.execute("UPDATE maintenance_records SET end_date = created_at WHERE end_date IS NULL")
                                elif 'start_date' in missing_columns and 'created_at' in missing_columns:
                                    cur.execute("UPDATE maintenance_records SET start_date = datetime('now') WHERE start_date IS NULL")
                                    cur.execute("UPDATE maintenance_records SET end_date = datetime('now') WHERE end_date IS NULL")
                            
                            conn.commit()
                            st.success("🎉 Columnas críticas agregadas exitosamente!")
                            
                        except Exception as e:
                            st.error(f"Error agregando columnas: {e}")
                    
                    # Opción 2: Recrear tabla (opción nuclear pero segura)
                    st.write("---")
                    st.warning("**Opción alternativa si lo anterior no funciona:**")
                    
                    if st.button("⚠️ Recrear Tabla Completa (Respaldará datos existentes)"):
                        try:
                            # Paso 1: Respaldar datos existentes
                            cur.execute("SELECT * FROM maintenance_records")
                            backup_data = cur.fetchall()
                            
                            # Obtener nombres de columnas actuales
                            cur.execute("PRAGMA table_info(maintenance_records)")
                            old_columns = [col[1] for col in cur.fetchall()]
                            
                            st.info(f"Respaldando {len(backup_data)} registros...")
                            
                            # Paso 2: Renombrar tabla actual
                            cur.execute("ALTER TABLE maintenance_records RENAME TO maintenance_records_backup")
                            
                            # Paso 3: Crear nueva tabla con estructura completa
                            cur.execute("""
                                CREATE TABLE maintenance_records (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    machinery_id INTEGER,
                                    maintenance_type_id INTEGER,
                                    start_date TEXT,
                                    end_date TEXT,
                                    performed_by TEXT DEFAULT 'admin',
                                    odometer_start REAL DEFAULT 0,
                                    odometer_end REAL DEFAULT 0,
                                    hour_meter_start REAL DEFAULT 0,
                                    hour_meter_end REAL DEFAULT 0,
                                    cost REAL,
                                    description TEXT,
                                    parts_used TEXT,
                                    notes TEXT,
                                    created_at TEXT,
                                    FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
                                    FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types(id)
                                )
                            """)
                            
                            # Paso 4: Migrar datos
                            if backup_data:
                                for row in backup_data:
                                    # Crear diccionario de datos del registro viejo
                                    row_dict = dict(zip(old_columns, row))
                                    
                                    # Mapear a nuevas columnas con valores por defecto
                                    new_row = {
                                        'id': row_dict.get('id'),
                                        'machinery_id': row_dict.get('machinery_id'),
                                        'maintenance_type_id': row_dict.get('maintenance_type_id'),
                                        'start_date': row_dict.get('start_date') or row_dict.get('created_at') or 'datetime("now")',
                                        'end_date': row_dict.get('end_date') or row_dict.get('created_at') or 'datetime("now")',
                                        'performed_by': row_dict.get('performed_by') or 'admin',
                                        'odometer_start': row_dict.get('odometer_start') or 0,
                                        'odometer_end': row_dict.get('odometer_end') or 0,
                                        'hour_meter_start': row_dict.get('hour_meter_start') or 0,
                                        'hour_meter_end': row_dict.get('hour_meter_end') or 0,
                                        'cost': row_dict.get('cost'),
                                        'description': row_dict.get('description'),
                                        'parts_used': row_dict.get('parts_used'),
                                        'notes': row_dict.get('notes'),
                                        'created_at': row_dict.get('created_at') or 'datetime("now")'
                                    }
                                    
                                    # Insertar registro migrado
                                    placeholders = ', '.join(['?' for _ in new_row])
                                    columns = ', '.join(new_row.keys())
                                    values = list(new_row.values())
                                    
                                    cur.execute(f"INSERT INTO maintenance_records ({columns}) VALUES ({placeholders})", values)
                            
                            # Paso 5: Eliminar tabla de respaldo
                            cur.execute("DROP TABLE maintenance_records_backup")
                            
                            conn.commit()
                            st.success("🎉 Tabla recreada y datos migrados exitosamente!")
                            
                        except Exception as e:
                            st.error(f"Error recreando tabla: {e}")
                            # Intentar restaurar si algo salió mal
                            try:
                                cur.execute("DROP TABLE IF EXISTS maintenance_records")
                                cur.execute("ALTER TABLE maintenance_records_backup RENAME TO maintenance_records")
                                conn.commit()
                                st.info("Tabla original restaurada")
                            except:
                                st.error("No se pudo restaurar automáticamente. Revisa la base de datos.")
                else:
                    st.success("✅ Tabla maintenance_records tiene todas las columnas críticas")
                    
                    # Mostrar muestra de datos
                    if record_count > 0:
                        st.write("**Muestra de datos:**")
                        try:
                            cur.execute("""
                                SELECT m.name, mt.name, 
                                       COALESCE(mr.created_at, mr.start_date, 'Sin fecha') as fecha,
                                       COALESCE(mr.hour_meter_end, 0) as horas,
                                       COALESCE(mr.odometer_end, 0) as km
                                FROM maintenance_records mr
                                LEFT JOIN machinery m ON mr.machinery_id = m.id
                                LEFT JOIN maintenance_types mt ON mr.maintenance_type_id = mt.id
                                ORDER BY mr.id DESC
                                LIMIT 3
                            """)
                            records = cur.fetchall()
                            
                            for machine, maint_type, date, hours, km in records:
                                st.write(f"- {machine or 'N/A'}: {maint_type or 'N/A'} ({date}) - {hours}h, {km}km")
                        except Exception as e:
                            st.write(f"Error mostrando datos: {e}")
            
            else:
                st.error("La tabla maintenance_records no existe")
                if st.button("🔨 Crear Tabla maintenance_records Desde Cero"):
                    try:
                        cur.execute("""
                            CREATE TABLE maintenance_records (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                machinery_id INTEGER,
                                maintenance_type_id INTEGER,
                                start_date TEXT,
                                end_date TEXT,
                                performed_by TEXT DEFAULT 'admin',
                                odometer_start REAL DEFAULT 0,
                                odometer_end REAL DEFAULT 0,
                                hour_meter_start REAL DEFAULT 0,
                                hour_meter_end REAL DEFAULT 0,
                                cost REAL,
                                description TEXT,
                                parts_used TEXT,
                                notes TEXT,
                                created_at TEXT,
                                FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
                                FOREIGN KEY (maintenance_type_id) REFERENCES maintenance_types(id)
                            )
                        """)
                        
                        conn.commit()
                        st.success("✅ Tabla maintenance_records creada desde cero")
                        
                    except Exception as e:
                        st.error(f"Error creando tabla: {e}")
                        
    except Exception as e:
        st.error(f"Error en diagnóstico de maintenance_records: {e}")

def mostrar_diagnostico_sqlite_compatible():
    """Diagnóstico compatible con las limitaciones de SQLite"""
    st.subheader("Diagnóstico de Base de Datos - Compatible SQLite")
    
    st.info("""
    **Nota:** SQLite tiene limitaciones con ALTER TABLE. Si algo no funciona con el método seguro, 
    usa la opción de recrear tabla que migrará todos los datos automáticamente.
    """)
    
    tab1, tab2, tab3 = st.tabs(["maintenance_types", "maintenance_intervals", "maintenance_records"])
    
    with tab1:
        debug_and_fix_maintenance_types_table()
    
    with tab2:
        debug_and_fix_maintenance_intervals_table()
    
    with tab3:
        debug_and_fix_maintenance_records_table_v3()

# OPCIONAL: En maintenance_module.py 
# Agregar esta función para mostrar estados de manera consistente

def mostrar_estado_con_compatibilidad(machine_data):
    """
    Muestra el estado de una máquina de manera consistente
    """
    try:
        from db_utils import normalize_machinery_status, get_localized_status_display
        
        current_status = machine_data.get('status', 'Activa')
        normalized = normalize_machinery_status(current_status)
        display_status = get_localized_status_display(normalized, locale='es')
        
        # Mostrar tanto el estado actual como el normalizado si son diferentes
        if current_status != display_status:
            return f"{display_status} ({current_status})"
        else:
            return display_status
            
    except ImportError:
        # Fallback si no hay funciones de compatibilidad
        return machine_data.get('status', 'Activa')

# También puedes actualizar la función safe_get_machinery_data para usar estados normalizados
def safe_get_machinery_data_compatible(empresa_id):
    """
    Versión compatible que normaliza estados
    """
    try:
        from db_utils import get_machinery_with_normalized_status
        
        df = get_machinery_with_normalized_status(empresa_id)
        
        if not df.empty:
            # Agregar columna de estado para mostrar (en español)
            df['status_display'] = df['normalized_status'].apply(
                lambda x: get_localized_status_display(x, locale='es')
            )
        
        return df
        
    except ImportError:
        # Usar la función original como fallback
        return safe_get_machinery_data(empresa_id)

def manejar_acciones_mantenimiento_programado(empresa_id):
    """Maneja las acciones pendientes (Realizado, No Realizado, Reprogramar)"""
    # Buscar acciones pendientes en session_state
    for key in list(st.session_state.keys()):
        if key.startswith(('mark_done_', 'mark_skip_', 'reschedule_')):
            parts = key.split('_')
            if len(parts) >= 3:
                action_type = parts[1]
                schedule_id_str = '_'.join(parts[2:])
                
                try:
                    schedule_id = int(schedule_id_str)
                    
                    if action_type == 'done':
                        mostrar_formulario_mantenimiento_realizado(schedule_id)
                    elif action_type == 'skip':
                        mostrar_formulario_no_realizado(schedule_id)
                    elif action_type == 'reschedule':
                        mostrar_formulario_reprogramar(schedule_id)
                except ValueError:
                    # Si no se puede convertir a int, limpiar la clave
                    if key in st.session_state:
                        del st.session_state[key]

def mostrar_formulario_mantenimiento_realizado(schedule_id):
    """Formulario para marcar mantenimiento como realizado"""
    st.subheader("Registrar Mantenimiento Realizado")
    
    try:
        with get_conn() as conn:
            # Obtener datos del mantenimiento programado
            schedule_data = conn.execute("""
                SELECT ms.*, m.name as vehiculo, mt.name as tipo_mantenimiento
                FROM maintenance_schedules ms
                JOIN machinery m ON ms.machinery_id = m.id
                JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
                WHERE ms.id = ?
            """, (schedule_id,)).fetchone()
            
            if schedule_data:
                st.info(f"Mantenimiento: {schedule_data[11]} - {schedule_data[12]}")
                
                with st.form(f"form_realizado_{schedule_id}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fecha_realizacion = st.date_input(
                            "Fecha de Realización",
                            value=date.today(),
                            key=f"fecha_real_{schedule_id}"
                        )
                        
                        costo = st.number_input(
                            "Costo ($)",
                            min_value=0.0,
                            step=10.0,
                            format="%.2f",
                            key=f"costo_{schedule_id}"
                        )
                    
                    with col2:
                        duracion_real = st.number_input(
                            "Duración Real (horas)",
                            min_value=0.1,
                            value=float(schedule_data[6] or 8.0),
                            step=0.5,
                            key=f"duracion_{schedule_id}"
                        )
                        
                        realizado_por = st.text_input(
                            "Realizado por",
                            value=schedule_data[9] or st.session_state.get("username", "admin"),
                            key=f"realizado_por_{schedule_id}"
                        )
                    
                    descripcion = st.text_area(
                        "Descripción del Trabajo Realizado",
                        key=f"desc_realizado_{schedule_id}"
                    )
                    
                    repuestos = st.text_area(
                        "Repuestos/Materiales Utilizados",
                        key=f"repuestos_{schedule_id}"
                    )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.form_submit_button("Confirmar Realizado", type="primary"):
                            from db_utils import log_maintenance_compliance, update_scheduled_maintenance_status
                            
                            # Registrar mantenimiento en maintenance_records
                            conn.execute("""
                                INSERT INTO maintenance_records
                                (machinery_id, maintenance_type_id, start_date, end_date, performed_by,
                                 cost, description, parts_used, notes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (schedule_data[1], schedule_data[2], fecha_realizacion.isoformat(),
                                  fecha_realizacion.isoformat(), realizado_por, costo,
                                  descripcion, repuestos, f"Mantenimiento programado completado"))
                            
                            # Log compliance
                            log_maintenance_compliance(
                                schedule_id, 'COMPLETED', 
                                f"Mantenimiento realizado el {fecha_realizacion}",
                                descripcion, realizado_por
                            )
                            
                            # Actualizar estado
                            update_scheduled_maintenance_status(schedule_id, 'COMPLETADO')
                            
                            conn.commit()
                            
                            # Limpiar session_state
                            if f'mark_done_{schedule_id}' in st.session_state:
                                del st.session_state[f'mark_done_{schedule_id}']
                            st.success("Mantenimiento registrado exitosamente")
                            st.rerun()
                    
                    with col_btn2:
                        if st.form_submit_button("Cancelar"):
                            if f'mark_done_{schedule_id}' in st.session_state:
                                del st.session_state[f'mark_done_{schedule_id}']
                            st.rerun()
                            
    except Exception as e:
        st.error(f"Error en formulario: {e}")

def mostrar_formulario_no_realizado(schedule_id):
    """Formulario para marcar mantenimiento como no realizado"""
    st.subheader("Registrar Mantenimiento No Realizado")
    
    try:
        with get_conn() as conn:
            schedule_data = conn.execute("""
                SELECT ms.*, m.name as vehiculo, mt.name as tipo_mantenimiento
                FROM maintenance_schedules ms
                JOIN machinery m ON ms.machinery_id = m.id
                JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
                WHERE ms.id = ?
            """, (schedule_id,)).fetchone()
            
            if schedule_data:
                st.warning(f"Mantenimiento: {schedule_data[11]} - {schedule_data[12]}")
                
                with st.form(f"form_no_realizado_{schedule_id}"):
                    motivos_predefinidos = [
                        "Falta de repuestos",
                        "Vehículo no disponible", 
                        "Técnico no disponible",
                        "Condiciones climáticas",
                        "Prioridades operativas",
                        "Problemas de presupuesto",
                        "Otro"
                    ]
                    
                    motivo = st.selectbox(
                        "Motivo de No Realización",
                        motivos_predefinidos,
                        key=f"motivo_{schedule_id}"
                    )
                    
                    notas = st.text_area(
                        "Notas Adicionales",
                        placeholder="Explicación detallada del motivo...",
                        key=f"notas_skip_{schedule_id}"
                    )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.form_submit_button("Confirmar No Realizado", type="primary"):
                            from db_utils import log_maintenance_compliance, update_scheduled_maintenance_status
                            
                            # Log compliance
                            log_maintenance_compliance(
                                schedule_id, 'SKIPPED', 
                                motivo, notas, 
                                st.session_state.get("username", "admin")
                            )
                            
                            # Actualizar estado
                            update_scheduled_maintenance_status(schedule_id, 'NO_REALIZADO')
                            
                            conn.commit()
                            
                            # Limpiar session_state
                            if f'mark_skip_{schedule_id}' in st.session_state:
                                del st.session_state[f'mark_skip_{schedule_id}']
                            st.success("Registro de no realización guardado")
                            st.rerun()
                    
                    with col_btn2:
                        if st.form_submit_button("Cancelar"):
                            if f'mark_skip_{schedule_id}' in st.session_state:
                                del st.session_state[f'mark_skip_{schedule_id}']
                            st.rerun()
                            
    except Exception as e:
        st.error(f"Error en formulario: {e}")

def mostrar_formulario_reprogramar(schedule_id):
    """Formulario para reprogramar mantenimiento"""
    st.subheader("Reprogramar Mantenimiento")
    
    try:
        with get_conn() as conn:
            schedule_data = conn.execute("""
                SELECT ms.*, m.name as vehiculo, mt.name as tipo_mantenimiento
                FROM maintenance_schedules ms
                JOIN machinery m ON ms.machinery_id = m.id
                JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
                WHERE ms.id = ?
            """, (schedule_id,)).fetchone()
            
            if schedule_data:
                st.info(f"Mantenimiento: {schedule_data[11]} - {schedule_data[12]}")
                st.write(f"Fecha original: {schedule_data[3]}")
                
                with st.form(f"form_reprogramar_{schedule_id}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        nueva_fecha_inicio = st.date_input(
                            "Nueva Fecha de Inicio",
                            value=date.today() + timedelta(days=7),
                            min_value=date.today(),
                            key=f"nueva_fecha_{schedule_id}"
                        )
                        
                        nueva_fecha_fin = st.date_input(
                            "Nueva Fecha de Fin",
                            value=nueva_fecha_inicio + timedelta(days=1),
                            min_value=nueva_fecha_inicio,
                            key=f"nueva_fecha_fin_{schedule_id}"
                        )
                    
                    with col2:
                        nuevo_responsable = st.text_input(
                            "Responsable",
                            value=schedule_data[9] or "",
                            key=f"nuevo_resp_{schedule_id}"
                        )
                        
                        nueva_prioridad = st.selectbox(
                            "Prioridad",
                            ["NORMAL", "ALTA", "CRÍTICA"],
                            index=["NORMAL", "ALTA", "CRÍTICA"].index(schedule_data[8]) if schedule_data[8] in ["NORMAL", "ALTA", "CRÍTICA"] else 0,
                            key=f"nueva_prio_{schedule_id}"
                        )
                    
                    motivo_reprogramacion = st.text_area(
                        "Motivo de la Reprogramación",
                        placeholder="Explicar por qué se reprograma...",
                        key=f"motivo_reprog_{schedule_id}"
                    )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        if st.form_submit_button("Confirmar Reprogramación", type="primary"):
                            from db_utils import log_maintenance_compliance
                            
                            # Actualizar mantenimiento programado
                            conn.execute("""
                                UPDATE maintenance_schedules 
                                SET scheduled_start_date = ?, scheduled_end_date = ?, 
                                    responsible_person = ?, priority = ?
                                WHERE id = ?
                            """, (nueva_fecha_inicio.isoformat(), nueva_fecha_fin.isoformat(),
                                  nuevo_responsable, nueva_prioridad, schedule_id))
                            
                            # Log compliance
                            log_maintenance_compliance(
                                schedule_id, 'POSTPONED',
                                f"Reprogramado para {nueva_fecha_inicio}",
                                motivo_reprogramacion,
                                st.session_state.get("username", "admin")
                            )
                            
                            conn.commit()
                            
                            # Limpiar session_state
                            if f'reschedule_{schedule_id}' in st.session_state:
                                del st.session_state[f'reschedule_{schedule_id}']
                            st.success("Mantenimiento reprogramado exitosamente")
                            st.rerun()
                    
                    with col_btn2:
                        if st.form_submit_button("Cancelar"):
                            if f'reschedule_{schedule_id}' in st.session_state:
                                del st.session_state[f'reschedule_{schedule_id}']
                            st.rerun()
                            
    except Exception as e:
        st.error(f"Error en formulario: {e}")

def mostrar_compliance_log(empresa_id):
    """Muestra el log de cumplimiento de mantenimientos"""
    try:
        from db_utils import get_compliance_log
        
        # Filtros para el log
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            fecha_inicio_log = st.date_input(
                "Fecha Inicio",
                value=date.today() - timedelta(days=30),
                key="fecha_inicio_compliance"
            )
        
        with col_f2:
            fecha_fin_log = st.date_input(
                "Fecha Fin",
                value=date.today(),
                key="fecha_fin_compliance"
            )
        
        # Obtener log
        compliance_df = get_compliance_log(empresa_id, fecha_inicio_log, fecha_fin_log)
        
        if not compliance_df.empty:
            # Métricas de cumplimiento
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            
            total_acciones = len(compliance_df)
            completados = len(compliance_df[compliance_df['accion'] == 'COMPLETED'])
            no_realizados = len(compliance_df[compliance_df['accion'] == 'SKIPPED'])
            reprogramados = len(compliance_df[compliance_df['accion'] == 'POSTPONED'])
            
            with col_m1:
                st.metric("Total Acciones", total_acciones)
            
            with col_m2:
                porcentaje_cumplimiento = (completados / total_acciones * 100) if total_acciones > 0 else 0
                st.metric("Completados", completados, f"{porcentaje_cumplimiento:.1f}%")
            
            with col_m3:
                st.metric("No Realizados", no_realizados)
            
            with col_m4:
                st.metric("Reprogramados", reprogramados)
            
            # Mostrar tabla del log
            st.dataframe(compliance_df, use_container_width=True)
            
            # Gráfico de distribución de acciones
            if total_acciones > 0:
                acciones_counts = compliance_df['accion'].value_counts()
                
                fig = px.pie(
                    values=acciones_counts.values, 
                    names=acciones_counts.index,
                    title='Distribución de Acciones de Mantenimiento',
                    color_discrete_map={
                        'COMPLETED': '#4CAF50',
                        'SKIPPED': '#f44336', 
                        'POSTPONED': '#ff9800'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Botón de descarga
            import io
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                compliance_df.to_excel(writer, sheet_name='Log_Cumplimiento', index=False)
            
            st.download_button(
                label="Descargar Log en Excel",
                data=output.getvalue(),
                file_name=f"compliance_log_{fecha_inicio_log}_{fecha_fin_log}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        else:
            st.info("No hay registros de cumplimiento en el período seleccionado.")
            
    except Exception as e:
        st.error(f"Error mostrando log de cumplimiento: {e}")

def formatear_hoja_excel_segura(writer, nombre_hoja, df, titulo_original):
    """Versión segura que maneja todos los errores posibles en el formato"""
    try:
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        
        workbook = writer.book
        worksheet = writer.sheets[nombre_hoja]
        
        # 1. Aplicar título sin usar merge_cells (más seguro)
        titulo_cell = worksheet.cell(row=1, column=1)
        titulo_cell.value = titulo_original
        titulo_cell.font = Font(bold=True, size=14)
        titulo_cell.alignment = Alignment(horizontal='center')
        
        # 2. Formatear encabezados fila 3 (después del título)
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        border = Border(
            bottom=Side(style='medium', color='000000'),
            top=Side(style='medium', color='000000')
        )
        
        for i, columna in enumerate(df.columns, 1):
            celda = worksheet.cell(row=3, column=i)
            celda.fill = header_fill
            celda.font = header_font
            celda.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            celda.border = border
        
        # 3. Ajustar ancho de columnas de forma segura
        for i, columna in enumerate(df.columns, 1):
            try:
                # Obtener la letra de columna desde una celda normal
                celda = worksheet.cell(row=3, column=i)
                columna_letra = celda.column_letter
                
                # Calcular ancho máximo
                valores = df.iloc[:, i-1].astype(str)
                max_len = max([len(str(s)) for s in valores.values] + [len(str(columna))])
                
                # Ajustar ancho con un límite
                worksheet.column_dimensions[columna_letra].width = min(max_len + 3, 40)
            except Exception as col_err:
                # Si hay error, usar un ancho fijo
                try:
                    worksheet.column_dimensions[get_column_letter(i)].width = 15
                except:
                    # Ignorar si todo falla
                    pass
        
        # 4. Aplicar formato a todas las celdas
        data_font = Font(name='Arial', size=10)
        alt_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
        
        # Formato de filas alternas
        for row_idx, row in enumerate(worksheet.iter_rows(min_row=4, max_row=worksheet.max_row), 1):
            for cell in row:
                # Fuente estándar
                cell.font = data_font
                
                # Alineación según tipo de dato
                try:
                    cell_value = cell.value
                    if isinstance(cell_value, (int, float)) or (isinstance(cell_value, str) and cell_value.replace('.', '', 1).isdigit()):
                        cell.alignment = Alignment(horizontal='right')
                    else:
                        cell.alignment = Alignment(horizontal='left')
                except:
                    cell.alignment = Alignment(horizontal='left')
                
                # Filas alternas con color
                if row_idx % 2 == 0:
                    cell.fill = alt_fill
                    
    except Exception as e:
        # Error silencioso para no interrumpir la generación
        print(f"Error en formateo avanzado: {e}")


def aplicar_formato_basico(writer, nombre_hoja, df):
    """Formato mínimo para asegurar que el Excel sea útil"""
    try:
        from openpyxl.styles import Font
        
        worksheet = writer.sheets[nombre_hoja]
        
        # Aplicar solo título y encabezados en negrita
        worksheet.cell(row=1, column=1).value = nombre_hoja
        worksheet.cell(row=1, column=1).font = Font(bold=True, size=14)
        
        # Encabezados en negrita
        for i, _ in enumerate(df.columns, 1):
            worksheet.cell(row=3, column=i).font = Font(bold=True)
            
    except Exception:
        # Ignorar cualquier error para asegurar la generación del Excel
        pass


def crear_hoja_resumen_corregida(writer, titulo, fecha_inicio, fecha_fin, dataframes_dict):
    """Crea hoja de resumen del reporte - CORREGIDA para evitar errores"""
    try:
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        
        # Datos básicos para el resumen
        resumen_data = {
            'Información': ['Título', 'Período', 'Fecha Generación', 'Total Registros'],
            'Valor': [
                titulo,
                f"{fecha_inicio} al {fecha_fin}",
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                sum(len(df) for df in dataframes_dict.values() if not df.empty)
            ]
        }
        
        # Crear DataFrame y escribir a Excel
        resumen_df = pd.DataFrame(resumen_data)
        resumen_df.to_excel(writer, sheet_name='Resumen', index=False)
        
        # Aplicar formato
        worksheet = writer.sheets['Resumen']
        
        # Título
        worksheet.merge_cells('A1:B1')  # Combinar celdas para título
        titulo_cell = worksheet.cell(row=1, column=1)
        titulo_cell.value = "RESUMEN DE REPORTE"
        titulo_cell.font = Font(bold=True, size=16)
        titulo_cell.alignment = Alignment(horizontal='center')
        
        # Estilo encabezado
        for i in range(1, 3):
            header_cell = worksheet.cell(row=2, column=i)
            header_cell.font = Font(bold=True, color="FFFFFF")
            header_cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_cell.alignment = Alignment(horizontal='center')
            header_cell.border = Border(
                bottom=Side(style='medium'),
                top=Side(style='medium')
            )
        
        # Estilo datos
        for i in range(3, 7):
            for j in range(1, 3):
                cell = worksheet.cell(row=i, column=j)
                if j == 1:  # Primera columna en negrita
                    cell.font = Font(bold=True)
                
                # Alterna colores de fondo
                if i % 2 == 0:
                    cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
                
                # Bordes
                cell.border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    bottom=Side(style='thin')
                )
        
        # Ajustar ancho de columnas
        worksheet.column_dimensions['A'].width = 20
        worksheet.column_dimensions['B'].width = 40
        
        # Agregar información de hojas
        row = 8
        worksheet.cell(row=row, column=1).value = "Contenido del Reporte:"
        worksheet.cell(row=row, column=1).font = Font(bold=True, size=12)
        
        row += 2
        for idx, (nombre, df) in enumerate(dataframes_dict.items(), 1):
            if not df.empty:
                worksheet.cell(row=row, column=1).value = f"{idx}. {nombre}"
                worksheet.cell(row=row, column=2).value = f"{len(df)} registros"
                row += 1
        
    except Exception as e:
        # Si hay error, crear una versión mínima
        try:
            resumen_df = pd.DataFrame({
                'Información': ['Título', 'Período', 'Registros'],
                'Valor': [titulo, f"{fecha_inicio} a {fecha_fin}", sum(len(df) for df in dataframes_dict.values())]
            })
            resumen_df.to_excel(writer, sheet_name='Resumen', index=False)
        except:
            # Si todo falla, al menos asegurar que el Excel se genere
            pass

def get_column_letter(col_idx):
    """Convierte un índice de columna a letra (ej: 1 -> A, 27 -> AA)"""
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result