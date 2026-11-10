"""
Модуль оконного менеджера (Window Manager)
Управление сворачиванием/восстановлением лаунчера при запуске приложений
"""

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


class WindowManager:
  """Управление состоянием окна лаунчера"""

  def __init__(self, launcher):
    self.launcher = launcher
    self.was_minimized = False

  def should_minimize(self):
    """Проверяет, нужно ли сворачивать лаунчер при запуске приложения"""
    # Сворачиваем ТОЛЬКО если параметр «Всегда во весь экран» ОТКЛЮЧЕН
    return not self.launcher.config_data.get("fullscreen", True)

  def on_app_launch(self):
    """Вызывается при запуске приложения"""
    if self.should_minimize():
      self.was_minimized = True
      self.launcher.showMinimized()
    else:
      self.was_minimized = False

  def on_app_close(self):
    """Вызывается при закрытии приложения"""
    if self.was_minimized:
      # Восстанавливаем окно в ПОЛНОЭКРАННОМ режиме (не normal)
      self.launcher.showFullScreen()

      # На некоторых платформах требуется задержка, чтобы окно гарантированно вернулось на передний план
      QTimer.singleShot(100, self._ensure_foreground)

      self.was_minimized = False

  def _ensure_foreground(self):
    """Гарантирует, что лаунчер возвращается на передний план"""
    self.launcher.raise_()
    self.launcher.activateWindow()
    self.launcher.setFocus()

