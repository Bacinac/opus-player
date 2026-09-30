package biz.boskovic.opus.player

import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ResolveInfo
import android.os.Build

/** The small, deliberate set of applications the television can open from
 * Home. Each is resolved through Android rather than by guessing its activity. */
internal class HomeApps(private val packages: PackageManager) {

    data class App(
        val component: ComponentName,
        val label: String,
    )

    fun named(packageName: String): App? =
        entries(Intent.CATEGORY_LEANBACK_LAUNCHER, packageName).firstOrNull()
            ?: entries(Intent.CATEGORY_LAUNCHER, packageName).firstOrNull()

    private fun entries(category: String, packageName: String): List<App> {
        val intent = Intent(Intent.ACTION_MAIN).addCategory(category).setPackage(packageName)
        return query(intent).map { it.app() }
    }

    private fun ResolveInfo.app(): App {
        val info = activityInfo
        return App(ComponentName(info.packageName, info.name), loadLabel(packages).toString())
    }

    private fun query(intent: Intent): List<ResolveInfo> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            packages.queryIntentActivities(intent, PackageManager.ResolveInfoFlags.of(0))
        } else {
            @Suppress("DEPRECATION")
            packages.queryIntentActivities(intent, 0)
        }

}
