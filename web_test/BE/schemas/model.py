from pydantic import BaseModel
from typing import Optional, List

from web_test.BE.config import TEST_PATIENT

class SensorSignal(BaseModel):
    timestamp: float
    eda: float
    hr: Optional[int] = None
    acc: Optional[float] = None
    bvp: Optional[float] = None
    ibi: Optional[float] = None
    temp: Optional[float] = None

class PredictionResult(BaseModel):
    is_stress: bool
    confidence: float

class RealtimePayload(BaseModel):   
    patient_id: str
    timestamp: float
    metrics: SensorSignal
    prediction: PredictionResult

class TestContent(BaseModel):
    patient_path: str = TEST_PATIENT

class SignalSample(BaseModel):
    data: List[float]


#Combined With Others
class SignalResponse(BaseModel):
    x: List[float]
    y: List[float]
    timestamps: List[float]
    
class PredictResponse(BaseModel):
    label: int


    