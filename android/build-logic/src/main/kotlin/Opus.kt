import com.android.build.api.dsl.CommonExtension
import org.gradle.api.JavaVersion
import org.gradle.api.Project
import org.gradle.api.artifacts.VersionCatalog
import org.gradle.api.artifacts.VersionCatalogsExtension
import org.gradle.kotlin.dsl.getByType
import org.gradle.kotlin.dsl.withType
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

internal val Project.libs: VersionCatalog
    get() = extensions.getByType<VersionCatalogsExtension>().named("libs")

internal fun VersionCatalog.number(name: String): Int = findVersion(name).get().requiredVersion.toInt()

internal fun Project.opusAndroid(android: CommonExtension) {
    android.apply {
        compileSdk {
            version = release(libs.number("compileSdk")) {
                minorApiLevel = libs.number("compileSdkMinor")
            }
        }
        buildToolsVersion = libs.findVersion("buildTools").get().requiredVersion
        defaultConfig.minSdk = libs.number("minSdk")
        compileOptions.apply {
            val java = JavaVersion.toVersion(libs.number("java"))
            sourceCompatibility = java
            targetCompatibility = java
        }
        lint.apply {
            // targetSdk stays below 37: API 37 makes local-network access a runtime
            // permission and refuses background audio without a foreground service,
            // and the OPUS host may well resolve to an address on the LAN.
            disable += "OldTargetApi"
            abortOnError = true
            warningsAsErrors = true
            checkReleaseBuilds = true
        }
        testOptions.unitTests.all { it.useJUnitPlatform() }
    }
    dependencies.add("testImplementation", libs.findLibrary("junit-jupiter").get())
    dependencies.add("testRuntimeOnly", libs.findLibrary("junit-platform-launcher").get())
    tasks.withType<KotlinCompile>().configureEach {
        compilerOptions.allWarningsAsErrors.set(true)
    }
}
