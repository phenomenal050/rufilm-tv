plugins { id("com.android.application") }
android {
    namespace = "tv.rufilm.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "tv.rufilm.app"
        minSdk = 23
        targetSdk = 28
        versionCode = 17
        versionName = "3.0.1"
    }
}

dependencies {
    implementation("androidx.annotation:annotation:1.9.1")
    implementation("androidx.media3:media3-exoplayer:1.5.1")
    implementation("androidx.media3:media3-exoplayer-hls:1.5.1")
    implementation("androidx.media3:media3-exoplayer-dash:1.5.1")
    implementation("androidx.media3:media3-ui:1.5.1")
}
