def safe_execute_with_retry(operation, max_retries=3, base_delay=0.1):
    """
    Ejecuta una operación de base de datos con reintentos y manejo de bloqueos
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            with _connection_lock:
                return operation()
        except sqlite3.OperationalError as e:
            last_error = e
            if "database is locked" in str(e) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Backoff exponencial
                print(f"Database locked, reintentando en {delay}s (intento {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            else:
                raise e
        except Exception as e:
            raise e
    raise last_error
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import time
import threading

import numpy as np

try:
    from github_backup_utils import (
        setup_github_auto_backup, 
        github_manual_backup, 
        get_github_backups, 
        restore_from_github,
        test_github_connection,
        stop_auto_backup
    )
    GITHUB_BACKUP_AVAILABLE = True
    print("✅ GitHub backup integration disponible")
except ImportError as e:
    GITHUB_BACKUP_AVAILABLE = False
    print(f"⚠️ GitHub backup no disponible: {str(e)}")

# Variable global para controlar el sistema de backup
BACKUP_INITIALIZED = False

def convert_numpy_types(obj):
    """Convierte tipos numpy a tipos Python nativos para JSON"""
    if isinstance(obj, np.int64):
        return int(obj)
    elif isinstance(obj, np.int32):
        return int(obj)
    elif isinstance(obj, np.float64):
        return float(obj)
    elif isinstance(obj, np.float32):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj

DB_PATH = "gestion_empresas.db"
_connection_lock = threading.RLock()
_wal_initialized = False

def enable_wal_mode():
    """Habilita el modo Write-Ahead Logging para mejor concurrencia"""
    try:
        with get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.commit()
            print("WAL mode enabled successfully")
            return True
    except Exception as e:
        print(f"Error enabling WAL mode: {e}")
        return False
"db_utils"
def migrate_database():
    """Función para migrar esquema de base de datos existente"""
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            # Verificar si existe la columna config_value en alert_configurations
            cur.execute("PRAGMA table_info(alert_configurations)")
            columns = [col[1] for col in cur.fetchall()]
            if 'config_value' not in columns:
                cur.execute("ALTER TABLE alert_configurations ADD COLUMN config_value TEXT NOT NULL DEFAULT ''")
            # Verificar si existe la columna duration_in_previous_status en status_history
            cur.execute("PRAGMA table_info(status_history)")
            columns = [col[1] for col in cur.fetchall()]
            if 'duration_in_previous_status' not in columns:
                cur.execute("ALTER TABLE status_history ADD COLUMN duration_in_previous_status INTEGER;")
            conn.commit()
            st.success("Esquema de base de datos actualizado correctamente")
        except sqlite3.OperationalError as e:
            # Si la tabla no existe, se creará más tarde
            pass

# En db_utils.py

def migrate_maintenance_tables():
    """
    Verifica y añade las columnas faltantes para el módulo de mantenimiento.
    Esta función es segura para ejecutarse múltiples veces.
    """
    print("INFO: Verificando y migrando tablas de mantenimiento...")
    try:
        with get_conn() as conn:
            cur = conn.cursor()

            # 1. Verificar la tabla 'maintenance_records'
            cur.execute("PRAGMA table_info(maintenance_records)")
            columns = [col[1] for col in cur.fetchall()]
            
            # Columnas que deberían existir en maintenance_records
            expected_columns_records = {
                "start_date": "TEXT",
                "end_date": "TEXT",
                "odometer_start": "REAL",
                "odometer_end": "REAL",
                "hour_meter_start": "REAL",
                "hour_meter_end": "REAL", # La columna del error
                "cost": "REAL",
                "description": "TEXT",
                "parts_used": "TEXT",
                "notes": "TEXT"
            }

            for col_name, col_type in expected_columns_records.items():
                if col_name not in columns:
                    print(f"    -> Migrando: Añadiendo columna '{col_name}' a 'maintenance_records'...")
                    cur.execute(f"ALTER TABLE maintenance_records ADD COLUMN {col_name} {col_type};")

            # 2. Verificar la tabla 'machinery' para columnas de mantenimiento
            cur.execute("PRAGMA table_info(machinery)")
            columns_machinery = [col[1] for col in cur.fetchall()]

            expected_columns_machinery = {
                "current_hours": "REAL DEFAULT 0.0",
                "current_km": "REAL DEFAULT 0.0", # Nota: El módulo usa 'current_km', no 'current_odometer'
                "last_status_change": "TEXT",
                "last_maintenance_date": "TEXT",
                "last_maintenance_hours": "REAL",
                "last_maintenance_km": "REAL"
            }

            for col_name, col_def in expected_columns_machinery.items():
                 if col_name not in columns_machinery:
                    print(f"    -> Migrando: Añadiendo columna '{col_name}' a 'machinery'...")
                    cur.execute(f"ALTER TABLE machinery ADD COLUMN {col_name} {col_def};")

            conn.commit()
            print("INFO: Migración de tablas de mantenimiento completada.")
            return True
    except Exception as e:
        print(f"ERROR: Falló la migración de tablas de mantenimiento: {e}")
        return False

"db_utils"
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st  # Asegúrate de tener este import si usas st.error y st.dataframe

DB_PATH = "gestion_empresas.db"

def get_conn():
    """Conexión optimizada sin reconfigurar WAL en cada llamada"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    # Solo configurar foreign_keys y timeout, WAL ya está configurado
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn

def ensure_indexes():
    """Crea índices para mejorar el rendimiento en tablas críticas si no existen"""
    with get_conn() as conn:
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_fluid_tanks_company_fluid 
            ON company_fluid_tanks(company_id, fluid_type_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tank_refill_logs_tank_id 
            ON tank_refill_logs(tank_id);
        """)
        conn.commit()

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    
    # Tabla de empresas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Tabla para logs de eliminación de empresas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS deletion_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            company_name TEXT,
            deleted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            deleted_by TEXT
        );
    """)
    
    # Tabla de maquinaria (actualizada con nuevos campos)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS machinery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT NOT NULL,
            model TEXT,
            serial_number TEXT UNIQUE,
            identifier TEXT,
            classification TEXT,
            consumption_rate REAL DEFAULT 0.0,
            purchase_date TEXT,
            last_maintenance TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies (id) ON DELETE CASCADE
        );
    """)
    
    # Actualizar tabla existente si faltan columnas
    try:
        cur.execute("ALTER TABLE machinery ADD COLUMN identifier TEXT;")
    except sqlite3.OperationalError:
        pass  # Columna ya existe
    
    try:
        cur.execute("ALTER TABLE machinery ADD COLUMN classification TEXT;")
    except sqlite3.OperationalError:
        pass
    
    try:
        cur.execute("ALTER TABLE machinery ADD COLUMN consumption_rate REAL DEFAULT 0.0;")
    except sqlite3.OperationalError:
        pass
    
    try:
        cur.execute("ALTER TABLE machinery ADD COLUMN last_maintenance TEXT;")
    except sqlite3.OperationalError:
        pass
    
    # Tabla para logs de eliminación de maquinaria
    cur.execute("""
        CREATE TABLE IF NOT EXISTS machinery_deletion_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machinery_id INTEGER,
            machinery_name TEXT,
            company_id INTEGER,
            deleted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            deleted_by TEXT
        );
    """)
    
    # Tabla para registros de combustible (actualizada)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fuel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machinery_id INTEGER,
            company_id INTEGER,
            fuel_added REAL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            added_by TEXT,
            FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );
    """)
    
    # Tabla para clasificaciones de máquinas (configurable)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS machine_classifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Insertar clasificaciones por defecto
    default_classifications = ["Maquinaria Pesada", "Camión", "Trituradora"]
    for classification in default_classifications:
        cur.execute("""
            INSERT OR IGNORE INTO machine_classifications (name) VALUES (?)
        """, (classification,))
    
    # Extensiones para controles
    new_columns = [
        ("consumption_per_hour", "REAL DEFAULT 0.0"),
        ("current_odometer", "REAL DEFAULT 0.0"),
        ("maintenance_interval_hours", "REAL"),
        ("maintenance_interval_km", "REAL"),
        ("last_odometer_update", "TEXT")
    ]
    
    for column_name, column_def in new_columns:
        try:
            cur.execute(f"ALTER TABLE machinery ADD COLUMN {column_name} {column_def};")
        except sqlite3.OperationalError:
            pass  # Columna ya existe
    
    # Migrar datos de consumption_rate a consumption_per_hour si es necesario
    cur.execute("""
        UPDATE machinery 
        SET consumption_per_hour = ROUND(COALESCE(consumption_rate, 0) / 24.0, 3)
        WHERE consumption_per_hour IS NULL OR consumption_per_hour = 0
    """)
    
    # Tabla para logs de horómetro
    cur.execute("""
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

    # Tabla para logs de odómetro
    cur.execute("""
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
    
    conn.commit()
    conn.close()
    ensure_indexes()
    def init_additional_tables():
        """
        Inicializa tablas adicionales necesarias para el sistema.
        Esta función complementa a init_db() con tablas específicas de módulos avanzados.
        """
        try:
            with get_conn() as conn:
                cur = conn.cursor()
                
                # Tabla para logs de horómetro (si no existe)
                cur.execute("""
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
                
                # Tabla para logs de odómetro (si no existe)
                cur.execute("""
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
                
                # Tabla para tipos de fluidos (si no existe)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS fluid_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        unit_type TEXT DEFAULT 'galones',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insertar tipos de fluidos por defecto si no existen
                default_fluids = [
                    ("Combustible", "Combustible para maquinaria", "galones"),
                    ("Aceite", "Aceite de motor", "litros"),
                    ("Grasa", "Grasa para componentes", "kg"),
                    ("Coolant", "Líquido refrigerante", "litros")
                ]
                
                for name, description, unit_type in default_fluids:
                    cur.execute("""
                        INSERT OR IGNORE INTO fluid_types (name, description, unit_type)
                        VALUES (?, ?, ?)
                    """, (name, description, unit_type))
                
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
                        FOREIGN KEY (fluid_type_id) REFERENCES fluid_types(id)
                    )
                """)
                
                # Tabla para movimientos de inventario de fluidos
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS fluid_inventory_movements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tank_id INTEGER,
                        machinery_id INTEGER,
                        movement_type TEXT CHECK(movement_type IN ('ENTRADA', 'SALIDA')),
                        quantity REAL NOT NULL,
                        supplier TEXT,
                        operator TEXT,
                        notes TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (tank_id) REFERENCES company_fluid_tanks(id) ON DELETE CASCADE,
                        FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE SET NULL
                    )
                """)
                
                # Tabla para logs de reabastecimiento de tanques
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tank_refill_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tank_id INTEGER,
                        amount_added REAL NOT NULL,
                        cost REAL,
                        supplier TEXT,
                        refilled_by TEXT,
                        notes TEXT,
                        refilled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (tank_id) REFERENCES company_fluid_tanks(id) ON DELETE CASCADE
                    )
                """)
                
                # Tabla para configuración de la empresa
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS company_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER,
                        setting_key TEXT NOT NULL,
                        setting_value TEXT,
                        UNIQUE(company_id, setting_key),
                        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
                    )
                """)
                
                # Tabla para información adicional de empresas
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS company_info (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER UNIQUE,
                        name TEXT,
                        owner TEXT,
                        creation_date TEXT,
                        phone TEXT,
                        email TEXT,
                        address TEXT,
                        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
                    )
                """)
                
                conn.commit()
                print("✅ Tablas adicionales inicializadas correctamente")
                return True
                
        except Exception as e:
            print(f"❌ Error al inicializar tablas adicionales: {e}")
            return False

def list_companies():
    init_db()
    with get_conn() as conn:
        return pd.read_sql_query("SELECT id, name, created_at FROM companies ORDER BY name", conn)

def add_company(name: str):
    if not name.strip():
        return False
    with get_conn() as conn:
        conn.execute("INSERT INTO companies(name) VALUES (?)", (name.strip(),))
    return True

def delete_company(company_id: int, deleted_by: str = "admin"):
    with get_conn() as conn:
        # Obtener nombre de la empresa antes de eliminarla
        company_name = pd.read_sql_query("SELECT name FROM companies WHERE id = ?", conn, params=(company_id,)).iloc[0]['name']
        
        # Eliminar la empresa
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        
        # Registrar en log de eliminación
        conn.execute(
            "INSERT INTO deletion_logs (company_id, company_name, deleted_by) VALUES (?, ?, ?)",
            (company_id, company_name, deleted_by)
        )

# Funciones para maquinaria (actualizadas)
def add_machinery(company_id, name, model, serial_number, identifier, classification, consumption_rate, purchase_date, status="Active"):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO machinery (
                company_id, name, model, serial_number, identifier, 
                classification, consumption_rate, purchase_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (company_id, name, model, serial_number, identifier, classification, consumption_rate, purchase_date, status))
    return True

def add_machinery_extended(empresa_id, name, model, serial_number, identifier, classification, 
                         consumption_per_hour, purchase_date, status, current_hours=0, current_odometer=0):
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

def list_machinery(company_id):
    init_db()
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT * FROM machinery WHERE company_id = ? ORDER BY name", 
            conn, 
            params=(company_id,)
        )

def update_machinery(machinery_id, **kwargs):
    """Actualiza campos específicos de una maquinaria"""
    with get_conn() as conn:
        # Construir query dinámico
        fields = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if fields:
            values.append(machinery_id)
            query = f"UPDATE machinery SET {', '.join(fields)} WHERE id = ?"
            conn.execute(query, values)
    return True

def update_machinery_extended(machinery_id, **kwargs):
    """Actualiza campos extendidos de una maquinaria incluyendo campos de controles"""
    with get_conn() as conn:
        # Construir query dinámico
        fields = []
        values = []
        
        # Mapear campos legacy a nuevos campos
        if 'consumption_rate' in kwargs and 'consumption_per_hour' not in kwargs:
            kwargs['consumption_per_hour'] = kwargs.pop('consumption_rate')
        
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if fields:
            values.append(machinery_id)
            query = f"UPDATE machinery SET {', '.join(fields)} WHERE id = ?"
            conn.execute(query, values)
            conn.commit()
    return True

def delete_machinery(machinery_id, deleted_by="admin"):
    """
    Elimina una maquinaria y todos sus registros relacionados en cascada
    """
    try:
        with get_conn() as conn:
            # Obtener información de la maquinaria antes de eliminarla
            machinery_info = pd.read_sql_query(
                "SELECT id, name, company_id FROM machinery WHERE id = ?", 
                conn, 
                params=(machinery_id,)
            )

            if machinery_info.empty:
                return False

            machinery_info = machinery_info.iloc[0]
            
            # Eliminar registros de combustible (ON DELETE CASCADE debería hacerlo automáticamente)
            conn.execute("DELETE FROM fuel_logs WHERE machinery_id = ?", (machinery_id,))
            
            # Eliminar la maquinaria
            conn.execute("DELETE FROM machinery WHERE id = ?", (machinery_id,))
            
            # Registrar en log de eliminación
            conn.execute(
                "INSERT INTO machinery_deletion_logs (machinery_id, machinery_name, company_id, deleted_by) VALUES (?, ?, ?, ?)",
                (machinery_id, machinery_info['name'], machinery_info['company_id'], deleted_by)
            )

        return True
    except Exception as e:
        print(f"Error al eliminar maquinaria {machinery_id}: {e}")
        raise e

# Funciones para gestión de combustible (actualizadas)
def add_fuel_log(machinery_id, company_id, fuel_added, added_by="admin", added_at=None):
    with get_conn() as conn:
        if added_at:
            conn.execute("""
                INSERT INTO fuel_logs (machinery_id, company_id, fuel_added, added_by, added_at)
                VALUES (?, ?, ?, ?, ?)
            """, (machinery_id, company_id, fuel_added, added_by, added_at))
        else:
            conn.execute("""
                INSERT INTO fuel_logs (machinery_id, company_id, fuel_added, added_by)
                VALUES (?, ?, ?, ?)
            """, (machinery_id, company_id, fuel_added, added_by))
    
    return "Combustible registrado correctamente"

def get_fuel_logs(machinery_id):
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT id, fuel_added, added_at, added_by
            FROM fuel_logs
            WHERE machinery_id = ?
            ORDER BY added_at DESC
        """, conn, params=(machinery_id,))

def get_fuel_status_advanced(machinery_id):
    """
    Calcula el estado del combustible basado en:
    - Total de combustible agregado
    - Consumo promedio de la máquina
    - Fechas de recarga
    """
    with get_conn() as conn:
        # Obtener información de la máquina
        machine_info = pd.read_sql_query("""
            SELECT consumption_rate, name FROM machinery WHERE id = ?
        """, conn, params=(machinery_id,))
        
        if machine_info.empty:
            return {"status": "error", "message": "Máquina no encontrada"}
        
        consumption_rate = machine_info.iloc[0]['consumption_rate']
        machine_name = machine_info.iloc[0]['name']
        
        if not consumption_rate or consumption_rate <= 0:
            return {"status": "warning", "message": "Consumo promedio no definido"}
        
        # Obtener todos los registros de combustible
        fuel_logs = pd.read_sql_query("""
            SELECT fuel_added, added_at 
            FROM fuel_logs 
            WHERE machinery_id = ? 
            ORDER BY added_at ASC
        """, conn, params=(machinery_id,))
        
        if fuel_logs.empty:
            return {"status": "info", "message": "No hay registros de combustible"}
        
        # Calcular combustible total agregado
        total_fuel_added = fuel_logs['fuel_added'].sum()
        
        # Calcular días desde el primer registro
        first_date = pd.to_datetime(fuel_logs.iloc[0]['added_at'])
        current_date = pd.Timestamp.now()
        days_elapsed = (current_date - first_date).days
        
        # Calcular combustible consumido
        fuel_consumed = consumption_rate * days_elapsed
        
        # Calcular combustible restante
        remaining_fuel = max(0, total_fuel_added - fuel_consumed)
        
        # Calcular días restantes
        days_remaining = remaining_fuel / consumption_rate if consumption_rate > 0 else 0
        
        # Última recarga
        last_refuel = fuel_logs.iloc[-1]
        last_refuel_date = pd.to_datetime(last_refuel['added_at'])
        last_refuel_amount = last_refuel['fuel_added']
        
        result = {
            "machine_name": machine_name,
            "total_added": total_fuel_added,
            "consumed": fuel_consumed,
            "remaining": remaining_fuel,
            "days_remaining": days_remaining,
            "consumption_rate": consumption_rate,
            "last_refuel_date": last_refuel_date,
            "last_refuel_amount": last_refuel_amount,
            "days_elapsed": days_elapsed
        }
        
        # Determinar estado
        if remaining_fuel <= 0:
            result["status"] = "critical"
            result["message"] = f"COMBUSTIBLE AGOTADO - {machine_name}"
        elif days_remaining <= 2:
            result["status"] = "critical"
            result["message"] = f"CRÍTICO: {days_remaining:.1f} días restantes - {machine_name}"
        elif days_remaining <= 5:
            result["status"] = "warning"
            result["message"] = f"BAJO: {days_remaining:.1f} días restantes - {machine_name}"
        else:
            result["status"] = "ok"
            result["message"] = f"Normal: {days_remaining:.1f} días restantes - {machine_name}"
        
        return result

def get_fuel_status_extended(machinery_id):
    """Versión extendida que incluye estado de controles si está disponible"""
    try:
        # Intentar usar el nuevo sistema de controles
        from controles_module import get_machine_fluid_status, get_company_setting
        
        with get_conn() as conn:
            # Obtener empresa de la máquina
            empresa_query = pd.read_sql_query("""
                SELECT company_id FROM machinery WHERE id = ?
            """, conn, params=(machinery_id,))
            
            if not empresa_query.empty:
                empresa_id = empresa_query.iloc[0]['company_id']
                unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
                
                # ID 1 debería ser combustible por defecto
                status = get_machine_fluid_status(machinery_id, 1, unit_preference)
                
                # Convertir formato para compatibilidad
                legacy_status = status.get('level', 'unknown')
                if legacy_status == 'critico':
                    legacy_status = 'critical'
                elif legacy_status in ['malo', 'regular']:
                    legacy_status = 'warning'
                elif legacy_status in ['ok', 'excelente']:
                    legacy_status = 'ok'
                
                return {
                    'status': legacy_status,
                    'remaining': status.get('remaining', 0),
                    'days_remaining': status.get('hours_remaining', 0) / 24,  # Convertir horas a días
                    'total_added': status.get('total_added', 0),
                    'consumed': status.get('consumed', 0),
                    'message': status.get('message', '')
                }
    except:
        pass
    
    # Fallback al sistema original
    return get_fuel_status_advanced(machinery_id)

# Funciones para clasificaciones
def get_machine_classifications():
    with get_conn() as conn:
        return pd.read_sql_query("SELECT name FROM machine_classifications ORDER BY name", conn)['name'].tolist()

def add_machine_classification(name):
    with get_conn() as conn:
        try:
            conn.execute("INSERT INTO machine_classifications (name) VALUES (?)", (name,))
            return True
        except sqlite3.IntegrityError:
            return False  # Ya existe

# Funciones para reportes mejorados
def get_machinery_report(company_id):
    """Genera reporte completo de maquinaria para Excel"""
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT 
                m.name AS 'Nombre',
                m.model AS 'Modelo',
                m.serial_number AS 'Número de Serie',
                m.identifier AS 'Matrícula/Identificador',
                m.classification AS 'Clasificación',
                m.consumption_rate AS 'Consumo Promedio (gal/día)',
                m.purchase_date AS 'Fecha de Compra',
                m.last_maintenance AS 'Último Mantenimiento',
                m.status AS 'Estado',
                m.created_at AS 'Fecha de Registro'
            FROM machinery m
            WHERE m.company_id = ?
            ORDER BY m.name
        """, conn, params=(company_id,))

def get_extended_machinery_report(company_id):
    """Genera reporte extendido de maquinaria incluyendo nuevos campos"""
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT 
                m.name AS 'Nombre',
                m.model AS 'Modelo',
                m.serial_number AS 'Número de Serie',
                m.identifier AS 'Matrícula/Identificador',
                m.classification AS 'Clasificación',
                m.consumption_per_hour AS 'Consumo (gal/hora)',
                COALESCE(m.consumption_rate, 0) AS 'Consumo Legacy (gal/día)',
                m.current_hours AS 'Horas Actuales',
                m.current_odometer AS 'Odómetro Actual',
                m.maintenance_interval_hours AS 'Intervalo Mant. (horas)',
                m.maintenance_interval_km AS 'Intervalo Mant. (km)',
                m.purchase_date AS 'Fecha de Compra',
                m.last_maintenance AS 'Último Mantenimiento',
                m.last_odometer_update AS 'Última Act. Odómetro',
                m.status AS 'Estado',
                m.created_at AS 'Fecha de Registro'
            FROM machinery m
            WHERE m.company_id = ?
            ORDER BY m.name
        """, conn, params=(company_id,))

def get_fuel_report(company_id):
    """Genera reporte completo de combustible para Excel"""
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT 
                m.name AS 'Máquina',
                m.identifier AS 'Matrícula',
                f.fuel_added AS 'Combustible Agregado (gal)',
                f.added_at AS 'Fecha de Recarga',
                f.added_by AS 'Registrado por',
                m.consumption_rate AS 'Consumo (gal/día)'
            FROM fuel_logs f
            JOIN machinery m ON f.machinery_id = m.id
            WHERE f.company_id = ?
            ORDER BY f.added_at DESC
        """, conn, params=(company_id,))

def get_critical_fuel_machines(company_id):
    """Obtiene máquinas con combustible crítico"""
    machinery = list_machinery(company_id)
    critical_machines = []
    
    for _, machine in machinery.iterrows():
        if machine['consumption_rate'] and machine['consumption_rate'] > 0:
            status = get_fuel_status_advanced(machine['id'])
            if status['status'] in ['critical', 'warning']:
                critical_machines.append({
                    'id': machine['id'],
                    'name': machine['name'],
                    'identifier': machine.get('identifier', ''),
                    'status': status['status'],
                    'message': status['message'],
                    'days_remaining': status.get('days_remaining', 0)
                })
    
    return critical_machines

def get_critical_fuel_machines_extended(empresa_id):
    """Versión extendida que incluye alertas de controles"""
    try:
        # Intentar usar el nuevo sistema
        control_alerts = get_critical_control_alerts(empresa_id)
        fuel_alerts = []
        
        for alert in control_alerts:
            if 'COMBUSTIBLE' in alert['type'].upper():
                fuel_alerts.append({
                    'id': alert['machine_id'],
                    'name': alert['machine_name'],
                    'identifier': alert.get('identifier', ''),
                    'status': 'critical' if alert['level'] == 'critico' else 'warning',
                    'message': alert['message'],
                    'days_remaining': 0  # Se calculará si es necesario
                })
        
        if fuel_alerts:
            return fuel_alerts
    except:
        pass
    
    # Fallback al sistema original
    return get_critical_fuel_machines(empresa_id)

def get_critical_control_alerts(empresa_id):
    """Obtiene alertas críticas de todos los controles"""
    alerts = []
    
    try:
        # Importar funciones del módulo de controles
        from controles_module import get_fluid_types, get_machine_fluid_status, get_company_setting
        
        # Obtener máquinas de la empresa
        with get_conn() as conn:
            maquinas_df = pd.read_sql_query("""
                SELECT id, name, identifier, consumption_per_hour
                FROM machinery WHERE company_id = ? AND status = 'Active'
            """, conn, params=(empresa_id,))
            
            # Obtener tipos de fluidos
            fluid_types = get_fluid_types()
            unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
            
            # Verificar estado de cada máquina para cada fluido
            for _, machine in maquinas_df.iterrows():
                for _, fluid in fluid_types.iterrows():
                    try:
                        status = get_machine_fluid_status(machine['id'], fluid['id'], unit_preference)
                        
                        if status['level'] in ['critico', 'malo']:
                            alerts.append({
                                'type': f"FLUIDO - {fluid['name']}",
                                'level': status['level'],
                                'machine_id': machine['id'],
                                'machine_name': machine['name'],
                                'identifier': machine.get('identifier', ''),
                                'message': status.get('message', f"{fluid['name']} en estado {status['level']}")
                            })
                    except Exception:
                        continue
                        
    except ImportError:
        pass  # Módulo de controles no disponible
    except Exception:
        pass  # Error en obtener alertas
    
    return alerts

def get_machine_control_status(machinery_id, empresa_id):
    """Obtiene el estado general de controles para una máquina"""
    try:
        from controles_module import get_machine_fluid_status, get_maintenance_status_by_hours_km, get_fluid_types, get_company_setting
        
        with get_conn() as conn:
            machine_info = pd.read_sql_query("""
                SELECT * FROM machinery WHERE id = ? AND company_id = ?
            """, conn, params=(machinery_id, empresa_id))
            
            if machine_info.empty:
                return {"status": "error", "message": "Máquina no encontrada"}
            
            machine = machine_info.iloc[0]
            fluid_types = get_fluid_types()
            unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
            
            # Estados de fluidos
            fluid_statuses = {}
            for _, fluid in fluid_types.iterrows():
                try:
                    status = get_machine_fluid_status(machinery_id, fluid['id'], unit_preference)
                    fluid_statuses[fluid['name']] = status
                except Exception:
                    continue
            
            # Estado de mantenimiento
            maintenance_status = get_maintenance_status_by_hours_km(machine)
            
            # Determinar estado general más crítico
            all_levels = [status['level'] for status in fluid_statuses.values() if 'level' in status]
            if maintenance_status.get('status'):
                all_levels.append(maintenance_status['status'])
            
            priority_order = {"vencido": 0, "critico": 1, "malo": 2, "advertencia": 3, "regular": 4, "ok": 5, "excelente": 6}
            
            if all_levels:
                worst_level = min(all_levels, key=lambda x: priority_order.get(x, 10))
                return {
                    "status": worst_level,
                    "fluid_statuses": fluid_statuses,
                    "maintenance_status": maintenance_status,
                    "message": f"Estado general: {worst_level}"
                }
            else:
                return {"status": "sin_datos", "message": "No hay datos suficientes"}
                
    except ImportError:
        return {"status": "error", "message": "Módulo de controles no disponible"}
    except Exception as e:
        return {"status": "error", "message": f"Error: {str(e)}"}

# Funciones para el módulo de mantenimiento
def get_maintenance_types():
    """Obtiene todos los tipos de mantenimiento disponibles"""
    with get_conn() as conn:
        return pd.read_sql_query("SELECT * FROM maintenance_types ORDER BY name", conn)

def add_maintenance_type(name, description=None):
    """Añade un nuevo tipo de mantenimiento"""
    with get_conn() as conn:
        try:
            conn.execute("INSERT INTO maintenance_types (name, description) VALUES (?, ?)", 
                        (name, description))
            return True
        except sqlite3.IntegrityError:
            return False  # Ya existe

def get_maintenance_schedules(company_id):
    """Obtiene las programaciones de mantenimiento de una empresa"""
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT 
                ms.id,
                ms.machinery_id,
                m.name as machinery_name,
                m.identifier,
                mt.name as maintenance_type,
                ms.interval_hours,
                ms.interval_days,
                ms.description,
                ms.is_active
            FROM maintenance_schedules ms
            JOIN machinery m ON ms.machinery_id = m.id
            JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
            WHERE m.company_id = ?
            ORDER BY m.name, mt.name
        """, conn, params=(company_id,))

