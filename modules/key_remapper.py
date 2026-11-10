"""
Модуль переназначения клавиш для TV Launcher — СТИЛИЗОВАННАЯ ВЕРСИЯ
Соответствует визуальному дизайну лаунчера
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QScrollArea, QWidget,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer,QObject, QEvent 
from PyQt6.QtGui import QKeyEvent, QPixmap, QIcon
from pathlib import Path
import json

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class KeyMapper:
    """Основная логика маппинга — преобразует действия пользователя"""
    
    # Стандартные маппинги клавиатуры по умолчанию
    DEFAULT_KEYBOARD = {
        'navigate_left': Qt.Key.Key_Left,
        'navigate_right': Qt.Key.Key_Right,
        'navigate_up': Qt.Key.Key_Up,
        'navigate_down': Qt.Key.Key_Down,
        'launch': Qt.Key.Key_Return,
        'back': Qt.Key.Key_Escape,
        'edit': Qt.Key.Key_E,
        'delete': Qt.Key.Key_Delete,
        'quick_search': Qt.Key.Key_F,
        'reorder_mode': Qt.Key.Key_R,
        'settings': Qt.Key.Key_S,
        'change_category': Qt.Key.Key_C,
    }
    
    # Обратный маппинг из действий в стандартные клавиши
    ACTION_TO_DEFAULT_KEY = {
        'navigate_left': Qt.Key.Key_Left,
        'navigate_right': Qt.Key.Key_Right,
        'navigate_up': Qt.Key.Key_Up,
        'navigate_down': Qt.Key.Key_Down,
        'launch': Qt.Key.Key_Return,
        'back': Qt.Key.Key_Escape,
        'edit': Qt.Key.Key_E,
        'delete': Qt.Key.Key_Delete,
        'quick_search': Qt.Key.Key_F,
        'reorder_mode': Qt.Key.Key_R,
        'settings': Qt.Key.Key_S,
        'change_category': Qt.Key.Key_C,
    }
    
    @staticmethod
    def get_default_config():
        """Получить конфигурацию по умолчанию для новых установок или сброса"""
        mapper = KeyMapper.__new__(KeyMapper)
        mapper._reset_to_defaults()
        return {
            'current_profile': 'keyboard',
            'mappings': mapper.mappings
        }
    
    
    
    PROFILES = {
        'keyboard': ('⌨️ Клавиатура / Пульт ДУ', DEFAULT_KEYBOARD),
        
    }
    
    ACTION_NAMES = {
        'navigate_left': 'Влево',
        'navigate_right': 'Вправо',
        'navigate_up': 'Вверх',
        'navigate_down': 'Вниз',
        'launch': 'Запустить приложение',
        'back': 'Назад / Отмена',
        'edit': 'Изменить приложение',
        'delete': 'Удалить приложение',
        'quick_search': 'Быстрый поиск',
        'reorder_mode': 'Режим сортировки',
        'settings': 'Меню настроек',
        'change_category': 'Изменить категорию',
    }
    
    def __init__(self, config_file='key_mappings.json'):
        self.config_file = Path(config_file)
        self.current_profile = 'keyboard'
        self.mappings = {}
        self.load_mappings()
    
    
    def translate_key(self, pressed_key):
        """
        Переводит нажатую клавишу в стандартную клавишу, которую ожидает лаунчер
        
        Пример:
        - Пользователь назначил "Settings" на Qt.Key.Key_P
        - Пользователь нажимает P
        - translate_key(Qt.Key.Key_P) → возвращает Qt.Key.Key_S
        - Лаунчер получает Qt.Key.Key_S и открывает настройки
        """
        # Получаем действие, связанное с нажатой клавишей
        action = self.get_action_for_key(pressed_key)
        
        if action:
            # Возвращаем стандартную клавишу для этого действия
            return self.ACTION_TO_DEFAULT_KEY.get(action, pressed_key)
        
        # Если клавиша не привязана, возвращаем оригинальную
        return pressed_key
    
    def load_mappings(self):
        """Загрузка маппингов из файла или использование значений по умолчанию"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.current_profile = 'keyboard'  # ← Всегда keyboard
                    self.mappings = data.get('mappings', {})
                    
                    # Убедимся, что существует только профиль keyboard
                    if 'keyboard' not in self.mappings:
                        self.mappings['keyboard'] = self._serialize_mapping(
                            self.DEFAULT_KEYBOARD
                        )
            except:
                self._reset_to_defaults()
        else:
            self._reset_to_defaults()

    def _reset_to_defaults(self):
        """Сброс к маппингу клавиатуры по умолчанию"""
        self.mappings = {
            'keyboard': self._serialize_mapping(self.DEFAULT_KEYBOARD)
        }
        self.current_profile = 'keyboard'
    
    def save_mappings(self):
        """Сохранение маппингов в файл"""
        data = {
            'current_profile': self.current_profile,
            'mappings': self.mappings
        }
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _reset_to_defaults(self):
        """Сброс всех профилей к маппингам по умолчанию"""
        self.mappings = {}
        for profile_id, (_, default_map) in self.PROFILES.items():
            self.mappings[profile_id] = self._serialize_mapping(default_map)
    
    def _serialize_mapping(self, mapping):
        """Конвертация Qt.Key enum в сериализуемый формат"""
        serialized = {}
        for action, key in mapping.items():
            if isinstance(key, Qt.Key):
                serialized[action] = f"key_{key.value}"
            else:
                serialized[action] = key
        return serialized
    
    def _deserialize_key(self, key_str):
        """Конвертация сериализованной клавиши обратно в Qt.Key или строку кнопки"""
        # Обработка целых чисел (для обратной совместимости)
        if isinstance(key_str, int):
            try:
                return Qt.Key(key_str)
            except:
                print(f"⚠️ Не удалось конвертировать int {key_str} в Qt.Key")
                return key_str
        
        # Обработка сериализованных строк "key_XXXXX"
        if isinstance(key_str, str) and key_str.startswith('key_'):
            try:
                key_value = int(key_str.split('_')[1])
                return Qt.Key(key_value)
            except Exception as e:
                print(f"⚠️ Ошибка десериализации {key_str}: {e}")
                return key_str
        
        # Строки кнопок (button_0, dpad_left и т.д.)
        return key_str
    
    def get_current_mappings(self):
        """Получение маппингов текущего профиля"""
        mapping = self.mappings.get(self.current_profile, {})
        return {action: self._deserialize_key(key) for action, key in mapping.items()}
    
    def set_profile(self, profile_id):
        """Переключение на другой профиль"""
        if profile_id in self.PROFILES:
            self.current_profile = profile_id
            self.save_mappings()
    
    def remap_action(self, action, new_key):
        """Переназначение конкретного действия на новую клавишу"""
        if action in self.ACTION_NAMES:
            if isinstance(new_key, Qt.Key):
                self.mappings[self.current_profile][action] = f"key_{new_key.value}"
            else:
                self.mappings[self.current_profile][action] = new_key
            self.save_mappings()
    
    def get_action_for_key(self, key):
        """Получение имени действия для заданной клавиши/кнопки"""
        current = self.get_current_mappings()
        for action, mapped_key in current.items():
            if mapped_key == key:
                return action
        return None
    
    def reset_profile_to_default(self):
        """Сброс текущего профиля к значениям по умолчанию"""
        if self.current_profile in self.PROFILES:
            default_map = self.PROFILES[self.current_profile][1]
            self.mappings[self.current_profile] = self._serialize_mapping(default_map)
            self.save_mappings()
    
    # Глобальный фильтр событий для автоматического перевода клавиш
    def install_event_filter(self, app):
        """
        Установка глобального фильтра для автоматического перевода всех клавиш
        """
        class KeyTranslatorFilter(QObject):
            def __init__(self, mapper):
                super().__init__()
                self.mapper = mapper
            
            def eventFilter(self, obj, event):
                # Перехватываем только события KeyPress
                if event.type() == QEvent.Type.KeyPress:
                    original_key = event.key()
                    translated_key = self.mapper.translate_key(original_key)
                    
                    # Если клавиша была переведена, заменяем её
                    if translated_key != original_key:
                        try:
                            # Создаем новое событие с переведенной клавишей
                            new_event = QKeyEvent(
                                QEvent.Type.KeyPress,
                                translated_key,
                                event.modifiers(),
                                event.text(),
                                event.isAutoRepeat(),
                                event.count()
                            )
                            # Отправляем новое событие
                            app.sendEvent(obj, new_event)
                            return True  # Блокируем оригинальное событие
                        except:
                            pass
                
                return False  # Пропускаем остальные события
        
        self.filter = KeyTranslatorFilter(self)
        app.installEventFilter(self.filter)


