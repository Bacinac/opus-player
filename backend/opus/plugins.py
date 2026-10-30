"""What the installation's plugins add to the Player (opus_core.plugins).

A plugin hands this module a `Plugin`: the ways into music that stand on what
it adds to the Library, and the words for them."""

from dataclasses import dataclass, field

from opus_core import plugins

# the ways into music the Player can answer only when a Library plugin answers
# them: what its catalogue puts in front of the house, and the artists it counts
# as close to the ones the house plays
MUSIC_WAYS = ("offered", "similar")


@dataclass(frozen=True)
class Plugin:
    music_ways: tuple[str, ...] = ()
    words: dict[str, dict[str, str]] = field(default_factory=dict)


PLUGINS: tuple[Plugin, ...] = plugins.load("opus-player")
if not all(isinstance(plugin, Plugin) for plugin in PLUGINS):
    raise plugins.PluginError("a plugin for opus-player must hand over an opus.plugins.Plugin")
if unknown := {way for plugin in PLUGINS for way in plugin.music_ways} - set(MUSIC_WAYS):
    raise plugins.PluginError(f"no way into music the Player can answer: {', '.join(sorted(unknown))}")

OPENED_MUSIC_WAYS: tuple[str, ...] = tuple(
    way for way in MUSIC_WAYS if any(way in plugin.music_ways for plugin in PLUGINS))
