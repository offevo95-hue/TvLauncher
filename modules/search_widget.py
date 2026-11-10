import os
import platform
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QListWidget, QListWidgetItem, QGraphicsDropShadowEffect, QPushButton
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect, QSize
from PyQt6.QtGui import QFont, QKeyEvent, QColor, QPixmap, QIcon, QImage

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    try:
        import win32api
        import win32con
        import win32gui
        import win32ui
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False
        print("⚠️ win32api недоступен, иконки будут базовыми")
else:
    HAS_WIN32 = False


class QuickSearchWidget(QWidget):
    """
    Виджет быстрого поиска с динамической фильтрацией приложений.
    Поддерживает физическую клавиатуру и навигацию с геймпада/пульта ДУ.
    Интерфейс унифицирован с палитрой главного лаунчера.
    """
    app_selected = pyqtSignal(int)  # Выдает индекс выбранного приложения
    search_closed = pyqtSignal()    # Выдает сигнал при закрытии поиска
    
    def __init__(self, scaling, parent=None):
        super().__init__(parent)
        self.scaling = scaling
        self.apps = []  # Список приложений для поиска
        self.filtered_indices = []  # Индексы отфильтрованных приложений
        self.current_selection = 0
        self.is_typing_mode = True  # True = ввод текста, False = навигация по результатам
        
        # Ссылка на родительский объект для обработки ввода с геймпада
        self.launcher_parent = parent
        
        self.init_ui()
        self.hide()
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса с унифицированной палитрой"""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Адаптивные размеры
        width = self.scaling.scale(800)
        height = self.scaling.scale(600)
        self.setFixedSize(width, height)
        
        # Главный контейнер с темным фоном
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Внутренний контейнер — УНИФИЦИРОВАННАЯ ПАЛИТРА
        self.container = QWidget()
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: #1a1a1a;
                border-radius: {self.scaling.scale(20)}px;
                border: {self.scaling.scale(2)}px solid #444;
            }}
        """)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(self.scaling.scale(20))
        container_layout.setContentsMargins(
            self.scaling.scale(30),
            self.scaling.scale(30),
            self.scaling.scale(30),
            self.scaling.scale(30)
        )
        
        # === ШАПКА (HEADER) ===
        header_layout = QHBoxLayout()
        
        # Иконка поиска
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(f"""
            font-size: {self.scaling.scale_font(32)}px;
        """)
        header_layout.addWidget(search_icon)
        
        # Поле поиска — УНИФИЦИРОВАННАЯ ПАЛИТРА
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите текст для поиска приложений...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #2a2a2a;
                color: white;
                border: {self.scaling.scale(2)}px solid #444;
                border-radius: {self.scaling.scale(12)}px;
                padding: {self.scaling.scale(15)}px {self.scaling.scale(20)}px;
                font-size: {self.scaling.scale_font(20)}px;
                font-weight: 500;
            }}
            QLineEdit:focus {{
                border: {self.scaling.scale(2)}px solid white;
            }}
        """)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        header_layout.addWidget(self.search_input, stretch=1)
        
        # Кнопка закрытия — УНИФИЦИРОВАННАЯ ПАЛИТРА
        self.close_btn = QPushButton("✕")
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: rgba(255, 255, 255, 0.7);
                font-size: {self.scaling.scale_font(24)}px;
                border: {self.scaling.scale(2)}px solid #444;
                border-radius: {self.scaling.scale(20)}px;
                padding: {self.scaling.scale(8)}px;
                min-width: {self.scaling.scale(40)}px;
                min-height: {self.scaling.scale(40)}px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: #444;
            }}
        """)
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.clicked.connect(self.close_search)
        header_layout.addWidget(self.close_btn)
        
        container_layout.addLayout(header_layout)
        
        # Индикатор режима — УНИФИЦИРОВАННЫЕ ЦВЕТА
        self.mode_label = QLabel("🔤 РЕЖИМ ВВОДА")
        self.mode_label.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.6);
            font-size: {self.scaling.scale_font(11)}px;
            font-weight: 600;
            padding: {self.scaling.scale(5)}px {self.scaling.scale(10)}px;
        """)
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.mode_label)
        
        # === РЕЗУЛЬТАТЫ ===
        results_label = QLabel("Результаты")
        results_label.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.6);
            font-size: {self.scaling.scale_font(14)}px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        """)
        container_layout.addWidget(results_label)
        
        # Список результатов — УНИФИЦИРОВАННАЯ ПАЛИТРА
        self.results_list = QListWidget()
        self.results_list.setIconSize(QSize(32, 32))  # Как в program_scanner
        self.results_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #2a2a2a;
                border: {self.scaling.scale(2)}px solid #444;
                border-radius: {self.scaling.scale(12)}px;
                padding: {self.scaling.scale(10)}px;
                font-size: {self.scaling.scale_font(16)}px;
                outline: none;
            }}
            QListWidget::item {{
                color: rgba(255, 255, 255, 0.7);
                padding: {self.scaling.scale(15)}px {self.scaling.scale(20)}px;
                border-radius: {self.scaling.scale(8)}px;
                margin: {self.scaling.scale(2)}px 0px;
            }}
            QListWidget::item:selected {{
                background-color: #3a3a3a;
                color: white;
                font-weight: 600;
                border: {self.scaling.scale(2)}px solid white;
            }}
            QListWidget::item:hover {{
                background-color: #333;
            }}
        """)
        self.results_list.itemDoubleClicked.connect(self.on_item_activated)
        container_layout.addWidget(self.results_list, stretch=1)
        
        # === НИЖНЯЯ ПАНЕЛЬ (FOOTER) — Подсказки ===
        instructions_layout = QHBoxLayout()
        instructions_layout.setSpacing(self.scaling.scale(20))
        
        instructions = [
            ("Ввод", "Поиск"),
            ("↑↓", "Навигация"),
            ("Enter/A", "Запуск"),
            ("Esc/B", "Закрыть"),
            ("Tab/X", "Режим")
        ]
        
        for key, action in instructions:
            inst_widget = QWidget()
            inst_layout = QHBoxLayout(inst_widget)
            inst_layout.setContentsMargins(0, 0, 0, 0)
            inst_layout.setSpacing(self.scaling.scale(8))
            
            # Клавиши — УНИФИЦИРОВАННАЯ ПАЛИТРА
            key_label = QLabel(key)
            key_label.setStyleSheet(f"""
                background-color: #2a2a2a;
                color: white;
                padding: {self.scaling.scale(4)}px {self.scaling.scale(10)}px;
                border-radius: {self.scaling.scale(6)}px;
                border: {self.scaling.scale(1)}px solid #444;
                font-size: {self.scaling.scale_font(12)}px;
                font-weight: 600;
            """)
            
            action_label = QLabel(action)
            action_label.setStyleSheet(f"""
                color: rgba(255, 255, 255, 0.5);
                font-size: {self.scaling.scale_font(12)}px;
            """)
            
            inst_layout.addWidget(key_label)
            inst_layout.addWidget(action_label)
            instructions_layout.addWidget(inst_widget)
        
        instructions_layout.addStretch()
        container_layout.addLayout(instructions_layout)
        
        main_layout.addWidget(self.container)
        self.setLayout(main_layout)
        
        # Эффект тени
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(self.scaling.scale(50))
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, self.scaling.scale(10))
        self.container.setGraphicsEffect(shadow)
    
    def set_apps(self, apps):
        """Установка списка приложений для поиска"""
        self.apps = apps
        self.update_results()
    
    def show_search(self):
        """Отображение виджета поиска с анимацией"""
        if self.parent():
            # Центрирование относительно родительского элемента
            parent_rect = self.parent().geometry()
            x = (parent_rect.width() - self.width()) // 2
            y = (parent_rect.height() - self.height()) // 2
            self.move(x, y)
        
        self.show()
        self.raise_()
        
        # Сброс состояния
        self.search_input.clear()
        self.search_input.setFocus()
        self.is_typing_mode = True
        self.current_selection = 0
        self.update_mode_indicator()
        self.update_results()
        
        # Анимация появления
        self.setWindowOpacity(0)
        fade_in = QPropertyAnimation(self, b"windowOpacity")
        fade_in.setDuration(200)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_in.start()
        self.fade_animation = fade_in
    
    def close_search(self):
        """Закрытие виджета поиска с анимацией"""
        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(150)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        fade_out.finished.connect(self.hide)
        fade_out.finished.connect(self.search_closed.emit)
        fade_out.start()
        self.fade_animation = fade_out
    
    def on_search_text_changed(self, text):
        """Обработка изменения текста поиска"""
        self.update_results()
        # Автоматическое переключение в режим ввода при наборе текста
        if text and not self.is_typing_mode:
            self.is_typing_mode = True
            self.update_mode_indicator()
    
    def _extract_icon_from_exe(self, exe_path):
        """Извлечение иконки из exe-файла — ТОЧНАЯ КОПИЯ из program_scanner.py"""
        try:
            from PyQt6.QtWidgets import QFileIconProvider
            from PyQt6.QtCore import QFileInfo
            
            if not exe_path or not os.path.exists(exe_path):
                return None
            
            provider = QFileIconProvider()
            file_info = QFileInfo(exe_path)
            icon = provider.icon(file_info)
            
            if not icon.isNull():
                pixmap = icon.pixmap(32, 32)
                if not pixmap.isNull():
                    return pixmap
        except Exception as e:
            print(f"Ошибка извлечения иконки из {exe_path}: {e}")
        
        return None
    
    def update_results(self):
        """Обновление списка результатов на основе поискового запроса"""
        search_text = self.search_input.text().lower().strip()
        
        self.results_list.clear()
        self.filtered_indices = []

        temp_results = []  # (app_name, index, app_data)

        if not search_text:
            # Отображение всех приложений
            for i, app in enumerate(self.apps):
                temp_results.append((app["name"], i, app))
        else:
            # Фильтрация
            for i, app in enumerate(self.apps):
                app_name = app['name']
                if search_text in app_name.lower():
                    temp_results.append((app_name, i, app))

        # Сортировка по алфавиту
        temp_results.sort(key=lambda x: x[0].lower())

        # Добавление в QListWidget после сортировки с иконками
        for name, original_index, app_data in temp_results:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, original_index)
            
            # ИЗВЛЕЧЕНИЕ ИКОНОК ИЗ EXE В РЕАЛЬНОМ ВРЕМЕНИ (как в program_scanner)
            icon_loaded = False
            
            # Используем поле 'path' для извлечения иконки из exe
            if 'path' in app_data and app_data['path']:
                exe_path = app_data['path']
                
                # Очистка пути от аргументов и кавычек
                if exe_path.startswith('"'):
                    # Путь в кавычках: "C:\Program Files\App.exe" -arg
                    parts = exe_path.split('"')
                    if len(parts) >= 2:
                        exe_path = parts[1]
                elif ' -' in exe_path or ' /' in exe_path:
                    # Путь с аргументами: C:\App.exe -arg
                    # Находим начало аргументов
                    for sep in [' -', ' /']:
                        if sep in exe_path:
                            exe_path = exe_path.split(sep)[0].strip()
                            break
                
                # Проверка на валидный exe-файл
                if exe_path and os.path.exists(exe_path) and exe_path.lower().endswith('.exe'):
                    icon_pixmap = self._extract_icon_from_exe(exe_path)
                    
                    if icon_pixmap and not icon_pixmap.isNull():
                        scaled_icon = icon_pixmap.scaled(
                            32, 32,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        item.setIcon(QIcon(scaled_icon))
                        icon_loaded = True
            
            # Если иконка отсутствует, используем заглушку
            if not icon_loaded:
                item.setText(f"🎮  {name}")
            
            self.results_list.addItem(item)
            self.filtered_indices.append(original_index)

        # Выбор первого результата
        if self.results_list.count() > 0:
            self.current_selection = 0
            self.results_list.setCurrentRow(0)

        # Если ничего не найдено
        if self.results_list.count() == 0:
            item = QListWidgetItem("❌  Приложения не найдены")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results_list.addItem(item)
    
    def update_mode_indicator(self):
        """Обновление индикатора режима — УНИФИЦИРОВАННЫЕ ЦВЕТА"""
        if self.is_typing_mode:
            self.mode_label.setText("🔤 РЕЖИМ ВВОДА")
            self.mode_label.setStyleSheet(f"""
                color: white;
                font-size: {self.scaling.scale_font(11)}px;
                font-weight: 600;
                padding: {self.scaling.scale(5)}px {self.scaling.scale(10)}px;
            """)
        else:
            self.mode_label.setText("🎯 РЕЖИМ НАВИГАЦИИ")
            self.mode_label.setStyleSheet(f"""
                color: rgba(255, 255, 255, 0.6);
                font-size: {self.scaling.scale_font(11)}px;
                font-weight: 600;
                padding: {self.scaling.scale(5)}px {self.scaling.scale(10)}px;
            """)
    
    def switch_mode(self):
        """Переключение между режимом ввода и навигации"""
        self.is_typing_mode = not self.is_typing_mode
        self.update_mode_indicator()
        
        if self.is_typing_mode:
            self.search_input.setFocus()
        else:
            self.results_list.setFocus()
    
    def navigate_up(self):
        """Навигация вверх по результатам"""
        if self.results_list.count() > 0:
            current = self.results_list.currentRow()
            prev_row = max(current - 1, 0)
            self.results_list.setCurrentRow(prev_row)
            # Автоматическое переключение в режим навигации
            if self.is_typing_mode:
                self.is_typing_mode = False
                self.update_mode_indicator()
    
    def navigate_down(self):
        """Навигация вниз по результатам"""
        if self.results_list.count() > 0:
            current = self.results_list.currentRow()
            next_row = min(current + 1, self.results_list.count() - 1)
            self.results_list.setCurrentRow(next_row)
            # Автоматическое переключение в режим навигации
            if self.is_typing_mode:
                self.is_typing_mode = False
                self.update_mode_indicator()
    
    def launch_selected(self):
        """Запуск выбранного приложения"""
        if self.results_list.count() > 0 and self.filtered_indices:
            current_row = self.results_list.currentRow()
            if 0 <= current_row < len(self.filtered_indices):
                app_index = self.filtered_indices[current_row]
                self.app_selected.emit(app_index)
                self.close_search()
    
    def on_item_activated(self, item):
        """Обработка двойного клика или нажатия Enter на элементе"""
        if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
            app_index = item.data(Qt.ItemDataRole.UserRole)
            if app_index is not None:
                self.app_selected.emit(app_index)
                self.close_search()
    
    def handle_joypad_input(self, key_code):
        """Обработка ввода с геймпада (вызывается из родительского объекта)"""
        if key_code == Qt.Key.Key_Escape:
            self.close_search()
        elif key_code == Qt.Key.Key_Up:
            self.navigate_up()
        elif key_code == Qt.Key.Key_Down:
            self.navigate_down()
        elif key_code == Qt.Key.Key_Return or key_code == Qt.Key.Key_Enter:
            self.launch_selected()
        elif key_code == Qt.Key.Key_E:  # Кнопка X для смены режима
            self.switch_mode()
        elif key_code == Qt.Key.Key_Backspace:
            # Клавиша Backspace в режиме навигации возвращает в режим ввода
            if not self.is_typing_mode:
                self.is_typing_mode = True
                self.search_input.setFocus()
                self.update_mode_indicator()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Обработка ввода с клавиатуры"""
        key = event.key()
        
        # Esc всегда закрывает поиск
        if key == Qt.Key.Key_Escape:
            self.close_search()
            return
        
        # Tab переключает режим
        if key == Qt.Key.Key_Tab:
            self.switch_mode()
            event.accept()
            return
        
        # Enter запускает выбранное приложение
        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self.launch_selected()
            return
        
        # Навигация по результатам (всегда активна)
        if key == Qt.Key.Key_Down:
            self.navigate_down()
            event.accept()
            return
        
        if key == Qt.Key.Key_Up:
            self.navigate_up()
            event.accept()
            return
        
        # Backspace в режиме навигации возвращает в режим ввода
        if key == Qt.Key.Key_Backspace and not self.is_typing_mode:
            self.is_typing_mode = True
            self.search_input.setFocus()
            self.update_mode_indicator()
            # Позволяем Backspace обрабатываться стандартным образом
        
        # Любой другой символ в режиме навигации переключает обратно в режим ввода
        if not self.is_typing_mode and event.text().isprintable():
            self.is_typing_mode = True
            self.search_input.setFocus()
            self.update_mode_indicator()
        
        super().keyPressEvent(event)

