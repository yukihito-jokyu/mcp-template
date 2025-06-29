from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS設定（React側からアクセスできるようにする）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # ReactのURL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/hello")
async def hello():
    return {"message": "Hello from FastAPI!"}
