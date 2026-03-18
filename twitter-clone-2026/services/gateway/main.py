import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.tweets.app import router as tweets_router

# Импортируем роутеры из наших сервисов
from services.users.app import router as users_router

# Создаем экземпляр приложения
app = FastAPI(
    title="Twitter Clone 2026",
    description="Микросервисный клон Twitter (Modular Monolith)",
    version="1.0.0",
    docs_url="/api/docs",  # Swagger UI будет здесь
)

# Настройка CORS (чтобы фронтенд мог обращаться к бэкенду)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В проде лучше указать конкретный домен фронтенда
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры (эндпоинты)
app.include_router(users_router)
app.include_router(tweets_router)


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """
    Корневой эндпоинт для проверки, что сервер жив.
    """
    return {"message": "Twitter Clone API is running"}


# Точка входа для запуска через python main.py
if __name__ == "__main__":
    uvicorn.run("services.gateway.main:app", host="0.0.0.0", port=8000, reload=True)
