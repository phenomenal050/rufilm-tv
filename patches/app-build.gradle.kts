plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android") version "2.2.20"
}

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
        versionCode = 129
        versionName = "3.1.1-beta.80-mpv"
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
    implementation("io.github.yuroyami:libmpv-kmp-view:0.4.0")
}

// beta.69: reject OK.ru placeholder stream before Media3 handoff
