from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from rider import Rider
from pydantic import BaseModel
import asyncio

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Order_db = {}  # Simulated database for orders
Rider_database = {}  # Simulated database for riders
# Pydantic model to determine the data type of the rider object
class RiderCreate(BaseModel):
    rd_id: str
    name: str
    lat: float
    lon: float
#Pydantic model for the client's order request
class OrderRequest(BaseModel):
    clients_lat: float
    clients_lon: float
    order_id: str

@app.post("/riders/register")
def register_rider(rider: RiderCreate):
    Key = (rider.rd_id, rider.name)
    if Key in Rider_database:
        return {"message": "Rider already exists."}
    
    new_rider = Rider(rd_id=rider.rd_id, name=rider.name, lat=rider.lat, lon=rider.lon)
    Rider_database[Key] = new_rider # Store the new rider in the simulated database
    return {"message": "Rider registered successfully.", "status": new_rider.status()}
 
@app.post("/riders/activate")
def activate_rider(rider_data: RiderCreate):
    Key = (rider_data.rd_id, rider_data.name)
    if Key not in Rider_database:
        raise HTTPException(status_code=404, detail="Rider not found.")
    rider = Rider_database[Key]
    rider.active = True
    return {"message": "Rider activated successfully.", "status": rider.status()}

@app.post("/riders/deactivate")
def deactivate_rider(rider_data: RiderCreate):
    Key = (rider_data.rd_id, rider_data.name)
    if Key not in Rider_database:
        raise HTTPException(status_code=404, detail="Rider not found.")
    rider = Rider_database[Key]
    rider.active = False
    return {"message": "Rider deactivated successfully.", "status": rider.status()}

@app.post("/riders/log_activity")
def get_rider_activity(rider_data: RiderCreate):
    Key = (rider_data.rd_id, rider_data.name)
    if Key not in Rider_database:
        raise HTTPException(status_code=404, detail="Rider not found.")
    rider = Rider_database[Key]
    return {"activities": rider.activities}

@app.post("/riders/profile")
def get_rider_profile(rider_data: RiderCreate):
    Key = (rider_data.rd_id, rider_data.name)
    if Key not in Rider_database:
        raise HTTPException(status_code=404, detail="Rider not found.")
    rider = Rider_database[Key]
    return {"profile": rider.get_profile()}

@app.post("/clients/request_order")
#filter the active riders and find the nearest one to the client
def request_order(order_request: OrderRequest):
    active_riders = [rider for rider in Rider_database.values() if rider.active]
    if not active_riders:
        raise HTTPException(status_code=404, detail="No active riders available.")
    nearest_rider = min(active_riders, key=lambda r: r.calculate_distance(order_request.clients_lat, order_request.clients_lon))
    nearest_rider.log_activity(f"Received order request {order_request.order_id} from client at ({order_request.clients_lat}, {order_request.clients_lon})")
    return {"message": f"Order request {order_request.order_id} sent to nearest rider {nearest_rider.name} ({nearest_rider.rd_id}).", "rider_status": nearest_rider.status()}

@app.post("/riders/nearest")
def get_nearest_rider(client_lat: float, client_lon: float):
    active_riders = [rider for rider in Rider_database.values() if rider.active]
    if not active_riders:
        raise HTTPException(status_code=404, detail="No active riders available.")
    nearest_rider = min(active_riders, key=lambda r: r.calculate_distance(client_lat, client_lon))
    active_riders.sort(key=lambda r: r.calculate_distance(client_lat, client_lon))
    return {"nearest_rider": nearest_rider.status(), "distance_km": round(distance := nearest_rider.calculate_distance(client_lat, client_lon), 2)}

async def handle_order_timeout(rider: Rider, order_id: str, timeout: int = 30):
    await asyncio.sleep(timeout)
    order= Order_db.get(order_id)
    if not order or order["status"] != "pending":
        return  # Order has already been accepted or completed
    rider= Rider_database.get(nearest_rider_key := (rider.rd_id, rider.name))
    if rider and getattr(rider, 'pending_order_id', None) == order_id:
        print(f"Timeout reached for rider {rider.name}. Passing order automatically to the next nearest rider.")
        rider.pass_order(order_id)
        
    await dispatch_next(order_id, rider, timeout)
    
async def dispatch_next(order_id: str, current_rider: Rider, timeout: int = 30):
    """pick the next nearest rider and send the order to them"""
    order = Order_db.get(order_id)
    if not order :
        return
    
    candidates= order["candidates"]
    index= order["current_index"]
    #look for the next nearest active rider in the candidates list
    while index < len(candidates):
        next_rider_key = candidates[index]
        next_rider = Rider_database.get(next_rider_key)
        if next_rider and next_rider.active:
            order["current_index"] = index
            next_rider.log_activity(f"Received order request {order_id} from client at ({order['clients_lat']}, {order['clients_lon']})")
            print(f"Order {order_id} sent to next nearest rider {next_rider.name} ({next_rider.rd_id}).")
            await handle_order_timeout(next_rider, order_id, timeout)
            return
        index += 1
        #if we run out of riders
        order["status"] = "no more riders available"
        print(f"Order {order_id}: All nearby riders passed or are available")
        
