import requests
import gridstatus

from typing import Dict, Optional
from datetime import datetime

from src.config import (
    OPENMETEO_URL,
    ERCOT_SETTLEMENT_POINT,
    ERCOT_AUTH_URL,
    ERCOT_CLIENT_ID,
    ERCOT_SCOPE
)


class DataFetcher:
    def __init__(
        self,
        ercot_subscription_key: Optional[str] = None,
        ercot_username: Optional[str] = None,
        ercot_password: Optional[str] = None
    ):
        self.ercot_subscription_key = ercot_subscription_key
        self.ercot_username = ercot_username
        self.ercot_password = ercot_password
        self.id_token = None

    # --------------------------------------------------
    # TEMPERATURE
    # --------------------------------------------------

    def get_temperature(self) -> Optional[float]:
        try:
            response = requests.get(OPENMETEO_URL, timeout=10)
            response.raise_for_status()

            data = response.json()

            return data.get("current", {}).get("temperature_2m")

        except Exception as e:
            print(f"Error fetching temperature: {e}")
            return None

    # --------------------------------------------------
    # ERCOT AUTHENTICATION
    # --------------------------------------------------

    def _get_ercot_token(self) -> bool:
        if not all([
            self.ercot_subscription_key,
            self.ercot_username,
            self.ercot_password
        ]):
            print("ERCOT credentials not provided")
            return False

        try:
            auth_params = {
                "username": self.ercot_username,
                "password": self.ercot_password,
                "grant_type": "password",
                "scope": ERCOT_SCOPE,
                "client_id": ERCOT_CLIENT_ID,
                "response_type": "id_token"
            }

            auth_response = requests.post(
                ERCOT_AUTH_URL,
                params=auth_params,
                timeout=10
            )

            auth_response.raise_for_status()

            self.id_token = auth_response.json().get("id_token")

            return self.id_token is not None

        except Exception as e:
            print(f"Error getting ERCOT token: {e}")
            return False

    # --------------------------------------------------
    # ERCOT PRICE
    # --------------------------------------------------

    def get_ercot_price(self) -> Optional[float]:
        if not self.id_token and not self._get_ercot_token():
            return None

        try:
            url = (
                "https://api.ercot.com/api/public-reports/"
                "np6-905-cd/spp_node_zone_hub"
            )

            headers = {
                "accept": "application/json",
                "Ocp-Apim-Subscription-Key": self.ercot_subscription_key,
                "Authorization": f"Bearer {self.id_token}"
            }

            params = {
                "settlementPoint": ERCOT_SETTLEMENT_POINT,
                "settlementPointType": "LZ"
            }

            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            if isinstance(data, dict) and "data" in data:
                records = data["data"]

                if len(records) > 0:
                    latest = records[-1]

                    # ERCOT price is $/MWh
                    price_mwh = latest[5]

                    # Convert $/MWh -> $/kWh
                    return price_mwh / 1000

            return None

        except Exception as e:
            print(f"Error fetching ERCOT price: {e}")
            return None

    # --------------------------------------------------
    # ERCOT LOAD
    # --------------------------------------------------

    def get_ercot_load(self) -> Optional[Dict[str, float]]:
        try:
            iso = gridstatus.Ercot()
            load_data = iso.get_load_by_weather_zone("today")

            if load_data is None or load_data.empty:
                return None

            latest = load_data.iloc[-1]

            return {
                "current_load": float(latest["North Central"]),
                "timestamp": latest["Time"]
            }

        except Exception as e:
            print(f"Error fetching ERCOT load: {e}")
            return None

    # --------------------------------------------------
    # ALL DATA
    # --------------------------------------------------

    def get_all_data(self) -> Dict:
        return {
            "temperature": self.get_temperature(),
            "price_per_kwh": self.get_ercot_price(),
            "load_data": self.get_ercot_load(),
            "timestamp": datetime.now().isoformat()
        }