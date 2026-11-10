from pathlib import Path
from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QSoundEffect


class SoundManager:
  """Управление звуками навигации лаунчера"""

  def __init__(self, enabled=False):
    self.enabled = enabled
    self.sounds = {}
    self.assets_dir = Path("assets/sounds")
    self.assets_dir.mkdir(exist_ok=True)

    # Загрузка доступных звуков
    self._load_sounds()

  def _load_sounds(self):
    """Загружает все аудиофайлы из папки assets/sounds"""
    sound_files = {
        "navigate": "navigate.wav",  # Перемещение вверх/вниз/влево/вправо
        "select": "select.wav",  # Подтверждение/Enter
        "back": "back.wav",  # Esc/Назад
    }

    for sound_name, filename in sound_files.items():
      sound_path = self.assets_dir / filename
      if sound_path.exists():
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(str(sound_path.absolute())))
        effect.setVolume(0.4)  # Громкость по умолчанию 80% (примечание: 0.4 — это 40%)
        self.sounds[sound_name] = effect

  def play(self, sound_name):
    """Воспроизводит звук, если они включены"""
    if not self.enabled:
      return

    if sound_name in self.sounds:
      self.sounds[sound_name].play()

  def set_enabled(self, enabled):
    """Включает/отключает звуки"""
    self.enabled = enabled

  def set_volume(self, volume):
    """Устанавливает общую громкость (от 0.0 до 1.0)"""
    for sound in self.sounds.values():
      sound.setVolume(volume)

  # Удобные методы для вызова
  def navigate(self):
    self.play("navigate")

  def select(self):
    self.play("select")

  def back(self):
    self.play("back")

