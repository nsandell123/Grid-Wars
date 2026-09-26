import asyncio
import json
import random
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
        "soc": round(random.uniform(0.5, 1.0), 2),
        "max_rate": 5.0,
        "capacity": 13.5,
        "status": "idle",
        "target": None,
    }


# --- Global Simulation State ---

NUM_BATTERIES = 20
HOMEOWNER_RESERVE = 0.20
TICK_INTERVAL = 1.0

batteries = [create_battery(i) for i in range(NUM_BATTERIES)]
ercot_price = 0.03
utility_stress = 0.2
simulation_running = True
connected_clients: list[WebSocket] = []

# Revenue tracking
total_market_revenue = 0.0
total_utility_revenue = 0.0
UTILITY_RATE = 0.50

# Price history (for the chart)
price_history: list[dict] = []
MAX_PRICE_HISTORY = 120  # last 2 minutes of ticks

# Order book
order_book: list[dict] = []
executed_trades: list[dict] = []
MAX_TRADES = 50
next_order_id = 1


# --- Smart Optimizer ---

def optimize_dispatch(batteries: list[dict], ercot_price: float, utility_stress: float) -> list[dict]:
    RESERVE_FLOOR = 0.20
    DEGRADATION_THRESHOLD_PRICE = 0.08
    PRICE_SPIKE_THRESHOLD = 0.50
    MAX_UTILITY_RELIEF_KW = 25.0

    if utility_stress > 0.7:
        stress_factor = (utility_stress - 0.7) / 0.3
        target_utility_kw = 15.0 + (stress_factor * (MAX_UTILITY_RELIEF_KW - 15.0))
    else:
        target_utility_kw = 0.0

    current_utility_allocated_kw = 0.0
    decisions = []

    sorted_batteries = sorted(
        [b for b in batteries if b["status"] != "offline"],
        key=lambda b: b["soc"],
        reverse=True,
    )

    for b in batteries:
        if b["status"] == "offline":
            decisions.append({"id": b["id"], "action": "offline", "rate": 0, "target": None})

    for b in sorted_batteries:
        soc = b["soc"]
        max_rate = b["max_rate"]
        usable_soc = max(0.0, soc - RESERVE_FLOOR)

        if usable_soc <= 0.001:
            decisions.append({"id": b["id"], "action": "idle", "rate": 0.0, "target": None})
            continue

        soc_scale = min(1.0, usable_soc / 0.15)

        if current_utility_allocated_kw < target_utility_kw:
            needed_kw = target_utility_kw - current_utility_allocated_kw
            dispatch_rate = round(min(max_rate * soc_scale, needed_kw, max_rate), 2)
            if dispatch_rate > 0.1:
                decisions.append({"id": b["id"], "action": "discharge", "rate": dispatch_rate, "target": "utility"})
                current_utility_allocated_kw += dispatch_rate
                continue

        if ercot_price >= DEGRADATION_THRESHOLD_PRICE:
            if ercot_price >= PRICE_SPIKE_THRESHOLD:
                market_rate = round(max_rate * soc_scale, 2)
            else:
                price_factor = (ercot_price - DEGRADATION_THRESHOLD_PRICE) / (PRICE_SPIKE_THRESHOLD - DEGRADATION_THRESHOLD_PRICE)
                market_rate = round(max_rate * soc_scale * price_factor, 2)
            if market_rate > 0.1:
                decisions.append({"id": b["id"], "action": "discharge", "rate": market_rate, "target": "market"})
                continue

        decisions.append({"id": b["id"], "action": "idle", "rate": 0.0, "target": None})

    decisions.sort(key=lambda d: d["id"])
    return decisions


# --- Order Book Logic ---

