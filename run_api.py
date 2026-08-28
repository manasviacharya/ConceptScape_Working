import uvicorn

from config import settings

if __name__ == "__main__":
    uvicorn.run("api.service:app", host=settings.api_host, port=settings.api_port, reload=False)
