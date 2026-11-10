Import os
import json
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QFont


class CategoryManager:
    """Управление категориями и фильтрацией приложений"""
    
    DEFAULT_CATEGORIES = [
        {"name": "All", "icon": "🎮", "color": "#ffffff"},
        {"name": "Games", "icon": "🎮", "color": "#4CAF50"},
        {"name": "Media", "icon": "🎬", "color": "#2196F3"},
        {"name": "Programs", "icon": "💼", "color": "#FF9800"},
        {"name": "Other", "icon": "📦", "color": "#9E9E9E"}
    ]
    
    def __init__(self, config_file="launcher_apps.json"):
        self.config_file = Path(config_file)
        self.categories = self.DEFAULT_CATEGORIES.copy()
        self.current_category = 0
        self.load_categories()
        self._set_initial_category()
    
    def load_categories(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    if 'categories' in data:
                        self.categories = data['categories']
        except Exception as e:
            print(f"⚠️ Ошибка загрузки категорий: {e}")
    
    def save_categories(self, config_data):
        config_data['categories'] = self.categories
        return config_data
    
    def _clamp_current_category(self):
        """Возвращает current_category в допустимые пределы.

        Может выйти за границы, если количество категорий изменилось (например,
        категория была удалена), а current_category все еще указывает
        на несуществующую позицию.
        """
        if not self.categories:
            self.current_category = 0
            return
        if self.current_category >= len(self.categories) or self.current_category < 0:
            self.current_category = 0

    def get_filtered_apps(self, all_apps):
        self._clamp_current_category()
        if self.current_category == 0:
            return all_apps
        category_name = self.categories[self.current_category]['name']
        return [app for app in all_apps if app.get('category', 'Other') == category_name]
    
    def get_current_category(self):
        self._clamp_current_category()
        return self.categories[self.current_category]
    
    def next_category(self):
        self._clamp_current_category()
        self.current_category = (self.current_category + 1) % len(self.categories)
        return self.get_current_category()
    
    def prev_category(self):
        self._clamp_current_category()
        self.current_category = (self.current_category - 1) % len(self.categories)
        return self.get_current_category()
    
    def set_app_category(self, app_data, category_name):
        app_data['category'] = category_name
        return app_data
    
    def get_category_names(self):
        return [cat['name'] for cat in self.categories[1:]]

    def get_default_category(self):
        for category in self.categories:
            if category.get('is_default', False):
                return category['name']
        return 'Other'

    def _set_initial_category(self):
        """Устанавливает начальную категорию при запуске на основе флага is_default"""
        for i, category in enumerate(self.categories):
            if category.get('is_default', False):
                self.current_category = i
                print(f"Категория по умолчанию установлена: {category['name']} (индекс {i})")
                return
        
        


class CategorySelector(QWidget):
    """Виджет пользовательского интерфейса для визуального выбора категорий"""
    
    category_changed = pyqtSignal(int)
    
    def __init__(self, category_manager, scaling, parent=None):
        super().__init__(parent)
        self.category_manager = category_manager
        self.scaling = scaling
        self.category_labels = []
        self.is_animating = False
        self.is_visible_state = False
        
        self.setup_ui()
        self.update_display()
        self.hide_animated()
    
    def setup_ui(self):
        self._normal_height = self.scaling.scale(90)
        self.setFixedHeight(self._normal_height)
        self.setMaximumHeight(0)
        
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(
            self.scaling.scale(20),
            self.scaling.scale(12),
            self.scaling.scale(20),
            self.scaling.scale(12)
        )
        self._layout.setSpacing(self.scaling.scale(15))
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(42, 42, 42, 0.95);
                border: 2px solid #444;
                border-radius: {self.scaling.scale(12)}px;
            }}
        """)
        
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity_effect)
        
        self._build_labels()

    def _build_labels(self):
        """Создает элементы QLabel для текущих категорий.

        Вынесено из setup_ui(), чтобы можно было вызывать из rebuild()
        при изменении категорий (добавление/переименование/удаление),
        а не оставлять панель с метками, созданными один раз при запуске.
        """
        for label in self.category_labels:
            self._layout.removeWidget(label)
            label.deleteLater()
        self.category_labels = []

        for i, category in enumerate(self.category_manager.categories):
            label = QLabel(f"{category['icon']} {category['name']}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(self.scaling.scale(150), self.scaling.scale(60))
            self._apply_style(label, is_active=False, color=category['color'])
            self._layout.addWidget(label)
            self.category_labels.append(label)

    def rebuild(self):
        """Перестраивает панель после изменения категорий
        (добавление/переименование/удаление из Менеджера категорий),
        чтобы изменения были видны сразу без перезапуска лаунчера,
        и предотвращает IndexError в update_display(), если количество
        категорий изменилось.
        """
        num_categories = len(self.category_manager.categories)
        if num_categories == 0:
            return
        if self.category_manager.current_category >= num_categories:
            self.category_manager.current_category = 0

        self._build_labels()

        selector_width = (num_categories * self.scaling.scale(155)) + self.scaling.scale(40)
        self.setFixedWidth(selector_width)

        self.update_display()
    
    def _apply_style(self, label, is_active, color):
        if is_active:
            label.setStyleSheet(f"""
                QLabel {{
                    background-color: {color};
                    color: #000000;
                    border: 3px solid white;
                    border-radius: {self.scaling.scale(10)}px;
                    font-size: {self.scaling.scale_font(20)}px;
                    font-weight: bold;
                    padding: {self.scaling.scale(10)}px;
                }}
            """)
        else:
            label.setStyleSheet(f"""
                QLabel {{
                    background-color: #2a2a2a;
                    color: white;
                    border: 2px solid #555;
                    border-radius: {self.scaling.scale(10)}px;
                    font-size: {self.scaling.scale_font(18)}px;
                    font-weight: 600;
                    padding: {self.scaling.scale(10)}px;
                }}
            """)
    
    def update_display(self):
        current = self.category_manager.current_category
        num_categories = len(self.category_manager.categories)
        for i, label in enumerate(self.category_labels):
            if i >= num_categories:
                # Категории изменились (например, удаление), но rebuild()
                # еще не вызван: не пытаемся читать несуществующий индекс.
                break
            category = self.category_manager.categories[i]
            is_active = (i == current)
            self._apply_style(label, is_active, category['color'])
    
    def navigate_right(self):
        if self.is_animating:
            return
        self.is_animating = True
        self.category_manager.next_category()
        self.update_display()
        self.category_changed.emit(self.category_manager.current_category)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, lambda: setattr(self, 'is_animating', False))
    
    def navigate_left(self):
        if self.is_animating:
            return
        self.is_animating = True
        self.category_manager.prev_category()
        self.update_display()
        self.category_changed.emit(self.category_manager.current_category)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, lambda: setattr(self, 'is_animating', False))
    
    def show_animated(self):
        if self.is_visible_state:
            return
        self.is_visible_state = True
        self.setMaximumHeight(self._normal_height)
        self.show()  
        self.raise_()  
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(250)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_animation.start()
    
    def hide_animated(self):
        if not self.is_visible_state:
            return
        self.is_visible_state = False
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade_animation.finished.connect(lambda: self.setMaximumHeight(0))
        self.fade_animation.start()


def _position_category_selector(launcher):
    """Выравнивает виджет категорий по текущей вертикальной позиции
    карусели (которая может смещаться вверх/вниз ползунком в настройках),
    а не фиксирует ее на значении y, вычисленном при запуске. Селектор
    прикрепляется прямо над каруселью, следуя за ее перемещением.
    """
    if not hasattr(launcher, 'category_selector') or not hasattr(launcher, 'carousel_container'):
        return

    selector = launcher.category_selector
    carousel_top_in_launcher = launcher.carousel_container.mapTo(launcher, QPoint(0, 0)).y()

    gap = launcher.scaling.scale(20)
    y = carousel_top_in_launcher - selector.height() - gap
    y = max(0, y)

    screen_width = launcher.width()
    selector_width = selector.width()
    selector.move((screen_width - selector_width) // 2, y)


def integrate_categories(launcher):
    """Интеграция системы категорий в лаунчер"""
    launcher.category_manager = CategoryManager(launcher.config_file)
    launcher.category_selector = CategorySelector(
        launcher.category_manager, 
        launcher.scaling, 
        launcher 
    )
    
    # УСТАНОВКА ФИКСИРОВАННЫХ РАЗМЕРОВ
    num_categories = len(launcher.category_manager.categories)
    selector_width = (num_categories * launcher.scaling.scale(155)) + launcher.scaling.scale(40)
    launcher.category_selector.setFixedWidth(selector_width)
    
    # Начальная позиция: закреплена над каруселью (без фиксированного y)
    _position_category_selector(launcher)
    
    launcher.category_selector.setWindowFlags(Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint)
    launcher.category_selector.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    launcher.category_selector.raise_()
    
    launcher.category_selector.category_changed.connect(launcher._on_category_changed)
    launcher.is_in_category_selector = False
    launcher._category_selector_blocking_input = False
    
    original_build = launcher.build_infinite_carousel
    
    def build_infinite_carousel_with_filter():
        if not hasattr(launcher, '_all_apps_backup'):
            launcher._all_apps_backup = launcher.apps.copy()
        launcher.apps = launcher.category_manager.get_filtered_apps(launcher._all_apps_backup)
        if launcher.current_index >= len(launcher.apps) and launcher.apps:
            launcher.current_index = 0
        original_build()
    
    launcher.build_infinite_carousel = build_infinite_carousel_with_filter
    
    def apply_default_categories():
        default_cat = launcher.category_manager.get_default_category()
        changed = False
        for app in launcher.apps:
            if 'category' not in app or not app['category']:
                app['category'] = default_cat
                changed = True
        if changed:
            launcher.save_config()
            print(f"Применена категория по умолчанию '{default_cat}' к приложениям без категории")
    
    apply_default_categories()
    launcher.apply_default_categories = apply_default_categories
    
    launcher.build_infinite_carousel()


def add_category_navigation_to_keypressevent(launcher, event):
    """Добавление навигации по категориям с клавиатуры"""
    if not hasattr(launcher, 'category_selector'):
        return False
    
    key = event.key()
    
    if launcher.is_in_category_selector:
        if key == Qt.Key.Key_Left:
            launcher.sound_manager.navigate()
            launcher.category_selector.navigate_left()
            event.accept()
            return True
        elif key == Qt.Key.Key_Right:
            launcher.sound_manager.navigate()
            launcher.category_selector.navigate_right()
            event.accept()
            return True
        elif key == Qt.Key.Key_Down:
            launcher.sound_manager.navigate()
            launcher.is_in_category_selector = False
            launcher.category_selector.hide_animated()
            event.accept()
            return True
        elif key == Qt.Key.Key_Escape:
            launcher.sound_manager.back()
            launcher.is_in_category_selector = False
            launcher.category_selector.hide_animated()
            event.accept()
            return True
        event.accept()
        return True
    
    if key == Qt.Key.Key_Up:
        if not launcher.is_in_menu and not getattr(launcher, 'reorder_active', False):
            launcher.sound_manager.navigate()
            launcher.is_in_category_selector = True
            _position_category_selector(launcher)
            launcher.category_selector.show_animated()
            event.accept()
            return True
        else:
            return False
    
    return False


def add_quick_category_shortcut(launcher):
    """Добавление горячей клавиши C для быстрого диалога категорий"""
    original_key_press = launcher.keyPressEvent
    
    def enhanced_key_press(event):
        key = event.key()
        
        if key == Qt.Key.Key_C and not launcher.is_in_menu and launcher.apps and not launcher.is_in_category_selector:
            app_data = launcher.apps[launcher.current_index]
            launcher._category_dialog_open = True
            new_category = QuickCategoryDialog.show(launcher, app_data)
            launcher._category_dialog_open = False
            
            if new_category:
                if not hasattr(launcher, '_all_apps_backup'):
                    launcher._all_apps_backup = launcher.apps.copy()
                
                original_index = next((i for i, app in enumerate(launcher._all_apps_backup) 
                                     if app['name'] == app_data['name']), None)
                
                if original_index is not None:
                    launcher._all_apps_backup[original_index]['category'] = new_category
                    launcher.save_config()
                    launcher.build_infinite_carousel()
                    print(f"✅ {app_data['name']} → {new_category}")
            
            launcher.setFocus()
            launcher.activateWindow()
            return
        
        original_key_press(event)
    
    launcher.keyPressEvent = enhanced_key_press


class QuickCategoryDialog:
    """Быстрый диалог для изменения категории"""
    
    @staticmethod
    def show(launcher, app_data):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QWidget
        from PyQt6.QtCore import Qt, QTimer
        import pygame
        
        dialog = QDialog(launcher)
        dialog.setWindowTitle(f"Категория: {app_data['name']}")
        dialog.setModal(True)
        dialog.setFixedSize(launcher.scaling.scale(450), launcher.scaling.scale(450))
        dialog.setStyleSheet("QDialog { background-color: #1a1a1a; }")
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(launcher.scaling.scale(10))
        layout.setContentsMargins(
            launcher.scaling.scale(20),
            launcher.scaling.scale(15),
            launcher.scaling.scale(20),
            launcher.scaling.scale(20)
        )
        
        header_widget = QWidget()
        header_widget.setStyleSheet(f"""
            QWidget {{
                background-color: #2a2a2a;
                border-radius: {launcher.scaling.scale(8)}px;
                padding: {launcher.scaling.scale(10)}px;
            }}
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(
            launcher.scaling.scale(12), launcher.scaling.scale(8),
            launcher.scaling.scale(12), launcher.scaling.scale(8)
        )
        header_layout.setSpacing(launcher.scaling.scale(2))
        
        title = QLabel("📂 Категория")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: {launcher.scaling.scale_font(15)}px;
                font-weight: bold;
                color: white;
                background: transparent;
                border: none;
            }}
        """)
        header_layout.addWidget(title)
        
        subtitle = QLabel(f"{app_data['name']}")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"""
            QLabel {{
                font-size: {launcher.scaling.scale_font(11)}px;
                color: #888;
                background: transparent;
                border: none;
            }}
        """)
        subtitle.setWordWrap(True)
        subtitle.setMaximumHeight(launcher.scaling.scale(30))
        header_layout.addWidget(subtitle)
        
        layout.addWidget(header_widget)
        
        category_buttons = []
        current_category = app_data.get('category', 'Other')
        dialog._category_selected = False
        categories_to_show = launcher.category_manager.categories[1:]
        
        for category in categories_to_show:
            btn = QPushButton(f"{category['icon']}  {category['name']}")
            btn.setFixedHeight(launcher.scaling.scale(55))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            base_style = f"""
                QPushButton {{
                    background-color: #2a2a2a;
                    color: white;
                    border: 2px solid #444;
                    padding: {launcher.scaling.scale(12)}px {launcher.scaling.scale(15)}px;
                    border-radius: {launcher.scaling.scale(8)}px;
                    font-size: {launcher.scaling.scale_font(14)}px;
                    font-weight: bold;
                    text-align: left;
                }}
                QPushButton:hover {{ background-color: #3a3a3a; }}
            """
            
            if category['name'] == current_category:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {category['color']};
                        color: #000000;
                        border: 2px solid #666;
                        padding: {launcher.scaling.scale(12)}px {launcher.scaling.scale(15)}px;
                        border-radius: {launcher.scaling.scale(8)}px;
                        font-size: {launcher.scaling.scale_font(14)}px;
                        font-weight: bold;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background-color: {category['color']};
                        border-color: #888;
                    }}
                """)
            else:
                btn.setStyleSheet(base_style)
            
            btn_index = categories_to_show.index(category)
            
            def on_category_click(checked, idx=btn_index):
                dialog._category_selected = True
                dialog.done(idx)
            
            btn.clicked.connect(on_category_click)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            category_buttons.append((btn, category))
            layout.addWidget(btn)
        
        layout.addStretch()
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                color: white;
                border: 2px solid #444;
                padding: {launcher.scaling.scale(10)}px;
                border-radius: {launcher.scaling.scale(8)}px;
                font-size: {launcher.scaling.scale_font(13)}px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #3a3a3a; }}
        """)
        cancel_btn.clicked.connect(dialog.reject)
        cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(cancel_btn)
        
        dialog.current_index = [0]
        dialog.category_buttons = category_buttons
        
        def update_focus():
            for i, (btn, category) in enumerate(dialog.category_buttons):
                is_current = (category['name'] == current_category)
                
                if i == dialog.current_index[0]:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {category['color'] if is_current else '#3a3a3a'};
                            color: {'#000000' if is_current else 'white'};
                            border: 3px solid white;
                            padding: {launcher.scaling.scale(12)}px {launcher.scaling.scale(15)}px;
                            border-radius: {launcher.scaling.scale(8)}px;
                            font-size: {launcher.scaling.scale_font(15)}px;
                            font-weight: bold;
                            text-align: left;
                        }}
                    """)
                else:
                    if is_current:
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {category['color']};
                                color: #000000;
                                border: 2px solid #666;
                                padding: {launcher.scaling.scale(12)}px {launcher.scaling.scale(15)}px;
                                border-radius: {launcher.scaling.scale(8)}px;
                                font-size: {launcher.scaling.scale_font(14)}px;
                                font-weight: bold;
                                text-align: left;
                            }}
                            QPushButton:hover {{
                                background-color: {category['color']};
                                border-color: #888;
                            }}
                        """)
                    else:
                        btn.setStyleSheet(f"""
                            QPushButton {{
                                background-color: #2a2a2a;
                                color: white;
                                border: 2px solid #444;
                                padding: {launcher.scaling.scale(12)}px {launcher.scaling.scale(15)}px;
                                border-radius: {launcher.scaling.scale_font(8)}px;
                                font-size: {launcher.scaling.scale_font(14)}px;
                                font-weight: bold;
                                text-align: left;
                            }}
                            QPushButton:hover {{ background-color: #3a3a3a; }}
                        """)
        
        def key_handler(event):
            if event.isAutoRepeat():
                return
            key = event.key()
            
            if key == Qt.Key.Key_Up:
                dialog.current_index[0] = (dialog.current_index[0] - 1) % len(dialog.category_buttons)
                update_focus()
                event.accept()
                return
            elif key == Qt.Key.Key_Down:
                dialog.current_index[0] = (dialog.current_index[0] + 1) % len(dialog.category_buttons)
                update_focus()
                event.accept()
                return
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                dialog._category_selected = True
                dialog.category_buttons[dialog.current_index[0]][0].click()
                event.accept()
                return
            elif key == Qt.Key.Key_Escape:
                dialog.reject()
                event.accept()
                return
            else:
                super(dialog.__class__, dialog).keyPressEvent(event)
        
        dialog.keyPressEvent = key_handler
        
        update_focus()
        
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        dialog.setFocus()
        
        result = dialog.exec()
        
        if hasattr(dialog, '_category_selected') and dialog._category_selected:
            if 0 <= result < len(categories_to_show):
                selected_category = categories_to_show[result]['name']
                return selected_category
        
        return None


def add_category_joystick_support(launcher):
    """УПРОЩЕНО: Регистрация селектора категорий в JoystickManager"""
    
    if not hasattr(launcher, 'joystick_manager') or not launcher.joystick_manager:
        print("⚠️ JoystickManager не найден, интеграция джойстика для категорий пропущена")
        return
    
    launcher.joystick_manager.register_category_support(launcher)


def _handle_bottom_menu_joystick(launcher):
    """Обработка ввода с джойстика в нижнем меню"""
    import pygame
    
    y_axis = launcher.joystick.get_axis(1)
    hat = (0, 0)
    if launcher.joystick.get_numhats() > 0:
        hat = launcher.joystick.get_hat(0)
    
    current_state_y = (y_axis < -launcher.axis_deadzone, hat[1])
    last_state_y = getattr(launcher, '_bottom_menu_category_last_y', (False, 0))
    
    if y_axis < -launcher.axis_deadzone and not last_state_y[0]:
        launcher._ignore_up_until = pygame.time.get_ticks() + 300
    elif hat[1] == 1 and last_state_y[1] != 1:
        launcher._ignore_up_until = pygame.time.get_ticks() + 300
    
    launcher._bottom_menu_category_last_y = current_state_y


def _handle_category_selector_joystick_blocking(launcher):
    """ИСПРАВЛЕНИЕ: Управление селектором категорий — LEFT/RIGHT навигация, DOWN закрытие + ПОДДЕРЖКА D-PAD"""
    import pygame
    from PyQt6.QtCore import QTimer
    
    x_axis = launcher.joystick.get_axis(0)
    y_axis = launcher.joystick.get_axis(1)
    
    hat = (0, 0)
    if launcher.joystick.get_numhats() > 0:
        hat = launcher.joystick.get_hat(0)
    
    # Полное чтение D-Pad PS4
    dpad_left = launcher.joystick.get_button(13) if launcher.joystick.get_numbuttons() > 13 else False
    dpad_right = launcher.joystick.get_button(14) if launcher.joystick.get_numbuttons() > 14 else False
    dpad_down = launcher.joystick.get_button(12) if launcher.joystick.get_numbuttons() > 12 else False
    
    # ГОРИЗОНТАЛЬНАЯ НАВИГАЦИЯ (смена категории LEFT/RIGHT)
    current_state_x = (x_axis > launcher.axis_deadzone, x_axis < -launcher.axis_deadzone, hat[0], dpad_right, dpad_left)
    last_state_x = getattr(launcher, '_category_selector_last_x', (False, False, 0, False, False))
    
    moved_right = False
    moved_left = False
    
    # Аналоговый стик
    if x_axis > launcher.axis_deadzone and not last_state_x[0]:
        moved_right = True
    elif x_axis < -launcher.axis_deadzone and not last_state_x[1]:
        moved_left = True
    # Hat (крестовина)
    elif hat[0] == 1 and last_state_x[2] != 1:
        moved_right = True
    elif hat[0] == -1 and last_state_x[2] != -1:
        moved_left = True
    # D-Pad PS4
    elif dpad_right and not last_state_x[3]:
        moved_right = True
    elif dpad_left and not last_state_x[4]:
        moved_left = True
    
    if moved_right:
        launcher.sound_manager.navigate()
        launcher.category_selector.navigate_right()
    elif moved_left:
        launcher.sound_manager.navigate()
        launcher.category_selector.navigate_left()
    
    launcher._category_selector_last_x = current_state_x
    
    current_state_y = (y_axis < -launcher.axis_deadzone, y_axis > launcher.axis_deadzone, hat[1], dpad_down)
    last_state_y = getattr(launcher, '_category_selector_last_y', (False, False, 0, False))
    
    # Обнаружение ТОЛЬКО нажатия DOWN (не UP)
    moved_down = False
    # Аналоговый стик
    if y_axis > launcher.axis_deadzone and not last_state_y[1]:
        moved_down = True
    # Hat
    elif hat[1] == -1 and last_state_y[2] != -1:
        moved_down = True
    # D-Pad PS4
    elif dpad_down and not last_state_y[3]:
        moved_down = True
    
    if moved_down:
        launcher.sound_manager.navigate()
        _close_category_selector_with_block(launcher)
        return
    
    launcher._category_selector_last_y = current_state_y
    
    current_b_state = launcher.joystick.get_button(1)
    last_b_state = getattr(launcher, '_category_selector_last_b', False)
    
    # Обнаружение нажатия (а не удержания)
    if current_b_state and not last_b_state:
        launcher.sound_manager.back()
        _close_category_selector_with_block(launcher)
        current_time = pygame.time.get_ticks()
        launcher.button_cooldown[1] = current_time + 500  # Дополнительная блокировка B на 500мс
        launcher._category_selector_last_b = True  # Оставляем True во избежание повторного срабатывания
        return
    
    launcher._category_selector_last_b = current_b_state
    
    for i in range(launcher.joystick.get_numbuttons()):
        if launcher.joystick.get_button(i):
            current_time = pygame.time.get_ticks()
            # Обновление cooldown для ВСЕХ кнопок
            launcher.button_cooldown[i] = current_time + 400


def _close_category_selector_with_block(launcher):
    """Закрывает селектор категорий и блокирует ВСЕ входы на 500мс"""
    from PyQt6.QtCore import QTimer
    import pygame
    
    launcher.is_in_category_selector = False
    launcher.category_selector.hide_animated()
    
    launcher._category_selector_blocking_input = True
    
    # Сброс состояний (5 элементов для X и 4 для Y)
    launcher._category_selector_last_x = (False, False, 0, False, False)
    launcher._category_selector_last_y = (False, False, 0, False)
    launcher._category_selector_last_b = False
    
    # Блокировка ВСЕХ кнопок на 500мс
    current_time = pygame.time.get_ticks()
    for i in range(launcher.joystick.get_numbuttons()):
        launcher.button_cooldown[i] = current_time + 500
    
    # Принудительная установка состояния D-Pad в TRUE во избежание повторного срабатывания
    y_axis = launcher.joystick.get_axis(1)
    hat = (0, 0)
    if launcher.joystick.get_numhats() > 0:
        hat = launcher.joystick.get_hat(0)
    dpad_down = launcher.joystick.get_button(12) if launcher.joystick.get_numbuttons() > 12 else False
    dpad_up = launcher.joystick.get_button(11) if launcher.joystick.get_numbuttons() > 11 else False
    
    launcher._carousel_last_y = (
        y_axis > launcher.axis_deadzone or dpad_down,  # Если зажат D-Pad DOWN, принудительно TRUE
        y_axis < -launcher.axis_deadzone or dpad_up,   # Если зажат D-Pad UP, принудительно TRUE
        hat[1] if hat[1] != 0 else launcher._carousel_last_y[2] if hasattr(launcher, '_carousel_last_y') else 0,
        True if dpad_down else False,  # Принудительно D-Pad DOWN как TRUE
        True if dpad_up else False     # Принудительно D-Pad UP как TRUE
    )
    
    # Блокировка специфичных cooldown для D-Pad
    if dpad_down:
        launcher.button_cooldown[12] = current_time + 600  # Дополнительно 100мс для D-Pad DOWN
    if dpad_up:
        launcher.button_cooldown[11] = current_time + 600  # Дополнительно 100мс для D-Pad UP
    
    def unblock():
        launcher._category_selector_blocking_input = False
    
    QTimer.singleShot(500, unblock)


def add_category_to_edit_dialog(dialog, launcher):
    """Добавление выбора категории в EditAppDialog"""
    from PyQt6.QtWidgets import QComboBox, QLabel
    
    layout = dialog.layout()
    if layout is None:
        print("⚠️ add_category_to_edit_dialog вызван до setLayout()")
        return
    
    category_label = QLabel("Категория:")
    category_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
    
    category_combo = QComboBox()
    category_combo.addItems(launcher.category_manager.get_category_names())
    category_combo.setStyleSheet("""
        QComboBox {
            background-color: #2a2a2a;
            color: white;
            border: 2px solid #444;
            padding: 10px;
            border-radius: 8px;
            font-size: 14px;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox::down-arrow {
            image: none;
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #2a2a2a;
            color: white;
            selection-background-color: #3a3a3a;
        }
    """)
    
    if hasattr(dialog, 'app_data'):
        current_category = dialog.app_data.get('category', 'Other')
    else:
        current_category = 'Other'
    
    index = category_combo.findText(current_category)
    if index >= 0:
        category_combo.setCurrentIndex(index)
    
    button_layout_index = layout.count() - 1
    layout.insertWidget(button_layout_index - 1, category_label)
    layout.insertWidget(button_layout_index, category_combo)
    
    dialog.category_combo = category_combo
    
    original_get_data = dialog.get_app_data
    
    def get_app_data_with_category():
        data = original_get_data()
        data['category'] = dialog.category_combo.currentText()
        return data
    
    dialog.get_app_data = get_app_data_with_category