def process_limit_orders():
    """Check if any limit orders should execute at current price."""
    global next_order_id
    filled = []
    for order in order_book:
        if order["status"] != "open":
            continue
        if order["side"] == "sell" and ercot_price >= order["price"]:
            order["status"] = "filled"
            order["filled_price"] = ercot_price
            order["filled_at"] = time.time()
            executed_trades.append({
                "id": order["id"],
                "side": "sell",
                "kw": order["kw"],
                "limit_price": order["price"],
                "filled_price": ercot_price,
                "revenue": order["kw"] * ercot_price * (TICK_INTERVAL / 3600),
                "time": time.time(),
            })
            filled.append(order)
        elif order["side"] == "buy" and ercot_price <= order["price"]:
            order["status"] = "filled"
            order["filled_price"] = ercot_price
            order["filled_at"] = time.time()
            executed_trades.append({
                "id": order["id"],
                "side": "buy",
                "kw": order["kw"],
                "limit_price": order["price"],
                "filled_price": ercot_price,
                "cost": order["kw"] * ercot_price * (TICK_INTERVAL / 3600),
                "time": time.time(),
            })
            filled.append(order)

    # Keep trades list trimmed
    while len(executed_trades) > MAX_TRADES:
        executed_trades.pop(0)


# --- Simulation Loop ---

async def simulation_loop():
    global ercot_price, utility_stress
    global total_market_revenue, total_utility_revenue

    while simulation_running:
        ercot_price = max(0.01, ercot_price + random.uniform(-0.005, 0.005))
        utility_stress = max(0.0, min(1.0, utility_stress + random.uniform(-0.02, 0.02)))

        # Track price history
        price_history.append({
            "price": round(ercot_price, 4),
            "stress": round(utility_stress, 4),
            "time": time.time(),
        })
        while len(price_history) > MAX_PRICE_HISTORY:
            price_history.pop(0)

        # Process limit orders
        process_limit_orders()

        decisions = optimize_dispatch(batteries, ercot_price, utility_stress)

        tick_market_revenue = 0.0
        tick_utility_revenue = 0.0

        for decision in decisions:
            b = batteries[decision["id"]]
            if decision["action"] == "offline":
                continue

            b["status"] = decision["action"]
            b["target"] = decision["target"]

            if decision["action"] == "discharge" and decision["rate"] > 0:
                energy_used = decision["rate"] * (TICK_INTERVAL / 3600)
                b["soc"] = max(HOMEOWNER_RESERVE, round(b["soc"] - energy_used / b["capacity"], 4))

                if decision["target"] == "market":
                    tick_market_revenue += decision["rate"] * ercot_price * (TICK_INTERVAL / 3600)
                elif decision["target"] == "utility":
                    tick_utility_revenue += decision["rate"] * UTILITY_RATE * (TICK_INTERVAL / 3600)

            elif decision["action"] == "charging":
                energy_added = b["max_rate"] * (TICK_INTERVAL / 3600)
                b["soc"] = min(1.0, round(b["soc"] + energy_added / b["capacity"], 4))

        total_market_revenue += tick_market_revenue
        total_utility_revenue += tick_utility_revenue

        market_count = sum(1 for d in decisions if d["target"] == "market")
        utility_count = sum(1 for d in decisions if d["target"] == "utility")
        idle_count = sum(1 for d in decisions if d["action"] == "idle")

        # Build open orders (bids and asks)
        open_sells = [o for o in order_book if o["status"] == "open" and o["side"] == "sell"]
        open_buys = [o for o in order_book if o["status"] == "open" and o["side"] == "buy"]

        # Auto-generated market bids (CoServe + ERCOT as buyers)
        auto_bids = []
        if utility_stress > 0.7:
            auto_bids.append({
                "source": "CoServe",
                "side": "buy",
                "price": round(UTILITY_RATE, 2),
                "kw": round(15.0 + ((utility_stress - 0.7) / 0.3) * 10.0, 1),
            })
        auto_bids.append({
            "source": "ERCOT",
            "side": "buy",
            "price": round(ercot_price, 4),
            "kw": 999,  # unlimited demand at market price
        })

        # Auto-generated asks (fleet's available capacity)
        total_available_kw = sum(
            min(b["max_rate"], max(0, b["soc"] - HOMEOWNER_RESERVE) * b["capacity"])
            for b in batteries if b["status"] != "offline"
        )
        auto_asks = [{
            "source": "Fleet",
            "side": "sell",
            "price": 0.08,  # degradation threshold
            "kw": round(total_available_kw, 1),
        }]

        state = {
            "batteries": batteries,
            "ercot_price": round(ercot_price, 4),
            "utility_stress": round(utility_stress, 4),
            "fleet_soc": round(sum(b["soc"] for b in batteries if b["status"] != "offline") / max(1, sum(1 for b in batteries if b["status"] != "offline")), 4),
            "active_nodes": sum(1 for b in batteries if b["status"] != "offline"),
            "total_nodes": NUM_BATTERIES,
            "market_revenue": round(total_market_revenue, 2),
            "utility_revenue": round(total_utility_revenue, 2),
            "total_revenue": round(total_market_revenue + total_utility_revenue, 2),
            "tick_revenue": round(tick_market_revenue + tick_utility_revenue, 4),
            "market_count": market_count,
            "utility_count": utility_count,
            "idle_count": idle_count,
            "price_history": price_history,
            "order_book": {
                "bids": auto_bids + [{"source": "User", "side": "buy", "price": o["price"], "kw": o["kw"], "id": o["id"]} for o in open_buys],
                "asks": auto_asks + [{"source": "User", "side": "sell", "price": o["price"], "kw": o["kw"], "id": o["id"]} for o in open_sells],
            },
            "recent_trades": executed_trades[-10:],
        }

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
            await ws.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(ws)


