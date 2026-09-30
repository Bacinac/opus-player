"""What the player has to remember.

Not much, deliberately: the catalogue is the Library's and the files are the
Library's. What is the player's own is who is watching, where each of them got
to, and the settings of this installation."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class User(Base):
    """What this module knows about somebody who watches.

    Not who they are — the roster next door is the only list of that, and a
    second copy of it here would be a copy that drifts the day somebody is
    renamed. This row hangs off a name on that roster and holds what is
    genuinely the player's own: a colour to tell them apart across the room,
    which language a film should come up in, how they like a shelf arranged. It
    is made the first time somebody is picked, not when they are added over
    there.

    A profile is picked, not proved. On a television the only input is four
    arrow keys, and a lock nobody can operate from the sofa is a lock that gets
    left open — so what this decides is whose half-finished films these are,
    which is bookkeeping and not secrecy.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # the name on the roster this belongs to. Null for somebody who has no
    # account at all — a guest on the sofa is still a person to keep a place in
    # a film for
    person: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    # only for those: whoever is on the roster is called what the roster calls
    # them, asked fresh every time it is drawn
    name: Mapped[str] = mapped_column(String(64), default="")
    # what tells them apart across the room, where a photograph would be a
    # face too small to read
    colour: Mapped[str] = mapped_column(String(16), default="")
    # which sound and which subtitle a film should come up in for this person,
    # in order of preference — a film with no Croatian sound still has a second
    # answer. Per profile rather than per install: one house watches in two
    # languages, and answering it once per film is the thing nobody keeps doing
    audio_languages: Mapped[str] = mapped_column(String(32), default="")
    subtitle_languages: Mapped[str] = mapped_column(String(32), default="")
    # how this person likes each shelf arranged, one answer per shelf, as JSON.
    # Not the library's business: the catalogue owns what a thing IS, and a
    # viewer owns the order they want to walk past it in — and films and artists
    # do not want the same one
    shelf_orders: Mapped[str] = mapped_column(String(200), default="{}")
    # whose photographs a box's screensaver brings up while this profile is
    # picked on it, in the library's own words: the ids of the people there,
    # in the order chosen, or "household". Empty is whoever the profile is, and
    # the household for a profile the library has no face for
    screensaver: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # a name is one person's, but only among those who are nobody on the
        # roster: everybody else is told apart by the name over there, and two
        # rows sharing a name here would have one of them silently disappear
        # from a list that is keyed by it
        Index("ix_users_local_name", "name", unique=True,
              postgresql_where=text("person IS NULL AND name <> ''")),
    )


class BoxPreference(Base):
    """What a television let in keeps of its own: how the household in front of
    it arranges its shelves, and where in the house it is plugged in.

    A box is not a profile and never becomes one; but the household in front of
    it arranges its shelves too, and an arrangement that is gone the next time
    the screen wakes is one nobody bothers making. Keyed by the device's id in
    the Library's list, which is the only list of boxes there is.
    """

    __tablename__ = "box_preferences"

    box_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    shelf_orders: Mapped[str] = mapped_column(String(200), default="{}", server_default="{}")
    # the receiver's input this box's picture and sound arrive on. It belongs to
    # the box and not to the install: two boxes on one receiver arrive on two
    # inputs, and a box wired straight to a screen of its own has none
    amp_source: Mapped[str] = mapped_column(String(32), default="", server_default="")
    # what the box was plugged into when it was wired, as that device names
    # itself over HDMI: the box carried to a screen of its own arrives on none of
    # the receiver's inputs, and empty is a box that could not say
    amp_sink: Mapped[str] = mapped_column(String(160), default="", server_default="")


