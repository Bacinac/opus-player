# The page calls these by name at runtime; R8 has no way to see that and would
# rename them into silence.
-keepclassmembers class biz.boskovic.opus.player.OpusTv {
    @android.webkit.JavascriptInterface <methods>;
}
