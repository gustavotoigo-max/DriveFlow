plugins {
    id("com.android.application")
    id("com.google.gms.google-services")
}
android {
    namespace = "com.driveflow.monitor"
    compileSdk { version = release(36) { minorApiLevel = 1 } }
    buildToolsVersion = "36.1.0"
    defaultConfig {
        applicationId = "com.driveflow.monitor"
        minSdk = 26
        targetSdk = 36
        versionCode = 4
        versionName = "0.2.2"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
dependencies {
    implementation(platform("com.google.firebase:firebase-bom:34.11.0"))
    implementation("com.google.firebase:firebase-auth")
    implementation("com.google.firebase:firebase-firestore")
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
    testImplementation("junit:junit:4.13.2")
}
