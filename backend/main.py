import asyncio
import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Grid Wars")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Battery Model ---

def create_battery(id: int) -> dict:
    return {
        "id": id,
        "soc": round(random.uniform(0.5, 1.0), 2),  # 50-100% starting charge
        "max_rate": 5.0,       # kW max discharge/charge speed
        "capacity": 13.5,      # kWh total size
        "status": "idle",      # idle | charging | discharging | offline
        "target": None,        # None | "market" | "utility" | "homeowner"
    }


# --- Global Simulation State ---

NUM_BATTERIES = 20
HOMEOWNER_RESERVE = 0.20  # never go below 20%
TICK_INTERVAL = 1.0       # seconds between simulation updates

batteries = [create_battery(i) for i in range(NUM_BATTERIES)]
ercot_price = 0.03        # $/kWh — starts normal
utility_stress = 0.2      # 0 = chill, 1 = critical
simulation_running = True
connected_clients: list[WebSocket] = []


# --- Dumb Optimizer (placeholder until your teammate replaces this) ---

def optimize_dispatch(batteries: list[dict], ercot_price: float, utility_stress: float) -> list[dict]:
    """
    Dumb decision maker. For each battery, decide what to do.
    Priority: homeowner reserve > utility obligation > market profit > idle.
    """
    decisions = []

    for b in batteries:
        if b["status"] == "offline":
            decisions.append({"id": b["id"], "action": "offline", "rate": 0, "target": None})
            continue

        available = b["soc"] - HOMEOWNER_RESERVE
        if available <= 0:
            decisions.append({"id": b["id"], "action": "idle", "rate": 0, "target": None})
            continue

        discharge_rate = min(b["max_rate"], available * b["capacity"])

        if utility_stress > 0.7:
            decisions.append({"id": b["id"], "action": "discharge", "rate": round(discharge_rate, 2), "target": "utility"})
        elif ercot_price > 0.10:
            decisions.append({"id": b["id"], "action": "discharge", "rate": round(discharge_rate, 2), "target": "market"})
        else:
            decisions.append({"id": b["id"], "action": "idle", "rate": 0, "target": None})

    return decisions


# --- Simulation Loop ---

async def simulation_loop():
    global ercot_price, utility_stress

    while simulation_running:
        # Drift price and stress randomly each tick (small wobble)
        ercot_price = max(0.01, ercot_price + random.uniform(-0.005, 0.005))
        utility_stress = max(0.0, min(1.0, utility_stress + random.uniform(-0.02, 0.02)))

        # Run the optimizer
        decisions = optimize_dispatch(batteries, ercot_price, utility_stress)

        # Apply decisions to battery state
        for decision in decisions:
            b = batteries[decision["id"]]
            if decision["action"] == "offline":
                continue

            b["status"] = decision["action"]
            b["target"] = decision["target"]

            if decision["action"] == "discharge" and decision["rate"] > 0:
                # Drain the battery: rate (kW) over TICK_INTERVAL seconds
                energy_used = decision["rate"] * (TICK_INTERVAL / 3600)  # kWh
                b["soc"] = max(HOMEOWNER_RESERVE, round(b["soc"] - energy_used / b["capacity"], 4))

            elif decision["action"] == "charging":
                energy_added = b["max_rate"] * (TICK_INTERVAL / 3600)
                b["soc"] = min(1.0, round(b["soc"] + energy_added / b["capacity"], 4))

        # Build the state snapshot
        state = {
            "batteries": batteries,
            "ercot_price": round(ercot_price, 4),
            "utility_stress": round(utility_stress, 4),
            "fleet_soc": round(sum(b["soc"] for b in batteries if b["status"] != "offline") / max(1, sum(1 for b in batteries if b["status"] != "offline")), 4),
            "active_nodes": sum(1 for b in batteries if b["status"] != "offline"),
            "total_nodes": NUM_BATTERIES,
        }

        # Push to all connected frontends
        disconnected = []
        for ws in connected_clients:
            try:
                await ws.send_text(json.dumps(state))
            except:
                disconnected.append(ws)
        for ws in disconnected:
            connected_clients.remove(ws)

        await asyncio.sleep(TICK_INTERVAL)


# --- Startup ---

@app.on_event("startup")
async def startup():
    asyncio.create_task(simulation_loop())


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        connected_clients.remove(ws)


# --- Chaos Endpoints ---

@app.post("/kill/{battery_id}")
def kill_battery(battery_id: int):
    """Kill a battery node. It goes offline and stops responding."""
    if 0 <= battery_id < NUM_BATTERIES:
        batteries[battery_id]["status"] = "offline"
        batteries[battery_id]["target"] = None
        return {"message": f"Battery {battery_id} killed"}
    return {"error": "Invalid battery ID"}


@app.post("/revive/{battery_id}")
def revive_battery(battery_id: int):
    """Bring a dead battery back online."""
    if 0 <= battery_id < NUM_BATTERIES:
        batteries[battery_id]["status"] = "idle"
        return {"message": f"Battery {battery_id} revived"}
    return {"error": "Invalid battery ID"}


@app.post("/price-spike")
def trigger_price_spike():
    """Spike ERCOT price to $2/kWh. Watch batteries rush to sell."""
    global ercot_price
    ercot_price = 2.0
    return {"message": "Price spiked to $2.00/kWh", "ercot_price": ercot_price}


@app.post("/price-normal")
def reset_price():
    """Reset ERCOT price back to normal."""
    global ercot_price
    ercot_price = 0.03
    return {"message": "Price reset to $0.03/kWh", "ercot_price": ercot_price}


@app.post("/heatwave")
def trigger_heatwave():
    """Crank utility stress to critical. CoServe needs help NOW."""
    global utility_stress
    utility_stress = 0.95
    return {"message": "Heatwave triggered, utility stress critical", "utility_stress": utility_stress}


@app.post("/heatwave-off")
def end_heatwave():
    """End the heatwave. Utility stress drops back to normal."""
    global utility_stress
    utility_stress = 0.2
    return {"message": "Heatwave ended", "utility_stress": utility_stress}


@app.get("/state")
def get_state():
    """Get current simulation state (for debugging)."""
    return {
        "batteries": batteries,
        "ercot_price": round(ercot_price, 4),
        "utility_stress": round(utility_stress, 4),
        "fleet_soc": round(sum(b["soc"] for b in batteries if b["status"] != "offline") / max(1, sum(1 for b in batteries if b["status"] != "offline")), 4),
        "active_nodes": sum(1 for b in batteries if b["status"] != "offline"),
        "total_nodes": NUM_BATTERIES,
    }
