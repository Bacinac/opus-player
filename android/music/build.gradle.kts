plugins {
    id("opus.application")
}

android {
    namespace = "biz.boskovic.opus.music"
    defaultConfig {
        applicationId = "biz.boskovic.opus.music"
    }
}

dependencies {
    implementation(project(":core"))
    implementation(libs.media3.exoplayer)
    implementation(libs.media3.session)
    implementation(libs.media3.datasource)
    implementation(libs.media3.datasource.okhttp)
    implementation(libs.media3.database)
    implementation(libs.coroutines.guava)
}
