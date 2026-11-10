import json
from pathlib import Path
import re
import urllib.error
import urllib.request

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QThread,
    QUrl,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


# Текущая версия


LAUNCHER_VERSION = "1.4.2"


#  Константы GitHub 

GITHUB_OWNER = "Darkvinx88"
GITHUB_REPO = "TvLauncher"
RELEASES_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
REQUEST_TIMEOUT = 8


#  Реестр активных уведомлений 

_active_notifications: dict = {}

# Константы макета (логические пиксели, затем масштабируются во время выполнения)
_SLOT_HEIGHT_BASE = 73  # высота одной JoystickNotification
_SLOT_GAP_BASE = 8  # вертикальный отступ между двумя уведомлениями
_MARGIN_BOTTOM = 94  # такой же нижний отступ, как у JoystickNotification
_MARGIN_RIGHT = 15


#  Утилита для работы с версиями 


def _parse_version(tag: str) -> tuple:
  tag = tag.lstrip("vV").strip()
  parts = re.findall(r"\d+", tag)
  return tuple(int(p) for p in parts) if parts else (0,)


def _is_newer(latest_tag: str, current_version: str) -> bool:
  return _parse_version(latest_tag) > _parse_version(current_version)


#  Расчет позиции 


def _compute_position(widget: QWidget, slot: int, scaling) -> tuple:
  def s(v):
    return scaling.scale(v) if scaling else v

  screen = QApplication.primaryScreen()
  if screen:
    geo = screen.geometry()
    sw, sh = geo.width(), geo.height()
  elif widget.parent():
    r = widget.parent().geometry()
    sw, sh = r.width(), r.height()
  else:
    sw, sh = 1920, 1080

  x = sw - widget.width() - s(_MARGIN_RIGHT)
  y = (
      sh
      - widget.height()
      - s(_MARGIN_BOTTOM)
      - slot * (s(_SLOT_HEIGHT_BASE) + s(_SLOT_GAP_BASE))
  )
  return x, y


#  Рабочий поток (Worker thread) 


class _UpdateCheckWorker(QThread):

  update_available = pyqtSignal(str, str)  # (latest_tag, release_url)
  check_failed = pyqtSignal(str)

  def __init__(self, current_version: str):
    super().__init__()
    self.current_version = current_version

  def run(self):
    try:
      req = urllib.request.Request(
          RELEASES_API,
          headers={
              "Accept": "application/vnd.github+json",
              "User-Agent": f"{GITHUB_REPO}-updater/1.0",
          },
      )
      with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))

      latest_tag = data.get("tag_name", "")
      release_url = data.get(
          "html_url",
          f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest",
      )

      if not latest_tag:
        self.check_failed.emit("В ответе API отсутствует tag_name")
        return

      if _is_newer(latest_tag, self.current_version):
        self.update_available.emit(latest_tag, release_url)

    except urllib.error.URLError as e:
      self.check_failed.emit(f"Сеть недоступна: {e}")
    except Exception as e:
      self.check_failed.emit(f"Непредвиденная ошибка: {e}")


#  Toast-уведомление 


