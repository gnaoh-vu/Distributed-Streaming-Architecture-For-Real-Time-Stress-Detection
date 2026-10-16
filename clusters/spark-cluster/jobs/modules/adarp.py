import os
import csv

import numpy as np
from scipy.signal import butter, filtfilt, lfilter

from .constants import *
from .signal import *

def read_signal_data(s_type: SignalType, path: str) -> Signal:
    data = []

    with open(os.path.join(path, f'{str(s_type)}.csv')) as file:
        reader = csv.reader(file)
        for row in reader: data.extend([float(e) for e in row])

    return Signal(data[0], data[1], data[2:], s_type)

def read_ibi_data(path: str) -> list:
    data = []

    with open(os.path.join(path, 'IBI.csv')) as file:
        reader = csv.reader(file)

        try:
          initial_time = float(next(reader)[0])
          data.append(initial_time)

          for elapsed, ibi in reader:
            data.append(float(elapsed) + initial_time)

        except StopIteration:
          pass

    return data

def read_tag_timestamps(path: str):
    timestamps = []

    with open(os.path.join(path, 'tags.csv')) as tags_file:
        reader = csv.reader(tags_file)
        for row in reader: timestamps.extend([float(e) for e in row])

    return timestamps

def get_segments_around_tags(signal: Signal, timestamps: list, participant: str, folder: str) -> list[Segment]:
    n_obs = int(STRESSED_BUFFER * signal.freq)
    segments = []

    for timestamp in timestamps:
        if (timestamp > signal.start_time and timestamp < signal.end_time):
            diff = int(timestamp - signal.start_time)
            index = int(diff * signal.freq)

            if (index - n_obs < 0 or index + n_obs > len(signal.data)):
                continue

            segments.append(Segment(
                signal.start_time + int((index - n_obs) / signal.freq),
                signal.freq,
                signal.data[index - n_obs : index + n_obs],
                signal.s_type,
                participant=participant,
                folder=folder,
                is_stress=True,
                timestamp=timestamp
            ))

    return segments

def get_segments_outside_tags(signal: Signal, timestamps: list, participant: str, folder: str) -> list[Segment]:
    roi_obs = int(ROI * signal.freq)
    mask = np.zeros(len(signal.data), dtype=bool)

    for timestamp in timestamps:
        diff = int(timestamp - signal.start_time)
        index = int(diff * signal.freq)
        l_bound =  max(0, index - roi_obs)
        r_bound =  min(len(signal.data), index + roi_obs)
        mask[l_bound:r_bound] = True

    segments = []
    slices = np.ma.clump_unmasked(np.ma.masked_array(signal.data, mask=mask))

    for s in slices:
        if (s.stop - s.start) >= (WINDOW_LENGTH * signal.freq):
            segments.append(Segment(
                signal.start_time + int(s.start / signal.freq),
                signal.freq,
                signal.data[s.start : s.stop],
                signal.s_type,
                participant=participant,
                folder=folder,
                is_stress=False
            ))

    return segments

def get_segments(
        path:str, include_signal_types: list[SignalType], is_stress=True,
        from_patient=None, to_patient=None, left_out=[]
) -> tuple[
        dict[str, dict[str, list[Segment]]],
        dict[str, list[Segment]]
]:
    if len(include_signal_types) == 0:
        print('No signals were included')
        return

    participants = sorted(os.listdir(path))
    from_patient = 0 if from_patient is None else from_patient
    to_patient = len(participants) - 1 if to_patient is None else to_patient

    participants_signals = {p: {} for p in participants}
    all_signals = { 'HR': [], 'EDA': [], 'BVP': [], 'ACC': [], 'TEMP': [], 'IBI': [] }

    f = get_segments_around_tags if is_stress else get_segments_outside_tags

    for idx, p in enumerate(participants):
        if idx < from_patient or idx > to_patient or idx in left_out: continue

        p_folder = os.path.join(path, p)
        p_segments = { 'HR': [], 'EDA': [], 'BVP': [], 'ACC': [], 'TEMP': [], 'IBI': [] }

        for folder in os.listdir(p_folder):
            data_folder = os.path.join(p_folder, folder)
            if not os.path.isdir(data_folder): continue

            timestamps = read_tag_timestamps(data_folder)
            ibi = read_ibi_data(data_folder)
            is_valid = False

            for s_type in include_signal_types:
                signal = read_signal_data(s_type, data_folder)
                segments = f(signal, timestamps, p, folder)

                if len(segments):
                    p_segments[str(s_type)].append(segments)
                    is_valid = True

            if is_valid:
              p_segments['IBI'].append(ibi)

        if (SignalType.EDA in include_signal_types):
            for segments in p_segments['EDA']:
              for s in segments:
                  butter_lpf(
                      s,
                      order=2,
                      fs=FREQ[str(SignalType.EDA)],
                      cutoff=5/FREQ[str(SignalType.EDA)]
                  )
                  min_max_scaler(s)

        participants_signals[p] = p_segments
        for k, v in p_segments.items(): all_signals[k].extend(v)

    return participants_signals, all_signals

def extract_windows_from_segment(segment: Segment) -> list[Window]:
    window_size = FREQ[str(segment.s_type)] * WINDOW_LENGTH
    offset = int(window_size * (1 - OVERLAP_RATIO))
    windows = []

    for i in range(0, len(segment.data), offset):
        data = segment.data[i : i + window_size]
        if (len(data) == window_size):
            windows.append(Window(
                segment.start_time + int(i / segment.freq),
                segment.freq,
                data,
                segment.s_type,
                segment=segment
            ))

    return windows

def extract_windows_from_segment_list(segments: list[Segment]):
    all_windows = []

    for segment in segments:
        windows = extract_windows_from_segment(segment)
        all_windows.extend(windows)

    return all_windows

def min_max_scaler(segment: Segment):
  segment.data = segment.data - (np.min(segment.data))
  segment.data /= np.max(segment.data)

def butter_lpf(segment: Segment, order, fs, cutoff):
    b, a = butter(order, cutoff, btype='lowpass', fs=fs, analog=False)
    filtered = lfilter(b, a, segment.data)
    segment.data = filtered