# --- Chaos Endpoints ---

@app.post("/kill/{battery_id}")
def kill_battery(battery_id: int):
    if 0 <= battery_id < NUM_BATTERIES:
        batteries[battery_id]["status"] = "offline"
        batteries[battery_id]["target"] = None
        return {"message": f"Battery {battery_id} killed"}
    return {"error": "Invalid battery ID"}


@app.post("/revive/{battery_id}")
def revive_battery(battery_id: int):
    if 0 <= battery_id < NUM_BATTERIES:
        batteries[battery_id]["status"] = "idle"
        return {"message": f"Battery {battery_id} revived"}
    return {"error": "Invalid battery ID"}


@app.post("/price-spike")
def trigger_price_spike():
    global ercot_price
    ercot_price = 2.0
    return {"message": "Price spiked to $2.00/kWh"}


@app.post("/price-normal")
def reset_price():
    global ercot_price
    ercot_price = 0.03
    return {"message": "Price reset to $0.03/kWh"}


@app.post("/heatwave")
def trigger_heatwave():
    global utility_stress
    utility_stress = 0.95
    return {"message": "Heatwave triggered"}


@app.post("/heatwave-off")
def end_heatwave():
    global utility_stress
    utility_stress = 0.2
    return {"message": "Heatwave ended"}


@app.post("/reset-revenue")
def reset_revenue():
    global total_market_revenue, total_utility_revenue
    total_market_revenue = 0.0
    total_utility_revenue = 0.0
    return {"message": "Revenue counters reset"}


# --- Trading Endpoints ---

class LimitOrder(BaseModel):
    side: str       # "buy" or "sell"
    price: float    # trigger price
    kw: float       # how much power

@app.post("/order")
def place_order(order: LimitOrder):
    global next_order_id
    new_order = {
        "id": next_order_id,
        "side": order.side,
        "price": order.price,
        "kw": order.kw,
        "status": "open",
        "created_at": time.time(),
    }
    order_book.append(new_order)
    next_order_id += 1
    return {"message": f"Order #{new_order['id']} placed", "order": new_order}


@app.post("/order/{order_id}/cancel")
def cancel_order(order_id: int):
    for order in order_book:
        if order["id"] == order_id and order["status"] == "open":
            order["status"] = "cancelled"
            return {"message": f"Order #{order_id} cancelled"}
    return {"error": "Order not found or already filled"}


@app.get("/orders")
def get_orders():
    return {
        "open": [o for o in order_book if o["status"] == "open"],
        "filled": [o for o in order_book if o["status"] == "filled"],
        "recent_trades": executed_trades[-10:],
    }


@app.get("/state")
def get_state():
    return {
        "batteries": batteries,
        "ercot_price": round(ercot_price, 4),
        "utility_stress": round(utility_stress, 4),
        "fleet_soc": round(sum(b["soc"] for b in batteries if b["status"] != "offline") / max(1, sum(1 for b in batteries if b["status"] != "offline")), 4),
        "active_nodes": sum(1 for b in batteries if b["status"] != "offline"),
        "total_nodes": NUM_BATTERIES,
        "market_revenue": round(total_market_revenue, 2),
        "utility_revenue": round(total_utility_revenue, 2),
        "total_revenue": round(total_market_revenue + total_utility_revenue, 2),
    }
