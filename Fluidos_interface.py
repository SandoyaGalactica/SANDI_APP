"""
Interfaz simplificada para gestión de fluidos
Este módulo reemplaza el anterior sistema y actúa como wrapper del sistema unificado
"""
import streamlit as st
from controles_module import (
    mostrar_controles,
    get_company_tanks,
    calculate_tank_percentage,
    get_inventory_stats,
    initialize_company_tanks,
    get_company_setting
)

def mostrar_gestion_fluidos(empresa_id):
    """
    Función principal de gestión de fluidos - Interfaz simplificada
    Esta función ahora delega todo al sistema unificado de controles
    """
    # Redirigir al sistema unificado
    mostrar_controles(empresa_id)

def mostrar_resumen_fluidos(empresa_id):
    """
    Muestra un resumen rápido del estado de fluidos para el dashboard principal
    """
    # Inicializar tanques si es necesario
    initialize_company_tanks(empresa_id)
    
    # Obtener configuración de unidades
    unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
    
    # Obtener estado de tanques
    tanques = get_company_tanks(empresa_id)
    
    if tanques.empty:
        st.warning("⚠️ No hay tanques configurados")
        return
    
    st.subheader("📊 Estado de Inventario de Fluidos")
    
    # Crear columnas para mostrar cada tanque
    num_tanques = len(tanques)
    if num_tanques <= 4:
        cols = st.columns(num_tanques)
    else:
        cols = st.columns(4)  # Máximo 4 columnas
    
    alertas_criticas = 0
    
    for i, (_, tank) in enumerate(tanques.iterrows()):
        col_index = i % len(cols)
        
        with cols[col_index]:
            percentage = calculate_tank_percentage(tank)
            
            # Determinar color y estado
            if percentage <= 10:
                status_emoji = "🔴"
                status_text = "CRÍTICO"
                alertas_criticas += 1
            elif percentage <= 25:
                status_emoji = "🟡"
                status_text = "BAJO"
            elif percentage <= 70:
                status_emoji = "🟢"
                status_text = "NORMAL"
            else:
                status_emoji = "🔵"
                status_text = "LLENO"
            
            # Mostrar métrica
            st.metric(
                label=f"{status_emoji} {tank['fluid_name']}",
                value=f"{tank['current_level']:.0f} {unit_preference}",
                delta=f"{percentage:.1f}% - {status_text}"
            )
    
    # Mostrar alertas críticas si las hay
    if alertas_criticas > 0:
        st.error(f"🚨 {alertas_criticas} tanque(s) en estado crítico. Revise la sección de Fluidos.")
    
    # Botón para ir a gestión completa
    if st.button("🔧 Gestión Completa de Fluidos", type="primary"):
        st.session_state['nav_to_fluidos'] = True
        st.rerun()

def widget_estado_tanque(empresa_id, fluid_name=None):
    """
    Widget compacto para mostrar el estado de un tanque específico o todos
    Útil para incluir en otros módulos
    """
    tanques = get_company_tanks(empresa_id)
    unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
    
    if tanques.empty:
        st.info("No hay tanques configurados")
        return
    
    # Filtrar por fluido si se especifica
    if fluid_name:
        tanques = tanques[tanques['fluid_name'].str.lower() == fluid_name.lower()]
        if tanques.empty:
            st.warning(f"No se encontró tanque para {fluid_name}")
            return
    
    # Mostrar estado compacto
    for _, tank in tanques.iterrows():
        percentage = calculate_tank_percentage(tank)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write(f"**{tank['fluid_name']}**: {tank['current_level']:.1f}/{tank['tank_capacity']:.0f} {unit_preference}")
        
        with col2:
            if percentage <= 10:
                st.error(f"{percentage:.1f}%")
            elif percentage <= 25:
                st.warning(f"{percentage:.1f}%")
            else:
                st.success(f"{percentage:.1f}%")

def get_fluid_availability(empresa_id, fluid_name):
    """
    Obtiene la disponibilidad de un fluido específico
    Útil para otros módulos que necesiten verificar disponibilidad
    """
    tanques = get_company_tanks(empresa_id)
    
    if tanques.empty:
        return 0.0, "galones"
    
    # Buscar el tanque del fluido especificado
    tank_match = tanques[tanques['fluid_name'].str.lower() == fluid_name.lower()]
    
    if tank_match.empty:
        return 0.0, "galones"
    
    tank = tank_match.iloc[0]
    return float(tank['current_level']), tank['unit']

def verificar_disponibilidad_despacho(empresa_id, fluid_name, cantidad_requerida):
    """
    Verifica si hay suficiente fluido disponible para un despacho
    Retorna: (disponible: bool, mensaje: str, cantidad_disponible: float)
    """
    cantidad_disponible, unit = get_fluid_availability(empresa_id, fluid_name)
    
    if cantidad_disponible >= cantidad_requerida:
        return True, f"Suficiente {fluid_name} disponible", cantidad_disponible
    else:
        faltante = cantidad_requerida - cantidad_disponible
        return False, f"Insuficiente {fluid_name}. Disponible: {cantidad_disponible:.1f} {unit}, Faltante: {faltante:.1f} {unit}", cantidad_disponible

