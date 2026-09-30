"""What the installation's plugins add to the Player (opus_core.plugins).

A plugin hands this module a `Plugin`: the picture hosts the catalogue it adds
hands out addresses on, the ways into music that stand on what it adds to the
Library, and the words for both. A picture source is named by the dotted path
of an `opus.api.routers.art.Source` and imported when a picture is first asked
for, so the plugin may import the art route while this module, which the route
imports, is still being put together."""

from dataclasses import dataclass, field

from opus_core import plugins

# the ways into music the Player can answer only when a Library plugin answers
# them: what its catalogue puts in front of the house, and the artists it counts
# as close to the ones the house plays
MUSIC_WAYS = ("offered", "similar")


@dataclass(frozen=True)
class Plugin:
    # (host, "package.module:Source")
    art: tuple[tuple[str, str], ...] = ()
    music_ways: tuple[str, ...] = ()
    words: dict[str, dict[str, str]] = field(default_factory=dict)


PLUGINS: tuple[Plugin, ...] = plugins.load("opus-player")
if not all(isinstance(plugin, Plugin) for plugin in PLUGINS):
    raise plugins.PluginError("a plugin for opus-player must hand over an opus.plugins.Plugin")
if unknown := {way for plugin in PLUGINS for way in plugin.music_ways} - set(MUSIC_WAYS):
    raise plugins.PluginError(f"no way into music the Player can answer: {', '.join(sorted(unknown))}")

ART: tuple[tuple[str, str], ...] = tuple(entry for plugin in PLUGINS for entry in plugin.art)
OPENED_MUSIC_WAYS: tuple[str, ...] = tuple(
    way for way in MUSIC_WAYS if any(way in plugin.music_ways for plugin in PLUGINS))
