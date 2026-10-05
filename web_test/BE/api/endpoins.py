import torch
from fastapi import APIRouter

from web_test.BE.schemas.model import *
from web_test.BE.service.model_loader import ai_model
from web_test.BE.service.prediction import predict_realtime
from web_test.BE.service.read_data import load_eda_signal

router = APIRouter(prefix="/signal", tags=["Signal & Prediction"])

@router.post("/test", response_model=SignalResponse)
def test_signal(content: TestContent):
    return  load_eda_signal(content.patient_path)

@router.post("/test-predict", response_model=PredictResponse)
def test_predict(sample: SignalSample):
    input_tensor = torch.tensor(sample.data, dtype=torch.float32).reshape(1, -1)
    
    with torch.no_grad():
        logits = ai_model(input_tensor)
        pred_y = torch.argmax(logits.softmax(dim=1), dim=1)

    return {'label': pred_y.item()}