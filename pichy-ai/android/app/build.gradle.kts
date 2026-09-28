plugins {
    id("com.android.application")
}

android {
    namespace = "com.pichy.ai"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.pichy.ai"
        minSdk = 33
        targetSdk = 36
        versionCode = 10
        versionName = "0.5.0-local-lab"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}


dependencies {
    implementation(project(":local-llama"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
}
