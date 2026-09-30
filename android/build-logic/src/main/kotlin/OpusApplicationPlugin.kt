import com.android.build.api.dsl.ApplicationExtension
import java.util.Properties
import org.gradle.api.GradleException
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.configure

class OpusApplicationPlugin : Plugin<Project> {
    override fun apply(project: Project) = with(project) {
        pluginManager.apply("com.android.application")
        val code = providers.gradleProperty("$name.versionCode").orNull?.toInt()
            ?: throw GradleException("$name.versionCode is not set; build through android/build.sh")
        val version = providers.gradleProperty("$name.versionName").orNull
            ?: throw GradleException("$name.versionName is not set; build through android/build.sh")

        extensions.configure<ApplicationExtension> {
            opusAndroid(this)
            defaultConfig {
                targetSdk = libs.number("targetSdk")
                versionCode = code
                versionName = version
            }
            signingConfigs {
                create("release") {
                    val file = rootProject.file("keystore/keystore.properties")
                    if (file.exists()) {
                        val keys = Properties().apply { file.inputStream().use { load(it) } }
                        storeFile = rootProject.file(keys.getProperty("storeFile"))
                        storePassword = keys.getProperty("storePassword")
                        keyAlias = keys.getProperty("keyAlias")
                        keyPassword = keys.getProperty("keyPassword")
                    }
                }
            }
            buildTypes {
                release {
                    isMinifyEnabled = true
                    isShrinkResources = true
                    proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
                    file("proguard-rules.pro").takeIf { it.exists() }?.let { proguardFiles(it) }
                    signingConfig = signingConfigs.getByName("release")
                }
            }
        }
    }
}
