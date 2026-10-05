import random
import torch
import torch.nn.functional as F

from models import *
from models import SupervisedFullAdarpModel

from .model_loader import ai_model
from ..schemas.model import *

from web_test.BE.config import WINDOW_SIZE


def predict_realtime(sample: SignalSample) -> PredictionResult:
    if isinstance(sample, SignalSample):
        data = sample.data
    elif isinstance(sample, list):
        data = sample
    else:
        raise ValueError(f"Kiểu dữ liệu không hợp lệ: {type(sample)}")

    
    if len(data) < WINDOW_SIZE:
        return PredictionResult(is_stress=False, confidence=0.0)

    input_tensors = torch.tensor(data[-WINDOW_SIZE:], dtype=torch.float32).reshape(1, -1)

    ai_model.eval()
    with torch.no_grad():
        logits = ai_model(input_tensors)

        probs = F.softmax(logits, dim=-1).squeeze(0)
        pred_label = torch.argmax(probs).item()

        is_stress = (pred_label == 1)
        conf = float(probs[pred_label].item())

        return PredictionResult(
            is_stress= is_stress,
            confidence = conf
        )



    







    