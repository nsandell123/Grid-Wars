import numpy as np
from scipy.optimize import minimize
from typing import Dict, Tuple
from src.config import *


def calculate_benefit_metric(
    load_ratio: float,
    temperature: float,
    price_per_kwh: float,
    is_valid_call_window: bool
) -> float:
    transmission_term = TRANSMISSION_WEIGHT * is_valid_call_window * load_ratio
    temp_term = TEMP_WEIGHT * max(0, temperature - TEMP_THRESHOLD)
    price_term = PRICE_WEIGHT_FACTOR * price_per_kwh * 1000
    
    return transmission_term + temp_term + price_term


def get_available_power_per_battery(energy_kwh: float, temperature: float) -> float:
    safety_floor_kwh = BATTERY_CAPACITY_KWH * SAFETY_FLOOR_PERCENT
    usable_energy = energy_kwh - safety_floor_kwh
    
    if usable_energy <= 0:
        return 0.0
    
    inverter_limit = INVERTER_MAX_KW
    if temperature > 95:
        inverter_limit *= 0.85
    elif temperature > 85:
        inverter_limit *= 0.95
    
    power_from_energy = usable_energy / INTERVAL_HOURS
    
    return min(inverter_limit, power_from_energy)


def dispatch_optimization(
    battery_states: np.ndarray,
    temperature: float,
    wholesale_price_per_kwh: float,
    charging_cost_per_kwh: float,
    benefit_metric: float,
    benefit_threshold: float,
    historical_peak_load: float,
    current_load: float,
    is_valid_call_window: bool
) -> Dict[str, float]:
    
    num_batteries = len(battery_states)
    available_power_per_battery = np.array([
        get_available_power_per_battery(state, temperature) 
        for state in battery_states
    ])
    
    total_available_kw = np.sum(available_power_per_battery)
    
    coserv_can_call = is_valid_call_window and benefit_metric >= benefit_threshold
    
    if coserv_can_call:
        load_ratio = current_load / historical_peak_load if historical_peak_load > 0 else 0
        coserv_requested_kw = min(
            # research how to obtain amt kw requested from benefit metric
            benefit_metric * 1000,
            total_available_kw,
            FLEET_MAX_KW
        )
    else:
        coserv_requested_kw = 0.0
    
    coserv_allocated_kw = min(coserv_requested_kw, total_available_kw)
    base_allocated_kw = total_available_kw - coserv_allocated_kw
    
    capacity_fee_revenue = (COSERV_CAPACITY_FEE_PER_KW_MONTH * FLEET_MAX_KW * INTERVAL_HOURS) / 720
    
    shortfall_kw = max(0, 0.9 * coserv_requested_kw - coserv_allocated_kw)
    hourly_capacity_rate = COSERV_CAPACITY_FEE_PER_KW_MONTH / 720
    penalty = 1.25 * hourly_capacity_rate * shortfall_kw * INTERVAL_HOURS
    
    base_revenue = (wholesale_price_per_kwh * base_allocated_kw * INTERVAL_HOURS) + capacity_fee_revenue - penalty
    
    return {
        'total_available_kw': total_available_kw,
        'coserv_requested_kw': coserv_requested_kw,
        'coserv_allocated_kw': coserv_allocated_kw,
        'base_allocated_kw': base_allocated_kw,
        'coserv_percent': (coserv_allocated_kw / total_available_kw * 100) if total_available_kw > 0 else 0,
        'base_percent': (base_allocated_kw / total_available_kw * 100) if total_available_kw > 0 else 0,
        'base_revenue': base_revenue,
        'penalty': penalty,
        'benefit_metric': benefit_metric,
        'coserv_call_valid': coserv_can_call
    }


def update_battery_states(
    battery_states: np.ndarray,
    discharge_kw_per_battery: np.ndarray,
    charge_kw_per_battery: np.ndarray = None
) -> np.ndarray:
    new_states = battery_states.copy()
    
    new_states -= discharge_kw_per_battery * INTERVAL_HOURS
    
    if charge_kw_per_battery is not None:
        new_states += charge_kw_per_battery * INTERVAL_HOURS * CHARGING_EFFICIENCY
    
    new_states = np.clip(new_states, 
                         BATTERY_CAPACITY_KWH * SAFETY_FLOOR_PERCENT,
                         BATTERY_CAPACITY_KWH)
    
    return new_states
