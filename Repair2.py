def repair_database():
    """Repara problemas comunes de SQLite"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Verificar integridad
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            print(f"Problema de integridad: {integrity}")
            return False
        
        # Reindexar
        conn.execute("REINDEX")
        
        # Vacuum para optimizar
        conn.execute("VACUUM")
        
        # Configurar WAL apropiadamente
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        conn.close()
        print("Base de datos reparada correctamente")
        return True
    except Exception as e:
        print(f"Error reparando base de datos: {e}")
        return False