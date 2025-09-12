# diagnostic_tools.py - Herramientas avanzadas de diagnóstico

import sqlite3
import pandas as pd
import time
from contextlib import contextmanager
from db_utils import get_conn, DB_PATH

def diagnose_database_issues():
    """Diagnóstico completo de problemas de base de datos"""
    print("\n" + "="*50)
    print("DIAGNÓSTICO COMPLETO DE BASE DE DATOS")
    print("="*50)
    
    # 1. Verificar integridad de la base de datos
    print("\n1. VERIFICANDO INTEGRIDAD DE BASE DE DATOS...")
    try:
        with get_conn() as conn:
            result = conn.execute("PRAGMA integrity_check;").fetchone()
            print(f"   Integridad: {result[0]}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # 2. Verificar configuración actual
    print("\n2. CONFIGURACIÓN ACTUAL DE SQLITE...")
    try:
        with get_conn() as conn:
            configs = [
                "journal_mode", "synchronous", "cache_size", 
                "temp_store", "locking_mode", "wal_autocheckpoint"
            ]
            for config in configs:
                result = conn.execute(f"PRAGMA {config};").fetchone()
                print(f"   {config}: {result[0] if result else 'N/A'}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # 3. Verificar bloqueos activos
    print("\n3. VERIFICANDO BLOQUEOS...")
    check_database_locks()
    
    # 4. Verificar estructura de tablas críticas
    print("\n4. ESTRUCTURA DE TABLAS...")
    verify_table_structure()
    
    # 5. Test de escritura
    print("\n5. TEST DE ESCRITURA...")
    test_database_write()
    
    print("\n" + "="*50)
    print("DIAGNÓSTICO COMPLETADO")
    print("="*50 + "\n")

def check_database_locks():
    """Verifica si hay bloqueos en la base de datos"""
    try:
        # Intentar conexión rápida
        conn = sqlite3.connect(DB_PATH, timeout=1)
        
        # Verificar si hay escritores activos
        result = conn.execute("BEGIN IMMEDIATE;")
        conn.execute("ROLLBACK;")
        conn.close()
        print("   Sin bloqueos detectados")
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            print("   ⚠️ BASE DE DATOS BLOQUEADA")
            print("   Posibles causas:")
            print("     - Transacción larga sin commit")
            print("     - Proceso colgado")
            print("     - Conexión no cerrada correctamente")
        else:
            print(f"   Error de operación: {e}")
    except Exception as e:
        print(f"   Error inesperado: {e}")

def verify_table_structure():
    """Verifica la estructura de tablas críticas"""
    critical_tables = [
        "company_fluid_tanks",
        "fluid_types", 
        "tank_refill_logs"
    ]
    
    try:
        with get_conn() as conn:
            for table in critical_tables:
                print(f"\n   Tabla: {table}")
                
                # Verificar existencia
                exists = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table,)).fetchone()
                
                if not exists:
                    print(f"     ❌ NO EXISTE")
                    continue
                
                # Mostrar estructura
                columns = conn.execute(f"PRAGMA table_info({table});").fetchall()
                print(f"     Columnas ({len(columns)}):")
                for col in columns:
                    print(f"       - {col[1]} ({col[2]})" + (" NOT NULL" if col[3] else ""))
                
                # Contar registros
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"     Registros: {count}")
                
    except Exception as e:
        print(f"   Error verificando estructura: {e}")