def add_maintenance_schedule(machinery_id, maintenance_type_id, interval_hours=None, interval_days=None, description=None):
    """Añade una programación de mantenimiento"""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO maintenance_schedules 
            (machinery_id, maintenance_type_id, interval_hours, interval_days, description)
            VALUES (?, ?, ?, ?, ?)
        """, (machinery_id, maintenance_type_id, interval_hours, interval_days, description))
    return True

def update_maintenance_schedule(schedule_id, **kwargs):
    """Actualiza una programación de mantenimiento"""
    with get_conn() as conn:
        fields = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if fields:
            values.append(schedule_id)
            query = f"UPDATE maintenance_schedules SET {', '.join(fields)} WHERE id = ?"
            conn.execute(query, values)
    return True

def delete_maintenance_schedule(schedule_id):
    """Elimina una programación de mantenimiento"""
    with get_conn() as conn:
        conn.execute("DELETE FROM maintenance_schedules WHERE id = ?", (schedule_id,))
    return True

def add_maintenance_record(machinery_id, maintenance_type_id, performed_by, hours_at_maintenance, 
                          performed_at=None, cost=None, description=None, parts_used=None, notes=None):
    """Registra un mantenimiento realizado"""
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO maintenance_records 
            (machinery_id, maintenance_type_id, performed_by, hours_at_maintenance, 
             performed_at, cost, description, parts_used, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (machinery_id, maintenance_type_id, performed_by, hours_at_maintenance,
              performed_at or datetime.now().isoformat(), cost, description, parts_used, notes))
    return True

def get_maintenance_records(company_id, machinery_id=None, maintenance_type_id=None, limit=None):
    """Obtiene registros de mantenimientos realizados - VERSIÓN CON FECHAS CORREGIDAS"""
    try:
        with get_conn() as conn:
            # Verificar qué columnas existen en maintenance_records
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(maintenance_records)")
            columns_info = cursor.fetchall()
            available_columns = [col[1] for col in columns_info]
            
            print(f"Columnas disponibles en maintenance_records: {available_columns}")
            
            # Construir SELECT dinámicamente basado en columnas disponibles
            select_parts = ["mr.id"]
            
            # Columnas de maquinaria (siempre disponibles)
            select_parts.extend([
                "m.name as machinery_name",
                "COALESCE(m.identifier, 'Sin matrícula') as identifier"
            ])
            
            # Verificar maintenance_types
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_types'")
            has_maintenance_types = cursor.fetchone() is not None
            
            if has_maintenance_types and 'maintenance_type_id' in available_columns:
                select_parts.append("COALESCE(mt.name, 'Mantenimiento') as maintenance_type")
                join_mt = "LEFT JOIN maintenance_types mt ON mr.maintenance_type_id = mt.id"
            else:
                select_parts.append("'Mantenimiento' as maintenance_type")
                join_mt = ""
            
            # FECHA DE REALIZACIÓN - PRIORIZAR FECHA FIN
            date_column = None
            # Buscar columnas de fecha en orden de prioridad (fecha fin primero)
            date_priority = ['end_date', 'date_fin', 'fecha_fin', 'performed_at', 'date_performed', 'maintenance_date', 'created_at']
            
            for col in date_priority:
                if col in available_columns:
                    date_column = col
                    print(f"Usando columna de fecha: {col}")
                    break
            
            if date_column:
                select_parts.append(f"mr.{date_column} as performed_at")
            else:
                select_parts.append("datetime('now') as performed_at")
                print("No se encontró columna de fecha, usando fecha actual")
            
            # Otras columnas opcionales
            optional_columns = {
                'performed_by': "'admin' as performed_by",
                'hours_at_maintenance': "0 as hours_at_maintenance", 
                'cost': "0 as cost",
                'description': "'' as description",
                'parts_used': "'' as parts_used",
                'notes': "'' as notes"
            }
            
            for col, default_value in optional_columns.items():
                if col in available_columns:
                    select_parts.append(f"COALESCE(mr.{col}, {default_value.split(' as ')[0]}) as {col}")
                else:
                    select_parts.append(default_value)
            
            # Construir consulta completa
            base_query = f"""
                SELECT {', '.join(select_parts)}
                FROM maintenance_records mr
                JOIN machinery m ON mr.machinery_id = m.id
                {join_mt}
                WHERE m.company_id = ?
            """
            
            params = [company_id]
            
            if machinery_id:
                base_query += " AND mr.machinery_id = ?"
                params.append(machinery_id)
            
            if maintenance_type_id and 'maintenance_type_id' in available_columns:
                base_query += " AND mr.maintenance_type_id = ?"
                params.append(maintenance_type_id)
            
            # Ordenar por fecha si existe, sino por ID
            if date_column:
                base_query += f" ORDER BY mr.{date_column} DESC"
            else:
                base_query += " ORDER BY mr.id DESC"
            
            if limit:
                base_query += " LIMIT ?"
                params.append(limit)
            
            print(f"Consulta generada: {base_query}")
            
            return pd.read_sql_query(base_query, conn, params=params)
            
    except Exception as e:
        print(f"Error en get_maintenance_records: {e}")
        # Fallback a consulta muy básica
        try:
            with get_conn() as conn:
                return pd.read_sql_query("""
                    SELECT 
                        mr.id,
                        m.name as machinery_name,
                        COALESCE(m.identifier, 'Sin matrícula') as identifier,
                        'Mantenimiento' as maintenance_type,
                        COALESCE(mr.created_at, datetime('now')) as performed_at,
                        'admin' as performed_by,
                        0 as hours_at_maintenance,
                        COALESCE(mr.cost, 0) as cost,
                        '' as description,
                        '' as parts_used,
                        '' as notes
                    FROM maintenance_records mr
                    JOIN machinery m ON mr.machinery_id = m.id
                    WHERE m.company_id = ?
                    ORDER BY mr.id DESC
                """, conn, params=[company_id])
        except Exception as e2:
            print(f"Error en fallback: {e2}")

def update_machinery_hours(machinery_id, current_hours, updated_by="admin", notes=None):
    """Actualiza las horas del horómetro de una máquina"""
    with get_conn() as conn:
        # Actualizar tabla machinery
        conn.execute("""
            UPDATE machinery 
            SET current_hours = ?, last_hour_update = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (current_hours, machinery_id))
        
        # Registrar en log
        conn.execute("""
            INSERT INTO hour_meter_logs (machinery_id, current_hours, recorded_by, notes)
            VALUES (?, ?, ?, ?)
        """, (machinery_id, current_hours, updated_by, notes))
    
    return True

def get_hour_meter_logs(machinery_id, limit=10):
    """Obtiene el historial de actualizaciones de horómetro"""
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT current_hours, recorded_at, recorded_by, notes
            FROM hour_meter_logs
            WHERE machinery_id = ?
            ORDER BY recorded_at DESC
            LIMIT ?
        """, conn, params=(machinery_id, limit))

def get_machinery_maintenance_status(machinery_id):
    """Obtiene el estado de mantenimiento de una máquina específica"""
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT 
                m.id,
                m.name,
                m.current_hours,
                ms.interval_hours,
                mt.name as maintenance_type,
                mr.hours_at_maintenance,
                mr.performed_at as last_maintenance,
                (m.current_hours - COALESCE(mr.hours_at_maintenance, 0)) as hours_since_maintenance,
                (ms.interval_hours - (m.current_hours - COALESCE(mr.hours_at_maintenance, 0))) as hours_until_maintenance
            FROM machinery m
            LEFT JOIN maintenance_schedules ms ON m.id = ms.machinery_id AND ms.is_active = 1
            LEFT JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
            LEFT JOIN (
                SELECT DISTINCT 
                    machinery_id,
                    maintenance_type_id,
                    hours_at_maintenance,
                    performed_at,
                    ROW_NUMBER() OVER (PARTITION BY machinery_id, maintenance_type_id ORDER BY performed_at DESC) as rn
                FROM maintenance_records
            ) mr ON m.id = mr.machinery_id AND ms.maintenance_type_id = mr.maintenance_type_id AND mr.rn = 1
            WHERE m.id = ?
        """, conn, params=(machinery_id,))

def get_company_maintenance_overview(company_id):
    """Obtiene un resumen del estado de mantenimiento de todas las máquinas de una empresa"""
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT 
                m.id,
                m.name,
                m.identifier,
                m.current_hours,
                ms.interval_hours,
                mt.name as maintenance_type,
                mr.hours_at_maintenance,
                mr.performed_at as last_maintenance,
                (m.current_hours - COALESCE(mr.hours_at_maintenance, 0)) as hours_since_maintenance,
                (ms.interval_hours - (m.current_hours - COALESCE(mr.hours_at_maintenance, 0))) as hours_until_maintenance
            FROM machinery m
            LEFT JOIN maintenance_schedules ms ON m.id = ms.machinery_id AND ms.is_active = 1
            LEFT JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
            LEFT JOIN (
                SELECT DISTINCT 
                    machinery_id,
                    maintenance_type_id,
                    hours_at_maintenance,
                    performed_at,
                    ROW_NUMBER() OVER (PARTITION BY machinery_id, maintenance_type_id ORDER BY performed_at DESC) as rn
                FROM maintenance_records
            ) mr ON m.id = mr.machinery_id AND ms.maintenance_type_id = mr.maintenance_type_id AND mr.rn = 1
            WHERE m.company_id = ?
            ORDER BY hours_until_maintenance ASC NULLS LAST
        """, conn, params=(company_id,))

def get_maintenance_report(company_id):
    """Genera reporte completo de mantenimiento para Excel"""
    with get_conn() as conn:
        return pd.read_sql_query("""
            SELECT 
                m.name AS 'Máquina',
                m.identifier AS 'Matrícula',
                m.current_hours AS 'Horas Actuales',
                mt.name AS 'Tipo de Mantenimiento',
                ms.interval_hours AS 'Intervalo (horas)',
                mr.performed_at AS 'Último Mantenimiento',
                mr.hours_at_maintenance AS 'Horas en Último Mant.',
                mr.performed_by AS 'Realizado por',
                mr.cost AS 'Costo',
                mr.description AS 'Descripción',
                (m.current_hours - COALESCE(mr.hours_at_maintenance, 0)) AS 'Horas Desde Último',
                (ms.interval_hours - (m.current_hours - COALESCE(mr.hours_at_maintenance, 0))) AS 'Horas Hasta Próximo'
            FROM machinery m
            LEFT JOIN maintenance_schedules ms ON m.id = ms.machinery_id AND ms.is_active = 1
            LEFT JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
            LEFT JOIN (
                SELECT DISTINCT 
                    machinery_id,
                    maintenance_type_id,
                    hours_at_maintenance,
                    performed_at,
                    performed_by,
                    cost,
                    description,
                    ROW_NUMBER() OVER (PARTITION BY machinery_id, maintenance_type_id ORDER BY performed_at DESC) as rn
                FROM maintenance_records
            ) mr ON m.id = mr.machinery_id AND ms.maintenance_type_id = mr.maintenance_type_id AND mr.rn = 1
            WHERE m.company_id = ?
            ORDER BY m.name, mt.name
        """, conn, params=(company_id,))

# Funciones para reportes extendidos
def get_controls_report(company_id):
    """Genera reporte de controles (fluidos, trabajo, etc.)"""
    try:
        from controles_module import get_company_tanks, get_company_setting
        
        with get_conn() as conn:
            # Reporte de trabajo diario
            work_report = pd.read_sql_query("""
                SELECT 
                    m.name AS 'Máquina',
                    m.identifier AS 'Matrícula',
                    dwl.work_date AS 'Fecha',
                    dwl.hours_worked AS 'Horas Trabajadas',
                    dwl.odometer_reading AS 'Lectura Odómetro',
                    dwl.operator AS 'Operador',
                    dwl.work_description AS 'Descripción del Trabajo',
                    dwl.recorded_by AS 'Registrado por',
                    dwl.recorded_at AS 'Fecha de Registro'
                FROM daily_work_logs dwl
                JOIN machinery m ON dwl.machinery_id = m.id
                WHERE dwl.company_id = ?
                ORDER BY dwl.work_date DESC, m.name
            """, conn, params=(company_id,))
            
            # Reporte de tanques
            tanks_info = get_company_tanks(company_id)
            unit_preference = get_company_setting(company_id, "unit_preference", "galones")
            
            # Reporte de reabastecimientos de tanques
            tank_refills = pd.read_sql_query("""
                SELECT 
                    ft.name AS 'Tipo de Fluido',
                    trl.amount_added AS 'Cantidad Agregada',
                    trl.cost AS 'Costo',
                    trl.supplier AS 'Proveedor',
                    trl.refilled_at AS 'Fecha de Reabastecimiento',
                    trl.refilled_by AS 'Registrado por',
                    trl.notes AS 'Notas'
                FROM tank_refill_logs trl
                JOIN company_fluid_tanks cft ON trl.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ?
                ORDER BY trl.refilled_at DESC
            """, conn, params=(company_id,))
            
            return {
                "work_report": work_report,
                "tanks_info": tanks_info,
                "tank_refills": tank_refills,
                "unit_preference": unit_preference
            }
            
    except ImportError:
        return {"error": "Módulo de controles no disponible"}
    except Exception as e:
        return {"error": f"Error al generar reporte: {str(e)}"}

def get_fluids_consumption_report(company_id):
    """Genera reporte de consumo de fluidos por máquina"""
    try:
        from controles_module import get_fluid_types, get_company_setting
        fluid_types = get_fluid_types()
        unit_preference = get_company_setting(company_id, "unit_preference", "galones")
        with get_conn() as conn:
            consumption_data = []
            # Obtener máquinas activas
            machines = pd.read_sql_query("""
                SELECT id, name, identifier, consumption_per_hour, current_hours
                FROM machinery 
                WHERE company_id = ? AND status = 'Active'
                ORDER BY name
            """, conn, params=(company_id,))
            for _, machine in machines.iterrows():
                for _, fluid in fluid_types.iterrows():
                    # Obtener registros de este fluido para esta máquina
                    fluid_logs = pd.read_sql_query("""
                        SELECT 
                            SUM(fuel_added) as total_added,
                            COUNT(*) as refill_count,
                            MIN(added_at) as first_refill,
                            MAX(added_at) as last_refill,
                            SUM(work_hours) as total_work_hours
                        FROM fuel_logs
                        WHERE machinery_id = ? AND fluid_type_id = ?
                    """, conn, params=(machine['id'], fluid['id']))
                    if not fluid_logs.empty and fluid_logs.iloc[0]['total_added'] is not None:
                        log_data = fluid_logs.iloc[0]
                        # Calcular consumo estimado
                        consumption_per_hour = machine.get('consumption_per_hour', 0) or 0
                        work_hours = log_data['total_work_hours'] or 0
                        if work_hours > 0:
                            estimated_consumption = consumption_per_hour * work_hours
                        else:
                            # Estimar basado en tiempo transcurrido
                            if log_data['first_refill'] and log_data['last_refill']:
                                days_diff = (pd.to_datetime(log_data['last_refill']) - pd.to_datetime(log_data['first_refill'])).days
                                estimated_consumption = consumption_per_hour * days_diff * 8  # 8 horas promedio por día
                            else:
                                estimated_consumption = 0
                        # LÍNEA CORREGIDA:
                        remaining = max(0, log_data['total_added'] - estimated_consumption)
                        consumption_data.append({
                            'Máquina': machine['name'],
                            'Matrícula': machine.get('identifier', ''),
                            'Tipo de Fluido': fluid['name'],
                            f'Total Agregado ({unit_preference})': round(log_data['total_added'], 2),
                            f'Consumo Estimado ({unit_preference})': round(estimated_consumption, 2),
                            f'Restante ({unit_preference})': round(remaining, 2),
                            'Número de Recargas': int(log_data['refill_count']),
                            'Primera Recarga': log_data['first_refill'],
                            'Última Recarga': log_data['last_refill'],
                            'Horas Trabajadas': round(work_hours, 1)
                        })
            return pd.DataFrame(consumption_data)
    except Exception as e:
        return pd.DataFrame()

# Funciones para gestión de tanques empresariales
def setup_default_company_tanks(empresa_id, unit_preference="galones"):
    """Configura tanques por defecto para una empresa"""
    try:
        from controles_module import get_fluid_types, setup_company_tank
        
        fluid_types = get_fluid_types()
        
        # Capacidades por defecto según el tipo de fluido
        default_capacities = {
            "Combustible": 1000,
            "Aceite": 200,
            "Grasa": 50,
            "Coolant": 100
        }
        
        for _, fluid in fluid_types.iterrows():
            capacity = default_capacities.get(fluid['name'], 100)
            setup_company_tank(empresa_id, fluid['id'], capacity, unit_preference)
        
        return True
        
    except Exception as e:
        return False

def migrate_legacy_fuel_data():
    """Migra datos de combustible legacy al nuevo sistema"""
    with get_conn() as conn:
        # Actualizar fuel_logs para que tengan fluid_type_id = 1 (Combustible) si no lo tienen
        conn.execute("""
            UPDATE fuel_logs 
            SET fluid_type_id = 1 
            WHERE fluid_type_id IS NULL
        """)
        
        # Migrar consumption_rate a consumption_per_hour dividiendo por 24 (asumiendo 24h/día)
        conn.execute("""
            UPDATE machinery 
            SET consumption_per_hour = ROUND(COALESCE(consumption_rate, 0) / 24.0, 3)
            WHERE consumption_per_hour IS NULL OR consumption_per_hour = 0
        """)
        
        conn.commit()

# Funciones de análisis y estadísticas avanzadas
def get_machinery_efficiency_analysis(empresa_id):
    """Analiza la eficiencia de las máquinas basado en consumo vs trabajo"""
    with get_conn() as conn:
        analysis = pd.read_sql_query("""
            SELECT 
                m.name,
                m.identifier,
                m.classification,
                m.consumption_per_hour,
                m.current_hours,
                COALESCE(SUM(dwl.hours_worked), 0) as total_work_hours,
                COALESCE(SUM(fl.fuel_added), 0) as total_fuel_added,
                CASE 
                    WHEN SUM(dwl.hours_worked) > 0 THEN SUM(fl.fuel_added) / SUM(dwl.hours_worked)
                    ELSE 0 
                END as actual_consumption_per_hour,
                CASE 
                    WHEN m.consumption_per_hour > 0 AND SUM(dwl.hours_worked) > 0 THEN
                        ABS(m.consumption_per_hour - (SUM(fl.fuel_added) / SUM(dwl.hours_worked))) / m.consumption_per_hour * 100
                    ELSE 0
                END as efficiency_variance_percent
            FROM machinery m
            LEFT JOIN daily_work_logs dwl ON m.id = dwl.machinery_id
            LEFT JOIN fuel_logs fl ON m.id = fl.machinery_id AND fl.fluid_type_id = 1
            WHERE m.company_id = ?
            GROUP BY m.id, m.name, m.identifier, m.classification, m.consumption_per_hour, m.current_hours
            ORDER BY efficiency_variance_percent DESC
        """, conn, params=(empresa_id,))
        
        return analysis

def get_predictive_maintenance_analysis(empresa_id):
    """Análisis predictivo de mantenimiento basado en horas de trabajo"""
    with get_conn() as conn:
        analysis = pd.read_sql_query("""
            SELECT 
                m.name,
                m.identifier,
                m.classification,
                m.current_hours,
                m.maintenance_interval_hours,
                m.maintenance_interval_km,
                m.current_odometer,
                COALESCE(MAX(mr.hours_at_maintenance), 0) as last_maintenance_hours,
                COALESCE(MAX(mr.performed_at), 'Nunca') as last_maintenance_date,
                CASE 
                    WHEN m.maintenance_interval_hours > 0 THEN
                        m.maintenance_interval_hours - (m.current_hours - COALESCE(MAX(mr.hours_at_maintenance), 0))
                    ELSE NULL
                END as hours_until_maintenance,
                CASE 
                    WHEN m.maintenance_interval_km > 0 THEN
                        m.maintenance_interval_km - (m.current_odometer - COALESCE(MAX(mr_km.odometer_at_maintenance), 0))
                    ELSE NULL
                END as km_until_maintenance
            FROM machinery m
            LEFT JOIN maintenance_records mr ON m.id = mr.machinery_id
            LEFT JOIN maintenance_records mr_km ON m.id = mr_km.machinery_id
            WHERE m.company_id = ?
            GROUP BY m.id, m.name, m.identifier, m.classification, m.current_hours, 
                     m.maintenance_interval_hours, m.maintenance_interval_km, m.current_odometer
            ORDER BY 
                CASE 
                    WHEN hours_until_maintenance IS NOT NULL AND hours_until_maintenance <= 0 THEN 1
                    WHEN km_until_maintenance IS NOT NULL AND km_until_maintenance <= 0 THEN 1
                    WHEN hours_until_maintenance IS NOT NULL THEN hours_until_maintenance
                    WHEN km_until_maintenance IS NOT NULL THEN km_until_maintenance
                    ELSE 9999
                END ASC
        """, conn, params=(empresa_id,))
        
        return analysis

def get_cost_analysis_report(empresa_id):
    """Análisis de costos por máquina y tipo de fluido"""
    with get_conn() as conn:
        cost_analysis = pd.read_sql_query("""
            SELECT 
                m.name as machine_name,
                m.identifier,
                ft.name as fluid_type,
                COUNT(fl.id) as refill_count,
                SUM(fl.fuel_added) as total_volume,
                AVG(fl.fuel_added) as avg_refill_volume,
                COALESCE(SUM(trl.cost), 0) as total_fluid_cost,
                COALESCE(SUM(mr.cost), 0) as total_maintenance_cost,
                (COALESCE(SUM(trl.cost), 0) + COALESCE(SUM(mr.cost), 0)) as total_cost
            FROM machinery m
            LEFT JOIN fuel_logs fl ON m.id = fl.machinery_id
            LEFT JOIN fluid_types ft ON fl.fluid_type_id = ft.id
            LEFT JOIN company_fluid_tanks cft ON ft.id = cft.fluid_type_id AND cft.company_id = m.company_id
            LEFT JOIN tank_refill_logs trl ON cft.id = trl.tank_id
            LEFT JOIN maintenance_records mr ON m.id = mr.machinery_id
            WHERE m.company_id = ?
            GROUP BY m.id, m.name, m.identifier, ft.id, ft.name
            HAVING total_volume > 0
            ORDER BY total_cost DESC, m.name, ft.name
        """, conn, params=(empresa_id,))
        
        return cost_analysis

def add_fuel_to_tank(company_id, fluid_type_id, amount, cost=None, supplier=None, added_by="admin", notes=None):
    """Añade fluido al tanque empresarial"""
    try:
        with get_conn() as conn:
            # Buscar el tanque correspondiente a la empresa y tipo de fluido
            tank_info = pd.read_sql_query("""
                SELECT id, tank_capacity, current_level, unit
                FROM company_fluid_tanks
                WHERE company_id = ? AND fluid_type_id = ?
            """, conn, params=(company_id, fluid_type_id))
            
            if tank_info.empty:
                return False, "Tanque no encontrado"
            
            tank = tank_info.iloc[0]
            tank_id = int(tank['id'])
            current_level = float(tank['current_level'] or 0)
            tank_capacity = float(tank['tank_capacity'])
            new_level = current_level + float(amount)
            
            # Validar capacidad
            if new_level > tank_capacity:
                available = tank_capacity - current_level
                return False, f"Excede la capacidad del tanque. Disponible: {available:.1f} {tank['unit']}"
            
            # Actualizar nivel del tanque
            conn.execute("""
                UPDATE company_fluid_tanks 
                SET current_level = ?
                WHERE id = ? AND company_id = ?
            """, (new_level, tank_id, company_id))
            
            # Registrar el reabastecimiento
            conn.execute("""
                INSERT INTO tank_refill_logs 
                (tank_id, amount_added, cost, supplier, refilled_by, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tank_id, amount, cost, supplier, added_by, notes))
            
            conn.commit()
            return True, f"Fluido agregado correctamente. Nuevo nivel: {new_level:.1f}/{tank_capacity:.0f} {tank['unit']}"
            
    except Exception as e:
        return False, f"Error al agregar fluido: {str(e)}"

def add_fuel_to_tank_safe(company_id, fluid_type_id, amount, cost=None, supplier=None, added_by="admin", notes=None):
    """Versión mejorada para añadir combustible con manejo de concurrencia"""
    def _add_fuel_operation():
        with get_conn() as conn:
            cursor = conn.cursor()
            # Obtener información del tanque
            cursor.execute("""
                SELECT id, tank_capacity, current_level, unit
                FROM company_fluid_tanks
                WHERE company_id = ? AND fluid_type_id = ?
            """, (company_id, fluid_type_id))
            tank_row = cursor.fetchone()
            if not tank_row:
                return False, "Tanque no encontrado"
            tank_id, tank_capacity, current_level, unit = tank_row
            current_level = float(current_level or 0)
            tank_capacity = float(tank_capacity)
            new_level = current_level + float(amount)
            # Validar capacidad
            if new_level > tank_capacity:
                available = tank_capacity - current_level
                return False, f"Excede la capacidad del tanque. Disponible: {available:.1f} {unit}"
            # Actualizar nivel del tanque
            cursor.execute("""
                UPDATE company_fluid_tanks 
                SET current_level = ?
                WHERE id = ?
            """, (new_level, tank_id))
            # Registrar el reabastecimiento
            cursor.execute("""
                INSERT INTO tank_refill_logs 
                (tank_id, amount_added, cost, supplier, refilled_by, notes, refilled_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (tank_id, amount, cost, supplier, added_by, notes))
            conn.commit()
            return True, f"Fluido agregado correctamente. Nuevo nivel: {new_level:.1f}/{tank_capacity:.0f} {unit}"
    try:
        return safe_execute_with_retry(_add_fuel_operation)
    except Exception as e:
        return False, f"Error al agregar fluido: {str(e)}"

def init_additional_tables():
    """
    Inicializa tablas adicionales necesarias para el sistema.
    Esta función puede ser extendida según tus necesidades específicas.
    """
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Tabla para registros de uso de combustible por máquina
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fuel_usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machinery_id INTEGER,
                    fuel_amount REAL NOT NULL,
                    usage_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    operator TEXT,
                    notes TEXT,
                    FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE
                )
            """)
            
            # Tabla para registros de productividad
            cur.execute("""
                CREATE TABLE IF NOT EXISTS productivity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machinery_id INTEGER,
                    hours_worked REAL NOT NULL,
                    work_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    task_description TEXT,
                    operator TEXT,
                    FOREIGN KEY (machinery_id) REFERENCES machinery(id) ON DELETE CASCADE
                )
            """)
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Error inicializando tablas adicionales: {e}")
        return False

