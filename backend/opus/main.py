import asyncio
import logging
from contextlib import asynccontextmanager

import opus_auth
from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opus_core import dida
from opus_core.door import Door
from opus_core.encoding import CompressJSON

from opus import auth
from opus.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# httpx narrates every request with its whole address, and some of what this
# fetches carries a credential in the query string.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
opus_auth.quiet_access_log()


class _Player(FastAPI):
    def build_middleware_stack(self):
        return CompressJSON(opus_auth.secured(super().build_middleware_stack()))


@asynccontextmanager
async def lifespan(app):
    from opus.dac_watchdog import monitor
    from opus.history import sender
    tasks = [asyncio.create_task(monitor.run()), asyncio.create_task(sender.run())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await dida.close()


app = _Player(title="OPUS · Player", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)
log = logging.getLogger("opus")


@app.exception_handler(RequestValidationError)
async def refused(request: Request, exc: RequestValidationError):
    """The access log says only 422, and a client sending a broken body once a
    minute for an hour said nothing more than that. Which fields, and from what.
    The values are left out: a sign-in body is one of the things refused here."""
    log.warning("refused %s %s from %r: %s", request.method, request.url.path,
                request.headers.get("user-agent", ""),
                [(".".join(str(part) for part in e["loc"]), e["type"]) for e in exc.errors()])
    return await request_validation_exception_handler(request, exc)


async def refusal(request: Request) -> JSONResponse | None:
    """One door for every route, so a route cannot be added and forgotten."""
    bearer = auth.bearer_of(request)
    person = request.cookies.get(opus_auth.SESSION_COOKIE)
    if (not bearer
            and not await auth.from_house(request.headers.get(opus_auth.TOKEN_HEADER))
            and not opus_auth.same_origin(request)):
        return JSONResponse({"detail": "not sent from this module's pages"}, status_code=403)
    if not await auth.allowed(request.url.path,
                              person_cookie=person,
                              ticket=request.query_params.get("ticket"),
                              box=request.cookies.get(auth.DEVICE_COOKIE),
                              token=request.headers.get(opus_auth.TOKEN_HEADER),
                              bearer=bearer):
        # somebody who said who they are and is still refused is told so, rather
        # than sent back to a login they already passed
        if (person or bearer) and await auth.person(person, bearer):
            return JSONResponse({"detail": "not yours to open"}, status_code=403)
        return JSONResponse({"detail": "authentication required"}, status_code=401)
    return None


app.add_middleware(Door, refusal=refusal)


app.include_router(router)