class Progress(Base):
    """How far into something you got, per person and per item. Not per device:
    stopping on the sofa and carrying on in the kitchen is the whole point of
    keeping this on the server — and not shared between people, because two of
    them watching the same series are not in the same place in it."""

    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("user_id", "kind", "item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))  # movie | episode | track
    item_id: Mapped[int] = mapped_column(Integer, index=True)
    position_s: Mapped[float] = mapped_column(Float, default=0.0)
    duration_s: Mapped[float | None] = mapped_column(Float)
    # what played it last, so a device can say "you were watching this on the TV"
    surface: Mapped[str] = mapped_column(String(16), default="")
    # when this person got to the end of it, if they ever did. The position is
    # cleared at the end and this is not: where somebody stopped stops being
    # true the moment they finish, and "seen it" goes on being true for years.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # what the thing belongs to — the series an episode is an episode of. Not a
    # catalogue: the player is not writing down what exists, it is writing down
    # the whole of its own sentence, and "watched episode E" without saying of
    # what leaves a shelf of series unable to say how far anybody got.
    parent_id: Mapped[int | None] = mapped_column(Integer, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MusicFavorite(Base):
    """A record a person wants to find again.

    The Player keeps the preference, rather than a second music catalogue: a
    track's title, cover and whether it is currently playable are still facts
    the Library owns.  ``person`` is the roster key, not a Player profile, so
    the same favourite follows the signed-in person between their browser and
    their paired car without asking an Android Auto session to pick a sofa
    profile.
    """

    __tablename__ = "music_favorites"
    __table_args__ = (
        UniqueConstraint("person", "track_id"),
        Index("ix_music_favorites_person_created", "person", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person: Mapped[str] = mapped_column(String(64), index=True)
    track_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MusicPlay(Base):
    """One song heard, by one person. Not where they stopped — that is
    `Progress`, one row per song and overwritten — but how often, which is what
    "most listened" is made of and what a bookmark can never say. Heard means
    what it has meant since scrobbling: half the song, or four minutes of it."""

    __tablename__ = "music_plays"
    __table_args__ = (Index("ix_music_plays_user_played", "user_id", "played_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    track_id: Mapped[int] = mapped_column(Integer)
    release_id: Mapped[int] = mapped_column(Integer)
    artist_id: Mapped[int] = mapped_column(Integer)
    played_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HistoryLink(Base):
    """Somebody's own account at a service that keeps what they listened to or
    watched — ListenBrainz for records, Simkl for films and television. Linked
    by them, from their own settings, and able to write their history and
    nobody else's."""

    __tablename__ = "history_links"
    __table_args__ = (UniqueConstraint("user_id", "service"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    service: Mapped[str] = mapped_column(String(16))
    # the name the service knows them by, said back so a wrong account shows
    account: Mapped[str] = mapped_column(String(128))
    token: Mapped[str] = mapped_column(Text)
    refresh: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HistorySend(Base):
    """A song heard or a film seen, on its way to a linked service. Deleted once
    the service has it: the history is theirs to keep, not a second copy here.
    What failed stays, with why, and is tried again later."""

    __tablename__ = "history_outbox"
    __table_args__ = (Index("ix_history_outbox_due", "service", "due_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    service: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))  # track | movie | episode
    item_id: Mapped[int] = mapped_column(Integer)
    # when it was heard or seen, which is what the service writes down
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tries: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    problem: Mapped[str] = mapped_column(Text, default="", server_default="")
    # none once the service has said it does not know the thing: no retry
    # changes that, only somebody asking again
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RadioStation(Base):
    """A station, which is a thing to listen to and not a device.

    The list lived in the house's automation until 2026-08-23, where it had
    ended up because that was what could play it. What exists to listen to is
    the player's business — the same business as the records and the films —
    so it lives here now."""

    __tablename__ = "radio_stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(Text)
    logo: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(String(8), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class GameRound(Base):
    """A round of the guessing game: ten photographs, and what was answered.

    The whole round is one row. Its questions were built from the library on
    the spot and mean nothing without each other — the options offered for one
    picture are only right or wrong against that picture — so they are kept
    together rather than shredded into a table of answers that would have to be
    reassembled to say anything.

    What is scored is written down once, per answer, and the round's total is
    read from it. A total in a column of its own would be a second place the
    same arithmetic lives, free to disagree with the answers it came from."""

    __tablename__ = "game_rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # the questions as built, answers and all. Never sent out whole: the
    # router hands over the half a player is allowed to see.
    questions: Mapped[list] = mapped_column(JSONB, default=list)
    # one entry per question answered: what was picked, whether it was right,
    # how long it took, what it was worth
    answers: Mapped[list] = mapped_column(JSONB, default=list)
    # how long each question is allowed. On the row rather than in the code, so
    # a round already in progress keeps the clock it was started with.
    seconds: Mapped[int] = mapped_column(Integer, default=20)
    # When the question now on the screen was handed out, and which one it was.
    # The clock is the server's: a client that reported its own elapsed time
    # would be reporting the number it is being scored on.
    asked_n: Mapped[int | None] = mapped_column(Integer)
    asked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CarToken(Base):
    """A car the music app was paired in, one row per bearer handed out.

    The bearer carries this row's id under the module's signature, so it cannot
    be pointed at another row; the row is what lets one lost phone be taken back
    without its owner changing a password and signing out of everything else."""

    __tablename__ = "car_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    # the name on the roster it was minted for
    person: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
