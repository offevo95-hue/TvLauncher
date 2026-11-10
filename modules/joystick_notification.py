from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QPixmap, QIcon, QScreen, QColor
from PyQt6.QtWidgets import QApplication
from pathlib import Path


class JoystickNotification(QWidget):
    """Всплывающее уведомление (toast) о подключении/отключении джойстика с единой палитрой"""
    
    def __init__(self, parent=None, scaling=None):
        super().__init__(parent)
        self.scaling = scaling
        
        # Конфигурация окна
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Масштабированные размеры (компактный прямоугольник)
        self.notification_width = self.scaling.scale(240) if scaling else 240
        self.notification_height = self.scaling.scale(73) if scaling else 73
        
        self.setFixedSize(self.notification_width, self.notification_height)
        
        # Настройка интерфейса
        self.setup_ui()
        
        # Таймер для автоскрытия
        self.hide_timer = QTimer()
        self.hide_timer.timeout.connect(self.hide_notification)
        
        # Анимации
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")

  
    def setup_ui(self):
        """Создает интерфейс уведомления с унифицированной палитрой"""
        # Внешний прозрачный компоновщик
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Контейнер с фоном — УНИФИЦИРОВАННАЯ ПАЛИТРА
        self.container = QWidget()
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: {self.scaling.scale(2) if self.scaling else 2}px solid #444;
                border-radius: {self.scaling.scale(16) if self.scaling else 16}px;
            }}
        """)
        
        # Внутренний компоновщик контейнера
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(
            self.scaling.scale(15) if self.scaling else 15,
            self.scaling.scale(12) if self.scaling else 12,
            self.scaling.scale(15) if self.scaling else 15,
            self.scaling.scale(12) if self.scaling else 12
        )
        layout.setSpacing(self.scaling.scale(12) if self.scaling else 12)
        
        # Иконка джойстика
        self.icon_label = QLabel()
        icon_size = self.scaling.scale(48) if self.scaling else 48
        self.icon_label.setFixedSize(icon_size, icon_size)
        self.icon_label.setScaledContents(True)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.icon_label)
        
        # Текст сообщения — УНИФИЦИРОВАННЫЕ ЦВЕТА И ЦЕНТРИРОВАНИЕ
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(14) if self.scaling else 14}px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self.message_label, 1)
        
        main_layout.addWidget(self.container)
        
        # Унифицированный эффект тени
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(self.scaling.scale(25) if self.scaling else 25)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, self.scaling.scale(8) if self.scaling else 8)
        self.container.setGraphicsEffect(shadow)
    
    def show_notification(self, message, is_connected=True):
        """
        Показывает уведомление
        
        Args:
            message: Текст для отображения
            is_connected: True для подключения, False для отключения
        """
        # Установка иконки
        icon_path = self._get_icon_path(is_connected)
        if icon_path and Path(icon_path).exists():
            pixmap = QPixmap(icon_path)
            self.icon_label.setPixmap(pixmap)
        else:
            # Запасной вариант (fallback): Unicode-эмодзи — УНИФИЦИРОВАННЫЕ ЦВЕТА
            self.icon_label.setText("🎮" if is_connected else "❌")
            self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.icon_label.setStyleSheet(f"""
                QLabel {{
                    color: white;
                    font-size: {self.scaling.scale_font(32) if self.scaling else 32}px;
                    background: transparent;
                    border: none;
                }}
            """)
        
        # Установка сообщения
        self.message_label.setText(message)
        
        # Позиционирование с использованием экрана
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            # Масштабированные отступы под разрешение
            margin_right = self.scaling.scale(15) if self.scaling else 15
            margin_bottom = self.scaling.scale(94) if self.scaling else 94
            
            x = screen_geometry.width() - self.width() - margin_right
            y = screen_geometry.height() - self.height() - margin_bottom
            
            self.move(x, y)
        elif self.parent():
            # Запасной вариант, если primaryScreen недоступен
            parent_rect = self.parent().geometry()
            margin = self.scaling.scale(25) if self.scaling else 25
            x = parent_rect.width() - self.notification_width - margin
            y = parent_rect.height() - self.notification_height - margin
            self.move(x, y)
        
        # Анимация появления (fade in)
        self.opacity_effect.setOpacity(0.0)
        self.show()
        
        self.fade_animation.stop()
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_animation.start()
        
        # Таймер для скрытия через 3 секунды
        self.hide_timer.stop()
        self.hide_timer.start(3000)
    
    def hide_notification(self):
        """Скрывает уведомление с анимацией исчезновения (fade out)"""
        self.fade_animation.stop()
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_animation.finished.connect(self.hide)
        self.fade_animation.start()
    
    def _get_icon_path(self, is_connected):
        """Возвращает путь к соответствующей иконке"""
        # Поиск в системных или пользовательских иконках
        base_paths = [
            "assets/icons/",
            "/usr/share/icons/",
            ""
        ]
        
        icon_name = "gamepad-connected.png" if is_connected else "gamepad-disconnected.png"
        
        for base in base_paths:
            icon_path = Path(base) / icon_name
            if icon_path.exists():
                return str(icon_path)
        
        return None


def show_joystick_connected(parent, joystick_name, scaling=None):
    """
    Вспомогательная функция для отображения уведомления о подключении джойстика
    
    Args:
        parent: Родительский виджет
        joystick_name: Название джойстика
        scaling: Объект ResponsiveScaling (необязательно)
    """
    parent.last_joystick_name = joystick_name
    notification = JoystickNotification(parent, scaling)
    notification.show_notification(
        f"Контроллер подключен\n{joystick_name}",
        is_connected=True
    )
    return notification


def show_joystick_disconnected(parent, joystick_name=None, scaling=None):
    """
    Вспомогательная функция для отображения уведомления об отключении джойстика
    Совместима с устаревшими вызовами (legacy)
    """

    # Если имя недействительно, восстанавливаем последнее сохраненное
    if not isinstance(joystick_name, str):
        joystick_name = getattr(parent, "last_joystick_name", "Неизвестный контроллер")

    notification = JoystickNotification(parent, scaling)
    notification.show_notification(
        f"Контроллер отключен\n{joystick_name}",
        is_connected=False
    )
    return notification

