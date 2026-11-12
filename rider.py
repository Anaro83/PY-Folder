from datetime import datetime
import math
class Rider:
    def __init__(self, rd_id="AA253RD", name="Vinc Taira", profile_picture: str = "default.jpg", lat: float = 0.0, lon: float = 0.0):
        self.lat = lat #rider's latitude coordinate
        self.lon = lon #rider's longitude coordinate
        self.name = name
        self.rd_id = rd_id
        self.profile_picture = profile_picture
        self.active = False
        self.activities = []  # List to store activities related to the rider
    def calculate_distance(self, client_lat: float, client_lon: float) -> float:
        """Calculate the distance between the rider and a client using the Haversine formula."""
        # Convert latitude and longitude from degrees to kilometers
        return math.sqrt((self.lat - client_lat) ** 2 + (self.lon - client_lon) ** 2) * 111  # Approximate conversion factor from degrees to kilometers
 

    def status(self):
        return f"Rider ID: {self.rd_id}, Name: {self.name}, Active: {self.active}"
    def reseive_order(self, order_id: str, client_location: str):
        """notifies the rider of a new hunging nearer order"""
        self.pending_order = order_id
        self.client_location = client_location
        self.log_activity(f"Notified of order {order_id} from {client_location}")
        
    def accept_order(self):
        """Allows the rider to accept the pending order """
        if not hasattr(self, 'pending_order_id') or not hasattr(self, 'client_location'):
            return {"error": "No pending order to accept."}
        
        self.current_order_id = self.pending_order_id
        self.pending_order_id = None  # Clear the pending order
        self.log_activity(f"Accepted order {self.current_order_id} from {self.client_location}")
        return { "success": True, "message": f"Order {self.current_order_id} accepted.", "status": self.status()}

    
    def log_activity(self, activity = str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "activity": activity, 
            "timestamp": timestamp,
            "status": "Active" if self.active else "Inactive"
            }
        self.activities.append(entry)
    def get_profile(self):
        return{
            "profile_picture": self.profile_picture,
            "rd_id": self.rd_id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "active": self.active,
            "activities": self.activities
        }
class client:
    def __init__(self, location="Katoloni", lat: float = 0.0, lon: float = 0.0):
        self.location = location #[span_2](start span)[span_2](end span)
        self.executable_order = False #[span_3](start span) [span_3](end span)
        self.assigned_rider = None
        self.current_order_id = None

    def status(self): #[span_4](start span) [span_4](end span)
        rider_info = f"Assigned Rider: {self.assigned_rider.name} ({self.assigned_rider.rd_id})" if self.assigned_rider else "No Rider Assigned"
        return F"Client Location: {self.location}, Order done: {self.executable_order}, {rider_info}" #[span_5](start span)[span_5](end span)
    
    def assign_order_to_rider(self, rider:Rider, order_id: str):
        """Assign an order to a rider and log the activity"""
        if not rider.active:
            return {"error": "Rider is not active and cannot be assigned to an order."}
        self.assigned_rider = rider
        self.current_order_id = order_id
        self.executable_order = True
    
    #log in the assigned rider history
        rider.log_activity(f"Assigned to client order {order_id} from {self.location}")
    
    def complete_delivery(self, success: bool):
        """Finalize the order, recording success or cancellation on the assigned order"""
        if not self.assigned_rider or not self.current_order_id:
            return{"error":"No active order or rider assigned."}
        outcome = "completed successfully" if success else "cancelled"
        action_msg = f"Order {self.current_order_id} {outcome} for client at {self.location}"
        self.assigned_rider.log_activity(action_msg)
        #Reset client state
        completed_rider = self.assigned_rider
        self.assigned_rider = None
        self.current_order_id = None
        self.executable_order = False
        
        return {
            "message": f"Order {self.current_order_id} {outcome}.",
            "rider_status": completed_rider.status(),
        }
    