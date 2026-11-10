from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QTimer
import time

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class ReorderMode:
    """Управляет состоянием изменения порядка и обратной связью пользовательского интерфейса"""
    
    def __init__(self, launcher):
        self.launcher = launcher
        self.is_active = False
        self.selected_index = None
        self.target_index = None
        
        # Таймер для определения длинного нажатия (только для клавиатуры)
        self.long_press_timer = QTimer()
        self.long_press_timer.timeout.connect(self._activate_reorder)
        self.long_press_duration = 800  # мс удерживания перед активацией
        
        # Оверлей пользовательского интерфейса
        self.overlay = None
        self.instruction_label = None

        # Защита от частых нажатий (дебаунс) для кнопок
        self.last_button_times = {}
        
        # Флаг предотвращения повторной активации после выхода
        self.recently_exited = False
        self.exit_cooldown_timer = QTimer()
        self.exit_cooldown_timer.timeout.connect(self._clear_exit_cooldown)
        self.exit_cooldown_timer.setSingleShot(True)
        
    def _clear_exit_cooldown(self):
        """Очищает флаг задержки выхода"""
        self.recently_exited = False
    
    def _is_dialog_active(self):
        """Проверяет, активен ли какой-либо диалог или меню"""
        from PyQt6.QtWidgets import QApplication
        # Проверка, открыт ли модальный диалог
        active_modal = QApplication.activeModalWidget()
        if active_modal:
            return True
        # Проверка, открыт ли какой-либо всплывающий элемент
        active_popup = QApplication.activePopupWidget()
        if active_popup:
            return True
        return False
        
    def start_long_press(self):
        """Вызывается при нажатии кнопки запуска"""
        # Не активировать, если открыто меню, диалог или недавно выполнен выход
        if (not self.is_active and 
            self.launcher.apps and 
            not self.recently_exited and
            not self.launcher.is_in_menu and
            not self._is_dialog_active()):
            self.long_press_timer.start(self.long_press_duration)
    
    def cancel_long_press(self):
        """Вызывается при отпускании кнопки запуска"""
        if self.long_press_timer.isActive():
            self.long_press_timer.stop()
    
    def force_cancel_all_timers(self):
        """Принудительно отменяет все таймеры — вызывается при запуске приложения"""
        if self.long_press_timer.isActive():
            self.long_press_timer.stop()
        if self.exit_cooldown_timer.isActive():
            self.exit_cooldown_timer.stop()
    
    def _activate_reorder(self):
        """Активирует режим сортировки после длинного нажатия"""
        self.long_press_timer.stop()
        
        # Не активировать, если открыт диалог или меню
        if (self.launcher.apps and 
            not self.is_active and 
            not self.launcher.is_in_menu and
            not self._is_dialog_active()):
            self.is_active = True
            self.selected_index = self.launcher.current_index
            self.target_index = self.launcher.current_index
            self._show_reorder_ui()
            self._update_tile_highlights()
            print(f"🔄 Режим сортировки активирован — Выбрано: {self.launcher.apps[self.selected_index]['name']}")
    
    def _show_reorder_ui(self):
        """Показывает визуальную обратную связь для режима сортировки"""
        if self.overlay is None:
            # Создание полупрозрачного оверлея
            self.overlay = QWidget(self.launcher)
            self.overlay.setGeometry(0, 0, self.launcher.width(), self.launcher.height())
            self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.5);")
            self.overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            
            # Создание метки с инструкциями
            self.instruction_label = QLabel(self.overlay)
            self.instruction_label.setText(
                "🔄 РЕЖИМ СОРТИРОВКИ\n\n"
                "← → для перемещения\n"
                "Enter/A для подтверждения | Esc/B для отмены\n"
                "R или RB для переключения режима"
            )
            self.instruction_label.setStyleSheet(f"""
                QLabel {{
                    background-color: rgba(30, 30, 30, 0.95);
                    color: white;
                    font-size: {self.launcher.scaling.scale_font(18)}px;
                    font-weight: bold;
                    padding: {self.launcher.scaling.scale(30)}px;
                    border-radius: {self.launcher.scaling.scale(20)}px;
                    border: {self.launcher.scaling.scale(3)}px solid white;
                }}
            """)
            self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Позиционирование по центру вверху
            self.instruction_label.adjustSize()
            x = (self.launcher.width() - self.instruction_label.width()) // 2
            y = self.launcher.scaling.scale(100)
            self.instruction_label.move(x, y)
        
        self.overlay.raise_()
        self.overlay.show()
        self.instruction_label.show()
        
        # Добавление номеров позиций на плитки
        self._add_position_numbers()
    
    def _hide_reorder_ui(self):
        """Скрывает интерфейс режима сортировки"""
        if self.overlay:
            self.overlay.hide()
        if self.instruction_label:
            self.instruction_label.hide()
        
        # Удаление номеров позиций
        self._remove_position_numbers()
    
    def _add_position_numbers(self):
        """Добавляет метки номеров позиций к каждой плитке"""
        if not self.launcher.tiles:
            return
        
        for tile in self.launcher.tiles:
            if not hasattr(tile, 'position_label'):
                # Создание метки позиции
                tile.position_label = QLabel(tile)
                tile.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                tile.position_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: rgba(0, 0, 0, 0.8);
                        color: white;
                        font-size: {self.launcher.scaling.scale_font(32)}px;
                        font-weight: bold;
                        border-radius: {self.launcher.scaling.scale(25)}px;
                        border: {self.launcher.scaling.scale(2)}px solid white;
                    }}
                """)
                
                # Позиционирование в верхнем левом углу плитки
                size = self.launcher.scaling.scale(50)
                tile.position_label.setFixedSize(size, size)
                tile.position_label.move(
                    self.launcher.scaling.scale(10),
                    self.launcher.scaling.scale(10)
                )
            
            # Обновление номера (индексация с 1 для пользователя)
            tile.position_label.setText(str(tile.app_index + 1))
            tile.position_label.show()
            tile.position_label.raise_()
    
    def _remove_position_numbers(self):
        """Удаляет метки номеров позиций с плиток"""
        if not self.launcher.tiles:
            return
        
        for tile in self.launcher.tiles:
            if hasattr(tile, 'position_label'):
                tile.position_label.hide()
    
    def _update_tile_highlights(self):
        """Обновляет визуальную подсветку плиток во время сортировки"""
        if not self.is_active or not self.launcher.tiles:
            return
        
        num_apps = len(self.launcher.apps)
        
        for i, tile in enumerate(self.launcher.tiles):
            app_idx = tile.app_index
            
            # Выбранная плитка — яркая золотая рамка
            if app_idx == self.selected_index:
                tile.image_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: #1a1a1a;
                        border: {self.launcher.scaling.scale(5)}px solid #FFD700;
                        border-radius: {tile.border_radius}px;
                        color: #ffffff;
                        font-size: {self.launcher.scaling.scale_font(18)}px;
                        font-weight: 600;
                    }}
                """)
            # Целевая позиция — синяя рамка
            elif app_idx == self.target_index:
                tile.image_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: #1a1a1a;
                        border: {self.launcher.scaling.scale(5)}px solid #00BFFF;
                        border-radius: {tile.border_radius}px;
                        color: #ffffff;
                        font-size: {self.launcher.scaling.scale_font(18)}px;
                        font-weight: 600;
                    }}
                """)
            # Обычные плитки
            else:
                tile.image_label.setStyleSheet(f"""
                    QLabel {{
                        background-color: #1a1a1a;
                        border: {self.launcher.scaling.scale(2)}px solid #444;
                        border-radius: {tile.border_radius}px;
                        color: #cccccc;
                        font-size: {self.launcher.scaling.scale_font(18)}px;
                        font-weight: 600;
                    }}
                """)
        
        # Обновление номеров позиций
        self._add_position_numbers()    

    def move_left(self):
        """Перемещает целевую позицию влево"""
        if not self.is_active:
            return False
        
        num_apps = len(self.launcher.apps)
        
        if num_apps <= 5:
            # Линейное перемещение
            if self.target_index > 0:
                self.target_index -= 1
                # Без анимации, только обновление подсветки
                self._update_tile_highlights()
                return True
        else:
            # Циклическое перемещение — обновление цели ДО анимации
            new_target = (self.target_index - 1) % num_apps
            self.target_index = new_target
            self.launcher.current_index = self.target_index
            self.launcher.animate_carousel("left")
            # Подсветка обновится после анимации
            QTimer.singleShot(260, self._update_tile_highlights)
            return True
        
        return False
    
    def move_right(self):
        """Перемещает целевую позицию вправо"""
        if not self.is_active:
            return False
        
        num_apps = len(self.launcher.apps)
        
        if num_apps <= 5:
            # Линейное перемещение
            if self.target_index < num_apps - 1:
                self.target_index += 1
                # Без анимации, только обновление подсветки
                self._update_tile_highlights()
                return True
        else:
            # Циклическое перемещение — обновление цели ДО анимации
            new_target = (self.target_index + 1) % num_apps
            self.target_index = new_target
            self.launcher.current_index = self.target_index
            self.launcher.animate_carousel("right")
            # Подсветка обновится после анимации
            QTimer.singleShot(260, self._update_tile_highlights)
            return True
        
        return False
    
    def confirm_reorder(self):
        """Подтверждает и применяет изменения порядка"""
        if not self.is_active:
            return False
        
        # Установка флага НЕМЕДЛЕННО для блокировки любых других обработчиков
        self.recently_exited = True
        
        if self.selected_index != self.target_index:
            # Выполнение перестановки
            app_to_move = self.launcher.apps.pop(self.selected_index)
            self.launcher.apps.insert(self.target_index, app_to_move)
            
            # Обновление текущего индекса для следования за перемещенным приложением
            self.launcher.current_index = self.target_index
            
            # Сохранение и пересоздание
            self.launcher.save_config()
            
            print(f"✅ Перемещено '{app_to_move['name']}' из позиции {self.selected_index} в {self.target_index}")
        
        self._exit_reorder()
        # Пересоздание ПОСЛЕ выхода, чтобы избежать повторной активации режима сортировки
        self.launcher.build_infinite_carousel()
        
        # Увеличенная задержка после подтверждения для предотвращения случайного запуска
        self.exit_cooldown_timer.start(1000)  # Задержка 1 секунда
        return True
    
    def cancel_reorder(self):
        """Отменяет режим сортировки без изменений"""
        if not self.is_active:
            return False
        
        # Возврат в исходную позицию
        original_index = self.selected_index
        
        print("❌ Сортировка отменена")
        self._exit_reorder()
        
        # Пересоздание ПОСЛЕ выхода
        self.launcher.current_index = original_index
        self.launcher.build_infinite_carousel()
        return True
    
    def _exit_reorder(self):
        """Выходит из режима сортировки и выполняет очистку"""
        self.is_active = False
        self.selected_index = None
        self.target_index = None
        self._hide_reorder_ui()
        
        # Установка задержки для предотвращения немедленной повторной активации
        self.recently_exited = True
        self.exit_cooldown_timer.start(500)  # Задержка 500 мс
        
        # Принудительная остановка всех таймеров
        self.cancel_long_press()
    
    def handle_joypad_button(self, button_index):
        """Обрабатывает кнопку геймпада для режима сортировки — кнопка RB (5) переключает"""
        current_time = time.time()
        if button_index in self.last_button_times and current_time - self.last_button_times[button_index] < 0.3:
            return False
        self.last_button_times[button_index] = current_time

        # Кнопка RB переключает режим сортировки
        if button_index in (5, 10):  # Кнопка RB
            # Не активировать, если открыт диалог или меню
            if self._is_dialog_active() or self.launcher.is_in_menu:
                return False
                
            if not self.is_active:
                if self.launcher.apps and not self.recently_exited:
                    self._activate_reorder()
                    return True
            else:
                self.cancel_reorder()
                return True
        
        return False


def integrate_reorder_mode(launcher):
    """
    Интегрирует режим сортировки в лаунчер.
    Вызывайте это из TVLauncher.__init__() после self.init_ui()
    
    Использование:
        from app_reorder import integrate_reorder_mode
        # В TVLauncher.__init__:
        integrate_reorder_mode(self)
    """
    launcher.reorder_mode = ReorderMode(launcher)
    
    # Сохранение исходного keyPressEvent
    original_key_press = launcher.keyPressEvent
    
    def enhanced_key_press(event):
        """Улучшенный keyPressEvent с поддержкой сортировки"""
        if event.isAutoRepeat():
            original_key_press(event)
            return
        
        key = event.key()
        
        # Клавиша R переключает режим сортировки
        if key == Qt.Key.Key_R:
            # Не активировать, если открыт диалог или меню
            if launcher.reorder_mode._is_dialog_active() or launcher.is_in_menu:
                original_key_press(event)
                return
                
            if not launcher.reorder_mode.is_active:
                if launcher.apps and not launcher.reorder_mode.recently_exited:
                    launcher.reorder_mode._activate_reorder()
            else:
                launcher.reorder_mode.cancel_reorder()
            return
        
        # В режиме сортировки перехват навигации
        if launcher.reorder_mode.is_active:
            if key == Qt.Key.Key_Left:
                if launcher.reorder_mode.move_left():
                    return
            elif key == Qt.Key.Key_Right:
                if launcher.reorder_mode.move_right():
                    return
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if launcher.reorder_mode.confirm_reorder():
                    return
            elif key == Qt.Key.Key_Escape:
                if launcher.reorder_mode.cancel_reorder():
                    return
        else:
            # Определение длинного нажатия для клавиши Enter (только если не в меню/диалоге)
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not launcher.is_in_menu and not launcher.reorder_mode._is_dialog_active():
                    launcher.reorder_mode.start_long_press()
        
        # Передача исходному обработчику
        original_key_press(event)
    
    # Сохранение исходного keyReleaseEvent, если он существует
    original_key_release = getattr(launcher, 'keyReleaseEvent', None)
    
    def enhanced_key_release(event):
        """Улучшенный keyReleaseEvent для определения длинного нажатия"""
        if event.isAutoRepeat():
            return
        
        key = event.key()
        
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not launcher.reorder_mode.is_active:
                launcher.reorder_mode.cancel_long_press()
        
        if original_key_release:
            original_key_release(event)
    
    # Сохранение исходного launch_current_app для отмены таймеров
    original_launch = launcher.launch_current_app
    launcher.reorder_active = False
    launcher.reorder_original_index = 0
    launcher.reorder_overlay = None
    
    # Сохранение исходного метода keyPressEvent
    original_key_press = launcher.keyPressEvent
    
    def enhanced_launch():
        """Улучшенный запуск, который отменяет все таймеры сортировки"""
        # Принудительная отмена любого ожидающего активирования сортировки
        launcher.reorder_mode.force_cancel_all_timers()
        launcher.reorder_mode.recently_exited = False
        # Вызов исходного запуска
        original_launch()
    
    launcher.launch_current_app = enhanced_launch
    
    # Сохранение исходного handle_button
    original_handle_button = getattr(launcher, 'handle_button', lambda button_index: None)

    def enhanced_handle_button(button_index):
        """Улучшенный обработчик кнопок с поддержкой сортировки"""
        # КРИТИЧЕСКИ ВАЖНО: Блокировка всей обработки кнопок во время задержки
        if launcher.reorder_mode.recently_exited:
            return
        
        # В режиме сортировки специальная обработка кнопок A и B
        if launcher.reorder_mode.is_active:
            if button_index == 0:  # Кнопка A — подтвердить сортировку
                print("✅ Нажата кнопка A в режиме сортировки — подтверждение")
                launcher.reorder_mode.confirm_reorder()
                return  # Не передавать исходному обработчику
            elif button_index == 1:  # Кнопка B — отменить сортировку
                print("❌ Нажата кнопка B в режиме сортировки — отмена")
                launcher.reorder_mode.cancel_reorder()
                return  # Не передавать исходному обработчику
        
        # Кнопка RB (кнопка 5) переключает режим сортировки
        if launcher.reorder_mode.handle_joypad_button(button_index):
            return
        
        # Передача исходному обработчику, если не обработано режимом сортировки
        original_handle_button(button_index)
    
    # Сохранение исходного handle_navigation и его улучшение для поддержки контроллера в режиме сортировки
    if hasattr(launcher, 'handle_navigation'):
        original_handle_navigation = launcher.handle_navigation
        
        def enhanced_handle_navigation(direction):
            """Улучшенный обработчик навигации с поддержкой сортировки"""
            if launcher.reorder_mode.is_active:
                if direction == "left":
                    return launcher.reorder_mode.move_left()
                elif direction == "right":
                    return launcher.reorder_mode.move_right()
                return False
            else:
                original_handle_navigation(direction)
        
        launcher.handle_navigation = enhanced_handle_navigation
    
    # Замена методов
    launcher.keyPressEvent = enhanced_key_press
    launcher.keyReleaseEvent = enhanced_key_release
    launcher.handle_button = enhanced_handle_button
    
    # Обновление метки инструкций
    if hasattr(launcher, 'findChild'):
        instructions = launcher.findChildren(QLabel)
        for label in instructions:
            if "Navigate:" in label.text() or "Навигация:" in label.text():
                label.setText(
                    "Навигация: ← → ↑ ↓ | Запуск: Enter/A | Изменить: E/X | Удалить: Del/Y | "
                    "Настройки: S/Start | Сортировка: R/RB | Поиск: F/LB | Выход: Esc/B"
                )
                label.setStyleSheet(f"""
                        color: rgba(255, 255, 255, 0.3);
                        font-size: {launcher.scaling.scale_font(11)}px;
                        background: transparent;
                    """)
                break