def debug_tank_status(empresa_id):
    """Función de diagnóstico para revisar estado de tanques"""
    print(f"\n=== DEBUG TANK STATUS para empresa {empresa_id} ===")
    try:
        with get_conn() as conn:
            tables = pd.read_sql_query("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('company_fluid_tanks', 'fluid_types', 'tank_refill_logs')
            """, conn)
            print(f"Tablas encontradas: {tables['name'].tolist()}")
            fluid_types = pd.read_sql_query("SELECT * FROM fluid_types", conn)
            print(f"Tipos de fluidos: {len(fluid_types)}")
            for _, ft in fluid_types.iterrows():
                print(f"  - {ft['id']}: {ft['name']}")
            tanks = pd.read_sql_query("""
                SELECT cft.*, ft.name as fluid_name
                FROM company_fluid_tanks cft
                LEFT JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ?
            """, conn, params=(empresa_id,))
            print(f"Tanques empresa {empresa_id}: {len(tanks)}")
            for _, tank in tanks.iterrows():
                print(f"  - {tank['fluid_name']}: {tank['current_level']}/{tank['tank_capacity']} {tank['unit']}")
            logs = pd.read_sql_query("""
                SELECT trl.*, ft.name as fluid_name
                FROM tank_refill_logs trl
                JOIN company_fluid_tanks cft ON trl.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ?
                ORDER BY trl.refilled_at DESC
                LIMIT 5
            """, conn, params=(empresa_id,))
            print(f"Últimos logs de reabastecimiento: {len(logs)}")
            for _, log in logs.iterrows():
                print(f"  - {log['fluid_name']}: +{log['amount_added']} el {log['refilled_at']}")
    except Exception as e:
        print(f"ERROR en debug: {e}")
    print("=== FIN DEBUG ===\n")

def optimize_db_connection():
    """Optimiza la configuración de la base de datos"""
    try:
        with get_conn() as conn:
            # Configuraciones de rendimiento
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL") 
            conn.execute("PRAGMA cache_size = 10000")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.commit()
    except Exception as e:
        print(f"Error optimizing DB: {str(e)}")

def add_fuel_to_tank_unified(company_id, fluid_type_id, amount, cost=None, supplier=None, added_by="admin", notes=None):
    """Función unificada para añadir fluido al tanque - conecta con módulo de controles"""
    try:
        from controles_module import update_tank_level

        with get_conn() as conn:
            # Obtener información del tanque
            tank_query = """
                SELECT id, tank_capacity, current_level, unit
                FROM company_fluid_tanks
                WHERE company_id = ? AND fluid_type_id = ?
            """
            tank = pd.read_sql_query(tank_query, conn, params=(company_id, fluid_type_id))
            
            if tank.empty:
                return False, "Tanque no encontrado"
            
            tank_info = tank.iloc[0]
            current_level = float(tank_info['current_level'] or 0)
            tank_capacity = float(tank_info['tank_capacity'])
            new_level = current_level + float(amount)
            
            # Validar capacidad
            if new_level > tank_capacity:
                available = tank_capacity - current_level
                return False, f"Excede la capacidad del tanque. Disponible: {available:.1f} {tank_info['unit']}"
            
            # Actualizar nivel usando módulo de controles
            success = update_tank_level(company_id, fluid_type_id, amount)
            if not success:
                return False, "Error al actualizar el nivel del tanque"
            
            # Registrar el reabastecimiento
            conn.execute("""
                INSERT INTO tank_refill_logs 
                (tank_id, amount_added, cost, supplier, refilled_by, notes, refilled_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (tank_info['id'], amount, cost, supplier, added_by, notes))
            
            conn.commit()
            return True, f"Fluido agregado correctamente. Nuevo nivel: {new_level:.1f}/{tank_capacity:.0f} {tank_info['unit']}"
    except Exception as e:
        return False, f"Error al agregar fluido: {str(e)}"

def verificar_consistencia_tanques(empresa_id):
    """Verifica que los datos de los tanques sean consistentes"""
    try:
        # Configurar pandas para evitar el warning de downcasting
        pd.set_option('future.no_silent_downcasting', True)
        
        with get_conn() as conn:
            # Verificar que todos los tanques tengan fluid_type_id válido
            consistency_check = pd.read_sql_query("""
                SELECT cft.id, cft.fluid_type_id, ft.name as fluid_name,
                       (ft.id IS NULL) as missing_fluid_type
                FROM company_fluid_tanks cft
                LEFT JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ?
            """, conn, params=(empresa_id,))
            
            # Usar infer_objects para evitar el warning de downcasting
            consistency_check = consistency_check.infer_objects(copy=False)
            
            problemas = consistency_check[consistency_check['missing_fluid_type'] == True]
            if not problemas.empty:
                print("❌ Se encontraron tanques con fluid_type_id inválido")
                print(problemas)
                return False
            
            # Verificar que los niveles actuales sean consistentes con los logs
            nivel_vs_logs = pd.read_sql_query("""
                SELECT 
                    cft.id,
                    cft.current_level,
                    (SELECT COALESCE(SUM(amount_added), 0) 
                     FROM tank_refill_logs 
                     WHERE tank_id = cft.id) as total_logs
                FROM company_fluid_tanks cft
                WHERE cft.company_id = ?
            """, conn, params=(empresa_id,))
            
            # Usar infer_objects para evitar el warning de downcasting
            nivel_vs_logs = nivel_vs_logs.infer_objects(copy=False)
            
            inconsistencias = nivel_vs_logs[abs(nivel_vs_logs['current_level'] - nivel_vs_logs['total_logs']) > 0.1]
            if not inconsistencias.empty:
                print("❌ Se encontraron inconsistencias entre niveles y logs:")
                print(inconsistencias)
                return False
            
            return True
    except Exception as e:
        print(f"Error en verificación de consistencia: {str(e)}")
        return False
    
    # ... (el código existente de db_utils.py)

# =============================================
# Funciones de db_utils_extension.py
# =============================================

def optimize_db_connection():
    """Optimiza la configuración de la base de datos"""
    try:
        with get_conn() as conn:
            # Configuraciones de rendimiento
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL") 
            conn.execute("PRAGMA cache_size = 10000")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.commit()
    except Exception as e:
        print(f"Error optimizing DB: {str(e)}")

def get_company_tanks(empresa_id):
    """
    Obtiene todos los tanques de una empresa con información actualizada
    Esta función reemplaza versiones anteriores con mejor manejo de errores
    """
    try:
        with get_conn() as conn:
            query = """
                SELECT 
                    cft.id,
                    cft.company_id,
                    cft.tank_capacity,
                    cft.current_level,
                    cft.unit,
                    cft.fluid_type_id,
                    ft.name as fluid_name,
                    ft.unit_type,
                    cft.created_at
                FROM company_fluid_tanks cft
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ?
                ORDER BY ft.name
            """
            
            result = pd.read_sql_query(query, conn, params=(empresa_id,))
            
            # Asegurar tipos de datos correctos
            if not result.empty:
                result['current_level'] = result['current_level'].astype(float)
                result['tank_capacity'] = result['tank_capacity'].astype(float)
            
            return result
            
    except Exception as e:
        print(f"Error getting company tanks: {str(e)}")
        return pd.DataFrame()

def validate_tank_operations(empresa_id):
    """
    Valida que todas las operaciones de tanques sean consistentes
    """
    try:
        with get_conn() as conn:
            issues = []
            
            # Verificar que los niveles calculados coincidan con los movimientos
            validation_query = """
                SELECT 
 
                    cft.id as tank_id,
                    ft.name as fluid_name,
                    cft.current_level as recorded_level,
                    COALESCE(
                        (SELECT SUM(
                            CASE 
                                WHEN fim.movement_type = 'ENTRADA' THEN fim.quantity
                                WHEN fim.movement_type = 'SALIDA' THEN -fim.quantity
                                ELSE 0
                            END
                        )
                        FROM fluid_inventory_movements fim
                        WHERE fim.tank_id = cft.id), 0
                    ) as calculated_level
                FROM company_fluid_tanks cft
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ?
            """
            
            validation_results = pd.read_sql_query(validation_query, conn, params=(empresa_id,))
            
            for _, tank in validation_results.iterrows():
                recorded = float(tank['recorded_level'])
                calculated = float(tank['calculated_level'])
                difference = abs(recorded - calculated)
                
                if difference > 0.01:  # Tolerancia de 0.01 unidades
                    issues.append({
                        'tank_id': tank['tank_id'],
                        'fluid_name': tank['fluid_name'],
                        'issue_type': 'level_mismatch',
                        'recorded_level': recorded,
                        'calculated_level': calculated,
                        'difference': difference
                    })
            
            # Verificar movimientos huérfanos
            orphaned_movements = pd.read_sql_query("""
                SELECT fim.id, fim.tank_id, fim.movement_type, fim.quantity
                FROM fluid_inventory_movements fim
                LEFT JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                WHERE cft.id IS NULL
            """, conn)
            
            for _, movement in orphaned_movements.iterrows():
                issues.append({
                    'movement_id': movement['id'],
                    'tank_id': movement['tank_id'],
                    'issue_type': 'orphaned_movement',
                    'movement_type': movement['movement_type'],
                    'quantity': movement['quantity']
                })
            
            return issues
            
    except Exception as e:
        print(f"Error validating tank operations: {str(e)}")
        return [{'issue_type': 'validation_error', 'error': str(e)}]

def obtener_info_empresa(empresa_id):
    """Obtiene información adicional de la empresa"""
    with get_conn() as conn:
        result = pd.read_sql_query("""
            SELECT * FROM company_info WHERE company_id = ?
        """, conn, params=(empresa_id,))
        if not result.empty:
            return result.iloc[0].to_dict()
        return {}

def actualizar_info_empresa(empresa_id, datos):
    """Actualiza la información de la empresa"""
    with get_conn() as conn:
        # Verificar si ya existe información
        existente = pd.read_sql_query("SELECT * FROM company_info WHERE company_id = ?", conn, params=(empresa_id,))
        if existente.empty:
            # Insertar nueva información
            conn.execute("""
                INSERT INTO company_info (company_id, name, owner, creation_date, phone, email, address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (empresa_id, datos['name'], datos['owner'], datos['creation_date'],
                  datos['phone'], datos['email'], datos['address']))
        else:
            # Actualizar información existente
            conn.execute("""
                UPDATE company_info 
                SET name = ?, owner = ?, creation_date = ?, phone = ?, email = ?, address = ?
                WHERE company_id = ?
            """, (datos['name'], datos['owner'], datos['creation_date'],
                  datos['phone'], datos['email'], datos['address'], empresa_id))
        conn.commit()

def eliminar_datos_empresa(empresa_id):
    """Elimina todos los datos asociados a una empresa"""
    with get_conn() as conn:
        # Eliminar en orden para respetar las foreign keys
        tablas = [
            "fluid_inventory_movements", "company_fluid_tanks", "fuel_logs",
            "maintenance_records", "maintenance_schedules", "machinery",
            "company_settings", "alert_configurations", "company_info"
        ]
        for tabla in tablas:
            try:
                conn.execute(f"DELETE FROM {tabla} WHERE company_id = ?", (empresa_id,))
            except Exception:
                continue  # Algunas tablas pueden no tener company_id
        conn.commit()

def obtener_historial_filtrado(empresa_id, tipo_movimiento, filtro_fluido, rango_fechas):
    """Obtiene el historial de movimientos filtrado"""
    with get_conn() as conn:
        query = """
            SELECT 
                fim.movement_type as Tipo,
                ft.name as Fluido,
                fim.quantity as Cantidad,
                cft.unit as Unidad,
                m.name as Maquina,
                fim.supplier as Proveedor,
                fim.operator as Operador,
                fim.created_at as Fecha
            FROM fluid_inventory_movements fim
            JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
            JOIN fluid_types ft ON cft.fluid_type_id = ft.id
            LEFT JOIN machinery m ON fim.machinery_id = m.id
            WHERE cft.company_id = ?
        """
        params = [empresa_id]
        # Aplicar filtros
        if tipo_movimiento != "Todos":
            query += " AND fim.movement_type = ?"
            params.append(tipo_movimiento)
        if filtro_fluido != "Todos":
            query += " AND ft.name = ?"
            params.append(filtro_fluido)
        if len(rango_fechas) == 2:
            query += " AND DATE(fim.created_at) BETWEEN ? AND ?"
            params.extend([rango_fechas[0].isoformat(), rango_fechas[1].isoformat()])
        query += " ORDER BY fim.created_at DESC"
        return pd.read_sql_query(query, conn, params=params)

def auto_migrate():
    """Ejecuta migraciones automáticamente al iniciar"""
    try:
        migrate_database()
        init_additional_tables()  # Esta es la función que acabamos de agregar
        print("✅ Auto-migración completada")
        return True
    except Exception as e:
        print(f"❌ Error en auto-migración: {e}")
        return False
    
def update_machine_hours(machinery_id, new_hours, updated_by="admin"):
    """Actualiza las horas de trabajo de una máquina de forma segura"""
    try:
        with get_conn() as conn:
            # Verificar que las nuevas horas sean mayores que las actuales
            current = pd.read_sql_query("SELECT current_hours FROM machinery WHERE id = ?", 
                                      conn, params=(machinery_id,))
            if not current.empty and new_hours >= current.iloc[0]['current_hours']:
                conn.execute("UPDATE machinery SET current_hours = ? WHERE id = ?", 
                           (new_hours, machinery_id))
                
                # Registrar en log de horas
                conn.execute("""
                    INSERT INTO hour_meter_logs (machinery_id, current_hours, recorded_by)
                    VALUES (?, ?, ?)
                """, (machinery_id, new_hours, updated_by))
                
                conn.commit()
                return True
            return False
    except Exception as e:
        print(f"Error updating hours: {e}")
        return False

def update_machine_km(machinery_id, new_km, updated_by="admin"):
    """Actualiza los kilómetros de una máquina de forma segura"""
    try:
        with get_conn() as conn:
            # Verificar que los nuevos km sean mayores que los actuales
            current = pd.read_sql_query("SELECT current_km FROM machinery WHERE id = ?", 
                                      conn, params=(machinery_id,))
            if not current.empty and new_km >= current.iloc[0]['current_km']:
                conn.execute("UPDATE machinery SET current_km = ? WHERE id = ?", 
                           (new_km, machinery_id))
                
                # Registrar en log de km
                conn.execute("""
                    INSERT INTO odometer_logs (machinery_id, current_km, recorded_by)
                    VALUES (?, ?, ?)
                """, (machinery_id, new_km, updated_by))
                
                conn.commit()
                return True
            return False
    except Exception as e:
        print(f"Error updating km: {e}")
        return False

def get_machine_current_values(machine_id):
    """Obtiene los valores actuales de horómetro y odómetro de forma segura"""
    try:
        with get_conn() as conn:
            # Consultar tabla machinery para los valores actuales
            query = """
                SELECT 
                    COALESCE(current_hours, 0) as current_hours,
                    COALESCE(current_odometer, 0) as current_odometer,
                    COALESCE(status, 'Activa') as status
                FROM machinery 
                WHERE id = ?
            """
            
            result = conn.execute(query, (machine_id,)).fetchone()
            
            if result:
                return {
                    'current_hours': float(result[0]),
                    'current_odometer': float(result[1]),
                    'status': result[2]
                }
            else:
                return {
                    'current_hours': 0.0,
                    'current_odometer': 0.0,
                    'status': 'Activa'
                }
    except Exception as e:
        print(f"Error obteniendo valores actuales: {e}")
        return {
            'current_hours': 0.0,
            'current_odometer': 0.0,
            'status': 'Activa'
        }
    
def verify_database_tables():
    """Verifica que todas las tablas necesarias existan en la base de datos"""
    required_tables = [
        'companies', 'machinery', 'fuel_logs', 'machine_classifications',
        'deletion_logs', 'machinery_deletion_logs', 'maintenance_types',
        'maintenance_schedules', 'maintenance_records', 'status_change_reasons',
        'status_history', 'alert_configurations', 'hour_meter_logs',
        'odometer_logs', 'fluid_types', 'company_fluid_tanks',
        'fluid_inventory_movements', 'tank_refill_logs', 'company_settings',
        'company_info'
    ]
    
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [table[0] for table in cur.fetchall()]
            
            missing_tables = []
            for table in required_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
            
            if missing_tables:
                print(f"❌ Tablas faltantes: {missing_tables}")
                return False
            else:
                print("✅ Todas las tablas existen en la base de datos")
                return True
                
    except Exception as e:
        print(f"❌ Error al verificar tablas: {e}")
        return False

def update_machine_odometer(machine_id, new_odometer, updated_by="admin"):
    """Versión corregida para actualizar odómetro"""
    def _update_operation():
        with get_conn() as conn:
            # Usar una sola transacción para ambas operaciones
            cursor = conn.cursor()
            # Obtener valor actual
            cursor.execute("SELECT current_odometer FROM machinery WHERE id = ?", (machine_id,))
            result = cursor.fetchone()
            current_odometer = result[0] if result else 0
            # Validar que el nuevo valor sea mayor o igual
            if new_odometer < current_odometer:
                raise ValueError(f"El nuevo odómetro ({new_odometer}) debe ser mayor o igual al actual ({current_odometer})")
            # Actualizar en una sola transacción
            cursor.execute("""
                UPDATE machinery 
                SET current_odometer = ?, last_odometer_update = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (new_odometer, machine_id))
            # Registrar en log
            cursor.execute("""
                INSERT INTO odometer_logs (machinery_id, current_odometer, recorded_by, recorded_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (machine_id, new_odometer, updated_by))
            conn.commit()
            return True
    try:
        return safe_execute_with_retry(_update_operation)
    except Exception as e:
        print(f"Error actualizando odómetro: {str(e)}")
        return False
    
# Agregar a db_utils.py si no existe:
def get_machine_maintenance_intervals(machine_id, maintenance_type_id):
    """Obtiene intervalos específicos de una máquina"""
    # Implementación similar a get_machine_current_values

# Extensión de compatibilidad de estados para db_utils.py
# Agregar estas funciones al final de tu db_utils.py

import sqlite3
import pandas as pd

# Diccionarios de mapeo de estados
STATUS_MAPPING_TO_ENGLISH = {
    'Activa': 'Active',
    'Activo': 'Active', 
    'Active': 'Active',
    'Mantenimiento': 'Maintenance',
    'Maintenance': 'Maintenance',
    'Mant.': 'Maintenance',
    'En Mantenimiento': 'Maintenance',
    'Inactiva': 'Inactive',
    'Inactivo': 'Inactive',
    'Inactive': 'Inactive',
    'Fuera de Servicio': 'Inactive',
    'No Operativa': 'Inactive',
    'Parada': 'Inactive',
    '': 'Active',  # Estado por defecto
    None: 'Active'  # Estado por defecto
}

STATUS_MAPPING_TO_SPANISH = {
    'Active': 'Activa',
    'Activa': 'Activa',
    'Activo': 'Activa',
    'Maintenance': 'Mantenimiento',
    'Mantenimiento': 'Mantenimiento',
    'Mant.': 'Mantenimiento',
    'En Mantenimiento': 'Mantenimiento',
    'Inactive': 'Inactiva',
    'Inactiva': 'Inactiva',
    'Inactivo': 'Inactiva',
    'Fuera de Servicio': 'Inactiva',
    'No Operativa': 'Inactiva',
    'Parada': 'Inactiva',
    '': 'Activa',  # Estado por defecto
    None: 'Activa'  # Estado por defecto
}

def normalize_status_to_english(status):
    """Convierte cualquier estado a formato inglés estándar"""
    if pd.isna(status) or status is None:
        return 'Active'
    
    status_str = str(status).strip()
    return STATUS_MAPPING_TO_ENGLISH.get(status_str, 'Active')

def normalize_status_to_spanish(status):
    """Convierte cualquier estado a formato español estándar"""
    if pd.isna(status) or status is None:
        return 'Activa'
    
    status_str = str(status).strip()
    return STATUS_MAPPING_TO_SPANISH.get(status_str, 'Activa')

def get_status_variants(status):
    """Obtiene todas las variantes posibles de un estado para consultas OR"""
    status_variants = {
        'Active': ['Active', 'Activa', 'Activo'],
        'Maintenance': ['Maintenance', 'Mantenimiento', 'Mant.', 'En Mantenimiento'],
        'Inactive': ['Inactive', 'Inactiva', 'Inactivo', 'Fuera de Servicio', 'No Operativa', 'Parada']
    }
    
    normalized = normalize_status_to_english(status)
    return status_variants.get(normalized, [status])

def migrate_status_standardization():
    """Migra todos los estados de maquinaria a formato estándar inglés"""
    try:
        with get_conn() as conn:
            # Obtener todos los estados actuales
            current_statuses = pd.read_sql_query("""
                SELECT DISTINCT status FROM machinery WHERE status IS NOT NULL
            """, conn)
            
            print("Estados encontrados en la base de datos:")
            for status in current_statuses['status']:
                normalized = normalize_status_to_english(status)
                print(f"  '{status}' -> '{normalized}'")
            
            # Actualizar todos los estados a formato inglés estándar
            updates = []
            for status in current_statuses['status']:
                normalized = normalize_status_to_english(status)
                if status != normalized:
                    updates.append((normalized, status))
            
            # Ejecutar actualizaciones
            for normalized, original in updates:
                conn.execute("""
                    UPDATE machinery SET status = ? WHERE status = ?
                """, (normalized, original))
                print(f"  Actualizados registros: '{original}' -> '{normalized}'")
            
            conn.commit()
            print(f"✅ Migración completada. {len(updates)} tipos de estado normalizados.")
            return True
            
    except Exception as e:
        print(f"❌ Error en migración de estados: {e}")
        return False

def list_machinery_with_status_normalization(company_id, normalize_to='english'):
    """Versión mejorada de list_machinery que normaliza estados"""
    try:
        with get_conn() as conn:
            machinery_df = pd.read_sql_query(
                "SELECT * FROM machinery WHERE company_id = ? ORDER BY name", 
                conn, 
                params=(company_id,)
            )
            
            if not machinery_df.empty:
                # Normalizar estados según el formato solicitado
                if normalize_to == 'english':
                    machinery_df['status'] = machinery_df['status'].apply(normalize_status_to_english)
                else:
                    machinery_df['status'] = machinery_df['status'].apply(normalize_status_to_spanish)
                
                # También normalizar estados de columnas que puedan tener estados
                for col in machinery_df.columns:
                    if 'status' in col.lower():
                        if normalize_to == 'english':
                            machinery_df[col] = machinery_df[col].apply(normalize_status_to_english)
                        else:
                            machinery_df[col] = machinery_df[col].apply(normalize_status_to_spanish)
            
            return machinery_df
            
    except Exception as e:
        print(f"Error in list_machinery_with_normalization: {e}")
        return pd.DataFrame()

def update_machinery_status_compatible(machinery_id, new_status, updated_by="admin", notes=None):
    """Actualiza el estado de una máquina con normalización automática"""
    try:
        # Normalizar el estado a formato estándar inglés para la base de datos
        normalized_status = normalize_status_to_english(new_status)
        
        with get_conn() as conn:
            # Obtener estado actual
            current_result = pd.read_sql_query("""
                SELECT status FROM machinery WHERE id = ?
            """, conn, params=(machinery_id,))
            
            if current_result.empty:
                return False, "Máquina no encontrada"
            
            current_status = normalize_status_to_english(current_result.iloc[0]['status'])
            
            # Solo actualizar si hay cambio
            if current_status != normalized_status:
                # Actualizar estado
                conn.execute("""
                    UPDATE machinery 
                    SET status = ?, last_status_change = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (normalized_status, machinery_id))
                
                # Registrar cambio si existe la tabla status_history
                try:
                    conn.execute("""
                        INSERT INTO status_history 
                        (machinery_id, previous_status, new_status, changed_by, notes, changed_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (machinery_id, current_status, normalized_status, updated_by, notes))
                except sqlite3.OperationalError:
                    # La tabla status_history puede no existir en versiones básicas
                    pass
                
                conn.commit()
                return True, f"Estado actualizado de '{current_status}' a '{normalized_status}'"
            else:
                return True, "Estado sin cambios"
                
    except Exception as e:
        return False, f"Error actualizando estado: {str(e)}"

def get_machinery_by_status_flexible(company_id, status_filter=None, normalize_to='english'):
    """Obtiene maquinaria filtrando por estado de manera flexible"""
    try:
        with get_conn() as conn:
            base_query = """
                SELECT * FROM machinery WHERE company_id = ?
            """
            params = [company_id]
            
            if status_filter:
                # Obtener todas las variantes del estado para búsqueda flexible
                status_variants = get_status_variants(status_filter)
                placeholders = ','.join(['?' for _ in status_variants])
                base_query += f" AND status IN ({placeholders})"
                params.extend(status_variants)
            
            base_query += " ORDER BY name"
            
            machinery_df = pd.read_sql_query(base_query, conn, params=params)
            
            # Normalizar estados en el resultado
            if not machinery_df.empty:
                if normalize_to == 'english':
                    machinery_df['status'] = machinery_df['status'].apply(normalize_status_to_english)
                else:
                    machinery_df['status'] = machinery_df['status'].apply(normalize_status_to_spanish)
            
            return machinery_df
            
    except Exception as e:
        print(f"Error getting machinery by status: {e}")
        return pd.DataFrame()

def get_active_machinery_compatible(company_id, normalize_to='english'):
    """Obtiene solo la maquinaria activa con compatibilidad de estados"""
    return get_machinery_by_status_flexible(company_id, 'Active', normalize_to)

def get_machinery_status_summary_compatible(company_id):
    """Obtiene resumen de estados de maquinaria con normalización"""
    try:
        with get_conn() as conn:
            # Obtener todos los estados y normalizarlos
            machinery_df = pd.read_sql_query("""
                SELECT id, name, identifier, status FROM machinery WHERE company_id = ?
            """, conn, params=(company_id,))
            
            if machinery_df.empty:
                return {
                    'total': 0,
                    'active': 0, 
                    'maintenance': 0,
                    'inactive': 0,
                    'details': []
                }
            
            # Normalizar estados
            machinery_df['normalized_status'] = machinery_df['status'].apply(normalize_status_to_english)
            
            # Contar por estado normalizado
            status_counts = machinery_df['normalized_status'].value_counts()
            
            summary = {
                'total': len(machinery_df),
                'active': status_counts.get('Active', 0),
                'maintenance': status_counts.get('Maintenance', 0),
                'inactive': status_counts.get('Inactive', 0),
                'details': []
            }
            
            # Agregar detalles por máquina
            for _, machine in machinery_df.iterrows():
                summary['details'].append({
                    'id': machine['id'],
                    'name': machine['name'],
                    'identifier': machine.get('identifier', ''),
                    'original_status': machine['status'],
                    'normalized_status': machine['normalized_status']
                })
            
            return summary
            
    except Exception as e:
        print(f"Error getting status summary: {e}")
        return {'total': 0, 'active': 0, 'maintenance': 0, 'inactive': 0, 'details': []}

def verify_status_compatibility():
    """Verifica la compatibilidad de estados en la base de datos"""
    try:
        with get_conn() as conn:
            # Obtener todos los estados únicos
            unique_statuses = pd.read_sql_query("""
                SELECT DISTINCT status, COUNT(*) as count
                FROM machinery 
                WHERE status IS NOT NULL
                GROUP BY status
                ORDER BY count DESC
            """, conn)
            
            print("=== VERIFICACIÓN DE COMPATIBILIDAD DE ESTADOS ===")
            print("\nEstados encontrados en la base de datos:")
            
            compatibility_issues = []
            
            for _, row in unique_statuses.iterrows():
                original = row['status']
                normalized = normalize_status_to_english(original)
                count = row['count']
                
                if original != normalized:
                    compatibility_issues.append({
                        'original': original,
                        'normalized': normalized,
                        'count': count
                    })
                    print(f"  ⚠️  '{original}' -> '{normalized}' ({count} registros)")
                else:
                    print(f"  ✅  '{original}' (ya normalizado, {count} registros)")
            
            if compatibility_issues:
                print(f"\n❌ Se encontraron {len(compatibility_issues)} tipos de estado que necesitan normalización.")
                print("Ejecuta migrate_status_standardization() para corregir automáticamente.")
            else:
                print("\n✅ Todos los estados están en formato estándar.")
            
            return len(compatibility_issues) == 0
            
    except Exception as e:
        print(f"❌ Error verificando compatibilidad: {e}")
        return False

def setup_status_compatibility_triggers():
    """Configura triggers para mantener compatibilidad automática (opcional)"""
    try:
        with get_conn() as conn:
            # Trigger para normalizar estados automáticamente en INSERT
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS normalize_status_on_insert
                AFTER INSERT ON machinery
                WHEN NEW.status IS NOT NULL
                BEGIN
                    UPDATE machinery 
                    SET status = CASE 
                        WHEN NEW.status IN ('Activa', 'Activo') THEN 'Active'
                        WHEN NEW.status IN ('Mantenimiento', 'Mant.', 'En Mantenimiento') THEN 'Maintenance'
                        WHEN NEW.status IN ('Inactiva', 'Inactivo', 'Fuera de Servicio', 'Parada') THEN 'Inactive'
                        ELSE 'Active'
                    END
                    WHERE id = NEW.id AND status != CASE 
                        WHEN NEW.status IN ('Activa', 'Activo') THEN 'Active'
                        WHEN NEW.status IN ('Mantenimiento', 'Mant.', 'En Mantenimiento') THEN 'Maintenance'
                        WHEN NEW.status IN ('Inactiva', 'Inactivo', 'Fuera de Servicio', 'Parada') THEN 'Inactive'
                        ELSE 'Active'
                    END;
                END;
            """)
            
            # Trigger para normalizar estados automáticamente en UPDATE
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS normalize_status_on_update
                AFTER UPDATE OF status ON machinery
                WHEN NEW.status IS NOT NULL
                BEGIN
                    UPDATE machinery 
                    SET status = CASE 
                        WHEN NEW.status IN ('Activa', 'Activo') THEN 'Active'
                        WHEN NEW.status IN ('Mantenimiento', 'Mant.', 'En Mantenimiento') THEN 'Maintenance'
                        WHEN NEW.status IN ('Inactiva', 'Inactivo', 'Fuera de Servicio', 'Parada') THEN 'Inactive'
                        ELSE 'Active'
                    END
                    WHERE id = NEW.id AND status != CASE 
                        WHEN NEW.status IN ('Activa', 'Activo') THEN 'Active'
                        WHEN NEW.status IN ('Mantenimiento', 'Mant.', 'En Mantenimiento') THEN 'Maintenance'
                        WHEN NEW.status IN ('Inactiva', 'Inactivo', 'Fuera de Servicio', 'Parada') THEN 'Inactive'
                        ELSE 'Active'
                    END;
                END;
            """)
            
            conn.commit()
            print("✅ Triggers de compatibilidad configurados correctamente")
            return True
            
    except Exception as e:
        print(f"❌ Error configurando triggers: {e}")
        return False

# Función de conveniencia para módulos externos
def get_machinery_for_controls(company_id):
    """Función específica para el módulo de controles que garantiza formato compatible"""
    return get_active_machinery_compatible(company_id, normalize_to='english')

def get_machinery_for_maintenance(company_id):
    """Función específica para el módulo de mantenimiento"""
    return list_machinery_with_status_normalization(company_id, normalize_to='spanish')

# Auto-ejecutar verificación al importar (opcional)
def auto_setup_status_compatibility():
    """Configuración automática de compatibilidad de estados"""
    try:
        print("Configurando compatibilidad de estados...")
        
        # Verificar compatibilidad actual
        is_compatible = verify_status_compatibility()
        
        if not is_compatible:
            print("Aplicando migración automática...")
            migrate_status_standardization()
        
        # Configurar triggers (opcional)
        # setup_status_compatibility_triggers()
        
        print("✅ Compatibilidad de estados configurada")
        return True
        
    except Exception as e:
        print(f"❌ Error en configuración automática: {e}")
        return False
    
# Al final de tu db_utils.py, agrega:
if __name__ == "__main__":
    auto_setup_status_compatibility()

def normalize_machinery_status(status):
    """
    Normaliza los estados de maquinaria para compatibilidad entre módulos
    Convierte estados en español/inglés a un formato estándar
    """
    if not status:
        return 'Active'  # Por defecto
    
    status = str(status).strip()
    
    # Mapeo de estados
    status_mapping = {
        # Estados en español (mantenimiento)
        'Activa': 'Active',
        'Activo': 'Active', 
        'Inactiva': 'Inactive',
        'Inactivo': 'Inactive',
        'Mantenimiento': 'Maintenance',
        
        # Estados en inglés (controles)
        'Active': 'Active',
        'Inactive': 'Inactive', 
        'Maintenance': 'Maintenance',
        
        # Variaciones comunes
        'ACTIVE': 'Active',
        'INACTIVE': 'Inactive',
        'MAINTENANCE': 'Maintenance',
        'activa': 'Active',
        'inactiva': 'Inactive',
        'mantenimiento': 'Maintenance'
    }
    
    return status_mapping.get(status, 'Active')

def get_machinery_for_controls_compatible(company_id):
    """
    Versión compatible de get_machinery_for_controls que maneja estados en español/inglés
    """
    try:
        with get_conn() as conn:
            # Obtener toda la maquinaria de la empresa
            query = """
                SELECT id, name, identifier, classification, status, 
                       COALESCE(consumption_per_hour, 0) as consumption_per_hour,
                       COALESCE(current_hours, 0) as current_hours,
                       COALESCE(current_odometer, 0) as current_odometer
                FROM machinery 
                WHERE company_id = ?
                ORDER BY name
            """
            
            df = pd.read_sql_query(query, conn, params=(company_id,))
            
            if df.empty:
                return df
            
            # Normalizar estados
            df['normalized_status'] = df['status'].apply(normalize_machinery_status)
            
            # Filtrar solo las activas para controles
            active_machinery = df[df['normalized_status'] == 'Active'].copy()
            
            return active_machinery
            
    except Exception as e:
        print(f"Error obteniendo maquinaria compatible: {e}")
        return pd.DataFrame()

def get_machinery_with_normalized_status(company_id, status_filter=None):
    """
    Obtiene maquinaria con estados normalizados, opcionalmente filtrada por estado
    """
    try:
        with get_conn() as conn:
            query = """
                SELECT id, name, identifier, classification, status,
                       COALESCE(current_hours, 0) as current_hours,
                       COALESCE(current_odometer, 0) as current_odometer,
                       last_maintenance_date, last_status_change
                FROM machinery 
                WHERE company_id = ?
                ORDER BY name
            """
            
            df = pd.read_sql_query(query, conn, params=(company_id,))
            
            if df.empty:
                return df
            
            # Agregar columna con estado normalizado
            df['normalized_status'] = df['status'].apply(normalize_machinery_status)
            
            # Filtrar por estado si se especifica
            if status_filter:
                normalized_filter = normalize_machinery_status(status_filter)
                df = df[df['normalized_status'] == normalized_filter]
            
            return df
            
    except Exception as e:
        print(f"Error obteniendo maquinaria con estados normalizados: {e}")
        return pd.DataFrame()

def update_machinery_status_compatible(machinery_id, new_status, user="admin"):
    """
    Actualiza el estado de una máquina manteniendo compatibilidad
    Acepta estados en español o inglés y los normaliza
    """
    try:
        normalized_status = normalize_machinery_status(new_status)
        
        # Convertir de vuelta al formato que use cada módulo
        # Para mantenimiento (español)
        spanish_status_mapping = {
            'Active': 'Activa',
            'Inactive': 'Inactiva', 
            'Maintenance': 'Mantenimiento'
        }
        
        # Usar el estado normalizado en inglés por defecto
        # pero podríamos usar el español si es necesario
        status_to_save = normalized_status  # o spanish_status_mapping.get(normalized_status, normalized_status)
        
        with get_conn() as conn:
            conn.execute("""
                UPDATE machinery 
                SET status = ?, last_status_change = ?
                WHERE id = ?
            """, (status_to_save, datetime.now().isoformat(), machinery_id))
            
            conn.commit()
            return True, f"Estado actualizado a {status_to_save}"
            
    except Exception as e:
        return False, f"Error actualizando estado: {str(e)}"

def get_localized_status_display(status, locale='es'):
    """
    Convierte estados normalizados a formato de visualización según idioma
    """
    if locale == 'es':
        display_mapping = {
            'Active': 'Activa',
            'Inactive': 'Inactiva',
            'Maintenance': 'Mantenimiento'
        }
    else:  # inglés por defecto
        display_mapping = {
            'Active': 'Active',
            'Inactive': 'Inactive', 
            'Maintenance': 'Maintenance'
        }
    
    normalized = normalize_machinery_status(status)
    return display_mapping.get(normalized, normalized)

def create_maintenance_compliance_table():
    """Crea la tabla de log de cumplimiento de mantenimientos"""
    try:
        with get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_compliance_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scheduled_maintenance_id INTEGER,
                    action_type TEXT NOT NULL,
                    execution_date TEXT NOT NULL,
                    reason TEXT,
                    notes TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (scheduled_maintenance_id) REFERENCES maintenance_schedules(id) ON DELETE CASCADE
                )
            """)
            conn.commit()
            return True
    except Exception as e:
        print(f"Error creating compliance table: {e}")
        return False

