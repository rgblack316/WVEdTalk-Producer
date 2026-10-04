import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
from lib.db import client, db, ensure_indexes
from fastapi import Depends
from lib.auth import require_auth, require_admin, ensure_seed_admin
from lib.desk import scheduler_loop
from lib.producer import scheduler_loop as weekly_scheduler_loop
from routers.auth import router as auth_router
from routers.briefings import router as briefings_router
from routers.episodes import router as episodes_router
from routers.settings import router as settings_router
from routers.users import router as users_router
from routers.public import router as public_router
from routers.submissions import router as submissions_router
from routers.data_io import router as data_io_router


# Startup runs before the yield, shutdown after it. Add your own setup/teardown here.
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.index_task = asyncio.create_task(ensure_indexes())  # background: a big index build must not block boot
    await ensure_seed_admin()  # create the bootstrap admin the first time the app starts
    app.state.scheduler_task = asyncio.create_task(scheduler_loop())  # daily 6:00 AM ET edition
    app.state.weekly_task = asyncio.create_task(weekly_scheduler_loop())  # Friday 2:00 PM ET WVEdTalk episode
    yield
    app.state.scheduler_task.cancel()
    app.state.weekly_task.cancel()
    client.close()


# Create the main app without a prefix
app = FastAPI(lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Health/readiness probe — the only open, non-auth route besides /api/auth/*.
@api_router.get("/")
async def root():
    return {"message": "WV Education News Desk API"}

# Auth routes are open; everything else requires the shared passcode (cookie or header).
api_router.include_router(auth_router)
api_router.include_router(public_router)  # open, but each route validates a share token
_guard = [Depends(require_auth)]
api_router.include_router(briefings_router, dependencies=_guard)
api_router.include_router(settings_router, dependencies=_guard)
api_router.include_router(episodes_router, dependencies=_guard)
api_router.include_router(submissions_router, dependencies=_guard)
api_router.include_router(users_router, dependencies=[Depends(require_admin)])
api_router.include_router(data_io_router, dependencies=[Depends(require_admin)])  # full DB export/import, admin-only

# Include the router in the main app
app.include_router(api_router)

# CORS: never combine a wildcard origin with credentials (browsers reject it and it
# would leak the session cookie). Only enable credentials when explicit origins are set.
_cors_origins = [o.strip() for o in os.environ.get('CORS_ORIGINS', '').split(',') if o.strip()]
_wildcard = (not _cors_origins) or ('*' in _cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=not _wildcard,
    allow_origins=["*"] if _wildcard else _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
