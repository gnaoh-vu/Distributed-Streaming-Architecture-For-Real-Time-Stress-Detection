import random

from schemas.model import SensorSignal, PredictionResult


def predict_stress_testing(sensor: SensorSignal) -> PredictionResult:
    is_stress = sensor.eda > 5.0 or sensor.hr > 100

    confidence = round(random.uniform(0.85, 0.99), 2)

    return PredictionResult(
        is_stress=is_stress,
        confidence=confidence
    )


    