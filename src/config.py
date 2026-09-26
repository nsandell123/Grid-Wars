BATTERY_CAPACITY_KWH = 39.2
BATTERY_COUNT = 9091
SAFETY_FLOOR_PERCENT = 0.2
INVERTER_MAX_KW = 11.0
FLEET_MAX_KW = 100000

COSERV_MAX_EVENTS_PER_YEAR = 125
COSERV_MAX_EVENT_DURATION_INTERVALS = 8
COSERV_CAPACITY_FEE_PER_KW_MONTH = 9.0         # research to back?

CHARGING_EFFICIENCY = 0.92
INTERVAL_HOURS = 0.25

TRANSMISSION_WEIGHT = 15.0
PRICE_WEIGHT_FACTOR = 0.25 / 1000    
TEMP_WEIGHT = 0.02
TEMP_THRESHOLD = 85

ERCOT_API_BASE = "https://api.ercot.com"
ERCOT_SETTLEMENT_POINT = "LZ_NORTH"
ERCOT_LOAD_ZONE = "NORTH_C"

ERCOT_AUTH_URL = "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
ERCOT_CLIENT_ID = "fec253ea-0d06-4272-a5e6-b478baeecd70"
ERCOT_SCOPE = "openid fec253ea-0d06-4272-a5e6-b478baeecd70 offline_access"

OPENMETEO_LAT = 33.2148
OPENMETEO_LON = -97.1331
OPENMETEO_URL = f"https://api.open-meteo.com/v1/forecast?latitude={OPENMETEO_LAT}&longitude={OPENMETEO_LON}&current=temperature_2m&hourly=temperature_2m&temperature_unit=fahrenheit&timezone=America/Chicago"
