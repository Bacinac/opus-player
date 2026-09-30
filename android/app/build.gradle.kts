plugins {
    id("opus.application")
}

android {
    namespace = "biz.boskovic.opus.player"
    defaultConfig {
        applicationId = "biz.boskovic.opus.player"
    }
    testOptions.unitTests.all {
        it.jvmArgs("--enable-native-access=ALL-UNNAMED", "--sun-misc-unsafe-memory-access=allow")
    }
}

dependencies {
    implementation(project(":core"))
    implementation(libs.media3.exoplayer)
    implementation(libs.media3.datasource.okhttp)
    implementation(libs.media3.ui)
    implementation(libs.media3.session)
    implementation(libs.androidx.webkit)
    testImplementation(libs.graalvm.polyglot)
    testRuntimeOnly(libs.graalvm.js)
}