def log_maintenance_compliance(scheduled_id, action_type, reason=None, notes=None, created_by="admin"):
    """Registra el cumplimiento o incumplimiento de un mantenimiento programado"""
    try:
        create_maintenance_compliance_table()
        
        with get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO maintenance_compliance_log 
                (scheduled_maintenance_id, action_type, execution_date, reason, notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (scheduled_id, action_type, datetime.now().isoformat(), reason, notes, created_by))
            
            log_id = cursor.lastrowid
            conn.commit()
            return log_id
            
    except Exception as e:
        print(f"Error logging compliance: {e}")
        return None

def get_upcoming_scheduled_maintenances(empresa_id, days_ahead=7):
    """Obtiene mantenimientos programados próximos a vencer"""
    try:
        with get_conn() as conn:
            query = """
            SELECT 
                ms.id,
                m.name as vehiculo,
                COALESCE(m.identifier, 'N/A') as identifier,
                mt.name as tipo_mantenimiento,
                ms.scheduled_start_date,
                ms.scheduled_end_date,
                ms.description,
                ms.responsible_person,
                ms.priority,
                ms.status,
                CAST((julianday(ms.scheduled_start_date) - julianday('now')) AS INTEGER) as dias_restantes
            FROM maintenance_schedules ms
            JOIN machinery m ON ms.machinery_id = m.id
            JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
            WHERE m.company_id = ?
            AND ms.status = 'PROGRAMADO'
            AND date(ms.scheduled_start_date) BETWEEN date('now') AND date('now', '+' || ? || ' days')
            ORDER BY ms.scheduled_start_date ASC
            """
            
            return pd.read_sql_query(query, conn, params=(empresa_id, days_ahead))
            
    except Exception as e:
        print(f"Error getting upcoming maintenances: {e}")
        return pd.DataFrame()

def get_overdue_scheduled_maintenances(empresa_id):
    """Obtiene mantenimientos programados vencidos"""
    try:
        with get_conn() as conn:
            query = """
            SELECT 
                ms.id,
                m.name as vehiculo,
                COALESCE(m.identifier, 'N/A') as identifier,
                mt.name as tipo_mantenimiento,
                ms.scheduled_start_date,
                ms.scheduled_end_date,
                ms.description,
                ms.responsible_person,
                ms.priority,
                ms.status,
                CAST((julianday('now') - julianday(ms.scheduled_start_date)) AS INTEGER) as dias_vencido
            FROM maintenance_schedules ms
            JOIN machinery m ON ms.machinery_id = m.id
            JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
            WHERE m.company_id = ?
            AND ms.status = 'PROGRAMADO'
            AND date(ms.scheduled_start_date) < date('now')
            ORDER BY ms.scheduled_start_date ASC
            """
            
            return pd.read_sql_query(query, conn, params=(empresa_id,))
            
    except Exception as e:
        print(f"Error getting overdue maintenances: {e}")
        return pd.DataFrame()

def get_compliance_log(empresa_id, fecha_inicio=None, fecha_fin=None):
    """Obtiene el log de cumplimiento de mantenimientos"""
    try:
        with get_conn() as conn:
            where_clause = "WHERE m.company_id = ?"
            params = [empresa_id]
            
            if fecha_inicio:
                where_clause += " AND date(mcl.execution_date) >= ?"
                params.append(fecha_inicio)
            
            if fecha_fin:
                where_clause += " AND date(mcl.execution_date) <= ?"
                params.append(fecha_fin)
            
            query = f"""
            SELECT 
                mcl.id,
                m.name as vehiculo,
                COALESCE(m.identifier, 'N/A') as identifier,
                mt.name as tipo_mantenimiento,
                ms.scheduled_start_date as fecha_programada,
                mcl.execution_date as fecha_accion,
                mcl.action_type as accion,
                mcl.reason as motivo,
                mcl.notes as notas,
                mcl.created_by as registrado_por,
                mcl.created_at
            FROM maintenance_compliance_log mcl
            JOIN maintenance_schedules ms ON mcl.scheduled_maintenance_id = ms.id
            JOIN machinery m ON ms.machinery_id = m.id
            JOIN maintenance_types mt ON ms.maintenance_type_id = mt.id
            {where_clause}
            ORDER BY mcl.created_at DESC
            """
            
            return pd.read_sql_query(query, conn, params=params)
            
    except Exception as e:
        print(f"Error getting compliance log: {e}")
        return pd.DataFrame()

def update_scheduled_maintenance_status(scheduled_id, new_status):
    """Actualiza el estado de un mantenimiento programado"""
    try:
        with get_conn() as conn:
            conn.execute("""
                UPDATE maintenance_schedules 
                SET status = ?
                WHERE id = ?
            """, (new_status, scheduled_id))
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Error updating scheduled maintenance status: {e}")
        return False
    
def ensure_fluid_types_exist():
    """Asegura que los tipos de fluidos básicos existan"""
    try:
        with get_conn() as conn:
            # Verificar si existen tipos de fluidos
            existing = pd.read_sql_query("SELECT COUNT(*) as count FROM fluid_types", conn)
            if existing.iloc[0]['count'] == 0:
                # Crear tipos básicos
                default_fluids = [
                    ("Combustible", "volume"),
                    ("Aceite", "volume"), 
                    ("Grasa", "volume"),
                    ("Coolant", "volume")
                ]
                for name, unit_type in default_fluids:
                    conn.execute("""
                        INSERT OR IGNORE INTO fluid_types (name, unit_type) 
                        VALUES (?, ?)
                    """, (name, unit_type))
                conn.commit()
        return True
    except Exception as e:
        print(f"Error ensuring fluid types: {e}")
        return False

def get_fluid_types():
    """Obtiene todos los tipos de fluidos disponibles - COMPATIBLE CON CONTROLES"""
    try:
        ensure_fluid_types_exist()
        with get_conn() as conn:
            return pd.read_sql_query("SELECT * FROM fluid_types ORDER BY name", conn)
    except Exception as e:
        print(f"Error getting fluid types: {e}")
        return pd.DataFrame()

def get_company_tanks(empresa_id):
    """Obtiene tanques de una empresa - COMPATIBLE CON CONTROLES"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT cft.id, cft.tank_capacity, cft.current_level, cft.unit,
                       ft.name as fluid_name, ft.id as fluid_type_id
                FROM company_fluid_tanks cft
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ?
                ORDER BY ft.name
            """, conn, params=(empresa_id,))
    except Exception as e:
        print(f"Error getting company tanks: {e}")
        return pd.DataFrame()

def create_company_tank(empresa_id, fluid_type_id, capacidad, unidad='galones'):
    """Crea un tanque específico para una empresa"""
    try:
        with get_conn() as conn:
            # Verificar que no existe ya
            existing = pd.read_sql_query("""
                SELECT id FROM company_fluid_tanks 
                WHERE company_id = ? AND fluid_type_id = ?
            """, conn, params=(empresa_id, fluid_type_id))
            
            if not existing.empty:
                return False, "Ya existe un tanque de este tipo para esta empresa"
            
            # Verificar que el fluid_type_id existe
            fluid_check = pd.read_sql_query("""
                SELECT name FROM fluid_types WHERE id = ?
            """, conn, params=(fluid_type_id,))
            
            if fluid_check.empty:
                return False, "Tipo de fluido no válido"
            
            # Crear tanque
            conn.execute("""
                INSERT INTO company_fluid_tanks 
                (company_id, fluid_type_id, tank_capacity, current_level, unit)
                VALUES (?, ?, ?, 0.0, ?)
            """, (empresa_id, fluid_type_id, capacidad, unidad))
            conn.commit()
            
            fluid_name = fluid_check.iloc[0]['name']
            return True, f"Tanque de {fluid_name} creado exitosamente"
    except Exception as e:
        return False, f"Error creando tanque: {str(e)}"

def delete_company_tank(empresa_id, tank_id):
    """Elimina un tanque de una empresa (solo si está vacío)"""
    try:
        with get_conn() as conn:
            # Verificar que el tanque pertenece a la empresa
            tank_info = pd.read_sql_query("""
                SELECT cft.current_level, ft.name as fluid_name
                FROM company_fluid_tanks cft
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.id = ? AND cft.company_id = ?
            """, conn, params=(tank_id, empresa_id))
            
            if tank_info.empty:
                return False, "Tanque no encontrado o no pertenece a esta empresa"
            
            tank = tank_info.iloc[0]
            
            if tank['current_level'] > 0:
                return False, f"No se puede eliminar el tanque de {tank['fluid_name']} porque tiene {tank['current_level']:.1f} unidades"
            
            # Verificar que no tenga movimientos
            movements = pd.read_sql_query("""
                SELECT COUNT(*) as count FROM fluid_inventory_movements 
                WHERE tank_id = ?
            """, conn, params=(tank_id,))
            
            if movements.iloc[0]['count'] > 0:
                return False, f"No se puede eliminar el tanque de {tank['fluid_name']} porque tiene historial de movimientos"
            
            # Eliminar tanque
            conn.execute("""
                DELETE FROM company_fluid_tanks 
                WHERE id = ? AND company_id = ?
            """, (tank_id, empresa_id))
            conn.commit()
            return True, f"Tanque de {tank['fluid_name']} eliminado exitosamente"
    except Exception as e:
        return False, f"Error eliminando tanque: {str(e)}"

