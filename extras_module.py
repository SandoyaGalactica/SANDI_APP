import streamlit as st
import pandas as pd
from datetime import datetime
from db_utils import get_conn
import importlib

# Importar submódulos
try:
    from extras_costos_especificos import mostrar_costos_especificos
    COSTOS_ESPECIFICOS_AVAILABLE = True
except ImportError:
    COSTOS_ESPECIFICOS_AVAILABLE = False
    print("⚠️ Módulo de costos específicos no disponible")

def mostrar_extras(empresa_id):
    """Módulo principal de EXTRAS - Funcionalidades Alpha"""
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #ff6b6b 0%, #4ecdc4 100%); 
                padding: 20px; border-radius: 15px; color: white; margin-bottom: 20px;">
        <h1>🚀 EXTRAS - Funcionalidades Alpha</h1>
        <p>Módulos experimentales y nuevas implementaciones</p>
        <div style="background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px; margin-top: 10px;">
            <small>⚠️ Estas funcionalidades están en desarrollo y pueden cambiar</small>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Obtener nombre de empresa
    try:
        from db_utils import list_companies
        empresas = list_companies()
        empresa = empresas[empresas['id'] == empresa_id]
        empresa_nombre = empresa.iloc[0]['name'] if not empresa.empty else f"Empresa {empresa_id}"
    except:
        empresa_nombre = f"Empresa {empresa_id}"
    
    # Verificar si hay submódulos disponibles
    modulos_disponibles = []
    
    if COSTOS_ESPECIFICOS_AVAILABLE:
        modulos_disponibles.append("Costos Específicos")
    
    # Agregar más módulos aquí cuando estén disponibles
    # if OTRO_MODULO_AVAILABLE:
    #     modulos_disponibles.append("Otro Módulo")
    
    if not modulos_disponibles:
        st.error("No hay módulos EXTRAS disponibles. Verifica las instalaciones.")
        st.info("Módulos esperados: extras_costos_especificos.py")
        return
    
    # Crear pestañas para submódulos
    tabs = st.tabs(modulos_disponibles)
    
    # Pestaña de Costos Específicos
    if "Costos Específicos" in modulos_disponibles:
        with tabs[modulos_disponibles.index("Costos Específicos")]:
            try:
                mostrar_costos_especificos(empresa_id, empresa_nombre)
            except Exception as e:
                st.error(f"Error cargando módulo de costos específicos: {str(e)}")
                st.info("Verifica que el archivo extras_costos_especificos.py esté disponible")
    
    # Agregar más pestañas aquí para otros módulos
    # if "Otro Módulo" in modulos_disponibles:
    #     with tabs[modulos_disponibles.index("Otro Módulo")]:
    #         mostrar_otro_modulo(empresa_id, empresa_nombre)

def get_extras_summary(empresa_id):
    """Obtiene resumen de funcionalidades EXTRAS para dashboard"""
    try:
        summary = {
            'total_modules': 0,
            'active_modules': [],
            'recommendations': []
        }
        
        # Verificar módulos disponibles
        if COSTOS_ESPECIFICOS_AVAILABLE:
            summary['total_modules'] += 1
            summary['active_modules'].append('Costos Específicos')
            
            # Verificar si hay datos
            try:
                from db_utils import get_maintenance_records
                maintenance_records = get_maintenance_records(empresa_id, limit=5)
                if not maintenance_records.empty:
                    summary['recommendations'].append("Puedes agregar detalles de costos a tus mantenimientos")
            except:
                pass
        
        return summary
        
    except Exception as e:
        return {'error': str(e)}

def init_extras_database():
    """Inicializa las tablas necesarias para los módulos EXTRAS"""
    try:
        from db_utils import get_conn
        
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
            
            # Registrar módulos disponibles
            modules_info = [
                ('costos_especificos', '1.0'),
                # Agregar más módulos aquí
            ]
            
            for module_name, version in modules_info:
                conn.execute("""
                    INSERT OR REPLACE INTO extras_modules (module_name, module_version)
                    VALUES (?, ?)
                """, (module_name, version))
            
            conn.commit()
        
        # Inicializar submódulos específicos
        if COSTOS_ESPECIFICOS_AVAILABLE:
            try:
                from extras_costos_especificos import init_costos_especificos_db
                init_costos_especificos_db()
            except Exception as e:
                print(f"Error inicializando BD costos específicos: {e}")
        
        return True
        
    except Exception as e:
        print(f"Error inicializando BD EXTRAS: {e}")
        return False

def verificar_compatibilidad_extras():
    """Verifica compatibilidad de los módulos EXTRAS con el sistema"""
    try:
        issues = []
        
        # Verificar dependencias básicas
        required_tables = ['machinery', 'maintenance_records', 'companies']
        
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [table[0] for table in cursor.fetchall()]
            
            for table in required_tables:
                if table not in existing_tables:
                    issues.append(f"Tabla requerida faltante: {table}")
        
        # Verificar módulos específicos
        if COSTOS_ESPECIFICOS_AVAILABLE:
            try:
                from extras_costos_especificos import verificar_compatibilidad_costos
                costos_issues = verificar_compatibilidad_costos()
                issues.extend(costos_issues)
            except Exception as e:
                issues.append(f"Error verificando costos específicos: {str(e)}")
        
        return {
            'is_compatible': len(issues) == 0,
            'issues': issues,
            'modules_checked': 1 if COSTOS_ESPECIFICOS_AVAILABLE else 0
        }
        
    except Exception as e:
        return {
            'is_compatible': False,
            'issues': [f"Error en verificación: {str(e)}"],
            'modules_checked': 0
        }

# Inicialización automática
if __name__ != "__main__":
    try:
        init_extras_database()
        print("✅ Sistema EXTRAS inicializado")
    except Exception as e:
        print(f"⚠️ Error inicializando EXTRAS: {e}")