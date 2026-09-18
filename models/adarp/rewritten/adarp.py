import os
import csv

import numpy as np
from enum import StrEnum
from scipy.signal import butter, filtfilt, lfilter

class SignalType(StrEnum):
    TEMP = 'TEMP'
    ACC = 'ACC'
    BVP = 'BVP'
    EDA = 'EDA'
    HR = 'HR'

class Signal():
    def __init__(self, start_time, freq, data: list, s_type: SignalType):
        self.data = np.asarray(data, dtype=np.float32)
        self.start_time = start_time
        self.s_type = s_type
        self.freq = freq

    @property
    def end_time(self):
        return self.start_time + (len(self.data) / self.freq)  

SENSOR_DATA_PATH = '../ADARP/Sensor Data'
PARTICIPANTS = [
    'Part 101C',
    'Part 102C',
    'Part 104C',
    'Part 105C',
    'Part 106C',
    'Part 107C',
    'Part 108C',
    'Part 109C',
    'Part 110C',
    'Part 111C',
    'Part 112C',
]

FREQ = {
    'ACC': 32,
    'BVP': 64,
    'TEMP': 4,
    'EDA': 4,
    'HR': 1
}

STRESSED_BUFFER = 60 * 60

OVERLAP_RATIO = 0.5
WINDOW_LENGTH = 60

def read_signal_data(s_type: SignalType, path: str) -> Signal:
    data = []

    with open(os.path.join(path, f'{str(s_type)}.csv')) as file:
        reader = csv.reader(file)
        for row in reader: data.extend([float(e) for e in row])

    return Signal(data[0], data[1], data[2:], s_type)

def read_tag_timestamps(path: str):
    timestamps = []

    with open(os.path.join(path, 'tags.csv')) as tags_file:
        reader = csv.reader(tags_file)
        for row in reader: timestamps.extend([float(e) for e in row])

    return timestamps

def get_segments_around_tags(signal: Signal, timestamps: list) -> list[Signal]:
    n_obs = int(STRESSED_BUFFER * signal.freq)
    segments = []

    for timestamp in timestamps:
        if (timestamp > signal.start_time and timestamp < signal.end_time):
            diff = int(timestamp - signal.start_time)
            index = int(diff * signal.freq)

            if (index - n_obs < 0 or index + n_obs > len(signal.data)): 
                continue

            segments.append(Signal(
                signal.start_time,
                signal.freq,
                signal.data[index - n_obs : index + n_obs],
                signal.s_type,
            ))

    return segments

def get_segments_outside_tags(signal: Signal, timestamps: list) -> list[Signal]:
    n_obs = int(STRESSED_BUFFER * signal.freq)
    indices = [0, len(signal.data) - 1]
    segments = []

    for timestamp in timestamps:
        diff = int(timestamp - signal.start_time)
        index = int(diff * signal.freq)
        r_bound =  index + n_obs
        l_bound =  index - n_obs
        indices.insert(-1, l_bound)
        indices.insert(-1, r_bound)

    for i in range(0, len(indices), 2):
        if (indices[i] < indices[i + 1]):
            segments.append(Signal(
                signal.start_time,
                signal.freq,
                signal.data[indices[i] : indices[i + 1]],
                signal.s_type
            ))

    return segments

def get_segments(
        include_signal_types: list[SignalType], is_stress=True, 
        from_patient=0, to_patient=len(PARTICIPANTS)
) -> tuple[
        dict[str, dict[str, list[Signal]]],     
        dict[str, list[Signal]]
]:
    if len(include_signal_types) == 0:
        print('No signals were included')
        return

    participants_signals = {p: {} for p in PARTICIPANTS}
    all_signals = { 'HR': [], 'EDA': [], 'BVP': [], 'ACC': [], 'TEMP': [] }
    f = get_segments_around_tags if is_stress else get_segments_outside_tags

    for p in PARTICIPANTS[from_patient:to_patient]:
        p_invalid = 0
        p_folder = os.path.join(SENSOR_DATA_PATH, p)
        p_segments = { 'HR': [], 'EDA': [], 'BVP': [], 'ACC': [], 'TEMP': [] }

        for folder in os.listdir(p_folder):
            data_folder = os.path.join(p_folder, folder)
            timestamps = read_tag_timestamps(data_folder)

            for s_type in include_signal_types:
                signal = read_signal_data(s_type, data_folder)
                segments = f(signal, timestamps)

                if len(segments): 
                    p_segments[str(s_type)].extend(segments)

        if (SignalType.EDA in include_signal_types):
            for s in p_segments['EDA']:
                min_max_scaler(s)
                butter_lpf(
                    s, 
                    order=4, 
                    fs=FREQ[str(SignalType.EDA)], 
                    cutoff=5/FREQ[str(SignalType.EDA)]
                )

        participants_signals[p] = p_segments
        for k, v in p_segments.items(): all_signals[k].extend(v)

    return participants_signals, all_signals

def extract_windows_from_segment(segment: Signal) -> list[Signal]:
    window_size = FREQ[str(segment.s_type)] * WINDOW_LENGTH
    offset = int(window_size * (1 - OVERLAP_RATIO))
    windows = []

    for i in range(0, len(segment.data), offset):
        data = segment.data[i : i + window_size]
        if (len(data) == window_size): 
            windows.append(Signal(
                segment.start_time,
                segment.freq,
                data, 
                segment.s_type
            ))

    return windows

def extract_windows_from_signal(segments: list[Signal]):
    all_windows = []

    for segment in segments:
        windows = extract_windows_from_segment(segment)
        all_windows.extend(windows)

    return all_windows

def min_max_scaler(segment: Signal):
  segment.data = segment.data - (np.min(segment.data))
  segment.data /= np.max(segment.data)

def butter_lpf(segment: Signal, order, fs, cutoff):
    b, a = butter(order, cutoff, btype='lowpass', fs=fs)
    filtered = lfilter(b, a, segment.data)
    segment.data = filtered

# participants_signals = get_segments([SignalType.EDA], is_stress=False)
# signal = participants_signals[PARTICIPANTS[0]]['EDA']
# print(signal[0].data)
