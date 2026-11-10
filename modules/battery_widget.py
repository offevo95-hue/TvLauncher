import psutil
from pathlib import Path


_DEBUG_BATTERY = False
_DEBUG_PERCENT  = 80      # процент для симуляции
_DEBUG_CHARGING = False   # True = симуляция зарядки

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer


# Пороговые значения процентов
THRESHOLD_LOW  = 30
THRESHOLD_FULL = 50

# Имена файлов иконок (в assets/icons/)
ICON_CHARGING = "battery_charging.png"
ICON_FULL     = "battery_full.png"
ICON_MID      = "battery_mid.png"
ICON_LOW      = "battery_low.png"

# Запасные эмодзи (fallback), если иконка не существует
EMOJI_CHARGING = "🔌"
EMOJI_FULL     = "🔋"
EMOJI_MID      = "🔋"
EMOJI_LOW      = "🪫"


def _pick_icon_name(percent: int, charging: bool) -> str:
    if charging:
        return ICON_CHARGING
    if percent >= THRESHOLD_FULL:
        return ICON_FULL
    if percent >= THRESHOLD_LOW:
        return ICON_MID
    return ICON_LOW


def _pick_emoji(percent: int, charging: bool) -> str:
    if charging:
        return EMOJI_CHARGING
    if percent >= THRESHOLD_FULL:
        return EMOJI_FULL
    if percent >= THRESHOLD_LOW:
        return EMOJI_MID
    return EMOJI_LOW


def _pick_color(percent: int, charging: bool) -> str:
    if charging:
        return "#4CAF50"   # зеленый
    if percent < THRESHOLD_LOW:
        return "#ff4a4a"   # красный
    if percent < THRESHOLD_FULL:
        return "#FFA500"   # оранжевый
    return "#aaaaaa"       # нейтральный серый


class BatteryWidget(QWidget):
   

    def __init__(self, scaling, icon_dir="assets/icons", refresh_ms=60_000, parent=None):
        super().__init__(parent)
        self.scaling   = scaling
        self.icon_dir  = Path(icon_dir)
        self.refresh_ms = refresh_ms

        self._build_ui()
        self._refresh()
        self._last_charging = None  # Предыдущее состояние зарядки

        # Основной таймер: обновление всего каждые refresh_ms
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(self.refresh_ms)

        # Быстрый таймер: проверка подключения/отключения кабеля каждую секунду
        self._plug_timer = QTimer(self)
        self._plug_timer.timeout.connect(self._check_plug_change)
        self._plug_timer.start(1_000)

   

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaling.scale(8))
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._icon_label = QLabel()
        self._icon_label.setStyleSheet("background: transparent; border: none;")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)

        self._pct_label = QLabel()
        self._pct_label.setStyleSheet(
            f"background: transparent; border: none; "
            f"font-size: {self.scaling.scale_font(23)}px; font-weight: bold; color: #aaaaaa;"
        )
        self._pct_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self._icon_label)
        layout.addWidget(self._pct_label)

    

    @staticmethod
    def battery_available() -> bool:
        """Возвращает True, если присутствует батарея (реальная или в режиме отладки)."""
        return _DEBUG_BATTERY or psutil.sensors_battery() is not None

    def _check_plug_change(self):
        """Проверяет, изменилось ли состояние зарядного устройства, и сразу обновляет данные."""
        if _DEBUG_BATTERY:
            return
        battery = psutil.sensors_battery()
        if battery is None:
            return
        current_charging = battery.power_plugged
        if self._last_charging is not None and current_charging != self._last_charging:
            self._refresh()  # Немедленное обновление
        self._last_charging = current_charging

    def _refresh(self):
        if _DEBUG_BATTERY:
            percent  = _DEBUG_PERCENT
            charging = _DEBUG_CHARGING
        else:
            battery = psutil.sensors_battery()
            if battery is None:
                self.hide()
                return
            percent  = int(battery.percent)
            charging = battery.power_plugged

        self._update_icon(percent, charging)
        self._update_label(percent, charging)
        self._last_charging = charging
        self.show()

    def _update_icon(self, percent: int, charging: bool):
        from PyQt6.QtGui import QPixmap

        icon_name = _pick_icon_name(percent, charging)
        icon_path = self.icon_dir / icon_name
        size      = self.scaling.scale(33)

        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                self._icon_label.setPixmap(
                    pixmap.scaled(
                        size, size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self._icon_label.setFixedSize(size, size)
                return

        # Резервный вариант (Fallback): эмодзи
        self._icon_label.setText(_pick_emoji(percent, charging))
        self._icon_label.setStyleSheet(
            f"background: transparent; border: none; "
            f"font-size: {self.scaling.scale_font(20)}px;"
        )

    def _update_label(self, percent: int, charging: bool):
        color = _pick_color(percent, charging)
        suffix = " " if charging else ""
        self._pct_label.setText(f"{percent}%{suffix}")
        self._pct_label.setStyleSheet(
            f"background: transparent; border: none; "
            f"font-size: {self.scaling.scale_font(23)}px; font-weight: bold; color: {color};"
        )

   

    def cleanup(self):
        """Останавливает таймеры. Вызывать перед закрытием."""
        if self._timer.isActive():
            self._timer.stop()
        if self._plug_timer.isActive():
            self._plug_timer.stop()

