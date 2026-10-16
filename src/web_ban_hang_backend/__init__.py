def main() -> None:
    import uvicorn

    uvicorn.run("web_ban_hang_backend.main:app", host="0.0.0.0", port=8000)
