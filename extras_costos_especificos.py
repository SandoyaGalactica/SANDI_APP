import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from db_utils import get_conn, get_maintenance_records, list_machinery
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_costos_especificos_db():
    """Inicializa las tablas necesarias para costos específicos"""
    try:
        with get_conn() as conn:
            # Tabla para categorías de insumos/costos
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
            
            # Insertar categorías por defecto
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
        logger.error(f"Error inicializando BD costos específicos: {e}")
        return False

# Asegurar que las tablas y categorías estén inicializadas
try:
    init_costos_especificos_db()
    logger.info("Tablas y categorías inicializadas correctamente")
except Exception as e:
    logger.error(f"Error inicializando tablas y categorías: {e}")

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_costos_especificos_db():
    """Inicializa las tablas necesarias para costos específicos"""
    try:
        with get_conn() as conn:
            # Tabla para categorías de insumos/costos
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
            
            # Insertar categorías por defecto
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
        logger.error(f"Error inicializando BD costos específicos: {e}")
        return False

def mostrar_costos_especificos(empresa_id, empresa_nombre):
    """Interfaz principal del módulo de costos específicos"""
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 15px; border-radius: 10px; color: white; margin-bottom: 15px;">
        <h3>💰 Costos Específicos de Mantenimiento</h3>
        <p>Detalla en qué se gastó específicamente cada mantenimiento</p>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        maintenance_records = get_maintenance_records(empresa_id)
        
        if maintenance_records.empty:
            st.info("No hay registros de mantenimiento para esta empresa.")
            st.info("Ve al módulo de Mantenimiento para registrar mantenimientos primero.")
            return
        
        
    except Exception as e:
        st.error(f"Error obteniendo registros de mantenimiento: {str(e)}")
        return
    
    # Crear pestañas
    tab1, tab2, tab3 = st.tabs(["Costos Especificos", "Gestión de Categorías", "Resumen de Costos"])
    
    with tab1:
        mostrar_agregar_detalles(empresa_id, maintenance_records)
    
    with tab2:
        gestionar_categorias()
    
    with tab3:
        mostrar_resumen_costos(empresa_id)

def parse_date_flexible(date_value):
    """Parsea fechas de manera flexible manejando múltiples formatos"""
    if pd.isna(date_value) or date_value is None:
        return None
    
    if isinstance(date_value, str) and date_value.lower() in ['none', 'null', '', 'sin fecha']:
        return None
    
    # Lista de formatos de fecha a intentar
    date_formats = [
        '%Y-%m-%dT%H:%M:%S.%f',      # 2025-09-10T14:04:56.285979
        '%Y-%m-%dT%H:%M:%S',         # 2025-09-10T14:04:56
        '%Y-%m-%d %H:%M:%S.%f',      # 2025-09-10 14:04:56.285979
        '%Y-%m-%d %H:%M:%S',         # 2025-09-10 14:04:56
        '%Y-%m-%d',                  # 2025-09-10
        '%d/%m/%Y',                  # 10/09/2025
        '%m/%d/%Y',                  # 09/10/2025
        '%d-%m-%Y',                  # 10-09-2025
        '%m-%d-%Y'                   # 09-10-2025
    ]
    
    # Intentar parsear con cada formato
    for fmt in date_formats:
        try:
            return datetime.strptime(str(date_value), fmt)
        except ValueError:
            continue
    
    # Último intento con pandas
    try:
        return pd.to_datetime(date_value)
    except:
        return None

def parse_and_format_date(date_value, format_output='%Y-%m-%d'):
    """Parsea y formatea fecha para mostrar en la interfaz"""
    parsed_date = parse_date_flexible(date_value)
    
    if parsed_date:
        return parsed_date.strftime(format_output)
    else:
        # Si no se pudo parsear, intentar extraer fecha del string
        date_str = str(date_value)
        if len(date_str) >= 10 and '-' in date_str:
            # Intentar extraer los primeros 10 caracteres si parece una fecha
            potential_date = date_str[:10]
            if potential_date.count('-') == 2:
                return potential_date
        
        return "Sin fecha registrada"

