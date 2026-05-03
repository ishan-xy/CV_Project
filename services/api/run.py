import uvicorn

if __name__ == "__main__":
    uvicorn.run("services.api.app.main:app", host="0.0.0.0", port=8000, reload=True, app_dir=".")