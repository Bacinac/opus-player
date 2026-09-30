plugins {
    `kotlin-dsl`
}

dependencies {
    implementation(libs.android.gradle)
    implementation(libs.kotlin.gradle)
}

gradlePlugin {
    plugins {
        register("opusApplication") {
            id = "opus.application"
            implementationClass = "OpusApplicationPlugin"
        }
        register("opusLibrary") {
            id = "opus.library"
            implementationClass = "OpusLibraryPlugin"
        }
    }
}
