package biz.boskovic.opus.music

import androidx.annotation.OptIn
import androidx.car.app.CarContext
import androidx.car.app.model.Action
import androidx.car.app.model.Header
import androidx.car.app.model.Template
import androidx.media3.common.util.UnstableApi
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

/** One folder of the browse tree: the children of [parentId], under a back
 *  header carrying the folder's [title]. */
@OptIn(UnstableApi::class)
class BrowseScreen(
    carContext: CarContext,
    link: CarLink,
    private val parentId: String,
    private val title: String,
) : CarScreen(carContext, link) {

    private var state: Shelf = Shelf.Loading
    private var started = false

    override fun onGetTemplate(): Template {
        if (!started) {
            started = true
            lifecycleScope.launch {
                state = prepare { listOf(Group(null, MusicTree.children(carContext, parentId))) }
                invalidate()
            }
        }
        val header = Header.Builder()
            .setStartHeaderAction(Action.BACK)
            .apply { if (title.isNotEmpty()) setTitle(title) }
            .build()
        return sectioned(header, state)
    }
}