def mostrar_alertas_fluidos(empresa_id, solo_criticas=True):
    """
    Muestra alertas de fluidos en formato compacto
    Para usar en sidebar o notificaciones
    """
    tanques = get_company_tanks(empresa_id)
    
    if tanques.empty:
        return
    
    alertas = []
    
    for _, tank in tanques.iterrows():
        percentage = calculate_tank_percentage(tank)
        
        if percentage <= 10:
            alertas.append({
                'level': 'error',
                'fluid': tank['fluid_name'],
                'percentage': percentage,
                'message': f"🔴 {tank['fluid_name']}: {percentage:.1f}% (CRÍTICO)"
            })
        elif not solo_criticas and percentage <= 25:
            alertas.append({
                'level': 'warning',
                'fluid': tank['fluid_name'],
                'percentage': percentage,
                'message': f"🟡 {tank['fluid_name']}: {percentage:.1f}% (BAJO)"
            })
    
    # Mostrar alertas
    for alerta in alertas:
        if alerta['level'] == 'error':
            st.error(alerta['message'])
        elif alerta['level'] == 'warning':
            st.warning(alerta['message'])

def get_consumption_summary(empresa_id, days=7):
    """
    Obtiene resumen de consumo de los últimos días
    """
    try:
        from datetime import datetime, timedelta
        from db_utils import get_conn
        import pandas as pd
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        with get_conn() as conn:
            consumo = pd.read_sql_query("""
                SELECT 
                    ft.name as fluid_name,
                    SUM(fim.quantity) as total_consumed,
                    COUNT(*) as num_dispatches,
                    AVG(fim.quantity) as avg_dispatch
                FROM fluid_inventory_movements fim
                JOIN company_fluid_tanks cft ON fim.tank_id = cft.id
                JOIN fluid_types ft ON cft.fluid_type_id = ft.id
                WHERE cft.company_id = ? 
                AND fim.movement_type = 'SALIDA'
                AND fim.created_at >= ?
                GROUP BY ft.name
                ORDER BY total_consumed DESC
            """, conn, params=(empresa_id, start_date.isoformat()))
        
        return consumo
        
    except Exception:
        return pd.DataFrame()  # Retornar DataFrame vacío en caso de error

def mostrar_widgets_dashboard(empresa_id):
    """
    Muestra widgets de fluidos para el dashboard principal
    """
    col1, col2 = st.columns(2)
    
    with col1:
        mostrar_resumen_fluidos(empresa_id)
    
    with col2:
        st.subheader("📈 Consumo Semanal")
        consumo = get_consumption_summary(empresa_id, 7)
        
        if not consumo.empty:
            unit_preference = get_company_setting(empresa_id, "unit_preference", "galones")
            
            for _, row in consumo.iterrows():
                st.metric(
                    label=row['fluid_name'],
                    value=f"{row['total_consumed']:.1f} {unit_preference}",
                    delta=f"{row['num_dispatches']} despachos"
                )
        else:
            st.info("No hay datos de consumo esta semana")

# Funciones de compatibilidad con el sistema anterior

def add_fuel_to_tank(empresa_id, tank_id, amount, cost=None, supplier=None, added_by="admin", notes=None):
    """
    Función de compatibilidad - redirige al nuevo sistema
    """
    from controles_module import procesar_entrada_inventario
    
    # Convertir parámetros al nuevo formato
    costo_unitario = cost / amount if cost and amount > 0 else 0
    
    return procesar_entrada_inventario(
        tank_id=tank_id,
        cantidad=amount,
        costo_unitario=costo_unitario,
        proveedor=supplier,
        referencia=None,
        notas=notes,
        usuario=added_by
    )

def despachar_fluido_a_maquina(empresa_id, tank_id, machine_id, cantidad, operador=None, notas=None):
    """
    Función simplificada para despachar fluido a una máquina
    """
    from controles_module import procesar_salida_inventario
    
    return procesar_salida_inventario(
        tank_id=tank_id,
        machine_id=machine_id,
        cantidad=cantidad,
        operador=operador or "N/A",
        horas=0,
        odometro=0,
        notas=notas or "",
        usuario=st.session_state.get("username", "admin")
    )

# Función principal para navegación

def main_fluidos_interface(empresa_id):
    """
    Función principal de la interfaz de fluidos
    Se puede llamar desde el menú principal o desde otros módulos
    """
    # Verificar si hay navegación pendiente
    if st.session_state.get('nav_to_fluidos', False):
        st.session_state['nav_to_fluidos'] = False
    
    # Mostrar interfaz completa
    mostrar_gestion_fluidos(empresa_id)