[app]
title = Tv Launcher
package.name = tvlauncher
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav
source.include_dir = assets
version = 1.4.2
requirements = python3,pygame,requests,pyqt6
orientation = landscape
fullscreen = 1
android.permissions = INTERNET
android.accept_sdk_license = True

# Добавьте эти строки для принудительного использования стабильной ветки p4a
android.branch = master
p4a.fork = kivy
p4a.branch = master

