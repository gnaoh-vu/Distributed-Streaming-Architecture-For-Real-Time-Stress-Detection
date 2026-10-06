import time
import asyncio
from fastapi.middleware.cors import CORSMiddleware

from web_test.BE.api.endpoins import router as rest_router
from web_test.BE.api.websocket import router as websocket_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],    
)

app.include_router(websocket_router)

@app.get("/")
def heath_check():
    return {
        "msg": "Ok"
    }

