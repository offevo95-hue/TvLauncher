from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QCheckBox, QDialog,
    QLineEdit, QFileDialog, QMessageBox, QRadioButton,
    QButtonGroup, QSlider
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, pyqtSignal, QTimer, QRectF, pyqtProperty, QSize
from PyQt6.QtGui import QIcon, QPainter, QColor, QPen, QPixmap, QFont, QFontMetrics
from pathlib import Path
import json
from modules.key_remapper import KeyRemapperDialog
from modules.weather_settings import add_weather_settings_to_menu
from modules.parental_control import integrate_parental_control

class ResetDialog(QDialog):
    """Диалоговое окно для выбора типа сброса (Мягкий/Полный)"""
    
    def __init__(self, launcher, scaling, parent=None):
        super().__init__(parent)
        self.launcher = launcher
        self.scaling = scaling
        self.selected_type = "soft"  
        
        self.setWindowTitle("Выберите тип сброса")
        self.setModal(True)
        self.setFixedSize(self.scaling.scale(550), self.scaling.scale(500))
        
        # Базовый стиль диалогового окна
        self.setStyleSheet("""
            QDialog { 
                background-color: #1a1a1a; 
            }
        """)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(self.scaling.scale(20))
        layout.setContentsMargins(
            self.scaling.scale(30), 
            self.scaling.scale(30), 
            self.scaling.scale(30), 
            self.scaling.scale(30)
        )
        
        # === СОЗДАНИЕ ГРУППЫ КНОПОК ===
        self.button_group = QButtonGroup(self)
        
        # Заголовок
        title = QLabel("🔄 Сброс конфигурации")
        title.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(20)}px; 
                font-weight: bold;
                color: white;
                background: transparent;
                border: none;
            }}
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Подзаголовок
        subtitle = QLabel("Выберите, что именно вы хотите сбросить:")
        subtitle.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(13)}px;
                color: #aaa;
                background: transparent;
                border: none;
            }}
        """)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        layout.addSpacing(self.scaling.scale(20))
        
        # === ВАРИАНТ 1: МЯГКИЙ СБРОС ===
        soft_container = self._create_option_container(
            "Мягкий сброс",
            "Сброс настроек до значений по умолчанию",
            [
                "✅ Приложения СОХРАНЕНЫ",
                "✅ Фон (оии) СОХРАНЕН", 
                "✅ API-ключ СОХРАНЕН",
                "🔄 Настройки сброшены по умолчанию"
            ],
            "soft"
        )
        layout.addWidget(soft_container)
        
        # Добавление в группу
        self.button_group.addButton(soft_container.radio)
        
        # === ВАРИАНТ 2: ПОЛНЫЙ СБРОС ===
        full_container = self._create_option_container(
            "Полный сброс",
            "Удаление ВСЕГО (сброс к заводским настройкам)",
            [
                "❌ ВСЕ приложения УДАЛЕНЫ",
                "❌ Фон УДАЛЕН",
                "❌ API-ключ УДАЛЕН",
                "❌ Все данные утеряны навсегда"
            ],
            "full"
        )
        layout.addWidget(full_container)
        
        # Добавление в группу
        self.button_group.addButton(full_container.radio)
        
        layout.addStretch()
        
        # Текущее количество приложений
        apps_count = len(self.launcher.apps) if self.launcher else 0
        info = QLabel(f"💡 Текущих приложений: {apps_count}")
        info.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(12)}px;
                color: #888;
                padding: {self.scaling.scale(10)}px;
                background-color: #2a2a2a;
                border-radius: {self.scaling.scale(6)}px;
                border: none;
            }}
        """)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        
        # Кнопки подтверждения/отмены
        button_layout = QHBoxLayout()
        button_layout.setSpacing(self.scaling.scale(15))
        
        self.ok_button = QPushButton("Продолжить")
        self.ok_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setStyleSheet(f"""
            QPushButton {{ 
                background-color: #2a2a2a; 
                color: white; 
                border: 2px solid #444; 
                padding: {self.scaling.scale(12)}px {self.scaling.scale(30)}px; 
                border-radius: {self.scaling.scale(8)}px; 
                font-size: {self.scaling.scale_font(14)}px; 
                font-weight: bold; 
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet(f"""
            QPushButton {{ 
                background-color: #2a2a2a; 
                color: white; 
                border: 2px solid #444; 
                padding: {self.scaling.scale(12)}px {self.scaling.scale(30)}px; 
                border-radius: {self.scaling.scale(8)}px; 
                font-size: {self.scaling.scale_font(14)}px; 
                font-weight: bold; 
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Навигация с клавиатуры
        self.confirm_buttons = [self.ok_button, self.cancel_button]
        self.confirm_index = [0]
        self.update_confirm_focus()
    
    def _create_option_container(self, title, description, details, option_type):
        """Создает контейнер для варианта сброса"""
        container = QWidget()
        container.setObjectName("resetContainer")  
        
        bg_color = "#2a2a2a" if option_type == "soft" else "#3a2020"
        border_color = "#4a9eff" if option_type == "soft" else "#ff4a4a"
        
        container.setStyleSheet(f"""
            QWidget#resetContainer {{
                background-color: {bg_color};
                border: 3px solid {border_color};
                border-radius: {self.scaling.scale(10)}px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QRadioButton {{
                background: transparent;
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(self.scaling.scale(10))
        layout.setContentsMargins(
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15)
        )
        
        # Радиокнопка + Заголовок
        radio = QRadioButton(title)
        radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)  
        radio.setStyleSheet(f"""
            QRadioButton {{
                font-size: {self.scaling.scale_font(16)}px;
                font-weight: bold;
                color: white;
                spacing: {self.scaling.scale(10)}px;
                background: transparent;
                border: none;
                outline: none;
            }}
            QRadioButton::indicator {{
                width: {self.scaling.scale(20)}px;
                height: {self.scaling.scale(20)}px;
                border: 2px solid #666;
                border-radius: {self.scaling.scale(10)}px;
                background-color: #1a1a1a;
            }}
            QRadioButton::indicator:checked {{
                background-color: {border_color};
                border-color: {border_color};
            }}
            QRadioButton::indicator:hover {{
                border-color: {border_color};
            }}
        """)
        
        if option_type == "soft":
            radio.setChecked(True)
        
        radio.toggled.connect(lambda checked: self._on_radio_toggled(option_type, checked))
        layout.addWidget(radio)
        
        # Описание
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(13)}px;
                color: #cccccc;
                font-weight: 500;
                padding-left: {self.scaling.scale(30)}px;
                background: transparent;
                border: none;
            }}
        """)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        layout.addSpacing(self.scaling.scale(5))
        
        # Детали
        for detail in details:
            detail_label = QLabel(detail)
            detail_label.setStyleSheet(f"""
                QLabel {{
                    font-size: {self.scaling.scale_font(12)}px;
                    color: #aaaaaa;
                    padding-left: {self.scaling.scale(30)}px;
                    background: transparent;
                    border: none;
                }}
            """)
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)
        
        container.radio = radio
        return container
    
    def _on_radio_toggled(self, option_type, checked):
        """Обновляет выбранный тип при переключении радиокнопки"""
        if checked:
            self.selected_type = option_type
    
    def get_reset_type(self):
        """Возвращает выбранный тип сброса"""
        return self.selected_type
    
    def update_confirm_focus(self):
        """Управляет фокусом на кнопках подтверждения"""
        for i, btn in enumerate(self.confirm_buttons):
            if i == self.confirm_index[0]:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #2a2a2a;
                        color: white;
                        border: 3px solid white;
                        padding: {self.scaling.scale(12)}px {self.scaling.scale(30)}px;
                        border-radius: {self.scaling.scale(8)}px;
                        font-size: {self.scaling.scale_font(14)}px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{ background-color: #3a3a3a; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #2a2a2a;
                        color: white;
                        border: 2px solid #444;
                        padding: {self.scaling.scale(12)}px {self.scaling.scale(30)}px;
                        border-radius: {self.scaling.scale(8)}px;
                        font-size: {self.scaling.scale_font(14)}px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{ background-color: #3a3a3a; }}
                """)
    
    def keyPressEvent(self, event):
        """Обрабатывает навигацию с клавиатуры/геймпада"""
        if event.isAutoRepeat():
            return
        
        key = event.key()
        
        if key == Qt.Key.Key_Left:
            self.confirm_index[0] = (self.confirm_index[0] - 1) % 2
            self.update_confirm_focus()
        elif key == Qt.Key.Key_Right:
            self.confirm_index[0] = (self.confirm_index[0] + 1) % 2
            self.update_confirm_focus()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.confirm_buttons[self.confirm_index[0]].click()
        elif key == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

class AnimatedToggle(QWidget):
    """Анимированный переключатель (Toggle switch) с бегунком"""
    
    def __init__(self, scaling, parent=None):
        super().__init__(parent)
        self.scaling = scaling
        self._checked = False
        self._circle_position = self.scaling.scale(4)
        
        width = self.scaling.scale(60)
        height = self.scaling.scale(32)
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Анимация перемещения круга
        self.animation = QPropertyAnimation(self, b"circle_position")
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(250)
        
    @pyqtProperty(float)
    def circle_position(self):
        return self._circle_position
    
    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()
    
    def isChecked(self):
        return self._checked
    
    def setChecked(self, checked):
        if self._checked == checked:
            return
        
        self._checked = checked
        
        # Анимация движения круга
        start_x = self.scaling.scale(4) if not checked else self.scaling.scale(32)
        end_x = self.scaling.scale(32) if checked else self.scaling.scale(4)
        
        self.animation.setStartValue(start_x)
        self.animation.setEndValue(end_x)
        self.animation.start()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Фоновая дорожка
        track_rect = QRectF(0, 0, self.width(), self.height())
        
        if self._checked:
            painter.setBrush(QColor(76, 175, 80))  # Зеленый, когда включено
        else:
            painter.setBrush(QColor(58, 58, 58))  # Серый, когда выключено
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, self.scaling.scale(16), self.scaling.scale(16))
        
        # Бегунок
        circle_y = self.scaling.scale(4)
        circle_diameter = self.scaling.scale(24)
        
        # Тень бегунка
        shadow_rect = QRectF(
            self._circle_position + self.scaling.scale(2), 
            circle_y + self.scaling.scale(2), 
            circle_diameter, 
            circle_diameter
        )
        painter.setBrush(QColor(0, 0, 0, 60))
        painter.drawEllipse(shadow_rect)
        
        # Белый круг
        circle_rect = QRectF(
            self._circle_position, 
            circle_y, 
            circle_diameter, 
            circle_diameter
        )
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(circle_rect)
        
        # Текст ON/OFF
        painter.setPen(QColor(255, 255, 255, 200))
        font = painter.font()
        font.setPixelSize(self.scaling.scale_font(10))
        font.setBold(True)
        painter.setFont(font)
        
        if self._checked:
            painter.drawText(QRectF(self.scaling.scale(8), 0, self.scaling.scale(20), self.height()), 
                           Qt.AlignmentFlag.AlignCenter, "ON")
        else:
            painter.drawText(QRectF(self.width() - self.scaling.scale(28), 0, self.scaling.scale(24), self.height()), 
                           Qt.AlignmentFlag.AlignCenter, "OFF")
    
    def mousePressEvent(self, event):
        self.setChecked(not self._checked)
        super().mousePressEvent(event)

class SettingsMenu(QWidget):
    """Боковое меню настроек со стилем, согласованным с лаунчером"""
    
    menu_closed = pyqtSignal()
    config_changed = pyqtSignal(dict)
    
    def __init__(self, scaling, parent=None):
        super().__init__(parent)
        self.scaling = scaling
        self.is_open = False
        self.current_index = 0
        self.menu_items = []
        self.launcher = None
        
        self.config = {
            'show_clock': True,
            'sound_effects': False,
            'fullscreen': True,
            'tile_glow': True,
            'auto_change_wallpaper': False,
            'carousel_vertical_position': 50,
        }
        
        self.init_ui()
        self.hide()
            
    def init_ui(self):
        """Инициализация интерфейса с единым стилем"""
        self.setFixedWidth(self.scaling.scale(420))
        
        # Основной стиль, согласованный со сканером программ
        self.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-left: 2px solid #444;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ШАПКА (HEADER)
        header = self._create_header()
        main_layout.addWidget(header)
        
        # ПРОКРУЧИВАЕМОЕ СОДЕРЖИМОЕ
        scroll = self._create_scroll_area()
        content = self._create_content()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # НИЖНЯЯ ПАНЕЛЬ (FOOTER)
        footer = self._create_footer()
        main_layout.addWidget(footer)
        
        self.update_focus()
        
    def _create_header(self):
        """Шапка в едином стиле"""
        header = QWidget()
        header.setFixedHeight(self.scaling.scale(100))
        header.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                border-bottom: 2px solid #444;
                border-left: none;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(
            self.scaling.scale(30), 
            self.scaling.scale(20), 
            self.scaling.scale(30), 
            self.scaling.scale(20)
        )
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        title = QLabel("⚙️ Настройки")
        title.setStyleSheet(f"""
            color: white;
            font-size: {self.scaling.scale_font(24)}px;
            font-weight: bold;
            background: transparent;
            border: none;
        """)
        layout.addWidget(title)
        layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(self.scaling.scale(40), self.scaling.scale(40))
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: white;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(20)}px;
                font-size: {self.scaling.scale_font(18)}px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        close_btn.clicked.connect(self.close_menu)
        layout.addWidget(close_btn)
        
        return header
        
    def _create_scroll_area(self):
        """Область прокрутки в едином стиле"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1a1a1a;
            }
            QScrollBar:vertical {
                background-color: #2a2a2a;
                width: 10px;
                border-radius: 5px;
                border: 1px solid #444;
            }
            QScrollBar::handle:vertical {
                background-color: #444;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        return scroll
        
    def _create_content(self):
        """Контент в едином стиле"""
        if self.menu_items:
             self.menu_items.clear()
        
        content = QWidget()
        content.setStyleSheet("QWidget { border: none; background-color: #1a1a1a; }")
        
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            self.scaling.scale(20), 
            self.scaling.scale(20), 
            self.scaling.scale(20), 
            self.scaling.scale(20)
        )
        layout.setSpacing(self.scaling.scale(15))
        
        # ДЕЙСТВИЯ (ACTIONS) 
        self._add_section_title(layout, "Быстрые действия")
        
        icon_dir = Path("assets/icons")
        
        actions = [
            ("API-ключ", "Установить ключ SteamGridDB", self._handle_api_key, icon_dir / "key.png"),
            ("Сканировать программы", "Найти установленные приложения", self._handle_scan, icon_dir / "search.png"),
            ("Добавить приложение", "Добавить приложение вручную", self._handle_add_app, icon_dir / "plus.png"),
            ("Загрузить обложки", "Получить изображения для существующих приложений", self._handle_download_covers, icon_dir / "download.png"),
            ("Установить фон", "Выбрать обои", self._handle_background, icon_dir / "image.png"),
        ]
        
        for title, desc, callback, icon_path in actions:
            btn = self._create_menu_button(title, desc, callback, str(icon_path))
            layout.addWidget(btn)
            self.menu_items.append(btn)

        # Видеообои (потоковые, в стиле Projectivy Overflight)
        from modules.video_wallpaper_dialog import add_video_wallpaper_button_to_settings
        add_video_wallpaper_button_to_settings(self, self.launcher, layout, self.menu_items, icon_dir)

        # ДОСТУПНО ОБНОВЛЕНИЕ (UPDATE AVAILABLE) 
        
        self.update_available_btn = self._create_menu_button(
            "Доступно обновление",
            "Проверка...",
            self._handle_open_update,
            str(icon_dir / "update.png")
        )
        self.update_available_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #1a3a4a;
                border: 2px solid #4fc3f7;
                border-radius: {self.scaling.scale(8)}px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #1e4a5e;
                border-color: #81d4fa;
            }}
        """)
        self.update_available_btn.setVisible(False)
        layout.addWidget(self.update_available_btn)
        self.menu_items.append(self.update_available_btn)

        
        # ВНЕШНИЙ ВИД (APPEARANCE)  
        layout.addSpacing(self.scaling.scale(20))
        self._add_section_title(layout, "Внешний вид")
        manage_cat_btn = self._create_menu_button(
            "Управление категориями",
            "Настройка имен, иконок и цветов",
            lambda: self._open_category_editor(),
            icon_dir / "folder.png"
        )
        layout.addWidget(manage_cat_btn)
        self.menu_items.append(manage_cat_btn)

        
        self.clock_toggle = self._create_toggle(
            "Показывать часы",
            "Отображать время и дату в шапке",
            self.config['show_clock'],
            lambda val: self._handle_toggle('show_clock', val),
            icon_dir / "clock.png"
        )
        layout.addWidget(self.clock_toggle)
        self.menu_items.append(self.clock_toggle)
        
        self.glow_toggle = self._create_toggle(
            "Эффект свечения плитки",
            "Плавное свечение выбранного приложения",
            self.config['tile_glow'],
            lambda val: self._handle_toggle('tile_glow', val),
            icon_dir / "star.png"  
        )
        layout.addWidget(self.glow_toggle)
        self.menu_items.append(self.glow_toggle)

        self.carousel_position_slider = self._create_slider(
            "Положение карусели",
            "Перемещение карусели выше или ниже на экране",
            self.config.get('carousel_vertical_position', 50),
            0, 100,
            lambda val: self._handle_carousel_position(val),
            icon_dir / "carousel.png",
            default_reset_value=50
        )
        layout.addWidget(self.carousel_position_slider)
        self.menu_items.append(self.carousel_position_slider)

        # Погода (Weather) 
        self.weather_btn = add_weather_settings_to_menu(self, self.launcher)
        layout.addWidget(self.weather_btn)
        self.menu_items.append(self.weather_btn)

        # ПОВЕДЕНИЕ (BEHAVIOR) 
        layout.addSpacing(self.scaling.scale(20))
        self._add_section_title(layout, "Поведение")
        
        self.sound_toggle = self._create_toggle(
            "Звуковые эффекты",
            "Воспроизводить звуки при навигации",
            self.config['sound_effects'],
            lambda val: self._handle_toggle('sound_effects', val),
            icon_dir / "sound.png"
        )
        layout.addWidget(self.sound_toggle)
        self.menu_items.append(self.sound_toggle)
        
        self.fullscreen_toggle = self._create_toggle(
            "Всегда во весь экран",
            "Полноэкранный режим / свертывание при запуске приложений",
            self.config['fullscreen'],
            lambda val: self._handle_toggle('fullscreen', val),
            icon_dir / "fullscreen.png"

        )
        layout.addWidget(self.fullscreen_toggle)
        self.menu_items.append(self.fullscreen_toggle)

        # Переключатель автосмены обоев
        self.wallpaper_toggle = self._create_toggle(
            "Автосмена обоев",
            "Случайные обои каждые 5 минут",
            self.config.get('auto_change_wallpaper', False),
            lambda val: self._handle_wallpaper_toggle(val),
            icon_dir / "wallpaper.png"
        )
        layout.addWidget(self.wallpaper_toggle)
        self.menu_items.append(self.wallpaper_toggle)
        
        # ДОПОЛНИТЕЛЬНО (ADVANCED) 
        layout.addSpacing(self.scaling.scale(20))
        self._add_section_title(layout, "Дополнительно")

        network_btn = self._create_menu_button(
            "Настройки сети",
            "Настройка Wi-Fi, Ethernet, Bluetooth",
            self._handle_network_settings,
            icon_dir / "wifi.png"
        )
        layout.addWidget(network_btn)
        self.menu_items.append(network_btn)

        # Переназначение кнопок (Key Remapper) 
        keyremap_btn = self._create_menu_button(
            "Назначение клавиш",
            "Настройка кнопок клавиатуры / пульта",
            self._handle_key_remapper,
            icon_dir / "remote.png"
        )
        layout.addWidget(keyremap_btn)
        self.menu_items.append(keyremap_btn)
        
        backup_btn = self._create_menu_button(
            "Резервная копия конфигурации",
            "Экспорт вашей конфигурации",
            self._handle_backup,
            icon_dir / "backup.png"
        )
        layout.addWidget(backup_btn)
        self.menu_items.append(backup_btn)
        
        restore_btn = self._create_menu_button(
            "Восстановить конфигурацию",
            "Импорт конфигурации",
            self._handle_restore,
            icon_dir / "restore.png"
        )
        layout.addWidget(restore_btn)
        self.menu_items.append(restore_btn)
        
        reset_btn = self._create_menu_button(
            "Сбросить настройки",
            "Восстановить настройки по умолчанию",
            self._handle_reset,
            icon_dir / "reset.png"
        )
        layout.addWidget(reset_btn)
        self.menu_items.append(reset_btn)

        self.parental_control_btn = self._create_menu_button(
            "Родительский контроль",
            "Не настроен",                    # начальное значение
            self._handle_parental_control,
            icon_dir / "lock.png"
        )

        # Сохраняем ссылки на QLabel для удобного обновления только описания
        self._parental_title_label = None
        self._parental_desc_label = None

        # Ищем два QLabel внутри кнопки
        for child in self.parental_control_btn.findChildren(QLabel):
            style = child.styleSheet()
            if "font-weight: bold" in style or "font-size" in style and "14px" in style:
                self._parental_title_label = child
            else:
                self._parental_desc_label = child

        layout.addWidget(self.parental_control_btn)
        self.menu_items.append(self.parental_control_btn)
        

        config_files_btn = self._create_menu_button(
            "Файлы конфигурации",
            "Открыть папку конфигурации",
            self._handle_open_config_folder,
            icon_dir / "config_files.png"
        )
        layout.addWidget(config_files_btn)
        self.menu_items.append(config_files_btn)
        
        # ИНФОРМАЦИЯ (INFO) 
        layout.addSpacing(self.scaling.scale(20))
        self._add_section_title(layout, "Информация")
        
        info_widget = self._create_info_widget()
        layout.addWidget(info_widget)

        if hasattr(info_widget, 'update_btn'):
            self.menu_items.append(info_widget.update_btn)
        
        layout.addStretch()
        
        return content

    def _handle_wallpaper_toggle(self, enabled):
        """Управляет переключателем автоматической смены обоев"""
        self.config['auto_change_wallpaper'] = enabled
        if self.launcher:
            self.launcher.toggle_wallpaper_rotation(enabled)
        self.config_changed.emit(self.config)
        
    def _create_effect_selector(self, title, description, default_value, icon_path=None):
        """Селектор с радиокнопками для эффектов плитки"""
        container = QWidget()
        container.setFixedHeight(self.scaling.scale(180))
        
        container.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(8)}px;
            }}
        """)
        
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(self.scaling.scale(8))
        main_layout.setContentsMargins(
            self.scaling.scale(15), 
            self.scaling.scale(10), 
            self.scaling.scale(15), 
            self.scaling.scale(10)
        )
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(self.scaling.scale(12))
        
        if icon_path and Path(icon_path).exists():
            icon_label = QLabel()
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.scaling.scale(40), 
                    self.scaling.scale(40), 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label.setPixmap(scaled_pixmap)
                icon_label.setFixedSize(self.scaling.scale(40), self.scaling.scale(40))
                icon_label.setStyleSheet("background: transparent; border: none;")
                header_layout.addWidget(icon_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(self.scaling.scale(3))
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(14)}px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            QLabel {{
                color: #aaa;
                font-size: {self.scaling.scale_font(12)}px;
                background: transparent;
                border: none;
            }}
        """)
        text_layout.addWidget(desc_label)
        
        header_layout.addLayout(text_layout)
        header_layout.addStretch()
        
        main_layout.addLayout(header_layout)
        
        # РАДИОКНОПКИ (RADIO) 
        radio_layout = QVBoxLayout()
        radio_layout.setSpacing(self.scaling.scale(5))
        radio_layout.setContentsMargins(self.scaling.scale(45), 0, 0, 0) 
        
        effects = [
            ("Нет", "none", "Без анимации"),
            ("Пульсация рамки", "border", "Тонкая пульсация рамки (рекомендуется)"),
            ("Эффект свечения", "glow", "Эффект затухания прозрачности"),
            ("Пульсация размера", "pulse", "Эффект изменения размера"),
        ]
        
        button_group = QButtonGroup(container)
        radio_buttons = []
        
        for name, effect_id, tooltip in effects:
            radio = QRadioButton(name)
            radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            radio.setToolTip(tooltip)
            
            radio.setStyleSheet(f"""
                QRadioButton {{
                    color: #ccc;
                    font-size: {self.scaling.scale_font(12)}px;
                    spacing: {self.scaling.scale(8)}px;
                    background: transparent;
                    border: none;
                }}
                QRadioButton::indicator {{
                    width: {self.scaling.scale(16)}px;
                    height: {self.scaling.scale(16)}px;
                    border: 2px solid #666;
                    border-radius: {self.scaling.scale(8)}px;
                    background-color: #1a1a1a;
                }}
                QRadioButton::indicator:checked {{
                    background-color: #4a9eff;
                    border-color: #4a9eff;
                }}
                QRadioButton::indicator:hover {{
                    border-color: #4a9eff;
                }}
            """)
            
            if effect_id == default_value:
                radio.setChecked(True)
            
            radio.toggled.connect(lambda checked, eid=effect_id: 
                self._handle_effect_change(eid) if checked else None)
            
            button_group.addButton(radio)
            radio_buttons.append(radio)
            radio_layout.addWidget(radio)
        
        main_layout.addLayout(radio_layout)
        
        container.radio_buttons = radio_buttons
        container.button_group = button_group
        
        return container    

    def _create_footer(self):
        """Нижняя панель в едином стиле"""
        footer = QWidget()
        footer.setFixedHeight(self.scaling.scale(60))
        footer.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                border-top: 2px solid #444;
                border-left: none;
            }
        """)
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(
            self.scaling.scale(30), 
            self.scaling.scale(15), 
            self.scaling.scale(30), 
            self.scaling.scale(15)
        )
        
        hint = QLabel("Навигация: ↑↓ | Выбор: Enter/A | Закрыть: Esc/B/Start")
        hint.setStyleSheet(f"""
            color: #aaa;
            font-size: {self.scaling.scale_font(11)}px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(hint)
        
        return footer
        
    def _add_section_title(self, layout, text):
        """Заголовок секции в едином стиле"""
        title = QLabel(text)
        title.setStyleSheet(f"""
            color: #888;
            font-size: {self.scaling.scale_font(14)}px;
            font-weight: bold;
            padding: {self.scaling.scale(10)}px 0px {self.scaling.scale(5)}px 0px;
        """)
        layout.addWidget(title)
        
    def _create_menu_button(self, title, description, callback, icon_path=None):
        """Кнопка меню с поддержкой иконок"""
        btn = QPushButton()
        btn.setFixedHeight(self.scaling.scale(70))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        btn_layout = QHBoxLayout(btn)
        btn_layout.setContentsMargins(
            self.scaling.scale(15), 
            self.scaling.scale(10), 
            self.scaling.scale(15), 
            self.scaling.scale(10)
        )
        btn_layout.setSpacing(self.scaling.scale(12))
        
        if icon_path and Path(icon_path).exists():
            icon_label = QLabel()
            pixmap = QPixmap(str(icon_path))  
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.scaling.scale(40), 
                    self.scaling.scale(40), 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label.setPixmap(scaled_pixmap)
                icon_label.setFixedSize(self.scaling.scale(40), self.scaling.scale(40))
                icon_label.setStyleSheet("background: transparent; border: none;")
                btn_layout.addWidget(icon_label)
                
        # ТЕКСТ 
        text_layout = QVBoxLayout()
        text_layout.setSpacing(self.scaling.scale(5))
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(14)}px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            QLabel {{
                color: #aaa;
                font-size: {self.scaling.scale_font(12)}px;
                background: transparent;
                border: none;
            }}
        """)
        text_layout.addWidget(desc_label)
        
        btn_layout.addLayout(text_layout)
        btn_layout.addStretch()
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(8)}px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        
        btn.clicked.connect(callback)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        return btn
        
    def _create_toggle(self, title, description, default_value, callback, icon_path=None):
        """Улучшенный переключатель с плавной анимацией"""
        container = QWidget()
        container.setFixedHeight(self.scaling.scale(70))
        
        container.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(8)}px;
            }}
        """)
        
        layout = QHBoxLayout(container)
        layout.setSpacing(self.scaling.scale(12))
        layout.setContentsMargins(
            self.scaling.scale(15), 
            self.scaling.scale(10), 
            self.scaling.scale(15), 
            self.scaling.scale(10)
        )
        if icon_path and Path(icon_path).exists():
            icon_label = QLabel()
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.scaling.scale(40), 
                    self.scaling.scale(40), 
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label.setPixmap(scaled_pixmap)
                icon_label.setFixedSize(self.scaling.scale(40), self.scaling.scale(40))
                icon_label.setStyleSheet("background: transparent; border: none;")
                layout.addWidget(icon_label)
                
        text_layout = QVBoxLayout()
        text_layout.setSpacing(self.scaling.scale(5))
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(14)}px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            QLabel {{
                color: #aaa;
                font-size: {self.scaling.scale_font(12)}px;
                background: transparent;
                border: none;
            }}
        """)
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Используем новый анимированный переключатель
        toggle = AnimatedToggle(self.scaling)
        toggle.setChecked(default_value)
        
        def on_toggle_changed(event):
            toggle.setChecked(not toggle.isChecked())
            callback(toggle.isChecked())
            super(AnimatedToggle, toggle).mousePressEvent(event)
        
        toggle.mousePressEvent = on_toggle_changed
        
        layout.addWidget(toggle)
        
        container.checkbox = toggle  
        return container

    def _create_slider(self, title, description, default_value, min_val, max_val, callback, icon_path=None, default_reset_value=None, value_suffix="%"):
        """Слайдер со стилем + кнопка сброса."""
        if default_reset_value is None:
            default_reset_value = default_value

        container = QWidget()
        container.setFixedHeight(self.scaling.scale(100))

        container.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(8)}px;
            }}
        """)

        outer_layout = QVBoxLayout(container)
        outer_layout.setSpacing(self.scaling.scale(6))
        outer_layout.setContentsMargins(
            self.scaling.scale(15),
            self.scaling.scale(10),
            self.scaling.scale(15),
            self.scaling.scale(10)
        )

        top_layout = QHBoxLayout()
        top_layout.setSpacing(self.scaling.scale(12))

        if icon_path:
            icon_size = self.scaling.scale(40)
            pixmap = QPixmap(str(icon_path)) if Path(icon_path).exists() else None
            icon_label = QLabel()
            icon_label.setFixedSize(icon_size, icon_size)
            icon_label.setStyleSheet("background: transparent; border: none;")
            if pixmap is not None and not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    icon_size,
                    icon_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label.setPixmap(scaled_pixmap)
            top_layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(self.scaling.scale(5))

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(14)}px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        text_layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            QLabel {{
                color: #aaa;
                font-size: {self.scaling.scale_font(12)}px;
                background: transparent;
                border: none;
            }}
        """)
        text_layout.addWidget(desc_label)

        top_layout.addLayout(text_layout)
        top_layout.addStretch()

        value_label = QLabel(f"{int(default_value)}{value_suffix}")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_font = QFont()
        value_font.setPixelSize(self.scaling.scale_font(13))
        value_font.setBold(True)
        value_label.setFont(value_font)
        widest_text = f"100{value_suffix}"
        value_label.setFixedWidth(
            QFontMetrics(value_font).horizontalAdvance(widest_text) + self.scaling.scale(2)
        )
        value_label.setStyleSheet(f"""
            QLabel {{
                color: #4fc3f7;
                font-size: {self.scaling.scale_font(13)}px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        top_layout.addWidget(value_label)

        reset_btn = QPushButton("↺")
        reset_btn.setFixedSize(self.scaling.scale(28), self.scaling.scale(28))
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setToolTip("Сбросить по умолчанию")
        reset_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                color: #ccc;
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: {self.scaling.scale(14)}px;
                font-size: {self.scaling.scale_font(14)}px;
            }}
            QPushButton:hover {{
                background-color: #4a4a4a;
                color: white;
            }}
        """)
        top_layout.addWidget(reset_btn)

        outer_layout.addLayout(top_layout)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(int(default_value))
        slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: {self.scaling.scale(6)}px;
                background: #444;
                border-radius: {self.scaling.scale(3)}px;
            }}
            QSlider::sub-page:horizontal {{
                background: #4fc3f7;
                border-radius: {self.scaling.scale(3)}px;
            }}
            QSlider::handle:horizontal {{
                background: white;
                width: {self.scaling.scale(18)}px;
                height: {self.scaling.scale(18)}px;
                margin: -{self.scaling.scale(6)}px 0;
                border-radius: {self.scaling.scale(9)}px;
            }}
        """)

        def on_slider_moved(v):
            value_label.setText(f"{v}{value_suffix}")
            callback(v)

        slider.valueChanged.connect(on_slider_moved)

        def do_reset():
            slider.setValue(int(default_reset_value))

        reset_btn.clicked.connect(do_reset)

        outer_layout.addWidget(slider)

        container.slider = slider
        container.value_label = value_label
        container._default_reset_value = int(default_reset_value)

        def on_enter_press():
            do_reset()

        container._on_enter_press = on_enter_press

        step = max(1, (max_val - min_val) // 20)

        def on_left():
            slider.setValue(max(min_val, slider.value() - step))

        def on_right():
            slider.setValue(min(max_val, slider.value() + step))

        container._on_left_press = on_left
        container._on_right_press = on_right

        return container

    def _create_info_widget(self):
        """Информационный виджет в едином стиле"""
        info_widget = QWidget()
        info_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(8)}px;
                padding: {self.scaling.scale(15)}px;
            }}
        """)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(self.scaling.scale(8))

        # Кнопка перехода на GitHub
        update_btn = QPushButton("  Посмотреть на GitHub")
        update_btn.setFixedHeight(self.scaling.scale(50))
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        icon_path = Path("assets/icons/github.png")
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            update_btn.setIcon(icon)
            update_btn.setIconSize(QSize(self.scaling.scale(20), self.scaling.scale(20)))
        
        update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #3a3a3a;
                border: 2px solid #555;
                border-radius: {self.scaling.scale(6)}px;
                color: white;
                font-size: {self.scaling.scale_font(13)}px;
                font-weight: bold;
                text-align: left;
                padding-left: {self.scaling.scale(12)}px;
                padding-right: {self.scaling.scale(12)}px;
            }}
            QPushButton:hover {{
                background-color: #4a4a4a;
                border-color: #666;
            }}
        """)
        
        update_btn.clicked.connect(self._open_github)
        update_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        info_layout.addWidget(update_btn)
        
        from modules.update_notification import LAUNCHER_VERSION
        version_label = QLabel(f"Версия: {LAUNCHER_VERSION}")
        version_label.setStyleSheet(f"color: white; font-size: {self.scaling.scale_font(13)}px;")
        info_layout.addWidget(version_label)
  
        author_label = QLabel("Сделано с ❤️ от Darkvinx88")
        author_label.setStyleSheet(f"color: #aaa; font-size: {self.scaling.scale_font(12)}px;")
        info_layout.addWidget(author_label)
        
        self.apps_count_label = QLabel("Приложений: Загрузка...")
        self.apps_count_label.setStyleSheet(f"color: #888; font-size: {self.scaling.scale_font(11)}px;")
        info_layout.addWidget(self.apps_count_label)
        info_widget.update_btn = update_btn
        return info_widget
        
    # ===== ОБРАБОТЧИКИ (HANDLERS) =====
    
    def _handle_api_key(self):
        if not self.launcher:
            return
        self.close_menu()
        QTimer.singleShot(350, self.launcher.set_api_key)
        
    def _handle_scan(self):
        if not self.launcher:
            return
        self.close_menu()
        QTimer.singleShot(350, self.launcher.scan_programs)
        
    def _handle_add_app(self):
        if not self.launcher:
            return
        self.close_menu()
        QTimer.singleShot(350, self.launcher.add_app)
        
    def _handle_download_covers(self):
        if not self.launcher:
            return
        self.close_menu()
        QTimer.singleShot(350, self.launcher.download_covers_for_existing_apps)
        
    def _handle_background(self):
        if not self.launcher:
            return
        self.close_menu()
        QTimer.singleShot(350, self.launcher.set_background)

    def _open_github(self):
        """Открывает страницу проекта на GitHub"""
        import webbrowser
        github_url = "https://github.com/Darkvinx88/TvLauncher"
        
        try:
            webbrowser.open(github_url)
            
        except Exception as e:
            print(f"❌ Ошибка открытия браузера: {e}")
            QMessageBox.warning(
                self,
                "Не удалось открыть браузер",
                f"Пожалуйста, перейдите вручную:\n{github_url}"
            )    
        
    def _handle_open_update(self):
        """Открывает страницу релиза доступного обновления в браузере"""
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        url = getattr(self, '_update_release_url',
                      "https://github.com/Darkvinx88/TvLauncher/releases/latest")
        QDesktopServices.openUrl(QUrl(url))

    def _refresh_update_button(self, launcher):
        """Показывает/обновляет кнопку обновления, если лаунчер обнаружил новую версию"""
        if not hasattr(self, 'update_available_btn'):
            return
        update_info = getattr(launcher, '_update_info', None)
        if update_info:
            latest_tag  = update_info.get('latest_tag', '')
            release_url = update_info.get('release_url', '')
            current_ver = update_info.get('current_version', '')
            self._update_btn_desc(
                self.update_available_btn,
                f"v{current_ver.lstrip('vV')}  ->  {latest_tag}  |  Нажмите для скачивания"
            )
            self._update_release_url = release_url
            self.update_available_btn.setVisible(True)
        else:
            self.update_available_btn.setVisible(False)

    def _update_btn_desc(self, btn, new_desc):
        """Обновляет описание в QLabel внутри кнопки, созданной через _create_menu_button"""
        btn_layout = btn.layout()
        if not btn_layout:
            return
        for i in range(btn_layout.count()):
            item = btn_layout.itemAt(i)
            if item and item.layout():
                vbox = item.layout()
                if vbox.count() >= 2:
                    desc_item = vbox.itemAt(1)
                    if desc_item and desc_item.widget():
                        desc_item.widget().setText(new_desc)
                        return

    def _handle_carousel_position(self, value):
        """Вызывается при изменении вертикального положения карусели ползунком (0=вверху, 100=внизу)"""
        self.config['carousel_vertical_position'] = value
        if self.launcher and hasattr(self.launcher, 'set_carousel_vertical_position'):
            self.launcher.set_carousel_vertical_position(value)

    def _handle_toggle(self, key, value):
        self.config[key] = value
        
        if self.launcher:
            self.launcher.config_data[key] = value
            self.launcher.save_config()
            
            if key == 'show_clock':
                self.launcher.toggle_clock_visibility(value)
            elif key == 'sound_effects':
                self.launcher.sound_manager.set_enabled(value)
                if value:
                    self.launcher.sound_manager.select()
            elif key == 'tile_glow':
                if hasattr(self.launcher, 'tiles'):
                    for tile in self.launcher.tiles:
                        if hasattr(tile, 'glow_effect') and tile.glow_effect:
                            if hasattr(tile.glow_effect, 'timer') and tile.glow_effect.timer:
                                try:
                                    tile.glow_effect.timer.stop()
                                    tile.glow_effect.timer.deleteLater()
                                except:
                                    pass
                            try:
                                tile.glow_effect.stop()
                            except:
                                pass
                            tile.glow_effect = None
                
                if hasattr(self.launcher, 'tiles') and hasattr(self.launcher, 'current_index'):
                    for i, tile in enumerate(self.launcher.tiles):
                        is_focused = (tile.app_index == self.launcher.current_index)
                        tile.set_focused(is_focused)
                
                if value:
                    self.launcher.sound_manager.select()

    def _handle_backup(self):
        """Экспорт ВСЕЙ конфигурации в JSON-файл"""
        if not self.launcher:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт конфигурации",
            str(Path.home() / "launcher_backup.json"),
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_path:
            try:
                key_mappings_data = None
                key_mappings_file = getattr(
                    getattr(self.launcher, 'key_mapper', None), 'config_file', None
                ) or Path("key_mappings.json")
                if key_mappings_file.exists():
                    with open(key_mappings_file, 'r') as f:
                        key_mappings_data = json.load(f)
                
                complete_config = {
                    'apps': self.launcher.apps,
                    'steamgriddb_api_key': self.launcher.steamgriddb_api_key,
                    'show_clock': self.launcher.config_data.get('show_clock', True),
                    'sound_effects': self.launcher.config_data.get('sound_effects', False),
                    'fullscreen': self.launcher.config_data.get('fullscreen', True),
                    'tile_glow': self.launcher.config_data.get('tile_glow', True),
                    'show_weather': self.launcher.config_data.get('show_weather', True),
                    'key_mappings': key_mappings_data,
                }
                
                if hasattr(self.launcher, 'weather_widget') and self.launcher.weather_widget:
                    complete_config['weather_city'] = getattr(self.launcher.weather_widget, 'city', 'Milan')
                    complete_config['weather_country_code'] = getattr(self.launcher.weather_widget, 'country_code', 'IT')
                    complete_config['weather_units'] = getattr(self.launcher.weather_widget, 'units', 'metric')
                else:
                    complete_config['weather_city'] = self.launcher.config_data.get('weather_city', 'Milan')
                    complete_config['weather_country_code'] = self.launcher.config_data.get('weather_country_code', 'IT')
                    complete_config['weather_units'] = self.launcher.config_data.get('weather_units', 'metric')
                
                if hasattr(self.launcher, 'background_manager') and self.launcher.background_manager is not None:
                    bg_config = self.launcher.background_manager.get_config()
                    complete_config.update(bg_config)
                else:
                    complete_config['background'] = self.launcher.config_data.get('background', '')
                    complete_config['auto_change_wallpaper'] = self.launcher.config_data.get('auto_change_wallpaper', False)
                    complete_config['wallpaper_interval'] = self.launcher.config_data.get('wallpaper_interval', 180000)

                if hasattr(self.launcher, 'video_wallpaper_manager') and self.launcher.video_wallpaper_manager is not None:
                    complete_config['video_wallpaper'] = self.launcher.video_wallpaper_manager.get_config()
                else:
                    complete_config['video_wallpaper'] = self.launcher.config_data.get('video_wallpaper', {})
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(complete_config, f, indent=2, ensure_ascii=False)
                
                self._show_success_dialog(
                    "✅ Экспорт завершен",
                    f"Конфигурация успешно экспортирована!\n\n"
                    f"📦 Экспортировано:\n"
                    f"  • Приложений: {len(complete_config['apps'])}\n"
                    f"  • Фоновое изображение\n"
                    f"  • API-ключ\n"
                    f"  • Назначения клавиш\n"
                    f"  • Настройки погоды\n"
                    f"  • Все прочие настройки"
                )
                
            except Exception as e:
                self._show_error_dialog("Ошибка экспорта", f"Не удалось экспортировать конфигурацию:\n\n{str(e)}")
                
    def _handle_restore(self):
        """Восстановление ВСЕЙ конфигурации из JSON-файла"""
        if not self.launcher:
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт конфигурации",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            apps_count = len(imported_config.get('apps', []))
            has_background = bool(imported_config.get('background'))
            has_api_key = bool(imported_config.get('steamgriddb_api_key'))
            has_key_mappings = bool(imported_config.get('key_mappings'))
            
            if self._show_confirm_dialog(
                "⚠️ Подтверждение восстановления",
                f"Это заменит вашу текущую конфигурацию:\n\n"
                f"📦 Будет импортировано:\n"
                f"  • Приложений: {apps_count}\n"
                f"  • Фон: {'Да' if has_background else 'Нет'}\n"
                f"  • API-ключ: {'Да' if has_api_key else 'Нет'}\n"
                f"  • Назначения клавиш: {'Да' if has_key_mappings else 'Нет'}\n"
                f"  • Все остальные настройки\n\n"
                f"⚠️ Текущие данные будут ПЕРЕЗАПИСАНЫ!\n\n"
                f"Продолжить?"
            ):
                # ШАГ 1: Очистка существующих плиток перед восстановлением
                if hasattr(self.launcher, 'tiles'):
                    for tile in self.launcher.tiles:
                        if hasattr(tile, 'glow_effect') and tile.glow_effect:
                            try:
                                tile.glow_effect.stop()
                                tile.glow_effect = None
                            except:
                                pass
                        
                        if hasattr(tile, 'shadow'):
                            try:
                                tile.setGraphicsEffect(None)
                            except:
                                pass
                
                if hasattr(self.launcher, 'tiles'):
                    for tile in self.launcher.tiles:
                        tile.setParent(None)
                        tile.deleteLater()
                    self.launcher.tiles.clear()
                
                # ШАГ 2: Восстановление ВСЕГО
                self.launcher.apps = imported_config.get('apps', [])
                
                if hasattr(self.launcher, 'background_manager') and self.launcher.background_manager is not None:
                    self.launcher.background_manager.background_image = imported_config.get('background', '')
                    self.launcher.background_manager.auto_change_wallpaper = imported_config.get('auto_change_wallpaper', False)
                    self.launcher.background_manager.wallpaper_interval = imported_config.get('wallpaper_interval', 180000)

                if hasattr(self.launcher, 'video_wallpaper_manager') and self.launcher.video_wallpaper_manager is not None:
                    was_enabled = self.launcher.video_wallpaper_manager.enabled
                    self.launcher.video_wallpaper_manager.load_config(
                        {'video_wallpaper': imported_config.get('video_wallpaper', {})}
                    )
                    if self.launcher.video_wallpaper_manager.enabled != was_enabled:
                        self.launcher.video_wallpaper_manager.toggle_enabled(
                            self.launcher.video_wallpaper_manager.enabled
                        )
                
                self.launcher.steamgriddb_api_key = imported_config.get('steamgriddb_api_key', '')
                
                if imported_config.get('key_mappings'):
                    key_mappings_file = getattr(
                        getattr(self.launcher, 'key_mapper', None), 'config_file', None
                    ) or Path("key_mappings.json")
                    with open(key_mappings_file, 'w') as f:
                        json.dump(imported_config['key_mappings'], f, indent=2)
                    if hasattr(self.launcher, 'key_mapper'):
                        self.launcher.key_mapper.load_mappings()
            
                # ШАГ 3: Обновление config_data
                self.launcher.config_data = {
                    'apps': self.launcher.apps,
                    'steamgriddb_api_key': self.launcher.steamgriddb_api_key,
                    'show_clock': imported_config.get('show_clock', True),
                    'sound_effects': imported_config.get('sound_effects', False),
                    'fullscreen': imported_config.get('fullscreen', True),
                    'tile_glow': imported_config.get('tile_glow', True),
                    'show_weather': imported_config.get('show_weather', False),
                    'weather_city': imported_config.get('weather_city', 'Milan'),
                    'weather_country_code': imported_config.get('weather_country_code', 'IT'),
                    'weather_units': imported_config.get('weather_units', 'metric'),
                }
                
                if hasattr(self.launcher, 'weather_widget') and self.launcher.weather_widget:
                    weather_city = imported_config.get('weather_city', 'Milan')
                    weather_country = imported_config.get('weather_country_code', 'IT')
                    weather_units = imported_config.get('weather_units', 'metric')
                    show_weather = imported_config.get('show_weather', False)
                    
                    self.launcher.weather_widget.set_location(weather_city, weather_country)
                    self.launcher.weather_widget.set_units(weather_units)
                    self.launcher.weather_widget.setVisible(show_weather)
                
                if hasattr(self.launcher, 'background_manager') and self.launcher.background_manager is not None:
                    self.launcher.config_data.update(self.launcher.background_manager.get_config())
                else:
                    self.launcher.config_data['background'] = imported_config.get('background', '')
                    self.launcher.config_data['auto_change_wallpaper'] = imported_config.get('auto_change_wallpaper', False)
                    self.launcher.config_data['wallpaper_interval'] = imported_config.get('wallpaper_interval', 180000)

                if hasattr(self.launcher, 'video_wallpaper_manager') and self.launcher.video_wallpaper_manager is not None:
                    self.launcher.config_data['video_wallpaper'] = self.launcher.video_wallpaper_manager.get_config()
                else:
                    self.launcher.config_data['video_wallpaper'] = imported_config.get('video_wallpaper', {})
            
                # ШАГ 4: Сброс индекса и очистка бэкапа категорий
                self.launcher.current_index = 0
                
                if hasattr(self.launcher, '_all_apps_backup'):
                    delattr(self.launcher, '_all_apps_backup')
                
                # ШАГ 5: Сохранение на диск
                self.launcher.save_config()
                
                # ШАГ 6: Обновление UI
                self.launcher.update_background()
                self.launcher.image_manager.api_key = self.launcher.steamgriddb_api_key
                
                # ШАГ 7: Пересоздание карусели
                self.launcher.build_infinite_carousel()
                
                # ШАГ 8: Синхронизация переключателей в меню настроек
                self._sync_toggles_from_config(self.launcher.config_data)
                
                if hasattr(self, 'weather_btn') and hasattr(self.weather_btn, '_refresh_toggle'):
                    self.weather_btn._refresh_toggle()
                
                if hasattr(self, 'apps_count_label'):
                    self.apps_count_label.setText(f"Приложений: {len(self.launcher.apps)}")
                
                self._show_success_dialog(
                    "✅ Восстановление завершено",
                    f"Конфигурация успешно восстановлена!\n\n"
                    f"📦 Импортировано приложений: {apps_count}"
                    + ("\n🎮 Назначения клавиш восстановлены" if has_key_mappings else "")
                )
                
        except json.JSONDecodeError:
            self._show_error_dialog(
                "Неверный файл",
                "Некорректный формат JSON!\n\nПожалуйста, выберите действительный файл резервной копии."
            )
        except Exception as e:
            self._show_error_dialog("Ошибка восстановления", f"Не удалось импортировать конфигурацию:\n\n{str(e)}")
                
    def _handle_open_config_folder(self):
        """Открывает папку конфигурации в файловом менеджере"""
        import platform
        import subprocess
        import os

        if platform.system() == "Windows":
            config_dir = Path(os.environ.get('APPDATA', Path.home())) / 'TVLauncher'
        else:
            xdg = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
            config_dir = xdg / 'TVLauncher'

        config_dir.mkdir(parents=True, exist_ok=True)

        try:
            if platform.system() == "Windows":
                os.startfile(str(config_dir))
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(config_dir)])
            else:
                subprocess.Popen(["xdg-open", str(config_dir)])
        except Exception as e:
            self._show_error_dialog("Ошибка", f"Не удалось открыть папку:\n{config_dir}\n\n{e}")

    def _handle_reset(self):
        """Отображает диалог выбора типа сброса"""
        dialog = ResetDialog(self.launcher, self.scaling, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            reset_type = dialog.get_reset_type()
            
            if reset_type == "soft":
                self._do_soft_reset()
            elif reset_type == "full":
                self._do_full_reset()

    def _do_soft_reset(self):
        """Мягкий сброс (сохраняет приложения, фон, API-ключ)"""
        if self._show_confirm_dialog(
            "🔄 Мягкий сброс",
            "Будут сброшены только настройки:\n\n"
            "✅ Ваши приложения СОХРАНЯТСЯ\n"
            "✅ Фон СОХРАНИТСЯ\n"
            "✅ API-ключ СОХРАНИТСЯ\n\n"
            "  Настройки вернутся к значениям:\n"
            "  • Показывать часы → ВКЛ\n"
            "  • Звуковые эффекты → ВЫКЛ\n"
            "  • Во весь экран → ВКЛ\n\n"
            "Продолжить?"
        ):
            default_settings = {
                'show_clock': True,
                'sound_effects': False,
                'fullscreen': True,
                'carousel_vertical_position': 50,
            }
            
            self.launcher.config_data.update(default_settings)
            self.launcher.save_config()
            self._sync_toggles_from_config(default_settings)
            
            self.launcher.toggle_clock_visibility(True)
            if hasattr(self.launcher, 'set_carousel_vertical_position'):
                self.launcher.set_carousel_vertical_position(50)
            
            self._show_success_dialog(
                "✅ Мягкий сброс завершен",
                f"Настройки сброшены по умолчанию!\n\n"
                f"✅ Ваши приложения ({len(self.launcher.apps)}) в безопасности\n"
                f"✅ Фон сохранен\n"
                f"✅ API-ключ сохранен"
            )

    def _do_full_reset(self):
        """Полный сброс: удаляет всё"""
        if not self._show_confirm_dialog(
            "⚠️ Полный сброс",
            "ВНИМАНИЕ: Это удалит ВСЁ:\n\n"
            "❌ ВСЕ приложения будут УДАЛЕНЫ\n"
            "❌ Фон будет СБРОШЕН\n"
            "❌ API-ключ будет УДАЛЕН\n"
            "❌ Все настройки вернутся по умолчанию\n\n"
            "⚠️ Это действие НЕЛЬЗЯ отменить!\n\n"
            "💡 СОВЕТ: Сделайте резервную копию!\n\n"
            "Продолжить?"
        ):
            return
        
        if not self._show_confirm_dialog(
            "⚠️ Окончательное подтверждение",
            "Вы АБСОЛЮТНО уверены?\n\n"
            "🔴 Все ваши данные будут перманентно удалены!\n\n"
            f"Вы потеряете приложений: {len(self.launcher.apps)}."
        ):
            return
        
        if hasattr(self.launcher, 'tiles'):
            for tile in self.launcher.tiles:
                if hasattr(tile, 'glow_effect') and tile.glow_effect:
                    try:
                        tile.glow_effect.stop()
                        tile.glow_effect = None
                    except:
                        pass
                
                if hasattr(tile, 'shadow'):
                    try:
                        tile.setGraphicsEffect(None)
                    except:
                        pass
        
        if hasattr(self.launcher, 'tiles'):
            for tile in self.launcher.tiles:
                tile.setParent(None)
                tile.deleteLater()
            self.launcher.tiles.clear()
        
        default_config = {
            'apps': [],
            'background': '',
            'steamgriddb_api_key': '',
            'show_clock': True,
            'sound_effects': False,
            'fullscreen': True,
            'tile_glow': True,
            'carousel_vertical_position': 50,
        }
        
        key_mappings_file = getattr(
            getattr(self.launcher, 'key_mapper', None), 'config_file', None
        ) or Path("key_mappings.json")
        if key_mappings_file.exists():
            key_mappings_file.unlink()
        
        if hasattr(self.launcher, 'key_mapper'):
            self.launcher.key_mapper.load_mappings()
        
        if hasattr(self.launcher, '_all_apps_backup'):
            delattr(self.launcher, '_all_apps_backup')
        
        self.launcher.apps = []
        
        if hasattr(self.launcher, 'background_manager') and self.launcher.background_manager is not None:
            self.launcher.background_manager.background_image = ''
            self.launcher.background_manager.auto_change_wallpaper = False
            self.launcher.background_manager.wallpaper_interval = 180000

        if hasattr(self.launcher, 'video_wallpaper_manager') and self.launcher.video_wallpaper_manager is not None:
            if self.launcher.video_wallpaper_manager.enabled:
                self.launcher.video_wallpaper_manager.toggle_enabled(False)
            self.launcher.video_wallpaper_manager.categories = []
            self.launcher.video_wallpaper_manager.quality = '1080p'
            self.launcher.video_wallpaper_manager.interval_seconds = 600
        
        self.launcher.steamgriddb_api_key = ''
        self.launcher.config_data = default_config
        self.launcher.current_index = 0
        
        self.launcher.save_config()
        self.launcher.update_background()
        
        self.launcher.image_manager.api_key = ''
        self.launcher.build_infinite_carousel()
        
        if hasattr(self.launcher, 'set_carousel_vertical_position'):
            self.launcher.set_carousel_vertical_position(50)
        
        self._sync_toggles_from_config(default_config)
        
        if hasattr(self, 'apps_count_label'):
            self.apps_count_label.setText("Приложений: 0")
        
        self._show_success_dialog(
            "✅ Полный сброс завершен",
            "Все данные были удалены.\n\nЛаунчер возвращен в исходное состояние."
        )
    
    def _open_category_editor(self):
        """Открывает редактор категорий"""
        from modules.category_editor import CategoryEditorDialog
        from PyQt6.QtCore import Qt
        
        if not hasattr(self.launcher, 'category_manager'):
            msg_box = QMessageBox(self.launcher)
            msg_box.setWindowTitle("Недоступно")
            msg_box.setText("Система категорий не инициализирована!")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #1a1a1a;
                    color: white;
                }
                QMessageBox QLabel {
                    color: white;
                    font-size: 14px;
                    padding: 10px;
                }
                QMessageBox QPushButton {
                    background-color: #2a2a2a;
                    color: white;
                    border: 2px solid #444;
                    padding: 10px 30px;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: bold;
                    min-width: 80px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #3a3a3a;
                    border-color: #666;
                }
            """)
            
            msg_box.exec()
            return
        
        self.close_menu()
        
        def open_editor():
            dialog = CategoryEditorDialog(
                self.launcher.category_manager,
                self.scaling,
                self.launcher
            )
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.launcher.save_config()

                if hasattr(self.launcher, 'category_selector'):
                    try:
                        self.launcher.category_selector.rebuild()
                    except Exception as e:
                        print(f"⚠️ Не удалось пересоздать селектор категорий: {e}")

                self._show_success_dialog(
                    "Изменения сохранены",
                    "Категории обновлены!"
                )
            
            self.launcher.setFocus()
        
        QTimer.singleShot(350, open_editor)

    def _handle_key_remapper(self):
        """Открывает диалог перенаправления клавиш"""
        if not self.launcher:
            return
        
        self.close_menu()
        QTimer.singleShot(350, lambda: self._open_key_remapper_dialog())

    def _handle_network_settings(self):
        """Открывает настройки сети операционной системы"""
        import subprocess
        import platform
        
        try:
            system = platform.system()
            
            if system == "Windows":
                subprocess.Popen('explorer.exe ms-settings:network', shell=True)
            elif system == "Linux":
                if self.launcher:
                    print("🔽 Сворачивание лаунчера (Linux) перед открытием настроек сети")
                    self.launcher.showMinimized()
                
                network_managers = [
                    ['gnome-control-center', 'network'],
                    ['systemsettings5', 'kcm_networkmanagement'],
                    ['nm-connection-editor'],
                    ['xfce4-settings-manager', '--socket-id=network'],
                    ['nm-applet']
                ]
                
                opened = False
                for cmd in network_managers:
                    try:
                        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        opened = True
                        break
                    except FileNotFoundError:
                        continue
                
                if not opened:
                    raise Exception("Графический интерфейс сетевого менеджера не найден")
            else:
                raise Exception(f"Не поддерживаемая операционная система: {system}")
            
            self.close_menu()
            
        except Exception as e:
            print(f"⚠️ Ошибка открытия настроек сети: {e}")
            
            if platform.system() == "Linux" and self.launcher:
                self.launcher.showNormal()
                if self.launcher.config_data.get('fullscreen', True):
                    self.launcher.showFullScreen()
            
            self._show_error_dialog(
                "Ошибка",
                f"Не удалось открыть настройки сети.\n\n"
                f"Система: {platform.system()}\n"
                f"Ошибка: {str(e)}\n\n"
                f"Пожалуйста, откройте настройки сети вручную."
            )     

    def _handle_parental_control(self):
        """Открывает настройки родительского контроля. Интегрирует модуль, если еще не сделано."""
        if not self.launcher:
            return

        if not hasattr(self.launcher, "parental_control"):
            integrate_parental_control(self.launcher)

        self.launcher.open_parental_control_settings()
        self._refresh_parental_control_btn()

    def _refresh_parental_control_btn(self):
        """Обновляет только текст описания кнопки родительского контроля"""
        if not hasattr(self, 'parental_control_btn') or not self._parental_desc_label:
            return

        if not self.launcher or not hasattr(self.launcher, "parental_control"):
            new_status = "Не настроен"
        else:
            pc = self.launcher.parental_control
            if hasattr(pc, "get_status_text"):
                new_status = pc.get_status_text()
            elif getattr(pc, "is_configured", False):
                new_status = "Активен" if getattr(pc, "is_enabled", False) else "Неактивен — отключен"
            else:
                new_status = "Не настроен"

        self._parental_desc_label.setText(new_status)

    def _open_key_remapper_dialog(self):
        """Непосредственно открывает диалог перенаправления клавиш"""
        try:
            dialog = KeyRemapperDialog(self.launcher, self.scaling, self.launcher)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                if hasattr(self.launcher, 'key_mapper'):
                    self.launcher.key_mapper.load_mappings()
                    
                    self._show_success_dialog(
                        "✅ Назначения сохранены",
                        "Назначения клавиш успешно обновлены!\n\nВаше новое управление активно."
                    )
        
        except Exception as e:
            print(f"❌ Ошибка открытия перенаправления клавиш: {e}")
            self._show_error_dialog(
                "Ошибка",
                f"Не удалось открыть настройки клавиш:\n\n{str(e)}"
            )
        
        self.launcher.setFocus()
        self.launcher.activateWindow()

    # ПУБЛИЧНЫЕ МЕТОДЫ (PUBLIC METHODS) 

    def _sync_toggles_from_config(self, config):
        """Синхронизирует переключатели с данными конфигурации"""
        if hasattr(self, 'clock_toggle') and hasattr(self.clock_toggle, 'checkbox'):
            self.clock_toggle.checkbox.setChecked(config.get('show_clock', True))
        
        if hasattr(self, 'sound_toggle') and hasattr(self.sound_toggle, 'checkbox'):
            self.sound_toggle.checkbox.setChecked(config.get('sound_effects', False))
        
        if hasattr(self, 'fullscreen_toggle') and hasattr(self.fullscreen_toggle, 'checkbox'):
            self.fullscreen_toggle.checkbox.setChecked(config.get('fullscreen', True))
        
        if hasattr(self, 'glow_toggle') and hasattr(self.glow_toggle, 'checkbox'):
            self.glow_toggle.checkbox.setChecked(config.get('tile_glow', True))
        
        if hasattr(self, 'wallpaper_toggle') and hasattr(self.wallpaper_toggle, 'checkbox'):
            self.wallpaper_toggle.checkbox.setChecked(config.get('auto_change_wallpaper', False))

        if hasattr(self, 'carousel_position_slider') and hasattr(self.carousel_position_slider, 'slider'):
            value = int(config.get('carousel_vertical_position', 50))
            self.carousel_position_slider.slider.blockSignals(True)
            self.carousel_position_slider.slider.setValue(value)
            self.carousel_position_slider.slider.blockSignals(False)
            self.carousel_position_slider.value_label.setText(f"{value}%")
            
    def open_menu(self, launcher):
        """Открывает меню БЕЗ пересоздания контента"""
        if self.is_open:
            return
            
        self.launcher = launcher
        self.is_open = True
        
        if hasattr(launcher, 'config_data'):
            for key in self.config:
                if key in launcher.config_data:
                    self.config[key] = launcher.config_data[key]
            self._sync_toggles_from_config(launcher.config_data)
            if hasattr(self, 'weather_btn') and hasattr(self.weather_btn, '_refresh_toggle'):
                self.weather_btn._refresh_toggle()
        
        if hasattr(launcher, 'apps'):
            self.apps_count_label.setText(f"Приложений: {len(launcher.apps)}")
        self._refresh_update_button(launcher)
        self._refresh_parental_control_btn()
        
        parent_rect = launcher.geometry()
        parent_width = parent_rect.width()
        parent_height = parent_rect.height()
        
        self.setGeometry(parent_width, 0, self.width(), parent_height)
        
        self.show()
        self.raise_()
        self.setFocus()
        
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        start_pos = QPoint(parent_width, 0)
        end_pos = QPoint(parent_width - self.width(), 0)
        
        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)
        self.animation.start()
        
        self.current_index = 0
        self.update_focus()
        
    def close_menu(self):
        if hasattr(self.launcher, 'sound_manager'):
            self.launcher.sound_manager.back()
            
        if not self.is_open:
            return
        
        parent_width = self.launcher.width() if self.launcher else 1920
        
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InCubic)
        
        start_pos = self.pos()
        end_pos = QPoint(parent_width, 0)
        
        self.animation.setStartValue(start_pos)
        self.animation.setEndValue(end_pos)
        self.animation.finished.connect(self._on_close_finished)
        self.animation.start()
        
    def _on_close_finished(self):
        self.hide()
        self.is_open = False
        self.menu_closed.emit()
        
    def update_focus(self):
        """Фокус в едином стиле"""
        for i, item in enumerate(self.menu_items):
            if i == self.current_index:
                if isinstance(item, QPushButton):
                    if hasattr(item, 'icon') and not item.icon().isNull():
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #3a3a3a;
                                border: 3px solid white;
                                border-radius: {self.scaling.scale(8)}px;
                                color: white;
                                font-size: {self.scaling.scale_font(13)}px;
                                font-weight: bold;
                                text-align: left;
                                padding-left: {self.scaling.scale(12)}px;
                                padding-right: {self.scaling.scale(12)}px;
                            }}
                        """)
                    else:
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #3a3a3a;
                                border: 3px solid white;
                                border-radius: {self.scaling.scale(8)}px;
                                text-align: left;
                            }}
                        """)
                else:
                    item.setStyleSheet(f"""
                        QWidget {{
                            background-color: #3a3a3a;
                            border: 3px solid white;
                            border-radius: {self.scaling.scale(8)}px;
                        }}
                    """)
            else:
                if isinstance(item, QPushButton):
                    if hasattr(item, 'icon') and not item.icon().isNull():
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #3a3a3a;
                                border: 2px solid #555;
                                border-radius: {self.scaling.scale(6)}px;
                                color: white;
                                font-size: {self.scaling.scale_font(13)}px;
                                font-weight: bold;
                                text-align: left;
                                padding-left: {self.scaling.scale(12)}px;
                                padding-right: {self.scaling.scale(12)}px;
                            }}
                            QPushButton:hover {{
                                background-color: #4a4a4a;
                                border-color: #666;
                            }}
                        """)
                    else:
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #2a2a2a;
                                border: 2px solid #444;
                                border-radius: {self.scaling.scale(8)}px;
                                text-align: left;
                            }}
                            QPushButton:hover {{
                                background-color: #3a3a3a;
                            }}
                        """)
                else:
                    item.setStyleSheet(f"""
                        QWidget {{
                            background-color: #2a2a2a;
                            border: 2px solid #444;
                            border-radius: {self.scaling.scale(8)}px;
                        }}
                    """)
                    
    def navigate_up(self):
        """Навигация вверх с пропуском скрытых виджетов"""
        if self.current_index > 0:
            if hasattr(self.launcher, 'sound_manager'):
                self.launcher.sound_manager.navigate()
            
            original_index = self.current_index
            self.current_index -= 1
            
            while self.current_index >= 0 and not self.menu_items[self.current_index].isVisible():
                self.current_index -= 1
            
            if self.current_index < 0:
                self.current_index = original_index
                return
            
            self.update_focus()
            self._ensure_visible()
            
    def navigate_down(self):
        """Навигация вниз с пропуском скрытых виджетов"""
        if self.current_index < len(self.menu_items) - 1:
            if hasattr(self.launcher, 'sound_manager'):
                self.launcher.sound_manager.navigate()
            
            original_index = self.current_index
            self.current_index += 1
            
            while self.current_index < len(self.menu_items) and not self.menu_items[self.current_index].isVisible():
                self.current_index += 1
            
            if self.current_index >= len(self.menu_items):
                self.current_index = original_index
                return
            
            self.update_focus()
            self._ensure_visible()
            
    def activate_current(self):
        if hasattr(self.launcher, 'sound_manager'):
            self.launcher.sound_manager.select()
        current_item = self.menu_items[self.current_index]
        
        if isinstance(current_item, QPushButton):
            current_item.click()
        else:
            if hasattr(current_item, '_on_enter_press'):
                current_item._on_enter_press()
                return
            
            toggle = current_item.checkbox
            new_state = not toggle.isChecked()
            toggle.setChecked(new_state)
            
            if current_item == self.clock_toggle:
                self._handle_toggle('show_clock', new_state)
            elif current_item == self.sound_toggle:
                self._handle_toggle('sound_effects', new_state)
            elif current_item == self.fullscreen_toggle:
                self._handle_toggle('fullscreen', new_state)
            elif current_item == self.glow_toggle:
                self._handle_toggle('tile_glow', new_state)
            elif current_item == self.wallpaper_toggle:
                self._handle_wallpaper_toggle(new_state)
            
    def _ensure_visible(self):
        if not self.menu_items or self.current_index >= len(self.menu_items):
            return
        
        current_item = self.menu_items[self.current_index]
        
        scroll_area = None
        parent = current_item.parent()
        while parent:
            if isinstance(parent, QScrollArea):
                scroll_area = parent
                break
            parent = parent.parent()
        
        if not scroll_area:
            return
        
        item_y = 0
        widget = current_item
        
        scroll_content = scroll_area.widget()
        while widget and widget != scroll_content:
            item_y += widget.y()
            widget = widget.parent()
            if widget == scroll_content:
                break
        
        item_height = current_item.height()
        viewport_height = scroll_area.viewport().height()
        scrollbar = scroll_area.verticalScrollBar()
        current_scroll = scrollbar.value()
        
        visible_top = current_scroll
        visible_bottom = current_scroll + viewport_height
        item_top = item_y
        item_bottom = item_y + item_height
        padding = self.scaling.scale(20)
        
        if item_bottom + padding > visible_bottom:
            new_scroll = item_bottom - viewport_height + padding
            scrollbar.setValue(int(new_scroll))
        elif item_top - padding < visible_top:
            new_scroll = item_top - padding
            scrollbar.setValue(int(new_scroll))
            
    def keyPressEvent(self, event):
        """Обработка ввода с клавиатуры/контроллера"""
        if event.isAutoRepeat():
            return
            
        key = event.key()
        
        current_item = self.menu_items[self.current_index] if self.menu_items and 0 <= self.current_index < len(self.menu_items) else None
        
        if key == Qt.Key.Key_Up:
            self.navigate_up()
        elif key == Qt.Key.Key_Down:
            self.navigate_down()
        elif key == Qt.Key.Key_Left and current_item is not None and hasattr(current_item, '_on_left_press'):
            current_item._on_left_press()
        elif key == Qt.Key.Key_Right and current_item is not None and hasattr(current_item, '_on_right_press'):
            current_item._on_right_press()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate_current()
        elif key in (Qt.Key.Key_Escape, Qt.Key.Key_S):
            self.close_menu()
        else:
            super().keyPressEvent(event)

    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ДИАЛОГОВ (DIALOG HELPER METHODS) 

    def _show_confirm_dialog(self, title, message):
        """Показывает стилизованное диалоговое окно подтверждения (Да/Нет)"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setFixedSize(self.scaling.scale(550), self.scaling.scale(450))
        
        dialog.setStyleSheet("""
            QDialog { 
                background-color: #1a1a1a; 
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(self.scaling.scale(20))
        layout.setContentsMargins(
            self.scaling.scale(30), 
            self.scaling.scale(30), 
            self.scaling.scale(30), 
            self.scaling.scale(30)
        )
        
        # ШАПКА С ЗАГОЛОВКОМ
        header_widget = QWidget()
        header_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border-radius: {self.scaling.scale(10)}px;
                padding: {self.scaling.scale(15)}px;
            }}
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15)
        )
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(20)}px; 
                font-weight: bold;
                color: white;
                background: transparent;
                border: none;
            }}
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        layout.addWidget(header_widget)
        
        # СООБЩЕНИЕ В ПРЯМОУГОЛЬНИКЕ 
        message_widget = QWidget()
        message_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border-radius: {self.scaling.scale(10)}px;
                padding: {self.scaling.scale(15)}px;
            }}
        """)
        message_layout = QVBoxLayout(message_widget)
        message_layout.setContentsMargins(
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15)
        )
        
        message_label = QLabel(message)
        message_label.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(13)}px;
                color: #cccccc;
                background: transparent;
                border: none;
            }}
        """)
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        message_label.setWordWrap(True)
        message_layout.addWidget(message_label)
        
        layout.addWidget(message_widget)
        layout.addStretch()
        
        # КНОПКИ 
        button_layout = QHBoxLayout()
        button_layout.setSpacing(self.scaling.scale(15))
        
        yes_button = QPushButton("Да")
        yes_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        yes_button.clicked.connect(dialog.accept)
        
        no_button = QPushButton("Нет")
        no_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        no_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(yes_button)
        button_layout.addWidget(no_button)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        confirm_buttons = [yes_button, no_button]
        confirm_index = [1]  # По умолчанию на "Нет"
        
        def update_confirm_focus():
            for i, btn in enumerate(confirm_buttons):
                if i == confirm_index[0]:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: #2a2a2a;
                            color: white;
                            border: 3px solid white;
                            padding: {self.scaling.scale(12)}px {self.scaling.scale(30)}px;
                            border-radius: {self.scaling.scale(8)}px;
                            font-size: {self.scaling.scale_font(14)}px;
                            font-weight: bold;
                        }}
                        QPushButton:hover {{ background-color: #3a3a3a; }}
                    """)
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: #2a2a2a;
                            color: white;
                            border: 2px solid #444;
                            padding: {self.scaling.scale(12)}px {self.scaling.scale(30)}px;
                            border-radius: {self.scaling.scale(8)}px;
                            font-size: {self.scaling.scale_font(14)}px;
                            font-weight: bold;
                        }}
                        QPushButton:hover {{ background-color: #3a3a3a; }}
                    """)
        
        def confirm_key_handler(event):
            if event.isAutoRepeat():
                return
            key = event.key()
            if key == Qt.Key.Key_Left:
                confirm_index[0] = (confirm_index[0] - 1) % 2
                update_confirm_focus()
            elif key == Qt.Key.Key_Right:
                confirm_index[0] = (confirm_index[0] + 1) % 2
                update_confirm_focus()
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                confirm_buttons[confirm_index[0]].click()
            elif key == Qt.Key.Key_Escape:
                dialog.reject()
        
        dialog.keyPressEvent = confirm_key_handler
        update_confirm_focus()
        
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _show_success_dialog(self, title, message):
        """Показывает стилизованное диалоговое окно успеха (только ОК)"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setFixedSize(self.scaling.scale(500), self.scaling.scale(400))
        
        dialog.setStyleSheet("""
            QDialog { 
                background-color: #1a1a1a; 
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(self.scaling.scale(20))
        layout.setContentsMargins(
            self.scaling.scale(30), 
            self.scaling.scale(30), 
            self.scaling.scale(30), 
            self.scaling.scale(30)
        )
        
        header_widget = QWidget()
        header_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #2a3a2a;
                border: 2px solid #4CAF50;
                border-radius: {self.scaling.scale(10)}px;
                padding: {self.scaling.scale(15)}px;
            }}
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15)
        )
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(20)}px; 
                font-weight: bold;
                color: #4CAF50;
                background: transparent;
                border: none;
            }}
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        layout.addWidget(header_widget)
        
        message_widget = QWidget()
        message_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border-radius: {self.scaling.scale(10)}px;
                padding: {self.scaling.scale(15)}px;
            }}
        """)
        message_layout = QVBoxLayout(message_widget)
        message_layout.setContentsMargins(
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15)
        )
        
        message_label = QLabel(message)
        message_label.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(13)}px;
                color: #cccccc;
                background: transparent;
                border: none;
            }}
        """)
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        message_label.setWordWrap(True)
        message_layout.addWidget(message_label)
        
        layout.addWidget(message_widget)
        layout.addStretch()
        
        ok_button = QPushButton("ОК")
        ok_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ok_button.clicked.connect(dialog.accept)
        ok_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: white;
                border: 3px solid #4CAF50;
                padding: {self.scaling.scale(12)}px {self.scaling.scale(40)}px;
                border-radius: {self.scaling.scale(8)}px;
                font-size: {self.scaling.scale_font(14)}px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #3a3a3a; }}
        """)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        def ok_key_handler(event):
            if event.isAutoRepeat():
                return
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                dialog.accept()
        
        dialog.keyPressEvent = ok_key_handler
        dialog.exec()
        
    def _show_error_dialog(self, title, message):
        """Показывает стилизованное диалоговое окно ошибки (только ОК)"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setFixedSize(self.scaling.scale(500), self.scaling.scale(400))
        
        dialog.setStyleSheet("""
            QDialog { 
                background-color: #1a1a1a; 
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(self.scaling.scale(20))
        layout.setContentsMargins(
            self.scaling.scale(30), 
            self.scaling.scale(30), 
            self.scaling.scale(30), 
            self.scaling.scale(30)
        )
        
        header_widget = QWidget()
        header_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #3a2a2a;
                border: 2px solid #ff4a4a;
                border-radius: {self.scaling.scale(10)}px;
                padding: {self.scaling.scale(15)}px;
            }}
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15)
        )
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(20)}px; 
                font-weight: bold;
                color: #ff4a4a;
                background: transparent;
                border: none;
            }}
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        layout.addWidget(header_widget)
        
        message_widget = QWidget()
        message_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border-radius: {self.scaling.scale(10)}px;
                padding: {self.scaling.scale(15)}px;
            }}
        """)
        message_layout = QVBoxLayout(message_widget)
        message_layout.setContentsMargins(
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15),
            self.scaling.scale(15)
        )
        
        message_label = QLabel(message)
        message_label.setStyleSheet(f"""
            QLabel {{
                font-size: {self.scaling.scale_font(13)}px;
                color: #cccccc;
                background: transparent;
                border: none;
            }}
        """)
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        message_label.setWordWrap(True)
        message_layout.addWidget(message_label)
        
        layout.addWidget(message_widget)
        layout.addStretch()
        
        ok_button = QPushButton("ОК")
        ok_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        ok_button.clicked.connect(dialog.accept)
        ok_button.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: white;
                border: 3px solid #ff4a4a;
                padding: {self.scaling.scale(12)}px {self.scaling.scale(40)}px;
                border-radius: {self.scaling.scale(8)}px;
                font-size: {self.scaling.scale_font(14)}px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #3a3a3a; }}
        """)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        def ok_key_handler(event):
            if event.isAutoRepeat():
                return
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                dialog.accept()
        
        dialog.keyPressEvent = ok_key_handler
        dialog.exec()

