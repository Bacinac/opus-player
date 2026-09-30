package biz.boskovic.opus.music

/** Who may browse and drive the session: a controller the platform trusts
 *  (the system, this app, a holder of MEDIA_CONTENT_CONTROL), or one of the
 *  car and voice hosts by a name the platform matched to the caller's uid.
 *  An unmatched name is only what the caller says it is called. */
internal object Controllers {
    private val HOSTS = setOf(
        "com.google.android.projection.gearhead",
        "com.google.android.googlequicksearchbox",
        "com.android.bluetooth",
    )

    fun admits(packageName: String, verified: Boolean, trusted: Boolean): Boolean =
        trusted || (verified && packageName in HOSTS)
}
