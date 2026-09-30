plugins {
    id("opus.library")
}

android {
    namespace = "biz.boskovic.opus.core"
    buildFeatures {
        buildConfig = true
    }
    defaultConfig {
        val host = providers.gradleProperty("opusHost").orNull
            ?: error("opusHost is not set: build through android/build.sh, which takes it from keystore/keystore.properties")
        buildConfigField("String", "OPUS_ORIGIN", "\"https://$host\"")
    }
}

dependencies {
    api(libs.androidx.core)
    api(libs.androidx.activity)
    api(libs.androidx.lifecycle.runtime)
    api(libs.okhttp)
    api(libs.coroutines.android)
    testImplementation(libs.mockwebserver)
}
