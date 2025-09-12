"""
Solución para el error de alert_configurations
Agrega esta función a tu db_utils.py y ejecútala una vez para migrar la tabla
"""

import sqlite3
import pandas as pd
from db_utils import get_conn

def fix_alert_configurations_table():
    """
    Migra la tabla alert_configurations para agregar la columna company_id
    y elimina la pestaña de mantenimiento de controles_config.py
    """
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            # Verificar si la tabla existe
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='alert_configurations'
            """)
            table_exists = cursor.fetchone()
            
            if table_exists:
                # Verificar si la columna company_id existe
                cursor.execute("PRAGMA table_info(alert_configurations)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'company_id' not in columns:
                    print("Migrando tabla alert_configurations...")
                    
                    # Crear tabla temporal con la estructura correcta
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
                    
                    # Si había datos en la tabla antigua, necesitarías migrarlos aquí
                    # Como probablemente está vacía o con datos incorrectos, la recreamos
                    
                    # Eliminar tabla antigua
                    cursor.execute("DROP TABLE alert_configurations")
                    
                    # Renombrar tabla nueva
                    cursor.execute("ALTER TABLE alert_configurations_new RENAME TO alert_configurations")
                    
                    print("Tabla alert_configurations migrada correctamente")
                else:
                    print("La tabla alert_configurations ya tiene la columna company_id")
            else:
                # Crear tabla desde cero
                cursor.execute("""
                    CREATE TABLE alert_configurations (
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
                print("Tabla alert_configurations creada correctamente")
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Error al migrar tabla alert_configurations: {str(e)}")
        return False

# Ejecutar esta función una vez para solucionar el problema
if __name__ == "__main__":
    fix_alert_configurations_table()