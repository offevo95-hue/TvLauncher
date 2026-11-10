"""
Модуль диалога редактора категорий — Улучшенная версия с выборщиком эмодзи
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QColorDialog, QMessageBox, QWidget, QScrollArea,
    QGridLayout, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty
from PyQt6.QtGui import QColor, QPixmap, QIcon, QPainter, QBrush, QPen
from pathlib import Path


class AnimatedToggle(QCheckBox):
    """Анимированный квадратный переключатель (чекбокс) с галочкой"""
    
    def __init__(self, scaling, parent=None):
        super().__init__(parent)
        self.scaling = scaling
        self._check_progress = 0.0
        self.setFixedSize(self.scaling.scale(32), self.scaling.scale(32))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Анимация
        self.animation = QPropertyAnimation(self, b"check_progress", self)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.setDuration(200)
        
        self.stateChanged.connect(self._animate_check)
    
    def _animate_check(self, state):
        if state == Qt.CheckState.Checked.value:
            self.animation.setEndValue(1.0)
        else:
            self.animation.setEndValue(0.0)
        self.animation.start()
    
    @pyqtProperty(float)
    def check_progress(self):
        return self._check_progress
    
    @check_progress.setter
    def check_progress(self, value):
        self._check_progress = value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Фоновое поле
        if self.isChecked() or self._check_progress > 0:
            # Интерполяция между серым и зеленым цветом
            gray = QColor("#2a2a2a")
            green = QColor("#4CAF50")
            if self.underMouse():
                green = QColor("#5BC157")
            
            r = int(gray.red() + (green.red() - gray.red()) * self._check_progress)
            g = int(gray.green() + (green.green() - gray.green()) * self._check_progress)
            b = int(gray.blue() + (green.blue() - gray.blue()) * self._check_progress)
            bg_color = QColor(r, g, b)
        else:
            bg_color = QColor("#2a2a2a")
            if self.underMouse():
                bg_color = QColor("#333333")
        
        # Граница
        border_color = QColor("#444444")
        if self.underMouse():
            border_color = QColor("#666666")
        if self.isChecked():
            border_color = QColor("#4CAF50")
            if self.underMouse():
                border_color = QColor("#5BC157")
        
        painter.setPen(QPen(border_color, 2))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(2, 2, self.width() - 4, self.height() - 4,
                               self.scaling.scale(6), self.scaling.scale(6))
        
        # Отрисовка галочки с учетом анимации
        if self._check_progress > 0:
            painter.setPen(QPen(QColor("white"), self.scaling.scale(3), 
                              Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, 
                              Qt.PenJoinStyle.RoundJoin))
            
            # Масштабирование галочки в зависимости от прогресса
            scale = self._check_progress
            
            # Координаты галочки (относительные)
            x_offset = self.width() * 0.25
            y_offset = self.height() * 0.5
            
            # Короткая линия (от нижней левой точки к середине)
            x1 = int(x_offset)
            y1 = int(y_offset)
            x2 = int(x_offset + (self.width() * 0.15 * scale))
            y2 = int(y_offset + (self.height() * 0.15 * scale))
            painter.drawLine(x1, y1, x2, y2)
            
            # Длинная линия (от середины к верхней правой точке)
            if scale > 0.5:
                progress = (scale - 0.5) * 2
                x3 = int(x_offset + (self.width() * 0.45 * progress))
                y3 = int(y_offset - (self.height() * 0.25 * progress))
                painter.drawLine(x2, y2, x3, y3)
    
    def hitButton(self, pos):
        return self.contentsRect().contains(pos)



class EmojiPickerDialog(QDialog):
    """Диалоговое окно для выбора эмодзи"""
    
    # Распространенные эмодзи для категорий
    CATEGORY_EMOJIS = [
        "🎮", "🎯", "🎨", "🎬", "🎵", "📚", "💼", "🔧",
        "⚙️", "🌐", "📱", "💻", "🖥️", "⌨️", "🖱️", "🎧",
        "📷", "🎥", "📝", "📊", "📈", "📉", "🗂️", "📦",
        "🔍", "🔐", "🔒", "🔓", "🔑", "🛠️", "⚡", "🔥",
        "💡", "🌟", "⭐", "✨", "🎁", "🏆", "🎪", "🎭",
        "🎲", "🃏", "🎰", "🧩", "🎪", "🎨", "🖌️", "✏️",
        "📐", "📏", "📌", "📍", "🔖", "🏷️", "💾", "💿",
    ]
    
    def __init__(self, current_emoji, scaling, parent=None):
        super().__init__(parent)
        self.selected_emoji = current_emoji
        self.scaling = scaling
        
        self.setWindowTitle("Выбрать иконку")
        self.setModal(True)
        self.setFixedSize(self.scaling.scale(600), self.scaling.scale(500))
        
        self.setStyleSheet("QDialog { background-color: #1a1a1a; }")
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(
            self.scaling.scale(20),
            self.scaling.scale(20),
            self.scaling.scale(20),
            self.scaling.scale(20)
        )
        layout.setSpacing(self.scaling.scale(15))
        
        # Заголовок
        title = QLabel("Выберите иконку для категории")
        title.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(18)}px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(title)
        
        # Сетка эмодзи
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 2px solid #444;
                border-radius: {self.scaling.scale(8)}px;
                background: #2a2a2a;
            }}
            QScrollBar:vertical {{
                background-color: #2a2a2a;
                width: {self.scaling.scale(10)}px;
                border-radius: {self.scaling.scale(5)}px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #444;
                border-radius: {self.scaling.scale(4)}px;
            }}
        """)
        
        emoji_container = QWidget()
        emoji_container.setStyleSheet("background: #2a2a2a;")
        emoji_grid = QGridLayout(emoji_container)
        emoji_grid.setSpacing(self.scaling.scale(8))
        emoji_grid.setContentsMargins(
            self.scaling.scale(10),
            self.scaling.scale(10),
            self.scaling.scale(10),
            self.scaling.scale(10)
        )
        
        # Создание кнопок с эмодзи
        cols = 8
        for i, emoji in enumerate(self.CATEGORY_EMOJIS):
            btn = QPushButton(emoji)
            btn.setFixedSize(self.scaling.scale(50), self.scaling.scale(50))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #3a3a3a;
                    border: 2px solid #555;
                    border-radius: {self.scaling.scale(8)}px;
                    font-size: {self.scaling.scale_font(24)}px;
                }}
                QPushButton:hover {{
                    background-color: #4a4a4a;
                    border-color: white;
                }}
            """)
            btn.clicked.connect(lambda checked, e=emoji: self._select_emoji(e))
            emoji_grid.addWidget(btn, i // cols, i % cols)
        
        scroll.setWidget(emoji_container)
        layout.addWidget(scroll)
        
        # Кнопки действий
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(self.scaling.scale(10))
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedHeight(self.scaling.scale(40))
        
        ok_btn = QPushButton("Выбрать")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setFixedHeight(self.scaling.scale(40))
        
        for btn in [cancel_btn, ok_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2a2a2a;
                    color: white;
                    border: 2px solid #444;
                    border-radius: {self.scaling.scale(8)}px;
                    font-size: {self.scaling.scale_font(14)}px;
                    font-weight: bold;
                    padding: {self.scaling.scale(8)}px {self.scaling.scale(20)}px;
                }}
                QPushButton:hover {{
                    background-color: #3a3a3a;
                }}
            """)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def _select_emoji(self, emoji):
        self.selected_emoji = emoji
        self.accept()


