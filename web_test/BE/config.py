import os

from models.constants import ADARP_SENSOR_DATA_PATH

SENSOR_PATH = os.getenv("SENSOR_PATH", ADARP_SENSOR_DATA_PATH)
TEST_PATIENT = "Part 102C/A01b41_190603-165328"

WINDOW_SIZE = 60
OVERLAP_RATIO = 0.5
MODEL_PATH = os.getenv("MODEL_PATH", "./models/baseline/best_model.pt")