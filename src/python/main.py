from contextlib import asynccontextmanager
import os
import threading
import traceback

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from medication.router import router as medication_router
from quiz.router import router as quiz_router
from search.router import router as search_router
from settings.router import router as settings_router
from guidelines.router import router as guidelines_router
from sources.router import router as sources_router
from upload.router import router as upload_router
from quiz.router import warm_quiz_dependencies
from llm.base import LLMError, ErrorCategory
from paths import HOST as _HOST, PORT as _PORT
from seed import seed_user_data


def _start_warmup_thread() -> None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return

    def warm() -> None:
        try:
            warm_quiz_dependencies()
        except Exception:
            traceback.print_exc()

    threading.Thread(target=warm, daemon=True).start()


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_user_data()
    _start_warmup_thread()
    yield


app = FastAPI(title="StudyBot Backend", version="0.1.0", lifespan=lifespan)

_ALLOW_ORIGINS = ["http://localhost:5173", "http://localhost:5174"]
_ALLOW_ORIGIN_REGEX = None
if os.environ.get("STUDYBOT_USER_DATA"):
    _ALLOW_ORIGIN_REGEX = r"(file://.*|null)"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOW_ORIGINS,
    allow_origin_regex=_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    status_code = 500
    if exc.category == ErrorCategory.RATE_LIMIT:
        status_code = 429
    elif exc.category == ErrorCategory.AUTH:
        status_code = 401

    return JSONResponse(
        status_code=status_code, content={"detail": str(exc), "category": exc.category}
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(quiz_router)
app.include_router(settings_router)
app.include_router(medication_router)
app.include_router(search_router)
app.include_router(guidelines_router)
app.include_router(sources_router)
app.include_router(upload_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=_HOST, port=_PORT, reload=False)
