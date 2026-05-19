from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class DriverInfo(BaseModel):
    driver_id: str = Field(..., description="Unique driver identifier (e.g., 'VER', 'HAM')")
    team: str = Field(..., description="Constructor team name")

class TelemetryFrame(BaseModel):
    timestamp: datetime = Field(..., description="Exact time of the telemetry reading")
    driver_id: str = Field(..., description="Link to the driver")
    session_id: str = Field(..., description="Identifier for the race/session")
    
    # Core Car Physics
    speed: float = Field(..., description="Speed in km/h")
    rpm: int = Field(..., description="Engine RPM")
    gear: int = Field(..., description="Current gear")
    throttle: float = Field(..., description="Throttle pressure percentage 0-100")
    brake: float = Field(..., description="Brake pressure percentage or binary flag depending on data source")
    
    # Steering & Handling (Crucial for Stress Inference)
    steering_angle: float = Field(default=0.0, description="Steering wheel angle")
    drs: int = Field(default=0, description="DRS Activation status (0-14 codes in FastF1)")
    
    # Location
    x: float = Field(..., description="X coordinate on track map")
    y: float = Field(..., description="Y coordinate on track map")
    z: float = Field(..., description="Z coordinate on track map")
    
    status: str = Field(default="OnTrack", description="Track status")

class RaceEvent(BaseModel):
    timestamp: datetime
    event_type: str = Field(..., description="Type of event (Lap complete, Incident, Pit, etc.)")
    driver_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
