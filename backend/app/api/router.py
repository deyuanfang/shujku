from fastapi import APIRouter
from app.api import documents, categories, search, stats, changes, visualization, upload, settings, storage, knowledge_query, export_import, mobile_import, organizer_api, setup_api, monitor_api, manage_api

api_router = APIRouter()

api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(stats.router, prefix="/stats", tags=["Stats"])
api_router.include_router(changes.router, prefix="/changes", tags=["Changes"])
api_router.include_router(visualization.router, prefix="/visualization", tags=["Visualization"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(storage.router, prefix="/storage", tags=["Storage"])
api_router.include_router(knowledge_query.router, prefix="/knowledge", tags=["Knowledge"])
api_router.include_router(export_import.router, prefix="/data", tags=["Data"])
api_router.include_router(mobile_import.router, prefix="", tags=["Mobile"])
api_router.include_router(organizer_api.router, prefix="/organize", tags=["Organizer"])
api_router.include_router(setup_api.router, prefix="/system", tags=["System"])
api_router.include_router(monitor_api.router, prefix="/monitor", tags=["Monitor"])
api_router.include_router(manage_api.router, prefix="", tags=["Manage"])
