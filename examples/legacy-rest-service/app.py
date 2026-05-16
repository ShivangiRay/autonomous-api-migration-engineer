from fastapi import FastAPI

app = FastAPI(title="Legacy User Management")


@app.get("/users")
def list_users(page: int = 1, page_size: int = 25) -> list[dict]:
    return [{"id": "usr_001", "email": "demo@example.com", "status": "active"}]


@app.post("/users")
def create_user(payload: dict) -> dict:
    return {"id": "usr_002", "email": payload["email"], "status": "active"}