class UpdateNotification(QWidget):

  def __init__(self, parent=None, scaling=None):
    super().__init__(parent)
    self.scaling = scaling
    self._release_url = ""

    self.setWindowFlags(
        Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.Tool
        | Qt.WindowType.WindowStaysOnTopHint
    )
    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    # Размеры: контент 280x82 + отступ тени 10px с каждой стороны
    shadow_margin = self._s(10)
    self.notification_width = self._s(280) + shadow_margin * 2
    self.notification_height = self._s(82) + shadow_margin * 2
    self.setFixedSize(self.notification_width, self.notification_height)

    self._setup_ui()

    self.hide_timer = QTimer()
    self.hide_timer.setSingleShot(True)
    self.hide_timer.timeout.connect(self.hide_notification)

    self.opacity_effect = QGraphicsOpacityEffect()
    self.setGraphicsEffect(self.opacity_effect)
    self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
    self.fade_animation.setDuration(300)

  #  Масштабирование 

  def _s(self, v):
    return self.scaling.scale(v) if self.scaling else v

  def _sf(self, v):
    return self.scaling.scale_font(v) if self.scaling else v

  # Пользовательский интерфейс (UI)

  def _setup_ui(self):
    shadow_margin = self._s(10)
    main_layout = QHBoxLayout(self)
    main_layout.setContentsMargins(
        shadow_margin, shadow_margin, shadow_margin, shadow_margin
    )

    # Контейнер 
    self.container = QWidget()
    self.container.setCursor(Qt.CursorShape.PointingHandCursor)
    self.container.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: {self._s(2)}px solid #444;
                border-radius: {self._s(16)}px;
            }}
        """)

    inner = QHBoxLayout(self.container)
    inner.setContentsMargins(
        self._s(15), self._s(12), self._s(15), self._s(12)
    )
    inner.setSpacing(self._s(12))

    # Иконка — загружает assets/icons/update.png, фоллбэк на эмодзи
    self.icon_label = QLabel()
    self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_size = self._s(48)
    self.icon_label.setFixedSize(icon_size, icon_size)
    self.icon_label.setScaledContents(True)
    self.icon_label.setStyleSheet("background: transparent; border: none;")

    icon_path = Path("assets/icons/update.png")
    if icon_path.exists():
      from PyQt6.QtGui import QPixmap

      self.icon_label.setPixmap(QPixmap(str(icon_path)))
    else:
      # Фоллбэк-эмодзи, если файл отсутствует
      self.icon_label.setText("🔄")
      self.icon_label.setScaledContents(False)
      self.icon_label.setStyleSheet(f"""
                QLabel {{
                    color: white;
                    font-size: {self._sf(28)}px;
                    background: transparent;
                    border: none;
                }}
            """)

    inner.addWidget(self.icon_label)

    # Текст: заголовок + версия со стрелкой + подсказка клика
    text_layout = QVBoxLayout()
    text_layout.setSpacing(self._s(2))
    text_layout.setContentsMargins(0, 0, 0, 0)

    self.title_label = QLabel("Доступно обновление!")
    self.title_label.setStyleSheet(f"""
            QLabel {{
                color: #4fc3f7;
                font-size: {self._sf(13)}px;
                font-weight: 700;
                background: transparent;
                border: none;
            }}
        """)

    self.version_label = QLabel("")
    self.version_label.setStyleSheet(f"""
            QLabel {{
                color: #cccccc;
                font-size: {self._sf(11)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)

    self.click_label = QLabel("Нажмите, чтобы открыть страницу релиза")
    self.click_label.setStyleSheet(f"""
            QLabel {{
                color: #888888;
                font-size: {self._sf(10)}px;
                background: transparent;
                border: none;
            }}
        """)

    text_layout.addWidget(self.title_label)
    text_layout.addWidget(self.version_label)
    text_layout.addWidget(self.click_label)
    inner.addLayout(text_layout, 1)

    main_layout.addWidget(self.container)

    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(self._s(18))
    shadow.setColor(QColor(0, 0, 0, 160))
    shadow.setOffset(0, self._s(4))
    self.container.setGraphicsEffect(shadow)

  #  Расположение 

  def _current_slot(self) -> int:
    """0 = снизу, 1 = сверху. Зависит от видимости джойстика."""
    try:
      from modules.joystick_notification import JoystickNotification

      joy = _active_notifications.get(JoystickNotification)
      if joy and joy.isVisible():
        return 1
    except ImportError:
      pass
    return 0

  def _reposition(self, slot: int = None):
    """Перемещает виджет в правильную позицию (с указанием слота или без)."""
    if slot is None:
      slot = self._current_slot()
    x, y = _compute_position(self, slot, self.scaling)
    self.move(x, y)

  #  Публичные методы 

  def show_notification(
      self, latest_tag: str, current_version: str, release_url: str
  ):
    self._release_url = release_url
    self.version_label.setText(f"v{current_version.lstrip('vV')}  →  {latest_tag}")

    _active_notifications[UpdateNotification] = self
    self._reposition()

    self.opacity_effect.setOpacity(0.0)
    self.show()
    self.raise_()

    self.fade_animation.stop()
    self.fade_animation.setStartValue(0.0)
    self.fade_animation.setEndValue(1.0)
    self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    self.fade_animation.start()

    self.hide_timer.start(8000)

  def hide_notification(self):
    self.hide_timer.stop()
    self.fade_animation.stop()
    self.fade_animation.setStartValue(1.0)
    self.fade_animation.setEndValue(0.0)
    self.fade_animation.setEasingCurve(QEasingCurve.Type.InCubic)

    try:
      self.fade_animation.finished.disconnect()
    except (RuntimeError, TypeError):
      pass

    def _on_hidden():
      self.hide()
      _active_notifications.pop(UpdateNotification, None)

    self.fade_animation.finished.connect(_on_hidden)
    self.fade_animation.start()

  # Открытие ссылки в браузере по клику 

  def mousePressEvent(self, event):
    if self._release_url:
      QDesktopServices.openUrl(QUrl(self._release_url))
    self.hide_notification()
    super().mousePressEvent(event)


def _patch_joystick_notification():
  try:
    from modules.joystick_notification import JoystickNotification
  except ImportError:
    return

  if getattr(JoystickNotification, "_update_patched", False):
    return

  _orig_show = JoystickNotification.show_notification

  def _patched_show(self, message, is_connected=True):
    _orig_show(self, message, is_connected)
    _active_notifications[JoystickNotification] = self

    # Если уведомление об обновлении уже отображается, сдвигаем его вверх (слот 1)
    upd = _active_notifications.get(UpdateNotification)
    if upd and upd.isVisible():
      upd._reposition(slot=1)

  JoystickNotification.show_notification = _patched_show

  _orig_hide = JoystickNotification.hide_notification

  def _patched_hide(self):
    _orig_hide(self)

    # После затухания джойстика (300 мс) возвращаем уведомление об обновлении в слот 0
    def _after_joystick_gone():
      _active_notifications.pop(JoystickNotification, None)
      upd = _active_notifications.get(UpdateNotification)
      if upd and upd.isVisible():
        upd._reposition(slot=0)

    QTimer.singleShot(320, _after_joystick_gone)

  JoystickNotification.hide_notification = _patched_hide

  JoystickNotification._update_patched = True


# Применяем патч в момент импорта
_patch_joystick_notification()


def check_for_updates(parent, scaling=None):
  current_version = LAUNCHER_VERSION
  worker = _UpdateCheckWorker(current_version)

  def _on_update(latest_tag: str, release_url: str):
    # Сохраняем данные в лаунчере: settings_menu считывает их для отображения
    # постоянной кнопки обновления при каждом открытии меню
    parent._update_info = {
        "latest_tag": latest_tag,
        "release_url": release_url,
        "current_version": current_version,
    }
    notification = UpdateNotification(parent, scaling)
    notification.show_notification(latest_tag, current_version, release_url)
    parent._update_notification = notification  # сохраняем живую ссылку

  def _on_fail(error_msg: str):
    print(f"[UpdateChecker] {error_msg}")

  worker.update_available.connect(_on_update)
  worker.check_failed.connect(_on_fail)
  parent._update_worker = worker
  worker.start()

