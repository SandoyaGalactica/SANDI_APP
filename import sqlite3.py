import sqlite3
from datetime import date
import pandas as pd
import streamlit as st

DB_PATH = "gestion_empresas.db"

# -----------------------------
# Utilidades de base de datos
# -----------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            serial TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS hourmeters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            reading_date TEXT NOT NULL,
            hours REAL NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            maint_date TEXT NOT NULL,
            mtype TEXT NOT NULL, -- preventivo/correctivo/etc.
            notes TEXT,
            cost REAL,
            next_due_hours REAL, -- próxima intervención sugerida por horas
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
        );
        """
    )

    conn.commit()
    conn.close()


# -----------------------------
# Funciones CRUD simples
# -----------------------------

def list_companies():
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT id, name, created_at FROM companies ORDER BY name", conn)
    return df


def add_company(name: str):
    if not name:
        return False, "Nombre vacío"
    try:
        with get_conn() as conn:
            conn.execute("INSERT INTO companies(name) VALUES (?)", (name.strip(),))
        return True, f"Empresa '{name}' agregada"
    except sqlite3.IntegrityError:
        return False, "Ya existe una empresa con ese nombre"


def delete_company(company_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))


def list_equipment(company_id: int):
    query = (
        "SELECT id, name, category, serial, active FROM equipment WHERE company_id = ? ORDER BY name"
    )
    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=(company_id,))


def add_equipment(company_id: int, name: str, category: str, serial: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO equipment(company_id, name, category, serial) VALUES (?,?,?,?)",
            (company_id, name.strip(), category.strip() if category else None, serial.strip() if serial else None),
        )


def toggle_equipment_active(eq_id: int, new_active: bool):
    with get_conn() as conn:
        conn.execute("UPDATE equipment SET active = ? WHERE id = ?", (1 if new_active else 0, eq_id))


def delete_equipment(eq_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM equipment WHERE id = ?", (eq_id,))


def list_hourmeters(equipment_id: int):
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT id, reading_date, hours, notes FROM hourmeters WHERE equipment_id = ? ORDER BY reading_date DESC, id DESC",
            conn,
            params=(equipment_id,),
        )


def add_hourmeter(equipment_id: int, reading_date: str, hours: float, notes: str | None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO hourmeters(equipment_id, reading_date, hours, notes) VALUES (?,?,?,?)",
            (equipment_id, reading_date, hours, notes),
        )


def list_maintenances(equipment_id: int):
    with get_conn() as conn:
        return pd.read_sql_query(
            "SELECT id, maint_date, mtype, notes, cost, next_due_hours FROM maintenances WHERE equipment_id = ? ORDER BY maint_date DESC, id DESC",
            conn,
            params=(equipment_id,),
        )


def add_maintenance(equipment_id: int, maint_date: str, mtype: str, notes: str | None, cost: float | None, next_due_hours: float | None):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO maintenances(equipment_id, maint_date, mtype, notes, cost, next_due_hours)
            VALUES (?,?,?,?,?,?)
            """,
            (equipment_id, maint_date, mtype, notes, cost, next_due_hours),
        )


# -----------------------------
# UI con Streamlit
# -----------------------------

def sidebar_company_selector():
    st.sidebar.header("Empresas")
    companies_df = list_companies()

    # Selector o aviso si no hay empresas
    if companies_df.empty:
        st.sidebar.info("No hay empresas. Agrega la primera a continuación.")
        default_selection = None
    else:
        names = companies_df["name"].tolist()
        ids = companies_df["id"].tolist()
        if "selected_company_id" not in st.session_state:
            st.session_state.selected_company_id = ids[0]
        # Mapa nombre->id y viceversa
        name_to_id = dict(zip(names, ids))
        current_name = [k for k, v in name_to_id.items() if v == st.session_state.selected_company_id]
        current_name = current_name[0] if current_name else names[0]
        selection = st.sidebar.selectbox("Selecciona empresa", options=names, index=names.index(current_name))
        st.session_state.selected_company_id = name_to_id[selection]
        default_selection = st.session_state.selected_company_id

    # Form para agregar empresa
    with st.sidebar.expander("➕ Agregar empresa", expanded=companies_df.empty):
        with st.form("form_add_company", clear_on_submit=True):
            name = st.text_input("Nombre de la empresa")
            submitted = st.form_submit_button("Agregar")
            if submitted:
                ok, msg = add_company(name)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # Opcional: eliminar empresa seleccionada
    if default_selection is not None:
        with st.sidebar.expander("⚠️ Eliminar empresa"):
            if st.button("Eliminar empresa seleccionada", type="secondary"):
                delete_company(st.session_state.selected_company_id)
                st.warning("Empresa eliminada")
                st.session_state.pop("selected_company_id", None)
                st.rerun()

    return default_selection


