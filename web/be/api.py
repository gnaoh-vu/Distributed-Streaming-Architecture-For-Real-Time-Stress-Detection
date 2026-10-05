import os

import torch
import numpy as np

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from models import *
from models import SupervisedFullAdarpModel
from models.constants import ADARP_SENSOR_DATA_PATH

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],    
)

SENSOR_PATH = ADARP_SENSOR_DATA_PATH
TEST_PATIENT = 'Part 102C/A01b41_190603-165328'

WINDOW_SIZE = 60
OVERLAP_RATIO = 0.5
MODEL_PATH = './models/baseline/best_model.pt'

model = SupervisedFullAdarpModel()
model.load_state_dict(torch.load(MODEL_PATH, weights_only=True))
model.eval()

class TestContent(BaseModel):
    patient_path: str = TEST_PATIENT

class SignalSample(BaseModel):
    data: list

@app.post('/test')
def test_signal(content: TestContent):
    path = os.path.join(SENSOR_PATH, content.patient_path)
    signal = read_signal_data(SignalType.EDA, path)
    timestamps = read_tag_timestamps(path)
    min_max_scaler(signal)

    y = signal.data
    x = [signal.start_time]

    for i in range(1, len(y)):
        x.append(x[i-1] + 1/signal.freq)

    y = y[int(3600*5.65*signal.freq):]
    x = x[int(3600*5.65*signal.freq):]

    return {
        'x': x, 
        'y': y.tolist(),
        'timestamps': timestamps,
    }

@app.post('/test-predict')
def test_predict(sample: SignalSample):
    input = torch.tensor(sample.data).reshape(1, -1)
    logits = model(input)

    pred_y = torch.argmax(logits.softmax(dim=1), dim=1)
    return { 'label': pred_y.item() }

