from pydantic import BaseModel

class SensorSignal(BaseModel):
    timestamp: float
    eda: float
    hr: int
    acc: float
    bvp: float
    ibi: float
    temp: float

class PredictionResult(BaseModel):
    is_stress: bool
    confidence: float

class RealtimePayload(BaseModel):   
    patient_id: str
    timestamp: float
    metrics: SensorSignal
    prediction: PredictionResult

    