def equipment_section(company_id: int):
    st.subheader("Equipos de la empresa")

    # Alta de equipos
    with st.expander("➕ Registrar equipo"):
        with st.form("form_add_equipment", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Nombre del equipo *")
                category = st.text_input("Categoría (ej. excavadora, camión)")
            with col2:
                serial = st.text_input("Serial / Placa")
            submitted = st.form_submit_button("Guardar equipo")
            if submitted:
                if name.strip():
                    add_equipment(company_id, name, category, serial)
                    st.success("Equipo guardado")
                    st.rerun()
                else:
                    st.error("El nombre es obligatorio")

    df = list_equipment(company_id)

    if df.empty:
        st.info("Aún no hay equipos registrados para esta empresa.")
        return

    # Filtros
    categories = sorted([c for c in df["category"].dropna().unique().tolist() if c])
    colf1, colf2 = st.columns(2)
    with colf1:
        cat = st.selectbox("Filtrar por categoría", options=["(todas)"] + categories)
    with colf2:
        solo_activos = st.checkbox("Solo activos", value=True)

    dff = df.copy()
    if cat != "(todas)":
        dff = dff[dff["category"] == cat]
    if solo_activos:
        dff = dff[dff["active"] == 1]

    st.dataframe(dff, use_container_width=True)

    # Acciones por equipo
    st.markdown("---")
    st.markdown("### Detalle de equipo")
    if not dff.empty:
        eq_names = dff["name"].tolist()
        eq_ids = dff["id"].tolist()
        name_to_id = dict(zip(eq_names, eq_ids))
        sel_eq_name = st.selectbox("Selecciona un equipo", options=eq_names)
        eq_id = name_to_id[sel_eq_name]

        colA, colB, colC = st.columns(3)
        with colA:
            if st.button("Alternar activo/inactivo"):
                current_active = int(df[df["id"] == eq_id]["active"].iloc[0])
                toggle_equipment_active(eq_id, not bool(current_active))
                st.info("Estado actualizado")
                st.rerun()
        with colB:
            if st.button("Eliminar equipo", type="secondary"):
                delete_equipment(eq_id)
                st.warning("Equipo eliminado")
                st.rerun()
        with colC:
            st.write("")

        # Tabs: Horómetro y Mantenimientos
        tab1, tab2 = st.tabs(["Horómetros", "Mantenimientos"])

        with tab1:
            with st.form("form_add_hourmeter", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    hm_date = st.date_input("Fecha", value=date.today())
                with c2:
                    hm_hours = st.number_input("Horas acumuladas", min_value=0.0, step=0.5)
                with c3:
                    hm_notes = st.text_input("Notas")
                if st.form_submit_button("Agregar lectura"):
                    add_hourmeter(eq_id, hm_date.isoformat(), float(hm_hours), hm_notes.strip() or None)
                    st.success("Lectura registrada")
                    st.rerun()

            hm_df = list_hourmeters(eq_id)
            if hm_df.empty:
                st.info("Sin lecturas aún.")
            else:
                st.dataframe(hm_df, use_container_width=True)

        with tab2:
            with st.form("form_add_maint", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    m_date = st.date_input("Fecha mantenimiento", value=date.today())
                    m_type = st.selectbox("Tipo", ["Preventivo", "Correctivo", "Predictivo", "Otro"])
                with c2:
                    m_cost = st.number_input("Costo", min_value=0.0, step=1.0, format="%f")
                    next_hours = st.number_input("Próxima intervención (horas)", min_value=0.0, step=1.0, format="%f")
                with c3:
                    notes = st.text_area("Notas")
                if st.form_submit_button("Registrar mantenimiento"):
                    add_maintenance(eq_id, m_date.isoformat(), m_type, notes.strip() or None, float(m_cost) if m_cost else None, float(next_hours) if next_hours else None)
                    st.success("Mantenimiento registrado")
                    st.rerun()

            m_df = list_maintenances(eq_id)
            if m_df.empty:
                st.info("Sin mantenimientos aún.")
            else:
                st.dataframe(m_df, use_container_width=True)


# -----------------------------
# Exportación / Importación CSV
# -----------------------------

def export_company(company_id: int):
    """Exporta tablas relacionadas a una empresa a CSVs en memoria para descarga."""
    with get_conn() as conn:
        comp = pd.read_sql_query("SELECT * FROM companies WHERE id = ?", conn, params=(company_id,))
        eq = pd.read_sql_query("SELECT * FROM equipment WHERE company_id = ?", conn, params=(company_id,))
        if eq.empty:
            hm = pd.DataFrame(columns=["id","equipment_id","reading_date","hours","notes","created_at"])
            mt = pd.DataFrame(columns=["id","equipment_id","maint_date","mtype","notes","cost","next_due_hours","created_at"])
        else:
            ids = tuple(eq["id"].tolist())
            placeholder = ",".join(["?"] * len(ids))
            hm = pd.read_sql_query(f"SELECT * FROM hourmeters WHERE equipment_id IN ({placeholder})", conn, params=ids)
            mt = pd.read_sql_query(f"SELECT * FROM maintenances WHERE equipment_id IN ({placeholder})", conn, params=ids)

    return comp, eq, hm, mt


# -----------------------------
# APP
# -----------------------------

def main():
    st.set_page_config(page_title="Gestión Multiempresa", layout="wide")
    st.title("Gestión de Empresas, Equipos, Horómetros y Mantenimientos")
    st.caption("Prototipo inicial • Streamlit + SQLite • Sin necesidad de editar código para agregar empresas")

    init_db()

    company_id = sidebar_company_selector()

    if company_id is None:
        st.stop()

    # Resumen rápido de empresa
    col1, col2, col3 = st.columns(3)
    with col1:
        eq_count = len(list_equipment(company_id))
        st.metric("Equipos", eq_count)
    with col2:
        # último mantenimiento registrado
        with get_conn() as conn:
            last_m = pd.read_sql_query(
                """
                SELECT maint_date FROM maintenances m
                JOIN equipment e ON e.id = m.equipment_id
                WHERE e.company_id = ?
                ORDER BY maint_date DESC, m.id DESC
                LIMIT 1
                """,
                conn,
                params=(company_id,),
            )
        last_maint = last_m["maint_date"].iloc[0] if not last_m.empty else "—"
        st.metric("Último mantenimiento", last_maint)
    with col3:
        # total costo mantenimientos
        with get_conn() as conn:
            total_cost = pd.read_sql_query(
                """
                SELECT COALESCE(SUM(cost),0) AS total FROM maintenances m
                JOIN equipment e ON e.id = m.equipment_id
                WHERE e.company_id = ?
                """,
                conn,
                params=(company_id,),
            )["total"].iloc[0]
        st.metric("Costo total (registro)", f"${total_cost:,.2f}")

    st.markdown("---")
    equipment_section(company_id)

    st.markdown("---")
    with st.expander("⬇️ Exportar datos de la empresa a CSV"):
        comp, eq, hm, mt = export_company(company_id)
        st.download_button("Descargar empresas.csv", comp.to_csv(index=False).encode("utf-8"), file_name="empresas.csv")
        st.download_button("Descargar equipos.csv", eq.to_csv(index=False).encode("utf-8"), file_name="equipos.csv")
        st.download_button("Descargar horometros.csv", hm.to_csv(index=False).encode("utf-8"), file_name="horometros.csv")
        st.download_button("Descargar mantenimientos.csv", mt.to_csv(index=False).encode("utf-8"), file_name="mantenimientos.csv")


if __name__ == "__main__":
    main()
