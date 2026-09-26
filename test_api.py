import os
from dotenv import load_dotenv
from src.data_fetcher import DataFetcher

load_dotenv()

ercot_subscription_key = os.getenv('ERCOT_SUBSCRIPTION_KEY')
ercot_username = os.getenv('ERCOT_USERNAME')
ercot_password = os.getenv('ERCOT_PASSWORD')

fetcher = DataFetcher(ercot_subscription_key, ercot_username, ercot_password)

print("Fetching real-time data...\n")

temp = fetcher.get_temperature()
print(f"Temperature (Denton, TX): {temp}°F" if temp else "Temperature: Failed to fetch")

price = fetcher.get_ercot_price()
print(f"ERCOT Price (LZ_NORTH): ${price:.4f}/kWh" if price else "Price: Failed to fetch (check API key)")

load_data = fetcher.get_ercot_load()
if load_data:
    print(f"ERCOT Load (NORTH_C): {load_data['current_load']:,.0f} MW")
else:
    print("Load: Failed to fetch (check API key)")

print("\nAll data:")
all_data = fetcher.get_all_data()
for key, value in all_data.items():
    print(f"  {key}: {value}")
