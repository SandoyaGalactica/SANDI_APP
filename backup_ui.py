import streamlit as st
from datetime import datetime

def mostrar_panel_backup_simple():
    """Panel simple para gestión de backups"""
    st.subheader("🔄 Sistema de Backup")
    
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
                    for backup in backups[:10]:  # Mostrar solo los últimos 10
                        with st.expander(f"📁 {backup['name']}", expanded=False):
                            col_info, col_action = st.columns([2, 1])
                            
                            with col_info:
                                # Información del backup
                                st.write(f"**Archivo:** {backup['name']}")
                                st.write(f"**Tamaño:** {backup.get('size', 'N/A')} bytes")
                                
                                # Determinar tipo
                                if "auto" in backup['name']:
                                    st.write("**Tipo:** 🤖 Automático")
                                else:
                                    st.write("**Tipo:** 👤 Manual")
                            
                            with col_action:
                                if st.button("↩️ Restaurar", key=f"restore_{backup['sha'][:8]}"):
                                    if st.session_state.get(f"confirm_{backup['sha'][:8]}", False):
                                        # Confirmar restauración
                                        with st.spinner("Restaurando..."):
                                            success, message = restore_database_from_backup(backup)
                                            if success:
                                                st.success("✅ Base de datos restaurada!")
                                                st.balloons()
                                            else:
                                                st.error(f"❌ {message}")
                                        del st.session_state[f"confirm_{backup['sha'][:8]}"]
                                        st.rerun()
                                    else:
                                        st.session_state[f"confirm_{backup['sha'][:8]}"] = True
                                        st.warning("⚠️ Esto reemplazará tu BD actual. Clic de nuevo para confirmar.")
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
