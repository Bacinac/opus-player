package biz.boskovic.opus.music

import androidx.annotation.OptIn
import androidx.car.app.CarContext
import androidx.car.app.model.Action
import androidx.car.app.model.CarIcon
import androidx.car.app.model.Tab
import androidx.car.app.model.TabContents
import androidx.car.app.model.TabTemplate
import androidx.car.app.model.Template
import androidx.core.graphics.drawable.IconCompat
import androidx.lifecycle.lifecycleScope
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import kotlinx.coroutines.launch

/** The car-app home: four tabs over the same shelf — artists, radio, what was
 *  played recently, and what is held offline. Each tab loads the first time it
 *  is shown and keeps its result for the rest of the drive. */
@OptIn(UnstableApi::class)
class RootScreen(carContext: CarContext, link: CarLink) : CarScreen(carContext, link) {

    private data class TabDef(val id: String, val title: Int, val icon: Int)

    private val tabs = listOf(
        TabDef(MUSIC, R.string.car_tab_music, R.drawable.ic_car_music),
        TabDef(RADIO, R.string.car_tab_radio, R.drawable.ic_car_radio),
        TabDef(RECENT, R.string.car_tab_recent, R.drawable.ic_car_recent),
        TabDef(OFFLINE, R.string.car_tab_offline, R.drawable.ic_car_offline),
    )
    private val states = HashMap<String, Shelf>()
    private val started = HashSet<String>()
    private var active = MUSIC

    override fun onGetTemplate(): Template {
        val state = states.getOrPut(active) { Shelf.Loading }
        if (started.add(active)) {
            val tab = active
            lifecycleScope.launch {
                states[tab] = prepare { groupsFor(tab) }
                if (active == tab) invalidate()
            }
        }
        val builder = TabTemplate.Builder(object : TabTemplate.TabCallback {
            override fun onTabSelected(tabContentId: String) {
                active = tabContentId
                invalidate()
            }
        })
        builder.setHeaderAction(Action.APP_ICON)
        tabs.forEach { tab ->
            builder.addTab(
                Tab.Builder()
                    .setTitle(carContext.getString(tab.title))
                    .setIcon(CarIcon.Builder(IconCompat.createWithResource(carContext, tab.icon)).build())
                    .setContentId(tab.id)
                    .build(),
            )
        }
        builder.setActiveTabContentId(active)
        builder.setTabContents(TabContents.Builder(sectioned(null, state)).build())
        return builder.build()
    }

    private suspend fun groupsFor(tab: String): List<Group> = when (tab) {
        MUSIC -> listOf(Group(null, MusicTree.children(carContext, MusicTree.ARTISTS)))
        RADIO -> listOf(Group(null, MusicTree.children(carContext, MusicTree.RADIO)))
        RECENT -> listOf(
            Group(carContext.getString(R.string.car_section_recent), recent()),
            Group(carContext.getString(R.string.car_section_favorites), MusicTree.children(carContext, MusicTree.FAVORITES)),
        )
        OFFLINE -> listOf(Group(null, MusicTree.children(carContext, MusicTree.OFFLINE)))
        else -> emptyList()
    }

    private suspend fun recent(): List<MediaItem> = buildList {
        MusicTree.continuation(carContext)?.let(::add)
        addAll(MusicTree.children(carContext, MusicTree.RECENT))
    }

    private companion object {
        const val MUSIC = "music"
        const val RADIO = "radio"
        const val RECENT = "recent"
        const val OFFLINE = "offline"
    }
}
