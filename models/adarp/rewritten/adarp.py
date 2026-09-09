import os
import csv
from enum import StrEnum

class SignalType(StrEnum):
    TEMP = 'TEMP'
    ACC = 'ACC'
    BVP = 'BVP'
    EDA = 'EDA'
    HR = 'HR'

class Signal():
    def __init__(self, start_time, freq, data: list, s_type: SignalType):
        self.start_time = start_time
        self.freq = freq
        self.data = data
        self.s_type = s_type

    @property
    def end_time(self):
        return self.start_time + (len(self.data) / self.freq)  

class Segment():
    def __init__(self, data: list, s_type: SignalType):
        self.data = data
        self.s_type = s_type

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
        # valid = next(reader, None)

        # if not valid: return []
        for row in reader: timestamps.extend([float(e) for e in row])

    return timestamps

def read_all_tag_timestamps(path: str) -> list:
    timestamps = []

    for subfolder in os.listdir(path):
        tags_path = os.path.join(path, subfolder, 'tags.csv')
        with open(tags_path, newline='') as tags_file:
            reader = csv.reader(tags_file)
            valid = next(reader, None)

            if not valid: continue
            for row in reader: timestamps.extend([float(e) for e in row])

    return timestamps

def get_segments_around_tags(signal: Signal, timestamps: list) -> list[Segment]:
    n_obs = int(STRESSED_BUFFER * signal.freq)
    segments = []

    for timestamp in timestamps:
        if (timestamp > signal.start_time and timestamp < signal.end_time):
            diff = int(timestamp - signal.start_time)
            index = int(diff * signal.freq)

            if (index - n_obs < 0 or index + n_obs > len(signal.data)): 
                continue

            segments.append(Segment(
                signal.data[index - n_obs : index + n_obs],
                signal.s_type,
            ))

    return segments

def get_segments_outside_tags(signal: Signal, timestamps: list) -> list[Segment]:
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
            segments.append(Segment(
                signal.data[indices[i] : indices[i + 1]],
                signal.s_type
            ))

    return segments

def get_stressed_segments(include_signal_types: list[SignalType])-> dict[str, dict[str, list[Segment]]]:
    if len(include_signal_types) == 0:
        print('No signals were included')
        return

    participants_signals = {p: {} for p in PARTICIPANTS}
    for p in PARTICIPANTS:
        p_invalid = 0
        p_folder = os.path.join(SENSOR_DATA_PATH, p)
        p_segments = { 'HR': [], 'EDA': [], 'BVP': [], 'ACC': [], 'TEMP': [] }

        for folder in os.listdir(p_folder):
            data_folder = os.path.join(p_folder, folder)
            timestamps = read_tag_timestamps(data_folder)

            for s_type in include_signal_types:
                signal = read_signal_data(s_type, data_folder)
                segments = get_segments_around_tags(signal, timestamps)
                if len(segments): p_segments[str(s_type)].extend(segments)

        participants_signals[p] = p_segments
    return participants_signals

def get_non_stressed_segments(include_signal_types: list[SignalType]) -> dict[str, dict[str, list[Segment]]]:
    if len(include_signal_types) == 0:
        print('No signals were included')
        return

    participants_signals = {p: {} for p in PARTICIPANTS}
    for p in PARTICIPANTS:
        p_folder = os.path.join(SENSOR_DATA_PATH, p)
        p_segments = { 'HR': [], 'EDA': [], 'BVP': [], 'ACC': [], 'TEMP': [] }

        for folder in os.listdir(p_folder):
            data_folder = os.path.join(p_folder, folder)
            timestamps = read_tag_timestamps(data_folder)

            for s_type in include_signal_types:
                signal = read_signal_data(s_type, data_folder)
                segments = get_segments_outside_tags(signal, timestamps)
                if len(segments): p_segments[str(s_type)].extend(segments)

        participants_signals[p] = p_segments
    return participants_signals

def extract_windows_from_segment(segment: Segment) -> list[Segment]:
    window_size = FREQ[str(segment.s_type)] * WINDOW_LENGTH
    offset = int(window_size * OVERLAP_RATIO)
    segments = []

    for i in range(0, len(segment.data), offset):
        data = segment.data[i : i + window_size]
        if (len(data) == window_size): 
            segments.append(Segment(data, segment.s_type))

    return segments

def extract_windows_from_signal(segments: list[Segment]):
    segments = []

    for segment in segments:
        windows = extract_windows_from_segment(segment)
        segments.extend(windows)

    return segments

# normalize
# nosie filter

participants_signals = get_stressed_segments([SignalType.EDA])
segment = participants_signals[PARTICIPANTS[0]]['EDA'][0]
windows = extract_windows_from_segment(segment)
print(len(windows))


# get_non_stressed_segments([SignalType.EDA])

# p_path = os.path.join(SENSOR_DATA_PATH, PARTICIPANTS[0])
# p_day_path = os.path.join(p_path, 'A01f4c_190430-161241')

# timestamps = read_all_tag_timestamps(p_path)
# eda_data = read_signal_data(SignalType.EDA, p_day_path)
# segments = get_segments_around_tags(eda_data, timestamps)

# count = 0
# for segment in segments:
    # count +=1
    # print(len(segment.data))

# print(count)