def get_available_fluid_types_for_company(empresa_id):
    """Obtiene tipos de fluidos que la empresa AÚN NO tiene como tanques"""
    try:
        ensure_fluid_types_exist()
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT ft.id, ft.name, ft.unit_type
                FROM fluid_types ft
                WHERE ft.id NOT IN (
                    SELECT DISTINCT fluid_type_id 
                    FROM company_fluid_tanks 
                    WHERE company_id = ?
                )
                ORDER BY ft.name
            """, conn, params=(empresa_id,))
    except Exception as e:
        print(f"Error getting available fluid types: {e}")
        return pd.DataFrame()

def verify_company_tank_integrity(empresa_id):
    """Verifica la integridad de los tanques de una empresa"""
    issues = []
    try:
        with get_conn() as conn:
            # Verificar tanques huérfanos (sin fluid_type válido)
            orphaned_tanks = pd.read_sql_query("""
                SELECT cft.id, cft.fluid_type_id
                FROM company_fluid_tanks cft
                LEFT JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ? AND ft.id IS NULL
            """, conn, params=(empresa_id,))
            
            for _, tank in orphaned_tanks.iterrows():
                issues.append(f"Tanque ID {tank['id']} tiene fluid_type_id inválido: {tank['fluid_type_id']}")
            
            # Verificar tanques duplicados
            duplicates = pd.read_sql_query("""
                SELECT fluid_type_id, COUNT(*) as count
                FROM company_fluid_tanks
                WHERE company_id = ?
                GROUP BY fluid_type_id
                HAVING COUNT(*) > 1
            """, conn, params=(empresa_id,))
            
            for _, dup in duplicates.iterrows():
                issues.append(f"Tipo de fluido {dup['fluid_type_id']} tiene {dup['count']} tanques (debería ser 1)")
            
            # Verificar niveles negativos
            negative_levels = pd.read_sql_query("""
                SELECT cft.id, ft.name, cft.current_level
                FROM company_fluid_tanks cft
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ? AND cft.current_level < 0
            """, conn, params=(empresa_id,))
            
            for _, tank in negative_levels.iterrows():
                issues.append(f"Tanque de {tank['name']} tiene nivel negativo: {tank['current_level']}")
            
    except Exception as e:
        issues.append(f"Error verificando integridad: {str(e)}")
    
    return issues

# FUNCIONES ADICIONALES PARA db_utils.py
# Agregar al final de tu archivo db_utils.py

# ============================================
# FUNCIONES DE COMPATIBILIDAD ENTRE MÓDULOS
# ============================================

def get_company_fluid_summary(empresa_id):
    """Obtiene resumen de fluidos para otros módulos (mantenimiento, reportes, etc.)"""
    try:
        with get_conn() as conn:
            summary = pd.read_sql_query("""
                SELECT 
                    ft.name as fluid_name,
                    cft.tank_capacity,
                    cft.current_level,
                    cft.unit,
                    ROUND((cft.current_level / cft.tank_capacity * 100), 2) as percentage_full,
                    CASE 
                        WHEN (cft.current_level / cft.tank_capacity * 100) >= 70 THEN 'OK'
                        WHEN (cft.current_level / cft.tank_capacity * 100) >= 40 THEN 'LOW'
                        ELSE 'CRITICAL'
                    END as status,
                    cft.id as tank_id
                FROM company_fluid_tanks cft
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ?
                ORDER BY ft.name
            """, conn, params=(empresa_id,))
            
            return summary
            
    except Exception as e:
        print(f"Error getting fluid summary: {e}")
        return pd.DataFrame()

def get_machinery_fuel_status_for_external(empresa_id):
    """Obtiene estado de combustible de maquinaria para módulos externos"""
    try:
        maquinaria = get_active_machinery_compatible(empresa_id)
        fuel_status_list = []
        
        for _, machine in maquinaria.iterrows():
            try:
                # Intentar obtener estado desde controles
                from controles_module import get_machine_fluid_status, get_company_setting
                
                unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
                # ID 1 = Combustible por defecto
                fuel_status = get_machine_fluid_status(machine['id'], 1, unit_preference)
                
                fuel_status_list.append({
                    'machinery_id': machine['id'],
                    'machinery_name': machine['name'],
                    'identifier': machine.get('identifier', ''),
                    'fuel_level': fuel_status.get('level', 'unknown'),
                    'remaining_hours': fuel_status.get('hours_remaining', 0),
                    'remaining_fuel': fuel_status.get('remaining', 0),
                    'message': fuel_status.get('message', 'Sin datos')
                })
                
            except ImportError:
                # Fallback al sistema legacy
                legacy_status = get_fuel_status_advanced(machine['id'])
                fuel_status_list.append({
                    'machinery_id': machine['id'],
                    'machinery_name': machine['name'],
                    'identifier': machine.get('identifier', ''),
                    'fuel_level': legacy_status.get('status', 'unknown'),
                    'remaining_hours': legacy_status.get('days_remaining', 0) * 24,
                    'remaining_fuel': legacy_status.get('remaining', 0),
                    'message': legacy_status.get('message', 'Sin datos')
                })
                
        return pd.DataFrame(fuel_status_list)
        
    except Exception as e:
        print(f"Error getting machinery fuel status: {e}")
        return pd.DataFrame()

def get_recent_fluid_movements_summary(empresa_id, days=7):
    """Obtiene resumen de movimientos recientes para dashboard principal"""
    try:
        from datetime import date, timedelta
        fecha_limite = (date.today() - timedelta(days=days)).isoformat()
        
        with get_conn() as conn:
            movements = pd.read_sql_query("""
                SELECT 
                    ft.name as fluid_name,
                    fim.movement_type,
                    SUM(fim.quantity) as total_quantity,
                    COUNT(*) as movement_count,
                    cft.unit
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ? AND DATE(fim.created_at) >= ?
                GROUP BY ft.name, fim.movement_type, cft.unit
                ORDER BY ft.name, fim.movement_type
            """, conn, params=(empresa_id, fecha_limite))
            
            return movements
            
    except Exception as e:
        print(f"Error getting recent movements: {e}")
        return pd.DataFrame()

def get_tank_by_fluid_type(empresa_id, fluid_type_name):
    """Obtiene tanque específico por tipo de fluido"""
    try:
        with get_conn() as conn:
            tank = pd.read_sql_query("""
                SELECT cft.*, ft.name as fluid_name
                FROM company_fluid_tanks cft
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ? AND ft.name = ?
            """, conn, params=(empresa_id, fluid_type_name))
            
            return tank.iloc[0] if not tank.empty else None
            
    except Exception as e:
        print(f"Error getting tank by fluid type: {e}")
        return None

def update_tank_level_external(empresa_id, fluid_type_name, new_level):
    """Actualiza nivel de tanque desde módulos externos"""
    try:
        tank = get_tank_by_fluid_type(empresa_id, fluid_type_name)
        if tank is None:
            return False, f"No se encontró tanque de {fluid_type_name}"
        
        if new_level < 0:
            return False, "El nivel no puede ser negativo"
        
        if new_level > tank['tank_capacity']:
            return False, f"El nivel excede la capacidad ({tank['tank_capacity']} {tank['unit']})"
        
        with get_conn() as conn:
            conn.execute("""
                UPDATE company_fluid_tanks 
                SET current_level = ?
                WHERE id = ?
            """, (new_level, tank['id']))
            conn.commit()
            
        return True, f"Nivel actualizado a {new_level} {tank['unit']}"
        
    except Exception as e:
        return False, f"Error actualizando nivel: {str(e)}"

def get_fluid_consumption_by_machine(empresa_id, machine_id, days=30):
    """Obtiene consumo de fluidos por máquina para análisis"""
    try:
        from datetime import date, timedelta
        fecha_limite = (date.today() - timedelta(days=days)).isoformat()
        
        with get_conn() as conn:
            consumption = pd.read_sql_query("""
                SELECT 
                    ft.name as fluid_name,
                    SUM(fim.quantity) as total_consumed,
                    COUNT(*) as refill_count,
                    AVG(fim.quantity) as avg_per_refill,
                    cft.unit,
                    MIN(fim.created_at) as first_refill,
                    MAX(fim.created_at) as last_refill
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE fim.machinery_id = ? 
                AND fim.movement_type = 'SALIDA'
                AND DATE(fim.created_at) >= ?
                GROUP BY ft.name, cft.unit
                ORDER BY total_consumed DESC
            """, conn, params=(machine_id, fecha_limite))
            
            return consumption
            
    except Exception as e:
        print(f"Error getting consumption by machine: {e}")
        return pd.DataFrame()

def check_critical_fluid_levels(empresa_id, threshold=20):
    """Verifica niveles críticos para alertas en otros módulos"""
    try:
        tanks = get_company_tanks(empresa_id)
        critical_tanks = []
        
        for _, tank in tanks.iterrows():
            percentage = (tank['current_level'] / tank['tank_capacity']) * 100
            if percentage <= threshold:
                critical_tanks.append({
                    'tank_id': tank['id'],
                    'fluid_name': tank['fluid_name'],
                    'current_level': tank['current_level'],
                    'capacity': tank['tank_capacity'],
                    'percentage': percentage,
                    'unit': tank['unit'],
                    'status': 'CRITICAL' if percentage <= 10 else 'LOW'
                })
        
        return critical_tanks
        
    except Exception as e:
        print(f"Error checking critical levels: {e}")
        return []

def get_company_fluid_config(empresa_id):
    """Obtiene configuración de fluidos de la empresa"""
    try:
        with get_conn() as conn:
            # Configuración general
            config = pd.read_sql_query("""
                SELECT setting_key, setting_value
                FROM company_settings
                WHERE company_id = ? 
                AND setting_key IN ('unit_preference', 'default_supplier', 'alert_threshold')
            """, conn, params=(empresa_id,))
            
            config_dict = dict(zip(config['setting_key'], config['setting_value'])) if not config.empty else {}
            
            # Configuraciones por defecto
            defaults = {
                'unit_preference': 'galones',
                'default_supplier': '',
                'alert_threshold': '20'
            }
            
            for key, default_value in defaults.items():
                if key not in config_dict:
                    config_dict[key] = default_value
            
            return config_dict
            
    except Exception as e:
        print(f"Error getting fluid config: {e}")
        return {'unit_preference': 'galones', 'default_supplier': '', 'alert_threshold': '20'}

def set_company_fluid_config(empresa_id, config_dict):
    """Establece configuración de fluidos de la empresa"""
    try:
        with get_conn() as conn:
            for key, value in config_dict.items():
                conn.execute("""
                    INSERT OR REPLACE INTO company_settings (company_id, setting_key, setting_value)
                    VALUES (?, ?, ?)
                """, (empresa_id, key, str(value)))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error setting fluid config: {e}")
        return False

def get_machinery_with_fluid_alerts(empresa_id):
    """Obtiene maquinaria con alertas de fluidos para dashboard principal"""
    try:
        machinery_alerts = []
        maquinas = get_active_machinery_compatible(empresa_id)
        
        for _, machine in maquinas.iterrows():
            alerts = []
            
            # Verificar cada tipo de fluido
            fluid_types = get_fluid_types()
            for _, fluid in fluid_types.iterrows():
                try:
                    from controles_module import get_machine_fluid_status, get_company_setting
                    unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
                    status = get_machine_fluid_status(machine['id'], fluid['id'], unit_preference)
                    
                    if status['level'] in ['critico', 'malo']:
                        alerts.append({
                            'fluid_name': fluid['name'],
                            'level': status['level'],
                            'message': status.get('message', '')
                        })
                except:
                    continue
            
            if alerts:
                machinery_alerts.append({
                    'machinery_id': machine['id'],
                    'machinery_name': machine['name'],
                    'identifier': machine.get('identifier', ''),
                    'alerts': alerts,
                    'alert_count': len(alerts)
                })
        
        return machinery_alerts
        
    except Exception as e:
        print(f"Error getting machinery alerts: {e}")
        return []

def create_fluid_movement_record(tank_id, movement_type, quantity, **kwargs):
    """Crea registro de movimiento de fluido desde módulos externos"""
    try:
        with get_conn() as conn:
            # Campos básicos
            fields = ['tank_id', 'movement_type', 'quantity']
            values = [tank_id, movement_type, quantity]
            placeholders = ['?', '?', '?']
            
            # Campos opcionales
            optional_fields = {
                'machinery_id': kwargs.get('machinery_id'),
                'supplier': kwargs.get('supplier'),
                'operator': kwargs.get('operator'),
                'reference_number': kwargs.get('reference_number'),
                'notes': kwargs.get('notes'),
                'created_by': kwargs.get('created_by', 'system'),
                'unit_cost': kwargs.get('unit_cost'),
                'total_cost': kwargs.get('total_cost')
            }
            
            for field, value in optional_fields.items():
                if value is not None:
                    fields.append(field)
                    values.append(value)
                    placeholders.append('?')
            
            query = f"""
                INSERT INTO fluid_inventory_movements ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            """
            
            conn.execute(query, values)
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Error creating movement record: {e}")
        return False

def get_fluid_cost_analysis(empresa_id, months=6):
    """Análisis de costos de fluidos para reportes financieros"""
    try:
        from datetime import date, timedelta
        fecha_limite = (date.today() - timedelta(days=months*30)).isoformat()
        
        with get_conn() as conn:
            cost_analysis = pd.read_sql_query("""
                SELECT 
                    ft.name as fluid_name,
                    COUNT(fim.id) as transaction_count,
                    SUM(fim.quantity) as total_quantity,
                    SUM(fim.total_cost) as total_cost,
                    AVG(fim.unit_cost) as avg_unit_cost,
                    cft.unit,
                    strftime('%Y-%m', fim.created_at) as month_year
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ? 
                AND fim.movement_type = 'ENTRADA'
                AND DATE(fim.created_at) >= ?
                AND fim.total_cost IS NOT NULL
                GROUP BY ft.name, cft.unit, strftime('%Y-%m', fim.created_at)
                ORDER BY month_year DESC, total_cost DESC
            """, conn, params=(empresa_id, fecha_limite))
            
            return cost_analysis
            
    except Exception as e:
        print(f"Error getting cost analysis: {e}")
        return pd.DataFrame()

def sync_legacy_fuel_to_controls(empresa_id):
    """Sincroniza datos legacy de fuel_logs con el nuevo sistema de controles"""
    try:
        with get_conn() as conn:
            # Obtener registros de fuel_logs que no están en el nuevo sistema
            legacy_data = pd.read_sql_query("""
                SELECT fl.machinery_id, fl.fuel_added, fl.added_at, fl.added_by
                FROM fuel_logs fl
                JOIN machinery m ON fl.machinery_id = m.id
                WHERE m.company_id = ?
                AND NOT EXISTS (
                    SELECT 1 FROM fluid_inventory_movements fim
                    JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                    WHERE fim.machinery_id = fl.machinery_id
                    AND ABS(julianday(fim.created_at) - julianday(fl.added_at)) < 1
                    AND cft.fluid_type_id = 1
                )
            """, conn, params=(empresa_id,))
            
            # Verificar si existe tanque de combustible
            fuel_tank = get_tank_by_fluid_type(empresa_id, "Combustible")
            if not fuel_tank:
                return False, "No existe tanque de combustible para sincronizar"
            
            synced_count = 0
            for _, record in legacy_data.iterrows():
                # Crear movimiento de salida en el nuevo sistema
                success = create_fluid_movement_record(
                    tank_id=fuel_tank['id'],
                    movement_type='SALIDA',
                    quantity=record['fuel_added'],
                    machinery_id=record['machinery_id'],
                    operator=record['added_by'],
                    notes=f"Migrado desde fuel_logs - {record['added_at']}",
                    created_by='migration_system'
                )
                
                if success:
                    synced_count += 1
            
            return True, f"Sincronizados {synced_count} registros legacy"
            
    except Exception as e:
        return False, f"Error en sincronización: {str(e)}"

def validate_company_fluid_integrity(empresa_id):
    """Validación completa de integridad de datos de fluidos"""
    try:
        issues = []
        
        # 1. Verificar que existan tipos de fluidos
        fluid_types = get_fluid_types()
        if fluid_types.empty:
            issues.append("No existen tipos de fluidos en el sistema")
        
        # 2. Verificar tanques de la empresa
        tanks = get_company_tanks(empresa_id)
        if tanks.empty:
            issues.append("La empresa no tiene tanques configurados")
        
        # 3. Verificar consistencia de niveles vs movimientos
        for _, tank in tanks.iterrows():
            with get_conn() as conn:
                movements = pd.read_sql_query("""
                    SELECT 
                        SUM(CASE WHEN movement_type = 'ENTRADA' THEN quantity ELSE 0 END) as total_in,
                        SUM(CASE WHEN movement_type = 'SALIDA' THEN quantity ELSE 0 END) as total_out
                    FROM fluid_inventory_movements
                    WHERE tank_id = ?
                """, conn, params=(tank['id'],))
                
                if not movements.empty:
                    calculated_level = movements.iloc[0]['total_in'] - movements.iloc[0]['total_out']
                    actual_level = tank['current_level']
                    
                    if abs(calculated_level - actual_level) > 0.1:
                        issues.append(
                            f"Tanque {tank['fluid_name']}: Nivel calculado ({calculated_level:.2f}) "
                            f"no coincide con actual ({actual_level:.2f})"
                        )
        
        # 4. Verificar movimientos huérfanos
        with get_conn() as conn:
            orphaned = pd.read_sql_query("""
                SELECT COUNT(*) as count
                FROM fluid_inventory_movements fim
                LEFT JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                WHERE cft.id IS NULL
            """, conn)
            
            if not orphaned.empty and orphaned.iloc[0]['count'] > 0:
                issues.append(f"Existen {orphaned.iloc[0]['count']} movimientos huérfanos")
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'tanks_count': len(tanks),
            'fluid_types_count': len(fluid_types)
        }
        
    except Exception as e:
        return {
            'is_valid': False,
            'issues': [f"Error en validación: {str(e)}"],
            'tanks_count': 0,
            'fluid_types_count': 0
        }

# ============================================
# FUNCIONES DE INICIALIZACIÓN Y MIGRACIÓN
# ============================================

def ensure_company_has_fluid_infrastructure(empresa_id):
    """Asegura que una empresa tenga la infraestructura básica de fluidos"""
    try:
        # 1. Verificar que existan tipos de fluidos
        ensure_fluid_types_exist()
        
        # 2. Verificar configuración básica
        config = get_company_fluid_config(empresa_id)
        if not config.get('unit_preference'):
            set_company_fluid_config(empresa_id, {'unit_preference': 'galones'})
        
        return True
        
    except Exception as e:
        print(f"Error ensuring fluid infrastructure: {e}")
        return False

def auto_migrate_company_fluids(empresa_id):
    """Migración automática de datos de fluidos para una empresa"""
    try:
        print(f"Iniciando migración automática para empresa {empresa_id}")
        
        # 1. Asegurar infraestructura básica
        ensure_company_has_fluid_infrastructure(empresa_id)
        
        # 2. Sincronizar datos legacy si existen
        sync_success, sync_message = sync_legacy_fuel_to_controls(empresa_id)
        if sync_success:
            print(f"Sincronización legacy: {sync_message}")
        
        # 3. Validar integridad
        validation = validate_company_fluid_integrity(empresa_id)
        
        return {
            'success': True,
            'infrastructure_ready': True,
            'legacy_synced': sync_success,
            'validation': validation
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'infrastructure_ready': False,
            'legacy_synced': False,
            'validation': {'is_valid': False, 'issues': [str(e)]}
        }

# ============================================
# FUNCIONES PARA REPORTES Y DASHBOARDS
# ============================================

def get_empresa_fluid_dashboard_data(empresa_id):
    """Obtiene todos los datos necesarios para dashboard de fluidos"""
    try:
        return {
            'tanks_summary': get_company_fluid_summary(empresa_id),
            'recent_movements': get_recent_fluid_movements_summary(empresa_id),
            'machinery_fuel_status': get_machinery_fuel_status_for_external(empresa_id),
            'critical_levels': check_critical_fluid_levels(empresa_id),
            'machinery_alerts': get_machinery_with_fluid_alerts(empresa_id),
            'config': get_company_fluid_config(empresa_id)
        }
    except Exception as e:
        print(f"Error getting dashboard data: {e}")
        return None
    
def get_tank_alert_configuration(tank_id, config_key, default_value):
    """Obtiene configuración de alerta específica de un tanque desde db_utils"""
    try:
        with get_conn() as conn:
            result = pd.read_sql_query("""
                SELECT config_value FROM tank_configurations 
                WHERE tank_id = ? AND config_key = ?
            """, conn, params=(tank_id, config_key))
            
            if not result.empty:
                return result.iloc[0]['config_value']
            return default_value
    except Exception as e:
        print(f"Error obteniendo configuración de tanque desde db_utils: {e}")
        return default_value

def set_tank_alert_configuration(tank_id, config_key, config_value):
    """Establece configuración de alerta específica de un tanque desde db_utils"""
    try:
        with get_conn() as conn:
            # Crear tabla si no existe
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
            
            conn.execute("""
                INSERT OR REPLACE INTO tank_configurations (tank_id, config_key, config_value)
                VALUES (?, ?, ?)
            """, (tank_id, config_key, str(config_value)))
            
            conn.commit()
        return True
    except Exception as e:
        print(f"Error estableciendo configuración de tanque desde db_utils: {e}")
        return False

def get_tank_status_with_individual_config(tank_info, empresa_id):
    """Calcula el estado de un tanque usando configuración individual desde db_utils"""
    try:
        # Calcular porcentaje
        percentage = (tank_info['current_level'] / tank_info['tank_capacity']) * 100
        
        # Obtener configuración específica del tanque
        tank_id = tank_info['id']
        
        # Intentar obtener configuración individual
        critical_threshold = get_tank_alert_configuration(tank_id, "critical_threshold", None)
        low_threshold = get_tank_alert_configuration(tank_id, "low_threshold", None)
        
        # Si no hay configuración individual, usar la global
        if critical_threshold is None or low_threshold is None:
            try:
                # Intentar obtener configuración global de la empresa
                from controles_module import get_alert_configuration
                critical_threshold = float(get_alert_configuration(empresa_id, "fuel_levels", "critical_threshold", "10"))
                low_threshold = float(get_alert_configuration(empresa_id, "fuel_levels", "low_threshold", "25"))
            except:
                # Valores por defecto como último recurso
                critical_threshold = 10
                low_threshold = 25
        else:
            critical_threshold = float(critical_threshold)
            low_threshold = float(low_threshold)
        
        # Determinar estado usando solo 3 niveles
        if percentage <= critical_threshold:
            return {
                "status": "critico",
                "percentage": percentage,
                "threshold_used": critical_threshold,
                "config_source": "individual" if get_tank_alert_configuration(tank_id, "critical_threshold", None) else "global"
            }
        elif percentage <= low_threshold:
            return {
                "status": "bajo", 
                "percentage": percentage,
                "threshold_used": low_threshold,
                "config_source": "individual" if get_tank_alert_configuration(tank_id, "low_threshold", None) else "global"
            }
        else:
            return {
                "status": "normal",
                "percentage": percentage,
                "threshold_used": low_threshold,
                "config_source": "individual" if get_tank_alert_configuration(tank_id, "low_threshold", None) else "global"
            }
            
    except Exception as e:
        print(f"Error calculando estado de tanque: {e}")
        # Fallback a lógica simple
        percentage = (tank_info['current_level'] / tank_info['tank_capacity']) * 100
        if percentage <= 10:
            return {"status": "critico", "percentage": percentage, "config_source": "fallback"}
        elif percentage <= 25:
            return {"status": "bajo", "percentage": percentage, "config_source": "fallback"}
        else:
            return {"status": "normal", "percentage": percentage, "config_source": "fallback"}

def get_critical_fluid_levels_enhanced(empresa_id, include_config_info=False):
    """Versión mejorada que usa configuraciones individuales para determinar niveles críticos"""
    try:
        tanks = get_company_tanks(empresa_id)
        critical_tanks = []
        
        for _, tank in tanks.iterrows():
            status_info = get_tank_status_with_individual_config(tank, empresa_id)
            
            if status_info['status'] in ['critico', 'bajo']:
                tank_alert = {
                    'tank_id': tank['id'],
                    'fluid_name': tank['fluid_name'],
                    'current_level': tank['current_level'],
                    'capacity': tank['tank_capacity'],
                    'percentage': status_info['percentage'],
                    'unit': tank['unit'],
                    'status': status_info['status']
                }
                
                if include_config_info:
                    tank_alert.update({
                        'threshold_used': status_info['threshold_used'],
                        'config_source': status_info['config_source']
                    })
                
                critical_tanks.append(tank_alert)
        
        return critical_tanks
        
    except Exception as e:
        print(f"Error obteniendo niveles críticos mejorados: {e}")
        # Fallback a función original si existe
        try:
            return check_critical_fluid_levels(empresa_id)
        except:
            return []

def migrate_tank_configurations_from_global(empresa_id):
    """Migra tanques para usar configuración global si no tienen configuración individual"""
    try:
        tanks = get_company_tanks(empresa_id)
        
        if tanks.empty:
            return True
        
        # Obtener configuración global
        try:
            from controles_module import get_alert_configuration
            global_critical = get_alert_configuration(empresa_id, "fuel_levels", "critical_threshold", "10")
            global_low = get_alert_configuration(empresa_id, "fuel_levels", "low_threshold", "25")
        except:
            global_critical = "10"
            global_low = "25"
        
        migrated_count = 0
        
        for _, tank in tanks.iterrows():
            tank_id = tank['id']
            
            # Verificar si ya tiene configuración individual
            existing_critical = get_tank_alert_configuration(tank_id, "critical_threshold", None)
            existing_low = get_tank_alert_configuration(tank_id, "low_threshold", None)
            
            # Si no tiene configuración individual, no hacer nada (usará la global automáticamente)
            # Solo migrar si se solicita explícitamente establecer configuración individual
            
        print(f"Verificación de configuraciones completada para {len(tanks)} tanques")
        return True
        
    except Exception as e:
        print(f"Error en migración de configuraciones de tanques: {e}")
        return False

def init_tank_configurations_table():
    """Inicializa la tabla de configuraciones de tanques en db_utils"""
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
        return True
    except Exception as e:
        print(f"Error inicializando tabla tank_configurations en db_utils: {e}")
        return False

def get_company_fluid_summary_enhanced(empresa_id):
    """Versión mejorada del resumen de fluidos que incluye configuraciones individuales"""
    try:
        tanks = get_company_tanks(empresa_id)
        
        if tanks.empty:
            return pd.DataFrame()
        
        summary_data = []
        
        for _, tank in tanks.iterrows():
            status_info = get_tank_status_with_individual_config(tank, empresa_id)
            
            summary_data.append({
                'fluid_name': tank['fluid_name'],
                'tank_capacity': tank['tank_capacity'],
                'current_level': tank['current_level'],
                'unit': tank['unit'],
                'percentage_full': status_info['percentage'],
                'status': status_info['status'],
                'tank_id': tank['id'],
                'config_source': status_info.get('config_source', 'unknown'),
                'threshold_used': status_info.get('threshold_used', 'N/A')
            })
        
        return pd.DataFrame(summary_data)
        
    except Exception as e:
        print(f"Error obteniendo resumen mejorado de fluidos: {e}")
        # Fallback a función original
        try:
            return get_company_fluid_summary(empresa_id)
        except:
            return pd.DataFrame()

def validate_tank_configurations(empresa_id):
    """Valida que las configuraciones de tanques sean coherentes"""
    try:
        tanks = get_company_tanks(empresa_id)
        issues = []
        
        for _, tank in tanks.iterrows():
            tank_id = tank['id']
            
            # Obtener configuraciones
            critical = get_tank_alert_configuration(tank_id, "critical_threshold", None)
            low = get_tank_alert_configuration(tank_id, "low_threshold", None)
            
            if critical is not None and low is not None:
                try:
                    critical_val = float(critical)
                    low_val = float(low)
                    
                    if critical_val >= low_val:
                        issues.append(f"Tanque {tank['fluid_name']}: Umbral crítico ({critical_val}%) debe ser menor que umbral bajo ({low_val}%)")
                    
                    if critical_val < 1 or critical_val > 50:
                        issues.append(f"Tanque {tank['fluid_name']}: Umbral crítico ({critical_val}%) fuera de rango válido (1-50%)")
                    
                    if low_val < 1 or low_val > 80:
                        issues.append(f"Tanque {tank['fluid_name']}: Umbral bajo ({low_val}%) fuera de rango válido (1-80%)")
                        
                except ValueError:
                    issues.append(f"Tanque {tank['fluid_name']}: Valores de configuración no numéricos")
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'tanks_checked': len(tanks)
        }
        
    except Exception as e:
        return {
            'is_valid': False,
            'issues': [f"Error en validación: {str(e)}"],
            'tanks_checked': 0
        }

def export_tank_configurations(empresa_id):
    """Exporta configuraciones de tanques para respaldo"""
    try:
        tanks = get_company_tanks(empresa_id)
        configurations = []
        
        for _, tank in tanks.iterrows():
            tank_id = tank['id']
            
            # Obtener todas las configuraciones del tanque
            with get_conn() as conn:
                configs = pd.read_sql_query("""
                    SELECT config_key, config_value, updated_at
                    FROM tank_configurations
                    WHERE tank_id = ?
                """, conn, params=(tank_id,))
            
            tank_config = {
                'tank_id': tank_id,
                'fluid_name': tank['fluid_name'],
                'capacity': tank['tank_capacity'],
                'unit': tank['unit'],
                'configurations': configs.to_dict('records') if not configs.empty else []
            }
            
            configurations.append(tank_config)
        
        return configurations
        
    except Exception as e:
        print(f"Error exportando configuraciones: {e}")
        return []

def import_tank_configurations(empresa_id, configurations_data):
    """Importa configuraciones de tanques desde respaldo"""
    try:
        imported_count = 0
        
        for tank_config in configurations_data:
            tank_id = tank_config.get('tank_id')
            
            if not tank_id:
                continue
            
            # Verificar que el tanque existe
            with get_conn() as conn:
                tank_exists = pd.read_sql_query("""
                    SELECT id FROM company_fluid_tanks 
                    WHERE id = ? AND company_id = ?
                """, conn, params=(tank_id, empresa_id))
            
            if tank_exists.empty:
                continue
            
            # Importar configuraciones
            for config in tank_config.get('configurations', []):
                success = set_tank_alert_configuration(
                    tank_id, 
                    config['config_key'], 
                    config['config_value']
                )
                if success:
                    imported_count += 1
        
        return imported_count
        
    except Exception as e:
        print(f"Error importando configuraciones: {e}")
        return 0

# FUNCIÓN DE INICIALIZACIÓN AUTOMÁTICA
def auto_init_tank_configurations():
    """Inicialización automática al importar db_utils"""
    try:
        init_tank_configurations_table()
        print("Sistema de configuraciones de tanques inicializado")
    except Exception as e:
        print(f"Advertencia: No se pudo inicializar configuraciones de tanques: {e}")

# Ejecutar inicialización automática
if __name__ != "__main__":
    auto_init_tank_configurations()

def get_tank_alert_configuration(tank_id, config_key, default_value):
    """Obtiene configuración específica de un tanque"""
    try:
        with get_conn() as conn:
            result = pd.read_sql_query("""
                SELECT config_value FROM tank_configurations 
                WHERE tank_id = ? AND config_key = ?
            """, conn, params=(tank_id, config_key))
            
            if not result.empty:
                return result.iloc[0]['config_value']
            return default_value
    except Exception as e:
        print(f"Error obteniendo configuración de tanque: {e}")
        return default_value

def set_tank_alert_configuration(tank_id, config_key, config_value):
    """Establece configuración específica de un tanque"""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO tank_configurations 
                (tank_id, config_key, config_value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (tank_id, config_key, str(config_value)))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error estableciendo configuración de tanque: {e}")
        return False

def get_tank_with_fluid_info(tank_id):
    """Obtiene información completa de un tanque con datos del fluido"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT cft.*, ft.name as fluid_name
                FROM company_fluid_tanks cft
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.id = ?
            """, conn, params=(tank_id,))
    except Exception as e:
        print(f"Error obteniendo información de tanque: {e}")
        return pd.DataFrame()

def init_tank_configurations_table():
    """Inicializa la tabla de configuraciones por tanque"""
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
        return True
    except Exception as e:
        print(f"Error inicializando tabla tank_configurations: {e}")
        return False
    

# Agregar estas funciones al final de db_utils.py

import os
import base64
from PIL import Image
import io

# ============================================
# FUNCIONES PARA INFORMACIÓN EXTENDIDA DE EMPRESA
# ============================================

def init_company_info_extended():
    """Inicializa la tabla company_info con campos extendidos"""
    try:
        with get_conn() as conn:
            # Crear tabla extendida si no existe
            conn.execute("""
                CREATE TABLE IF NOT EXISTS company_info_extended (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER UNIQUE,
                    company_name TEXT,
                    email TEXT,
                    phone TEXT,
                    address TEXT,
                    owner_name TEXT,
                    foundation_date TEXT,
                    tax_id TEXT,
                    description TEXT,
                    logo_filename TEXT,
                    website TEXT,
                    industry TEXT,
                    employee_count INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
                )
            """)
            
            # Crear directorio para logos si no existe
            os.makedirs("assets/logos", exist_ok=True)
            
            conn.commit()
        return True
    except Exception as e:
        print(f"Error inicializando company_info_extended: {e}")
        return False

def get_company_info_complete(company_id):
    """Obtiene información completa de la empresa"""
    try:
        with get_conn() as conn:
            # Obtener información básica
            basic_info = pd.read_sql_query("""
                SELECT * FROM companies WHERE id = ?
            """, conn, params=(company_id,))
            
            if basic_info.empty:
                return None
            
            # Obtener información extendida
            extended_info = pd.read_sql_query("""
                SELECT * FROM company_info_extended WHERE company_id = ?
            """, conn, params=(company_id,))
            
            # Combinar información
            company_data = {
                'id': basic_info.iloc[0]['id'],
                'name': basic_info.iloc[0]['name'],
                'created_at': basic_info.iloc[0]['created_at']
            }
            
            # Agregar información extendida si existe
            if not extended_info.empty:
                extended = extended_info.iloc[0]
                company_data.update({
                    'email': extended.get('email', ''),
                    'phone': extended.get('phone', ''),
                    'address': extended.get('address', ''),
                    'owner_name': extended.get('owner_name', ''),
                    'foundation_date': extended.get('foundation_date', ''),
                    'tax_id': extended.get('tax_id', ''),
                    'description': extended.get('description', ''),
                    'logo_filename': extended.get('logo_filename', ''),
                    'website': extended.get('website', ''),
                    'industry': extended.get('industry', ''),
                    'employee_count': extended.get('employee_count', 0),
                    'updated_at': extended.get('updated_at', '')
                })
            else:
                # Valores por defecto
                company_data.update({
                    'email': '', 'phone': '', 'address': '', 'owner_name': '',
                    'foundation_date': '', 'tax_id': '', 'description': '',
                    'logo_filename': '', 'website': '', 'industry': '',
                    'employee_count': 0, 'updated_at': ''
                })
            
            return company_data
            
    except Exception as e:
        print(f"Error obteniendo información completa: {e}")
        return None

def update_company_info_complete(company_id, company_data):
    """Actualiza información completa de la empresa"""
    try:
        with get_conn() as conn:
            # CRÍTICO: Actualizar nombre en tabla principal
            if 'name' in company_data and company_data['name']:
                conn.execute("""
                    UPDATE companies SET name = ? WHERE id = ?
                """, (company_data['name'], company_id))
                print(f"Nombre actualizado a: {company_data['name']}")
            
            # Verificar si existe registro extendido
            existing = pd.read_sql_query("""
                SELECT id FROM company_info_extended WHERE company_id = ?
            """, conn, params=(company_id,))
            
            if existing.empty:
                # Insertar nuevo registro
                conn.execute("""
                    INSERT INTO company_info_extended (
                        company_id, company_name, email, phone, address, 
                        owner_name, foundation_date, tax_id, description,
                        logo_filename, website, industry, employee_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    company_id,
                    company_data.get('name', ''),
                    company_data.get('email', ''),
                    company_data.get('phone', ''),
                    company_data.get('address', ''),
                    company_data.get('owner_name', ''),
                    company_data.get('foundation_date', ''),
                    company_data.get('tax_id', ''),
                    company_data.get('description', ''),
                    company_data.get('logo_filename', ''),
                    company_data.get('website', ''),
                    company_data.get('industry', ''),
                    company_data.get('employee_count', 0)
                ))
            else:
                # Actualizar registro existente
                conn.execute("""
                    UPDATE company_info_extended SET
                        company_name = ?, email = ?, phone = ?, address = ?,
                        owner_name = ?, foundation_date = ?, tax_id = ?, description = ?,
                        logo_filename = ?, website = ?, industry = ?, employee_count = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = ?
                """, (
                    company_data.get('name', ''),
                    company_data.get('email', ''),
                    company_data.get('phone', ''),
                    company_data.get('address', ''),
                    company_data.get('owner_name', ''),
                    company_data.get('foundation_date', ''),
                    company_data.get('tax_id', ''),
                    company_data.get('description', ''),
                    company_data.get('logo_filename', ''),
                    company_data.get('website', ''),
                    company_data.get('industry', ''),
                    company_data.get('employee_count', 0),
                    company_id
                ))
            
            conn.commit()
        return True, "Información actualizada correctamente"
        
    except Exception as e:
        return False, f"Error actualizando información: {str(e)}"

# ============================================
# FUNCIONES PARA GESTIÓN DE LOGOS
# ============================================

def save_company_logo(company_id, uploaded_file, max_size=(300, 300)):
    """Guarda el logo de la empresa y lo redimensiona"""
    try:
        # Validar tipo de archivo
        if uploaded_file.type not in ['image/png', 'image/jpeg', 'image/jpg']:
            return False, "Tipo de archivo no válido. Use PNG o JPG"
        
        # Generar nombre de archivo único
        file_extension = uploaded_file.name.split('.')[-1].lower()
        logo_filename = f"logo_empresa_{company_id}.{file_extension}"
        logo_path = os.path.join("assets", "logos", logo_filename)
        
        # Procesar imagen
        image = Image.open(uploaded_file)
        
        # Convertir a RGB si es necesario (para PNG con transparencia)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Crear fondo blanco para transparencias
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        
        # Redimensionar manteniendo proporción
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Guardar imagen
        os.makedirs(os.path.dirname(logo_path), exist_ok=True)
        image.save(logo_path, 'JPEG', quality=85, optimize=True)
        
        return True, logo_filename
        
    except Exception as e:
        return False, f"Error procesando logo: {str(e)}"

def get_company_logo_path(company_id):
    """Obtiene la ruta del logo de la empresa"""
    try:
        company_info = get_company_info_complete(company_id)
        if company_info and company_info.get('logo_filename'):
            logo_path = os.path.join("assets", "logos", company_info['logo_filename'])
            if os.path.exists(logo_path):
                return logo_path
        return None
    except Exception as e:
        print(f"Error obteniendo ruta de logo: {e}")
        return None

