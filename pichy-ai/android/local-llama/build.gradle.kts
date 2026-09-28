plugins {
    id("com.android.library")
}

android {
    namespace = "com.arm.aichat"
    compileSdk = 36
    ndkVersion = "29.0.14206865"

    defaultConfig {
        minSdk = 28

        ndk {
            abiFilters += listOf("arm64-v8a")
        }

        externalNativeBuild {
            cmake {
                arguments += listOf(
                    "-DCMAKE_BUILD_TYPE=Release",
                    "-DCMAKE_MESSAGE_LOG_LEVEL=STATUS",
                    "-DBUILD_SHARED_LIBS=ON",
                    "-DLLAMA_BUILD_APP=OFF",
                    "-DLLAMA_BUILD_COMMON=ON",
                    "-DLLAMA_OPENSSL=OFF",
                    "-DGGML_NATIVE=OFF",
                    "-DGGML_BACKEND_DL=ON",
                    "-DGGML_CPU_ALL_VARIANTS=ON",
                    "-DGGML_LLAMAFILE=OFF"
                )
            }
        }
    }

    sourceSets {
        getByName("main") {
            manifest.srcFile("../vendor/llama.cpp/examples/llama.android/lib/src/main/AndroidManifest.xml")
        }
    }

    externalNativeBuild {
        cmake {
            path = file("../vendor/llama.cpp/examples/llama.android/lib/src/main/cpp/CMakeLists.txt")
            version = "3.31.6"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.datastore:datastore-preferences:1.2.0")
}
