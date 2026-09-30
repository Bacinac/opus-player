"""The /api aggregator. Small on purpose: the player owns the surface, not the
catalogue."""

from fastapi import APIRouter
from opus_core import plugins, revision

from opus.api.routers import (app, art, cast, explore, favorites, game, history, home,
                              launcher, listening, photos, play, progress, radio,
                              system, users)
from opus.plugins import PLUGINS

router = APIRouter(prefix="/api")
router.include_router(system.router)
router.include_router(plugins.router(PLUGINS))
router.include_router(revision.router("opus-player"))
router.include_router(home.router)
router.include_router(launcher.router)
router.include_router(play.router)
router.include_router(cast.router)
router.include_router(progress.router)
router.include_router(favorites.router)
router.include_router(listening.router)
router.include_router(history.router)
router.include_router(users.router)
router.include_router(explore.router)
router.include_router(art.router)
router.include_router(radio.router)
router.include_router(game.router)
router.include_router(photos.router)
router.include_router(app.router)
