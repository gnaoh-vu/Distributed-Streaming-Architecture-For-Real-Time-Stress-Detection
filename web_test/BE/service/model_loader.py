import torch

from web_test.BE.config import MODEL_PATH

from models import SupervisedFullAdarpModel

def load_model():
    model = SupervisedFullAdarpModel()
    model.load_state_dict(torch.load(MODEL_PATH,weights_only=True))
    model.eval()
    return model

ai_model = load_model()