def get_company_logo_base64(company_id):
    """Obtiene el logo en formato base64 para mostrar en Streamlit"""
    try:
        logo_path = get_company_logo_path(company_id)
        if logo_path and os.path.exists(logo_path):
            with open(logo_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        return None
    except Exception as e:
        print(f"Error obteniendo logo base64: {e}")
        return None

def delete_company_logo(company_id):
    """Elimina el logo de la empresa"""
    try:
        logo_path = get_company_logo_path(company_id)
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)
            
            # Actualizar base de datos
            with get_conn() as conn:
                conn.execute("""
                    UPDATE company_info_extended 
                    SET logo_filename = '', updated_at = CURRENT_TIMESTAMP
                    WHERE company_id = ?
                """, (company_id,))
                conn.commit()
            
            return True, "Logo eliminado correctamente"
        return False, "No se encontró logo para eliminar"
        
    except Exception as e:
        return False, f"Error eliminando logo: {str(e)}"

def validate_company_info(company_data):
    """Valida los datos de información de empresa"""
    errors = []
    
    # Validar email
    email = company_data.get('email', '').strip()
    if email and '@' not in email:
        errors.append("Email no tiene formato válido")
    
    # Validar teléfono (números, espacios, guiones, paréntesis)
    phone = company_data.get('phone', '').strip()
    if phone and not all(c.isdigit() or c in ' -()' for c in phone):
        errors.append("Teléfono contiene caracteres no válidos")
    
    # Validar URL del website
    website = company_data.get('website', '').strip()
    if website and not (website.startswith('http://') or website.startswith('https://')):
        if website:  # Si hay contenido pero no protocolo
            company_data['website'] = 'https://' + website
    
    # Validar número de empleados
    try:
        employee_count = int(company_data.get('employee_count', 0))
        if employee_count < 0:
            errors.append("Número de empleados no puede ser negativo")
    except ValueError:
        errors.append("Número de empleados debe ser un número entero")
    
    return errors

def get_companies_with_logos():
    """Obtiene todas las empresas con información de si tienen logo"""
    try:
        with get_conn() as conn:
            companies = pd.read_sql_query("""
                SELECT 
                    c.id,
                    c.name,
                    c.created_at,
                    COALESCE(cie.logo_filename, '') as logo_filename,
                    COALESCE(cie.description, '') as description,
                    CASE 
                        WHEN cie.logo_filename IS NOT NULL AND cie.logo_filename != '' 
                        THEN 1 ELSE 0 
                    END as has_logo
                FROM companies c
                LEFT JOIN company_info_extended cie ON c.id = cie.company_id
                ORDER BY c.name
            """, conn)
            
            return companies
            
    except Exception as e:
        print(f"Error obteniendo empresas con logos: {e}")
        return pd.DataFrame()

def cleanup_orphaned_logos():
    """Limpia logos huérfanos (sin empresa asociada)"""
    try:
        logos_dir = os.path.join("assets", "logos")
        if not os.path.exists(logos_dir):
            return True
        
        # Obtener logos en base de datos
        with get_conn() as conn:
            db_logos = pd.read_sql_query("""
                SELECT DISTINCT logo_filename 
                FROM company_info_extended 
                WHERE logo_filename IS NOT NULL AND logo_filename != ''
            """, conn)
        
        db_logo_files = set(db_logos['logo_filename'].tolist()) if not db_logos.empty else set()
        
        # Obtener archivos en directorio
        existing_files = set(os.listdir(logos_dir))
        
        # Eliminar huérfanos
        orphaned_files = existing_files - db_logo_files
        deleted_count = 0
        
        for file in orphaned_files:
            if file.startswith('logo_empresa_'):
                file_path = os.path.join(logos_dir, file)
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error eliminando {file}: {e}")
        
        return deleted_count
        
    except Exception as e:
        print(f"Error limpiando logos huérfanos: {e}")
        return 0

def get_company_summary_stats():
    """Obtiene estadísticas resumidas de todas las empresas"""
    try:
        with get_conn() as conn:
            stats = pd.read_sql_query("""
                SELECT 
                    COUNT(c.id) as total_companies,
                    COUNT(cie.logo_filename) as companies_with_logo,
                    COUNT(CASE WHEN cie.email IS NOT NULL AND cie.email != '' THEN 1 END) as companies_with_email,
                    COUNT(CASE WHEN cie.phone IS NOT NULL AND cie.phone != '' THEN 1 END) as companies_with_phone,
                    COUNT(CASE WHEN cie.address IS NOT NULL AND cie.address != '' THEN 1 END) as companies_with_address,
                    AVG(CASE WHEN cie.employee_count > 0 THEN cie.employee_count END) as avg_employees
                FROM companies c
                LEFT JOIN company_info_extended cie ON c.id = cie.company_id
            """, conn)
            
            if not stats.empty:
                return stats.iloc[0].to_dict()
            return {}
            
    except Exception as e:
        print(f"Error obteniendo estadísticas: {e}")
        return {}

# ============================================
# FUNCIONES PARA RESPALDOS EXTENDIDOS
# ============================================

def backup_company_info_extended(company_id):
    """Crea respaldo de información extendida de empresa"""
    try:
        company_info = get_company_info_complete(company_id)
        if not company_info:
            return None
        
        backup_data = {
            'company_info': company_info,
            'logo_base64': get_company_logo_base64(company_id),
            'backup_timestamp': datetime.now().isoformat()
        }
        
        return backup_data
        
    except Exception as e:
        print(f"Error creando respaldo extendido: {e}")
        return None

def restore_company_info_extended(company_id, backup_data):
    """Restaura información extendida desde respaldo"""
    try:
        # Restaurar información básica
        success, message = update_company_info_complete(
            company_id, 
            backup_data['company_info']
        )
        
        if not success:
            return False, message
        
        # Restaurar logo si existe
        if backup_data.get('logo_base64'):
            try:
                # Decodificar y guardar logo
                logo_data = base64.b64decode(backup_data['logo_base64'])
                logo_image = Image.open(io.BytesIO(logo_data))
                
                # Generar nombre y guardar
                logo_filename = f"logo_empresa_{company_id}.jpg"
                logo_path = os.path.join("assets", "logos", logo_filename)
                os.makedirs(os.path.dirname(logo_path), exist_ok=True)
                logo_image.save(logo_path, 'JPEG', quality=85)
                
                # Actualizar base de datos
                update_company_info_complete(company_id, {'logo_filename': logo_filename})
                
            except Exception as e:
                print(f"Error restaurando logo: {e}")
        
        return True, "Información restaurada correctamente"
        
    except Exception as e:
        return False, f"Error restaurando información: {str(e)}"

# ============================================
# INICIALIZACIÓN AUTOMÁTICA
# ============================================

def auto_init_company_info_extended():
    """Inicialización automática al importar"""
    try:
        init_company_info_extended()
        print("Sistema de información extendida de empresas inicializado")
    except Exception as e:
        print(f"Advertencia: No se pudo inicializar info extendida: {e}")

# Ejecutar inicialización automática
if __name__ != "__main__":
    auto_init_company_info_extended()

# Agregar estas funciones auxiliares a db_utils.py

def init_company_directories():
    """Inicializa los directorios necesarios para el sistema"""
    try:
        directories = [
            "assets",
            "assets/logos", 
            "assets/temp",
            "assets/exports",
            "assets/backups"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        # Crear archivo .gitkeep para mantener directorios vacíos en git
        for directory in directories:
            gitkeep_path = os.path.join(directory, ".gitkeep")
            if not os.path.exists(gitkeep_path):
                with open(gitkeep_path, 'w') as f:
                    f.write("# Este archivo mantiene el directorio en el control de versiones\n")
        
        return True
    except Exception as e:
        print(f"Error inicializando directorios: {e}")
        return False

def validate_image_file(uploaded_file):
    """Valida archivo de imagen antes de procesarlo"""
    try:
        # Verificar tipo MIME
        valid_types = ['image/png', 'image/jpeg', 'image/jpg']
        if uploaded_file.type not in valid_types:
            return False, "Tipo de archivo no válido. Use PNG, JPG o JPEG"
        
        # Verificar tamaño (máximo 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if uploaded_file.size > max_size:
            return False, f"Archivo muy grande. Máximo permitido: 5MB"
        
        # Intentar abrir imagen para verificar que es válida
        try:
            image = Image.open(uploaded_file)
            # Verificar dimensiones mínimas
            if image.size[0] < 50 or image.size[1] < 50:
                return False, "Imagen muy pequeña. Mínimo 50x50 píxeles"
            
            # Verificar dimensiones máximas
            if image.size[0] > 2000 or image.size[1] > 2000:
                return False, "Imagen muy grande. Máximo 2000x2000 píxeles"
            
            return True, "Archivo válido"
            
        except Exception as e:
            return False, "Archivo de imagen corrupto o no válido"
            
    except Exception as e:
        return False, f"Error validando archivo: {str(e)}"

def optimize_logo_image(image_path, max_size=(300, 300), quality=85):
    """Optimiza una imagen de logo para web"""
    try:
        with Image.open(image_path) as img:
            # Convertir a RGB si es necesario
            if img.mode in ('RGBA', 'LA', 'P'):
                # Crear fondo blanco para transparencias
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Redimensionar manteniendo proporción
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Crear versiones múltiples si es necesario
            sizes = {
                'small': (100, 100),
                'medium': (200, 200), 
                'large': (300, 300)
            }
            
            base_name = os.path.splitext(image_path)[0]
            
            # Guardar imagen principal optimizada
            img.save(image_path, 'JPEG', quality=quality, optimize=True)
            
            # Guardar versiones adicionales
            for size_name, size_dims in sizes.items():
                if size_dims != max_size:  # Evitar duplicar el tamaño principal
                    size_img = img.copy()
                    size_img.thumbnail(size_dims, Image.Resampling.LANCZOS)
                    size_path = f"{base_name}_{size_name}.jpg"
                    size_img.save(size_path, 'JPEG', quality=quality, optimize=True)
            
            return True, "Imagen optimizada correctamente"
            
    except Exception as e:
        return False, f"Error optimizando imagen: {str(e)}"

def get_company_logo_variants(company_id):
    """Obtiene todas las variantes de logo disponibles para una empresa"""
    try:
        company_info = get_company_info_complete(company_id)
        if not company_info or not company_info.get('logo_filename'):
            return {}
        
        base_filename = company_info['logo_filename']
        base_path = os.path.join("assets", "logos", base_filename)
        base_name = os.path.splitext(base_path)[0]
        
        variants = {}
        
        # Verificar archivo principal
        if os.path.exists(base_path):
            variants['original'] = base_path
        
        # Verificar variantes de tamaño
        size_variants = ['small', 'medium', 'large']
        for size in size_variants:
            variant_path = f"{base_name}_{size}.jpg"
            if os.path.exists(variant_path):
                variants[size] = variant_path
        
        return variants
        
    except Exception as e:
        print(f"Error obteniendo variantes de logo: {e}")
        return {}

def generate_company_card_html(company_data, logo_base64=None, theme="light"):
    """Genera HTML para tarjeta de empresa personalizada"""
    try:
        # Configurar colores según tema
        if theme == "dark":
            bg_color = "#2d3e50"
            text_color = "white"
            border_color = "#4a6fa5"
        else:
            bg_color = "#f8f9fa"
            text_color = "#333"
            border_color = "#dee2e6"
        
        # Contenido del logo
        if logo_base64:
            logo_content = f'''
                <img src="data:image/jpeg;base64,{logo_base64}" 
                     style="width: 80px; height: 80px; object-fit: cover; border-radius: 50%; border: 3px solid rgba(255,255,255,0.3);">
            '''
            status_indicator = '<div class="status-indicator complete">✓</div>'
        else:
            logo_content = '<span style="font-size: 50px;">🏢</span>'
            status_indicator = '<div class="status-indicator partial">!</div>'
        
        # Información adicional
        descripcion = company_data.get('description', '')
        descripcion_corta = descripcion[:80] + "..." if len(descripcion) > 80 else descripcion
        
        info_items = []
        if company_data.get('industry'):
            info_items.append(f"📍 {company_data['industry']}")
        if company_data.get('employee_count', 0) > 0:
            info_items.append(f"👥 {company_data['employee_count']} empleados")
        if company_data.get('email'):
            info_items.append("📧 Email configurado")
        
        info_text = "<br>".join(info_items[:2])
        
        html = f"""
        <div class="company-card fade-in-up" style="
            background: {bg_color}; 
            color: {text_color}; 
            border: 2px solid {border_color};
            min-height: 320px;
            position: relative;
        ">
            {status_indicator}
            
            <div class="logo-container">
                {logo_content}
            </div>
            
            <div style="padding: 0 15px;">
                <h4 style="margin: 10px 0; font-weight: bold;">{company_data['name']}</h4>
                <p style="font-size: 12px; opacity: 0.7;">ID: {company_data['id']}</p>
                
                {f'<p style="font-size: 13px; margin: 10px 0; line-height: 1.3;">{descripcion_corta}</p>' if descripcion_corta else ''}
                
                <div style="font-size: 11px; opacity: 0.8; margin: 10px 0;">
                    {info_text}
                </div>
            </div>
            
            <div style="position: absolute; bottom: 10px; left: 0; right: 0; text-align: center;">
                <small style="opacity: 0.6;">Registrada: {company_data.get('created_at', '')[:10]}</small>
            </div>
        </div>
        """
        
        return html
        
    except Exception as e:
        print(f"Error generando HTML de tarjeta: {e}")
        return f"<div>Error cargando empresa {company_data.get('name', 'Desconocida')}</div>"

def export_company_complete_info(company_id, include_logo=True):
    """Exporta información completa de empresa en formato JSON"""
    try:
        company_info = get_company_info_complete(company_id)
        if not company_info:
            return None
        
        export_data = {
            'company_info': company_info,
            'export_timestamp': datetime.now().isoformat(),
            'export_version': '1.0'
        }
        
        # Incluir logo en base64 si se solicita
        if include_logo:
            logo_base64 = get_company_logo_base64(company_id)
            if logo_base64:
                export_data['logo_base64'] = logo_base64
        
        # Incluir estadísticas básicas
        try:
            maquinarias = list_machinery(company_id)
            export_data['statistics'] = {
                'total_machines': len(maquinarias),
                'active_machines': len(maquinarias[maquinarias['status'] == 'Active']) if not maquinarias.empty else 0
            }
        except Exception:
            export_data['statistics'] = {}
        
        return export_data
        
    except Exception as e:
        print(f"Error exportando información completa: {e}")
        return None

def import_company_complete_info(import_data, target_company_id=None):
    """Importa información completa de empresa desde JSON"""
    try:
        if 'company_info' not in import_data:
            return False, "Datos de importación inválidos"
        
        company_data = import_data['company_info']
        
        # Determinar ID de empresa objetivo
        if target_company_id is None:
            # Crear nueva empresa
            from db_utils import add_company
            if not add_company(company_data['name']):
                return False, "Error creando nueva empresa"
            
            # Obtener ID de la empresa recién creada
            empresas = list_companies()
            nueva_empresa = empresas[empresas['name'] == company_data['name']]
            if nueva_empresa.empty:
                return False, "Error obteniendo ID de nueva empresa"
            
            target_company_id = nueva_empresa.iloc[0]['id']
        
        # Actualizar información
        success, message = update_company_info_complete(target_company_id, company_data)
        if not success:
            return False, f"Error actualizando información: {message}"
        
        # Importar logo si existe
        if 'logo_base64' in import_data and import_data['logo_base64']:
            try:
                logo_data = base64.b64decode(import_data['logo_base64'])
                logo_image = Image.open(io.BytesIO(logo_data))
                
                # Guardar logo
                logo_filename = f"logo_empresa_{target_company_id}.jpg"
                logo_path = os.path.join("assets", "logos", logo_filename)
                logo_image.save(logo_path, 'JPEG', quality=85)
                
                # Actualizar base de datos
                update_company_info_complete(target_company_id, {'logo_filename': logo_filename})
                
            except Exception as e:
                print(f"Error importando logo: {e}")
        
        return True, f"Información importada correctamente (ID: {target_company_id})"
        
    except Exception as e:
        return False, f"Error importando información: {str(e)}"

def get_companies_dashboard_summary():
    """Obtiene resumen para dashboard principal del sistema"""
    try:
        companies = get_companies_with_logos()
        
        if companies.empty:
            return {
                'total_companies': 0,
                'companies_with_logos': 0,
                'companies_with_complete_info': 0,
                'most_recent_company': None,
                'logo_percentage': 0
            }
        
        # Estadísticas básicas
        total = len(companies)
        with_logos = len(companies[companies['has_logo'] == 1])
        
        # Empresas con información completa
        complete_info_count = 0
        for _, company in companies.iterrows():
            info = get_company_info_complete(company['id'])
            if info and all([
                info.get('email'),
                info.get('phone'), 
                info.get('address'),
                info.get('description')
            ]):
                complete_info_count += 1
        
        # Empresa más reciente
        most_recent = companies.iloc[0] if not companies.empty else None
        
        summary = {
            'total_companies': total,
            'companies_with_logos': with_logos,
            'companies_with_complete_info': complete_info_count,
            'most_recent_company': most_recent.to_dict() if most_recent is not None else None,
            'logo_percentage': (with_logos / total * 100) if total > 0 else 0,
            'complete_info_percentage': (complete_info_count / total * 100) if total > 0 else 0
        }
        
        return summary
        
    except Exception as e:
        print(f"Error obteniendo resumen dashboard: {e}")
        return {}

def cleanup_system_files():
    """Limpia archivos del sistema que no están en uso"""
    try:
        cleanup_summary = {
            'logos_removed': 0,
            'temp_files_removed': 0,
            'total_space_freed': 0
        }
        
        # Limpiar logos huérfanos
        logos_removed = cleanup_orphaned_logos()
        cleanup_summary['logos_removed'] = logos_removed
        
        # Limpiar archivos temporales
        temp_dir = os.path.join("assets", "temp")
        if os.path.exists(temp_dir):
            temp_files = os.listdir(temp_dir)
            for temp_file in temp_files:
                if temp_file != ".gitkeep":
                    temp_path = os.path.join(temp_dir, temp_file)
                    try:
                        file_size = os.path.getsize(temp_path)
                        os.remove(temp_path)
                        cleanup_summary['temp_files_removed'] += 1
                        cleanup_summary['total_space_freed'] += file_size
                    except Exception:
                        continue
        
        # Limpiar respaldos antiguos (más de 30 días)
        backups_dir = os.path.join("assets", "backups")
        if os.path.exists(backups_dir):
            cutoff_date = datetime.now() - timedelta(days=30)
            backup_files = os.listdir(backups_dir)
            
            for backup_file in backup_files:
                if backup_file != ".gitkeep":
                    backup_path = os.path.join(backups_dir, backup_file)
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(backup_path))
                        if file_time < cutoff_date:
                            file_size = os.path.getsize(backup_path)
                            os.remove(backup_path)
                            cleanup_summary['total_space_freed'] += file_size
                    except Exception:
                        continue
        
        return cleanup_summary
        
    except Exception as e:
        print(f"Error en limpieza del sistema: {e}")
        return {'error': str(e)}

def validate_system_integrity():
    """Valida la integridad del sistema completo"""
    try:
        issues = []
        
        # Verificar estructura de directorios
        required_dirs = ["assets", "assets/logos", "assets/temp", "assets/exports", "assets/backups"]
        for directory in required_dirs:
            if not os.path.exists(directory):
                issues.append(f"Directorio faltante: {directory}")
        
        # Verificar base de datos
        try:
            with get_conn() as conn:
                # Verificar tablas principales
                required_tables = ['companies', 'company_info_extended', 'machinery']
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = [table[0] for table in cursor.fetchall()]
                
                for table in required_tables:
                    if table not in existing_tables:
                        issues.append(f"Tabla faltante en BD: {table}")
        except Exception as e:
            issues.append(f"Error conectando a BD: {str(e)}")
        
        # Verificar consistencia de logos
        companies = get_companies_with_logos()
        for _, company in companies.iterrows():
            if company['logo_filename']:
                logo_path = os.path.join("assets", "logos", company['logo_filename'])
                if not os.path.exists(logo_path):
                    issues.append(f"Logo faltante para empresa {company['name']}: {company['logo_filename']}")
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'checks_performed': len(required_dirs) + len(companies) + 3
        }
        
    except Exception as e:
        return {
            'is_valid': False,
            'issues': [f"Error en validación: {str(e)}"],
            'checks_performed': 0
        }

# Funciones de inicialización automática
def auto_setup_company_system():
    """Configuración automática del sistema de empresas"""
    try:
        print("Inicializando sistema de gestión de empresas...")
        
        # Inicializar directorios
        init_company_directories()
        
        # Inicializar base de datos extendida
        init_company_info_extended()
        
        # Validar integridad
        validation = validate_system_integrity()
        
        if validation['is_valid']:
            print("✅ Sistema de empresas inicializado correctamente")
        else:
            print(f"⚠️ Sistema inicializado con {len(validation['issues'])} advertencias")
            for issue in validation['issues'][:3]:  # Mostrar máximo 3 issues
                print(f"  - {issue}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error inicializando sistema de empresas: {e}")
        return False

# Ejecutar configuración automática
if __name__ != "__main__":
    auto_setup_company_system()

# ============================================
# EXTENSIONES PARA db_utils.py - MÓDULO EXTRAS
# ============================================
# Agregar estas funciones al final de tu archivo db_utils.py

def init_extras_tables():
    """Inicializa tablas para el módulo EXTRAS"""
    try:
        with get_conn() as conn:
            # Tabla para metadatos de módulos EXTRAS
            conn.execute("""
                CREATE TABLE IF NOT EXISTS extras_modules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_name TEXT UNIQUE NOT NULL,
                    module_version TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla para categorías de costos
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla para detalles específicos de costos de mantenimiento
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_cost_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    maintenance_record_id INTEGER,
                    category_id INTEGER,
                    item_name TEXT NOT NULL,
                    unit_cost REAL NOT NULL,
                    quantity REAL DEFAULT 1,
                    total_cost REAL NOT NULL,
                    supplier TEXT,
                    notes TEXT,
                    created_by TEXT DEFAULT 'admin',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (maintenance_record_id) REFERENCES maintenance_records(id) ON DELETE CASCADE,
                    FOREIGN KEY (category_id) REFERENCES cost_categories(id)
                )
            """)
            
            # Insertar módulos EXTRAS por defecto
            conn.execute("""
                INSERT OR REPLACE INTO extras_modules (module_name, module_version)
                VALUES ('costos_especificos', '1.0')
            """)
            
            # Insertar categorías por defecto si no existen
            default_categories = [
                ('Filtros', 'Filtros de aceite, aire, combustible, etc.'),
                ('Aceites', 'Aceites de motor, hidráulico, transmisión'),
                ('Ruedas', 'Neumáticos, rines, balanceado'),
                ('Servicios', 'Mano de obra especializada'),
                ('Repuestos', 'Piezas de repuesto y componentes'),
                ('Materiales', 'Materiales varios y consumibles'),
                ('Otros', 'Gastos diversos no categorizados')
            ]
            
            for category_name, description in default_categories:
                conn.execute("""
                    INSERT OR IGNORE INTO cost_categories (category_name, description)
                    VALUES (?, ?)
                """, (category_name, description))
            
            conn.commit()
        return True
    except Exception as e:
        print(f"Error inicializando tablas EXTRAS: {e}")
        return False

def get_extras_cost_categories():
    """Obtiene todas las categorías de costos activas"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT * FROM cost_categories 
                WHERE is_active = 1 
                ORDER BY category_name
            """, conn)
    except Exception as e:
        print(f"Error obteniendo categorías de costos: {e}")
        return pd.DataFrame()

def add_extras_cost_category(category_name, description=""):
    """Agrega nueva categoría de costo"""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO cost_categories (category_name, description)
                VALUES (?, ?)
            """, (category_name, description))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error agregando categoría de costo: {e}")
        return False

def update_extras_cost_category(category_id, description, is_active):
    """Actualiza categoría de costo"""
    try:
        with get_conn() as conn:
            conn.execute("""
                UPDATE cost_categories 
                SET description = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (description, 1 if is_active else 0, category_id))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error actualizando categoría de costo: {e}")
        return False

def get_maintenance_cost_details_db(maintenance_id):
    """Obtiene detalles de costo de un mantenimiento específico"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT 
                    mcd.*,
                    cc.category_name
                FROM maintenance_cost_details mcd
                JOIN cost_categories cc ON mcd.category_id = cc.id
                WHERE mcd.maintenance_record_id = ?
                ORDER BY mcd.created_at
            """, conn, params=(maintenance_id,))
    except Exception as e:
        print(f"Error obteniendo detalles de costo: {e}")
        return pd.DataFrame()

def add_maintenance_cost_detail_db(maintenance_id, category_id, item_name, unit_cost, quantity, total_cost, supplier=None, notes=None, created_by="admin"):
    """Agrega detalle de costo a mantenimiento"""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO maintenance_cost_details 
                (maintenance_record_id, category_id, item_name, unit_cost, quantity, total_cost, supplier, notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (maintenance_id, category_id, item_name, unit_cost, quantity, total_cost, supplier, notes, created_by))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error agregando detalle de costo: {e}")
        return False

def delete_maintenance_cost_detail_db(detail_id):
    """Elimina un detalle de costo"""
    try:
        with get_conn() as conn:
            conn.execute("DELETE FROM maintenance_cost_details WHERE id = ?", (detail_id,))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error eliminando detalle de costo: {e}")
        return False

def get_maintenance_detailed_cost_sum(maintenance_id):
    """Obtiene la suma de costos ya detallados para un mantenimiento"""
    try:
        with get_conn() as conn:
            result = pd.read_sql_query("""
                SELECT COALESCE(SUM(total_cost), 0) as total_detailed
                FROM maintenance_cost_details
                WHERE maintenance_record_id = ?
            """, conn, params=(maintenance_id,))
            return float(result.iloc[0]['total_detailed']) if not result.empty else 0.0
    except Exception as e:
        print(f"Error obteniendo suma de costos detallados: {e}")
        return 0.0

def get_cost_summary_by_category_db(empresa_id):
    """Obtiene resumen de costos por categoría para una empresa"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT 
                    cc.category_name,
                    COUNT(mcd.id) as transaction_count,
                    SUM(mcd.total_cost) as total_cost,
                    AVG(mcd.total_cost) as avg_cost
                FROM maintenance_cost_details mcd
                JOIN cost_categories cc ON mcd.category_id = cc.id
                JOIN maintenance_records mr ON mcd.maintenance_record_id = mr.id
                JOIN machinery m ON mr.machinery_id = m.id
                WHERE m.company_id = ?
                GROUP BY cc.category_name, cc.id
                ORDER BY total_cost DESC
            """, conn, params=(empresa_id,))
    except Exception as e:
        print(f"Error obteniendo resumen por categoría: {e}")
        return pd.DataFrame()

def get_machine_cost_analysis_db(empresa_id, machine_id=None):
    """Obtiene análisis de costos por máquina"""
    try:
        with get_conn() as conn:
            where_clause = "WHERE m.company_id = ?"
            params = [empresa_id]
            
            if machine_id:
                where_clause += " AND m.id = ?"
                params.append(machine_id)
            
            return pd.read_sql_query(f"""
                SELECT 
                    m.name as machine_name,
                    m.identifier,
                    COUNT(DISTINCT mr.id) as maintenance_count,
                    COUNT(mcd.id) as detailed_items,
                    SUM(mr.cost) as total_maintenance_cost,
                    SUM(mcd.total_cost) as total_detailed_cost,
                    (SUM(mr.cost) - SUM(mcd.total_cost)) as undetailed_cost
                FROM machinery m
                LEFT JOIN maintenance_records mr ON m.id = mr.machinery_id
                LEFT JOIN maintenance_cost_details mcd ON mr.id = mcd.maintenance_record_id
                {where_clause}
                GROUP BY m.id, m.name, m.identifier
                HAVING total_maintenance_cost > 0
                ORDER BY total_maintenance_cost DESC
            """, conn, params=params)
    except Exception as e:
        print(f"Error obteniendo análisis por máquina: {e}")
        return pd.DataFrame()