class KeyCaptureDialog(QDialog):
    """Диалог для захвата нажатия одной клавиши / кнопки — СТИЛИЗОВАННАЯ ВЕРСИЯ"""
    
    key_captured = pyqtSignal(object)
    
    def __init__(self, action_name, scaling, parent=None):
        super().__init__(parent)
        self.action_name = action_name
        self.scaling = scaling
        self.captured_key = None
        self.joystick = None
        self.timer = None
        
        # ВАЖНО: Инициализируем instruction_label ДО вызова init_ui
        self.instruction_label = None
        
        if PYGAME_AVAILABLE:
            try:
                pygame.joystick.init()
                if pygame.joystick.get_count() > 0:
                    self.joystick = pygame.joystick.Joystick(0)
                    self.joystick.init()
            except:
                pass
        
        self.init_ui()
        
        if self.joystick:
            self.timer = QTimer()
            self.timer.timeout.connect(self.poll_joystick)
            self.timer.start(16)
    
    def init_ui(self):
        self.setWindowTitle("Захват ввода")
        self.setModal(True)
        self.setFixedSize(self.scaling.scale(550), self.scaling.scale(350))
        
        # ВАЖНО: Разрешаем фокус для перехвата клавиш
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Стиль, согласованный с меню настроек
        self.setStyleSheet("""
            QDialog { 
                background-color: #1a1a1a; 
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(self.scaling.scale(25))
        layout.setContentsMargins(
            self.scaling.scale(30),
            self.scaling.scale(30),
            self.scaling.scale(30),
            self.scaling.scale(30)
        )
        
        # === ШАПКА ===
        header_widget = QWidget()
        header_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border-radius: {self.scaling.scale(10)}px;
                padding: {self.scaling.scale(20)}px;
            }}
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setSpacing(self.scaling.scale(10))
        
        title = QLabel("🎮 Переназначение действия")
        title.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(20)}px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)
        
        action_label = QLabel(self.action_name)
        action_label.setStyleSheet(f"""
            QLabel {{
                color: #4a9eff;
                font-size: {self.scaling.scale_font(16)}px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        action_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(action_label)
        
        layout.addWidget(header_widget)
        
        # === БЛОК ИНСТРУКЦИЙ ===
        instruction_box = QWidget()
        instruction_box.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: 2px solid #4a9eff;
                border-radius: {self.scaling.scale(10)}px;
                padding: {self.scaling.scale(30)}px;
            }}
        """)
        
        instruction_layout = QVBoxLayout(instruction_box)
        instruction_layout.setSpacing(self.scaling.scale(15))
        
        
        self.instruction_label = QLabel("⌨️ Нажмите любую клавишу или кнопку...")
        
        self.instruction_label.setStyleSheet(f"""
            QLabel {{
                color: #4a9eff;
                font-size: {self.scaling.scale_font(18)}px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instruction_label.setWordWrap(True)
        instruction_layout.addWidget(self.instruction_label)
        
        hint = QLabel("(или Esc для отмены)")
        hint.setStyleSheet(f"""
            QLabel {{
                color: #888;
                font-size: {self.scaling.scale_font(13)}px;
                background: transparent;
                border: none;
            }}
        """)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_layout.addWidget(hint)
        
        layout.addWidget(instruction_box)
        layout.addStretch()
        
        
        
        # === КНОПКА ОТМЕНЫ ===
        cancel_btn = QPushButton("Отмена (Esc)")
        cancel_btn.setFixedHeight(self.scaling.scale(50))
        cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Только эта кнопка не должна иметь фокус
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: white;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(8)}px;
                font-size: {self.scaling.scale_font(14)}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        self.setLayout(layout)
        
        # Принудительно устанавливаем фокус на диалог при открытии
        QTimer.singleShot(50, lambda: self.setFocus())
    
    def poll_joystick(self):
        """Опрос джойстика с визуальным откликом"""
        if not self.joystick:
            return
        
        # Проверка безопасности
        if self.instruction_label is None:
            return
        
        try:
            pygame.event.pump()
            
            # Проверка кнопок
            for i in range(self.joystick.get_numbuttons()):
                if self.joystick.get_button(i):
                    self.captured_key = f"button_{i}"
                    # Визуальный отклик
                    self.instruction_label.setText(f"✅ Захвачено: Кнопка {i}")
                    self.instruction_label.setStyleSheet(f"""
                        QLabel {{
                            color: #4CAF50;
                            font-size: {self.scaling.scale_font(18)}px;
                            font-weight: bold;
                            background: transparent;
                            border: none;
                        }}
                    """)
                    QTimer.singleShot(300, self.accept)
                    return
            
            # Проверка D-Pad (крестовины)
            if self.joystick.get_numhats() > 0:
                hat = self.joystick.get_hat(0)
                direction_map = {
                    (1, 0): ("dpad_right", "→ Крестовина Вправо"),
                    (-1, 0): ("dpad_left", "← Крестовина Влево"),
                    (0, 1): ("dpad_up", "↑ Крестовина Вверх"),
                    (0, -1): ("dpad_down", "↓ Крестовина Вниз"),
                }
                
                if hat in direction_map:
                    key, display = direction_map[hat]
                    self.captured_key = key
                    # Визуальный отклик
                    self.instruction_label.setText(f"✅ Захвачено: {display}")
                    self.instruction_label.setStyleSheet(f"""
                        QLabel {{
                            color: #4CAF50;
                            font-size: {self.scaling.scale_font(18)}px;
                            font-weight: bold;
                            background: transparent;
                            border: none;
                        }}
                    """)
                    QTimer.singleShot(300, self.accept)
                    return
        except:
            pass
    
    def keyPressEvent(self, event: QKeyEvent):
        """Захват ввода с клавиатуры с визуальным откликом"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        
        # Показываем визуальный отклик
        self.captured_key = event.key()
        
        # Проверка безопасности
        if self.instruction_label is None:
            print("⚠️ Предупреждение: instruction_label равен None!")
            self.accept()
            return
        
        # Обновляем текст с подтверждением
        key_display = self._get_key_display_name(self.captured_key)
        self.instruction_label.setText(f"✅ Захвачено: {key_display}")
        self.instruction_label.setStyleSheet(f"""
            QLabel {{
                color: #4CAF50;
                font-size: {self.scaling.scale_font(18)}px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        
        # Закрываем диалог после небольшой задержки для отображения отклика
        QTimer.singleShot(300, self.accept)
    
    def _get_key_display_name(self, key):
        """Получение читаемого имени для клавиши"""
        special_keys = {
            Qt.Key.Key_Left: "← Влево",
            Qt.Key.Key_Right: "→ Вправо",
            Qt.Key.Key_Up: "↑ Вверх",
            Qt.Key.Key_Down: "↓ Вниз",
            Qt.Key.Key_Return: "Enter",
            Qt.Key.Key_Space: "Пробел",
            Qt.Key.Key_Delete: "Delete",
            Qt.Key.Key_Backspace: "Backspace",
        }
        
        if key in special_keys:
            return special_keys[key]
        
        try:
            text = QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier).text()
            if text and text.strip():
                return text.upper()
        except:
            pass
        
        try:
            name = key.name
            if name.startswith('Key_'):
                name = name[4:]
            return name
        except:
            return "Клавиша"
    
    def get_captured_key(self):
        return self.captured_key
    
    def closeEvent(self, event):
        if self.timer:
            self.timer.stop()
        if self.joystick:
            try:
                self.joystick.quit()
            except:
                pass
        event.accept()
        
    def install_event_filter(self, app):
        """
        Установка глобального фильтра для автоматического перевода всех клавиш.
        Вызывайте сразу после создания KeyMapper в лаунчере.
        """
        class KeyTranslatorFilter(QObject):
            def __init__(self, mapper):
                super().__init__()
                self.mapper = mapper
            
            def eventFilter(self, obj, event):
                # Перехватываем только события KeyPress
                if event.type() == QEvent.Type.KeyPress:
                    original_key = event.key()
                    translated_key = self.mapper.translate_key(original_key)
                    
                    # Если клавиша была переведена, создаем новое событие
                    if translated_key != original_key:
                        # Создаем новое событие с переведенной клавишей
                        new_event = QKeyEvent(
                            QEvent.Type.KeyPress,
                            translated_key,
                            event.modifiers(),
                            event.text(),
                            event.isAutoRepeat(),
                            event.count()
                        )
                        # Заменяем оригинальное событие
                        app.postEvent(obj, new_event)
                        return True  # Блокируем оригинальное событие
                
                return False  # Пропускаем остальные события
        
        from PyQt6.QtCore import QObject, QEvent
        self.filter = KeyTranslatorFilter(self)
        app.installEventFilter(self.filter)    


class KeyRemapperDialog(QDialog):
    """Главный диалог переназначения клавиш — ФИНАЛЬНАЯ ВЕРСИЯ (в стиле лаунчера)"""
    
    mappings_changed = pyqtSignal(dict)
    
    def __init__(self, launcher, scaling, parent=None):
        super().__init__(parent)
        self.launcher = launcher
        self.scaling = scaling
        
        if hasattr(launcher, 'key_mapper'):
            self.mapper = launcher.key_mapper
        else:
            self.mapper = KeyMapper()
        
        self.action_buttons = {}
        self.current_index = 0
        self.focusable_items = []
        
        self.init_ui()
        self.update_all_bindings()
    
    def init_ui(self):
        self.setWindowTitle("Настройка клавиш")
        self.setModal(True)
        self.setFixedSize(self.scaling.scale(900), self.scaling.scale(900))
        
        # Фоновый цвет, согласованный с лаунчером
        self.setStyleSheet("""
            QDialog { 
                background-color: #0f0f0f;
            }
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === ШАПКА ===
        header = self._create_header()
        main_layout.addWidget(header)
        
        # === ИНФОРМАЦИОННЫЙ БАННЕР ===
        info_banner = self._create_info_banner()
        main_layout.addWidget(info_banner)
        
        # === ОБЛАСТЬ ПРОКРУТКИ ===
        scroll = self._create_scroll_area()
        content = self._create_content()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # === НИЖНЯЯ ПАНЕЛЬ (FOOTER) ===
        footer = self._create_footer()
        main_layout.addWidget(footer)
        
        self.setLayout(main_layout)
        self.update_focus()
    
    def _create_header(self):
        """Простая шапка без кнопки закрытия (крестика)"""
        header = QWidget()
        header.setFixedHeight(self.scaling.scale(140))
        header.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-bottom: 2px solid #444;
            }
        """)
        
        layout = QVBoxLayout(header)
        layout.setSpacing(self.scaling.scale(8))
        layout.setContentsMargins(
            self.scaling.scale(40),
            self.scaling.scale(35),
            self.scaling.scale(40),
            self.scaling.scale(25)
        )
        
        # Горизонтальный контейнер для иконки и заголовка
        title_container = QWidget()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QHBoxLayout(title_container)
        title_layout.setSpacing(self.scaling.scale(15))
        title_layout.setContentsMargins(0, 0, 0, 0)

        # Пользовательская иконка
        icon_label = QLabel()
        icon_path = Path("assets/icons/remote.png")
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            scaled_pixmap = pixmap.scaled(
                self.scaling.scale(40),
                self.scaling.scale(40),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            icon_label.setPixmap(scaled_pixmap)
        else:
            icon_label.setText("🎮")
            icon_label.setStyleSheet(f"""
                QLabel {{
                    color: white;
                    font-size: {self.scaling.scale_font(36)}px;
                    background: transparent;
                    border: none;
                }}
            """)
        title_layout.addWidget(icon_label)

        # Главный заголовок
        title = QLabel("Настройка клавиш")
        title.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(36)}px;
                font-weight: 700;
                background: transparent;
                border: none;
            }}
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_layout.addWidget(title)
        title_layout.addStretch()

        layout.addWidget(title_container)
        
        # Подзаголовок
        subtitle = QLabel("Настройте клавиатуру и кнопки пульта дистанционного управления")
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.5);
                font-size: {self.scaling.scale_font(15)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(subtitle)
        
        return header
    
    def _create_info_banner(self):
        """Информационный баннер в стиле лаунчера"""
        banner = QWidget()
        banner.setFixedHeight(self.scaling.scale(90))
        banner.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                border-bottom: 1px solid #444;
            }
        """)
        
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(
            self.scaling.scale(40),
            self.scaling.scale(20),
            self.scaling.scale(40),
            self.scaling.scale(20)
        )
        layout.setSpacing(self.scaling.scale(20))
        
        # Пользовательская иконка клавиатуры
        icon_label = QLabel()
        icon_label.setFixedSize(self.scaling.scale(36), self.scaling.scale(36))
        icon_path = Path("assets/icons/keyboard.png")
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            scaled_pixmap = pixmap.scaled(
                self.scaling.scale(36),  # Немного меньше
                self.scaling.scale(36),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            icon_label.setPixmap(scaled_pixmap)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setScaledContents(False)
        else:
            icon_label.setText("⌨️")
            icon_label.setStyleSheet(f"""
                QLabel {{
                    color: white;
                    font-size: {self.scaling.scale_font(36)}px;
                    background: transparent;
                    border: none;
                }}
            """)
        layout.addWidget(icon_label)
        
        # Информационный текст
        info_text = QLabel(
            "<b style='color: white; font-size: 15px;'>Раскладки клавиатуры и пульта</b><br>"
            "<span style='color: rgba(255,255,255,0.5); font-size: 13px;'>"
            "Контроллеры Xbox/PlayStation работают без дополнительной настройки"
            "</span>"
        )
        info_text.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                line-height: 1.5;
            }
        """)
        layout.addWidget(info_text, 1)
        
        layout.addStretch()
        
        # Кнопка сброса с кастомной иконкой
        reset_btn = QPushButton(" Сбросить")
        reset_icon_path = Path("assets/icons/refresh.png")
        if reset_icon_path.exists():
            reset_btn.setIcon(QIcon(str(reset_icon_path)))
            from PyQt6.QtCore import QSize
            reset_btn.setIconSize(QSize(self.scaling.scale(20), self.scaling.scale(20)))
        else:
            reset_btn.setText("🔄 Сбросить")

        reset_btn.setFixedSize(self.scaling.scale(140), self.scaling.scale(50))
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: white;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(8)}px;
                font-size: {self.scaling.scale_font(14)}px;
                font-weight: bold;
                text-align: left;
                padding-left: {self.scaling.scale(15)}px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        reset_btn.clicked.connect(self._reset_current_profile)
        layout.addWidget(reset_btn)

        self.focusable_items.append(reset_btn)
        self.reset_btn = reset_btn

        return banner
    
    def _create_scroll_area(self):
        """Область прокрутки в стиле лаунчера"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: #0f0f0f;
            }}
            QScrollBar:vertical {{
                background-color: #2a2a2a;
                width: {self.scaling.scale(10)}px;
                border-radius: {self.scaling.scale(5)}px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #444;
                border-radius: {self.scaling.scale(4)}px;
                min-height: {self.scaling.scale(40)}px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #555;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        return scroll
    
    def _create_content(self):
        """Контент с категориями разделов"""
        content = QWidget()
        content.setStyleSheet("background: #1a1a1a")
        
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            self.scaling.scale(40),
            self.scaling.scale(30),
            self.scaling.scale(40),
            self.scaling.scale(30)
        )
        layout.setSpacing(self.scaling.scale(25))
        
        # КАТЕГОРИЗИРОВАННЫЕ РАЗДЕЛЫ
        sections = [
            (" Навигация", "Перемещение по интерфейсу", [
                ('navigate_left', 'Влево'),
                ('navigate_right', 'Вправо'),
                ('navigate_up', 'Вверх'),
                ('navigate_down', 'Вниз'),
            ]),
            (" Основные действия", "Основные элементы управления приложениями", [
                ('launch', 'Запустить приложение'),
                ('back', 'Назад / Отмена'),
                ('edit', 'Изменить приложение'),
                ('delete', 'Удалить приложение'),
            ]),
            (" Функции", "Расширенные возможности", [
                ('quick_search', 'Быстрый поиск'),
                ('reorder_mode', 'Режим сортировки'),
                ('settings', 'Меню настроек'),
                ('change_category', 'Изменить категорию'),
            ]),
        ]
        
        for section_icon, section_desc, actions in sections:
            # Шапка раздела
            section_header = self._create_section_header(section_icon, section_desc)
            layout.addWidget(section_header)
            
            # Действия в этом разделе
            for action_id, action_name in actions:
                action_row = self._create_action_row(action_id, action_name)
                layout.addWidget(action_row)
            
            # Отступ между секциями
            layout.addSpacing(self.scaling.scale(15))
        
        layout.addStretch()
        
        return content
    
    def _create_section_header(self, title, description):
        """Простая шапка раздела"""
        header = QWidget()
        header.setFixedHeight(self.scaling.scale(60))
        header.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout(header)
        layout.setSpacing(self.scaling.scale(5))
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(18)}px;
                font-weight: 700;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(title_label)
        
        # Описание
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.4);
                font-size: {self.scaling.scale_font(12)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(desc_label)
        
        return header
    
    def _create_action_row(self, action_id, action_name):
        """Строка действия в стиле лаунчера (серый фон)"""
        row = QWidget()
        row.setFixedHeight(self.scaling.scale(75))
        row.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(12)}px;
            }}
            QWidget:hover {{
                background-color: #3a3a3a;
            }}
        """)
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(
            self.scaling.scale(25),
            self.scaling.scale(15),
            self.scaling.scale(20),
            self.scaling.scale(15)
        )
        layout.setSpacing(self.scaling.scale(15))
        
        # Имя действия с подсказкой
        name_container = QWidget()
        name_container.setStyleSheet("background: transparent; border: none;")
        name_layout = QVBoxLayout(name_container)
        name_layout.setSpacing(self.scaling.scale(3))
        name_layout.setContentsMargins(0, 0, 0, 0)
        
        name_label = QLabel(action_name)
        name_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(15)}px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        name_layout.addWidget(name_label)
        
        # Подзаголовок-подсказка
        hint_texts = {
            'navigate_left': 'Перемещение карусели влево',
            'navigate_right': 'Перемещение карусели вправо',
            'navigate_up': 'Перейти в меню',
            'navigate_down': 'Открыть нижнее меню',
            'launch': 'Запустить выбранное приложение',
            'back': 'Выход или отмена',
            'edit': 'Изменить данные приложения',
            'delete': 'Удалить приложение',
            'quick_search': 'Быстрый поиск приложений',
            'reorder_mode': 'Перестановка приложений',
            'settings': 'Открыть панель настроек',
            'change_category': 'Быстрое изменение категории',
        }
        
        hint_label = QLabel(hint_texts.get(action_id, ''))
        hint_label.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.35);
                font-size: {self.scaling.scale_font(11)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        name_layout.addWidget(hint_label)
        
        layout.addWidget(name_container, 1)
        
        layout.addStretch()
        
        # Текущая привязка (значок в стиле лаунчера)
        binding_label = QLabel("...")
        binding_label.setFixedHeight(self.scaling.scale(40))
        binding_label.setMinimumWidth(self.scaling.scale(100))
        binding_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(13)}px;
                font-weight: 700;
                background-color: #1a1a1a;
                border: 2px solid #555;
                border-radius: {self.scaling.scale(20)}px;
                padding: 0px {self.scaling.scale(16)}px;
            }}
        """)
        binding_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(binding_label)
        
        # Кнопка изменения в стиле лаунчера
        change_btn = QPushButton("Изменить")
        change_btn.setFixedSize(self.scaling.scale(110), self.scaling.scale(40))
        change_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #3a3a3a;
                color: white;
                border: 2px solid #555;
                border-radius: {self.scaling.scale(8)}px;
                font-size: {self.scaling.scale_font(13)}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #4a4a4a;
            }}
        """)
        change_btn.clicked.connect(lambda: self._remap_action(action_id, action_name))
        layout.addWidget(change_btn)
        
        self.action_buttons[action_id] = (binding_label, change_btn)
        self.focusable_items.append(change_btn)
        
        return row
    
    def _create_footer(self):
        """Нижняя панель (футер) в стиле лаунчера"""
        footer = QWidget()
        footer.setFixedHeight(self.scaling.scale(100))
        footer.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-top: 2px solid #444;
            }
        """)
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(
            self.scaling.scale(40),
            self.scaling.scale(25),
            self.scaling.scale(40),
            self.scaling.scale(25)
        )
        layout.setSpacing(self.scaling.scale(20))
        
        # Подсказка слева
        hint = QLabel("Навигация: ↑↓  •  Выбор: Enter  •  Закрыть: Esc")
        hint.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.4);
                font-size: {self.scaling.scale_font(13)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(hint)
        
        layout.addStretch()
        
        # Кнопка сохранения в стиле лаунчера (без градиента)
        save_btn = QPushButton(" Сохранить и закрыть")
        save_icon_path = Path("assets/icons/backup.png")
        if save_icon_path.exists():
            save_btn.setIcon(QIcon(str(save_icon_path)))
            from PyQt6.QtCore import QSize
            save_btn.setIconSize(QSize(self.scaling.scale(24), self.scaling.scale(24)))
        else:
            save_btn.setText("💾 Сохранить и закрыть")
        
        save_btn.setFixedSize(self.scaling.scale(230), self.scaling.scale(55))
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: white;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(8)}px;
                font-size: {self.scaling.scale_font(16)}px;
                font-weight: bold;
                text-align: left;
                padding-left: {self.scaling.scale(20)}px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
        """)
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)
        
        self.focusable_items.append(save_btn)
        self.save_btn = save_btn
        
        return footer
    
    
    
    def _reset_current_profile(self):
        """Сброс с визуальным подтверждением"""
        self.mapper.reset_profile_to_default()
        self.update_all_bindings()
        self.mappings_changed.emit(self.mapper.get_current_mappings())
        
        # Временный визуальный отклик
        if hasattr(self, 'reset_btn'):
            original_text = self.reset_btn.text()
            self.reset_btn.setText("✓ Сброшено!")
            self.reset_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #3a3a3a;
                    color: white;
                    border: 2px solid white;
                    border-radius: {self.scaling.scale(8)}px;
                    font-size: {self.scaling.scale_font(14)}px;
                    font-weight: bold;
                }}
            """)
            QTimer.singleShot(1500, lambda: self._restore_reset_button(original_text))
    
    def _restore_reset_button(self, original_text):
        """Восстановление стиля кнопки сброса"""
        if hasattr(self, 'reset_btn'):
            self.reset_btn.setText(original_text)
            self.reset_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2a2a2a;
                    color: white;
                    border: 2px solid #444;
                    border-radius: {self.scaling.scale(8)}px;
                    font-size: {self.scaling.scale_font(14)}px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #3a3a3a;
                }}
            """)
    
    def _remap_action(self, action_id, action_name):
        """Открытие диалога для переназначения"""
        dialog = KeyCaptureDialog(action_name, self.scaling, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_key = dialog.get_captured_key()
            if new_key:
                self.mapper.remap_action(action_id, new_key)
                self.update_all_bindings()
                self.mappings_changed.emit(self.mapper.get_current_mappings())
    
    def update_all_bindings(self):
        """Обновление всех привязок"""
        current_mappings = self.mapper.get_current_mappings()
        
        for action_id, (label, _) in self.action_buttons.items():
            binding = current_mappings.get(action_id)
            display_text = self._format_binding(binding)
            label.setText(display_text)
    
    def _format_binding(self, binding):
        """Форматирование привязки с иконками"""
        if binding is None:
            return "Не задано"
        
        if isinstance(binding, int):
            try:
                binding = Qt.Key(binding)
            except:
                return f"Клавиша {binding}"
        
        if isinstance(binding, Qt.Key):
            special_keys = {
                Qt.Key.Key_Left: "← Влево",
                Qt.Key.Key_Right: "→ Вправо",
                Qt.Key.Key_Up: "↑ Вверх",
                Qt.Key.Key_Down: "↓ Вниз",
                Qt.Key.Key_Return: "⏎ Enter",
                Qt.Key.Key_Enter: "⏎ Enter",
                Qt.Key.Key_Escape: "⎋ Esc",
                Qt.Key.Key_Delete: "⌫ Del",
                Qt.Key.Key_Space: "␣ Пробел",
                Qt.Key.Key_F: "F",
                Qt.Key.Key_R: "R",
                Qt.Key.Key_S: "S",
                Qt.Key.Key_E: "E",
            }
            
            if binding in special_keys:
                return special_keys[binding]
            
            try:
                key_name = QKeyEvent(QKeyEvent.Type.KeyPress, binding, Qt.KeyboardModifier.NoModifier).text()
                if key_name and key_name.strip():
                    return key_name.upper()
            except:
                pass
            
            try:
                name = binding.name
                if name.startswith('Key_'):
                    name = name[4:]
                return name.replace('_', ' ').title()
            except:
                return f"Клавиша {int(binding)}"
        
        elif isinstance(binding, str):
            if binding.startswith('button_'):
                btn_num = binding.split('_')[1]
                return f"🎮 Кн. {btn_num}"
            elif binding.startswith('dpad_'):
                direction = binding.split('_')[1].capitalize()
                arrows = {'Up': '↑', 'Down': '↓', 'Left': '←', 'Right': '→'}
                return f"{arrows.get(direction, '')} Крестовина"
        
        return "Неизвестно"
    
    def update_focus(self):
        """Фокус с белой рамкой в стиле лаунчера"""
        for i, item in enumerate(self.focusable_items):
            if i == self.current_index:
                if isinstance(item, QPushButton):
                    if "Сбросить" in item.text():
                        # Фокус на кнопке сброса
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #3a3a3a;
                                color: white;
                                border: 3px solid white;
                                border-radius: {self.scaling.scale(8)}px;
                                font-size: {self.scaling.scale_font(14)}px;
                                font-weight: bold;
                            }}
                        """)
                    elif "Сохранить" in item.text():
                        # Фокус на кнопке сохранения
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #3a3a3a;
                                color: white;
                                border: 3px solid white;
                                border-radius: {self.scaling.scale(8)}px;
                                font-size: {self.scaling.scale_font(16)}px;
                                font-weight: bold;
                            }}
                        """)
                    else:
                        # Фокус на кнопке изменения
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #4a4a4a;
                                color: white;
                                border: 3px solid white;
                                border-radius: {self.scaling.scale(8)}px;
                                font-size: {self.scaling.scale_font(13)}px;
                                font-weight: bold;
                            }}
                        """)
            else:
                # Стили без фокуса
                if isinstance(item, QPushButton):
                    if "Сбросить" in item.text():
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #2a2a2a;
                                color: white;
                                border: 2px solid #444;
                                border-radius: {self.scaling.scale(8)}px;
                                font-size: {self.scaling.scale_font(14)}px;
                                font-weight: bold;
                            }}
                            QPushButton:hover {{
                                background-color: #3a3a3a;
                            }}
                        """)
                    elif "Сохранить" in item.text():
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #2a2a2a;
                                color: white;
                                border: 2px solid #444;
                                border-radius: {self.scaling.scale(8)}px;
                                font-size: {self.scaling.scale_font(16)}px;
                                font-weight: bold;
                            }}
                            QPushButton:hover {{
                                background-color: #3a3a3a;
                            }}
                        """)
                    else:
                        item.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #3a3a3a;
                                color: white;
                                border: 2px solid #555;
                                border-radius: {self.scaling.scale(8)}px;
                                font-size: {self.scaling.scale_font(13)}px;
                                font-weight: bold;
                            }}
                            QPushButton:hover {{
                                background-color: #4a4a4a;
                            }}
                        """)
    
    def keyPressEvent(self, event):
        """Навигация с помощью клавиатуры"""
        if event.isAutoRepeat():
            return
        
        key = event.key()
        
        if key == Qt.Key.Key_Up:
            if self.current_index > 0:
                self.current_index -= 1
                self.update_focus()
                self._ensure_visible()
        elif key == Qt.Key.Key_Down:
            if self.current_index < len(self.focusable_items) - 1:
                self.current_index += 1
                self.update_focus()
                self._ensure_visible()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current_item = self.focusable_items[self.current_index]
            if isinstance(current_item, QPushButton):
                current_item.click()
        elif key == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)
    
    def _ensure_visible(self):
        """Автоматическая прокрутка к активному элементу в фокусе"""
        if not self.focusable_items or self.current_index >= len(self.focusable_items):
            return
        
        current_item = self.focusable_items[self.current_index]
        
        # Находим область прокрутки (scroll area)
        scroll_area = None
        parent = current_item.parent()
        while parent:
            if isinstance(parent, QScrollArea):
                scroll_area = parent
                break
            parent = parent.parent()
        
        if not scroll_area:
            return
        
        # Вычисляем позицию
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
        padding = self.scaling.scale(50)
        
        # Прокручиваем при необходимости
        if item_bottom + padding > visible_bottom:
            new_scroll = item_bottom - viewport_height + padding
            scrollbar.setValue(int(new_scroll))
        elif item_top - padding < visible_top:
            new_scroll = item_top - padding
            scrollbar.setValue(int(new_scroll))

