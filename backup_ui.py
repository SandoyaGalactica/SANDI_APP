import streamlit as st
from datetime import datetime

def mostrar_panel_backup_simple():
    """Panel simple para gestión de backups"""
    st.subheader("📤 Sistema de Backup")
    
    try:
        from db_utils import (
            get_backup_status, 
            manual_backup_database, 
            get_available_backups,
            restore_database_from_backup
        )
        
        # Mostrar estado del sistema
        status = get_backup_status()
        
        if status["available"]:
            if status["connected"]:
                st.success(f"✅ GitHub conectado: {status['message']}")
                
                # Información del estado
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Backups totales", status.get("total_backups", 0))
                with col2:
                    auto_status = "🟢 Activo" if status.get("auto_backup_active", False) else "🔴 Inactivo"
                    st.metric("Auto-backup", auto_status)
                with col3:
                    last_backup = status.get("last_backup", "Ninguno")
                    if last_backup != "Ninguno":
                        last_backup = last_backup.replace("sandi_", "").replace(".db", "")
                    st.metric("Último backup", last_backup)
                
                st.divider()
                
                # Botones de acción
                col_backup, col_refresh = st.columns(2)
                
                with col_backup:
                    if st.button("💾 Backup Manual", use_container_width=True):
                        with st.spinner("Creando backup..."):
                            success, message = manual_backup_database()
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
                        st.rerun()
                
                with col_refresh:
                    if st.button("🔄 Actualizar", use_container_width=True):
                        st.rerun()
                
                # Lista de backups
                st.subheader("📋 Backups Disponibles")
                backups = get_available_backups()
                
                if backups:
                    # Crear una lista formateada para mostrar en el selectbox
                    backup_options = []
                    for backup in backups:
                        name = backup['name']
                        if "_" in name:
                            parts = name.replace(".db", "").split("_")
                            if len(parts) >= 4:
                                backup_type = parts[1]  # auto o manual
                                date_str = parts[2]
                                time_str = parts[3]
                                
                                # Formatear fecha y hora
                                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                                formatted_time = f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
                                display_name = f"{'Manual' if backup_type == 'manual' else 'Auto'} - {formatted_date} {formatted_time}"
                            else:
                                display_name = name
                        else:
                            display_name = name
                        
                        backup_options.append({"display": display_name, "backup": backup})
                    
                    # Selectbox para elegir backup
                    selected_backup_idx = st.selectbox(
                        "Seleccionar backup para restaurar:",
                        range(len(backup_options)),
                        format_func=lambda i: backup_options[i]["display"]
                    )
                    
                    selected_backup = backup_options[selected_backup_idx]["backup"]
                    
                    # Mostrar detalles del backup seleccionado
                    with st.expander("Detalles del backup seleccionado"):
                        col_info, col_action = st.columns([2, 1])
                        
                        with col_info:
                            # Información del backup
                            st.write(f"**Archivo:** {selected_backup['name']}")
                            st.write(f"**Tamaño:** {selected_backup.get('size', 'N/A')} bytes")
                            
                            # Determinar tipo
                            if "auto" in selected_backup['name']:
                                st.write("**Tipo:** 🤖 Automático")
                            else:
                                st.write("**Tipo:** 👤 Manual")
                    
                    # Botón para restaurar
                    if st.button("↩️ Restaurar Backup Seleccionado", type="primary"):
                        # Primera advertencia
                        st.warning("⚠️ Esta acción reemplazará la base de datos actual. ¿Estás seguro?")
                        
                        # Mostrar confirmación
                        st.session_state["confirm_restore"] = True
                        st.session_state["backup_to_restore"] = selected_backup
                        st.rerun()
                    
                    # Confirmación final
                    if st.session_state.get("confirm_restore", False) and st.session_state.get("backup_to_restore"):
                        st.error("⚠️ CONFIRMAR RESTAURACIÓN")
                        st.error("Esta acción NO SE PUEDE DESHACER")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ SÍ, RESTAURAR AHORA"):
                                with st.spinner("Restaurando..."):
                                    success, message = restore_database_from_backup(
                                        st.session_state["backup_to_restore"]
                                    )
                                    if success:
                                        st.success("✅ Base de datos restaurada!")
                                        st.balloons()
                                        # Limpiar estado
                                        if "confirm_restore" in st.session_state:
                                            del st.session_state["confirm_restore"]
                                        if "backup_to_restore" in st.session_state:
                                            del st.session_state["backup_to_restore"]
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                        
                        with col2:
                            if st.button("❌ CANCELAR"):
                                if "confirm_restore" in st.session_state:
                                    del st.session_state["confirm_restore"]
                                if "backup_to_restore" in st.session_state:
                                    del st.session_state["backup_to_restore"]
                                st.rerun()
                else:
                    st.info("No hay backups disponibles")
            else:
                st.error(f"❌ Error de conexión: {status['message']}")
        else:
            st.warning("⚠️ Sistema de backup no disponible")
        
    except ImportError:
        st.error("❌ Funciones de backup no disponibles")
    except Exception as e:
        st.error(f"❌ Error en panel de backup: {str(e)}")

def mostrar_estado_backup_sidebar():
    """Mostrar estado de backup en sidebar"""
    try:
        from db_utils import get_backup_status
        
        status = get_backup_status()
        
        if status["available"] and status["connected"]:
            st.sidebar.success("☁️ Backup: Activo")
            if status.get("auto_backup_active"):
                st.sidebar.caption("🤖 Auto-backup funcionando")
        else:
            st.sidebar.warning("☁️ Backup: Desconectado")
            
    except:
        st.sidebar.info("☁️ Backup: No configurado")
