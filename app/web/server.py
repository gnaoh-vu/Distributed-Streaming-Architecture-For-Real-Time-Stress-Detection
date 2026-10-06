from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.corfrom fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templatess import CORSMiddleware

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],    
)

@app.get("/", response_class=HTMLResponse)
async def dash_board(request: Request):
    return templates.TemplateResponse(
        request=request, name='index.html'
    )
