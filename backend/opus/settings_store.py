"""Runtime, user-editable configuration persisted in Postgres and edited via the
Settings page. Distinct from opus.config (infra bootstrap from env).

The player owns almost no configuration, and that is the design: how DIDA is
reached and where the sound goes. Everything about WHAT exists is asked of
Library, never stored twice."""

from opus_core.settings import RuntimeConfig as _RuntimeConfig
from opus_core.settings import SettingSpec, SettingsValidationError, Store

from opus.db import SessionLocal
from opus.models import Setting

SETTINGS_SPEC: tuple[SettingSpec, ...] = (
    # the house's devices answer to DIDA; the player speaks to them through it
    SettingSpec("dida_url", "dida", ""),
    SettingSpec("dida_username", "dida", ""),
    SettingSpec("dida_password", "dida", "", secret=True),
    SettingSpec("dida_panel_key", "dida", "", secret=True),
    # where sound goes when it is not this screen. "dac" is the DAC on this
    # host, whose analog output feeds the amplifier's zones; the receiver's own
    # network player is deliberately not used, and surround belongs to the
    # television's engine over HDMI. The amplifier entries are what has to be
    # on and listening before the first note.
    SettingSpec("audio_output_stereo", "audio", "dac"),
    SettingSpec("audio_dac_name", "audio", "iFi"),
    # "tv" is our own wrapper on the television streamer — the one road
    # multichannel can take, because the receiver accepts it only over HDMI
    SettingSpec("audio_output_multi", "audio", "tv"),
    SettingSpec("audio_volume_entity", "audio", "denon:marantz_main"),
    SettingSpec("audio_amp_entity", "audio", "denon:marantz_main"),
    SettingSpec("audio_amp_source", "audio", "MUSIC"),
    # which of the boxes that were let in is that television — the one the
    # multichannel output and the house's own controls mean when they name
    # none. Unset, it is whichever box is the only one listening
    SettingSpec("tv_box", "audio", "", kind="number"),
    # the house's own name for that television, through which a film sent to it
    # while it sleeps, dreams or shows another app wakes it and opens the player
    SettingSpec("tv_box_entity", "audio", ""),
    # renderers fetch with a link and no session; a relative path is nothing to
    # them, so the player has to know its own address as the LAN sees it
    SettingSpec("stream_base", "audio", ""),

    # the install's own app at Simkl, which each person then links their
    # account through; ListenBrainz needs none, a person's token is enough
    SettingSpec("simkl_client_id", "history", ""),

    # the token home automation calls with instead of a session: generated here
    # and carried to DIDA, so the settings form neither shows it nor takes it
    SettingSpec("access_house_token", "access", "", secret=True, hidden=True),
)


def _validate(spec: SettingSpec, value: str):
    if spec.key == "tv_box" and value and not (value.isascii() and value.isdigit()):
        raise SettingsValidationError(spec.key, "bad_value")


class RuntimeConfig(_RuntimeConfig):
    spec = SETTINGS_SPEC


store = Store(RuntimeConfig, Setting, SessionLocal, _validate)
current_runtime = store.runtime
forget_runtime = store.forget
get_for_ui = store.for_ui
update_settings = store.update
store_credentials = store.store_credentials