def get_supplier_analysis_db(empresa_id):
    """Obtiene análisis de proveedores"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT 
                    COALESCE(mcd.supplier, 'Sin especificar') as supplier_name,
                    COUNT(mcd.id) as transaction_count,
                    SUM(mcd.total_cost) as total_spent,
                    AVG(mcd.total_cost) as avg_transaction,
                    COUNT(DISTINCT mcd.category_id) as categories_used
                FROM maintenance_cost_details mcd
                JOIN maintenance_records mr ON mcd.maintenance_record_id = mr.id
                JOIN machinery m ON mr.machinery_id = m.id
                WHERE m.company_id = ?
                GROUP BY COALESCE(mcd.supplier, 'Sin especificar')
                ORDER BY total_spent DESC
            """, conn, params=(empresa_id,))
    except Exception as e:
        print(f"Error obteniendo análisis de proveedores: {e}")
        return pd.DataFrame()

def get_monthly_cost_trend_db(empresa_id, months=12):
    """Obtiene tendencia de costos mensual"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT 
                    strftime('%Y-%m', mr.performed_at) as month_year,
                    COUNT(mcd.id) as item_count,
                    SUM(mcd.total_cost) as total_cost,
                    COUNT(DISTINCT mr.id) as maintenance_count
                FROM maintenance_cost_details mcd
                JOIN maintenance_records mr ON mcd.maintenance_record_id = mr.id
                JOIN machinery m ON mr.machinery_id = m.id
                WHERE m.company_id = ?
                AND mr.performed_at >= date('now', '-' || ? || ' months')
                GROUP BY strftime('%Y-%m', mr.performed_at)
                ORDER BY month_year
            """, conn, params=(empresa_id, months))
    except Exception as e:
        print(f"Error obteniendo tendencia mensual: {e}")
        return pd.DataFrame()

def export_cost_details_report_db(empresa_id):
    """Exporta reporte completo de detalles de costos"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT 
                    m.name as 'Máquina',
                    m.identifier as 'Matrícula',
                    mr.performed_at as 'Fecha Mantenimiento',
                    COALESCE(mt.name, 'No especificado') as 'Tipo Mantenimiento',
                    mr.cost as 'Costo Total Mantenimiento',
                    cc.category_name as 'Categoría',
                    mcd.item_name as 'Insumo/Servicio',
                    mcd.quantity as 'Cantidad',
                    mcd.unit_cost as 'Costo Unitario',
                    mcd.total_cost as 'Costo Total Item',
                    COALESCE(mcd.supplier, 'No especificado') as 'Proveedor',
                    COALESCE(mcd.notes, '') as 'Notas',
                    mcd.created_at as 'Fecha Registro Detalle'
                FROM maintenance_cost_details mcd
                JOIN cost_categories cc ON mcd.category_id = cc.id
                JOIN maintenance_records mr ON mcd.maintenance_record_id = mr.id
                LEFT JOIN maintenance_types mt ON mr.maintenance_type_id = mt.id
                JOIN machinery m ON mr.machinery_id = m.id
                WHERE m.company_id = ?
                ORDER BY mr.performed_at DESC, m.name, mcd.created_at
            """, conn, params=(empresa_id,))
    except Exception as e:
        print(f"Error exportando reporte de costos: {e}")
        return pd.DataFrame()

def get_maintenance_records_fixed(empresa_id, machinery_id=None, maintenance_type_id=None, limit=None):
    """Versión corregida de get_maintenance_records que se adapta a la estructura de BD"""
    try:
        with get_conn() as conn:
            # Verificar qué columnas existen
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(maintenance_records)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Construir consulta adaptativa
            base_query = """
                SELECT 
                    mr.id,
                    m.name as machinery_name,
                    COALESCE(m.identifier, 'Sin matrícula') as identifier
            """
            
            # Agregar columnas según disponibilidad
            if 'maintenance_type_id' in columns:
                base_query += ", COALESCE(mt.name, 'Mantenimiento') as maintenance_type"
                joins = " FROM maintenance_records mr JOIN machinery m ON mr.machinery_id = m.id LEFT JOIN maintenance_types mt ON mr.maintenance_type_id = mt.id"
            else:
                base_query += ", 'Mantenimiento' as maintenance_type"
                joins = " FROM maintenance_records mr JOIN machinery m ON mr.machinery_id = m.id"
            
            # Fecha de realización
            if 'performed_at' in columns:
                base_query += ", mr.performed_at"
            elif 'date_performed' in columns:
                base_query += ", mr.date_performed as performed_at"
            else:
                base_query += ", mr.created_at as performed_at"
            
            # Otras columnas
            if 'performed_by' in columns:
                base_query += ", mr.performed_by"
            else:
                base_query += ", 'admin' as performed_by"
            
            if 'cost' in columns:
                base_query += ", COALESCE(mr.cost, 0) as cost"
            else:
                base_query += ", 0 as cost"
            
            if 'description' in columns:
                base_query += ", COALESCE(mr.description, '') as description"
            else:
                base_query += ", '' as description"
            
            # Completar consulta
            base_query += joins
            base_query += " WHERE m.company_id = ?"
            
            params = [empresa_id]
            
            if machinery_id:
                base_query += " AND mr.machinery_id = ?"
                params.append(machinery_id)
            
            if maintenance_type_id:
                base_query += " AND mr.maintenance_type_id = ?"
                params.append(maintenance_type_id)
            
            base_query += " ORDER BY mr.id DESC"
            
            if limit:
                base_query += " LIMIT ?"
                params.append(limit)
            
            return pd.read_sql_query(base_query, conn, params=params)
            
    except Exception as e:
        print(f"Error en get_maintenance_records_fixed: {e}")
        return pd.DataFrame()

def validate_maintenance_cost_integrity(empresa_id):
    """Valida la integridad de los datos de costos de mantenimiento"""
    try:
        issues = []
        
        with get_conn() as conn:
            # Verificar detalles huérfanos (sin mantenimiento)
            orphaned_details = pd.read_sql_query("""
                SELECT COUNT(*) as count
                FROM maintenance_cost_details mcd
                LEFT JOIN maintenance_records mr ON mcd.maintenance_record_id = mr.id
                WHERE mr.id IS NULL
            """, conn)
            
            if not orphaned_details.empty and orphaned_details.iloc[0]['count'] > 0:
                issues.append(f"Se encontraron {orphaned_details.iloc[0]['count']} detalles de costo huérfanos")
            
            # Verificar categorías inactivas en uso
            inactive_categories = pd.read_sql_query("""
                SELECT cc.category_name, COUNT(mcd.id) as usage_count
                FROM maintenance_cost_details mcd
                JOIN cost_categories cc ON mcd.category_id = cc.id
                WHERE cc.is_active = 0
                GROUP BY cc.id, cc.category_name
            """, conn)
            
            if not inactive_categories.empty:
                for _, cat in inactive_categories.iterrows():
                    issues.append(f"Categoría inactiva '{cat['category_name']}' tiene {cat['usage_count']} registros en uso")
            
            # Verificar inconsistencias en totales
            inconsistent_totals = pd.read_sql_query("""
                SELECT 
                    mr.id,
                    m.name as machine_name,
                    mr.cost as recorded_cost,
                    SUM(mcd.total_cost) as detailed_cost
                FROM maintenance_records mr
                JOIN machinery m ON mr.machinery_id = m.id
                JOIN maintenance_cost_details mcd ON mr.id = mcd.maintenance_record_id
                WHERE m.company_id = ?
                GROUP BY mr.id, mr.cost, m.name
                HAVING ABS(mr.cost - SUM(mcd.total_cost)) > 0.01
            """, conn, params=(empresa_id,))
            
            if not inconsistent_totals.empty:
                for _, record in inconsistent_totals.iterrows():
                    issues.append(f"Mantenimiento ID {record['id']} ({record['machine_name']}): Costo registrado ${record['recorded_cost']:.2f} vs detallado ${record['detailed_cost']:.2f}")
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'checks_performed': 3
        }
        
    except Exception as e:
        return {
            'is_valid': False,
            'issues': [f"Error en validación: {str(e)}"],
            'checks_performed': 0
        }

def cleanup_maintenance_cost_data(empresa_id):
    """Limpia datos inconsistentes de costos de mantenimiento"""
    try:
        cleanup_summary = {
            'orphaned_details_removed': 0,
            'inactive_category_details_removed': 0,
            'total_space_freed': 0
        }
        
        with get_conn() as conn:
            # Eliminar detalles huérfanos
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM maintenance_cost_details 
                WHERE maintenance_record_id NOT IN (
                    SELECT id FROM maintenance_records
                )
            """)
            cleanup_summary['orphaned_details_removed'] = cursor.rowcount
            
            # Eliminar detalles con categorías inactivas
            cursor.execute("""
                DELETE FROM maintenance_cost_details 
                WHERE category_id IN (
                    SELECT id FROM cost_categories WHERE is_active = 0
                )
            """)
            cleanup_summary['inactive_category_details_removed'] = cursor.rowcount
            
            conn.commit()
        
        return cleanup_summary
        
    except Exception as e:
        print(f"Error limpiando datos de costos: {e}")
        return {'error': str(e)}

def get_extras_dashboard_summary(empresa_id):
    """Obtiene resumen para dashboard del módulo EXTRAS"""
    try:
        summary = {
            'total_detailed_maintenances': 0,
            'total_cost_categories_used': 0,
            'total_detailed_amount': 0.0,
            'most_used_category': None,
            'recent_activity': [],
            'recommendations': []
        }
        
        # Mantenimientos con detalles
        detailed_maintenances = get_maintenance_records_with_costs(empresa_id)
        if not detailed_maintenances.empty:
            summary['total_detailed_maintenances'] = len(detailed_maintenances[detailed_maintenances['detail_count'] > 0])
        
        # Resumen por categorías
        category_summary = get_cost_summary_by_category_db(empresa_id)
        if not category_summary.empty:
            summary['total_cost_categories_used'] = len(category_summary)
            summary['total_detailed_amount'] = category_summary['total_cost'].sum()
            summary['most_used_category'] = category_summary.iloc[0]['category_name']
        
        # Actividad reciente
        recent_details = get_recent_cost_activity(empresa_id, days=7)
        summary['recent_activity'] = recent_details
        
        # Recomendaciones
        if summary['total_detailed_maintenances'] == 0:
            summary['recommendations'].append("Comienza detallando los costos de tus mantenimientos más recientes")
        elif summary['total_cost_categories_used'] < 3:
            summary['recommendations'].append("Considera usar más categorías para un mejor análisis")
        
        return summary
        
    except Exception as e:
        return {'error': str(e)}

def get_recent_cost_activity(empresa_id, days=7):
    """Obtiene actividad reciente de costos"""
    try:
        from datetime import date, timedelta
        fecha_limite = (date.today() - timedelta(days=days)).isoformat()
        
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT 
                    mcd.item_name,
                    cc.category_name,
                    mcd.total_cost,
                    m.name as machine_name,
                    mcd.created_at
                FROM maintenance_cost_details mcd
                JOIN cost_categories cc ON mcd.category_id = cc.id
                JOIN maintenance_records mr ON mcd.maintenance_record_id = mr.id
                JOIN machinery m ON mr.machinery_id = m.id
                WHERE m.company_id = ? AND DATE(mcd.created_at) >= ?
                ORDER BY mcd.created_at DESC
                LIMIT 10
            """, conn, params=(empresa_id, fecha_limite))
    except Exception as e:
        print(f"Error obteniendo actividad reciente: {e}")
        return pd.DataFrame()

def backup_extras_data(empresa_id):
    """Crea respaldo de datos del módulo EXTRAS"""
    try:
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'empresa_id': empresa_id,
            'version': '1.0',
            'cost_categories': [],
            'maintenance_cost_details': []
        }
        
        # Respaldar categorías
        categories = get_extras_cost_categories()
        if not categories.empty:
            backup_data['cost_categories'] = categories.to_dict('records')
        
        # Respaldar detalles de costo
        cost_details = export_cost_details_report_db(empresa_id)
        if not cost_details.empty:
            backup_data['maintenance_cost_details'] = cost_details.to_dict('records')
        
        return backup_data
        
    except Exception as e:
        return {'error': str(e)}

def restore_extras_data(backup_data, target_empresa_id):
    """Restaura datos del módulo EXTRAS desde respaldo"""
    try:
        restored_count = {
            'categories': 0,
            'cost_details': 0,
            'errors': []
        }
        
        # Restaurar categorías
        for category in backup_data.get('cost_categories', []):
            success = add_extras_cost_category(category['category_name'], category.get('description', ''))
            if success:
                restored_count['categories'] += 1
            else:
                restored_count['errors'].append(f"Error restaurando categoría: {category['category_name']}")
        
        # Nota: Los detalles de costo dependen de maintenance_records existentes
        # por lo que solo se pueden restaurar si los mantenimientos existen
        
        return restored_count
        
    except Exception as e:
        return {'error': str(e)}

# ============================================
# FUNCIÓN DE INICIALIZACIÓN AUTOMÁTICA
# ============================================

def auto_init_extras_module():
    """Inicialización automática del módulo EXTRAS"""
    try:
        success = init_extras_tables()
        if success:
            print("✅ Módulo EXTRAS inicializado en db_utils")
        else:
            print("⚠️ Error inicializando módulo EXTRAS")
        return success
    except Exception as e:
        print(f"❌ Error en auto-inicialización EXTRAS: {e}")
        return False

# Ejecutar inicialización automática si no es main
if __name__ != "__main__":
    auto_init_extras_module()

def verificar_esquema_mantenimiento():
    """Verifica el esquema real de las tablas de mantenimiento"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            print("=== VERIFICACIÓN DE ESQUEMA DE MANTENIMIENTO ===")
            
            # Verificar maintenance_records
            cursor.execute("PRAGMA table_info(maintenance_records)")
            mr_columns = cursor.fetchall()
            print("\nTabla maintenance_records:")
            for col in mr_columns:
                print(f"  {col[1]} - {col[2]} (Not Null: {bool(col[3])}, Default: {col[4]})")
            
            # Verificar maintenance_types
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_types'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(maintenance_types)")
                mt_columns = cursor.fetchall()
                print("\nTabla maintenance_types:")
                for col in mt_columns:
                    print(f"  {col[1]} - {col[2]}")
            else:
                print("\nTabla maintenance_types: NO EXISTE")
            
            # Mostrar datos de muestra
            print("\n=== DATOS DE MUESTRA ===")
            cursor.execute("SELECT * FROM maintenance_records LIMIT 2")
            sample_data = cursor.fetchall()
            
            if sample_data:
                print("Registros de muestra:")
                column_names = [col[1] for col in mr_columns]
                for i, record in enumerate(sample_data):
                    print(f"\nRegistro {i+1}:")
                    for j, value in enumerate(record):
                        print(f"  {column_names[j]}: {value}")
            else:
                print("No hay datos en maintenance_records")
            
            return True
            
    except Exception as e:
        print(f"Error verificando esquema: {e}")
        return False

# FUNCIÓN TEMPORAL PARA DIAGNOSTICAR EN STREAMLIT
def diagnosticar_en_streamlit():
    """Función para usar en Streamlit para diagnosticar el problema"""
    st.subheader("Diagnóstico de Esquema de Mantenimiento")
    
    if st.button("Ejecutar Diagnóstico Completo"):
        with st.spinner("Analizando base de datos..."):
            try:
                with get_conn() as conn:
                    cursor = conn.cursor()
                    
                    # Verificar maintenance_records
                    st.write("**Estructura de maintenance_records:**")
                    cursor.execute("PRAGMA table_info(maintenance_records)")
                    mr_columns = cursor.fetchall()
                    
                    columns_df = pd.DataFrame(mr_columns, columns=['ID', 'Nombre', 'Tipo', 'NotNull', 'Default', 'PK'])
                    st.dataframe(columns_df)
                    
                    # Verificar maintenance_types
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_types'")
                    has_mt = cursor.fetchone() is not None
                    st.write(f"**Tabla maintenance_types existe:** {has_mt}")
                    
                    # Mostrar datos de muestra
                    st.write("**Datos de muestra:**")
                    cursor.execute("SELECT * FROM maintenance_records LIMIT 3")
                    sample_data = cursor.fetchall()
                    
                    if sample_data:
                        column_names = [col[1] for col in mr_columns]
                        sample_df = pd.DataFrame(sample_data, columns=column_names)
                        st.dataframe(sample_df)
                        
                        # Análisis específico de fechas
                        st.write("**Análisis de columnas de fecha:**")
                        for col in column_names:
                            if any(word in col.lower() for word in ['date', 'time', 'at']):
                                st.write(f"- {col}: Posible columna de fecha")
                    else:
                        st.write("No hay datos en la tabla")
                        
            except Exception as e:
                st.error(f"Error en diagnóstico: {e}")

def get_maintenance_records_with_costs(empresa_id, machine_id=None, limit=None):
    """Obtiene registros de mantenimiento con información de costos detallados"""
    try:
        with get_conn() as conn:
            base_query = """
                SELECT 
                    mr.*,
                    m.name as machinery_name,
                    m.identifier as machinery_identifier,
                    COALESCE(SUM(mcd.total_cost), 0) as detailed_cost,
                    COUNT(mcd.id) as detail_count
                FROM maintenance_records mr
                JOIN machinery m ON mr.machinery_id = m.id
                LEFT JOIN maintenance_cost_details mcd ON mr.id = mcd.maintenance_record_id
                WHERE m.company_id = ?
            """
            
            params = [empresa_id]
            
            if machine_id:
                base_query += " AND mr.machinery_id = ?"
                params.append(machine_id)
            
            base_query += " GROUP BY mr.id, m.name, m.identifier"
            base_query += " ORDER BY mr.id DESC"
            
            if limit:
                base_query += " LIMIT ?"
                params.append(limit)
            
            return pd.read_sql_query(base_query, conn, params=params)
    except Exception as e:
        print(f"Error obteniendo registros de mantenimiento con costos: {e}")
        return pd.DataFrame()
    
# ============================================
# SISTEMA DE RESPALDOS MEJORADO v2.0
# Agregar estas funciones a db_utils.py
# ============================================

import sqlite3
import pandas as pd
import json
import os
import base64
from datetime import datetime
from PIL import Image
import io

def get_database_schema():
    """Obtiene el esquema completo de la base de datos"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            # Obtener todas las tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [table[0] for table in cursor.fetchall()]
            
            schema = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                schema[table] = {
                    'columns': [{'name': col[1], 'type': col[2], 'notnull': bool(col[3]), 'default': col[4]} for col in columns],
                    'exists': True
                }
            
            return schema
            
    except Exception as e:
        print(f"Error obteniendo esquema: {e}")
        return {}

def backup_table_data(table_name, conn):
    """Respaldo seguro de datos de una tabla específica"""
    try:
        # Verificar que la tabla existe
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            return None
        
        # Obtener datos
        data = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        return data.to_dict('records') if not data.empty else []
        
    except Exception as e:
        print(f"Error respaldando tabla {table_name}: {e}")
        return None

def backup_company_assets(empresa_id=None):
    """Respalda archivos de assets (logos, etc.)"""
    try:
        assets_backup = {}
        
        # Respaldar logos
        logos_dir = os.path.join("assets", "logos")
        if os.path.exists(logos_dir):
            logos_backup = {}
            
            if empresa_id:
                # Solo logos de la empresa específica
                company_info = get_company_info_complete(empresa_id)
                if company_info and company_info.get('logo_filename'):
                    logo_path = os.path.join(logos_dir, company_info['logo_filename'])
                    if os.path.exists(logo_path):
                        with open(logo_path, 'rb') as f:
                            logos_backup[company_info['logo_filename']] = base64.b64encode(f.read()).decode()
            else:
                # Todos los logos
                for filename in os.listdir(logos_dir):
                    if filename.endswith(('.jpg', '.jpeg', '.png')) and filename != '.gitkeep':
                        logo_path = os.path.join(logos_dir, filename)
                        try:
                            with open(logo_path, 'rb') as f:
                                logos_backup[filename] = base64.b64encode(f.read()).decode()
                        except Exception as e:
                            print(f"Error respaldando logo {filename}: {e}")
            
            assets_backup['logos'] = logos_backup
        
        return assets_backup
        
    except Exception as e:
        print(f"Error respaldando assets: {e}")
        return {}

def crear_respaldo_completo_v2(include_assets=True):
    """Crea respaldo completo del sistema - VERSIÓN 2.0"""
    try:
        print("Iniciando respaldo completo v2.0...")
        
        backup_data = {
            'backup_info': {
                'version': '2.0',
                'timestamp': datetime.now().isoformat(),
                'system': 'SANDI',
                'description': 'Respaldo completo del sistema SANDI v2.0',
                'include_assets': include_assets
            },
            'schema': get_database_schema(),
            'modules': {}
        }
        
        with get_conn() as conn:
            
            # =========== MÓDULO CORE ===========
            print("Respaldando módulo CORE...")
            backup_data['modules']['core'] = {}
            
            core_tables = [
                'companies',
                'company_info_extended', 
                'deletion_logs',
                'machinery',
                'machinery_deletion_logs',
                'machine_classifications',
                'company_settings'
            ]
            
            for table in core_tables:
                data = backup_table_data(table, conn)
                if data is not None:
                    backup_data['modules']['core'][table] = data
                    print(f"  ✓ {table}: {len(data) if data else 0} registros")
                else:
                    print(f"  ⚠ {table}: Tabla no existe")
            
            # =========== MÓDULO COMBUSTIBLE/FLUIDOS ===========
            print("Respaldando módulo FLUIDOS...")
            backup_data['modules']['fluidos'] = {}
            
            fluidos_tables = [
                'fluid_types',
                'company_fluid_tanks',
                'fluid_inventory_movements',
                'tank_refill_logs',
                'tank_configurations',
                'fuel_logs'  # Legacy
            ]
            
            for table in fluidos_tables:
                data = backup_table_data(table, conn)
                if data is not None:
                    backup_data['modules']['fluidos'][table] = data
                    print(f"  ✓ {table}: {len(data) if data else 0} registros")
                else:
                    print(f"  ⚠ {table}: Tabla no existe")
            
            # =========== MÓDULO MANTENIMIENTO ===========
            print("Respaldando módulo MANTENIMIENTO...")
            backup_data['modules']['mantenimiento'] = {}
            
            mantenimiento_tables = [
                'maintenance_types',
                'maintenance_schedules',
                'maintenance_records',
                'maintenance_compliance_log',
                'status_change_reasons',
                'status_history',
                'hour_meter_logs',
                'odometer_logs'
            ]
            
            for table in mantenimiento_tables:
                data = backup_table_data(table, conn)
                if data is not None:
                    backup_data['modules']['mantenimiento'][table] = data
                    print(f"  ✓ {table}: {len(data) if data else 0} registros")
                else:
                    print(f"  ⚠ {table}: Tabla no existe")
            
            # =========== MÓDULO CONTROLES ===========
            print("Respaldando módulo CONTROLES...")
            backup_data['modules']['controles'] = {}
            
            controles_tables = [
                'control_records',
                'alert_configurations',
                'daily_work_logs'
            ]
            
            for table in controles_tables:
                data = backup_table_data(table, conn)
                if data is not None:
                    backup_data['modules']['controles'][table] = data
                    print(f"  ✓ {table}: {len(data) if data else 0} registros")
                else:
                    print(f"  ⚠ {table}: Tabla no existe")
            
            # =========== MÓDULO EXTRAS ===========
            print("Respaldando módulo EXTRAS...")
            backup_data['modules']['extras'] = {}
            
            extras_tables = [
                'extras_modules',
                'cost_categories', 
                'maintenance_cost_details'
            ]
            
            for table in extras_tables:
                data = backup_table_data(table, conn)
                if data is not None:
                    backup_data['modules']['extras'][table] = data
                    print(f"  ✓ {table}: {len(data) if data else 0} registros")
                else:
                    print(f"  ⚠ {table}: Tabla no existe")
        
        # =========== ASSETS ===========
        if include_assets:
            print("Respaldando ASSETS...")
            backup_data['assets'] = backup_company_assets()
            print(f"  ✓ Logos: {len(backup_data['assets'].get('logos', {}))} archivos")
        
        # =========== ESTADÍSTICAS DEL RESPALDO ===========
        backup_stats = calcular_estadisticas_respaldo(backup_data)
        backup_data['backup_info']['statistics'] = backup_stats
        
        print(f"\n✅ Respaldo completado:")
        print(f"   - Empresas: {backup_stats['total_companies']}")
        print(f"   - Máquinas: {backup_stats['total_machines']}")
        print(f"   - Registros totales: {backup_stats['total_records']}")
        print(f"   - Tablas respaldadas: {backup_stats['tables_backed_up']}")
        
        backup_data_clean = convert_numpy_types(backup_data)
        return json.dumps(backup_data_clean, indent=2, ensure_ascii=False)
        
    except Exception as e:
        print(f"❌ Error creando respaldo: {e}")
        raise Exception(f"Error al crear respaldo completo: {str(e)}")

def crear_respaldo_empresa(empresa_id, include_assets=True):
    """Crea respaldo específico de una empresa - VERSIÓN 2.0"""
    try:
        print(f"Iniciando respaldo de empresa {empresa_id}...")
        
        # Obtener información de la empresa
        company_info = get_company_info_complete(empresa_id)
        if not company_info:
            raise Exception(f"Empresa {empresa_id} no encontrada")
        
        backup_data = {
            'backup_info': {
                'version': '2.0',
                'type': 'empresa_especifica',
                'timestamp': datetime.now().isoformat(),
                'empresa_id': empresa_id,
                'empresa_nombre': company_info['name'],
                'include_assets': include_assets
            },
            'empresa': {},
            'modules': {}
        }
        
        with get_conn() as conn:
            
            # =========== INFORMACIÓN DE EMPRESA ===========
            backup_data['empresa']['company_info'] = company_info
            
            # =========== MAQUINARIA ===========
            machinery_data = pd.read_sql_query("""
                SELECT * FROM machinery WHERE company_id = ?
            """, conn, params=(empresa_id,))
            backup_data['empresa']['machinery'] = machinery_data.to_dict('records') if not machinery_data.empty else []
            
            # =========== MÓDULO FLUIDOS ===========
            backup_data['modules']['fluidos'] = {}
            
            # Tanques de la empresa
            tanks_data = pd.read_sql_query("""
                SELECT * FROM company_fluid_tanks WHERE company_id = ?
            """, conn, params=(empresa_id,))
            backup_data['modules']['fluidos']['tanks'] = tanks_data.to_dict('records') if not tanks_data.empty else []
            
            # Movimientos de fluidos
            movements_data = pd.read_sql_query("""
                SELECT fim.* FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                WHERE cft.company_id = ?
            """, conn, params=(empresa_id,))
            backup_data['modules']['fluidos']['movements'] = movements_data.to_dict('records') if not movements_data.empty else []
            
            # Logs de combustible legacy
            fuel_logs_data = pd.read_sql_query("""
                SELECT fl.* FROM fuel_logs fl
                JOIN machinery m ON fl.machinery_id = m.id
                WHERE m.company_id = ?
            """, conn, params=(empresa_id,))
            backup_data['modules']['fluidos']['fuel_logs'] = fuel_logs_data.to_dict('records') if not fuel_logs_data.empty else []
            
            # =========== MÓDULO MANTENIMIENTO ===========
            backup_data['modules']['mantenimiento'] = {}
            
            # Registros de mantenimiento
            maintenance_data = pd.read_sql_query("""
                SELECT mr.* FROM maintenance_records mr
                JOIN machinery m ON mr.machinery_id = m.id
                WHERE m.company_id = ?
            """, conn, params=(empresa_id,))
            backup_data['modules']['mantenimiento']['records'] = maintenance_data.to_dict('records') if not maintenance_data.empty else []
            
            # Programaciones de mantenimiento
            schedules_data = pd.read_sql_query("""
                SELECT ms.* FROM maintenance_schedules ms
                JOIN machinery m ON ms.machinery_id = m.id
                WHERE m.company_id = ?
            """, conn, params=(empresa_id,))
            backup_data['modules']['mantenimiento']['schedules'] = schedules_data.to_dict('records') if not schedules_data.empty else []
            
            # =========== MÓDULO EXTRAS ===========
            backup_data['modules']['extras'] = {}
            
            # Detalles de costos
            cost_details_data = pd.read_sql_query("""
                SELECT mcd.* FROM maintenance_cost_details mcd
                JOIN maintenance_records mr ON mcd.maintenance_record_id = mr.id
                JOIN machinery m ON mr.machinery_id = m.id
                WHERE m.company_id = ?
            """, conn, params=(empresa_id,))
            backup_data['modules']['extras']['cost_details'] = cost_details_data.to_dict('records') if not cost_details_data.empty else []
        
        # =========== ASSETS ===========
        if include_assets:
            backup_data['assets'] = backup_company_assets(empresa_id)
        
        # =========== ESTADÍSTICAS ===========
        backup_stats = {
            'total_machines': len(backup_data['empresa']['machinery']),
            'total_tanks': len(backup_data['modules']['fluidos']['tanks']),
            'total_maintenances': len(backup_data['modules']['mantenimiento']['records']),
            'total_cost_details': len(backup_data['modules']['extras']['cost_details']),
            'has_logo': bool(backup_data.get('assets', {}).get('logos'))
        }
        backup_data['backup_info']['statistics'] = backup_stats
        
        print(f"✅ Respaldo de empresa completado:")
        print(f"   - Máquinas: {backup_stats['total_machines']}")
        print(f"   - Mantenimientos: {backup_stats['total_maintenances']}")
        print(f"   - Tanques: {backup_stats['total_tanks']}")
        
        backup_data_clean = convert_numpy_types(backup_data)
        return json.dumps(backup_data_clean, indent=2, ensure_ascii=False)
        
    except Exception as e:
        print(f"❌ Error creando respaldo de empresa: {e}")
        raise Exception(f"Error al crear respaldo de empresa: {str(e)}")

