import streamlit as st
import base64
import requests
import json
import os
import shutil
from datetime import datetime
import threading
import time
import atexit

class GitHubBackupManager:
    def __init__(self):
    """Inicializar con tokens desde Streamlit secrets - MODIFICADO"""
    self.repo_owner = None
    self.repo_name = None
    self.access_token = None
    self.api_base = "https://api.github.com"
    self.backup_active = True
    
    # NUEVO: Límites de retención configurables
    self.keep_auto_backups = 10
    self.keep_manual_backups = 5
    
    self._initialize_from_secrets()
    
    def _initialize_from_secrets(self):
        """Inicializar configuración desde secrets"""
        try:
            # Intentar obtener configuración desde secrets
            if "github_backup" in st.secrets:
                config = st.secrets["github_backup"]
                self.repo_owner = config["repo_owner"]
                self.repo_name = config["repo_name"] 
                self.access_token = config["access_token"]
                print("✅ GitHub backup configurado desde secrets")
                return True
            else:
                print("⚠️ Configuración de GitHub backup no encontrada en secrets")
                return False
                
        except Exception as e:
            print(f"⚠️ Error configurando GitHub backup: {str(e)}")
            return False
    
    def is_configured(self):
        """Verificar si está configurado correctamente"""
        return all([self.repo_owner, self.repo_name, self.access_token])
    
    def test_connection(self):
        """Probar conexión con GitHub"""
        if not self.is_configured():
            return False, "Configuración incompleta"
        
        try:
            url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}"
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return True, "Conexión exitosa con GitHub"
            elif response.status_code == 401:
                return False, "Token inválido o expirado"
            elif response.status_code == 404:
                return False, "Repositorio no encontrado"
            else:
                return False, f"Error {response.status_code}: {response.text}"
                
        except requests.exceptions.Timeout:
            return False, "Timeout conectando con GitHub"
        except Exception as e:
            return False, f"Error de conexión: {str(e)}"
    
    def ensure_backup_folder(self):
        """Asegurar que existe la carpeta de backups en el repositorio"""
        try:
            folder_path = "database_backups"
            url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{folder_path}"
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 404:
                # Crear carpeta creando un archivo README
                readme_content = base64.b64encode(
                    "# Database Backups\n\nEsta carpeta contiene los backups automáticos de la base de datos SANDI.\n".encode()
                ).decode()
                
                readme_data = {
                    "message": "Crear carpeta de backups",
                    "content": readme_content,
                    "branch": "deploy"
                }
                
                readme_url = f"{url}/README.md"
                create_response = requests.put(readme_url, json=readme_data, headers=headers)
                
                if create_response.status_code == 201:
                    print("✅ Carpeta de backups creada")
                    return True
                else:
                    print(f"❌ Error creando carpeta: {create_response.text}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error verificando carpeta de backups: {str(e)}")
            return False
    
    def upload_database(self, db_path, custom_message=None, is_auto=False):
        """Subir base de datos como backup a GitHub"""
        if not self.is_configured():
            return False, "GitHub backup no configurado"
        
        if not os.path.exists(db_path):
            return False, f"Archivo de base de datos no encontrado: {db_path}"
        
        try:
            # Asegurar que existe la carpeta
            if not self.ensure_backup_folder():
                return False, "No se pudo crear carpeta de backups"
            
            # Leer y encodear la base de datos
            with open(db_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('utf-8')
            
            # Generar nombre de archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_type = "auto" if is_auto else "manual"
            filename = f"database_backups/sandi_{backup_type}_{timestamp}.db"
            
            # URL para crear/actualizar archivo
            file_url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{filename}"
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            # Preparar datos
            commit_message = custom_message or f"Database {backup_type} backup - {timestamp}"
            data = {
                "message": commit_message,
                "content": content,
                "branch": "deploy"
            }
            
            # Crear archivo
            response = requests.put(file_url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 201:
                file_info = response.json()
                print(f"✅ Backup subido a GitHub: {filename}")
                return True, f"Backup guardado: {filename}"
            else:
                error_info = response.json() if response.content else {"message": "Error desconocido"}
                error_msg = error_info.get("message", f"HTTP {response.status_code}")
                return False, f"Error GitHub: {error_msg}"
                
        except requests.exceptions.Timeout:
            return False, "Timeout subiendo backup"
        except Exception as e:
            return False, f"Error subiendo backup: {str(e)}"
    
    def list_backups(self):
        """Listar backups disponibles en GitHub"""
        if not self.is_configured():
            return []
        
        try:
            url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/database_backups"
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                files = response.json()
                # Filtrar solo archivos .db y ordenar por fecha (más reciente primero)
                backups = [f for f in files if f["name"].endswith(".db")]
                backups.sort(key=lambda x: x["name"], reverse=True)
                return backups
            else:
                print(f"❌ Error listando backups: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Error listando backups: {str(e)}")
            return []
    
    def download_backup(self, backup_info, local_path):
        """Descargar backup desde GitHub"""
        try:
            # Crear backup de la base actual
            if os.path.exists(local_path):
                backup_current = f"{local_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(local_path, backup_current)
                print(f"💾 Backup de seguridad creado: {backup_current}")
            
            # Obtener contenido del archivo desde GitHub
            download_url = backup_info.get("download_url")
            if not download_url:
                return False, "URL de descarga no disponible"
            
            response = requests.get(download_url, timeout=30)
            
            if response.status_code == 200:
                # Guardar archivo local
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"✅ Backup descargado: {local_path}")
                return True, "Base de datos restaurada exitosamente"
            else:
                return False, f"Error descargando: HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Error en descarga: {str(e)}"
    
    def cleanup_old_backups(self, keep_auto=None, keep_manual=None):
    """Limpiar backups antiguos - MODIFICADO para usar límites configurables"""
    try:
        # Usar límites configurables si no se especifican
        if keep_auto is None:
            keep_auto = getattr(self, 'keep_auto_backups', 10)
        if keep_manual is None:
            keep_manual = getattr(self, 'keep_manual_backups', 5)
        
        backups = self.list_backups()
        
        # Separar backups automáticos y manuales
        auto_backups = [b for b in backups if "auto" in b["name"]]
        manual_backups = [b for b in backups if "manual" in b["name"]]
        
        deleted_count = 0
        
        # Eliminar backups automáticos antiguos
        if len(auto_backups) > keep_auto:
            to_delete_auto = auto_backups[keep_auto:]
            for backup in to_delete_auto:
                if self._delete_backup(backup):
                    print(f"🗑️ Backup automático eliminado: {backup['name']}")
                    deleted_count += 1
        
        # Eliminar backups manuales antiguos
        if len(manual_backups) > keep_manual:
            to_delete_manual = manual_backups[keep_manual:]
            for backup in to_delete_manual:
                if self._delete_backup(backup):
                    print(f"🗑️ Backup manual eliminado: {backup['name']}")
                    deleted_count += 1
        
        return deleted_count
        
    except Exception as e:
        print(f"❌ Error limpiando backups antiguos: {str(e)}")
        return 0
    
    def _delete_backup(self, backup_info):
        """Eliminar un backup específico"""
        try:
            url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/contents/{backup_info['path']}"
            headers = {
                "Authorization": f"token {self.access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            data = {
                "message": f"Cleanup: Eliminar backup antiguo {backup_info['name']}",
                "sha": backup_info["sha"],
                "branch": "deploy"
            }
            
            response = requests.delete(url, json=data, headers=headers)
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ Error eliminando backup: {str(e)}")
            return False

# Instancia global
github_backup_manager = GitHubBackupManager()

# Variables para el sistema de auto-backup
_backup_thread = None
_backup_active = True
_last_backup_time = None

def setup_github_auto_backup(db_path, interval_minutes=30):
    """Configurar sistema de backup automático"""
    global _backup_thread, _backup_active
    
    if not github_backup_manager.is_configured():
        print("⚠️ GitHub backup no configurado, auto-backup deshabilitado")
        return False
    
    # Probar conexión
    success, message = github_backup_manager.test_connection()
    if not success:
        print(f"⚠️ No se pudo conectar con GitHub: {message}")
        return False
    
    _backup_active = True
    _backup_thread = threading.Thread(
        target=_auto_backup_worker, 
        args=(db_path, interval_minutes), 
        daemon=True
    )
    _backup_thread.start()
    
    # Registrar limpieza al salir
    atexit.register(stop_auto_backup)
    
    print(f"✅ Auto-backup GitHub configurado (cada {interval_minutes} minutos)")
    return True

def _auto_backup_worker(db_path, interval_minutes):
    """Worker thread para realizar backups automáticos"""
    global _backup_active, _last_backup_time
    
    while _backup_active:
        try:
            current_time = datetime.now()
            
            # Verificar si es tiempo de hacer backup
            if (_last_backup_time is None or 
                (current_time - _last_backup_time).total_seconds() >= interval_minutes * 60):
                
                if os.path.exists(db_path):
                    success, message = github_backup_manager.upload_database(db_path, is_auto=True)
                    if success:
                        _last_backup_time = current_time
                        print(f"🔄 Auto-backup completado: {current_time.strftime('%H:%M:%S')}")
                        
                        # Limpiar backups antiguos ocasionalmente
                        if current_time.minute == 0:  # Una vez por hora
                            github_backup_manager.cleanup_old_backups()
                    else:
                        print(f"⚠️ Auto-backup falló: {message}")
            
            # Esperar 5 minutos antes del próximo chequeo
            time.sleep(300)
            
        except Exception as e:
            print(f"❌ Error en auto-backup worker: {str(e)}")
            time.sleep(300)

def stop_auto_backup():
    """Detener sistema de auto-backup"""
    global _backup_active
    _backup_active = False
    print("🛑 Auto-backup detenido")

# Funciones para usar en db_utils.py
def github_manual_backup(db_path):
    """Realizar backup manual a GitHub"""
    if not github_backup_manager.is_configured():
        return False, "GitHub backup no configurado"
    
    return github_backup_manager.upload_database(db_path, "Manual backup", is_auto=False)

def get_github_backups():
    """Obtener lista de backups en GitHub"""
    return github_backup_manager.list_backups()

def restore_from_github(backup_info, local_path):
    """Restaurar desde backup de GitHub"""
    return github_backup_manager.download_backup(backup_info, local_path)

def test_github_connection():
    """Probar conexión con GitHub"""
    return github_backup_manager.test_connection()

def get_github_manager():
    """Obtener instancia del manager"""
    return github_backup_manager


def get_backups_with_details(self):
    """Obtener lista detallada de backups con información formateada"""
    if not self.is_configured():
        return []
    
    try:
        backups = self.list_backups()
        detailed_backups = []
        
        for backup in backups:
            # Parsear información del nombre del archivo
            filename = backup["name"]
            file_info = self._parse_backup_filename(filename)
            
            detailed_backups.append({
                "name": filename,
                "display_name": file_info["display_name"],
                "type": file_info["type"],
                "date": file_info["date"],
                "time": file_info["time"],
                "timestamp": file_info["timestamp"],
                "size": backup.get("size", 0),
                "download_url": backup.get("download_url"),
                "sha": backup.get("sha"),
                "path": backup.get("path"),
                "raw_info": backup
            })
        
        # Ordenar por timestamp (más reciente primero)
        detailed_backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return detailed_backups
        
    except Exception as e:
        print(f"❌ Error obteniendo detalles de backups: {str(e)}")
        return []

def _parse_backup_filename(self, filename):
    """Parsear nombre de archivo de backup para extraer información"""
    try:
        # Formato esperado: sandi_auto_20241215_143022.db o sandi_manual_20241215_143022.db
        parts = filename.replace(".db", "").split("_")
        
        if len(parts) >= 4:
            backup_type = parts[1]  # auto o manual
            date_part = parts[2]    # 20241215
            time_part = parts[3]    # 143022
            
            # Formatear fecha legible
            year = date_part[:4]
            month = date_part[4:6]
            day = date_part[6:8]
            
            hour = time_part[:2]
            minute = time_part[2:4]
            second = time_part[4:6]
            
            formatted_date = f"{day}/{month}/{year}"
            formatted_time = f"{hour}:{minute}:{second}"
            
            type_icon = "🤖" if backup_type == "auto" else "👤"
            type_text = "Automático" if backup_type == "auto" else "Manual"
            
            display_name = f"{type_icon} {type_text} - {formatted_date} {formatted_time}"
            
            return {
                "display_name": display_name,
                "type": backup_type,
                "date": formatted_date,
                "time": formatted_time,
                "timestamp": f"{date_part}_{time_part}"
            }
        else:
            # Formato no reconocido
            return {
                "display_name": filename,
                "type": "unknown",
                "date": "N/A",
                "time": "N/A",
                "timestamp": "00000000_000000"
            }
            
    except Exception as e:
        return {
            "display_name": filename,
            "type": "error",
            "date": "N/A", 
            "time": "N/A",
            "timestamp": "00000000_000000"
        }

def update_retention_limits(self, keep_auto=None, keep_manual=None):
    """Actualizar límites de retención de backups"""
    try:
        if keep_auto is not None:
            self.keep_auto_backups = max(1, min(keep_auto, 50))  # Entre 1 y 50
        
        if keep_manual is not None:
            self.keep_manual_backups = max(1, min(keep_manual, 20))  # Entre 1 y 20
        
        print(f"✅ Límites actualizados: Auto={self.keep_auto_backups}, Manual={self.keep_manual_backups}")
        return True
        
    except Exception as e:
        print(f"❌ Error actualizando límites: {str(e)}")
        return False

def get_retention_limits(self):
    """Obtener límites actuales de retención"""
    return {
        "auto": getattr(self, 'keep_auto_backups', 10),
        "manual": getattr(self, 'keep_manual_backups', 5)
    }
