plugins { id("com.android.application") }

val stableKeystorePath = System.getenv("ANDROID_KEYSTORE_PATH")
val stableKeystorePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
val stableKeyAlias = System.getenv("ANDROID_KEY_ALIAS")
val stableKeyPassword = System.getenv("ANDROID_KEY_PASSWORD")
val hasStableSigning = !stableKeystorePath.isNullOrBlank() &&
    !stableKeystorePassword.isNullOrBlank() &&
    !stableKeyAlias.isNullOrBlank() &&
    !stableKeyPassword.isNullOrBlank()

android {
    namespace = "tv.rufilm.app"
    compileSdk = 35

    lint {
        disable += "ExpiredTargetSdkVersion"
    }

    defaultConfig {
        applicationId = "tv.rufilm.app"
        minSdk = 23
        targetSdk = 28
        versionCode = 130
        versionName = "3.1.1-beta.81"
    }

    if (hasStableSigning) {
        signingConfigs {
            create("stable") {
                storeFile = file(stableKeystorePath!!)
                storePassword = stableKeystorePassword
                keyAlias = stableKeyAlias
                keyPassword = stableKeyPassword
            }
        }
    }

    buildTypes {
        getByName("debug") {
            if (hasStableSigning) signingConfig = signingConfigs.getByName("stable")
        }
        getByName("release") {
            isMinifyEnabled = false
            if (hasStableSigning) signingConfig = signingConfigs.getByName("stable")
        }
    }
}

dependencies {
    implementation("androidx.annotation:annotation:1.9.1")
    implementation("androidx.core:core:1.15.0")
    implementation("androidx.webkit:webkit:1.12.1")
    implementation("androidx.media3:media3-exoplayer:1.5.1")
    implementation("androidx.media3:media3-exoplayer-hls:1.5.1")
    implementation("androidx.media3:media3-exoplayer-dash:1.5.1")
    implementation("androidx.media3:media3-ui:1.5.1")
}

// beta.69: reject OK.ru placeholder stream before Media3 handoff
