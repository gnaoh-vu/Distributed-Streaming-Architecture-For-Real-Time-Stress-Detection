import numpy as np
from enum import StrEnum

class SignalType(StrEnum):
    TEMP = 'TEMP'
    ACC = 'ACC'
    BVP = 'BVP'
    EDA = 'EDA'
    HR = 'HR'

class Signal():
    def __init__(
        self,
        start_time: float,
        freq: float,
        data: list,
        s_type: SignalType
    ):
        self.data = np.asarray(data, dtype=np.float32)
        self.start_time = start_time
        self.s_type = s_type
        self.freq = freq

    @property
    def end_time(self):
        return self.start_time + (len(self.data) / self.freq)

class Segment(Signal):
    def __init__(
        self,
        start_time: float,
        freq: float,
        data: list,
        s_type: SignalType,
        participant: str,
        folder: str,
        is_stress: bool,
        timestamp: float | None =None
    ):
        super().__init__(start_time, freq, data, s_type)
        self.timestamp = timestamp
        self.is_stress = is_stress
        self.participant = participant
        self.folder = folder

class Window(Signal):
     def __init__(
        self,
        start_time: float,
        freq: float,
        data: list,
        s_type: SignalType,
        segment: Segment
    ):
        super().__init__(start_time, freq, data, s_type)
        self.segment = segment
