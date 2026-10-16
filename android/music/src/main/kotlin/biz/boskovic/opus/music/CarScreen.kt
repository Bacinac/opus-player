package biz.boskovic.opus.music

import android.net.Uri
import androidx.annotation.OptIn
import androidx.car.app.CarContext
import androidx.car.app.CarToast
import androidx.car.app.Screen
import androidx.car.app.model.CarColor
import androidx.car.app.model.CarIcon
import androidx.car.app.model.GridItem
import androidx.car.app.model.GridSection
import androidx.car.app.model.Header
import androidx.car.app.model.Row
import androidx.car.app.model.RowSection
import androidx.car.app.model.Section
import androidx.car.app.model.SectionedItemTemplate
import androidx.core.graphics.drawable.IconCompat
import androidx.lifecycle.lifecycleScope
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DataSourceBitmapLoader
import biz.boskovic.opus.core.Refused
import java.io.IOException
import kotlinx.coroutines.guava.await
import kotlinx.coroutines.launch
import org.json.JSONException

/** A titled band of shelf items; records and stations fall into a cover grid,
 *  everything else into a list, split within the band by what each item is. */
internal data class Group(val title: String?, val items: List<MediaItem>)

internal sealed interface Shelf {
    data object Loading : Shelf
    data class Failed(val message: String) : Shelf
    data class Ready(val groups: List<Group>, val art: Map<Uri, CarIcon>) : Shelf
}

/** What the car-app screens share: loading a band of shelf items with the covers
 *  its grid needs, turning them into template sections, and opening or playing
 *  a tap. Each screen holds its own [Shelf]; nothing is shared across them. */
@OptIn(UnstableApi::class)
abstract class CarScreen(carContext: CarContext, protected val link: CarLink) : Screen(carContext) {

    private val bitmaps by lazy { DataSourceBitmapLoader.Builder(carContext.applicationContext).build() }
    private val albumFallback by lazy {
        CarIcon.Builder(IconCompat.createWithResource(carContext, R.drawable.ic_car_album)).build()
    }
    // PRIMARY leaves the day/night choice to the host, so the mark on the item
    // being played reads against both a light and a dark panel.
    private val nowPlayingIcon by lazy {
        CarIcon.Builder(IconCompat.createWithResource(carContext, R.drawable.ic_car_playing))
            .setTint(CarColor.PRIMARY)
            .build()
    }

    internal suspend fun prepare(block: suspend () -> List<Group>): Shelf = try {
        val groups = block()
        Shelf.Ready(groups, coversOf(groups))
    } catch (error: IOException) {
        Shelf.Failed(message(error))
    } catch (error: JSONException) {
        Shelf.Failed(message(error))
    } catch (error: IllegalArgumentException) {
        Shelf.Failed(message(error))
    }

    internal fun sectioned(header: Header?, state: Shelf): SectionedItemTemplate {
        val builder = SectionedItemTemplate.Builder()
        header?.let { builder.setHeader(it) }
        when (state) {
            is Shelf.Loading -> builder.setLoading(true)
            is Shelf.Failed -> builder.addSection(empty(state.message, null))
            is Shelf.Ready -> {
                val sections = sections(state.groups, state.art)
                if (sections.isEmpty()) builder.addSection(empty(carContext.getString(R.string.car_empty), null))
                else sections.forEach { builder.addSection(it) }
            }
        }
        return builder.build()
    }

    private suspend fun coversOf(groups: List<Group>): Map<Uri, CarIcon> =
        groups.flatMap { it.items }
            .mapNotNull { it.mediaMetadata.artworkUri }
            .distinct()
            .mapNotNull { uri ->
                runCatching { CarIcon.Builder(IconCompat.createWithBitmap(bitmaps.loadBitmap(uri).await())).build() }
                    .getOrNull()?.let { uri to it }
            }
            .toMap()

    private fun sections(groups: List<Group>, art: Map<Uri, CarIcon>): List<Section<*>> = groups.flatMap { group ->
        if (group.items.isEmpty()) {
            return@flatMap listOf(empty(carContext.getString(R.string.car_empty), group.title))
        }
        val grid = group.items.filter { it.griddable }
        val rows = group.items.filterNot { it.griddable }
        buildList<Section<*>> {
            if (grid.isNotEmpty()) add(
                GridSection.Builder()
                    .apply { grid.forEach { addItem(gridItem(it, art)) } }
                    .apply { group.title?.let { setTitle(it) } }
                    .setItemSize(GridSection.ITEM_SIZE_LARGE)
                    .build(),
            )
            if (rows.isNotEmpty()) add(
                RowSection.Builder()
                    .apply { rows.forEach { addItem(row(it, art)) } }
                    .apply { (if (grid.isEmpty()) group.title else null)?.let { setTitle(it) } }
                    .build(),
            )
        }
    }

    private fun empty(message: String, title: String?): RowSection =
        RowSection.Builder()
            .setNoItemsMessage(message)
            .apply { title?.let { setTitle(it) } }
            .build()

    private fun row(item: MediaItem, art: Map<Uri, CarIcon>): Row {
        val meta = item.mediaMetadata
        return Row.Builder()
            .setTitle(meta.title ?: item.mediaId)
            .apply { meta.subtitle?.let { addText(it) } }
            .apply {
                when {
                    item.mediaId == link.nowPlaying -> setImage(nowPlayingIcon, Row.IMAGE_TYPE_ICON)
                    else -> meta.artworkUri?.let { art[it] }?.let { setImage(it, Row.IMAGE_TYPE_LARGE) }
                }
            }
            .apply { if (meta.isBrowsable == true) setBrowsable(true) }
            .setOnClickListener { open(item) }
            .build()
    }

    private fun gridItem(item: MediaItem, art: Map<Uri, CarIcon>): GridItem {
        val meta = item.mediaMetadata
        return GridItem.Builder()
            .setTitle(meta.title ?: item.mediaId)
            .apply { meta.subtitle?.let { setText(it) } }
            .setImage(meta.artworkUri?.let { art[it] } ?: albumFallback)
            .setOnClickListener { open(item) }
            .build()
    }

    private fun open(item: MediaItem) {
        if (item.mediaMetadata.isBrowsable == true) {
            screenManager.push(
                BrowseScreen(carContext, link, item.mediaId, item.mediaMetadata.title?.toString().orEmpty()),
            )
        } else {
            play(item.mediaId)
        }
    }

    private fun play(mediaId: String) {
        lifecycleScope.launch {
            runCatching { link.play(mediaId) }
                .onSuccess { screenManager.push(PlaybackScreen(carContext, link)) }
                .onFailure {
                    CarToast.makeText(carContext, R.string.car_playback_failed, CarToast.LENGTH_LONG).show()
                }
        }
    }

    protected fun message(error: Throwable): String = carContext.getString(
        when (error) {
            is NotPaired -> R.string.car_not_paired
            is VaultUnavailable -> R.string.car_vault_unavailable
            is Refused -> R.string.car_refused
            else -> R.string.car_unreachable
        },
    )

    private val MediaItem.griddable: Boolean
        get() = mediaMetadata.mediaType == MediaMetadata.MEDIA_TYPE_ALBUM
}
