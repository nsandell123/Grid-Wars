import numpy as np
from src.dispatch import dispatch_optimization, calculate_benefit_metric, update_battery_states
from src.config import BATTERY_COUNT, BATTERY_CAPACITY_KWH

battery_states = np.full(BATTERY_COUNT, BATTERY_CAPACITY_KWH * 0.8)

temperature = 92.0
wholesale_price = 0.15
charging_cost = 0.03
historical_peak = 50000
current_load = 45000
is_valid_window = True

benefit = calculate_benefit_metric(
    load_ratio=current_load / historical_peak,
    temperature=temperature,
    price_per_kwh=wholesale_price,
    is_valid_call_window=is_valid_window
)

result = dispatch_optimization(
    battery_states=battery_states,
    temperature=temperature,
    wholesale_price_per_kwh=wholesale_price,
    charging_cost_per_kwh=charging_cost,
    benefit_metric=benefit,
    benefit_threshold=10.0,
    historical_peak_load=historical_peak,
    current_load=current_load,
    is_valid_call_window=is_valid_window
)

print(f"\n{'='*60}")
print(f"DISPATCH OPTIMIZATION RESULTS")
print(f"{'='*60}")
print(f"Total Available Power:    {result['total_available_kw']:,.0f} kW")
print(f"CoServ Requested:         {result['coserv_requested_kw']:,.0f} kW")
print(f"CoServ Allocated:         {result['coserv_allocated_kw']:,.0f} kW ({result['coserv_percent']:.1f}%)")
print(f"Base Allocated:           {result['base_allocated_kw']:,.0f} kW ({result['base_percent']:.1f}%)")
print(f"Base Revenue:             ${result['base_revenue']:,.2f}")
print(f"Penalty:                  ${result['penalty']:,.2f}")
print(f"Benefit Metric:           {result['benefit_metric']:.2f}")
print(f"CoServ Call Valid:        {result['coserv_call_valid']}")
print(f"{'='*60}\n")
