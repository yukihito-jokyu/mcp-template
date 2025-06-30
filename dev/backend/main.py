from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from self_mcp.app import MultiMCPManager

clients = MultiMCPManager()

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

@app.post("/chat")
async def chat(message: dict):
    await clients.get_tool_list()
    results = await clients.process_message(message.get("message"), [])
    return {"message": results[-1][-1]["content"]}