@app.post("/clients/request_order")
async def request_order(order_data: OrderRequest, background_tasks: BackgroundTasks):
    #Guther and sort all active riders by distance to the client
    active_riders=[]
    for key, rider in Rider_database.items():
        if rider.active and not rider.current_order_id:
            distance= rider.calculate_distance(order_data.clients_lat, order_data.clients_lon)
            active_riders.append((distance, key))
            
        if not active_riders:
            raise HTTPException(status_code=404, detail="No active riders available.")
        
        #Sort accending[nearest first] by distance
        active_riders.sort(key=lambda x: x[0])
        candidate_keys= [rider_key for _, rider_key in active_riders]
        #Store the order in the simulated database
        Order_db[order_data.order_id] = {
            "clients_lat": order_data.clients_lat,
            "clients_lon": order_data.clients_lon,
            "candidates": candidate_keys,
            "current_index": 0,
            "status": "pending",
            "assigned_rider": None
        }
        
        #Dispatch the order to the absolute nearest rider
        await dispatch_next(order_data.order_id)
        
        first_rider_key= Order_db[order_data.order_id]["assigned_rider"]
        assigned_rider_obj = Rider_database[first_rider_key]
        return{
            "status": "Order request sent to nearest rider.",
            "message": F"Order broadcasted.offered to nearest rider {assigned_rider_obj.name} ({assigned_rider_obj.rd_id}).",
            "rider_status": assigned_rider_obj.status()
        }

@app.post("/riders/pass_order")
async def pass_order(rider_data: RiderCreate):
    """Endpoint trigered when a rider clicks the pass button to pass the order to the next nearest rider"""
    Key = (rider_data.rd_id, rider_data.name)
    if Key not in Rider_database:
        raise HTTPException(status_code=404, detail="Rider not found.")
    rider = Rider_database[Key]
    pending_order = getattr(rider, 'pending_order_id', None)
    
    success, message = rider.pass_order(pending_order)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    #if there was a pending order immediately cascade to the nearest rider
    if pending_order and pending_order in Order_db:
        await dispatch_next(pending_order)
        return{
            "message":"Successfuly passed order. Offer forwaded to next rider.",
            "status": rider.status()
               }

@app.post("/riders/accept_order")
async def accept_order(rider_data: RiderCreate):
    """Endpoint trigers when rider clicks 'accept' button"""
    Key=(rider_data.rd_id, rider_data.name)
    if Key not in Rider_database:
        raise HTTPException(status_code=404, detail="Rider not found")
    
    rider = Rider_database[Key]
    pending_id = getattr(rider, 'pending_order', None)
    
    #lock in the order
    rider.current_order_id=pending_id,
    rider.pending_order_id=None,
    rider.log_activity(f"Accepted order", {pending_id})
    
    #Update global order trackingif it exist
    if pending_id in Order_db:
        Order_db[pending_id]["status"] = "Accepted"
        Order_db[pending_id]["assigned rider"] = Key
        return{
            "message":f"Order {pending_id} accepted succesfully",
            "status" :rider.status()
        }
        
@app.post("/riders/complete/delivery")
async def complete_delivery(rider_data: RiderCreate, success: bool=True):
     """Endpoint for a rider to mark his delivery as a comple"""
     Key = (rider_data.rd_id, rider_data.name)
     
     rider = Rider_database[Key]
     active_id = getattr(rider, "current_order_id", None)

     status_str = "Completed successfuly"
     rider.log_activity(f"Order {active_id} {status_str}")
    #Free the rider for future orders
     rider.current_order_id = None
     if active_id in Order_db:
        Order_db[active_id]["status"] = status_str
    
     return {
        "message":f"Order {active_id} {status_str}.",
        "status" :rider.status()
    }
     
class AdminOverideRequest(BaseModel):
    rd_id: str
    name :str
    reason: str = "Admin manual override"
    
@app.get("/admin/riders")
def admin_get_riders():
    riders_list=[]
    for Key, rider in Rider_database.items():
        riders_list.append({
            "rd_id":rider.rd_id,
            "name":rider.name,
            "active":rider.active,
            "lat":rider.lat,
            "lon":rider.lon,
            "current_order_id":getattr(rider, "current_order_id", None),
            "pending_order_id":getattr(rider, "pending_order_id", None),
            "status":rider.status(),
            "history_count": len(rider.history)        
        })
    return{
        "total_riders":len(riders_list),
        "riders": riders_list
    }
        
@app.get("/admin/orders")
def admin_get_orders():
    return{
        "total_orders": len(Order_db),
        "orders": Order_db
    }
    
@app.post("/admin/override/clear_rider_order")
def admin_override(data: AdminOverideRequest):
    Key = (data.rd_id, data.name)
    if Key not in Rider_database:
        raise HTTPException(status_code=404 , detail="Rider not found")
    
    rider = Rider_database[Key]
    stuck_order = getattr(rider, "current_order_id", None) or getattr(rider, "pending_order_id", None)
    
    if not stuck_order:
        raise HTTPException(status_code=400, detail="No stucked order")
    
    #clear out the order state
    rider.current_order_id = None
    rider.pending_order_id = None
    rider.log_activity(f"ADMIN OVERRIDE {stuck_order} reason {data.reason}")
    
    #update global order_db of present
    if stuck_order in Order_db:
        Order_db[stuck_order]["status"] = "force_cleared_by_admin"
        
        return{
            "status":"Success",
            "message" : f"Successfuly cleared order {stuck_order} from rider {rider.name}.",
            "rider_status" : rider.status()
        }