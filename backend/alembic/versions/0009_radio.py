"""radio stations

Radio was the one thing playing in this house that the player could not put on.
The list lived in DIDA, which is the house's device plane — a station is not a
device, it is something to listen to, so it belongs where the records and the
films are. Moved here whole, in the order it was already in.

Revision ID: 0009_radio
Revises: 0008_watched_parent
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_radio"
down_revision = "0008_watched_parent"
branch_labels = None
depends_on = None

STATIONS = [
    {"name": "Yammat FM", "genre": "Rock / eclectic \u00b7 Zagreb", "url": "https://stream.yammat.fm/radio/8000/yammat.mp3", "logo": "https://yammat.fm/wp-content/uploads/2025/07/Logo_header_opaque_01.png", "country": "HR", "sort_order": 0},
    {"name": "Radio 101 Croatia", "genre": "", "url": "http://live.radio101.hr:9531/", "logo": "http://cdn-profiles.tunein.com/s8910/images/logoq.jpg", "country": "HR", "sort_order": 1},
    {"name": "100.5 | Radio Student (Public Radio)", "genre": "", "url": "http://161.53.122.184:8000/AAC128.aac", "logo": "http://cdn-radiotime-logos.tunein.com/s10351q.png", "country": "HR", "sort_order": 2},
    {"name": "87.8 | Radio Dalmacija (US News)", "genre": "", "url": "http://shoutcast.pondi.hr:8000", "logo": "http://cdn-radiotime-logos.tunein.com/s16198q.png", "country": "HR", "sort_order": 3},
    {"name": "HRT Prvi program 92.1 (Rock Music)", "genre": "", "url": "https://27753.live.streamtheworld.com:443/PROGRAM1AAC_SC?TGT=TuneIn&DIST=TuneIn&partnertok=eyJhbGciOiJIUzI1NiIsImtpZCI6InR1bmVpbiIsInR5cCI6IkpXVCJ9.eyJ0cnVzdGVkX3BhcnRuZXIiOnRydWUsImlhdCI6MTc4Mjg0OTY2NCwiaXNzIjoidGlzcnYifQ.x8LqNClU4NjoLq1luV8OCMl7V4z-cF0K0OcKKE-2RmQ&gdpr=1", "logo": "http://cdn-profiles.tunein.com/s15643/images/logoq.jpg?t=1", "country": "HR", "sort_order": 4},
    {"name": "HRT Drugi program 98.5 (Rock)", "genre": "", "url": "https://25553.live.streamtheworld.com:443/PROGRAM2AAC_SC?TGT=TuneIn&DIST=TuneIn&partnertok=eyJhbGciOiJIUzI1NiIsImtpZCI6InR1bmVpbiIsInR5cCI6IkpXVCJ9.eyJ0cnVzdGVkX3BhcnRuZXIiOnRydWUsImlhdCI6MTc4Mjg0OTY2NSwiaXNzIjoidGlzcnYifQ.v5Sn5QHlm_6mEFE7EAVv2mp4runv1U7C1hNg-h1-D2E&gdpr=1", "logo": "http://cdn-profiles.tunein.com/s15654/images/logoq.jpg?t=161167", "country": "HR", "sort_order": 5},
    {"name": "HRT Tre\u0107i program 94.3 (Classical Music)", "genre": "", "url": "https://25443.live.streamtheworld.com:443/PROGRAM3AAC_SC?TGT=TuneIn&DIST=TuneIn&partnertok=eyJhbGciOiJIUzI1NiIsImtpZCI6InR1bmVpbiIsInR5cCI6IkpXVCJ9.eyJ0cnVzdGVkX3BhcnRuZXIiOnRydWUsImlhdCI6MTc4Mjg0OTY2NCwiaXNzIjoidGlzcnYifQ.x8LqNClU4NjoLq1luV8OCMl7V4z-cF0K0OcKKE-2RmQ&gdpr=1", "logo": "http://cdn-profiles.tunein.com/s24907/images/logoq.jpg?t=156940", "country": "HR", "sort_order": 6},
    {"name": "HRT Radio Split", "genre": "", "url": "http://28503.live.streamtheworld.com:80/SPLITAAC_SC?TGT=TuneIn&tdtok=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiIsImtpZCI6ImZTeXA4In0.eyJpc3MiOiJ0aXNydiIsInN1YiI6IjIxMDY0IiwiaWF0IjoxNzgyODQ5NjYzLCJ0ZC1yZWciOmZhbHNlfQ.Mk2JFG3-70NSH60lvEhZ4N6tfXyRpPw0OcgFTl1dtxQ&DIST=TuneIn&partnertok=eyJhbGciOiJIUzI1NiIsImtpZCI6InR1bmVpbiIsInR5cCI6IkpXVCJ9.eyJ0cnVzdGVkX3BhcnRuZXIiOnRydWUsImlhdCI6MTc4Mjg0OTY2MywiaXNzIjoidGlzcnYifQ.2V1yeADs25V1Q3VvADvVwDvj0WjjeE1AUdPDwQo5hg0&gdpr=1", "logo": "http://cdn-profiles.tunein.com/s25504/images/logoq.jpg?t=157018", "country": "HR", "sort_order": 7},
    {"name": "HRT Radio Sljeme 88.1 (Adult Hits)", "genre": "", "url": "https://23623.live.streamtheworld.com:443/SLJEMEAAC_SC?TGT=TuneIn&DIST=TuneIn&partnertok=eyJhbGciOiJIUzI1NiIsImtpZCI6InR1bmVpbiIsInR5cCI6IkpXVCJ9.eyJ0cnVzdGVkX3BhcnRuZXIiOnRydWUsImlhdCI6MTc4Mjg0OTY2NCwiaXNzIjoidGlzcnYifQ.x8LqNClU4NjoLq1luV8OCMl7V4z-cF0K0OcKKE-2RmQ&gdpr=1", "logo": "http://cdn-profiles.tunein.com/s25503/images/logoq.jpg", "country": "HR", "sort_order": 8},
    {"name": "Otvoreni 105.6 (00's Music)", "genre": "", "url": "https://stream.otvoreni.hr/otvoreni", "logo": "http://cdn-profiles.tunein.com/s18415/images/logoq.png?t=155239", "country": "HR", "sort_order": 9},
    {"name": "Zfm - Zarazno Dobar Radio 96.0 (Top 40 & Pop Music)", "genre": "", "url": "https://ec2s.crolive.com.hr:7015/stream", "logo": "http://cdn-profiles.tunein.com/s73331/images/logoq.png?t=1", "country": "HR", "sort_order": 10},
    {"name": "Radio Paradise", "genre": "Eclectic mix", "url": "https://stream.radioparadise.com/aac-320", "logo": "https://radioparadise.com/apple-touch-icon.png", "country": "US", "sort_order": 11},
    {"name": "RP Mellow", "genre": "Mellow mix", "url": "https://stream.radioparadise.com/mellow-320", "logo": "https://radioparadise.com/apple-touch-icon.png", "country": "US", "sort_order": 12},
    {"name": "RP Rock", "genre": "Rock mix", "url": "https://stream.radioparadise.com/rock-320", "logo": "https://radioparadise.com/apple-touch-icon.png", "country": "US", "sort_order": 13},
    {"name": "Groove Salad", "genre": "Ambient / downtempo", "url": "https://ice1.somafm.com/groovesalad-128-mp3", "logo": "https://somafm.com/img3/groovesalad-400.jpg", "country": "US", "sort_order": 14},
    {"name": "Lush", "genre": "Vocal / chill", "url": "https://ice1.somafm.com/lush-128-mp3", "logo": "https://somafm.com/img3/lush-400.jpg", "country": "US", "sort_order": 15},
    {"name": "Indie Pop Rocks", "genre": "Indie", "url": "https://ice1.somafm.com/indiepop-128-mp3", "logo": "https://somafm.com/img3/indiepop-400.jpg", "country": "US", "sort_order": 16},
    {"name": "Secret Agent", "genre": "Spy jazz / lounge", "url": "https://ice1.somafm.com/secretagent-128-mp3", "logo": "https://somafm.com/img3/secretagent-400.jpg", "country": "US", "sort_order": 17},
    {"name": "Drone Zone", "genre": "Space ambient", "url": "https://ice1.somafm.com/dronezone-128-mp3", "logo": "https://somafm.com/img3/dronezone-400.jpg", "country": "US", "sort_order": 18},
]


def upgrade() -> None:
    stations = op.create_table(
        "radio_stations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("genre", sa.String(200), nullable=False, server_default=""),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("logo", sa.Text()),
        sa.Column("country", sa.String(8), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.bulk_insert(stations, STATIONS)


def downgrade() -> None:
    op.drop_table("radio_stations")
