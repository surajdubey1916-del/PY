[app]
title = FitMate
package.name = fitnessapp
package.domain = org.suraj
source.dir = .
source.include_exts = py,kv,db,png,jpg,sqlite3,mp4
version = 1.0
requirements = python3,kivy,sqlite3
orientation = portrait
fullscreen = 1
android.api = 30
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
android.permissions = INTERNET
android.extra_args = 

[buildozer]
log_level = 2
warn_on_root = 1