def restaurar_desde_respaldo(backup_data_json, modo='completo', target_empresa_id=None):
    """Restaura desde respaldo v2.0 con validaciones y opciones"""
    try:
        backup_data = json.loads(backup_data_json) if isinstance(backup_data_json, str) else backup_data_json
        
        # =========== VALIDACIONES ===========
        if 'backup_info' not in backup_data:
            raise Exception("Formato de respaldo inválido")
        
        backup_version = backup_data['backup_info'].get('version', '1.0')
        backup_type = backup_data['backup_info'].get('type', 'completo')
        
        print(f"Iniciando restauración desde respaldo v{backup_version} (tipo: {backup_type})")
        
        # Validar compatibilidad
        if backup_version not in ['1.0', '2.0']:
            raise Exception(f"Versión de respaldo no compatible: {backup_version}")
        
        restauration_log = {
            'timestamp': datetime.now().isoformat(),
            'backup_version': backup_version,
            'modo': modo,
            'tablas_restauradas': 0,
            'registros_restaurados': 0,
            'errores': []
        }
        
        with get_conn() as conn:
            # Deshabilitar foreign keys temporalmente
            conn.execute("PRAGMA foreign_keys = OFF")
            
            if modo == 'completo' and backup_type != 'empresa_especifica':
                # =========== RESTAURACIÓN COMPLETA ===========
                print("Realizando restauración completa...")
                
                # Limpiar base de datos
                print("Limpiando base de datos...")
                limpiar_base_datos_completa(conn)
                
                # Restaurar módulos
                for module_name, module_data in backup_data.get('modules', {}).items():
                    print(f"Restaurando módulo {module_name}...")
                    
                    for table_name, table_data in module_data.items():
                        try:
                            restaurar_tabla(conn, table_name, table_data)
                            restauration_log['tablas_restauradas'] += 1
                            restauration_log['registros_restaurados'] += len(table_data) if table_data else 0
                            print(f"  ✓ {table_name}: {len(table_data) if table_data else 0} registros")
                        except Exception as e:
                            error_msg = f"Error restaurando {table_name}: {str(e)}"
                            restauration_log['errores'].append(error_msg)
                            print(f"  ❌ {error_msg}")
                
                # Restaurar assets
                if backup_data.get('assets'):
                    print("Restaurando assets...")
                    restaurar_assets(backup_data['assets'])
            
            elif backup_type == 'empresa_especifica':
                # =========== RESTAURACIÓN DE EMPRESA ESPECÍFICA ===========
                print("Realizando restauración de empresa específica...")
                
                if target_empresa_id is None:
                    # Crear nueva empresa
                    empresa_data = backup_data['empresa']['company_info']
                    original_name = empresa_data['name']
                    unique_name = get_unique_company_name(original_name)

                    success = add_company(unique_name)
                    if not success:
                        raise Exception("Error creando empresa")
                    
                    # Obtener ID de nueva empresa
                    empresas = list_companies()
                    nueva_empresa = empresas[empresas['name'] == unique_name]  # Usar unique_name en lugar de empresa_data['name']
                    if nueva_empresa.empty:
                        raise Exception("Error obteniendo ID de nueva empresa")
                    target_empresa_id = nueva_empresa.iloc[0]['id']

                    print(f"Empresa creada con nombre: {unique_name}")
                
                # Restaurar información de empresa
                company_info = backup_data['empresa']['company_info']
                company_info['id'] = target_empresa_id  # Asegurar ID correcto
                update_company_info_complete(target_empresa_id, company_info)
                
                # Restaurar maquinaria
                for machine_data in backup_data['empresa']['machinery']:
                    restaurar_maquina(conn, machine_data, target_empresa_id)
                
                # Restaurar módulos específicos de la empresa
                for module_name, module_data in backup_data.get('modules', {}).items():
                    restaurar_modulo_empresa(conn, module_name, module_data, target_empresa_id)
                
                # Restaurar assets específicos
                if backup_data.get('assets'):
                    restaurar_assets_empresa(backup_data['assets'], target_empresa_id)
            
            # Reactivar foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()
        
        print(f"✅ Restauración completada:")
        print(f"   - Tablas restauradas: {restauration_log['tablas_restauradas']}")
        print(f"   - Registros restaurados: {restauration_log['registros_restaurados']}")
        if restauration_log['errores']:
            print(f"   - Errores: {len(restauration_log['errores'])}")
        
        return True, restauration_log
        
    except Exception as e:
        print(f"❌ Error en restauración: {e}")
        return False, {'error': str(e)}

def calcular_estadisticas_respaldo(backup_data):
    """Calcula estadísticas del respaldo"""
    try:
        stats = {
            'total_companies': 0,
            'total_machines': 0,
            'total_records': 0,
            'tables_backed_up': 0,
            'modules_included': []
        }
        
        # Contar desde módulos
        for module_name, module_data in backup_data.get('modules', {}).items():
            stats['modules_included'].append(module_name)
            
            for table_name, table_data in module_data.items():
                if table_data:
                    stats['tables_backed_up'] += 1
                    stats['total_records'] += len(table_data)
                    
                    # Conteos específicos
                    if table_name == 'companies':
                        stats['total_companies'] = len(table_data)
                    elif table_name == 'machinery':
                        stats['total_machines'] = len(table_data)
        
        return stats
        
    except Exception as e:
        print(f"Error calculando estadísticas: {e}")
        return {}

def restaurar_tabla(conn, table_name, table_data):
    """Restaura datos de una tabla específica"""
    try:
        if not table_data:
            return
        
        # Verificar que la tabla existe
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            print(f"  ⚠ Tabla {table_name} no existe, omitiendo...")
            return
        
        # Obtener columnas de la tabla
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        available_columns = [col[1] for col in columns_info]
        
        # Preparar datos para inserción
        for record in table_data:
            # Filtrar solo columnas que existen en la tabla actual
            filtered_record = {k: v for k, v in record.items() if k in available_columns}
            
            if filtered_record:
                columns = list(filtered_record.keys())
                values = list(filtered_record.values())
                placeholders = ','.join(['?' for _ in values])
                
                query = f"INSERT OR REPLACE INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
                cursor.execute(query, values)
        
    except Exception as e:
        raise Exception(f"Error restaurando tabla {table_name}: {str(e)}")

def limpiar_base_datos_completa(conn):
    """Limpia toda la base de datos manteniendo estructura"""
    try:
        # Obtener todas las tablas
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'")
        tables = [table[0] for table in cursor.fetchall()]
        
        # Limpiar todas las tablas
        for table in tables:
            try:
                cursor.execute(f"DELETE FROM {table}")
            except Exception as e:
                print(f"Error limpiando tabla {table}: {e}")
        
        # Reiniciar secuencias
        cursor.execute("DELETE FROM sqlite_sequence")
        
    except Exception as e:
        raise Exception(f"Error limpiando base de datos: {str(e)}")

def restaurar_assets(assets_data):
    """Restaura archivos de assets"""
    try:
        logos_data = assets_data.get('logos', {})
        
        if logos_data:
            # Crear directorio si no existe
            logos_dir = os.path.join("assets", "logos")
            os.makedirs(logos_dir, exist_ok=True)
            
            for filename, base64_data in logos_data.items():
                try:
                    # Decodificar y guardar
                    image_data = base64.b64decode(base64_data)
                    logo_path = os.path.join(logos_dir, filename)
                    
                    with open(logo_path, 'wb') as f:
                        f.write(image_data)
                    
                    print(f"  ✓ Logo restaurado: {filename}")
                    
                except Exception as e:
                    print(f"  ❌ Error restaurando logo {filename}: {e}")
        
    except Exception as e:
        print(f"Error restaurando assets: {e}")

def validar_respaldo_antes_restaurar(backup_data_json):
    """Valida un respaldo antes de restaurarlo"""
    try:
        backup_data = json.loads(backup_data_json) if isinstance(backup_data_json, str) else backup_data_json
        
        validation_result = {
            'is_valid': True,
            'version': None,
            'type': None,
            'warnings': [],
            'errors': [],
            'statistics': {}
        }
        
        # Verificar estructura básica
        if 'backup_info' not in backup_data:
            validation_result['errors'].append("Estructura de respaldo inválida")
            validation_result['is_valid'] = False
            return validation_result
        
        backup_info = backup_data['backup_info']
        validation_result['version'] = backup_info.get('version', 'unknown')
        validation_result['type'] = backup_info.get('type', 'completo')
        
        # Verificar versión
        if validation_result['version'] not in ['1.0', '2.0']:
            validation_result['warnings'].append(f"Versión {validation_result['version']} no reconocida")
        
        # Verificar módulos
        modules = backup_data.get('modules', {})
        if not modules:
            validation_result['warnings'].append("No se encontraron módulos en el respaldo")
        
        # Calcular estadísticas
        validation_result['statistics'] = calcular_estadisticas_respaldo(backup_data)
        
        # Verificar assets
        if backup_data.get('assets', {}).get('logos'):
            validation_result['statistics']['logos_count'] = len(backup_data['assets']['logos'])
        
        return validation_result
        
    except Exception as e:
        return {
            'is_valid': False,
            'errors': [f"Error validando respaldo: {str(e)}"],
            'version': None,
            'type': None
        }

# ============================================
# FUNCIONES DE MIGRACIÓN ENTRE VERSIONES
# ============================================

def migrar_respaldo_v1_a_v2(backup_v1_json):
    """Migra un respaldo v1.0 al formato v2.0"""
    try:
        backup_v1 = json.loads(backup_v1_json) if isinstance(backup_v1_json, str) else backup_v1_json
        
        print("Migrando respaldo v1.0 a v2.0...")
        
        # Crear estructura v2.0
        backup_v2 = {
            'backup_info': {
                'version': '2.0',
                'timestamp': datetime.now().isoformat(),
                'system': 'SANDI',
                'migrated_from': '1.0',
                'original_timestamp': backup_v1.get('timestamp', ''),
                'description': 'Respaldo migrado de v1.0 a v2.0'
            },
            'modules': {
                'core': {},
                'fluidos': {},
                'mantenimiento': {},
                'controles': {},
                'extras': {}
            },
            'assets': {}
        }
        
        # Migrar datos del formato v1.0
        if 'companies' in backup_v1:
            backup_v2['modules']['core']['companies'] = backup_v1['companies']
        
        if 'machinery' in backup_v1:
            backup_v2['modules']['core']['machinery'] = backup_v1['machinery']
        
        if 'fuel_logs' in backup_v1:
            backup_v2['modules']['fluidos']['fuel_logs'] = backup_v1['fuel_logs']
        
        if 'maintenance_records' in backup_v1:
            backup_v2['modules']['mantenimiento']['maintenance_records'] = backup_v1['maintenance_records']
        
        if 'machine_classifications' in backup_v1:
            backup_v2['modules']['core']['machine_classifications'] = backup_v1['machine_classifications']
        
        print("✅ Migración completada")
        return json.dumps(backup_v2, indent=2, ensure_ascii=False)
        
    except Exception as e:
        raise Exception(f"Error migrando respaldo: {str(e)}")

def get_backup_info_summary(backup_data_json):
    """Obtiene resumen informativo de un respaldo"""
    try:
        backup_data = json.loads(backup_data_json) if isinstance(backup_data_json, str) else backup_data_json
        
        summary = {
            'version': backup_data.get('backup_info', {}).get('version', 'unknown'),
            'timestamp': backup_data.get('backup_info', {}).get('timestamp', ''),
            'type': backup_data.get('backup_info', {}).get('type', 'completo'),
            'system': backup_data.get('backup_info', {}).get('system', ''),
            'modules': list(backup_data.get('modules', {}).keys()),
            'has_assets': bool(backup_data.get('assets')),
            'size_estimate': len(json.dumps(backup_data)) if backup_data else 0
        }
        
        # Estadísticas si están disponibles
        if 'statistics' in backup_data.get('backup_info', {}):
            summary.update(backup_data['backup_info']['statistics'])
        
        return summary
        
    except Exception as e:
        return {'error': f"Error obteniendo resumen: {str(e)}"}

def restaurar_maquina(conn, machine_data, new_empresa_id):
    """Restaura una máquina específica con nuevo ID de empresa"""
    try:
        # Actualizar company_id al nuevo
        machine_data = machine_data.copy()
        old_machine_id = machine_data.get('id')
        machine_data['company_id'] = new_empresa_id
        
        # Insertar máquina
        columns = list(machine_data.keys())
        values = list(machine_data.values())
        placeholders = ','.join(['?' for _ in values])
        
        query = f"INSERT OR REPLACE INTO machinery ({','.join(columns)}) VALUES ({placeholders})"
        cursor = conn.cursor()
        cursor.execute(query, values)
        
        # Obtener nuevo ID si fue insertado
        new_machine_id = cursor.lastrowid if cursor.lastrowid else machine_data.get('id')
        
        return new_machine_id, old_machine_id
        
    except Exception as e:
        print(f"Error restaurando máquina: {e}")
        return None, None

def restaurar_modulo_empresa(conn, module_name, module_data, empresa_id):
    """Restaura datos de módulos específicos para una empresa"""
    try:
        if module_name == 'fluidos':
            # Restaurar tanques
            for tank_data in module_data.get('tanks', []):
                tank_data = tank_data.copy()
                tank_data['company_id'] = empresa_id
                restaurar_tabla(conn, 'company_fluid_tanks', [tank_data])
            
            # Restaurar movimientos (requiere mapeo de IDs)
            for movement_data in module_data.get('movements', []):
                # Los movimientos requieren que los tanques ya existan
                restaurar_tabla(conn, 'fluid_inventory_movements', [movement_data])
            
            # Restaurar fuel_logs legacy
            for fuel_log in module_data.get('fuel_logs', []):
                # Los fuel_logs ya tienen machinery_id correcto
                restaurar_tabla(conn, 'fuel_logs', [fuel_log])
        
        elif module_name == 'mantenimiento':
            # Restaurar registros de mantenimiento
            for maintenance_data in module_data.get('records', []):
                restaurar_tabla(conn, 'maintenance_records', [maintenance_data])
            
            # Restaurar programaciones
            for schedule_data in module_data.get('schedules', []):
                restaurar_tabla(conn, 'maintenance_schedules', [schedule_data])
        
        elif module_name == 'extras':
            # Restaurar detalles de costos
            for cost_detail in module_data.get('cost_details', []):
                restaurar_tabla(conn, 'maintenance_cost_details', [cost_detail])
        
        print(f"Módulo {module_name} restaurado para empresa {empresa_id}")
        
    except Exception as e:
        print(f"Error restaurando módulo {module_name}: {e}")

def restaurar_assets_empresa(assets_data, empresa_id):
    """Restaura assets específicos de una empresa"""
    try:
        logos_data = assets_data.get('logos', {})
        
        # Buscar logo específico de la empresa
        for filename, base64_data in logos_data.items():
            if f"empresa_{empresa_id}" in filename or filename.startswith(f"logo_empresa_{empresa_id}"):
                try:
                    # Decodificar y guardar
                    image_data = base64.b64decode(base64_data)
                    logos_dir = os.path.join("assets", "logos")
                    os.makedirs(logos_dir, exist_ok=True)
                    
                    # Generar nuevo nombre si es necesario
                    new_filename = f"logo_empresa_{empresa_id}.jpg"
                    logo_path = os.path.join(logos_dir, new_filename)
                    
                    with open(logo_path, 'wb') as f:
                        f.write(image_data)
                    
                    # Actualizar base de datos
                    update_company_info_complete(empresa_id, {'logo_filename': new_filename})
                    
                    print(f"Logo restaurado para empresa {empresa_id}")
                    break
                    
                except Exception as e:
                    print(f"Error restaurando logo para empresa {empresa_id}: {e}")
        
    except Exception as e:
        print(f"Error restaurando assets de empresa: {e}")

def validar_respaldo_antes_restaurar(backup_data_json):
    """Valida un respaldo antes de restaurarlo"""
    try:
        backup_data = json.loads(backup_data_json) if isinstance(backup_data_json, str) else backup_data_json
        
        validation_result = {
            'is_valid': True,
            'version': None,
            'type': None,
            'warnings': [],
            'errors': [],
            'statistics': {}
        }
        
        # Verificar estructura básica
        if 'backup_info' not in backup_data:
            validation_result['errors'].append("Estructura de respaldo inválida")
            validation_result['is_valid'] = False
            return validation_result
        
        backup_info = backup_data['backup_info']
        validation_result['version'] = backup_info.get('version', 'unknown')
        validation_result['type'] = backup_info.get('type', 'completo')
        
        # Verificar versión
        if validation_result['version'] not in ['1.0', '2.0']:
            validation_result['warnings'].append(f"Versión {validation_result['version']} no reconocida")
        
        # Verificar módulos
        modules = backup_data.get('modules', {})
        if not modules:
            validation_result['warnings'].append("No se encontraron módulos en el respaldo")
        
        # Calcular estadísticas
        validation_result['statistics'] = calcular_estadisticas_respaldo(backup_data)
        
        # Verificar assets
        if backup_data.get('assets', {}).get('logos'):
            validation_result['statistics']['logos_count'] = len(backup_data['assets']['logos'])
        
        return validation_result
        
    except Exception as e:
        return {
            'is_valid': False,
            'errors': [f"Error validando respaldo: {str(e)}"],
            'version': None,
            'type': None
        }
    
def get_unique_company_name(base_name):
    """Genera un nombre único para empresa agregando sufijo si es necesario"""
    try:
        with get_conn() as conn:
            # Verificar si el nombre base existe
            existing = pd.read_sql_query("""
                SELECT name FROM companies WHERE name = ?
            """, conn, params=(base_name,))
            
            if existing.empty:
                return base_name
            
            # Si existe, buscar un nombre único
            counter = 1
            while True:
                new_name = f"{base_name} (copia {counter})"
                existing = pd.read_sql_query("""
                    SELECT name FROM companies WHERE name = ?
                """, conn, params=(new_name,))
                
                if existing.empty:
                    return new_name
                
                counter += 1
                
                # Evitar bucle infinito
                if counter > 100:
                    import random
                    random_suffix = random.randint(1000, 9999)
                    return f"{base_name} (copia {random_suffix})"
                    
    except Exception as e:
        # Fallback si hay error
        from datetime import datetime
        timestamp = datetime.now().strftime("%H%M%S")

        return f"{base_name} (copia {timestamp})"

def initialize_backup_system():
    """Inicializar sistema de backup con GitHub"""
    global BACKUP_INITIALIZED
    
    if not GITHUB_BACKUP_AVAILABLE:
        print("⚠️ Sistema de backup no disponible")
        return False
    
    if BACKUP_INITIALIZED:
        print("ℹ️ Sistema de backup ya inicializado")
        return True
    
    try:
        # Probar conexión con GitHub
        success, message = test_github_connection()
        if not success:
            print(f"⚠️ No se pudo conectar con GitHub: {message}")
            return False
        
        # Configurar auto-backup si está habilitado
        import streamlit as st
        backup_enabled = st.secrets.get("database", {}).get("backup_on_startup", True)
        
        if backup_enabled and os.path.exists(DATABASE_PATH):
            # Hacer backup inicial al arrancar
            initial_success, initial_message = github_manual_backup(DATABASE_PATH)
            if initial_success:
                print("✅ Backup inicial completado")
            else:
                print(f"⚠️ Backup inicial falló: {initial_message}")
            
            # Configurar auto-backup
            interval = st.secrets.get("app_config", {}).get("backup_interval_minutes", 30)
            if setup_github_auto_backup(DATABASE_PATH, interval):
                print(f"✅ Auto-backup configurado (cada {interval} minutos)")
            else:
                print("⚠️ Auto-backup no pudo configurarse")
        
        BACKUP_INITIALIZED = True
        return True
        
    except Exception as e:
        print(f"❌ Error inicializando sistema de backup: {str(e)}")
        return False

def manual_backup_database():
    """Realizar backup manual de la base de datos"""
    if not GITHUB_BACKUP_AVAILABLE:
        return False, "Sistema de backup no disponible"
    
    try:
        if not os.path.exists(DATABASE_PATH):
            return False, "Base de datos no encontrada"
        
        success, message = github_manual_backup(DATABASE_PATH)
        return success, message
        
    except Exception as e:
        return False, f"Error en backup manual: {str(e)}"

def restore_database_from_backup(backup_info):
    """Restaurar base de datos desde un backup específico"""
    if not GITHUB_BACKUP_AVAILABLE:
        return False, "Sistema de backup no disponible"
    
    try:
        success, message = restore_from_github(backup_info, DATABASE_PATH)
        return success, message
        
    except Exception as e:
        return False, f"Error restaurando backup: {str(e)}"

def get_available_backups():
    """Obtener lista de backups disponibles"""
    if not GITHUB_BACKUP_AVAILABLE:
        return []
    
    try:
        return get_github_backups()
    except Exception as e:
        print(f"❌ Error obteniendo backups: {str(e)}")
        return []

def get_backup_status():
    """Obtener estado del sistema de backup"""
    if not GITHUB_BACKUP_AVAILABLE:
        return {
            "available": False,
            "connected": False,
            "message": "GitHub backup no disponible"
        }
    
    try:
        connected, conn_message = test_github_connection()
        backups = get_available_backups()
        
        return {
            "available": True,
            "connected": connected,
            "last_backup": backups[0]["name"] if backups else None,
            "total_backups": len(backups),
            "auto_backup_active": BACKUP_INITIALIZED,
            "message": conn_message
        }
        
    except Exception as e:
        return {
            "available": True,
            "connected": False,
            "message": f"Error verificando estado: {str(e)}"
        }

# MODIFICAR tu función existente optimize_db_connection() o crear una nueva función de inicialización:
def setup_database_with_backup():
    """Setup completo de la base de datos con backup"""
    try:
        # Tu código existente de inicialización aquí
        # optimize_db_connection()
        # auto_migrate()
        # etc...
        
        # Después de tu inicialización normal, agregar:
        initialize_backup_system()
        
        print("✅ Base de datos y sistema de backup inicializados")
        return True
        
    except Exception as e:
        print(f"❌ Error en setup: {str(e)}")
        return False

# ============================================
# SISTEMA DE BACKUP AUTOMÁTICO PARA OPERACIONES CRÍTICAS
# ============================================

def trigger_backup_after_critical_operation(operation_name="operación"):
    """Dispara backup automático después de operaciones críticas"""
    try:
        from github_backup_utils import github_manual_backup
        import os
        
        if os.path.exists(DB_PATH):
            success, message = github_manual_backup(DB_PATH)
            if success:
                print(f"✅ Backup automático después de {operation_name}")
            else:
                print(f"⚠️ Backup falló después de {operation_name}: {message}")
    except Exception as e:
        print(f"⚠️ Error en backup automático: {e}")

def add_company_with_backup(name: str):
    """Versión con backup automático de add_company"""
    try:
        result = add_company(name)
        if result:
            trigger_backup_after_critical_operation("crear empresa")
        return result
    except Exception as e:
        print(f"Error en add_company_with_backup: {e}")
        return False

def add_machinery_with_backup(*args, **kwargs):
    """Versión con backup automático de add_machinery"""
    try:
        result = add_machinery_extended(*args, **kwargs)
        if result:
            trigger_backup_after_critical_operation("agregar máquina")
        return result
    except Exception as e:
        print(f"Error en add_machinery_with_backup: {e}")
        return False

def delete_machinery_with_backup(machinery_id, deleted_by="admin"):
    """Versión con backup automático de delete_machinery"""
    try:
        result = delete_machinery(machinery_id, deleted_by)
        if result:
            trigger_backup_after_critical_operation("eliminar máquina")
        return result
    except Exception as e:
        print(f"Error en delete_machinery_with_backup: {e}")
        return False

def update_machinery_with_backup(machinery_id, **kwargs):
    """Versión con backup automático de update_machinery"""
    try:
        result = update_machinery_extended(machinery_id, **kwargs)
        if result:
            trigger_backup_after_critical_operation("actualizar máquina")
        return result
    except Exception as e:
        print(f"Error en update_machinery_with_backup: {e}")
        return False

def add_fuel_log_with_backup(*args, **kwargs):
    """Versión con backup automático de add_fuel_log"""
    try:
        result = add_fuel_log(*args, **kwargs)
        if result:
            trigger_backup_after_critical_operation("registrar combustible")
        return result
    except Exception as e:
        print(f"Error en add_fuel_log_with_backup: {e}")
        return "Error registrando combustible"

def get_backup_status():
    """Obtiene el estado del sistema de backup"""
    try:
        from github_backup_utils import test_github_connection, get_github_backups
        
        # Probar conexión
        connected, conn_message = test_github_connection()
        
        # Obtener backups disponibles
        backups = get_github_backups() if connected else []
        
        return {
            "connected": connected,
            "message": conn_message,
            "total_backups": len(backups),
            "last_backup": backups[0]["name"] if backups else None,
            "last_backup_time": backups[0]["name"].split("_")[-1].replace(".db", "") if backups else None
        }
    except Exception as e:
        return {
            "connected": False,
            "message": f"Error: {str(e)}",
            "total_backups": 0,
            "last_backup": None,
            "last_backup_time": None
        }

def manual_backup_now():
    """Ejecuta backup manual inmediato"""
    try:
        from github_backup_utils import github_manual_backup
        import os
        
        if not os.path.exists(DB_PATH):
            return False, "Base de datos no encontrada"
        
        success, message = github_manual_backup(DB_PATH)
        return success, message
    except Exception as e:
        return False, f"Error: {str(e)}"

def restore_from_cloud():
    """Restaura la base de datos desde el último backup en la nube"""
    try:
        from github_backup_utils import get_github_backups, restore_from_github
        
        backups = get_github_backups()
        if not backups:
            return False, "No hay backups disponibles"
        
        # Crear backup local antes de restaurar
        import shutil
        from datetime import datetime
        
        if os.path.exists(DB_PATH):
            backup_local = f"{DB_PATH}.backup_local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(DB_PATH, backup_local)
        
        # Restaurar desde la nube
        success, message = restore_from_github(backups[0], DB_PATH)
        return success, message
        
    except Exception as e:
        return False, f"Error: {str(e)}"

def restore_database_from_backup(backup_info):
    """Restaura la base de datos desde un backup específico"""
    if not GITHUB_BACKUP_AVAILABLE:
        return False, "Sistema de backup no disponible"
    
    try:
        # Crear backup local antes de restaurar (medida de seguridad)
        import shutil
        from datetime import datetime
        
        if os.path.exists(DB_PATH):
            backup_local = f"{DB_PATH}.backup_local_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(DB_PATH, backup_local)
            print(f"💾 Backup de seguridad local creado: {backup_local}")
        
        # Restaurar desde la nube usando el backup específico
        success, message = restore_from_github(backup_info, DB_PATH)
        return success, message
        
    except Exception as e:
        return False, f"Error restaurando backup: {str(e)}"
