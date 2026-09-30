# API compatibility

OPUS Player serves Android applications that can remain installed after the
server is upgraded.  A route continuing to answer is insufficient if its JSON
shape changes under an older APK.

`backend/tests/test_android_api_contract.py` exercises the paired-car bearer
through the real Player ASGI application.  It fixes the browse and voice-search
fields read by the published **OPUS Music 0.1.443** release:

- `GET /api/library/music?order=title` — artist `id`, `title`, `held`, image;
- `GET /api/library/artist/{id}` — `releases` with `id`, `title`, `year`, cover;
- `GET /api/library/release/{id}` — `tracks` with the stream metadata;
- `GET /api/library/search?q=` — playable track card metadata.

`check.sh` separately derives every literal Android method/path from the source
and checks it against Player's OpenAPI route table.  Together, the two checks
cover both deleting an endpoint and changing a response that the released app
parses with `JSONObject.get*`.

Keep these response fields and their enclosing arrays or objects stable for
published clients.  New fields are safe.  Before a deliberately breaking
change, add the next client version's contract alongside this one and keep the
old contract until the supported APK release window has ended.
