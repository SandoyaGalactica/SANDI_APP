"""
Módulo de Estadísticas Avanzadas para SANDI
Sistema de análisis predictivo, financiero y operacional

Autor: Sistema SANDI
Versión: 2.0
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime, timedelta, date
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

# Importar funciones de base de datos
from db_utils import (
    get_conn, list_machinery, get_fuel_logs, get_maintenance_records,
    get_company_tanks, get_recent_fluid_movements_summary,
    get_machinery_efficiency_analysis, get_cost_analysis_report,
    get_predictive_maintenance_analysis
)

class AdvancedStatistics:
    """Clase principal para análisis estadísticos avanzados"""
    
    def __init__(self, empresa_id):
        self.empresa_id = empresa_id
        self.data_cache = {}
        self.last_update = None
    
    def _get_base_data(self, force_refresh=False):
        """Obtiene y cachea datos base del sistema"""
        if force_refresh or not self.data_cache or self._cache_expired():
            print("🔄 Cargando datos base...")
            
            self.data_cache = {
                'machinery': list_machinery(self.empresa_id),
                'tanks': get_company_tanks(self.empresa_id),
                'timestamp': datetime.now()
            }
            
            # Cargar datos adicionales si las máquinas existen
            if not self.data_cache['machinery'].empty:
                self.data_cache.update({
                    'fuel_logs': self._get_all_fuel_logs(),
                    'maintenance_records': self._get_all_maintenance_records(),
                    'work_logs': self._get_all_work_logs()
                })
            
            self.last_update = datetime.now()
        
        return self.data_cache
    
    def _cache_expired(self, max_age_minutes=5):
        """Verifica si el cache ha expirado"""
        if not self.last_update:
            return True
        return (datetime.now() - self.last_update).seconds > (max_age_minutes * 60)
    
    def _get_all_fuel_logs(self):
        """Obtiene logs de combustible de todas las máquinas"""
        fuel_data = []
        for _, machine in self.data_cache['machinery'].iterrows():
            logs = get_fuel_logs(machine['id'])
            if not logs.empty:
                logs['machine_id'] = machine['id']
                logs['machine_name'] = machine['name']
                logs['classification'] = machine.get('classification', 'Unknown')
                fuel_data.append(logs)
        
        return pd.concat(fuel_data, ignore_index=True) if fuel_data else pd.DataFrame()
    
    def _get_all_maintenance_records(self):
        """Obtiene registros de mantenimiento de todas las máquinas"""
        try:
            return get_maintenance_records(self.empresa_id)
        except Exception:
            return pd.DataFrame()
    
    def _get_all_work_logs(self):
        """Obtiene logs de trabajo de todas las máquinas"""
        try:
            with get_conn() as conn:
                return pd.read_sql_query("""
                    SELECT dwl.*, m.name as machine_name, m.classification
                    FROM daily_work_logs dwl
                    JOIN machinery m ON dwl.machinery_id = m.id
                    WHERE dwl.company_id = ?
                    ORDER BY dwl.work_date DESC
                """, conn, params=(self.empresa_id,))
        except Exception:
            return pd.DataFrame()

class PredictiveAnalyzer:
    """Analizador predictivo avanzado"""
    
    def __init__(self, stats_instance):
        self.stats = stats_instance
        self.data = stats_instance._get_base_data()
    
    def predict_maintenance_needs(self, days_ahead=30, confidence_level=0.8):
        """Predicción avanzada de necesidades de mantenimiento"""
        try:
            machinery = self.data['machinery']
            predictions = []
            
            for _, machine in machinery.iterrows():
                # Obtener historial de mantenimiento
                maintenance_history = self._get_machine_maintenance_history(machine['id'])
                
                if len(maintenance_history) < 2:
                    continue
                
                # Análisis de tendencias
                prediction = self._analyze_maintenance_patterns(
                    machine, maintenance_history, days_ahead, confidence_level
                )
                
                if prediction:
                    predictions.append(prediction)
            
            return pd.DataFrame(predictions)
        
        except Exception as e:
            st.error(f"Error en predicción de mantenimiento: {e}")
            return pd.DataFrame()
    
    def _get_machine_maintenance_history(self, machine_id):
        """Obtiene historial detallado de mantenimiento de una máquina"""
        maintenance_records = self.data.get('maintenance_records', pd.DataFrame())
        
        if maintenance_records.empty:
            return pd.DataFrame()
        
        machine_maintenance = maintenance_records[
            maintenance_records['machinery_id'] == machine_id
        ].copy()
        
        if not machine_maintenance.empty:
            machine_maintenance['performed_at'] = pd.to_datetime(machine_maintenance['performed_at'])
            machine_maintenance = machine_maintenance.sort_values('performed_at')
        
        return machine_maintenance
    
    def _analyze_maintenance_patterns(self, machine, history, days_ahead, confidence_level):
        """Analiza patrones de mantenimiento para predicción"""
        try:
            # Calcular intervalos entre mantenimientos
            history['days_since_last'] = history['performed_at'].diff().dt.days
            
            # Análisis estadístico de intervalos
            intervals = history['days_since_last'].dropna()
            
            if len(intervals) < 2:
                return None
            
            # Predicción basada en tendencias
            mean_interval = intervals.mean()
            std_interval = intervals.std()
            
            # Último mantenimiento
            last_maintenance = history['performed_at'].max()
            days_since_last = (datetime.now() - last_maintenance).days
            
            # Predicción de próximo mantenimiento
            predicted_interval = mean_interval
            
            # Ajuste por tendencia si hay suficientes datos
            if len(intervals) >= 3:
                trend_slope = self._calculate_trend_slope(intervals)
                predicted_interval += trend_slope * len(intervals)
            
            next_maintenance_days = max(0, predicted_interval - days_since_last)
            
            # Cálculo de riesgo
            risk_score = min(100, max(0, 
                (days_since_last / predicted_interval) * 100
            ))
            
            # Nivel de urgencia
            if next_maintenance_days <= 7:
                urgency = "CRÍTICO"
                urgency_color = "red"
            elif next_maintenance_days <= 14:
                urgency = "ALTO"
                urgency_color = "orange"
            elif next_maintenance_days <= 30:
                urgency = "MEDIO"
                urgency_color = "yellow"
            else:
                urgency = "BAJO"
                urgency_color = "green"
            
            return {
                'machine_id': machine['id'],
                'machine_name': machine['name'],
                'classification': machine.get('classification', 'Unknown'),
                'last_maintenance': last_maintenance.strftime('%Y-%m-%d'),
                'days_since_last': days_since_last,
                'predicted_next_days': int(next_maintenance_days),
                'predicted_date': (datetime.now() + timedelta(days=next_maintenance_days)).strftime('%Y-%m-%d'),
                'risk_score': round(risk_score, 1),
                'urgency_level': urgency,
                'urgency_color': urgency_color,
                'confidence': round(confidence_level * 100, 1),
                'maintenance_count': len(history),
                'avg_interval_days': round(mean_interval, 1),
                'interval_variance': round(std_interval, 1) if not pd.isna(std_interval) else 0
            }
        
        except Exception as e:
            print(f"Error analizando patrones para {machine['name']}: {e}")
            return None
    
    def _calculate_trend_slope(self, intervals):
        """Calcula la tendencia en los intervalos de mantenimiento"""
        try:
            x = np.arange(len(intervals))
            y = intervals.values
            
            if len(x) < 2:
                return 0
            
            slope, _, _, _, _ = stats.linregress(x, y)
            return slope
        except:
            return 0
    
    def predict_fuel_consumption(self, days_ahead=30):
        """Predicción de consumo de combustible"""
        try:
            fuel_logs = self.data.get('fuel_logs', pd.DataFrame())
            
            if fuel_logs.empty:
                return pd.DataFrame()
            
            # Preparar datos
            fuel_logs['added_at'] = pd.to_datetime(fuel_logs['added_at'])
            fuel_logs = fuel_logs.sort_values('added_at')
            
            predictions = []
            
            # Análisis por máquina
            for machine_id in fuel_logs['machine_id'].unique():
                machine_fuel = fuel_logs[fuel_logs['machine_id'] == machine_id]
                
                if len(machine_fuel) < 3:
                    continue
                
                prediction = self._analyze_fuel_patterns(machine_fuel, days_ahead)
                if prediction:
                    predictions.append(prediction)
            
            return pd.DataFrame(predictions)
        
        except Exception as e:
            st.error(f"Error en predicción de combustible: {e}")
            return pd.DataFrame()
    
    def _analyze_fuel_patterns(self, machine_fuel, days_ahead):
        """Analiza patrones de consumo de combustible por máquina"""
        try:
            machine_name = machine_fuel['machine_name'].iloc[0]
            
            # Calcular consumo diario promedio
            machine_fuel['days_diff'] = machine_fuel['added_at'].diff().dt.days
            machine_fuel['daily_consumption'] = machine_fuel['fuel_added'] / machine_fuel['days_diff']
            
            # Filtrar valores válidos
            valid_consumption = machine_fuel['daily_consumption'].dropna()
            valid_consumption = valid_consumption[valid_consumption > 0]
            
            if len(valid_consumption) < 2:
                return None
            
            # Análisis estadístico
            avg_daily = valid_consumption.mean()
            std_daily = valid_consumption.std()
            
            # Predicción para los próximos días
            predicted_total = avg_daily * days_ahead
            
            # Calcular tendencia
            if len(valid_consumption) >= 3:
                x = np.arange(len(valid_consumption))
                y = valid_consumption.values
                slope, _, r_value, _, _ = stats.linregress(x, y)
                trend_direction = "AUMENTANDO" if slope > 0 else "DISMINUYENDO" if slope < 0 else "ESTABLE"
                trend_strength = abs(r_value)
            else:
                trend_direction = "INSUFICIENTE_DATA"
                trend_strength = 0
            
            # Nivel de alerta
            days_last_refuel = (datetime.now() - machine_fuel['added_at'].max()).days
            
            if days_last_refuel > avg_daily * 7:  # Más de una semana sin recargar
                alert_level = "CRÍTICO"
            elif days_last_refuel > avg_daily * 3:  # Más de 3 días
                alert_level = "ALTO"
            else:
                alert_level = "NORMAL"
            
            return {
                'machine_name': machine_name,
                'avg_daily_consumption': round(avg_daily, 2),
                'predicted_consumption': round(predicted_total, 2),
                'trend_direction': trend_direction,
                'trend_strength': round(trend_strength, 2),
                'days_since_last_refuel': days_last_refuel,
                'alert_level': alert_level,
                'consumption_variance': round(std_daily, 2) if not pd.isna(std_daily) else 0,
                'prediction_days': days_ahead
            }
        
        except Exception as e:
            print(f"Error analizando combustible: {e}")
            return None

class EfficiencyAnalyzer:
    """Analizador de eficiencia operacional"""
    
    def __init__(self, stats_instance):
        self.stats = stats_instance
        self.data = stats_instance._get_base_data()
    
    def analyze_operational_efficiency(self):
        """Análisis completo de eficiencia operacional"""
        try:
            machinery = self.data['machinery']
            work_logs = self.data.get('work_logs', pd.DataFrame())
            
            if machinery.empty:
                return pd.DataFrame()
            
            efficiency_data = []
            
            for _, machine in machinery.iterrows():
                efficiency = self._calculate_machine_efficiency(machine, work_logs)
                if efficiency:
                    efficiency_data.append(efficiency)
            
            df = pd.DataFrame(efficiency_data)
            
            if not df.empty:
                # Agregar rankings y comparaciones
                df = self._add_efficiency_rankings(df)
            
            return df
        
        except Exception as e:
            st.error(f"Error en análisis de eficiencia: {e}")
            return pd.DataFrame()
    
    def _calculate_machine_efficiency(self, machine, work_logs):
        """Calcula métricas de eficiencia para una máquina"""
        try:
            machine_id = machine['id']
            machine_work = work_logs[work_logs['machinery_id'] == machine_id] if not work_logs.empty else pd.DataFrame()
            
            # Métricas básicas
            total_hours = machine.get('current_hours', 0)
            consumption_per_hour = machine.get('consumption_per_hour', 0)
            
            # Análisis de logs de trabajo
            if not machine_work.empty:
                machine_work['work_date'] = pd.to_datetime(machine_work['work_date'])
                recent_work = machine_work[machine_work['work_date'] >= datetime.now() - timedelta(days=30)]
                
                work_hours_30d = recent_work['hours_worked'].sum() if not recent_work.empty else 0
                work_days_30d = len(recent_work['work_date'].dt.date.unique()) if not recent_work.empty else 0
                avg_hours_per_day = work_hours_30d / max(1, work_days_30d)
                
                # Análisis de operadores
                if 'operator' in recent_work.columns:
                    operators = recent_work['operator'].value_counts()
                    primary_operator = operators.index[0] if len(operators) > 0 else "N/A"
                    operator_consistency = (operators.iloc[0] / len(recent_work)) * 100 if len(operators) > 0 else 0
                else:
                    primary_operator = "N/A"
                    operator_consistency = 0
            else:
                work_hours_30d = 0
                work_days_30d = 0
                avg_hours_per_day = 0
                primary_operator = "N/A"
                operator_consistency = 0
            
            # Cálculo de eficiencia
            theoretical_max_hours = 8 * 30  # 8 horas por día, 30 días
            utilization_rate = (work_hours_30d / theoretical_max_hours) * 100 if theoretical_max_hours > 0 else 0
            
            # Eficiencia de combustible
            if consumption_per_hour > 0 and work_hours_30d > 0:
                fuel_efficiency = work_hours_30d / (consumption_per_hour * work_hours_30d)
            else:
                fuel_efficiency = 0
            
            # Scoring de eficiencia general
            efficiency_score = self._calculate_efficiency_score(
                utilization_rate, operator_consistency, fuel_efficiency
            )
            
            return {
                'machine_id': machine_id,
                'machine_name': machine['name'],
                'classification': machine.get('classification', 'Unknown'),
                'total_hours': total_hours,
                'work_hours_30d': work_hours_30d,
                'work_days_30d': work_days_30d,
                'avg_hours_per_day': round(avg_hours_per_day, 2),
                'utilization_rate': round(utilization_rate, 2),
                'primary_operator': primary_operator,
                'operator_consistency': round(operator_consistency, 2),
                'fuel_efficiency': round(fuel_efficiency, 4),
                'efficiency_score': round(efficiency_score, 2),
                'consumption_per_hour': consumption_per_hour
            }
        
        except Exception as e:
            print(f"Error calculando eficiencia para {machine['name']}: {e}")
            return None
    
    def _calculate_efficiency_score(self, utilization, operator_consistency, fuel_efficiency):
        """Calcula un score general de eficiencia"""
        try:
            # Normalizar métricas (0-100)
            util_score = min(100, utilization)
            operator_score = operator_consistency
            fuel_score = min(100, fuel_efficiency * 1000) if fuel_efficiency > 0 else 50
            
            # Pesos para cada métrica
            weights = {
                'utilization': 0.4,
                'operator': 0.3,
                'fuel': 0.3
            }
            
            total_score = (
                util_score * weights['utilization'] +
                operator_score * weights['operator'] +
                fuel_score * weights['fuel']
            )
            
            return total_score
        
        except Exception:
            return 0
    
    def _add_efficiency_rankings(self, df):
        """Agrega rankings y comparaciones al DataFrame"""
        try:
            # Ranking por efficiency_score
            df['efficiency_rank'] = df['efficiency_score'].rank(ascending=False, method='dense').astype(int)
            
            # Ranking por utilización
            df['utilization_rank'] = df['utilization_rate'].rank(ascending=False, method='dense').astype(int)
            
            # Clasificación de performance
            df['performance_category'] = df['efficiency_score'].apply(self._categorize_performance)
            
            # Comparación con promedio
            avg_efficiency = df['efficiency_score'].mean()
            df['vs_average'] = df['efficiency_score'] - avg_efficiency
            df['vs_average_pct'] = (df['vs_average'] / avg_efficiency) * 100
            
            return df.sort_values('efficiency_score', ascending=False)
        
        except Exception as e:
            print(f"Error agregando rankings: {e}")
            return df
    
    def _categorize_performance(self, score):
        """Categoriza el performance basado en el score"""
        if score >= 80:
            return "EXCELENTE"
        elif score >= 65:
            return "BUENO"
        elif score >= 50:
            return "REGULAR"
        elif score >= 35:
            return "DEFICIENTE"
        else:
            return "CRÍTICO"

class FinancialAnalyzer:
    """Analizador financiero avanzado"""
    
    def __init__(self, stats_instance):
        self.stats = stats_instance
        self.data = stats_instance._get_base_data()
    
    def calculate_roi_analysis(self):
        """Análisis de ROI por máquina"""
        try:
            machinery = self.data['machinery']
            
            if machinery.empty:
                return pd.DataFrame()
            
            roi_data = []
            
            for _, machine in machinery.iterrows():
                roi_info = self._calculate_machine_roi(machine)
                if roi_info:
                    roi_data.append(roi_info)
            
            return pd.DataFrame(roi_data)
        
        except Exception as e:
            st.error(f"Error en análisis ROI: {e}")
            return pd.DataFrame()
    
    def _calculate_machine_roi(self, machine):
        """Calcula ROI para una máquina específica"""
        try:
            # Información básica
            machine_id = machine['id']
            machine_name = machine['name']
            purchase_date = machine.get('purchase_date')
            
            # Estimación de valor de compra (si no está disponible, usar heurísticas)
            estimated_purchase_value = self._estimate_purchase_value(machine)
            
            # Cálculos de costos operacionales
            monthly_operating_cost = self._calculate_monthly_operating_cost(machine)
            annual_operating_cost = monthly_operating_cost * 12
            
            # Cálculos de ingresos (basado en horas productivas)
            estimated_monthly_revenue = self._estimate_monthly_revenue(machine)
            annual_revenue = estimated_monthly_revenue * 12
            
            # ROI anual
            annual_profit = annual_revenue - annual_operating_cost
            roi_percentage = (annual_profit / estimated_purchase_value) * 100 if estimated_purchase_value > 0 else 0
            
            # Período de recuperación (Payback period)
            payback_months = (estimated_purchase_value / max(1, annual_profit)) * 12 if annual_profit > 0 else float('inf')
            
            # Costo total de propiedad (TCO) estimado para 5 años
            tco_5_years = estimated_purchase_value + (annual_operating_cost * 5)
            
            # Valor presente neto estimado (NPV) - simplificado
            discount_rate = 0.1  # 10% anual
            npv = self._calculate_npv(annual_profit, estimated_purchase_value, 5, discount_rate)
            
            return {
                'machine_id': machine_id,
                'machine_name': machine_name,
                'classification': machine.get('classification', 'Unknown'),
                'estimated_purchase_value': estimated_purchase_value,
                'monthly_operating_cost': round(monthly_operating_cost, 2),
                'annual_operating_cost': round(annual_operating_cost, 2),
                'estimated_monthly_revenue': round(estimated_monthly_revenue, 2),
                'annual_revenue': round(annual_revenue, 2),
                'annual_profit': round(annual_profit, 2),
                'roi_percentage': round(roi_percentage, 2),
                'payback_months': round(payback_months, 2) if payback_months != float('inf') else "N/A",
                'tco_5_years': round(tco_5_years, 2),
                'npv_5_years': round(npv, 2),
                'profitability_status': self._categorize_profitability(roi_percentage)
            }
        
        except Exception as e:
            print(f"Error calculando ROI para {machine['name']}: {e}")
            return None
    
    def _estimate_purchase_value(self, machine):
        """Estima el valor de compra basado en clasificación y año"""
        try:
            classification = machine.get('classification', 'Unknown')
            purchase_date = machine.get('purchase_date')
            
            # Valores base por clasificación (USD)
            base_values = {
                'Excavadora': 200000,
                'Bulldozer': 250000,
                'Camión': 150000,
                'Grúa': 300000,
                'Compactadora': 100000,
                'Cargador': 180000,
                'Motoniveladora': 220000,
                'Trituradora': 400000,
                'Maquinaria Pesada': 200000,
                'Unknown': 150000
            }
            
            base_value = base_values.get(classification, 150000)
            
            # Ajuste por antigüedad si hay fecha de compra
            if purchase_date:
                try:
                    purchase_year = pd.to_datetime(purchase_date).year
                    current_year = datetime.now().year
                    age = current_year - purchase_year
                    
                    # Depreciación del 8% anual
                    depreciation_factor = (1 - 0.08) ** age
                    estimated_value = base_value * depreciation_factor
                except:
                    estimated_value = base_value
            else:
                # Asumir máquina de 5 años si no hay fecha
                estimated_value = base_value * (1 - 0.08) ** 5
            
            return max(estimated_value, base_value * 0.2)  # Mínimo 20% del valor base
        
        except Exception:
            return 150000  # Valor por defecto
    
    def _calculate_monthly_operating_cost(self, machine):
        """Calcula costos operacionales mensuales"""
        try:
            # Costo de combustible
            consumption_per_hour = machine.get('consumption_per_hour', 0)
            fuel_cost_per_gallon = 3.5  # USD por galón (ajustable)
            hours_per_month = 160  # 8 horas x 20 días
            
            monthly_fuel_cost = consumption_per_hour * hours_per_month * fuel_cost_per_gallon
            
            # Costo de mantenimiento (estimado como % del valor de la máquina)
            estimated_value = self._estimate_purchase_value(machine)
            monthly_maintenance_cost = estimated_value * 0.015 / 12  # 1.5% anual
            
            # Otros costos operacionales (seguros, operador, etc.)
            monthly_operator_cost = 3000  # USD/mes
            monthly_insurance = estimated_value * 0.005 / 12  # 0.5% anual
            
            total_monthly_cost = (
                monthly_fuel_cost + 
                monthly_maintenance_cost + 
                monthly_operator_cost + 
                monthly_insurance
            )
            
            return total_monthly_cost
        
        except Exception:
            return 5000  # Costo por defecto
    
    def _estimate_monthly_revenue(self, machine):
        """Estima ingresos mensuales basado en capacidad productiva"""
        try:
            classification = machine.get('classification', 'Unknown')
            
            # Tarifas por hora por tipo de máquina (USD/hora)
            hourly_rates = {
                'Excavadora': 85,
                'Bulldozer': 90,
                'Camión': 55,
                'Grúa': 120,
                'Compactadora': 65,
                'Cargador': 75,
                'Motoniveladora': 80,
                'Trituradora': 150,
                'Maquinaria Pesada': 80,
                'Unknown': 70
            }
            
            hourly_rate = hourly_rates.get(classification, 70)
            hours_per_month = 160  # 8 horas x 20 días laborales
            
            # Factor de utilización (85% en promedio)
            utilization_factor = 0.85
            
            monthly_revenue = hourly_rate * hours_per_month * utilization_factor
            
            return monthly_revenue
        
        except Exception:
            return 8000  # Ingreso por defecto
    
    def _calculate_npv(self, annual_cash_flow, initial_investment, years, discount_rate):
        """Calcula Valor Presente Neto"""
        try:
            npv = -initial_investment
            
            for year in range(1, years + 1):
                npv += annual_cash_flow / ((1 + discount_rate) ** year)
            
            return npv
        
        except Exception:
            return 0
    
    def _categorize_profitability(self, roi_percentage):
        """Categoriza la rentabilidad"""
        if roi_percentage >= 20:
            return "EXCELENTE"
        elif roi_percentage >= 15:
            return "MUY_BUENO"
        elif roi_percentage >= 10:
            return "BUENO"
        elif roi_percentage >= 5:
            return "REGULAR"
        elif roi_percentage >= 0:
            return "MARGINAL"
        else:
            return "PERDIDA"

# Funciones auxiliares para visualización
def create_efficiency_chart(efficiency_data):
    """Crea gráfico de eficiencia operacional"""
    if efficiency_data.empty:
        return None
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Utilización vs Eficiencia', 'Ranking de Máquinas', 
                       'Distribución de Performance', 'Horas Trabajadas'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Gráfico 1: Scatter de utilización vs eficiencia
    fig.add_trace(
        go.Scatter(
            x=efficiency_data['utilization_rate'],
            y=efficiency_data['efficiency_score'],
            mode='markers',
            text=efficiency_data['machine_name'],
            marker=dict(
                size=efficiency_data['work_hours_30d'] / 10,
                color=efficiency_data['efficiency_score'],
                colorscale='RdYlGn',
                showscale=True
            ),
            name='Máquinas'
        ),
        row=1, col=1
    )
    
    # Gráfico 2: Top 10 máquinas por eficiencia
    top_10 = efficiency_data.head(10)
    fig.add_trace(
        go.Bar(
            x=top_10['machine_name'],
            y=top_10['efficiency_score'],
            marker_color='lightblue',
            name='Score Eficiencia'
        ),
        row=1, col=2
    )
    
    # Gráfico 3: Distribución de categorías
    performance_counts = efficiency_data['performance_category'].value_counts()
    fig.add_trace(
        go.Pie(
            labels=performance_counts.index,
            values=performance_counts.values,
            name='Categorías'
        ),
        row=2, col=1
    )
    
    # Gráfico 4: Horas trabajadas por máquina
    fig.add_trace(
        go.Bar(
            x=efficiency_data['machine_name'][:10],
            y=efficiency_data['work_hours_30d'][:10],
            marker_color='orange',
            name='Horas (30d)'
        ),
        row=2, col=2
    )
    
    fig.update_layout(height=800, showlegend=False, title_text="Dashboard de Eficiencia Operacional")
    return fig

def create_predictive_maintenance_chart(predictions_data):
    """Crea gráfico de predicciones de mantenimiento"""
    if predictions_data.empty:
        return None
    
    # Ordenar por urgencia y días hasta mantenimiento
    predictions_data = predictions_data.sort_values(['urgency_level', 'predicted_next_days'])
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Cronograma de Mantenimiento', 'Distribución de Riesgo',
                       'Urgencia por Máquina', 'Intervalos vs Predicción'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Gráfico 1: Timeline de mantenimientos
    fig.add_trace(
        go.Scatter(
            x=predictions_data['predicted_next_days'],
            y=predictions_data['machine_name'],
            mode='markers',
            marker=dict(
                size=predictions_data['risk_score'] / 5,
                color=predictions_data['risk_score'],
                colorscale='RdYlGn_r',
                showscale=True,
                colorbar=dict(title="Risk Score")
            ),
            text=predictions_data['urgency_level'],
            name='Predicciones'
        ),
        row=1, col=1
    )
    
    # Gráfico 2: Distribución de niveles de riesgo
    risk_counts = predictions_data['urgency_level'].value_counts()
    colors = {'CRÍTICO': 'red', 'ALTO': 'orange', 'MEDIO': 'yellow', 'BAJO': 'green'}
    
    fig.add_trace(
        go.Bar(
            x=risk_counts.index,
            y=risk_counts.values,
            marker_color=[colors.get(level, 'gray') for level in risk_counts.index],
            name='Distribución Urgencia'
        ),
        row=1, col=2
    )
    
    # Gráfico 3: Risk score por máquina
    fig.add_trace(
        go.Bar(
            x=predictions_data['machine_name'][:10],
            y=predictions_data['risk_score'][:10],
            marker_color='lightcoral',
            name='Risk Score'
        ),
        row=2, col=1
    )
    
    # Gráfico 4: Intervalos promedio vs predicción
    fig.add_trace(
        go.Scatter(
            x=predictions_data['avg_interval_days'],
            y=predictions_data['predicted_next_days'],
            mode='markers',
            text=predictions_data['machine_name'],
            marker=dict(color='blue', size=8),
            name='Intervalo vs Predicción'
        ),
        row=2, col=2
    )
    
    # Línea de referencia (y=x)
    max_val = max(predictions_data['avg_interval_days'].max(), predictions_data['predicted_next_days'].max())
    fig.add_trace(
        go.Scatter(
            x=[0, max_val],
            y=[0, max_val],
            mode='lines',
            line=dict(dash='dash', color='gray'),
            name='Línea de referencia'
        ),
        row=2, col=2
    )
    
    fig.update_layout(height=800, showlegend=False, title_text="Análisis Predictivo de Mantenimiento")
    return fig

def create_financial_dashboard(roi_data):
    """Crea dashboard financiero - VERSIÓN CORREGIDA"""
    if roi_data.empty:
        return None
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('ROI por Máquina', 'Distribución de Rentabilidad',
                       'Costos vs Ingresos', 'Análisis de Payback'),
        specs=[[{"secondary_y": False}, {"type": "pie"}],  # ← ESTA ES LA CORRECCIÓN
               [{"secondary_y": True}, {"secondary_y": False}]]
    )
    
    # Gráfico 1: ROI por máquina
    colors = roi_data['roi_percentage'].apply(lambda x: 'green' if x > 15 else 'orange' if x > 5 else 'red')
    
    fig.add_trace(
        go.Bar(
            x=roi_data['machine_name'],
            y=roi_data['roi_percentage'],
            marker_color=colors,
            name='ROI %'
        ),
        row=1, col=1
    )
    
    # Gráfico 2: Distribución de categorías de rentabilidad
    profit_counts = roi_data['profitability_status'].value_counts()
    fig.add_trace(
        go.Pie(
            labels=profit_counts.index,
            values=profit_counts.values,
            name='Rentabilidad'
        ),
        row=1, col=2
    )
    
    # Gráfico 3: Costos vs Ingresos (con líneas de tendencia)
    fig.add_trace(
        go.Scatter(
            x=roi_data['machine_name'],
            y=roi_data['annual_operating_cost'],
            mode='lines+markers',
            name='Costos Anuales',
            line=dict(color='red')
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=roi_data['machine_name'],
            y=roi_data['annual_revenue'],
            mode='lines+markers',
            name='Ingresos Anuales',
            line=dict(color='green')
        ),
        row=2, col=1, secondary_y=True
    )
    
    # Gráfico 4: Análisis de período de recuperación
    payback_data = roi_data[roi_data['payback_months'] != "N/A"].copy()
    if not payback_data.empty:
        payback_data['payback_months'] = pd.to_numeric(payback_data['payback_months'])
        
        fig.add_trace(
            go.Bar(
                x=payback_data['machine_name'],
                y=payback_data['payback_months'],
                marker_color='lightblue',
                name='Payback (meses)'
            ),
            row=2, col=2
        )
    
    fig.update_layout(height=800, showlegend=True, title_text="Dashboard Financiero")
    return fig
    
class ConsumptionAnalyzer:
    """Analizador inteligente de consumo"""

def __init__(self, stats_instance):
        self.stats = stats_instance
        self.data = stats_instance._get_base_data()
    
def analyze_consumption_patterns(self, months_back=6):
        """Análisis de patrones de consumo inteligente"""
        try:
            fuel_logs = self.data.get('fuel_logs', pd.DataFrame())
            
            if fuel_logs.empty:
                return {
                    'seasonal_patterns': pd.DataFrame(),
                    'consumption_trends': pd.DataFrame(),
                    'optimization_recommendations': [],
                    'inventory_alerts': []
                }
            
            # Preparar datos temporales
            fuel_logs['added_at'] = pd.to_datetime(fuel_logs['added_at'])
            fuel_logs['month'] = fuel_logs['added_at'].dt.month
            fuel_logs['week'] = fuel_logs['added_at'].dt.isocalendar().week
            fuel_logs['day_of_week'] = fuel_logs['added_at'].dt.dayofweek
            
            # Filtrar por período
            cutoff_date = datetime.now() - timedelta(days=months_back * 30)
            recent_data = fuel_logs[fuel_logs['added_at'] >= cutoff_date]
            
            # Análisis estacional
            seasonal_patterns = self._analyze_seasonal_patterns(recent_data)
            
            # Tendencias de consumo
            consumption_trends = self._analyze_consumption_trends(recent_data)
            
            # Recomendaciones de optimización
            optimization_recommendations = self._generate_optimization_recommendations(recent_data)
            
            # Alertas de inventario
            inventory_alerts = self._generate_inventory_alerts()
            
            return {
                'seasonal_patterns': seasonal_patterns,
                'consumption_trends': consumption_trends,
                'optimization_recommendations': optimization_recommendations,
                'inventory_alerts': inventory_alerts,
                'analysis_period': f"Últimos {months_back} meses",
                'total_records': len(recent_data)
            }
        
        except Exception as e:
            st.error(f"Error en análisis de consumo: {e}")
            return {}
    
def _analyze_seasonal_patterns(self, fuel_data):
        """Identifica patrones estacionales en el consumo"""
        try:
            if fuel_data.empty:
                return pd.DataFrame()
            
            # Agrupar por mes
            monthly_consumption = fuel_data.groupby(['month', 'machine_name']).agg({
                'fuel_added': ['sum', 'mean', 'count']
            }).reset_index()
            
            monthly_consumption.columns = ['month', 'machine_name', 'total_fuel', 'avg_fuel', 'refill_count']
            
            # Calcular estadísticas estacionales
            seasonal_stats = monthly_consumption.groupby('month').agg({
                'total_fuel': ['mean', 'std'],
                'refill_count': 'mean'
            }).reset_index()
            
            seasonal_stats.columns = ['month', 'avg_consumption', 'consumption_std', 'avg_refills']
            
            # Identificar meses de alto/bajo consumo
            seasonal_stats['consumption_category'] = seasonal_stats['avg_consumption'].apply(
                lambda x: 'ALTO' if x > seasonal_stats['avg_consumption'].quantile(0.75) 
                else 'BAJO' if x < seasonal_stats['avg_consumption'].quantile(0.25) 
                else 'NORMAL'
            )
            
            return seasonal_stats
        
        except Exception as e:
            print(f"Error en análisis estacional: {e}")
            return pd.DataFrame()
    
def _analyze_consumption_trends(self, fuel_data):
        """Analiza tendencias de consumo por máquina"""
        try:
            if fuel_data.empty:
                return pd.DataFrame()
            
            trends = []
            
            for machine_name in fuel_data['machine_name'].unique():
                machine_data = fuel_data[fuel_data['machine_name'] == machine_name].copy()
                machine_data = machine_data.sort_values('added_at')
                
                if len(machine_data) < 3:
                    continue
                
                # Calcular tendencia usando regresión lineal
                x = np.arange(len(machine_data))
                y = machine_data['fuel_added'].values
                
                if len(x) > 1:
                    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                    
                    # Determinar dirección de tendencia
                    if slope > 0.1:
                        trend_direction = "AUMENTANDO"
                        trend_color = "red"
                    elif slope < -0.1:
                        trend_direction = "DISMINUYENDO"
                        trend_color = "green"
                    else:
                        trend_direction = "ESTABLE"
                        trend_color = "yellow"
                    
                    # Calcular métricas adicionales
                    recent_avg = machine_data['fuel_added'].tail(5).mean()
                    historical_avg = machine_data['fuel_added'].mean()
                    change_percentage = ((recent_avg - historical_avg) / historical_avg) * 100
                    
                    trends.append({
                        'machine_name': machine_name,
                        'trend_direction': trend_direction,
                        'trend_color': trend_color,
                        'slope': round(slope, 4),
                        'correlation': round(r_value, 3),
                        'p_value': round(p_value, 4),
                        'recent_avg': round(recent_avg, 2),
                        'historical_avg': round(historical_avg, 2),
                        'change_percentage': round(change_percentage, 2),
                        'total_refills': len(machine_data),
                        'trend_strength': abs(r_value)
                    })
            
            return pd.DataFrame(trends)
        
        except Exception as e:
            print(f"Error en análisis de tendencias: {e}")
            return pd.DataFrame()
    
def _generate_optimization_recommendations(self, fuel_data):
        """Genera recomendaciones de optimización"""
        try:
            recommendations = []
            
            if fuel_data.empty:
                return recommendations
            
            # Análisis por máquina
            machine_stats = fuel_data.groupby('machine_name').agg({
                'fuel_added': ['sum', 'mean', 'std', 'count'],
                'added_at': ['min', 'max']
            }).reset_index()
            
            machine_stats.columns = ['machine_name', 'total_fuel', 'avg_fuel', 'fuel_std', 
                                   'refill_count', 'first_refill', 'last_refill']
            
            for _, machine in machine_stats.iterrows():
                machine_name = machine['machine_name']
                
                # Recomendación por alta variabilidad
                if machine['fuel_std'] > machine['avg_fuel'] * 0.5:
                    recommendations.append({
                        'machine': machine_name,
                        'type': 'VARIABILIDAD',
                        'priority': 'MEDIA',
                        'description': f"Alto desviación en consumo ({machine['fuel_std']:.1f})",
                        'recommendation': "Revisar patrones de uso y calibrar consumo esperado",
                        'potential_savings': f"{machine['fuel_std'] * 0.3:.1f} gal/mes"
                    })
                
                # Recomendación por baja frecuencia de reabastecimiento
                days_span = (machine['last_refill'] - machine['first_refill']).days
                if days_span > 0:
                    refill_frequency = machine['refill_count'] / (days_span / 30)  # Recargas por mes
                    
                    if refill_frequency < 2:  # Menos de 2 recargas por mes
                        recommendations.append({
                            'machine': machine_name,
                            'type': 'FRECUENCIA',
                            'priority': 'ALTA',
                            'description': f"Baja frecuencia de reabastecimiento ({refill_frequency:.1f}/mes)",
                            'recommendation': "Verificar si la máquina está subutilizada o tiene problemas",
                            'potential_savings': "Optimización de uso"
                        })
            
            # Recomendaciones generales del sistema
            total_consumption = fuel_data['fuel_added'].sum()
            avg_monthly_consumption = total_consumption / 6  # Asumiendo 6 meses de datos
            
            recommendations.append({
                'machine': 'SISTEMA_GENERAL',
                'type': 'INVENTARIO',
                'priority': 'MEDIA',
                'description': f"Consumo mensual promedio: {avg_monthly_consumption:.1f} gal",
                'recommendation': f"Mantener inventario mínimo de {avg_monthly_consumption * 1.5:.1f} gal",
                'potential_savings': "Evitar desabastecimientos"
            })
            
            return sorted(recommendations, key=lambda x: 
                         {'ALTA': 3, 'MEDIA': 2, 'BAJA': 1}[x['priority']], reverse=True)
        
        except Exception as e:
            print(f"Error generando recomendaciones: {e}")
            return []
    
def _generate_inventory_alerts(self):
        """Genera alertas de inventario predictivas"""
        try:
            tanks = self.data.get('tanks', pd.DataFrame())
            alerts = []
            
            if tanks.empty:
                return alerts
            
            for _, tank in tanks.iterrows():
                current_level = tank['current_level']
                capacity = tank['tank_capacity']
                fluid_name = tank['fluid_name']
                
                # Calcular días restantes basado en consumo histórico
                predicted_days = self._predict_tank_duration(tank)
                
                # Generar alertas según días restantes
                if predicted_days <= 3:
                    alert_level = "CRÍTICO"
                    alert_color = "red"
                elif predicted_days <= 7:
                    alert_level = "ALTO"
                    alert_color = "orange"
                elif predicted_days <= 14:
                    alert_level = "MEDIO"
                    alert_color = "yellow"
                else:
                    alert_level = "NORMAL"
                    alert_color = "green"
                
                if alert_level != "NORMAL":
                    alerts.append({
                        'fluid_name': fluid_name,
                        'current_level': current_level,
                        'capacity': capacity,
                        'percentage': round((current_level / capacity) * 100, 1),
                        'predicted_days': round(predicted_days, 1),
                        'alert_level': alert_level,
                        'alert_color': alert_color,
                        'recommended_order': round(capacity * 0.8 - current_level, 1),
                        'urgency_score': max(0, 14 - predicted_days)
                    })
            
            return sorted(alerts, key=lambda x: x['urgency_score'], reverse=True)
        
        except Exception as e:
            print(f"Error generando alertas de inventario: {e}")
            return []
    
def _predict_tank_duration(self, tank):
        """Predice duración del tanque basado en consumo histórico"""
        try:
            # Obtener movimientos recientes del tanque
            with get_conn() as conn:
                movements = pd.read_sql_query("""
                    SELECT * FROM fluid_inventory_movements 
                    WHERE tank_id = ? AND movement_type = 'SALIDA'
                    AND created_at >= date('now', '-30 days')
                    ORDER BY created_at DESC
                """, conn, params=(tank['id'],))
            
            if movements.empty:
                return 30  # Valor por defecto si no hay datos
            
            # Calcular consumo promedio diario
            movements['created_at'] = pd.to_datetime(movements['created_at'])
            days_span = (movements['created_at'].max() - movements['created_at'].min()).days
            
            if days_span <= 0:
                return 30
            
            total_consumption = movements['quantity'].sum()
            daily_consumption = total_consumption / days_span
            
            if daily_consumption <= 0:
                return 30
            
            # Calcular días restantes
            current_level = tank['current_level']
            predicted_days = current_level / daily_consumption
            
            return max(0, predicted_days)
        
        except Exception as e:
            print(f"Error prediciendo duración de tanque: {e}")
            return 30

def create_consumption_dashboard(consumption_analysis):
    """Crea dashboard de análisis de consumo"""
    try:
        seasonal = consumption_analysis.get('seasonal_patterns', pd.DataFrame())
        trends = consumption_analysis.get('consumption_trends', pd.DataFrame())
        
        if seasonal.empty and trends.empty:
            return None
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Patrones Estacionales', 'Tendencias por Máquina',
                           'Distribución de Tendencias', 'Correlación de Cambios'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Gráfico 1: Patrones estacionales
        if not seasonal.empty:
            fig.add_trace(
                go.Scatter(
                    x=seasonal['month'],
                    y=seasonal['avg_consumption'],
                    mode='lines+markers',
                    name='Consumo Promedio',
                    line=dict(color='blue', width=3),
                    error_y=dict(
                        type='data',
                        array=seasonal['consumption_std'],
                        visible=True
                    )
                ),
                row=1, col=1
            )
        
        # Gráfico 2: Tendencias por máquina
        if not trends.empty:
            colors = trends['trend_color'].map({'red': 'red', 'green': 'green', 'yellow': 'orange'})
            
            fig.add_trace(
                go.Bar(
                    x=trends['machine_name'],
                    y=trends['change_percentage'],
                    marker_color=colors,
                    name='Cambio %'
                ),
                row=1, col=2
            )
        
        # Gráfico 3: Distribución de direcciones de tendencia
        if not trends.empty:
            trend_counts = trends['trend_direction'].value_counts()
            fig.add_trace(
                go.Pie(
                    labels=trend_counts.index,
                    values=trend_counts.values,
                    name='Distribución Tendencias'
                ),
                row=2, col=1
            )
        
        # Gráfico 4: Correlación entre cambio reciente vs histórico
        if not trends.empty:
            fig.add_trace(
                go.Scatter(
                    x=trends['historical_avg'],
                    y=trends['recent_avg'],
                    mode='markers',
                    text=trends['machine_name'],
                    marker=dict(
                        size=trends['trend_strength'] * 20,
                        color=trends['change_percentage'],
                        colorscale='RdYlGn',
                        showscale=True
                    ),
                    name='Correlación'
                ),
                row=2, col=2
            )
            
            # Línea de referencia (y=x)
            max_val = max(trends['historical_avg'].max(), trends['recent_avg'].max())
            fig.add_trace(
                go.Scatter(
                    x=[0, max_val],
                    y=[0, max_val],
                    mode='lines',
                    line=dict(dash='dash', color='gray'),
                    name='Sin cambio'
                ),
                row=2, col=2
            )
        
        fig.update_layout(height=800, showlegend=False, title_text="Dashboard de Análisis de Consumo")
        return fig
    
    except Exception as e:
        st.error(f"Error creando dashboard de consumo: {e}")
        return None

# Funciones de utilidad para el módulo
def format_currency(amount):
    """Formatea cantidad como moneda"""
    return f"${amount:,.2f}"

def format_percentage(value):
    """Formatea valor como porcentaje"""
    return f"{value:.1f}%"

def get_status_color(status):
    """Obtiene color basado en status"""
    color_map = {
        'EXCELENTE': 'green',
        'MUY_BUENO': 'lightgreen',
        'BUENO': 'yellow',
        'REGULAR': 'orange',
        'MARGINAL': 'red',
        'PERDIDA': 'darkred',
        'CRÍTICO': 'red',
        'ALTO': 'orange',
        'MEDIO': 'yellow',
        'BAJO': 'green',
        'NORMAL': 'green'
    }
    return color_map.get(status, 'gray')

def calculate_kpis(empresa_id):
    """Calcula KPIs principales del sistema"""
    try:
        stats = AdvancedStatistics(empresa_id)
        data = stats._get_base_data()
        
        machinery = data['machinery']
        
        if machinery.empty:
            return {}
        
        # KPIs básicos
        total_machines = len(machinery)
        active_machines = len(machinery[machinery['status'] == 'Active'])
        utilization_rate = (active_machines / total_machines) * 100 if total_machines > 0 else 0
        
        # Eficiencia promedio
        efficiency_analyzer = EfficiencyAnalyzer(stats)
        efficiency_data = efficiency_analyzer.analyze_operational_efficiency()
        avg_efficiency = efficiency_data['efficiency_score'].mean() if not efficiency_data.empty else 0
        
        # Análisis financiero
        financial_analyzer = FinancialAnalyzer(stats)
        roi_data = financial_analyzer.calculate_roi_analysis()
        avg_roi = roi_data['roi_percentage'].mean() if not roi_data.empty else 0
        
        # Predicciones de mantenimiento
        predictive_analyzer = PredictiveAnalyzer(stats)
        maintenance_predictions = predictive_analyzer.predict_maintenance_needs()
        critical_machines = len(maintenance_predictions[
            maintenance_predictions['urgency_level'] == 'CRÍTICO'
        ]) if not maintenance_predictions.empty else 0
        
        return {
            'total_machines': total_machines,
            'active_machines': active_machines,
            'utilization_rate': round(utilization_rate, 1),
            'avg_efficiency_score': round(avg_efficiency, 1),
            'avg_roi_percentage': round(avg_roi, 1),
            'critical_maintenance_alerts': critical_machines,
            'efficiency_category': categorize_score(avg_efficiency),
            'roi_category': categorize_roi(avg_roi)
        }
    
    except Exception as e:
        st.error(f"Error calculando KPIs: {e}")
        return {}

def categorize_score(score):
    """Categoriza un score numérico"""
    if score >= 80:
        return "EXCELENTE"
    elif score >= 65:
        return "BUENO"
    elif score >= 50:
        return "REGULAR"
    else:
        return "DEFICIENTE"

def categorize_roi(roi):
    """Categoriza ROI"""
    if roi >= 15:
        return "EXCELENTE"
    elif roi >= 10:
        return "BUENO"
    elif roi >= 5:
        return "REGULAR"
    else:
        return "DEFICIENTE"