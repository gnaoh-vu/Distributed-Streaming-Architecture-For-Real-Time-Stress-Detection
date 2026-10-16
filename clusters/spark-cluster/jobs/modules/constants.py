FREQ = {
    'ACC': 32,
    'BVP': 64,
    'TEMP': 4,
    'EDA': 4,
    'HR': 1
}

THRESHOLD = 0.45
VALID_HRV_TIME = 200

STRESSED_BUFFER = 15 * 60
ROI = 60 * 60

WINDOW_LENGTH = 5 * 60
OVERLAP_RATIO = 0.5

MODEL_SAVING_PATH = './saved_states'

WESAD_SENSOR_DATA_PATH = 'hdfs:///shared/WESAD'
ADARP_SENSOR_DATA_PATH = 'hdfs:///shared/ADARP/Sensor Data'
