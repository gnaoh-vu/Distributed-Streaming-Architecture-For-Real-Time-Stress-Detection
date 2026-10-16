from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class Batch(BaseModel):
    label: int
    start: float
    end: float
    id: str

@router.post('/window')
def receive_label(batch: Batch):
    print(batch)