class CategoryEditorDialog(QDialog):
    """Диалоговое окно для изменения, добавления и удаления категорий"""
    
    def __init__(self, category_manager, scaling, parent=None):
        super().__init__(parent)
        self.category_manager = category_manager
        self.scaling = scaling
        self.selected_index = -1
        self.is_new_category = False
        self.current_emoji = "📦"
        
        self.setWindowTitle("Менеджер категорий")
        self.setModal(True)
        self.setFixedSize(self.scaling.scale(900), self.scaling.scale(950))
        
        self.setStyleSheet("QDialog { background-color: #0f0f0f; }")
        
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Верхняя панель (Header)
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Содержимое
        scroll = self._create_scroll_area()
        content = self._create_content()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Нижняя панель (Footer)
        footer = self._create_footer()
        main_layout.addWidget(footer)
        
        self.setLayout(main_layout)
        self._refresh_list()
    
    def _create_header(self):
        """Создание шапки с иконкой"""
        header = QWidget()
        header.setFixedHeight(self.scaling.scale(125))
        header.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-bottom: 2px solid #444;
            }
        """)
        
        layout = QVBoxLayout(header)
        
        layout.setContentsMargins(
            self.scaling.scale(40), self.scaling.scale(25),
            self.scaling.scale(40), self.scaling.scale(25)
        )
        
        # Контейнер заголовка
        title_container = QWidget()
        title_container.setStyleSheet("background: transparent; border: none;")
        title_layout = QHBoxLayout(title_container)
        title_layout.setSpacing(self.scaling.scale(15))
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # Иконка
        icon_label = QLabel()
        icon_path = Path("assets/icons/folder.png")
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            scaled_pixmap = pixmap.scaled(
                self.scaling.scale(40), self.scaling.scale(40),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            icon_label.setPixmap(scaled_pixmap)
        else:
            icon_label.setText("📁")
            icon_label.setStyleSheet(f"""
                QLabel {{
                    color: white;
                    font-size: {self.scaling.scale_font(36)}px;
                    background: transparent;
                    border: none;
                }}
            """)
        title_layout.addWidget(icon_label)
        
        # Заголовок
        title = QLabel("Менеджер категорий")
        title.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(36)}px;
                font-weight: 700;
                background: transparent;
                border: none;
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        
        layout.addWidget(title_container)
        
        # Подзаголовок
        subtitle = QLabel("Добавление, изменение или удаление категорий приложений")
        subtitle.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.5);
                font-size: {self.scaling.scale_font(15)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(subtitle)
        
        return header
    
    def _create_scroll_area(self):
        """Создание области прокрутки"""
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
        """)
        
        return scroll
    
    def _create_content(self):
        """Создание содержимого с секциями"""
        content = QWidget()
        content.setStyleSheet("background: #1a1a1a")
        
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            self.scaling.scale(40), self.scaling.scale(15),
            self.scaling.scale(40), self.scaling.scale(15)
        )
        layout.setSpacing(self.scaling.scale(25))
        
        # Секция: Текущие категории
        section_header = self._create_section_header(
            "Текущие категории",
            "Выберите категорию для редактирования"
        )
        layout.addWidget(section_header)
        
        # Список категорий
        self.category_list = QListWidget()
        self.category_list.setFixedHeight(self.scaling.scale(250))
        self.category_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #2a2a2a;
                color: white;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(15)}px;
                padding: {self.scaling.scale(15)}px;
                font-size: {self.scaling.scale_font(15)}px;
            }}
            QListWidget::item {{
                padding: {self.scaling.scale(15)}px;
                border-radius: {self.scaling.scale(8)}px;
                margin: {self.scaling.scale(3)}px 0px;
            }}
            QListWidget::item:selected {{
                background-color: #3a3a3a;
                border: 3px solid white;
            }}
            QListWidget::item:hover {{
                background-color: #353535;
            }}
        """)
        self.category_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.category_list.itemClicked.connect(self._on_category_selected)
        layout.addWidget(self.category_list)
        
        # Секция: Редактирование категории
        section_header2 = self._create_section_header(
            "Редактировать категорию",
            "Изменение названия, иконки и цвета"
        )
        layout.addWidget(section_header2)
        
        # Редактор
        editor = self._create_editor()
        layout.addWidget(editor)
        
        layout.addStretch()
        
        return content
    
    def _create_section_header(self, title, description):
        """Создание заголовка секции"""
        header = QWidget()
        header.setFixedHeight(self.scaling.scale(60))
        header.setStyleSheet("background: transparent;")
        
        layout = QVBoxLayout(header)
        layout.setSpacing(self.scaling.scale(5))
        layout.setContentsMargins(0, 0, 0, 0)
        
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
    
    def _create_editor(self):
        """Создание полей редактора"""
        editor = QWidget()
        editor.setFixedHeight(self.scaling.scale(260))
        editor.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: {self.scaling.scale(12)}px;
            }}
        """)
        
        layout = QVBoxLayout(editor)
        layout.setSpacing(self.scaling.scale(5))
        layout.setContentsMargins(
            self.scaling.scale(25), self.scaling.scale(10),
            self.scaling.scale(25), self.scaling.scale(10)
        )
        
        # Строка имени
        name_row = self._create_name_row()
        layout.addWidget(name_row)
        
        # Строка иконки (с выборщиком эмодзи)
        icon_row = self._create_icon_row()
        layout.addWidget(icon_row)
        
        # Строка цвета
        color_row = self._create_color_row()
        layout.addWidget(color_row)
        
        # Переключатель категории по умолчанию
        default_row = self._create_default_row()
        layout.addWidget(default_row)
        
        return editor
    
    def _create_name_row(self):
        """Строка ввода названия"""
        row = QWidget()
        row.setFixedHeight(self.scaling.scale(60))
        row.setStyleSheet("background: transparent; border: none;")
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaling.scale(15))
        
        # Метка
        label_container = QWidget()
        label_container.setStyleSheet("background: transparent; border: none;")
        label_layout = QVBoxLayout(label_container)
        label_layout.setSpacing(self.scaling.scale(3))
        label_layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel("Название")
        label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(15)}px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        label_layout.addWidget(label)
        
        hint = QLabel("Отображаемое имя категории")
        hint.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.35);
                font-size: {self.scaling.scale_font(11)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        label_layout.addWidget(hint)
        label_layout.addStretch()
        
        layout.addWidget(label_container, 1)
        
        # Поле ввода
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("например, Игры")
        self.name_input.setFixedHeight(self.scaling.scale(45))
        self.name_input.setFixedWidth(self.scaling.scale(300))
        self.name_input.textChanged.connect(self._on_field_changed)
        self.name_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #1a1a1a;
                color: white;
                border: 2px solid #555;
                border-radius: {self.scaling.scale(8)}px;
                padding: {self.scaling.scale(10)}px {self.scaling.scale(15)}px;
                font-size: {self.scaling.scale_font(14)}px;
            }}
            QLineEdit:focus {{
                border-color: white;
            }}
        """)
        
        layout.addWidget(self.name_input)
        
        return row
    
    def _create_icon_row(self):
        """Строка иконки с выборщиком эмодзи"""
        row = QWidget()
        row.setFixedHeight(self.scaling.scale(75))
        row.setStyleSheet("background: transparent; border: none;")
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaling.scale(15))
        
        # Метка
        label_container = QWidget()
        label_container.setStyleSheet("background: transparent; border: none;")
        label_layout = QVBoxLayout(label_container)
        label_layout.setSpacing(self.scaling.scale(3))
        label_layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel("Иконка")
        label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(15)}px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        label_layout.addWidget(label)
        
        hint = QLabel("Иконка категории")
        hint.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.35);
                font-size: {self.scaling.scale_font(11)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        label_layout.addWidget(hint)
        label_layout.addStretch()
        
        layout.addWidget(label_container, 1)
        
        # Предпросмотр текущей иконки
        self.icon_preview = QLabel(self.current_emoji)
        self.icon_preview.setFixedSize(self.scaling.scale(60), self.scaling.scale(45))
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_preview.setStyleSheet(f"""
            QLabel {{
                background-color: #1a1a1a;
                border: 2px solid #555;
                border-radius: {self.scaling.scale(8)}px;
                font-size: {self.scaling.scale_font(28)}px;
            }}
        """)
        layout.addWidget(self.icon_preview)
        
        # Кнопка открытия выборщика
        self.icon_picker_btn = QPushButton("Выбрать иконку")
        self.icon_picker_btn.setFixedSize(self.scaling.scale(140), self.scaling.scale(45))
        self.icon_picker_btn.clicked.connect(self._open_emoji_picker)
        self.icon_picker_btn.setStyleSheet(f"""
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
        layout.addWidget(self.icon_picker_btn)
        
        return row
    
    def _create_color_row(self):
        """Строка выбора цвета"""
        row = QWidget()
        row.setFixedHeight(self.scaling.scale(75))
        row.setStyleSheet("background: transparent; border: none;")
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaling.scale(15))
        
        # Метка
        label_container = QWidget()
        label_container.setStyleSheet("background: transparent; border: none;")
        label_layout = QVBoxLayout(label_container)
        label_layout.setSpacing(self.scaling.scale(3))
        label_layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel("Цвет")
        label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(15)}px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        label_layout.addWidget(label)
        
        hint = QLabel("Акцентный цвет категории")
        hint.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.35);
                font-size: {self.scaling.scale_font(11)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        label_layout.addWidget(hint)
        label_layout.addStretch()
        
        layout.addWidget(label_container, 1)
        
        # Поле ввода цвета
        self.color_input = QLineEdit()
        self.color_input.setPlaceholderText("#4CAF50")
        self.color_input.setFixedHeight(self.scaling.scale(45))
        self.color_input.setFixedWidth(self.scaling.scale(150))
        self.color_input.textChanged.connect(self._on_field_changed)
        self.color_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #1a1a1a;
                color: white;
                border: 2px solid #555;
                border-radius: {self.scaling.scale(8)}px;
                padding: {self.scaling.scale(10)}px {self.scaling.scale(15)}px;
                font-size: {self.scaling.scale_font(14)}px;
            }}
            QLineEdit:focus {{
                border-color: white;
            }}
        """)
        layout.addWidget(self.color_input)
        
        # Кнопка палитры
        self.color_picker_btn = QPushButton("Выбрать цвет")
        self.color_picker_btn.setFixedSize(self.scaling.scale(120), self.scaling.scale(45))
        self.color_picker_btn.clicked.connect(self._pick_color)
        self.color_picker_btn.setStyleSheet(f"""
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
        layout.addWidget(self.color_picker_btn)
        
        return row
    
    def _create_default_row(self):
        """Строка для отметки категории по умолчанию"""
        row = QWidget()
        row.setFixedHeight(self.scaling.scale(60))
        row.setStyleSheet("background: transparent; border: none;")
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaling.scale(15))
        
        # Метка
        label_container = QWidget()
        label_container.setStyleSheet("background: transparent; border: none;")
        label_layout = QVBoxLayout(label_container)
        label_layout.setSpacing(self.scaling.scale(3))
        label_layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel("Категория по умолчанию")
        label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.scaling.scale_font(15)}px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        label_layout.addWidget(label)
        
        hint = QLabel("Показывать эту категорию при запуске лаунчера")
        hint.setStyleSheet(f"""
            QLabel {{
                color: rgba(255, 255, 255, 0.35);
                font-size: {self.scaling.scale_font(11)}px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        label_layout.addWidget(hint)
        label_layout.addStretch()
        
        layout.addWidget(label_container, 1)
        
        # Анимированный переключатель
        self.default_checkbox = AnimatedToggle(self.scaling)
        layout.addWidget(self.default_checkbox)
        
        return row

    
    def _create_footer(self):
        """Создание нижней панели с кнопками"""
        footer = QWidget()
        footer.setFixedHeight(self.scaling.scale(90))
        footer.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border-top: 2px solid #444;
            }
        """)
        
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(
            self.scaling.scale(40), self.scaling.scale(25),
            self.scaling.scale(40), self.scaling.scale(25)
        )
        layout.setSpacing(self.scaling.scale(20))
        
        # Подсказка по управлению
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
        
        # Кнопки действий
        button_layout = QHBoxLayout()
        button_layout.setSpacing(self.scaling.scale(12))
        
        self.add_btn = QPushButton("+ Добавить")
        self.add_btn.clicked.connect(self._add_category)
        self.add_btn.setFixedSize(self.scaling.scale(120), self.scaling.scale(50))
        
        self.save_btn = QPushButton("💾 Сохранить")
        self.save_btn.clicked.connect(self._save_category)
        self.save_btn.setEnabled(False)
        self.save_btn.setFixedSize(self.scaling.scale(130), self.scaling.scale(50))
        
        self.delete_btn = QPushButton("🗑️ Удалить")
        self.delete_btn.clicked.connect(self._delete_category)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setFixedSize(self.scaling.scale(120), self.scaling.scale(50))
        
        for btn in [self.add_btn, self.save_btn, self.delete_btn]:
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet(f"""
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
                QPushButton:disabled {{
                    background-color: #1a1a1a;
                    color: #666;
                    border-color: #333;
                }}
            """)
        
        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.delete_btn)
        
        layout.addLayout(button_layout)
        
        # Кнопка закрытия
        self.close_btn = QPushButton("Закрыть")
        save_icon_path = Path("assets/icons/backup.png")
        if save_icon_path.exists():
            self.close_btn.setIcon(QIcon(str(save_icon_path)))
            self.close_btn.setIconSize(QSize(self.scaling.scale(24), self.scaling.scale(24)))
        
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setFixedSize(self.scaling.scale(150), self.scaling.scale(55))
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.setStyleSheet(f"""
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
        layout.addWidget(self.close_btn)
        
        return footer
    
    # ===== ФУНКЦИОНАЛЬНЫЕ МЕТОДЫ =====
    
    def _refresh_list(self):
        """Обновление списка категорий"""
        self.category_list.clear()
        
        for i, category in enumerate(self.category_manager.categories):
            # Пропуск категории "All" (Все)
            if category['name'] == 'All':
                continue
            
            # Отображение маркера, если категория по умолчанию
            is_default = category.get('is_default', False)
            display_name = f"{category['icon']} {category['name']}"
            if is_default:
                display_name += " ⭐"
            
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.category_list.addItem(item)
    
    def _on_category_selected(self, item):
        """Срабатывает при выборе категории из списка"""
        index = item.data(Qt.ItemDataRole.UserRole)
        self.selected_index = index
        self.is_new_category = False
        
        category = self.category_manager.categories[index]
        
        self.name_input.setText(category['name'])
        self.current_emoji = category.get('icon', '📦')
        self.icon_preview.setText(self.current_emoji)
        self.color_input.setText(category['color'])
        self.default_checkbox.setChecked(category.get('is_default', False))
        
        self.save_btn.setEnabled(True)
        self.delete_btn.setEnabled(len(self.category_manager.categories) > 2)
    
    def _on_field_changed(self):
        """Срабатывает при изменении полей ввода"""
        has_name = bool(self.name_input.text().strip())
        self.save_btn.setEnabled(has_name)
    
    def _open_emoji_picker(self):
        """Открытие диалогового окна выбора эмодзи"""
        picker = EmojiPickerDialog(self.current_emoji, self.scaling, self)
        if picker.exec() == QDialog.DialogCode.Accepted:
            self.current_emoji = picker.selected_emoji
            self.icon_preview.setText(self.current_emoji)
            self._on_field_changed()
    
    def _pick_color(self):
        """Открытие палитры выбора цвета"""
        current_color = QColor(self.color_input.text() if self.color_input.text() else "#4CAF50")
        
        color_dialog = QColorDialog(current_color, self)
        color_dialog.setWindowTitle("Выбрать цвет")
        color_dialog.setStyleSheet("""
            QColorDialog {
                background-color: #1a1a1a;
            }
            QWidget {
                background-color: #1a1a1a;
                color: white;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: white;
                border: 2px solid #444;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        
        if color_dialog.exec() == QColorDialog.DialogCode.Accepted:
            color = color_dialog.selectedColor()
            if color.isValid():
                self.color_input.setText(color.name())
    
    def _add_category(self):
        """Добавление новой категории"""
        self.category_list.clearSelection()
        
        self.name_input.clear()
        self.current_emoji = "📦"
        self.icon_preview.setText(self.current_emoji)
        self.color_input.setText("#4CAF50")
        self.default_checkbox.setChecked(False)
        
        self.selected_index = -1
        self.is_new_category = True
        
        self.save_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        
        self.name_input.setFocus()
    
    def _save_category(self):
        """Сохранение категории"""
        name = self.name_input.text().strip()
        icon = self.current_emoji
        color = self.color_input.text().strip()
        is_default = self.default_checkbox.isChecked()
        
        # Проверка корректности ввода
        if not name:
            QMessageBox.warning(self, "Неверный ввод", "Название категории не может быть пустым!")
            return
        
        if not color or not color.startswith('#'):
            color = "#4CAF50"
        
        # Проверка на дубликаты
        for i, cat in enumerate(self.category_manager.categories):
            if cat['name'].lower() == name.lower() and i != self.selected_index:
                QMessageBox.warning(self, "Дубликат", f"Категория '{name}' уже существует!")
                return
        
        if is_default:
            for cat in self.category_manager.categories:
                cat['is_default'] = False
        
        new_category = {
            "name": name,
            "icon": icon,
            "color": color,
            "is_default": is_default
        }
        
        if self.selected_index >= 0 and not self.is_new_category:
            # Редактирование существующей категории
            old_name = self.category_manager.categories[self.selected_index]['name']
            self.category_manager.categories[self.selected_index] = new_category
            print(f"Категория обновлена: {old_name} → {name}")

            # Перенос переименования на все приложения, которые использовали старое имя,
            # иначе они останутся привязаны к несуществующей категории.
            if old_name != name:
                self._reassign_apps_category(old_name, name)
        else:
            # Новая категория
            self.category_manager.categories.append(new_category)
            print(f"Категория добавлена: {name}")
        
        self.is_new_category = False
        self.selected_index = -1
        
        self.name_input.clear()
        self.current_emoji = "📦"
        self.icon_preview.setText(self.current_emoji)
        self.color_input.setText("#4CAF50")
        self.default_checkbox.setChecked(False)
        
        self._refresh_list()
        self.save_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

        # Сохранение на диск сразу: без этого изменения остаются
        # только в памяти до закрытия диалога кнопкой "Закрыть".
        # Если закрыть окно иным способом (крестик, Alt+F4, выключение),
        # метод closeEvent() ничего не сохранит, и изменения пропадут.
        launcher = self.parent()
        if hasattr(launcher, 'save_config'):
            try:
                launcher.save_config()
            except Exception as e:
                print(f"⚠️ Не удалось сохранить изменения категории: {e}")
    
    def _reassign_apps_category(self, old_name, new_name):
        """Обновление поля app['category'] для каждого приложения со старым именем.

        Без этого переименование или удаление категории оставляет приложения
        привязанными к имени, которого больше нет, из-за чего они исчезают из фильтров.
        """
        launcher = self.parent()
        apps = getattr(launcher, 'apps', None)
        if not apps:
            return

        changed = False
        for app in apps:
            if app.get('category', 'Other') == old_name:
                app['category'] = new_name
                changed = True

        if changed:
            print(f"Переназначены приложения: '{old_name}' → '{new_name}'")
            # Сохраняем сразу, чтобы данные не расходились при закрытии через Esc/Alt+F4.
            if hasattr(launcher, 'save_config'):
                try:
                    launcher.save_config()
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить переназначение категории приложения: {e}")

    def _delete_category(self):
        """Удаление категории"""
        if self.selected_index < 0:
            return
        
        category = self.category_manager.categories[self.selected_index]
        
        if category['name'] == 'All':
            QMessageBox.warning(self, "Удаление невозможно", "Нельзя удалить категорию 'All' (Все)!")
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Удалить категорию '{category['name']}'?\n\nПриложения из этой категории будут перемещены в 'Other' (Другое).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            deleted_name = category['name']
            self.category_manager.categories.pop(self.selected_index)
            print(f"Категория удалена: {deleted_name}")

            # Перенос приложений из удаленной категории в 'Other'
            self._reassign_apps_category(deleted_name, 'Other')

            self._refresh_list()
            self.selected_index = -1
            self.is_new_category = False
            self.name_input.clear()
            self.current_emoji = "📦"
            self.icon_preview.setText(self.current_emoji)
            self.color_input.clear()
            self.default_checkbox.setChecked(False)
            self.save_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)

