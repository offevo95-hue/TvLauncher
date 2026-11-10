"""
dialogs.py — Классы диалогов для TV Launcher
=============================================
Содержит все диалоги, вынесенные из tvlauncher.py:
  - ApiKeyDialog       : ввод API-ключа SteamGridDB
  - SystemMenuDialog   : быстрое меню перезагрузки/выключения/закрытия
  - AddAppDialog       : добавление нового приложения в лаунчер
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog,
    QWidget, QComboBox
)
from PyQt6.QtCore import Qt



class ApiKeyDialog(QDialog):
    def __init__(self, current_key="", parent=None, scaling=None):
        super().__init__(parent)
        s = scaling
        self.setWindowTitle("API-ключ SteamGridDB")
        self.setModal(True)
        self.setFixedSize(s.scale(600), s.scale(300))
        self.setStyleSheet(f"""
            QDialog {{ background-color: #1a1a1a; }}
            QLabel {{ color: white; font-size: {s.scale_font(14)}px; }}
            QLineEdit {{ 
                background-color: #2a2a2a; 
                color: white; 
                border: 2px solid #444; 
                padding: {s.scale(10)}px; 
                border-radius: {s.scale(8)}px; 
                font-size: {s.scale_font(14)}px; 
            }}
            QPushButton {{ 
                background-color: #2a2a2a; 
                color: white; 
                border: 2px solid #444; 
                padding: {s.scale(12)}px {s.scale(30)}px; 
                border-radius: {s.scale(8)}px; 
                font-size: {s.scale_font(14)}px; 
                font-weight: bold; 
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(s.scale(20))
        layout.setContentsMargins(s.scale(30), s.scale(30), s.scale(30), s.scale(30))
        
        # Заголовок
        title = QLabel("🔑 API-ключ SteamGridDB")
        title.setStyleSheet(f"font-size: {s.scale_font(18)}px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Информационный текст
        info = QLabel(
            "Для автоматической загрузки изображений 16:9:\n\n"
            "1. Перейдите на сайт steamgriddb.com\n"
            "2. Создайте бесплатный аккаунт\n"
            "3. Перейдите в Preferences (Настройки) → API\n"
            "4. Сгенерируйте API-ключ и вставьте его сюда"
        )
        info.setStyleSheet(f"color: #aaa; font-size: {s.scale_font(12)}px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Поле ввода API-ключа
        key_label = QLabel("API-ключ:")
        layout.addWidget(key_label)
        
        self.key_input = QLineEdit()
        self.key_input.setText(current_key)
        self.key_input.setPlaceholderText("Вставьте свой API-ключ сюда . . .")
        layout.addWidget(self.key_input)
        
        layout.addStretch()
        
        # Кнопки
        button_layout = QHBoxLayout()
        button_layout.setSpacing(s.scale(15))
        
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.save_btn.clicked.connect(self.accept)
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self._s = s
        self.confirm_buttons = [self.save_btn, self.cancel_btn]
        self.confirm_index = [0]
        self.update_confirm_focus()
    
    def update_confirm_focus(self):
        s = self._s
        for i, btn in enumerate(self.confirm_buttons):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2a2a2a;
                    color: white;
                    border: 2px solid #444;
                    padding: {s.scale(12)}px {s.scale(30)}px;
                    border-radius: {s.scale(8)}px;
                    font-size: {s.scale_font(14)}px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #3a3a3a; }}
            """)
    
    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.confirm_index[0] = (self.confirm_index[0] - 1) % 2
            self.update_confirm_focus()
        elif key == Qt.Key.Key_Right:
            self.confirm_index[0] = (self.confirm_index[0] + 1) % 2
            self.update_confirm_focus()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self.confirm_buttons[self.confirm_index[0]].click()
        elif key == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
    
    def get_api_key(self):
        return self.key_input.text().strip()




class SystemMenuDialog(QDialog):
    def __init__(self, parent=None, scaling=None):
        super().__init__(parent)
        s = scaling
        self._s = s
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        parent_rect = parent.geometry()
        dialog_width = s.scale(250)
        dialog_height = s.scale(100)
        self.setGeometry(
            parent_rect.width() - dialog_width - s.scale(40),
            parent_rect.height() - dialog_height - s.scale(40),
            dialog_width,
            dialog_height
        )
        self.current_index = 0
        self.buttons = []
        main_widget = QWidget()
        main_widget.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(30, 30, 30, 220);
                border-radius: {s.scale(50)}px;
            }}
        """)
        layout = QHBoxLayout(main_widget)
        layout.setSpacing(s.scale(20))
        layout.setContentsMargins(s.scale(20), s.scale(20), s.scale(20), s.scale(20))
        btn_size = s.scale(60)
        self.restart_btn = QPushButton("↻")
        self.restart_btn.setFixedSize(btn_size, btn_size)
        self.restart_btn.setToolTip("Перезагрузка")
        self.buttons.append(("restart", self.restart_btn))
        layout.addWidget(self.restart_btn)
        self.shutdown_btn = QPushButton("⏻")
        self.shutdown_btn.setFixedSize(btn_size, btn_size)
        self.shutdown_btn.setToolTip("Выключение")
        self.buttons.append(("shutdown", self.shutdown_btn))
        layout.addWidget(self.shutdown_btn)
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(btn_size, btn_size)
        self.close_btn.setToolTip("Закрыть")
        self.buttons.append(("close", self.close_btn))
        layout.addWidget(self.close_btn)
        for action, btn in self.buttons:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2a2a2a;
                    color: white;
                    border: {s.scale(3)}px solid #444;
                    border-radius: {s.scale(30)}px;
                    font-size: {s.scale_font(24)}px;
                }}
                QPushButton:hover {{ background-color: #3a3a3a; }}
            """)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        dialog_layout = QVBoxLayout()
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(main_widget)
        self.setLayout(dialog_layout)
        self.update_focus()
   
    def update_focus(self):
        s = self._s
        for i, (action, btn) in enumerate(self.buttons):
            if i == self.current_index:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #ffffff;
                        color: #1a1a1a;
                        border: {s.scale(4)}px solid white;
                        border-radius: {s.scale(30)}px;
                        font-size: {s.scale_font(24)}px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{ background-color: #3a3a3a; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #2a2a2a;
                        color: white;
                        border: {s.scale(3)}px solid #444;
                        border-radius: {s.scale(30)}px;
                        font-size: {s.scale_font(24)}px;
                    }}
                    QPushButton:hover {{ background-color: #3a3a3a; }}
                """)
   
    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_Right:
            self.current_index = (self.current_index + 1) % len(self.buttons)
            self.update_focus()
        elif key == Qt.Key.Key_Left:
            self.current_index = (self.current_index - 1) % len(self.buttons)
            self.update_focus()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            action = self.buttons[self.current_index][0]
            if action == "close":
                self.reject()
            else:
                self.selected_action = action
                self.accept()
        elif key == Qt.Key.Key_Escape or key == Qt.Key.Key_M:
            self.reject()
        else:
            super().keyPressEvent(event)
   
    def get_selected_action(self):
        return getattr(self, 'selected_action', 'close')




class AddAppDialog(QDialog):
    def __init__(self, parent=None, scaling=None):
        super().__init__(parent)
        s = scaling
        self._s = s
        self.setWindowTitle("Добавить новое приложение")
        self.setModal(True)
        self.setFixedSize(s.scale(600), s.scale(520))
        self.setStyleSheet(f"""
            QDialog {{ background-color: #1a1a1a; }}
            QLabel {{ color: white; font-size: {s.scale_font(16)}px; }}
            QLineEdit {{ background-color: #2a2a2a; color: white; border: 2px solid #444; padding: {s.scale(10)}px; border-radius: {s.scale(8)}px; font-size: {s.scale_font(14)}px; }}
            QPushButton {{ background-color: #2a2a2a; color: white; border: 2px solid #444; padding: {s.scale(12)}px {s.scale(30)}px; border-radius: {s.scale(8)}px; font-size: {s.scale_font(14)}px; font-weight: bold; }}
        """)
        layout = QVBoxLayout()
        layout.setSpacing(s.scale(20))
        layout.setContentsMargins(s.scale(30), s.scale(30), s.scale(30), s.scale(30))
        
        name_label = QLabel("Название приложения:")
        name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(name_label)
        self.name_input = QLineEdit()
        layout.addWidget(self.name_input)
        
        exe_label = QLabel("Путь к исполняемому файлу:")
        exe_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(exe_label)
        exe_container = QHBoxLayout()
        exe_container.setSpacing(s.scale(10))
        self.exe_input = QLineEdit()
        exe_container.addWidget(self.exe_input, 3)
        self.exe_button = QPushButton("Обзор")
        self.exe_button.clicked.connect(self.browse_exe)
        exe_container.addWidget(self.exe_button, 1)
        layout.addLayout(exe_container)
        
        icon_label = QLabel("Изображение иконки (рекомендуется 16:9):")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(icon_label)
        icon_container = QHBoxLayout()
        icon_container.setSpacing(s.scale(10))
        self.icon_input = QLineEdit()
        icon_container.addWidget(self.icon_input, 3)
        self.icon_button = QPushButton("Обзор")
        self.icon_button.clicked.connect(self.browse_icon)
        icon_container.addWidget(self.icon_button, 1)
        layout.addLayout(icon_container)
        
        category_label = QLabel("Категория:")
        category_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(category_label)
        
        self.category_combo = QComboBox()
        if hasattr(parent, 'category_manager'):
            self.category_combo.addItems(parent.category_manager.get_category_names())
        else:
            self.category_combo.addItems(['Игры', 'Медиа', 'Программы', 'Другое'])
        
        self.category_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #2a2a2a;
                color: white;
                border: 2px solid #444;
                padding: {s.scale(10)}px;
                border-radius: {s.scale(8)}px;
                font-size: {s.scale_font(14)}px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox::down-arrow {{ image: none; border: none; }}
            QComboBox QAbstractItemView {{
                background-color: #2a2a2a;
                color: white;
                selection-background-color: #3a3a3a;
            }}
        """)
        
        index = self.category_combo.findText('Другое')
        if index < 0:
            index = self.category_combo.findText('Other')
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
        
        layout.addWidget(self.category_combo)
        layout.addSpacing(s.scale(20))
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(s.scale(15))
        self.ok_button = QPushButton("Добавить")
        self.ok_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        self.confirm_buttons = [self.ok_button, self.cancel_button]
        self.confirm_index = [0]
        self.update_confirm_focus()
   
    def update_confirm_focus(self):
        s = self._s
        for i, btn in enumerate(self.confirm_buttons):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2a2a2a;
                    color: white;
                    border: 2px solid #444;
                    padding: {s.scale(12)}px {s.scale(30)}px;
                    border-radius: {s.scale(8)}px;
                    font-size: {s.scale_font(14)}px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #3a3a3a; }}
            """)
   
    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_Left:
            self.confirm_index[0] = (self.confirm_index[0] - 1) % 2
            self.update_confirm_focus()
        elif key == Qt.Key.Key_Right:
            self.confirm_index[0] = (self.confirm_index[0] + 1) % 2
            self.update_confirm_focus()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self.confirm_buttons[self.confirm_index[0]].click()
        elif key == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
   
    def browse_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите исполняемый файл", "", "Исполняемые файлы (*.exe);;Все файлы (*.*)"
        )
        if file_path:
            self.exe_input.setText(file_path)
            if not self.name_input.text():
                self.name_input.setText(Path(file_path).stem)
   
    def browse_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение иконки", "", "Изображения (*.png *.jpg *.jpeg *.bmp);;Все файлы (*.*)"
        )
        if file_path:
            self.icon_input.setText(file_path)
   
    def get_app_data(self):
        return {
            'name': self.name_input.text(),
            'path': self.exe_input.text(),
            'icon': self.icon_input.text(),
            'category': self.category_combo.currentText()
        }

