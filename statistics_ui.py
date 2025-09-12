"""
Interfaz de Usuario - Módulo de Estadísticas Avanzadas
Sistema de dashboards interactivos y análisis predictivo

Integración con SANDI v2.0
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, date
import time 
import numpy as np


# Importar módulo de estadísticas
from statistics_module import (
    AdvancedStatistics, PredictiveAnalyzer, EfficiencyAnalyzer, 
    FinancialAnalyzer, ConsumptionAnalyzer,
    create_efficiency_chart, create_predictive_maintenance_chart,
    create_financial_dashboard, create_consumption_dashboard,
    calculate_kpis, format_currency, format_percentage, get_conn, get_status_color
)

def mostrar_estadisticas_avanzadas(empresa_id, empresa_nombre):
    """Función principal del módulo de estadísticas"""
    
    # CSS personalizado para el módulo
    st.markdown("""
    <style>
    /* Estilos específicos para estadísticas */
    .stats-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.2);
    }
    
    .kpi-card {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        transition: all 0.3s ease;
    }
    
    .kpi-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.2);
    }
    
    .kpi-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 5px;
    }
    
    .kpi-label {
        font-size: 0.9rem;
        opacity: 0.8;
    }
    
    .metric-excellent { color: #28a745; }
    .metric-good { color: #17a2b8; }
    .metric-regular { color: #ffc107; }
    .metric-poor { color: #dc3545; }
    
    .analysis-section {
        background: white;
        border-radius: 12px;
        padding: 25px;
        margin: 15px 0;
        box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
    }
    
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #2c3e50;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
    }
    
    .section-icon {
        margin-right: 10px;
        font-size: 1.5rem;
    }
    
    .alert-card {
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid;
    }
    
    .alert-critical {
        background-color: #fff5f5;
        border-left-color: #e53e3e;
        color: #c53030;
    }
    
    .alert-warning {
        background-color: #fffaf0;
        border-left-color: #dd6b20;
        color: #c05621;
    }
    
    .alert-info {
        background-color: #ebf8ff;
        border-left-color: #3182ce;
        color: #2c5282;
    }
    
    .recommendation-item {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        transition: all 0.3s ease;
    }
    
    .recommendation-item:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    .filter-container {
        background: #f8fafc;
        border-radius: 10px;
        padding: 20px;
        margin: 20px 0;
        border: 1px solid #e2e8f0;
    }
    
    .progress-bar {
        width: 100%;
        height: 8px;
        background-color: #e2e8f0;
        border-radius: 4px;
        overflow: hidden;
        margin: 10px 0;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        transition: width 0.3s ease;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .stats-container {
            padding: 15px;
        }
        
        .kpi-card {
            padding: 15px;
        }
        
        .kpi-value {
            font-size: 2rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header principal del módulo
    st.markdown(f"""
    <div class="stats-container">
        <h1>📊 Análisis Estadístico Avanzado</h1>
        <h3>{empresa_nombre}</h3>
        <p>Dashboard interactivo de análisis predictivo, eficiencia operacional y análisis financiero</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Inicializar sesión si es necesario
    if 'stats_cache' not in st.session_state:
        st.session_state.stats_cache = {}
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = None
    
    # Controles principales
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown("### 🎛️ Panel de Control")
    
    with col2:
        if st.button("🔄 Actualizar Datos", type="secondary"):
            st.session_state.stats_cache = {}
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    
    with col3:
        auto_refresh = st.checkbox("Auto-actualizar", value=False)
    
    # Auto-refresh cada 5 minutos si está habilitado
    if auto_refresh:
        if (st.session_state.last_refresh is None or 
            (datetime.now() - st.session_state.last_refresh).seconds > 300):
            st.session_state.stats_cache = {}
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    
    # Mostrar KPIs principales
    mostrar_kpis_principales(empresa_id)
    
    # Navegación por pestañas
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Dashboard General", 
        "🔮 Análisis Predictivo", 
        "⚡ Eficiencia Operacional",
        "💰 Análisis Financiero",
        "⛽ Análisis de Consumo"
    ])
    
    with tab1:
        mostrar_dashboard_general(empresa_id)
    
    with tab2:
        mostrar_analisis_predictivo(empresa_id)
    
    with tab3:
        mostrar_analisis_eficiencia(empresa_id)
    
    with tab4:
        mostrar_analisis_financiero(empresa_id)
    
    with tab5:
        mostrar_analisis_consumo(empresa_id)

def mostrar_kpis_principales(empresa_id):
    """Muestra KPIs principales en tarjetas - SIN score de salud duplicado"""
    try:
        with st.spinner("Calculando KPIs principales..."):
            kpis = calculate_kpis(empresa_id)
        
        if not kpis:
            st.warning("No hay suficientes datos para calcular KPIs")
            return
        
        # SOLO UNA FILA DE MÉTRICAS (eliminar la cuarta columna del score de salud)
        col1, col2, col3 = st.columns(3)  # Era 4 columnas, ahora 3
        
        with col1:
            efficiency_color = get_metric_color(kpis.get('avg_efficiency_score', 0))
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value {efficiency_color}">{kpis.get('avg_efficiency_score', 0)}</div>
                <div class="kpi-label">Score Eficiencia Promedio</div>
                <div style="font-size: 0.8rem; margin-top: 5px;">
                    {kpis.get('efficiency_category', 'N/A')}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            roi_color = get_metric_color(kpis.get('avg_roi_percentage', 0))
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value {roi_color}">{kpis.get('avg_roi_percentage', 0)}%</div>
                <div class="kpi-label">ROI Promedio</div>
                <div style="font-size: 0.8rem; margin-top: 5px;">
                    {kpis.get('roi_category', 'N/A')}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            utilization_color = get_metric_color(kpis.get('utilization_rate', 0))
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value {utilization_color}">{kpis.get('utilization_rate', 0)}%</div>
                <div class="kpi-label">Tasa de Utilización</div>
                <div style="font-size: 0.8rem; margin-top: 5px;">
                    {kpis.get('active_machines', 0)}/{kpis.get('total_machines', 0)} activas
                </div>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error calculando KPIs: {e}")



def mostrar_dashboard_general(empresa_id):
    """Dashboard general con resumen de todos los módulos"""
    
    
    try:
        mostrar_resumen_ejecutivo(empresa_id)
        # Inicializar analizadores
        stats = AdvancedStatistics(empresa_id)
        
        if stats._get_base_data()['machinery'].empty:
            st.info("No hay máquinas registradas para mostrar estadísticas")
            return
        
        # Columnas para diferentes análisis
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🎯 Resumen de Eficiencia")
            efficiency_analyzer = EfficiencyAnalyzer(stats)
            efficiency_data = efficiency_analyzer.analyze_operational_efficiency()
            
            if not efficiency_data.empty:
                # Top 5 máquinas por eficiencia
                top_machines = efficiency_data.head(5)
                
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=top_machines['machine_name'],
                    y=top_machines['efficiency_score'],
                    marker_color=['#28a745' if score >= 70 else '#ffc107' if score >= 50 else '#dc3545' 
                                for score in top_machines['efficiency_score']],
                    text=[f"{score:.1f}" for score in top_machines['efficiency_score']],
                    textposition='auto'
                ))
                
                fig.update_layout(
                    title="Top 5 Máquinas - Score de Eficiencia",
                    xaxis_title="Máquinas",
                    yaxis_title="Score de Eficiencia",
                    height=400,
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Datos insuficientes para análisis de eficiencia")
        
        with col2:
            st.subheader("💰 Resumen Financiero")
            financial_analyzer = FinancialAnalyzer(stats)
            roi_data = financial_analyzer.calculate_roi_analysis()
            
            if not roi_data.empty:
                # Distribución de rentabilidad
                profit_counts = roi_data['profitability_status'].value_counts()
                
                fig = go.Figure(data=[go.Pie(
                    labels=profit_counts.index,
                    values=profit_counts.values,
                    hole=0.4,
                    marker_colors=['#28a745', '#17a2b8', '#ffc107', '#fd7e14', '#dc3545'][:len(profit_counts)]
                )])
                
                fig.update_layout(
                    title="Distribución de Rentabilidad",
                    height=400,
                    annotations=[dict(text=f'{len(roi_data)}<br>Máquinas', x=0.5, y=0.5, font_size=20, showarrow=False)]
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Datos insuficientes para análisis financiero")
        
        # Sección de alertas y recomendaciones
        mostrar_alertas_generales(empresa_id, stats)
        
        # Trends temporales
        mostrar_trends_temporales(empresa_id, stats)
        
    except Exception as e:
        st.error(f"Error en dashboard general: {e}")

def mostrar_analisis_predictivo(empresa_id):
    """Análisis predictivo de mantenimiento y consumo"""
    
    st.markdown("""
    <div class="analysis-section">
        <div class="section-header">
            <span class="section-icon">🔮</span>
            Análisis Predictivo
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Controles del análisis
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        prediction_days = st.slider("Días de predicción", 7, 90, 30)
    
    with col2:
        confidence_level = st.selectbox("Nivel de confianza", [0.8, 0.85, 0.9, 0.95], index=1)
    
    with col3:
        include_trends = st.checkbox("Incluir análisis de tendencias", value=True)
    
    try:
        stats = AdvancedStatistics(empresa_id)
        predictive_analyzer = PredictiveAnalyzer(stats)
        
        # Predicciones de mantenimiento
        st.subheader("🔧 Predicciones de Mantenimiento")
        
        with st.spinner("Analizando patrones de mantenimiento..."):
            maintenance_predictions = predictive_analyzer.predict_maintenance_needs(
                days_ahead=prediction_days, 
                confidence_level=confidence_level
            )
        
        if not maintenance_predictions.empty:
            # Gráfico de predicciones
            chart = create_predictive_maintenance_chart(maintenance_predictions)
            if chart:
                st.plotly_chart(chart, use_container_width=True)
            
            # Tabla de predicciones críticas
            critical_predictions = maintenance_predictions[
                maintenance_predictions['urgency_level'].isin(['CRÍTICO', 'ALTO'])
            ]
            
            if not critical_predictions.empty:
                st.subheader("⚠️ Mantenimientos Urgentes")
                
                for _, pred in critical_predictions.iterrows():
                    alert_class = "alert-critical" if pred['urgency_level'] == 'CRÍTICO' else "alert-warning"
                    
                    st.markdown(f"""
                    <div class="alert-card {alert_class}">
                        <strong>{pred['machine_name']}</strong><br>
                        <small>Clasificación: {pred['classification']}</small><br>
                        Predicción: <strong>{pred['predicted_next_days']} días</strong><br>
                        Risk Score: <strong>{pred['risk_score']}%</strong><br>
                        Último mantenimiento: {pred['last_maintenance']}<br>
                        Confianza: {pred['confidence']}%
                    </div>
                    """, unsafe_allow_html=True)
            
            # Tabla completa
            st.subheader("📋 Todas las Predicciones")
            st.dataframe(
                maintenance_predictions[[
                    'machine_name', 'classification', 'predicted_next_days', 
                    'predicted_date', 'risk_score', 'urgency_level'
                ]],
                use_container_width=True
            )
        else:
            st.info("No hay suficientes datos históricos para generar predicciones de mantenimiento")
        
        # Predicciones de combustible
        st.subheader("⛽ Predicciones de Consumo")
        
        with st.spinner("Analizando patrones de consumo..."):
            fuel_predictions = predictive_analyzer.predict_fuel_consumption(days_ahead=prediction_days)
        
        if not fuel_predictions.empty:
            # Mostrar predicciones
            for _, pred in fuel_predictions.iterrows():
                alert_class = {
                    'CRÍTICO': 'alert-critical',
                    'ALTO': 'alert-warning',
                    'NORMAL': 'alert-info'
                }.get(pred['alert_level'], 'alert-info')
                
                st.markdown(f"""
                <div class="alert-card {alert_class}">
                    <strong>{pred['machine_name']}</strong><br>
                    Consumo promedio: <strong>{pred['avg_daily_consumption']:.2f} gal/día</strong><br>
                    Predicción {prediction_days} días: <strong>{pred['predicted_consumption']:.2f} gal</strong><br>
                    Tendencia: <strong>{pred['trend_direction']}</strong><br>
                    Días desde última recarga: <strong>{pred['days_since_last_refuel']}</strong>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hay suficientes datos de combustible para generar predicciones")
        
    except Exception as e:
        st.error(f"Error en análisis predictivo: {e}")

def mostrar_analisis_eficiencia(empresa_id):
    """Análisis detallado de eficiencia operacional"""
    
    st.markdown("""
    <div class="analysis-section">
        <div class="section-header">
            <span class="section-icon">⚡</span>
            Análisis de Eficiencia Operacional
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Filtros
    with st.expander("🎛️ Configurar Análisis", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            period_filter = st.selectbox("Período de análisis", 
                                       ["Últimos 30 días", "Últimos 60 días", "Últimos 90 días"])
        
        with col2:
            min_hours = st.number_input("Horas mínimas trabajadas", min_value=0, value=10)
        
        with col3:
            sort_by = st.selectbox("Ordenar por", 
                                 ["Eficiencia", "Utilización", "Horas trabajadas"])
    
    try:
        stats = AdvancedStatistics(empresa_id)
        efficiency_analyzer = EfficiencyAnalyzer(stats)
        
        with st.spinner("Analizando eficiencia operacional..."):
            efficiency_data = efficiency_analyzer.analyze_operational_efficiency()
        
        if efficiency_data.empty:
            st.info("No hay datos suficientes para análisis de eficiencia")
            return
        
        # Filtrar por horas mínimas
        filtered_data = efficiency_data[efficiency_data['work_hours_30d'] >= min_hours]
        
        if filtered_data.empty:
            st.warning(f"No hay máquinas con más de {min_hours} horas trabajadas")
            return
        
        # Dashboard de eficiencia
        chart = create_efficiency_chart(filtered_data)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        
        # Análisis por categorías
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏆 Top Performers")
            top_performers = filtered_data.head(5)
            
            for _, machine in top_performers.iterrows():
                performance_color = get_status_color(machine['performance_category'])
                
                st.markdown(f"""
                <div class="recommendation-item">
                    <strong style="color: {performance_color};">{machine['machine_name']}</strong><br>
                    Score: <strong>{machine['efficiency_score']:.1f}</strong> | 
                    Utilización: <strong>{machine['utilization_rate']:.1f}%</strong><br>
                    Operador principal: {machine['primary_operator']}<br>
                    Horas trabajadas: {machine['work_hours_30d']:.1f}h
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.subheader("⚠️ Necesitan Atención")
            low_performers = filtered_data[filtered_data['efficiency_score'] < 50].head(5)
            
            if not low_performers.empty:
                for _, machine in low_performers.iterrows():
                    st.markdown(f"""
                    <div class="recommendation-item" style="border-left: 4px solid #dc3545;">
                        <strong>{machine['machine_name']}</strong><br>
                        Score: <strong>{machine['efficiency_score']:.1f}</strong> | 
                        Utilización: <strong>{machine['utilization_rate']:.1f}%</strong><br>
                        <small style="color: #dc3545;">Requiere optimización</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("Todas las máquinas tienen performance aceptable")
        
        # Tabla detallada
        st.subheader("📊 Análisis Detallado")
        
        # Preparar datos para mostrar
        display_data = filtered_data[[
            'machine_name', 'classification', 'efficiency_score', 'efficiency_rank',
            'utilization_rate', 'work_hours_30d', 'avg_hours_per_day',
            'primary_operator', 'performance_category'
        ]].copy()
        
        # Formatear columnas
        display_data['efficiency_score'] = display_data['efficiency_score'].round(1)
        display_data['utilization_rate'] = display_data['utilization_rate'].round(1)
        display_data['work_hours_30d'] = display_data['work_hours_30d'].round(1)
        display_data['avg_hours_per_day'] = display_data['avg_hours_per_day'].round(1)
        
        st.dataframe(display_data, use_container_width=True)
        
        # Recomendaciones de mejora
        mostrar_recomendaciones_eficiencia(filtered_data)
        
    except Exception as e:
        st.error(f"Error en análisis de eficiencia: {e}")

def mostrar_analisis_financiero(empresa_id):
    """Análisis financiero detallado"""
    
    st.markdown("""
    <div class="analysis-section">
        <div class="section-header">
            <span class="section-icon">💰</span>
            Análisis Financiero
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Configuración del análisis
    with st.expander("💼 Configuración Financiera", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            discount_rate = st.slider("Tasa de descuento (%)", 5, 20, 10) / 100
        
        with col2:
            analysis_years = st.slider("Años de análisis", 3, 10, 5)
        
        with col3:
            currency = st.selectbox("Moneda", ["USD", "DOP", "EUR"])
    
    try:
        stats = AdvancedStatistics(empresa_id)
        financial_analyzer = FinancialAnalyzer(stats)
        
        with st.spinner("Calculando análisis financiero..."):
            roi_data = financial_analyzer.calculate_roi_analysis()
        
        if roi_data.empty:
            st.info("No hay datos suficientes para análisis financiero")
            return
        
        # Dashboard financiero
        chart = create_financial_dashboard(roi_data)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        
        # Métricas financieras agregadas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_investment = roi_data['estimated_purchase_value'].sum()
            st.metric("Inversión Total", format_currency(total_investment))
        
        with col2:
            total_annual_revenue = roi_data['annual_revenue'].sum()
            st.metric("Ingresos Anuales", format_currency(total_annual_revenue))
        
        with col3:
            total_annual_profit = roi_data['annual_profit'].sum()
            st.metric("Ganancia Anual", format_currency(total_annual_profit))
        
        with col4:
            avg_roi = roi_data['roi_percentage'].mean()
            st.metric("ROI Promedio", format_percentage(avg_roi))
        
        # Análisis por máquina
        st.subheader("📈 Análisis por Máquina")
        
        # Ordenar por ROI
        roi_sorted = roi_data.sort_values('roi_percentage', ascending=False)
        
        # Mejores y peores performers
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🏆 Mejores ROI")
            top_roi = roi_sorted.head(5)
            
            for _, machine in top_roi.iterrows():
                roi_color = get_status_color(machine['profitability_status'])
                
                st.markdown(f"""
                <div class="recommendation-item">
                    <strong style="color: {roi_color};">{machine['machine_name']}</strong><br>
                    ROI: <strong>{machine['roi_percentage']:.1f}%</strong><br>
                    Ganancia anual: <strong>{format_currency(machine['annual_profit'])}</strong><br>
                    Payback: {machine['payback_months']} meses<br>
                    <small>{machine['profitability_status']}</small>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("#### ⚠️ ROI Bajo")
            bottom_roi = roi_sorted.tail(5)
            
            for _, machine in bottom_roi.iterrows():
                st.markdown(f"""
                <div class="recommendation-item" style="border-left: 4px solid #dc3545;">
                    <strong>{machine['machine_name']}</strong><br>
                    ROI: <strong>{machine['roi_percentage']:.1f}%</strong><br>
                    Ganancia anual: <strong>{format_currency(machine['annual_profit'])}</strong><br>
                    <small style="color: #dc3545;">Requiere revisión</small>
                </div>
                """, unsafe_allow_html=True)
        
        # Tabla detallada
        st.subheader("💼 Análisis Detallado por Máquina")
        
        display_cols = [
            'machine_name', 'classification', 'roi_percentage', 'profitability_status',
            'annual_revenue', 'annual_operating_cost', 'annual_profit', 'payback_months'
        ]
        
        financial_display = roi_sorted[display_cols].copy()
        
        # Formatear valores monetarios
        for col in ['annual_revenue', 'annual_operating_cost', 'annual_profit']:
            financial_display[col] = financial_display[col].apply(lambda x: f"${x:,.0f}")
        
        financial_display['roi_percentage'] = financial_display['roi_percentage'].apply(lambda x: f"{x:.1f}%")
        
        st.dataframe(financial_display, use_container_width=True)
        
        # Recomendaciones financieras
        mostrar_recomendaciones_financieras(roi_data)
        
    except Exception as e:
        st.error(f"Error en análisis financiero: {e}")

def mostrar_analisis_consumo(empresa_id):
    """Análisis inteligente de consumo"""
    
    st.markdown("""
    <div class="analysis-section">
        <div class="section-header">
            <span class="section-icon">⛽</span>
            Análisis Inteligente de Consumo
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Configuración del análisis
    with st.expander("⚙️ Configuración de Análisis", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            months_back = st.slider("Meses de historial", 3, 12, 6)
        
        with col2:
            include_seasonal = st.checkbox("Análisis estacional", value=True)
        
        with col3:
            alert_threshold = st.slider("Umbral de alerta (%)", 10, 50, 25)
    
    try:
        stats = AdvancedStatistics(empresa_id)
        consumption_analyzer = ConsumptionAnalyzer(stats)
        
        with st.spinner("Analizando patrones de consumo..."):
            consumption_analysis = consumption_analyzer.analyze_consumption_patterns(months_back)
        
        if not consumption_analysis:
            st.info("No hay datos suficientes para análisis de consumo")
            return
        
        # Dashboard de consumo
        chart = create_consumption_dashboard(consumption_analysis)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        
        # Mostrar patrones estacionales
        if include_seasonal and not consumption_analysis['seasonal_patterns'].empty:
            st.subheader("📅 Patrones Estacionales")
            
            seasonal_data = consumption_analysis['seasonal_patterns']
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico de consumo por mes
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=seasonal_data['month'],
                    y=seasonal_data['avg_consumption'],
                    mode='lines+markers',
                    name='Consumo Promedio',
                    line=dict(color='blue', width=3),
                    marker=dict(size=8)
                ))
                
                fig.update_layout(
                    title="Consumo Promedio por Mes",
                    xaxis_title="Mes",
                    yaxis_title="Consumo (gal)",
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Categorización de meses
                high_months = seasonal_data[seasonal_data['consumption_category'] == 'ALTO']['month'].tolist()
                low_months = seasonal_data[seasonal_data['consumption_category'] == 'BAJO']['month'].tolist()
                
                if high_months:
                    st.markdown("**Meses de Alto Consumo:**")
                    for month in high_months:
                        st.markdown(f"- Mes {month}")
                
                if low_months:
                    st.markdown("**Meses de Bajo Consumo:**")
                    for month in low_months:
                        st.markdown(f"- Mes {month}")
        
        # Tendencias por máquina
        if not consumption_analysis['consumption_trends'].empty:
            st.subheader("📈 Tendencias por Máquina")
            
            trends_data = consumption_analysis['consumption_trends']
            
            for _, trend in trends_data.iterrows():
                trend_color = get_status_color(trend['trend_direction'])
                
                st.markdown(f"""
                <div class="recommendation-item">
                    <strong style="color: {trend_color};">{trend['machine_name']}</strong><br>
                    Tendencia: <strong>{trend['trend_direction']}</strong> 
                    ({trend['change_percentage']:+.1f}%)<br>
                    Promedio reciente: {trend['recent_avg']:.2f} gal<br>
                    Promedio histórico: {trend['historical_avg']:.2f} gal<br>
                    Correlación: {trend['correlation']:.3f}
                </div>
                """, unsafe_allow_html=True)
        
        # Alertas de inventario
        inventory_alerts = consumption_analysis.get('inventory_alerts', [])
        if inventory_alerts:
            st.subheader("🚨 Alertas de Inventario")
            
            for alert in inventory_alerts:
                alert_class = f"alert-{alert['alert_level'].lower()}"
                
                st.markdown(f"""
                <div class="alert-card {alert_class}">
                    <strong>{alert['fluid_name']}</strong><br>
                    Nivel actual: <strong>{alert['current_level']:.1f}</strong> de {alert['capacity']:.0f} 
                    ({alert['percentage']:.1f}%)<br>
                    Días restantes estimados: <strong>{alert['predicted_days']} días</strong><br>
                    Recomendación: Ordenar {alert['recommended_order']:.1f} unidades
                </div>
                """, unsafe_allow_html=True)
        
        # Recomendaciones de optimización
        recommendations = consumption_analysis.get('optimization_recommendations', [])
        if recommendations:
            st.subheader("💡 Recomendaciones de Optimización")
            
            for rec in recommendations:
                priority_color = {
                    'ALTA': '#dc3545',
                    'MEDIA': '#ffc107', 
                    'BAJA': '#28a745'
                }.get(rec['priority'], '#6c757d')
                
                st.markdown(f"""
                <div class="recommendation-item">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong>{rec['machine']}</strong>
                        <span style="background: {priority_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem;">
                            {rec['priority']}
                        </span>
                    </div>
                    <br>
                    <strong>Tipo:</strong> {rec['type']}<br>
                    <strong>Descripción:</strong> {rec['description']}<br>
                    <strong>Recomendación:</strong> {rec['recommendation']}<br>
                    <strong>Ahorro potencial:</strong> {rec['potential_savings']}
                </div>
                """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"Error en análisis de consumo: {e}")

# Funciones auxiliares para la interfaz

def get_metric_color(value):
    """Obtiene clase CSS de color basada en valor numérico"""
    if value >= 80:
        return "metric-excellent"
    elif value >= 65:
        return "metric-good"
    elif value >= 50:
        return "metric-regular"
    else:
        return "metric-poor"

def calcular_salud_general(kpis):
    """Calcula score general de salud del sistema"""
    try:
        efficiency = kpis.get('avg_efficiency_score', 0)
        roi = min(100, max(0, kpis.get('avg_roi_percentage', 0) * 5))  # Normalizar ROI
        utilization = kpis.get('utilization_rate', 0)
        alerts = max(0, 100 - (kpis.get('critical_maintenance_alerts', 0) * 20))
        
        # Promedio ponderado
        score = (efficiency * 0.3 + roi * 0.3 + utilization * 0.2 + alerts * 0.2)
        
        if score >= 80:
            category = "EXCELENTE"
            description = "El sistema opera en condiciones óptimas"
        elif score >= 65:
            category = "BUENO"
            description = "El sistema opera correctamente con oportunidades de mejora"
        elif score >= 50:
            category = "REGULAR"
            description = "El sistema requiere atención en algunas áreas"
        else:
            category = "DEFICIENTE"
            description = "El sistema requiere intervención inmediata"
        
        return {
            'score': score,
            'category': category,
            'description': description
        }
    except:
        return {'score': 0, 'category': 'ERROR', 'description': 'Error calculando salud'}

def mostrar_alertas_generales(empresa_id, stats):
    """Muestra alertas generales del sistema"""
    st.subheader("🚨 Alertas del Sistema")
    
    try:
        # Alertas de mantenimiento
        predictive_analyzer = PredictiveAnalyzer(stats)
        maintenance_predictions = predictive_analyzer.predict_maintenance_needs(days_ahead=14)
        
        critical_maintenance = maintenance_predictions[
            maintenance_predictions['urgency_level'] == 'CRÍTICO'
        ] if not maintenance_predictions.empty else pd.DataFrame()
        
        # Alertas de eficiencia
        efficiency_analyzer = EfficiencyAnalyzer(stats)
        efficiency_data = efficiency_analyzer.analyze_operational_efficiency()
        
        low_efficiency = efficiency_data[
            efficiency_data['efficiency_score'] < 40
        ] if not efficiency_data.empty else pd.DataFrame()
        
        # Mostrar alertas
        if not critical_maintenance.empty:
            st.error(f"⚠️ {len(critical_maintenance)} máquinas requieren mantenimiento crítico")
        
        if not low_efficiency.empty:
            st.warning(f"📉 {len(low_efficiency)} máquinas tienen eficiencia muy baja (<40%)")
        
        if critical_maintenance.empty and low_efficiency.empty:
            st.success("✅ No hay alertas críticas del sistema")
    
    except Exception as e:
        st.error(f"Error obteniendo alertas: {e}")

def mostrar_trends_temporales(empresa_id, stats):
    """Muestra tendencias temporales del sistema"""
    st.subheader("📊 Tendencias Temporales")
    
    try:
        fuel_logs = stats._get_base_data().get('fuel_logs', pd.DataFrame())
        
        if fuel_logs.empty:
            st.info("No hay datos suficientes para mostrar tendencias")
            return
        
        # Preparar datos temporales
        fuel_logs['added_at'] = pd.to_datetime(fuel_logs['added_at'])
        fuel_logs['date'] = fuel_logs['added_at'].dt.date
        
        # Consumo diario agregado
        daily_consumption = fuel_logs.groupby('date')['fuel_added'].sum().reset_index()
        daily_consumption = daily_consumption.sort_values('date')
        
        # Crear gráfico de tendencia
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=daily_consumption['date'],
            y=daily_consumption['fuel_added'],
            mode='lines+markers',
            name='Consumo Diario',
            line=dict(color='#667eea', width=2),
            marker=dict(size=4)
        ))
        
        # Línea de tendencia
        if len(daily_consumption) > 1:
            x_numeric = np.arange(len(daily_consumption))
            slope, intercept = np.polyfit(x_numeric, daily_consumption['fuel_added'], 1)
            trend_line = slope * x_numeric + intercept
            
            fig.add_trace(go.Scatter(
                x=daily_consumption['date'],
                y=trend_line,
                mode='lines',
                name='Tendencia',
                line=dict(color='red', dash='dash', width=2)
            ))
        
        fig.update_layout(
            title="Tendencia de Consumo de Combustible",
            xaxis_title="Fecha",
            yaxis_title="Consumo (galones)",
            height=400,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Estadísticas de tendencia
        if len(daily_consumption) > 7:
            recent_avg = daily_consumption['fuel_added'].tail(7).mean()
            historical_avg = daily_consumption['fuel_added'].mean()
            change_pct = ((recent_avg - historical_avg) / historical_avg) * 100
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Promedio Últimos 7 días", f"{recent_avg:.1f} gal")
            
            with col2:
                st.metric("Promedio Histórico", f"{historical_avg:.1f} gal")
            
            with col3:
                st.metric("Cambio", f"{change_pct:+.1f}%")
    
    except Exception as e:
        st.error(f"Error mostrando tendencias: {e}")

def mostrar_recomendaciones_eficiencia(efficiency_data):
    """Muestra recomendaciones específicas de eficiencia"""
    st.subheader("💡 Recomendaciones de Eficiencia")
    
    try:
        recommendations = []
        
        for _, machine in efficiency_data.iterrows():
            machine_recs = []
            
            # Baja utilización
            if machine['utilization_rate'] < 60:
                machine_recs.append({
                    'type': 'UTILIZACIÓN',
                    'priority': 'ALTA',
                    'description': f"Utilización muy baja ({machine['utilization_rate']:.1f}%)",
                    'action': "Revisar programación de trabajo y asignación de tareas"
                })
            
            # Baja consistencia de operador
            if machine['operator_consistency'] < 70:
                machine_recs.append({
                    'type': 'OPERADOR',
                    'priority': 'MEDIA',
                    'description': f"Baja consistencia de operador ({machine['operator_consistency']:.1f}%)",
                    'action': "Asignar operador principal o mejorar capacitación"
                })
            
            # Baja eficiencia de combustible
            if machine['fuel_efficiency'] < 0.001:
                machine_recs.append({
                    'type': 'COMBUSTIBLE',
                    'priority': 'MEDIA',
                    'description': "Eficiencia de combustible subóptima",
                    'action': "Revisar calibración y patrones de uso"
                })
            
            if machine_recs:
                recommendations.append({
                    'machine': machine['machine_name'],
                    'recommendations': machine_recs
                })
        
        if recommendations:
            for machine_rec in recommendations:
                st.markdown(f"**{machine_rec['machine']}:**")
                
                for rec in machine_rec['recommendations']:
                    priority_color = {
                        'ALTA': '#dc3545',
                        'MEDIA': '#ffc107',
                        'BAJA': '#28a745'
                    }.get(rec['priority'], '#6c757d')
                    
                    st.markdown(f"""
                    <div class="recommendation-item">
                        <div style="display: flex; justify-content: space-between;">
                            <strong>{rec['type']}</strong>
                            <span style="background: {priority_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem;">
                                {rec['priority']}
                            </span>
                        </div>
                        <br>
                        <strong>Problema:</strong> {rec['description']}<br>
                        <strong>Acción recomendada:</strong> {rec['action']}
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.success("No hay recomendaciones específicas. El sistema opera eficientemente.")
    
    except Exception as e:
        st.error(f"Error generando recomendaciones: {e}")

def mostrar_recomendaciones_financieras(roi_data):
    """Muestra recomendaciones financieras"""
    st.subheader("💰 Recomendaciones Financieras")
    
    try:
        recommendations = []
        
        # Máquinas con ROI negativo
        negative_roi = roi_data[roi_data['roi_percentage'] < 0]
        if not negative_roi.empty:
            recommendations.append({
                'type': 'PERDIDA',
                'priority': 'CRÍTICA',
                'count': len(negative_roi),
                'description': f"{len(negative_roi)} máquinas generan pérdidas",
                'action': "Evaluar venta, reubicación o cambio de uso"
            })
        
        # Máquinas con ROI muy bajo
        low_roi = roi_data[(roi_data['roi_percentage'] >= 0) & (roi_data['roi_percentage'] < 5)]
        if not low_roi.empty:
            recommendations.append({
                'type': 'ROI_BAJO',
                'priority': 'ALTA',
                'count': len(low_roi),
                'description': f"{len(low_roi)} máquinas con ROI bajo (<5%)",
                'action': "Optimizar costos operacionales o aumentar utilización"
            })
        
        # Oportunidades de mejora
        avg_roi = roi_data['roi_percentage'].mean()
        if avg_roi < 10:
            recommendations.append({
                'type': 'SISTEMA',
                'priority': 'MEDIA',
                'count': len(roi_data),
                'description': f"ROI promedio del sistema bajo ({avg_roi:.1f}%)",
                'action': "Revisar estrategia de pricing y optimizar costos generales"
            })
        
        # Mostrar recomendaciones
        if recommendations:
            for rec in recommendations:
                priority_color = {
                    'CRÍTICA': '#dc3545',
                    'ALTA': '#fd7e14',
                    'MEDIA': '#ffc107',
                    'BAJA': '#28a745'
                }.get(rec['priority'], '#6c757d')
                
                st.markdown(f"""
                <div class="recommendation-item">
                    <div style="display: flex; justify-content: space-between;">
                        <strong>{rec['type']}</strong>
                        <span style="background: {priority_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem;">
                            {rec['priority']}
                        </span>
                    </div>
                    <br>
                    <strong>Situación:</strong> {rec['description']}<br>
                    <strong>Recomendación:</strong> {rec['action']}<br>
                    <strong>Máquinas afectadas:</strong> {rec['count']}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("El portafolio de máquinas muestra un desempeño financiero saludable.")
            
        # Mejores oportunidades de inversión
        best_performers = roi_data[roi_data['roi_percentage'] >= 15].head(3)
        if not best_performers.empty:
            st.markdown("#### 🎯 Modelos de Alta Rentabilidad")
            st.info("Considere adquirir más máquinas de estos tipos para maximizar ROI:")
            
            for _, machine in best_performers.iterrows():
                st.markdown(f"- **{machine['classification']}**: ROI {machine['roi_percentage']:.1f}%")
    
    except Exception as e:
        st.error(f"Error generando recomendaciones financieras: {e}")

# Funciones de exportación y reportes

def export_analysis_report(empresa_id, empresa_nombre, analysis_type="complete"):
    """Exporta reporte de análisis en diferentes formatos"""
    try:
        stats = AdvancedStatistics(empresa_id)
        
        report_data = {
            'metadata': {
                'company_name': empresa_nombre,
                'company_id': empresa_id,
                'generated_at': datetime.now().isoformat(),
                'analysis_type': analysis_type
            }
        }
        
        if analysis_type in ["complete", "efficiency"]:
            efficiency_analyzer = EfficiencyAnalyzer(stats)
            report_data['efficiency'] = efficiency_analyzer.analyze_operational_efficiency().to_dict('records')
        
        if analysis_type in ["complete", "financial"]:
            financial_analyzer = FinancialAnalyzer(stats)
            report_data['financial'] = financial_analyzer.calculate_roi_analysis().to_dict('records')
        
        if analysis_type in ["complete", "predictive"]:
            predictive_analyzer = PredictiveAnalyzer(stats)
            report_data['maintenance_predictions'] = predictive_analyzer.predict_maintenance_needs().to_dict('records')
            report_data['fuel_predictions'] = predictive_analyzer.predict_fuel_consumption().to_dict('records')
        
        if analysis_type in ["complete", "consumption"]:
            consumption_analyzer = ConsumptionAnalyzer(stats)
            consumption_analysis = consumption_analyzer.analyze_consumption_patterns()
            report_data['consumption'] = {
                'seasonal_patterns': consumption_analysis.get('seasonal_patterns', pd.DataFrame()).to_dict('records'),
                'trends': consumption_analysis.get('consumption_trends', pd.DataFrame()).to_dict('records'),
                'recommendations': consumption_analysis.get('optimization_recommendations', []),
                'inventory_alerts': consumption_analysis.get('inventory_alerts', [])
            }
        
        return report_data
    
    except Exception as e:
        st.error(f"Error exportando reporte: {e}")
        return None

# Función principal de configuración
def configurar_pagina_estadisticas():
    """Configuración inicial de la página de estadísticas"""
    st.set_page_config(
        page_title="SANDI - Estadísticas",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # CSS global adicional para estadísticas
    st.markdown("""
    <style>
    .main > div {
        padding-top: 1rem;
    }
    
    .stSelectbox > div > div {
        background-color: white;
        border-radius: 8px;
    }
    
    .stSlider > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    .stCheckbox > label {
        font-weight: 500;
    }
    
    .stMetric {
        background: rgba(255, 255, 255, 0.8);
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    </style>
    """, unsafe_allow_html=True)

def mostrar_resumen_ejecutivo(empresa_id):
    """Versión mejorada del resumen ejecutivo con explicaciones"""
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%); 
                padding: 25px; border-radius: 15px; color: white; margin: 20px 0;">
        <h2 style="margin: 0 0 10px 0;">📊 Resumen General</h2>
        <p style="margin: 0; opacity: 0.9;">Vista general del estado operacional</p>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        # Obtener datos base
        stats = AdvancedStatistics(empresa_id)
        data = stats._get_base_data()
        machinery = data['machinery']
        tanks = data.get('tanks', pd.DataFrame())
        
        if machinery.empty:
            st.warning("No hay datos suficientes para el resumen ejecutivo")
            return
        
        # Calcular métricas operacionales
        operational_metrics = calculate_operational_metrics(empresa_id, machinery, tanks)
        
        # Mostrar métricas en tarjetas
        mostrar_tarjetas_ejecutivas(operational_metrics)
        
        # AGREGAR explicación de salud del sistema
        mostrar_explicacion_salud_sistema()
        
        # Mostrar alertas críticas
        mostrar_alertas_ejecutivas(empresa_id, operational_metrics)
        
        # Mostrar tendencias con filtro de fechas
        mostrar_tendencias_ejecutivas(empresa_id, machinery)
        
    except Exception as e:
        st.error(f"Error generando resumen ejecutivo: {e}")

def calculate_operational_metrics(empresa_id, machinery, tanks):
    """Calcula métricas operacionales clave"""
    
    metrics = {}
    
    # === MÉTRICAS DE MAQUINARIA ===
    total_machines = len(machinery)
    metrics['total_machines'] = total_machines
    
    # Estados de máquinas
    active_machines = len(machinery[machinery['status'] == 'Active'])
    maintenance_machines = len(machinery[machinery['status'] == 'Maintenance'])
    inactive_machines = len(machinery[machinery['status'] == 'Inactive'])
    
    metrics['active_machines'] = active_machines
    metrics['maintenance_machines'] = maintenance_machines
    metrics['inactive_machines'] = inactive_machines
    metrics['operational_rate'] = (active_machines / total_machines * 100) if total_machines > 0 else 0
    
    # === ALERTAS DE MANTENIMIENTO ===
    try:
        # Obtener alertas de mantenimiento desde el módulo avanzado
        from statistics_module import PredictiveAnalyzer
        predictive_analyzer = PredictiveAnalyzer(AdvancedStatistics(empresa_id))
        maintenance_predictions = predictive_analyzer.predict_maintenance_needs(days_ahead=14)
        
        critical_maintenance = len(maintenance_predictions[
            maintenance_predictions['urgency_level'] == 'CRÍTICO'
        ]) if not maintenance_predictions.empty else 0
        
        warning_maintenance = len(maintenance_predictions[
            maintenance_predictions['urgency_level'] == 'ALTO'
        ]) if not maintenance_predictions.empty else 0
        
        metrics['critical_maintenance_alerts'] = critical_maintenance
        metrics['warning_maintenance_alerts'] = warning_maintenance
        metrics['total_maintenance_alerts'] = critical_maintenance + warning_maintenance
        
    except Exception:
        # Fallback a método básico
        metrics['critical_maintenance_alerts'] = 0
        metrics['warning_maintenance_alerts'] = 0
        metrics['total_maintenance_alerts'] = 0
    
    # === ALERTAS DE COMBUSTIBLE ===
    try:
        critical_fuel_machines = get_critical_fuel_machines(empresa_id)
        
        critical_fuel = len([m for m in critical_fuel_machines if m['status'] == 'critical'])
        warning_fuel = len([m for m in critical_fuel_machines if m['status'] == 'warning'])
        
        metrics['critical_fuel_alerts'] = critical_fuel
        metrics['warning_fuel_alerts'] = warning_fuel
        metrics['total_fuel_alerts'] = critical_fuel + warning_fuel
        
    except Exception:
        metrics['critical_fuel_alerts'] = 0
        metrics['warning_fuel_alerts'] = 0
        metrics['total_fuel_alerts'] = 0
    
    # === MÉTRICAS DE TANQUES ===
    metrics['total_tanks'] = len(tanks)
    
    if not tanks.empty:
        # Calcular niveles de tanques
        tank_levels = []
        critical_tanks = 0
        warning_tanks = 0
        
        for _, tank in tanks.iterrows():
            level_percentage = (tank['current_level'] / tank['tank_capacity']) * 100
            tank_levels.append(level_percentage)
            
            if level_percentage <= 10:
                critical_tanks += 1
            elif level_percentage <= 25:
                warning_tanks += 1
        
        metrics['avg_tank_level'] = np.mean(tank_levels) if tank_levels else 0
        metrics['critical_tank_alerts'] = critical_tanks
        metrics['warning_tank_alerts'] = warning_tanks
        metrics['total_tank_alerts'] = critical_tanks + warning_tanks
    else:
        metrics['avg_tank_level'] = 0
        metrics['critical_tank_alerts'] = 0
        metrics['warning_tank_alerts'] = 0
        metrics['total_tank_alerts'] = 0
    
    # === MÉTRICAS DE PRODUCTIVIDAD ===
    try:
        # Calcular horas trabajadas últimos 30 días
        total_work_hours = 0
        machines_with_data = 0
        
        for _, machine in machinery.iterrows():
            try:
                work_logs = get_machine_work_logs(machine['id'], days=30)
                if not work_logs.empty:
                    total_work_hours += work_logs['hours_worked'].sum()
                    machines_with_data += 1
            except:
                continue
        
        metrics['total_work_hours_30d'] = total_work_hours
        metrics['avg_hours_per_machine'] = (total_work_hours / machines_with_data) if machines_with_data > 0 else 0
        metrics['machines_with_activity'] = machines_with_data
        
    except Exception:
        metrics['total_work_hours_30d'] = 0
        metrics['avg_hours_per_machine'] = 0
        metrics['machines_with_activity'] = 0
    
    # === SCORE GENERAL DE SALUD ===
    health_factors = [
        metrics['operational_rate'],
        max(0, 100 - (metrics['total_maintenance_alerts'] * 10)),
        max(0, 100 - (metrics['total_fuel_alerts'] * 15)),
        max(0, 100 - (metrics['total_tank_alerts'] * 20)),
        min(100, metrics['avg_tank_level'])
    ]
    
    metrics['health_score'] = np.mean([f for f in health_factors if f >= 0])
    
    return metrics

def mostrar_tarjetas_ejecutivas(metrics):
    """Muestra métricas en tarjetas ejecutivas"""
    
    # Primera fila - Métricas de máquinas
    st.markdown("#### 🚜 Estado de Maquinaria")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value metric-excellent">{metrics['total_machines']}</div>
            <div class="kpi-label">Total Máquinas</div>
            <div style="font-size: 0.8rem; margin-top: 5px;">
                Flota completa
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        operational_color = get_metric_color(metrics['operational_rate'])
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value {operational_color}">{metrics['active_machines']}</div>
            <div class="kpi-label">Máquinas Activas</div>
            <div style="font-size: 0.8rem; margin-top: 5px;">
                {metrics['operational_rate']:.1f}% operacional
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        maint_color = "metric-poor" if metrics['maintenance_machines'] > metrics['total_machines'] * 0.3 else "metric-regular"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value {maint_color}">{metrics['maintenance_machines']}</div>
            <div class="kpi-label">En Mantenimiento</div>
            <div style="font-size: 0.8rem; margin-top: 5px;">
                Programado/correctivo
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        inactive_color = "metric-poor" if metrics['inactive_machines'] > 0 else "metric-excellent"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value {inactive_color}">{metrics['inactive_machines']}</div>
            <div class="kpi-label">Inactivas</div>
            <div style="font-size: 0.8rem; margin-top: 5px;">
                Fuera de servicio
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Segunda fila - Alertas críticas
    st.markdown("#### ⚠️ Alertas del Sistema")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        alert_color = "metric-poor" if metrics['total_maintenance_alerts'] > 0 else "metric-excellent"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value {alert_color}">{metrics['total_maintenance_alerts']}</div>
            <div class="kpi-label">Alertas Mantenimiento</div>
            <div style="font-size: 0.8rem; margin-top: 5px;">
                {metrics['critical_maintenance_alerts']} críticas
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        fuel_alert_color = "metric-poor" if metrics['total_fuel_alerts'] > 0 else "metric-excellent"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value {fuel_alert_color}">{metrics['total_fuel_alerts']}</div>
            <div class="kpi-label">Alertas Combustible</div>
            <div style="font-size: 0.8rem; margin-top: 5px;">
                {metrics['critical_fuel_alerts']} críticas
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        tank_color = get_metric_color(metrics['avg_tank_level'])
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value {tank_color}">{metrics['total_tanks']}</div>
            <div class="kpi-label">Tanques de Fluidos</div>
            <div style="font-size: 0.8rem; margin-top: 5px;">
                {metrics['avg_tank_level']:.1f}% promedio
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        health_color = get_metric_color(metrics['health_score'])
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value {health_color}">{metrics['health_score']:.0f}</div>
            <div class="kpi-label">Salud del Sistema</div>
            <div style="font-size: 0.8rem; margin-top: 5px;">
                Score general
            </div>
        </div>
        """, unsafe_allow_html=True)

def mostrar_alertas_ejecutivas(empresa_id, metrics):
    """Muestra alertas críticas para atención ejecutiva"""
    
    # Solo mostrar si hay alertas críticas
    total_critical = (metrics['critical_maintenance_alerts'] + 
                     metrics['critical_fuel_alerts'] + 
                     metrics['critical_tank_alerts'])
    
    if total_critical > 0:
        st.markdown("#### 🚨 Atención Requerida")
        
        alert_messages = []
        
        if metrics['critical_maintenance_alerts'] > 0:
            alert_messages.append(f"🔧 {metrics['critical_maintenance_alerts']} máquinas requieren mantenimiento URGENTE")
        
        if metrics['critical_fuel_alerts'] > 0:
            alert_messages.append(f"⛽ {metrics['critical_fuel_alerts']} máquinas con combustible CRÍTICO")
        
        if metrics['critical_tank_alerts'] > 0:
            alert_messages.append(f"🛢️ {metrics['critical_tank_alerts']} tanques en nivel CRÍTICO (<10%)")
        
        for message in alert_messages:
            st.markdown(f"""
            <div class="alert-card alert-critical">
                <strong>{message}</strong>
            </div>
            """, unsafe_allow_html=True)

def mostrar_tendencias_ejecutivas(empresa_id, machinery):
    """Muestra tendencias con filtro de fechas configurable"""
    
    st.markdown("#### 📈 Tendencias del Sistema")
    
    # Filtro de fechas
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        fecha_inicio = st.date_input(
            "Desde",
            value=datetime.now() - timedelta(days=30),
            max_value=datetime.now().date()
        )
    
    with col2:
        fecha_fin = st.date_input(
            "Hasta",
            value=datetime.now().date(),
            max_value=datetime.now().date()
        )
    
    with col3:
        quick_filters = st.selectbox(
            "Filtros rápidos",
            ["Personalizado", "Últimos 7 días", "Últimos 30 días", "Últimos 90 días"]
        )
        
        # Aplicar filtro rápido
        if quick_filters == "Últimos 7 días":
            fecha_inicio = datetime.now().date() - timedelta(days=7)
            fecha_fin = datetime.now().date()
        elif quick_filters == "Últimos 30 días":
            fecha_inicio = datetime.now().date() - timedelta(days=30)
            fecha_fin = datetime.now().date()
        elif quick_filters == "Últimos 90 días":
            fecha_inicio = datetime.now().date() - timedelta(days=90)
            fecha_fin = datetime.now().date()
    
    # Validar rango de fechas
    if fecha_inicio > fecha_fin:
        st.error("La fecha de inicio debe ser anterior a la fecha final")
        return
    
    days_diff = (fecha_fin - fecha_inicio).days
    if days_diff < 1:
        st.warning("Seleccione un rango de al menos 1 día")
        return
    
    try:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Tendencia de actividad
            activity_trend = calculate_activity_trend_filtered(machinery, fecha_inicio, fecha_fin)
            trend_icon = "📈" if activity_trend > 0 else "📉" if activity_trend < 0 else "➡️"
            trend_color = "green" if activity_trend > 0 else "red" if activity_trend < 0 else "gray"
            
            st.markdown(f"""
            <div style="text-align: center; padding: 15px; background: white; border-radius: 8px; border-left: 4px solid {trend_color};">
                <div style="font-size: 2rem;">{trend_icon}</div>
                <div style="color: #2c3e50;"><strong>Actividad</strong></div>
                <div style="color: #34495e;">{activity_trend:+.1f}% en período</div>
                <small style="color: #7f8c8d;">{days_diff} días</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # Tendencia de combustible
            fuel_trend = calculate_fuel_trend_filtered(empresa_id, fecha_inicio, fecha_fin)
            fuel_icon = "📈" if fuel_trend > 0 else "📉" if fuel_trend < 0 else "➡️"
            fuel_color = "red" if fuel_trend > 10 else "green" if fuel_trend < -10 else "gray"
            
            st.markdown(f"""
            <div style="text-align: center; padding: 15px; background: white; border-radius: 8px; border-left: 4px solid {fuel_color};">
                <div style="font-size: 2rem;">{fuel_icon}</div>
                <div style="color: #2c3e50;"><strong>Consumo</strong></div>
                <div style="color: #34495e;">{fuel_trend:+.1f}% en período</div>
                <small style="color: #7f8c8d;">{days_diff} días</small>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            # Eventos de mantenimiento
            maint_count = calculate_maintenance_count_filtered(empresa_id, fecha_inicio, fecha_fin)
            maint_icon = "🔧" if maint_count > 0 else "✅"
            maint_color = "orange" if maint_count > 5 else "green"
            
            st.markdown(f"""
            <div style="text-align: center; padding: 15px; background: white; border-radius: 8px; border-left: 4px solid {maint_color};">
                <div style="font-size: 2rem;">{maint_icon}</div>
                <div style="color: #2c3e50;"><strong>Mantenimiento</strong></div>
                <div style="color: #34495e;">{maint_count} eventos</div>
                <small style="color: #7f8c8d;">En período</small>
            </div>
            """, unsafe_allow_html=True)
        
        # Mostrar detalles adicionales si el período es largo
        if days_diff > 30:
            st.info(f"Período de análisis: {days_diff} días. Para mejor precisión en tendencias, considere períodos más cortos.")
    
    except Exception as e:
        st.error(f"Error calculando tendencias: {e}")

# Funciones auxiliares para cálculos de tendencias
def calculate_activity_trend(machinery):
    """Calcula tendencia de actividad (simplificado)"""
    try:
        # Simplificado: basado en máquinas activas vs total
        active_rate = len(machinery[machinery['status'] == 'Active']) / len(machinery) * 100
        # Simular comparación con mes anterior (en implementación real, usar datos históricos)
        return active_rate - 85  # 85% como baseline
    except:
        return 0

def calculate_fuel_trend(empresa_id):
    """Calcula tendencia de consumo de combustible"""
    try:
        # Obtener datos de combustible recientes
        with get_conn() as conn:
            recent_fuel = pd.read_sql_query("""
                SELECT DATE(added_at) as date, SUM(fuel_added) as daily_fuel
                FROM fuel_logs 
                WHERE machinery_id IN (SELECT id FROM machinery WHERE company_id = ?)
                AND DATE(added_at) >= DATE('now', '-60 days')
                GROUP BY DATE(added_at)
                ORDER BY date
            """, conn, params=(empresa_id,))
        
        if len(recent_fuel) < 30:
            return 0
        
        # Comparar últimos 30 días vs 30 días anteriores
        last_30 = recent_fuel.tail(30)['daily_fuel'].mean()
        prev_30 = recent_fuel.head(30)['daily_fuel'].mean()
        
        if prev_30 > 0:
            return ((last_30 - prev_30) / prev_30) * 100
        return 0
    except:
        return 0

def calculate_maintenance_trend(empresa_id):
    """Calcula eventos de mantenimiento del mes actual"""
    try:
        with get_conn() as conn:
            maintenance_count = pd.read_sql_query("""
                SELECT COUNT(*) as count
                FROM maintenance_records 
                WHERE machinery_id IN (SELECT id FROM machinery WHERE company_id = ?)
                AND DATE(performed_at) >= DATE('now', 'start of month')
            """, conn, params=(empresa_id,))
        
        return maintenance_count.iloc[0]['count'] if not maintenance_count.empty else 0
    except:
        return 0

def get_machine_work_logs(machine_id, days=30):
    """Obtiene logs de trabajo de una máquina (función auxiliar)"""
    try:
        with get_conn() as conn:
            return pd.read_sql_query("""
                SELECT * FROM daily_work_logs 
                WHERE machinery_id = ? 
                AND DATE(work_date) >= DATE('now', '-{} days')
            """.format(days), conn, params=(machine_id,))
    except:
        return pd.DataFrame()

# =============================================================================
# MODIFICACIÓN EN statistics_ui.py
# =============================================================================

# En la función mostrar_dashboard_general(), AGREGAR al inicio (después del header):

def mostrar_dashboard_general_MODIFICADO(empresa_id):
    """Dashboard general con resumen ejecutivo integrado"""
    
    st.markdown("""
    <div class="analysis-section">
        <div class="section-header">
            <span class="section-icon">📊</span>
            Dashboard General
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # === AGREGAR ESTA LÍNEA ===
    mostrar_resumen_ejecutivo(empresa_id)
    # === FIN LÍNEA AGREGADA ===
    
    try:
        # Resto del código existente sin cambios...
        stats = AdvancedStatistics(empresa_id)
        
        if stats._get_base_data()['machinery'].empty:
            st.info("No hay máquinas registradas para mostrar estadísticas")
            return
        
        # ... resto del código existente de mostrar_dashboard_general
        
    except Exception as e:
        st.error(f"Error en dashboard general: {e}")

def calculate_activity_trend_filtered(machinery, fecha_inicio, fecha_fin):
    """Calcula tendencia de actividad en período específico"""
    try:
        # Para esta versión simplificada, calculamos basado en estado actual
        # En implementación completa, usaríamos logs históricos de cambios de estado
        active_rate = len(machinery[machinery['status'] == 'Active']) / len(machinery) * 100
        
        # Simular variación basada en duración del período
        days_diff = (fecha_fin - fecha_inicio).days
        variation = (active_rate - 85) * (days_diff / 30)  # 85% como baseline
        
        return min(max(variation, -50), 50)  # Limitar entre -50% y +50%
    except:
        return 0

def calculate_fuel_trend_filtered(empresa_id, fecha_inicio, fecha_fin):
    """Calcula tendencia de consumo de combustible en período específico"""
    try:
        with get_conn() as conn:
            fuel_data = pd.read_sql_query("""
                SELECT DATE(added_at) as date, SUM(fuel_added) as daily_fuel
                FROM fuel_logs 
                WHERE machinery_id IN (SELECT id FROM machinery WHERE company_id = ?)
                AND DATE(added_at) BETWEEN ? AND ?
                GROUP BY DATE(added_at)
                ORDER BY date
            """, conn, params=(empresa_id, fecha_inicio.isoformat(), fecha_fin.isoformat()))
        
        if len(fuel_data) < 2:
            return 0
        
        # Dividir período en dos mitades para comparar
        mid_point = len(fuel_data) // 2
        first_half = fuel_data.head(mid_point)['daily_fuel'].mean()
        second_half = fuel_data.tail(len(fuel_data) - mid_point)['daily_fuel'].mean()
        
        if first_half > 0:
            return ((second_half - first_half) / first_half) * 100
        return 0
    except:
        return 0

def calculate_maintenance_count_filtered(empresa_id, fecha_inicio, fecha_fin):
    """Calcula eventos de mantenimiento en período específico"""
    try:
        with get_conn() as conn:
            maintenance_count = pd.read_sql_query("""
                SELECT COUNT(*) as count
                FROM maintenance_records 
                WHERE machinery_id IN (SELECT id FROM machinery WHERE company_id = ?)
                AND DATE(performed_at) BETWEEN ? AND ?
            """, conn, params=(empresa_id, fecha_inicio.isoformat(), fecha_fin.isoformat()))
        
        return maintenance_count.iloc[0]['count'] if not maintenance_count.empty else 0
    except:
        return 0

# =============================================================================
# EXPLICACIÓN DETALLADA: CÁLCULO DE SALUD GENERAL DEL SISTEMA
# =============================================================================

def mostrar_explicacion_salud_sistema():
    """Función para explicar cómo se calcula el score de salud del sistema"""
    
    with st.expander("🔍 ¿Cómo se calcula la Salud General del Sistema?"):
        st.markdown("""
        ### Componentes del Score de Salud (0-100)
        
        El score de salud es un **promedio ponderado** de 5 factores clave:
        
        #### 1. **Tasa Operacional** (Peso: 20%)
        ```
        Operational_Rate = (Máquinas_Activas / Total_Máquinas) × 100
        ```
        - **100%**: Todas las máquinas activas
        - **80%**: 80% de máquinas activas
        - **0%**: Ninguna máquina activa
        
        #### 2. **Alertas de Mantenimiento** (Peso: 20%)
        ```
        Maintenance_Factor = max(0, 100 - (Total_Alertas_Mantenimiento × 10))
        ```
        - **Cada alerta** reduce 10 puntos
        - **0 alertas**: 100 puntos
        - **5 alertas**: 50 puntos
        - **10+ alertas**: 0 puntos
        
        #### 3. **Alertas de Combustible** (Peso: 20%)
        ```
        Fuel_Factor = max(0, 100 - (Total_Alertas_Combustible × 15))
        ```
        - **Cada alerta** reduce 15 puntos (más crítico que mantenimiento)
        - **0 alertas**: 100 puntos
        - **3 alertas**: 55 puntos
        - **7+ alertas**: 0 puntos
        
        #### 4. **Alertas de Tanques** (Peso: 20%)
        ```
        Tank_Factor = max(0, 100 - (Total_Alertas_Tanques × 20))
        ```
        - **Cada alerta** reduce 20 puntos (muy crítico)
        - **0 alertas**: 100 puntos
        - **2 alertas**: 60 puntos
        - **5+ alertas**: 0 puntos
        
        #### 5. **Nivel Promedio de Tanques** (Peso: 20%)
        ```
        Tank_Level = Promedio_Nivel_Todos_Los_Tanques
        ```
        - **90%+**: Nivel excelente
        - **50%**: Nivel regular
        - **10%**: Nivel crítico
        
        ### Fórmula Final:
        ```
        Health_Score = (
            Operational_Rate × 0.20 +
            Maintenance_Factor × 0.20 +
            Fuel_Factor × 0.20 +
            Tank_Factor × 0.20 +
            Tank_Level × 0.20
        )
        ```
        
        ### Interpretación del Score:
        - **90-100**: 🟢 Sistema en estado **EXCELENTE**
        - **75-89**: 🔵 Sistema en estado **BUENO**
        - **60-74**: 🟡 Sistema **REGULAR** - requiere atención
        - **40-59**: 🟠 Sistema **DEFICIENTE** - acción necesaria
        - **0-39**: 🔴 Sistema **CRÍTICO** - intervención urgente
        
        ### Limitaciones del Cálculo:
        - Los pesos (20% cada factor) son **arbitrarios**
        - No considera **calidad** del trabajo realizado
        - No incluye **factores externos** (clima, mercado, etc.)
        - **Penalizaciones lineales** pueden ser demasiado severas
        - No considera **antigüedad** de las alertas
        
        ### Para Mejorar la Precisión:
        - Ajustar pesos según **importancia real** para tu operación
        - Incluir **histórico de performance**
        - Considerar **impacto financiero** de cada factor
        - Agregar **tendencias temporales**
        """)