def test_database_write():
    """Test de escritura para identificar problemas"""
    print("   Ejecutando test de escritura...")
    
    test_table = "diagnostic_test_temp"
    
    try:
        with get_conn() as conn:
            # Crear tabla temporal
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {test_table} (
                    id INTEGER PRIMARY KEY,
                    test_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Test de INSERT
            start_time = time.time()
            conn.execute(f"""
                INSERT INTO {test_table} (test_data) 
                VALUES ('test_write_operation')
            """)
            conn.commit()
            write_time = time.time() - start_time
            
            # Test de SELECT
            start_time = time.time()
            result = conn.execute(f"SELECT * FROM {test_table} ORDER BY id DESC LIMIT 1").fetchone()
            read_time = time.time() - start_time
            
            # Limpiar
            conn.execute(f"DROP TABLE {test_table}")
            conn.commit()
            
            print(f"   ✅ Escritura exitosa (tiempo: {write_time:.3f}s)")
            print(f"   ✅ Lectura exitosa (tiempo: {read_time:.3f}s)")
            print(f"   Datos recuperados: {result[1] if result else 'None'}")
            
    except Exception as e:
        print(f"   ❌ Error en test de escritura: {e}")

def force_unlock_database():
    """Fuerza el desbloqueo de la base de datos (usar con precaución)"""
    print("⚠️ FORZANDO DESBLOQUEO DE BASE DE DATOS...")
    print("ADVERTENCIA: Esto puede causar corrupción si hay transacciones activas")
    
    try:
        # Método 1: Checkpoint WAL
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA wal_checkpoint(RESTART);")
            print("   Checkpoint WAL ejecutado")
        
        # Método 2: Vacuum (reorganiza la BD)
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("VACUUM;")
            print("   VACUUM ejecutado")
        
        print("   ✅ Desbloqueo completado")
        
    except Exception as e:
        print(f"   ❌ Error en desbloqueo: {e}")

def repair_tank_data(empresa_id):
    """Repara datos inconsistentes de tanques"""
    print(f"\n🔧 REPARANDO DATOS DE TANQUES PARA EMPRESA {empresa_id}...")
    
    try:
        with get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            
            # 1. Corregir niveles negativos
            negative_fix = conn.execute("""
                UPDATE company_fluid_tanks 
                SET current_level = 0 
                WHERE current_level < 0 AND company_id = ?
            """, (empresa_id,)).rowcount
            
            # 2. Corregir sobrellenados
            overflow_fix = conn.execute("""
                UPDATE company_fluid_tanks 
                SET current_level = tank_capacity 
                WHERE current_level > tank_capacity AND company_id = ?
            """, (empresa_id,)).rowcount
            
            # 3. Corregir valores NULL
            null_fix = conn.execute("""
                UPDATE company_fluid_tanks 
                SET current_level = 0 
                WHERE current_level IS NULL AND company_id = ?
            """, (empresa_id,)).rowcount
            
            conn.commit()
            
            print(f"   Niveles negativos corregidos: {negative_fix}")
            print(f"   Sobrellenados corregidos: {overflow_fix}")
            print(f"   Valores NULL corregidos: {null_fix}")
            print("   ✅ Reparación completada")
            
    except Exception as e:
        print(f"   ❌ Error en reparación: {e}")

def monitor_database_activity(duration=30):
    """Monitorea la actividad de la base de datos por un período"""
    print(f"\n📊 MONITOREANDO ACTIVIDAD POR {duration} SEGUNDOS...")
    
    start_time = time.time()
    operations = []
    
    try:
        while time.time() - start_time < duration:
            with get_conn() as conn:
                # Verificar estadísticas
                stats = conn.execute("""
                    SELECT 
                        COUNT(*) as tank_count,
                        SUM(current_level) as total_fluid,
                        AVG(current_level/tank_capacity * 100) as avg_fill_percent
                    FROM company_fluid_tanks
                """).fetchone()
                
                operations.append({
                    'timestamp': time.time(),
                    'tank_count': stats[0],
                    'total_fluid': stats[1] or 0,
                    'avg_fill': stats[2] or 0
                })
            
            time.sleep(2)  # Check cada 2 segundos
    
    except KeyboardInterrupt:
        print("\n   Monitoreo interrumpido por usuario")
    except Exception as e:
        print(f"   Error en monitoreo: {e}")
    
    # Mostrar resultados
    if operations:
        print(f"\n   Operaciones registradas: {len(operations)}")
        print(f"   Tanques promedio: {sum(op['tank_count'] for op in operations) / len(operations):.1f}")
        print(f"   Fluido total promedio: {sum(op['total_fluid'] for op in operations) / len(operations):.1f}")
        print(f"   Llenado promedio: {sum(op['avg_fill'] for op in operations) / len(operations):.1f}%")

@contextmanager
def safe_db_operation():
    """Context manager para operaciones seguras de BD"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("BEGIN IMMEDIATE;")
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

# Función para usar en Streamlit
def streamlit_diagnostic_panel(empresa_id):
    """Panel de diagnóstico para Streamlit"""
    import streamlit as st
    
    st.subheader("🔧 Panel de Diagnóstico Avanzado")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔍 Diagnóstico Completo"):
            with st.spinner("Ejecutando diagnóstico..."):
                diagnose_database_issues()
            st.success("Diagnóstico completado (ver consola)")
    
    with col2:
        if st.button("🔓 Forzar Desbloqueo"):
            if st.confirm("⚠️ ¿Seguro? Esto puede causar problemas"):
                force_unlock_database()
                st.warning("Desbloqueo ejecutado")
    
    with col3:
        if st.button("🔧 Reparar Datos"):
            with st.spinner("Reparando..."):
                repair_tank_data(empresa_id)
            st.success("Reparación completada")
    
    # Monitor en tiempo real
    if st.checkbox("📊 Monitor en Tiempo Real"):
        placeholder = st.empty()
        
        for i in range(10):  # 10 iteraciones
            with placeholder.container():
                try:
                    with get_conn() as conn:
                        stats = conn.execute("""
                            SELECT 
                                ft.name,
                                cft.current_level,
                                cft.tank_capacity,
                                (cft.current_level/cft.tank_capacity*100) as percentage
                            FROM company_fluid_tanks cft
                            JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                            WHERE cft.company_id = ?
                        """, (empresa_id,)).fetchall()
                        
                        if stats:
                            df = pd.DataFrame(stats, columns=['Fluido', 'Nivel', 'Capacidad', 'Porcentaje'])
                            st.dataframe(df)
                        else:
                            st.warning("No hay datos de tanques")
                            
                except Exception as e:
                    st.error(f"Error en monitor: {e}")
            
            time.sleep(2)

# Función principal para testing
def main_diagnostic():
    """Función principal para ejecutar diagnósticos"""
    print("Iniciando diagnóstico completo...")
    diagnose_database_issues()
    
    empresa_id = input("\nIngrese ID de empresa para diagnóstico específico (o Enter para saltar): ")
    if empresa_id.isdigit():
        repair_tank_data(int(empresa_id))

if __name__ == "__main__":
    main_diagnostic()