def mostrar_agregar_detalles(empresa_id, maintenance_records):
    """Interfaz para ver y agregar detalles de costos"""
    
    st.subheader("Seleccionar Mantenimiento")
    
    # Obtener maquinaria para filtrar
    maquinaria = list_machinery(empresa_id)
    if maquinaria.empty:
        st.warning("No hay maquinaria registrada.")
        return
    
    # Verificar que maintenance_records tenga datos
    if maintenance_records.empty:
        st.info("No hay registros de mantenimiento disponibles.")
        return
    
    # Filtros
    col1, col2 = st.columns([1, 1])
    
    with col1:
        machine_options = ["Todas"] + maquinaria['name'].tolist()
        selected_machine = st.selectbox("Filtrar por máquina:", machine_options)
    
    with col2:
        date_filter = st.selectbox(
            "Filtrar por período:",
            ["Todos", "Últimos 30 días", "Últimos 3 meses", "Últimos 6 meses", "Último año"]
        )
    
    # Aplicar filtros
    filtered_records = maintenance_records.copy()
    
    # Filtro por máquina
    if selected_machine != "Todas":
        filtered_records = filtered_records[filtered_records['machinery_name'] == selected_machine]
    
    # Filtro por fecha
    if date_filter != "Todos":
        try:
            days_map = {
                "Últimos 30 días": 30,
                "Últimos 3 meses": 90,
                "Últimos 6 meses": 180,
                "Último año": 365
            }
            cutoff_date = datetime.now() - timedelta(days=days_map[date_filter])
            
            def is_date_within_range(date_val):
                """Función para verificar fechas"""
                if pd.isna(date_val) or date_val is None:
                    return True  # Incluir registros con fecha NULL
                try:
                    parsed_date = parse_date_flexible(date_val)
                    return parsed_date >= cutoff_date if parsed_date else True
                except:
                    return True  # Si no se puede parsear, incluir el registro
            
            if 'performed_at' in filtered_records.columns:
                mask = filtered_records['performed_at'].apply(is_date_within_range)
                filtered_records = filtered_records[mask]
                
        except Exception as e:
            st.warning(f"Error aplicando filtro de fecha: {e}")
    
    if filtered_records.empty:
        st.info("No hay mantenimientos que coincidan con los filtros.")
        return
    
    # Mostrar mantenimientos
    st.subheader("Mantenimientos Disponibles")
    
    maintenance_options = []
    maintenance_dict = {}
    
    for _, record in filtered_records.iterrows():
        machine_name = record['machinery_name']
        maintenance_type = record['maintenance_type']
        cost = record.get('cost', 0) or 0
        cost_str = f"${cost:.2f}"
        
        date_str = parse_and_format_date(record['performed_at'])
        
        option_text = f"{machine_name} - {maintenance_type} - {date_str} - {cost_str}"
        maintenance_options.append(option_text)
        maintenance_dict[option_text] = record
    
    # Seleccionar mantenimiento específico
    if maintenance_options:
        selected_maintenance_text = st.selectbox(
            "Seleccionar mantenimiento específico:",
            maintenance_options,
            help="Selecciona el mantenimiento al que quieres agregar detalles de costo"
        )
        
        selected_record = maintenance_dict[selected_maintenance_text]
        maintenance_id = selected_record['id']
        total_cost = selected_record.get('cost', 0) or 0
        
        # Mostrar información del mantenimiento seleccionado
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Costo Total", f"${total_cost:.2f}")
        with col2:
            date_display = parse_and_format_date(selected_record['performed_at'])
            st.metric("Fecha", date_display)
        with col3:
            st.metric("Tipo", selected_record['maintenance_type'])
        with col4:
            # Calcular costo ya detallado
            detailed_cost = get_detailed_cost_sum(maintenance_id)
            remaining_cost = total_cost - detailed_cost
            st.metric("Restante", f"${remaining_cost:.2f}")
        
        # Mostrar información adicional del mantenimiento
        with st.expander("Ver detalles del mantenimiento"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Máquina:** {selected_record['machinery_name']}")
                st.write(f"**Matrícula:** {selected_record.get('identifier', 'No especificada')}")
                st.write(f"**Realizado por:** {selected_record.get('performed_by', 'No especificado')}")
                st.write(f"**Horas al mantenimiento:** {selected_record.get('hours_at_maintenance', 'No especificado')}")
            with col2:
                st.write(f"**Descripción:** {selected_record.get('description', 'Sin descripción')}")
                st.write(f"**Repuestos usados:** {selected_record.get('parts_used', 'No especificado')}")
                st.write(f"**Notas:** {selected_record.get('notes', 'Sin notas')}")
        
        # Mostrar detalles existentes
        mostrar_detalles_existentes(maintenance_id)
        
        # Formulario para agregar nuevo detalle
        if remaining_cost > 0:
            agregar_nuevo_detalle(maintenance_id, remaining_cost)
        else:
            if total_cost > 0:
                st.success("✅ Todos los costos han sido detallados")
            else:
                st.info("Este mantenimiento no tiene costo registrado")
                st.info("💡 Puedes agregar detalles aunque el costo total sea 0")
                agregar_nuevo_detalle(maintenance_id, 999999)  # Permitir agregar sin límite

def mostrar_detalles_existentes(maintenance_id):
    """Muestra los detalles de costo ya registrados"""
    
    detalles = get_maintenance_cost_details(maintenance_id)
    
    if not detalles.empty:
        st.subheader("Detalles de Costo Existentes")
        
        # Formatear para mostrar
        display_df = detalles[['category_name', 'item_name', 'quantity', 'unit_cost', 'total_cost', 'supplier', 'notes']].copy()
        display_df.columns = ['Categoría', 'Insumo', 'Cantidad', 'Costo Unit.', 'Total', 'Proveedor', 'Notas']
        display_df['Costo Unit.'] = display_df['Costo Unit.'].apply(lambda x: f"${x:.2f}")
        display_df['Total'] = display_df['Total'].apply(lambda x: f"${x:.2f}")
        display_df['Cantidad'] = display_df['Cantidad'].apply(lambda x: f"{x:.1f}")
        
        st.dataframe(display_df, use_container_width=True)
        
        # Opción para eliminar detalles
        with st.expander("🗑️ Eliminar Detalle"):
            detail_to_delete = st.selectbox(
                "Seleccionar detalle a eliminar:",
                options=range(len(detalles)),
                format_func=lambda x: f"{detalles.iloc[x]['category_name']} - {detalles.iloc[x]['item_name']} (${detalles.iloc[x]['total_cost']:.2f})"
            )
            
            if st.button("Eliminar Detalle", type="secondary"):
                detail_id = detalles.iloc[detail_to_delete]['id']
                if delete_cost_detail(detail_id):
                    st.success("Detalle eliminado correctamente")
                    st.rerun()
                else:
                    st.error("Error eliminando detalle")
    else:
        st.info("No hay detalles de costo registrados para este mantenimiento")

def agregar_nuevo_detalle(maintenance_id, remaining_cost):
    """Formulario para agregar nuevo detalle"""
    
    st.subheader("Agregar Nuevo Detalle")
    
    with st.form(f"new_detail_form_{maintenance_id}"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Obtener categorías
            categories = get_cost_categories()
            
            if categories.empty:
                st.error("❌ No hay categorías disponibles.")
                st.info("Verifica la configuración de la base de datos.")
                
                # Botón para intentar crear categorías
                if st.form_submit_button("Crear Categorías Básicas"):
                    try:
                        init_costos_especificos_db()
                        st.success("Categorías creadas. Recarga la página.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creando categorías: {e}")
                return
            
            # Mostrar categorías disponibles para verificación
            with st.expander("Ver categorías disponibles", expanded=False):
                st.dataframe(categories[['id', 'category_name', 'is_active']])
            
            # Selectbox de categorías
            category_options = categories['category_name'].tolist()
            selected_category = st.selectbox("Categoría:", category_options)
            
            item_name = st.text_input("Nombre del insumo/servicio:", placeholder="Ej: Filtro de aceite")
            quantity = st.number_input("Cantidad:", min_value=0.1, value=1.0, step=0.1, format="%.1f")
        
        with col2:
            unit_cost = st.number_input("Costo unitario ($):", min_value=0.01, step=0.01, format="%.2f")
            total_cost = quantity * unit_cost
            st.metric("Costo total calculado:", f"${total_cost:.2f}")
            
            if remaining_cost < 999999:
                st.info(f"Costo restante: ${remaining_cost:.2f}")
                if total_cost > remaining_cost:
                    st.warning("⚠️ El costo excede el restante")
            
            supplier = st.text_input("Proveedor (opcional):", placeholder="Ej: Repuestos García")
        
        notes = st.text_area("Comentarios/Notas:", placeholder="Información adicional...")
        
        submitted = st.form_submit_button("Agregar Detalle", type="primary")
        
        if submitted:
            # Validaciones
            errors = []
            
            if not item_name or item_name.strip() == "":
                errors.append("❌ El nombre del insumo es obligatorio")
            if quantity <= 0:
                errors.append("❌ La cantidad debe ser mayor a 0")
            if unit_cost <= 0:
                errors.append("❌ El costo unitario debe ser mayor a $0.00")
            if remaining_cost < 999999 and total_cost > remaining_cost:
                errors.append("❌ El costo total excede el restante")
            
            if errors:
                st.error("Errores encontrados:")
                for error in errors:
                    st.write(error)
            else:
                try:
                    # Obtener category_id de manera segura
                    category_row = categories[categories['category_name'] == selected_category]
                    if category_row.empty:
                        st.error("❌ Error: Categoría seleccionada no válida")
                        st.write("Categorías disponibles:")
                        st.dataframe(categories)
                        return
                    
                    category_id = category_row.iloc[0]['id']
                    
                    # Insertar detalle
                    success = add_maintenance_cost_detail(
                        maintenance_id=maintenance_id,
                        category_id=category_id,
                        item_name=item_name.strip(),
                        unit_cost=unit_cost,
                        quantity=quantity,
                        total_cost=total_cost,
                        supplier=supplier.strip() if supplier.strip() else None,
                        notes=notes.strip() if notes.strip() else None
                    )
                    
                    if success:
                        st.success("✅ Detalle agregado correctamente")
                        st.rerun()
                    else:
                        st.error("❌ Error agregando detalle a la base de datos")
                        st.info("Revisa la consola de Python para más detalles del error")
                        
                except Exception as e:
                    st.error(f"❌ Error inesperado: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

def agregar_nuevo_detalle_con_warnings(maintenance_id, remaining_cost):
    """Versión alternativa con warnings en tiempo real pero botón siempre activo"""
    
    st.subheader("Agregar Nuevo Detalle")
    
    with st.form(f"new_detail_form_{maintenance_id}"):
        col1, col2 = st.columns(2)
        
        with col1:
            categories = get_cost_categories()
            if categories.empty:
                st.error("No hay categorías disponibles.")
                st.form_submit_button("No disponible", disabled=True)
                return
            
            category_options = categories['category_name'].tolist()
            selected_category = st.selectbox("Categoría:", category_options)
            
            item_name = st.text_input("Nombre del insumo/servicio:", placeholder="Ej: Filtro de aceite")
            # Warning en tiempo real para nombre
            if item_name and item_name.strip() == "":
                st.warning("⚠️ El nombre no puede estar vacío")
            
            quantity = st.number_input("Cantidad:", min_value=0.0, value=1.0, step=0.1, format="%.1f")
            # Warning en tiempo real para cantidad
            if quantity == 0:
                st.warning("⚠️ La cantidad debe ser mayor a 0")
        
        with col2:
            unit_cost = st.number_input("Costo unitario ($):", min_value=0.0, step=0.01, format="%.2f")
            # Warning en tiempo real para costo
            if unit_cost == 0:
                st.warning("⚠️ El costo debe ser mayor a $0.00")
            
            total_cost = quantity * unit_cost
            st.metric("Costo total calculado:", f"${total_cost:.2f}")
            
            # Warning en tiempo real para exceso de costo
            if remaining_cost < 999999 and total_cost > remaining_cost:
                st.error(f"⚠️ Excede el costo restante: ${remaining_cost:.2f}")
            
            st.info(f"Costo restante: ${remaining_cost:.2f}")
            
            supplier = st.text_input("Proveedor (opcional):", placeholder="Ej: Repuestos García")
        
        notes = st.text_area("Comentarios/Notas:", placeholder="Información adicional...")
        
        # BOTÓN SIEMPRE ACTIVO
        submitted = st.form_submit_button("Agregar Detalle", type="primary")
        
        if submitted:
            # Misma lógica de validación post-envío que la función anterior
            errors = []
            
            if not item_name or item_name.strip() == "":
                errors.append("❌ El nombre del insumo es obligatorio")
            if quantity <= 0:
                errors.append("❌ La cantidad debe ser mayor a 0")
            if unit_cost <= 0:
                errors.append("❌ El costo unitario debe ser mayor a $0.00")
            if remaining_cost < 999999 and total_cost > remaining_cost:
                errors.append(f"❌ El costo total excede el restante")
            
            if errors:
                st.error("Errores encontrados:")
                for error in errors:
                    st.write(error)
            else:
                try:
                    category_id = categories[categories['category_name'] == selected_category].iloc[0]['id']
                    success = add_maintenance_cost_detail(
                        maintenance_id=maintenance_id,
                        category_id=category_id,
                        item_name=item_name.strip(),
                        unit_cost=unit_cost,
                        quantity=quantity,
                        total_cost=total_cost,
                        supplier=supplier.strip() if supplier.strip() else None,
                        notes=notes.strip() if notes.strip() else None
                    )
                    
                    if success:
                        st.success("✅ Detalle agregado correctamente")
                        st.rerun()
                    else:
                        st.error("❌ Error en la base de datos")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

def gestionar_categorias():
    """Interfaz para gestionar categorías de costos"""
    
    st.subheader("Gestión de Categorías")
    
    # Mostrar categorías existentes
    with get_conn() as conn:
        all_categories = pd.read_sql_query("""
            SELECT id, category_name, description, is_active, created_at
            FROM cost_categories 
            ORDER BY is_active DESC, category_name
        """, conn)
    
    if not all_categories.empty:
        st.subheader("Categorías Existentes")
        
        # Mostrar en tabla
        display_categories = all_categories.copy()
        display_categories['Estado'] = display_categories['is_active'].map({1: '✅ Activa', 0: '❌ Inactiva'})
        display_categories = display_categories[['id', 'category_name', 'description', 'Estado']]
        display_categories.columns = ['ID', 'Nombre', 'Descripción', 'Estado']
        
        st.dataframe(display_categories, use_container_width=True)
        
        # Gestión de categorías
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("✏️ Editar Categoría")
            selected_category_id = st.selectbox(
                "Seleccionar categoría:",
                all_categories['id'].tolist(),
                format_func=lambda x: f"ID {x}: {all_categories[all_categories['id']==x].iloc[0]['category_name']}"
            )
            
            if selected_category_id:
                category_info = all_categories[all_categories['id'] == selected_category_id].iloc[0]
                
                new_description = st.text_area(
                    "Descripción:",
                    value=category_info['description'] or "",
                    key=f"desc_{category_info['id']}"
                )
                
                is_active = st.checkbox(
                    "Categoría activa",
                    value=bool(category_info['is_active']),
                    key=f"active_{category_info['id']}"
                )
                
                if st.button("Actualizar Categoría", type="primary"):
                    success = update_cost_category(
                        category_info['id'],
                        new_description,
                        is_active
                    )
                    if success:
                        st.success("Categoría actualizada")
                        st.rerun()
                    else:
                        st.error("Error actualizando categoría")
        
        with col2:
            st.subheader("🗑️ Eliminar Categoría")
            
            category_to_delete = st.selectbox(
                "Seleccionar categoría a eliminar:",
                all_categories['id'].tolist(),
                format_func=lambda x: f"ID {x}: {all_categories[all_categories['id']==x].iloc[0]['category_name']}",
                key="delete_selector"
            )
            
            if category_to_delete:
                selected_info = all_categories[all_categories['id'] == category_to_delete].iloc[0]
                
                st.warning(f"⚠️ Vas a eliminar: **{selected_info['category_name']}**")
                
                # Verificar uso
                with get_conn() as conn:
                    usage = pd.read_sql_query("""
                        SELECT COUNT(*) as count FROM maintenance_cost_details 
                        WHERE category_id = ?
                    """, conn, params=(category_to_delete,))
                    
                    usage_count = usage.iloc[0]['count'] if not usage.empty else 0
                
                if usage_count > 0:
                    st.info(f"Esta categoría tiene {usage_count} registros asociados. Se desactivará en lugar de eliminarse.")
                else:
                    st.info("Esta categoría no tiene registros asociados. Se eliminará completamente.")
                
                if st.button("🗑️ Confirmar Eliminación", type="secondary", key="confirm_delete"):
                    success, message = delete_cost_category(category_to_delete)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    
    # Agregar nueva categoría
    st.subheader("➕ Agregar Nueva Categoría")
    
    with st.form("new_category_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_category_name = st.text_input("Nombre de la categoría:")
        
        with col2:
            new_category_desc = st.text_input("Descripción:")
        
        if st.form_submit_button("Agregar Categoría", type="primary"):
            if new_category_name.strip():
                success = add_cost_category(new_category_name.strip(), new_category_desc.strip())
                if success:
                    st.success("Categoría agregada correctamente")
                    st.rerun()
                else:
                    st.error("Error agregando categoría (puede que ya exista)")
            else:
                st.error("El nombre de la categoría es obligatorio")

def mostrar_resumen_costos(empresa_id):
    """Muestra resumen y análisis de costos con filtros y descarga Excel"""
    
    st.subheader("Resumen de Costos por Categoría")
    
    # Obtener datos base
    cost_summary = get_cost_summary_by_category(empresa_id)
    
    if cost_summary.empty:
        st.info("No hay detalles de costo registrados aún.")
        return
    
    # Obtener datos para filtros
    maintenance_records = get_maintenance_records(empresa_id)
    maquinaria = list_machinery(empresa_id)
    categorias = get_cost_categories()
    
    # FILTROS
    st.subheader("Filtros")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**Rango de Fechas:**")
        fecha_inicio = st.date_input("Fecha inicio:", value=None, key="fecha_inicio_resumen")
        fecha_fin = st.date_input("Fecha fin:", value=None, key="fecha_fin_resumen")
    
    with col2:
        st.write("**Máquina:**")
        machine_options = ["Todas"] + (maquinaria['name'].tolist() if not maquinaria.empty else [])
        selected_machine = st.selectbox("Seleccionar máquina:", machine_options, key="machine_resumen")
    
    with col3:
        st.write("**Categoría:**")
        category_options = ["Todas"] + (categorias['category_name'].tolist() if not categorias.empty else [])
        selected_category = st.selectbox("Seleccionar categoría:", category_options, key="category_resumen")
    
    # Aplicar filtros
    filtered_data = apply_filters_to_cost_data(
        empresa_id, fecha_inicio, fecha_fin, selected_machine, selected_category
    )
    
    if filtered_data.empty:
        st.warning("No hay datos que coincidan con los filtros seleccionados.")
        return
    
    # Recalcular resumen con datos filtrados
    filtered_summary = filtered_data.groupby('category_name').agg({
        'total_cost': 'sum',
        'id': 'count'
    }).reset_index()
    filtered_summary.columns = ['category_name', 'total_cost', 'transaction_count']
    filtered_summary['avg_cost'] = filtered_summary['total_cost'] / filtered_summary['transaction_count']
    filtered_summary = filtered_summary.sort_values('total_cost', ascending=False)
    
    # MÉTRICAS PRINCIPALES
    col1, col2, col3, col4 = st.columns(4)
    
    total_detailed = filtered_summary['total_cost'].sum()
    categories_count = len(filtered_summary)
    most_expensive_category = filtered_summary.iloc[0]['category_name'] if not filtered_summary.empty else "N/A"
    least_expensive_category = filtered_summary.iloc[-1]['category_name'] if not filtered_summary.empty else "N/A"
    
    with col1:
        st.metric("Total Detallado", f"${total_detailed:.2f}")
    with col2:
        st.metric("Categorías Usadas", categories_count)
    with col3:
        st.metric("Categoría Mayor Gasto", most_expensive_category)
    with col4:
        st.metric("Categoría con Menos Gastos", least_expensive_category)
    
    # TABLA DETALLADA
    st.subheader("Detalle por Categoría")
    
    display_summary = filtered_summary.copy()
    display_summary['total_cost_formatted'] = display_summary['total_cost'].apply(lambda x: f"${x:.2f}")
    display_summary['avg_cost_formatted'] = display_summary['avg_cost'].apply(lambda x: f"${x:.2f}")
    
    display_df = display_summary[['category_name', 'transaction_count', 'total_cost_formatted', 'avg_cost_formatted']].copy()
    display_df.columns = ['Categoría', 'Transacciones', 'Costo Total', 'Costo Promedio']
    
    st.dataframe(display_df, use_container_width=True)
    
    # BOTÓN DE DESCARGA EXCEL
    st.subheader("Descargar Reporte")
    
    if st.button("Generar y Descargar Excel", type="primary"):
        excel_file = generate_excel_report(empresa_id, filtered_data, filtered_summary, fecha_inicio, fecha_fin, selected_machine, selected_category)
        if excel_file:
            st.download_button(
                label="Descargar Reporte Excel",
                data=excel_file,
                file_name=f"reporte_costos_{empresa_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ============================================
# FUNCIONES DE BASE DE DATOS
# ============================================

def get_cost_categories():
    """Obtiene todas las categorías de costos activas con verificación y reparación"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            # Verificar si la tabla existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cost_categories'")
            if not cursor.fetchone():
                logger.info("Tabla cost_categories no existe, inicializando...")
                init_costos_especificos_db()
            
            # Verificar si hay categorías
            cursor.execute("SELECT COUNT(*) FROM cost_categories")
            count = cursor.fetchone()[0]
            
            # Si no hay categorías, inicializar
            if count == 0:
                logger.info("No hay categorías, creando categorías por defecto...")
                init_costos_especificos_db()
            
            # Verificar si hay categorías activas
            cursor.execute("SELECT COUNT(*) FROM cost_categories WHERE is_active = 1")
            active_count = cursor.fetchone()[0]
            
            # Si no hay categorías activas, activar todas
            if active_count == 0 and count > 0:
                logger.info("No hay categorías activas, activando todas...")
                cursor.execute("UPDATE cost_categories SET is_active = 1")
                conn.commit()
            
            # Obtener categorías activas
            result = pd.read_sql_query("""
                SELECT id, category_name, description, is_active, created_at
                FROM cost_categories 
                WHERE is_active = 1
                ORDER BY category_name
            """, conn)
            
            # Verificación final
            if result.empty:
                logger.warning("¡Aún no hay categorías disponibles después de la reparación!")
                # Intentar obtener todas las categorías sin filtro de activas
                result = pd.read_sql_query("""
                    SELECT id, category_name, description, is_active, created_at
                    FROM cost_categories 
                    ORDER BY category_name
                """, conn)
            
            return result
            
    except Exception as e:
        logger.error(f"Error en get_cost_categories: {e}")
        # En caso de error, intentar inicializar la BD
        try:
            init_costos_especificos_db()
            logger.info("Se intentó inicializar la BD después de un error")
        except:
            pass
        return pd.DataFrame()

def add_cost_category(category_name, description=""):
    """Agrega nueva categoría de costo"""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO cost_categories (category_name, description, is_active)
                VALUES (?, ?, 1)
            """, (category_name, description))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error agregando categoría: {e}")
        return False

def update_cost_category(category_id, description, is_active):
    """Actualiza categoría de costo"""
    try:
        with get_conn() as conn:
            conn.execute("""
                UPDATE cost_categories 
                SET description = ?, is_active = ?
                WHERE id = ?
            """, (description, 1 if is_active else 0, category_id))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error actualizando categoría: {e}")
        return False

def get_maintenance_cost_details(maintenance_id):
    """Obtiene detalles de costo de un mantenimiento"""
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
        logger.error(f"Error obteniendo detalles: {e}")
        return pd.DataFrame()

def add_maintenance_cost_detail(maintenance_id, category_id, item_name, unit_cost, quantity, total_cost, supplier=None, notes=None):
    """Agrega detalle de costo a mantenimiento con validación mejorada"""
    try:
        # Validaciones básicas
        if not maintenance_id:
            logger.error("maintenance_id faltante")
            return False
        
        if not category_id:
            logger.error("category_id faltante")
            return False
        
        if not item_name or str(item_name).strip() == "":
            logger.error("item_name vacío")
            return False
        
        if quantity <= 0 or unit_cost <= 0:
            logger.error("quantity o unit_cost inválidos")
            return False
        
        with get_conn() as conn:
            cursor = conn.cursor()
            
            # Verificar maintenance_record
            cursor.execute("SELECT id FROM maintenance_records WHERE id = ?", (maintenance_id,))
            maintenance_exists = cursor.fetchone()
            
            if not maintenance_exists:
                logger.error(f"maintenance_record_id {maintenance_id} no existe")
                return False
            
            # Mostrar todas las categorías disponibles para diagnóstico
            all_categories = pd.read_sql_query("SELECT id, category_name, is_active FROM cost_categories", conn)
            logger.info(f"Categorías disponibles: {len(all_categories)}")
            for _, cat in all_categories.iterrows():
                logger.info(f"ID {cat['id']}: {cat['category_name']} - Activa: {cat['is_active']}")
            
            # Verificar categoría - intentar múltiples métodos
            # Método 1: Búsqueda directa
            cursor.execute("SELECT id, category_name, is_active FROM cost_categories WHERE id = ?", (category_id,))
            category = cursor.fetchone()
            
            # Método 2: Búsqueda por string
            if not category:
                cursor.execute("SELECT id, category_name, is_active FROM cost_categories WHERE id = ?", (str(category_id),))
                category = cursor.fetchone()
            
            # Método 3: Búsqueda por cast explícito
            if not category:
                cursor.execute("SELECT id, category_name, is_active FROM cost_categories WHERE CAST(id AS TEXT) = ?", (str(category_id),))
                category = cursor.fetchone()
            
            # Si aún no encontramos la categoría, verificar si necesitamos reinicializar
            if not category:
                logger.warning(f"No se encontró la categoría con ID {category_id}, intentando reparar...")
                
                # Verificar si hay categorías en general
                cursor.execute("SELECT COUNT(*) FROM cost_categories")
                cat_count = cursor.fetchone()[0]
                
                if cat_count == 0:
                    # No hay categorías, inicializar
                    logger.info("No hay categorías, inicializando...")
                    init_costos_especificos_db()
                    
                    # Buscar categoría nuevamente
                    cursor.execute("SELECT id, category_name, is_active FROM cost_categories WHERE id = ?", (category_id,))
                    category = cursor.fetchone()
                    
                    if not category:
                        # Si aún no hay, usar la primera categoría disponible
                        cursor.execute("SELECT id, category_name, is_active FROM cost_categories LIMIT 1")
                        category = cursor.fetchone()
                        
                        if category:
                            logger.info(f"Usando categoría alternativa: ID {category[0]}")
                            category_id = category[0]
                        else:
                            logger.error("No se pudo encontrar ninguna categoría después de la reparación")
                            return False
                else:
                    # Hay categorías pero no encontramos la específica, usar una existente
                    cursor.execute("SELECT id, category_name, is_active FROM cost_categories LIMIT 1")
                    category = cursor.fetchone()
                    
                    if category:
                        logger.info(f"Usando categoría alternativa: ID {category[0]}")
                        category_id = category[0]
                    else:
                        logger.error("No hay categorías disponibles")
                        return False
            
            # Activar categoría si está inactiva
            if category and not category[2]:  # is_active es 0
                logger.info(f"Activando categoría {category[1]} (ID {category[0]})")
                cursor.execute("UPDATE cost_categories SET is_active = 1 WHERE id = ?", (category[0],))
            
            # Insertar el detalle usando el category_id correcto
            insert_query = """
                INSERT INTO maintenance_cost_details 
                (maintenance_record_id, category_id, item_name, unit_cost, quantity, total_cost, supplier, notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            insert_values = (
                int(maintenance_id), 
                int(category_id), 
                str(item_name).strip(), 
                float(unit_cost), 
                float(quantity), 
                float(total_cost), 
                str(supplier).strip() if supplier else None, 
                str(notes).strip() if notes else None,
                'admin'
            )
            
            cursor.execute(insert_query, insert_values)
            conn.commit()
            
            logger.info(f"Detalle agregado correctamente para mantenimiento {maintenance_id}")
            return True
                
    except Exception as e:
        logger.error(f"Error en add_maintenance_cost_detail: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def get_detailed_cost_sum(maintenance_id):
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
        logger.error(f"Error obteniendo suma detallada: {e}")
        return 0.0

def get_cost_summary_by_category(empresa_id):
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
        logger.error(f"Error obteniendo resumen por categoría: {e}")
        return pd.DataFrame()

def get_machine_cost_analysis(empresa_id, machine_id=None):
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
        logger.error(f"Error obteniendo análisis por máquina: {e}")
        return pd.DataFrame()

def get_supplier_analysis(empresa_id):
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
        logger.error(f"Error obteniendo análisis de proveedores: {e}")
        return pd.DataFrame()

def get_monthly_cost_trend(empresa_id, months=12):
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
        logger.error(f"Error obteniendo tendencia mensual: {e}")
        return pd.DataFrame()

def delete_cost_detail(detail_id):
    """Elimina un detalle de costo"""
    try:
        with get_conn() as conn:
            conn.execute("DELETE FROM maintenance_cost_details WHERE id = ?", (detail_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error eliminando detalle: {e}")
        return False

def delete_cost_category(category_id):
    """Elimina una categoría de costo"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            # Verificar si la categoría tiene registros asociados
            cursor.execute("""
                SELECT COUNT(*) FROM maintenance_cost_details 
                WHERE category_id = ?
            """, (category_id,))
            
            usage_count = cursor.fetchone()[0]
            
            if usage_count > 0:
                # No eliminar, solo desactivar
                cursor.execute("""
                    UPDATE cost_categories 
                    SET is_active = 0 
                    WHERE id = ?
                """, (category_id,))
                conn.commit()
                return True, f"Categoría desactivada (tiene {usage_count} registros asociados)"
            else:
                # Eliminar completamente
                cursor.execute("DELETE FROM cost_categories WHERE id = ?", (category_id,))
                conn.commit()
                return True, "Categoría eliminada completamente"
                
    except Exception as e:
        logger.error(f"Error eliminando categoría: {e}")
        return False, f"Error: {str(e)}"

def apply_filters_to_cost_data(empresa_id, fecha_inicio, fecha_fin, selected_machine, selected_category):
    """Aplica filtros a los datos de costos"""
    try:
        with get_conn() as conn:
            # Verificar qué columnas de fecha existen
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(maintenance_records)")
            available_columns = [col[1] for col in cursor.fetchall()]
            
            # Buscar columna de fecha en orden de prioridad
            date_column = None
            date_priority = ['end_date', 'date_fin', 'fecha_fin', 'performed_at', 'date_performed', 'maintenance_date', 'created_at']
            
            for col in date_priority:
                if col in available_columns:
                    date_column = col
                    break
            
            if not date_column:
                date_column = 'created_at'  # Fallback
            
            # Query base usando la columna correcta
            base_query = f"""
                SELECT 
                    mcd.id,
                    mcd.item_name,
                    mcd.unit_cost,
                    mcd.quantity,
                    mcd.total_cost,
                    mcd.supplier,
                    mcd.notes,
                    mcd.created_at,
                    cc.category_name,
                    m.name as machine_name,
                    m.identifier as machine_identifier,
                    mr.{date_column} as maintenance_date,
                    COALESCE(mt.name, 'Mantenimiento') as maintenance_type
                FROM maintenance_cost_details mcd
                JOIN cost_categories cc ON mcd.category_id = cc.id
                JOIN maintenance_records mr ON mcd.maintenance_record_id = mr.id
                JOIN machinery m ON mr.machinery_id = m.id
                LEFT JOIN maintenance_types mt ON mr.maintenance_type_id = mt.id
                WHERE m.company_id = ?
            """
            
            params = [empresa_id]
            
            # Aplicar filtro de fechas usando la columna correcta
            if fecha_inicio:
                base_query += f" AND DATE(mr.{date_column}) >= ?"
                params.append(fecha_inicio.strftime('%Y-%m-%d'))
            
            if fecha_fin:
                base_query += f" AND DATE(mr.{date_column}) <= ?"
                params.append(fecha_fin.strftime('%Y-%m-%d'))
            
            # Aplicar filtro de máquina
            if selected_machine != "Todas":
                base_query += " AND m.name = ?"
                params.append(selected_machine)
            
            # Aplicar filtro de categoría
            if selected_category != "Todas":
                base_query += " AND cc.category_name = ?"
                params.append(selected_category)
            
            base_query += f" ORDER BY mr.{date_column} DESC, mcd.created_at DESC"
            
            result = pd.read_sql_query(base_query, conn, params=params)
            return result
            
    except Exception as e:
        logger.error(f"Error aplicando filtros: {e}")
        return pd.DataFrame()

def generate_excel_report(empresa_id, detailed_data, summary_data, fecha_inicio, fecha_fin, selected_machine, selected_category):
    """Genera archivo Excel con reporte completo"""
    try:
        import io
        
        # Obtener información de la empresa
        with get_conn() as conn:
            empresa_info = pd.read_sql_query("SELECT name FROM companies WHERE id = ?", conn, params=(empresa_id,))
            empresa_nombre = empresa_info.iloc[0]['name'] if not empresa_info.empty else f"Empresa {empresa_id}"
        
        # Crear buffer en memoria
        output = io.BytesIO()
        
        # Crear workbook con xlsxwriter
        try:
            import xlsxwriter
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            
            # Formatos
            header_format = workbook.add_format({
                'bold': True,
                'font_size': 16,
                'align': 'center',
                'valign': 'vcenter',
                'bg_color': '#2E86AB',
                'font_color': 'white'
            })
            
            subheader_format = workbook.add_format({
                'bold': True,
                'font_size': 12,
                'bg_color': '#E8E8E8'
            })
            
            currency_format = workbook.add_format({'num_format': '$#,##0.00'})
            date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
            
            # Hoja 1: Resumen
            worksheet1 = workbook.add_worksheet('Resumen por Categoría')
            
            # Encabezado principal
            row = 0
            worksheet1.merge_range(f'A{row+1}:F{row+1}', f'REPORTE DE COSTOS DE MANTENIMIENTO - {empresa_nombre}', header_format)
            row += 2
            
            # Información del reporte
            worksheet1.write(row, 0, 'Fecha de generación:', subheader_format)
            worksheet1.write(row, 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            row += 1
            
            worksheet1.write(row, 0, 'Filtros aplicados:', subheader_format)
            row += 1
            
            if fecha_inicio:
                worksheet1.write(row, 1, f'Desde: {fecha_inicio}')
                row += 1
            if fecha_fin:
                worksheet1.write(row, 1, f'Hasta: {fecha_fin}')
                row += 1
            if selected_machine != "Todas":
                worksheet1.write(row, 1, f'Máquina: {selected_machine}')
                row += 1
            if selected_category != "Todas":
                worksheet1.write(row, 1, f'Categoría: {selected_category}')
                row += 1
            
            row += 2
            
            # Tabla resumen
            worksheet1.write(row, 0, 'RESUMEN POR CATEGORÍA', subheader_format)
            row += 1
            
            headers = ['Categoría', 'Transacciones', 'Costo Total', 'Costo Promedio']
            for col, header in enumerate(headers):
                worksheet1.write(row, col, header, subheader_format)
            row += 1
            
            for _, categoria in summary_data.iterrows():
                worksheet1.write(row, 0, categoria['category_name'])
                worksheet1.write(row, 1, categoria['transaction_count'])
                worksheet1.write(row, 2, categoria['total_cost'], currency_format)
                worksheet1.write(row, 3, categoria['avg_cost'], currency_format)
                row += 1
            
            # Hoja 2: Detalles
            worksheet2 = workbook.add_worksheet('Detalles Completos')
            
            # Encabezado
            row = 0
            worksheet2.merge_range(f'A{row+1}:L{row+1}', 'DETALLES COMPLETOS DE COSTOS', header_format)
            row += 2
            
            # Headers de la tabla detallada
            detail_headers = [
                'Categoría', 'Insumo/Servicio', 'Cantidad', 'Costo Unitario', 'Costo Total',
                'Proveedor', 'Máquina', 'Matrícula', 'Tipo Mantenimiento', 'Fecha Mantenimiento', 'Notas'
            ]
            
            for col, header in enumerate(detail_headers):
                worksheet2.write(row, col, header, subheader_format)
            row += 1
            
            # Datos detallados
            for _, detail in detailed_data.iterrows():
                worksheet2.write(row, 0, detail['category_name'])
                worksheet2.write(row, 1, detail['item_name'])
                worksheet2.write(row, 2, detail['quantity'])
                worksheet2.write(row, 3, detail['unit_cost'], currency_format)
                worksheet2.write(row, 4, detail['total_cost'], currency_format)
                worksheet2.write(row, 5, detail.get('supplier', ''))
                worksheet2.write(row, 6, detail['machine_name'])
                worksheet2.write(row, 7, detail.get('machine_identifier', ''))
                worksheet2.write(row, 8, detail['maintenance_type'])
                
                # Fecha de mantenimiento
                try:
                    if pd.notna(detail['maintenance_date']):
                        parsed_date = parse_date_flexible(detail['maintenance_date'])
                        if parsed_date:
                            worksheet2.write(row, 9, parsed_date, date_format)
                        else:
                            worksheet2.write(row, 9, str(detail['maintenance_date']))
                    else:
                        worksheet2.write(row, 9, '')
                except:
                    worksheet2.write(row, 9, str(detail.get('maintenance_date', '')))
                
                worksheet2.write(row, 10, detail.get('notes', ''))
                row += 1
            
            # Ajustar ancho de columnas
            for worksheet in [worksheet1, worksheet2]:
                worksheet.set_column('A:A', 20)  # Categoría
                worksheet.set_column('B:B', 25)  # Insumo
                worksheet.set_column('C:C', 12)  # Cantidad
                worksheet.set_column('D:E', 15)  # Costos
                worksheet.set_column('F:G', 20)  # Proveedor/Máquina
                worksheet.set_column('H:H', 15)  # Matrícula
                worksheet.set_column('I:I', 20)  # Tipo
                worksheet.set_column('J:J', 15)  # Fecha
                worksheet.set_column('K:K', 30)  # Notas
            
            workbook.close()
            
        except ImportError:
            # Fallback sin formato si no está xlsxwriter
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                summary_data.to_excel(writer, sheet_name='Resumen', index=False)
                detailed_data.to_excel(writer, sheet_name='Detalles', index=False)
        
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Error generando Excel: {e}")
        return None

# Mantenemos estas funciones alternativas para compatibilidad
def mostrar_costos_especificos_con_diagnostico(empresa_id, empresa_nombre):
    """Versión con diagnóstico integrado - Redirección a versión principal"""
    return mostrar_costos_especificos(empresa_id, empresa_nombre)

def get_simple_maintenance_records(empresa_id):
    """Versión simplificada que solo usa tablas básicas - Redirección a función principal"""
    return get_maintenance_records(empresa_id)

def get_fallback_maintenance_data(empresa_id):
    """Función de respaldo para obtener datos de mantenimiento - Redirección a función principal"""
    return get_maintenance_records(empresa_id)

def get_maintenance_records_compatible(empresa_id):
    """Versión compatible - Redirección a función principal"""
    return get_maintenance_records(empresa_id)

# Función para activar categorías - Consolida múltiples funciones redundantes
def activar_todas_categorias():
    """Activa todas las categorías inactivas"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE cost_categories SET is_active = 1 WHERE is_active = 0")
            updated = cursor.rowcount
            conn.commit()
            return updated
    except Exception as e:
        logger.error(f"Error activando categorías: {e}")
        return 0

# Alias para mantener compatibilidad
activar_todas_las_categorias = activar_todas_categorias
resolver_problema_categorias_ahora = activar_todas_categorias

# Función para limpiar datos huérfanos
def cleanup_orphaned_cost_details():
    """Limpia detalles de costo huérfanos"""
    try:
        with get_conn() as conn:
            # Eliminar detalles sin mantenimiento asociados
            conn.execute("""
                DELETE FROM maintenance_cost_details 
                WHERE maintenance_record_id NOT IN (
                    SELECT id FROM maintenance_records
                )
            """)
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error limpiando datos huérfanos: {e}")
        return False

# Función para recalcular totales
def recalculate_maintenance_totals(empresa_id):
    """Recalcula totales de mantenimiento basado en detalles"""
    try:
        with get_conn() as conn:
            # Obtener mantenimientos con detalles
            maintenance_with_details = pd.read_sql_query("""
                SELECT 
                    mr.id,
                    mr.cost as original_cost,
                    SUM(mcd.total_cost) as detailed_cost
                FROM maintenance_records mr
                JOIN machinery m ON mr.machinery_id = m.id
                JOIN maintenance_cost_details mcd ON mr.id = mcd.maintenance_record_id
                WHERE m.company_id = ?
                GROUP BY mr.id, mr.cost
            """, conn, params=(empresa_id,))
            
            updated_count = 0
            
            for _, record in maintenance_with_details.iterrows():
                if abs(record['original_cost'] - record['detailed_cost']) > 0.01:
                    # Actualizar costo en maintenance_records
                    conn.execute("""
                        UPDATE maintenance_records 
                        SET cost = ?
                        WHERE id = ?
                    """, (record['detailed_cost'], record['id']))
                    updated_count += 1
            
            conn.commit()
            return updated_count
            
    except Exception as e:
        logger.error(f"Error recalculando totales: {e}")
        return 0