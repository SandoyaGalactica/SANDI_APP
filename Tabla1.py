import sqlite3
conn = sqlite3.connect('gestion_empresas.db')
conn.execute('DROP TABLE IF EXISTS odometer_logs')
conn.commit()
conn.close()