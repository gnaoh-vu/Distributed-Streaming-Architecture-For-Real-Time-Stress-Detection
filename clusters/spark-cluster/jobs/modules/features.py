import numpy as np
from bisect import bisect_left, bisect_right

from .adarp import extract_windows_from_segment_list

def extract_hrv_and_eda(all_segment_lists: dict[str, list], all_p_baselines=None):
  all_hrv_features = []
  all_eda_features = []
  all_p_ids = []

  for i in range(len(all_segment_lists['EDA'])):
    eda_segment_list = all_segment_lists['EDA'][i]
    ibi = all_segment_lists['IBI'][i]

    p = all_segment_lists['EDA'][i][0].participant
    windows = extract_windows_from_segment_list(eda_segment_list)
    eda_features, hrv_features = extract_hrv_and_eda_features_from_eda_windows(windows, ibi)

    if all_p_baselines is not None and len(eda_features) != 0:
      p_baseline = all_p_baselines[p]

      eda_features = np.array(eda_features)
      hrv_features = np.array(hrv_features)

      hrv_features = (hrv_features - p_baseline['HRV']['mean']) / (p_baseline['HRV']['std'] + 1e-9)
      eda_features = (eda_features - p_baseline['EDA']['mean']) / (p_baseline['EDA']['std'] + 1e-9)

    all_eda_features.extend(eda_features)
    all_hrv_features.extend(hrv_features)
    all_p_ids.extend([p] * len(eda_features))

  return all_eda_features, all_hrv_features, all_p_ids

def extract_hrv_and_eda_features_from_eda_windows(windows, ibi):
  eda_features_list, hrv_features_list = [], []

  for w in windows:
    result = extract_hrv_and_eda_features_from_eda_one_window(w, ibi)

    if (result is not None):
        hrv_features, eda_features = result
        hrv_features_list.append(hrv_features)
        eda_features_list.append(eda_features)

  return eda_features_list, hrv_features_list

def extract_hrv_and_eda_features_from_eda_one_window(window, ibi):
    if len(ibi) <= 3: return None

    lo = bisect_left(ibi, window.start_time)
    hi = bisect_right(ibi, window.end_time)
    lo = max(lo, 1)
    rr_segment = [ibi[i] - ibi[i-1] for i in range(lo, hi)]

    hrv_features = extract_hrv_features(rr_segment)
    eda_features = extract_eda_featurs(window.data)

    return hrv_features, eda_features

def extract_hrv_features(hrv):
  mean = np.mean(hrv)
  median = np.median(hrv)
  std = np.std(hrv, ddof=1)
  rms = np.sqrt(np.mean(np.diff(hrv) ** 2))

  # gap_mask = []
  # freq_features = []

  # for rr in hrv:
  #   diff = np.abs(rr - median)
  #   gap_mask.append(0 if diff < THRESHOLD else 1)

  # idx, max_gap = get_max_gap(gap_mask)
  # continuous_time = max_gap * median

  # if continuous_time > VALID_HRV_TIME:
  #   valid_hrv = hrv[idx : idx + max_gap]
  #   freq_features = []
  
  return [median, mean, std, rms]

def get_max_gap(gap_mask):
  best_count, count = 0, 0
  best_idx, idx = 0, 0

  for i in range(len(gap_mask)):
    if gap_mask[i] == 1:
      if count > best_count:
        best_count = count
        best_idx = idx

      idx = i
      count = 1

    else:
      count += 1

  if count > best_count:
    best_count = count
    best_idx = idx

  return best_idx, best_count

def extract_eda_featurs(eda):
  std = np.std(eda, ddof=1)
  median = np.median(eda)
  mean = np.mean(eda)
  min = np.min(eda)
  max = np.max(eda)
  return [median, mean, std, min, max]

def extract_eda(eda_list, timestamps, start, end):
    lo = bisect_left(timestamps, start)
    hi = bisect_right(timestamps, end)
    hi = min(hi, len(timestamps))

    eda_in_bound = eda_list[lo:hi]
    flat_eda = [float(value) for eda in eda_in_bound for value in eda]

    return flat_eda, hi

def extract_ibi(ibi_list, timestamps, start, end):
    lo = bisect_left(timestamps, start)
    hi = bisect_right(timestamps, end)
    hi = min(hi, len(timestamps))

    ibi_in_bound = ibi_list[lo:hi]
    flat_ibi = [float(value) for ibi in ibi_in_bound for value in ibi]

    if len(flat_ibi) > 1:
        ibi = [flat_ibi[i] - flat_ibi[i-1] for i in range(1, len(flat_ibi))]
    else:
        ibi = []

    return ibi, hi

