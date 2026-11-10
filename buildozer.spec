[app]

# (str) Title of your application
title = Tv Launcher

# (str) Package name
package.name = tvlauncher

# (str) Package domain (needed for android packaging)
package.domain = org.example

# (str) Source files where the let of data is located
source.dir = .

# (list) Source files to include (let it empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,wav

# (list) List of inclusions
source.include_dir = assets

# (str) Application versioning
version = 1.4.2

# (list) Application requirements
# Убрали pyqt6, оставили то, что поддерживается на Android:
requirements = python3,pygame,requests

# (str) Supported orientations
orientation = landscape

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 1

# (list) Permissions
android.permissions = INTERNET

# (bool) Automatically accept SDK license
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1

