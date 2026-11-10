[app]
title = Tv Launcher
package.name = tvlauncher
package.domain = org.example

# Обязательный параметр: указывает, что исходный код в текущей папке
source.dir = .

source.include_exts = py,png,jpg,kv,atlas,wav
source.include_dir = assets
version = 1.4.2
requirements = python3,pygame,requests,pyqt6
orientation = landscape
fullscreen = 1
android.permissions = INTERNET
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1

