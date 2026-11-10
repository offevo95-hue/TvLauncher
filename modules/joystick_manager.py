"""
Модуль для полной утилизации джойстика
Управление инициализацией, опросом, сопоставлением кнопок и уведомлениями
"""

from PyQt6.QtCore import QTimer, Qt, QCoreApplication
from PyQt6.QtGui import QKeyEvent
import pygame

try:
    import pygame
    JOYSTICK_AVAILABLE = True
except ImportError:
    JOYSTICK_AVAILABLE = False
    print("Предупреждение: библиотека pygame не установлена. Поддержка джойстиков отключена.")


class JoystickManager:
    """Управление всеми функциями джойстика"""
    
    def __init__(self, parent, scaling):
        self.parent = parent
        self.scaling = scaling
        self.joystick = None
        self.joystick_timer = None
        self.joystick_detection_timer = None
        self.joystick_notification = None
        
        # Конфигурация мертвой зоны и задержки (cooldown)
        self.axis_deadzone = 0.2
        self.button_cooldown = {}
        self.axis_cooldown = 0
        self._category_selector_enabled = False
        self._category_open_last_y = (False, 0, False)
        self._category_selector_last_x = (False, False, 0, False, False)
        self._category_selector_last_y = (False, 0, False)
        self._category_selector_last_b = False
        # Состояния осей для определения изменений
        self.last_axis_state = {'x': 0, 'y': 0}
        self.last_hat = (0, 0)
        
        # Состояния для различных меню (предотвращение повторов)
        self._menu_last_state = (False, False, 0, False, False)
        self._reorder_last_x = (False, False, 0, False, False)
        self._exit_dialog_last_x = (False, False, 0, False, False)
        self._search_last_state = (False, False, 0, False, False)
        self._category_dialog_last_state = (False, False, 0, False, False)
        self._bottom_menu_last_x = (False, False, 0, False, False)
        self._bottom_menu_last_y = (False, 0, False)
        self._carousel_last_x = (False, False, 0, False, False)
        self._carousel_last_y = (False, False, 0, False, False)
        self._pc_last_state = (False, False, 0, False, False)
        self._pc_last_x     = (False, False, 0, False, False)
        
        if JOYSTICK_AVAILABLE:
            pygame.init()
            self.init_joystick()
            self.start_detection_timer()

    def register_category_support(self, launcher):
        """Регистрация селектора категорий для поддержки джойстика"""
        self._category_selector_enabled = True
        

    def init_joystick(self):
        """Инициализация джойстика, если он доступен"""
        try:
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                
                # Отображение уведомления о подключении
                from modules.joystick_notification import show_joystick_connected
                self.joystick_notification = show_joystick_connected(
                    self.parent, 
                    self.joystick.get_name(), 
                    self.scaling
                )
                
                print(f"🎮 Джойстик подключен: {self.joystick.get_name()}")
                
                # Установка джойстика в менеджере громкости
                if hasattr(self.parent, 'volume_manager') and self.parent.volume_manager:
                    self.parent.volume_manager.set_joystick(self.joystick)
                
                # Запуск опроса
                self.joystick_timer = QTimer()
                self.joystick_timer.timeout.connect(self.poll_joystick)
                self.joystick_timer.start(12)  # ~83 Гц
                
        except Exception as e:
            print(f"❌ Ошибка инициализации джойстика: {e}")
    
    def start_detection_timer(self):
        """Запуск таймера для отслеживания подключений/отключений"""
        self.joystick_detection_timer = QTimer()
        self.joystick_detection_timer.timeout.connect(self.detect_joystick)
        self.joystick_detection_timer.start(5000)  # Проверка каждые 5 секунд
    
    def detect_joystick(self):
        """Определение подключения/отключения джойстика"""
        try:
            pygame.joystick.init()
            count = pygame.joystick.get_count()
            
            if count > 0 and self.joystick is None:
                # Джойстик подключен после запуска
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                
                from modules.joystick_notification import show_joystick_connected
                self.joystick_notification = show_joystick_connected(
                    self.parent, 
                    self.joystick.get_name(), 
                    self.scaling
                )
                
                print(f"🎮 Джойстик подключен (позднее обнаружение): {self.joystick.get_name()}")
                
                if self.joystick_timer is None:
                    self.joystick_timer = QTimer()
                    self.joystick_timer.timeout.connect(self.poll_joystick)
                    self.joystick_timer.start(12)
                
                if hasattr(self.parent, 'volume_manager') and self.parent.volume_manager:
                    self.parent.volume_manager.set_joystick(self.joystick)
                    
            elif count == 0 and self.joystick is not None:
                # Джойстик отключен
                print("🔌 Джойстик отключен")
                
                from modules.joystick_notification import show_joystick_disconnected
                self.joystick_notification = show_joystick_disconnected(
                    self.parent, 
                    self.scaling
                )
                
                if self.joystick_timer:
                    self.joystick_timer.stop()
                    self.joystick_timer = None
                
                self.joystick.quit()
                self.joystick = None
                
                if hasattr(self.parent, 'volume_manager') and self.parent.volume_manager:
                    self.parent.volume_manager.set_joystick(None)
                    
        except Exception as e:
            print(f"⚠️ Ошибка при обнаружении джойстика: {e}")
            if self.joystick is not None:
                if self.joystick_timer:
                    self.joystick_timer.stop()
                    self.joystick_timer = None
                self.joystick = None
                
                if hasattr(self.parent, 'volume_manager') and self.parent.volume_manager:
                    self.parent.volume_manager.set_joystick(None)
    
    def poll_joystick(self):
        """Основной опрос джойстика — распределяет по соответствующим обработчикам"""
        if not self.joystick:
            return
        
        try:
            # Проверка режима регулировки громкости 
            if hasattr(self.parent, 'volume_manager') and \
               self.parent.volume_manager and \
               self.parent.volume_manager.volume_mode_active:
                for event in pygame.event.get():
                    pass  # Обработка событий
                return
            
            # Поглощение событий pygame
            for event in pygame.event.get():
                pass
            
            # Проверка, что джойстик все еще активен
            if not pygame.joystick.get_init() or pygame.joystick.get_count() == 0:
                raise pygame.error("Система джойстиков не готова или устройство отсутствует")
            
            # Распределение по обработчикам в порядке приоритета
            if self._handle_parental_control():
                return

            if self._handle_settings_menu():
                return
            
            if not self.parent.inputs_enabled:
                return
            
            if self._handle_reorder_mode():
                return
            # Управление селектором категорий, если он включен и открыт
            if self._category_selector_enabled and \
                hasattr(self.parent, 'is_in_category_selector') and \
                self.parent.is_in_category_selector:
                    self._handle_category_selector()
                    return

            if self._handle_exit_dialog():
                return
            
            if self._handle_quick_search():
                return
            
            if self._handle_category_dialog():
                return
            
            if self._handle_bottom_menu():
                return
            
            # Основной обработчик навигации по карусели
            self._handle_carousel_navigation()
            self._handle_main_buttons()
            
        except (pygame.error, AttributeError, ValueError) as e:
            print(f"⚠️ Потеряно соединение с джойстиком: {e}")
            self._handle_disconnection()
        except Exception as e:
            print(f"⚠️ Непредвиденная ошибка при опросе джойстика: {e}")
    
    def _handle_parental_control(self):
        """Обработка ввода с джойстика при активном диалоговом окне родительского контроля.
        Должен быть первым обработчиком — блокирует все остальное, пока диалог открыт."""
        # Способ 1: явный флаг в лаунчере (надежно на Linux с FramelessWindowHint)
        # Способ 2: activeWindow() — запасной вариант для Windows, где это работает корректно
        active_via_flag = getattr(self.parent, 'parental_control_dialog_active', False)
        if not active_via_flag:
            from PyQt6.QtWidgets import QDialog
            active = QCoreApplication.instance().activeWindow()
            if not isinstance(active, QDialog):
                return False
            if not any(c.__name__ in ("PinEntryDialog", "PinRecoveryDialog", "PinSetupDialog")
                       for c in type(active).__mro__):
                return False

        hat      = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        y_axis   = self.joystick.get_axis(1)
        x_axis   = self.joystick.get_axis(0)
        dpad_up    = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
        dpad_down  = self.joystick.get_button(12) if self.joystick.get_numbuttons() > 12 else False
        dpad_left  = self.joystick.get_button(13) if self.joystick.get_numbuttons() > 13 else False
        dpad_right = self.joystick.get_button(14) if self.joystick.get_numbuttons() > 14 else False

        # Вверх / Вниз — навигация по цифровой клавиатуре или списку
        if (y_axis < -self.axis_deadzone and not self._pc_last_state[0]) or \
           (hat[1] == 1 and self._pc_last_state[2] != 1) or \
           (dpad_up and not self._pc_last_state[3]):
            self._simulate_key(Qt.Key.Key_Up)
        elif (y_axis > self.axis_deadzone and not self._pc_last_state[1]) or \
             (hat[1] == -1 and self._pc_last_state[2] != -1) or \
             (dpad_down and not self._pc_last_state[4]):
            self._simulate_key(Qt.Key.Key_Down)

        # Влево / Вправо — навигация по кнопкам в диалоге восстановления
        if (x_axis < -self.axis_deadzone and not self._pc_last_x[0]) or \
           (hat[0] == -1 and self._pc_last_x[2] != -1) or \
           (dpad_left and not self._pc_last_x[3]):
            self._simulate_key(Qt.Key.Key_Left)
        elif (x_axis > self.axis_deadzone and not self._pc_last_x[1]) or \
             (hat[0] == 1 and self._pc_last_x[2] != 1) or \
             (dpad_right and not self._pc_last_x[4]):
            self._simulate_key(Qt.Key.Key_Right)

        self._pc_last_state = (y_axis < -self.axis_deadzone, y_axis > self.axis_deadzone,
                               hat[1], dpad_up, dpad_down)
        self._pc_last_x     = (x_axis < -self.axis_deadzone, x_axis > self.axis_deadzone,
                               hat[0], dpad_left, dpad_right)

        # Кнопки: A (0) = Подтвердить, B (1) или X (2) = Отмена/Escape
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i) and self._check_button_cooldown(i):
                if i == 0:
                    self._simulate_key(Qt.Key.Key_Return)
                elif i in (1, 2):
                    self._simulate_key(Qt.Key.Key_Escape)

        return True  # Блокировка всех остальных обработчиков

    def _handle_settings_menu(self):
        """Управление навигацией в меню настроек"""
        if not (hasattr(self.parent, 'settings_menu') and 
                getattr(self.parent.settings_menu, 'is_open', False)):
            self._menu_last_state = (False, False, 0, False, False)
            return False
        
        y_axis = self.joystick.get_axis(1)
        hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        dpad_up = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
        dpad_down = self.joystick.get_button(12) if self.joystick.get_numbuttons() > 12 else False
        
        current_state = (y_axis > self.axis_deadzone, y_axis < -self.axis_deadzone, 
                        hat[1], dpad_down, dpad_up)
        
        # Определение движений
        if y_axis > self.axis_deadzone and not self._menu_last_state[0]:
            self.parent.settings_menu.navigate_down()
        elif y_axis < -self.axis_deadzone and not self._menu_last_state[1]:
            self.parent.settings_menu.navigate_up()
        elif hat[1] == -1 and self._menu_last_state[2] != -1:
            self.parent.settings_menu.navigate_down()
        elif hat[1] == 1 and self._menu_last_state[2] != 1:
            self.parent.settings_menu.navigate_up()
        elif dpad_down and not self._menu_last_state[3]:
            self.parent.settings_menu.navigate_down()
        elif dpad_up and not self._menu_last_state[4]:
            self.parent.settings_menu.navigate_up()
        
        self._menu_last_state = current_state
        
        # Обработка кнопок
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i) and self._check_button_cooldown(i):
                if i == 0:  # A/Крестик — Активировать
                    self.parent.settings_menu.activate_current()
                elif i in (1, 2, 6, 7, 9):  # Различные кнопки для закрытия
                    self.parent.settings_menu.close_menu()
        
        return True
    
    def _handle_reorder_mode(self):
        """Управление навигацией в режиме изменения порядка (reorder mode)"""
        if not (hasattr(self.parent, 'reorder_active') and self.parent.reorder_active):
            self._reorder_last_x = (False, False, 0, False, False)
            return False
        
        x_axis = self.joystick.get_axis(0)
        hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        dpad_left = self.joystick.get_button(13) if self.joystick.get_numbuttons() > 13 else False
        dpad_right = self.joystick.get_button(14) if self.joystick.get_numbuttons() > 14 else False
        
        current_state_x = (x_axis > self.axis_deadzone, x_axis < -self.axis_deadzone,
                          hat[0], dpad_right, dpad_left)
        
        if x_axis > self.axis_deadzone and not self._reorder_last_x[0]:
            self._simulate_key(Qt.Key.Key_Right)
        elif x_axis < -self.axis_deadzone and not self._reorder_last_x[1]:
            self._simulate_key(Qt.Key.Key_Left)
        elif hat[0] == 1 and self._reorder_last_x[2] != 1:
            self._simulate_key(Qt.Key.Key_Right)
        elif hat[0] == -1 and self._reorder_last_x[2] != -1:
            self._simulate_key(Qt.Key.Key_Left)
        elif dpad_right and not self._reorder_last_x[3]:
            self._simulate_key(Qt.Key.Key_Right)
        elif dpad_left and not self._reorder_last_x[4]:
            self._simulate_key(Qt.Key.Key_Left)
        
        self._reorder_last_x = current_state_x
        
        # Кнопки
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i) and self._check_button_cooldown(i):
                if i == 0:
                    self._simulate_key(Qt.Key.Key_Return)
                elif i in (1, 2):
                    self._simulate_key(Qt.Key.Key_Escape)
        
        return True

        
    
    def _handle_exit_dialog(self):
        """Управление диалоговым окном подтверждения выхода"""
        if not (hasattr(self.parent, '_exit_dialog_active') and self.parent._exit_dialog_active):
            self._exit_dialog_last_x = (False, False, 0, False, False)
            return False
        
        x_axis = self.joystick.get_axis(0)
        hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        dpad_left = self.joystick.get_button(13) if self.joystick.get_numbuttons() > 13 else False
        dpad_right = self.joystick.get_button(14) if self.joystick.get_numbuttons() > 14 else False
        
        current_state_x = (x_axis > self.axis_deadzone, x_axis < -self.axis_deadzone,
                          hat[0], dpad_right, dpad_left)
        
        if (x_axis > self.axis_deadzone and not self._exit_dialog_last_x[0]) or \
           (hat[0] == 1 and self._exit_dialog_last_x[2] != 1) or \
           (dpad_right and not self._exit_dialog_last_x[3]):
            self._simulate_key(Qt.Key.Key_Right)
        elif (x_axis < -self.axis_deadzone and not self._exit_dialog_last_x[1]) or \
             (hat[0] == -1 and self._exit_dialog_last_x[2] != -1) or \
             (dpad_left and not self._exit_dialog_last_x[4]):
            self._simulate_key(Qt.Key.Key_Left)
        
        self._exit_dialog_last_x = current_state_x
        
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i) and self._check_button_cooldown(i):
                if i == 0:
                    self._simulate_key(Qt.Key.Key_Return)
                elif i in (1, 2):
                    self._simulate_key(Qt.Key.Key_Escape)
        
        return True
    
    def _handle_quick_search(self):
        """Управление навигацией быстрого поиска"""
        if not (hasattr(self.parent, 'quick_search') and self.parent.quick_search.isVisible()):
            self._search_last_state = (False, False, 0, False, False)
            return False
        
        y_axis = self.joystick.get_axis(1)
        hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        dpad_up = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
        dpad_down = self.joystick.get_button(12) if self.joystick.get_numbuttons() > 12 else False
        
        current_state = (y_axis > self.axis_deadzone, y_axis < -self.axis_deadzone,
                        hat[1], dpad_down, dpad_up)
        
        if (y_axis > self.axis_deadzone and not self._search_last_state[0]) or \
           (hat[1] == -1 and self._search_last_state[2] != -1) or \
           (dpad_down and not self._search_last_state[3]):
            self.parent.quick_search.handle_joypad_input(Qt.Key.Key_Down)
        elif (y_axis < -self.axis_deadzone and not self._search_last_state[1]) or \
             (hat[1] == 1 and self._search_last_state[2] != 1) or \
             (dpad_up and not self._search_last_state[4]):
            self.parent.quick_search.handle_joypad_input(Qt.Key.Key_Up)
        
        self._search_last_state = current_state
        
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i) and self._check_button_cooldown(i):
                if i == 0:
                    self.parent.quick_search.handle_joypad_input(Qt.Key.Key_Return)
                elif i == 1:
                    self.parent.quick_search.handle_joypad_input(Qt.Key.Key_Escape)
                elif i == 2:
                    self.parent.quick_search.handle_joypad_input(Qt.Key.Key_E)
        
        return True
    
    def _handle_category_dialog(self):
        """Управление навигацией в диалоге категорий"""
        if not (hasattr(self.parent, '_category_dialog_open') and self.parent._category_dialog_open):
            self._category_dialog_last_state = (False, False, 0, False, False)
            return False
        
        y_axis = self.joystick.get_axis(1)
        hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        dpad_up = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
        dpad_down = self.joystick.get_button(12) if self.joystick.get_numbuttons() > 12 else False
        
        current_state = (y_axis > self.axis_deadzone, y_axis < -self.axis_deadzone,
                        hat[1], dpad_down, dpad_up)
        
        if (y_axis > self.axis_deadzone and not self._category_dialog_last_state[0]) or \
           (hat[1] == -1 and self._category_dialog_last_state[2] != -1) or \
           (dpad_down and not self._category_dialog_last_state[3]):
            self._simulate_key(Qt.Key.Key_Down)
        elif (y_axis < -self.axis_deadzone and not self._category_dialog_last_state[1]) or \
             (hat[1] == 1 and self._category_dialog_last_state[2] != 1) or \
             (dpad_up and not self._category_dialog_last_state[4]):
            self._simulate_key(Qt.Key.Key_Up)
        
        self._category_dialog_last_state = current_state
        
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i) and self._check_button_cooldown(i):
                if i == 0:
                    self._simulate_key(Qt.Key.Key_Return)
                elif i in (1, 2):
                    self._simulate_key(Qt.Key.Key_Escape)
        
        return True
    
    def _handle_bottom_menu(self):
        """Управление нижним меню (перезагрузка / выключение и т.д.)"""
        if not self.parent.is_in_menu:
            self._bottom_menu_last_x = (False, False, 0, False, False)
            self._bottom_menu_last_y = (False, 0, False)
            return False
        
        # Горизонтальная навигация
        x_axis = self.joystick.get_axis(0)
        hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        dpad_left = self.joystick.get_button(13) if self.joystick.get_numbuttons() > 13 else False
        dpad_right = self.joystick.get_button(14) if self.joystick.get_numbuttons() > 14 else False
        
        current_state_x = (x_axis > self.axis_deadzone, x_axis < -self.axis_deadzone,
                        hat[0], dpad_right, dpad_left)
        
        if (x_axis > self.axis_deadzone and not self._bottom_menu_last_x[0]) or \
        (hat[0] == 1 and self._bottom_menu_last_x[2] != 1) or \
        (dpad_right and not self._bottom_menu_last_x[3]):
            self._simulate_key(Qt.Key.Key_Right)
        elif (x_axis < -self.axis_deadzone and not self._bottom_menu_last_x[1]) or \
            (hat[0] == -1 and self._bottom_menu_last_x[2] != -1) or \
            (dpad_left and not self._bottom_menu_last_x[4]):
            self._simulate_key(Qt.Key.Key_Left)
        
        self._bottom_menu_last_x = current_state_x
        
        # Вертикальная навигация (UP для выхода)
        y_axis = self.joystick.get_axis(1)
        hat_y = self.joystick.get_hat(0)[1] if self.joystick.get_numhats() > 0 else 0
        dpad_up = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
        
        current_state_y = (y_axis < -self.axis_deadzone, hat_y, dpad_up)
        
        if (y_axis < -self.axis_deadzone and not self._bottom_menu_last_y[0]) or \
        (hat_y == 1 and self._bottom_menu_last_y[1] != 1) or \
        (dpad_up and not self._bottom_menu_last_y[2]):
            self._simulate_key(Qt.Key.Key_Up)
            
            # Принудительная установка состояния UP во избежание повторного открытия селектора категорий
            self._category_open_last_y = (
                True if (y_axis < -self.axis_deadzone or dpad_up) else False,
                hat_y if hat_y != 0 else 0,
                True if dpad_up else False
            )
        
        self._bottom_menu_last_y = current_state_y
        
        # Кнопки
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i) and self._check_button_cooldown(i):
                if i == 0:
                    self._simulate_key(Qt.Key.Key_Return)
                elif i in (1, 2):
                    self._simulate_key(Qt.Key.Key_Up)
                    
                    # Принудительное обновление состояния также для кнопки B
                    y_axis = self.joystick.get_axis(1)
                    hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
                    dpad_up = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
                    
                    self._category_open_last_y = (
                        True if y_axis < -self.axis_deadzone else False,
                        hat[1] if hat[1] != 0 else 0,
                        True if dpad_up else False
                    )
        
        return True
    
    def _handle_carousel_navigation(self):
        """Управление навигацией в основной карусели"""
        
        # Проверка, должна ли кнопка UP открывать селектор категорий
        if self._category_selector_enabled and \
        not self.parent.is_in_menu and \
        not getattr(self.parent, 'reorder_active', False):
            
            y_axis = self.joystick.get_axis(1)
            hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
            dpad_up = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
            
            current_state_y_up = (y_axis < -self.axis_deadzone, hat[1], dpad_up)
            
            moved_up = (y_axis < -self.axis_deadzone and not self._category_open_last_y[0]) or \
                    (hat[1] == 1 and self._category_open_last_y[1] != 1) or \
                    (dpad_up and not self._category_open_last_y[2])
            
            # Добавление задержки (cooldown) для D-PAD UP (кнопка 11)
            if moved_up and self._check_button_cooldown(11, cooldown_ms=250):
                self.parent.sound_manager.navigate()
                self.parent.is_in_category_selector = True
                self.parent.category_selector.show_animated()
                self._category_open_last_y = current_state_y_up
                return
            
            self._category_open_last_y = current_state_y_up
        
        # Горизонтальная навигация (LEFT/RIGHT)
        x_axis = self.joystick.get_axis(0)
        hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        dpad_left = self.joystick.get_button(13) if self.joystick.get_numbuttons() > 13 else False
        dpad_right = self.joystick.get_button(14) if self.joystick.get_numbuttons() > 14 else False
        
        current_state_x = (x_axis > self.axis_deadzone, x_axis < -self.axis_deadzone,
                        hat[0], dpad_right, dpad_left)
        
        moved_right = (x_axis > self.axis_deadzone and not self._carousel_last_x[0]) or \
                    (hat[0] == 1 and self._carousel_last_x[2] != 1) or \
                    (dpad_right and not self._carousel_last_x[3])
        
        moved_left = (x_axis < -self.axis_deadzone and not self._carousel_last_x[1]) or \
                    (hat[0] == -1 and self._carousel_last_x[2] != -1) or \
                    (dpad_left and not self._carousel_last_x[4])
        
        if moved_right and self.parent.apps and not self.parent.is_animating and not self.parent.is_in_menu:
            self._simulate_key(Qt.Key.Key_Right)
        elif moved_left and self.parent.apps and not self.parent.is_animating and not self.parent.is_in_menu:
            self._simulate_key(Qt.Key.Key_Left)
        
        self._carousel_last_x = current_state_x
        
        # Вертикальная навигация (DOWN для нижнего меню)
        y_axis = self.joystick.get_axis(1)
        hat_y = hat[1]
        dpad_up = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
        dpad_down = self.joystick.get_button(12) if self.joystick.get_numbuttons() > 12 else False
        
        current_state_y = (y_axis > self.axis_deadzone, y_axis < -self.axis_deadzone,
                        hat_y, dpad_down, dpad_up)
        
        moved_down = (y_axis > self.axis_deadzone and not self._carousel_last_y[0]) or \
                    (hat_y == -1 and self._carousel_last_y[2] != -1) or \
                    (dpad_down and not self._carousel_last_y[3])
        
        moved_up = (y_axis < -self.axis_deadzone and not self._carousel_last_y[1]) or \
                (hat_y == 1 and self._carousel_last_y[2] != 1) or \
                (dpad_up and not self._carousel_last_y[4])
        
        if moved_down and not self.parent.is_in_menu:
            self._simulate_key(Qt.Key.Key_Down)
        elif moved_up and self.parent.is_in_menu:
            self._simulate_key(Qt.Key.Key_Up)
        
        self._carousel_last_y = current_state_y

    def _handle_category_selector(self):
        """Управление вводом с джойстика в селекторе категорий"""
        # Горизонтальная навигация (LEFT/RIGHT переключает категории)
        x_axis = self.joystick.get_axis(0)
        y_axis = self.joystick.get_axis(1)
        hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        
        dpad_left = self.joystick.get_button(13)
        dpad_right = self.joystick.get_button(14)
        dpad_down = self.joystick.get_button(12)
        
        # Обработка LEFT/RIGHT для смены категории
        current_state_x = (x_axis > self.axis_deadzone, x_axis < -self.axis_deadzone,
                        hat[0], dpad_right, dpad_left)
        
        moved_right = (x_axis > self.axis_deadzone and not self._category_selector_last_x[0]) or \
                    (hat[0] == 1 and self._category_selector_last_x[2] != 1) or \
                    (dpad_right and not self._category_selector_last_x[3])
        
        moved_left = (x_axis < -self.axis_deadzone and not self._category_selector_last_x[1]) or \
                    (hat[0] == -1 and self._category_selector_last_x[2] != -1) or \
                    (dpad_left and not self._category_selector_last_x[4])
        
        if moved_right:
            self.parent.sound_manager.navigate()
            self.parent.category_selector.navigate_right()
        elif moved_left:
            self.parent.sound_manager.navigate()
            self.parent.category_selector.navigate_left()
        
        self._category_selector_last_x = current_state_x
        
        # Вертикальная навигация (DOWN закрывает)
        current_state_y = (y_axis > self.axis_deadzone, hat[1], dpad_down)
        
        moved_down = (y_axis > self.axis_deadzone and not self._category_selector_last_y[0]) or \
                    (hat[1] == -1 and self._category_selector_last_y[1] != -1) or \
                    (dpad_down and not self._category_selector_last_y[2])
        
        if moved_down:
            self.parent.sound_manager.navigate()
            self._close_category_selector()
            return
        
        self._category_selector_last_y = current_state_y
        
        # Кнопка B (закрытие)
        current_b_state = self.joystick.get_button(1)
        
        if current_b_state and not self._category_selector_last_b:
            self.parent.sound_manager.back()
            self._close_category_selector()
            current_time = pygame.time.get_ticks()
            self.button_cooldown[1] = current_time + 500
            self._category_selector_last_b = True
            return
        
        self._category_selector_last_b = current_b_state
        
        # Поглощение остальных кнопок
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i):
                current_time = pygame.time.get_ticks()
                self.button_cooldown[i] = current_time + 400

    def _close_category_selector(self):
        """Закрытие селектора категорий"""
        from PyQt6.QtCore import QTimer
        
        self.parent.is_in_category_selector = False
        self.parent.category_selector.hide_animated()
        
        # Сброс состояний
        self._category_selector_last_x = (False, False, 0, False, False)
        self._category_selector_last_y = (False, 0, False)
        self._category_selector_last_b = False
        
        # Блокировка всех кнопок на 500 мс
        current_time = pygame.time.get_ticks()
        for i in range(self.joystick.get_numbuttons()):
            self.button_cooldown[i] = current_time + 500
        
        # Принудительная установка состояния DOWN/UP в TRUE для предотвращения повторного срабатывания
        y_axis = self.joystick.get_axis(1)
        hat = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        dpad_up = self.joystick.get_button(11) if self.joystick.get_numbuttons() > 11 else False
        dpad_down = self.joystick.get_button(12) if self.joystick.get_numbuttons() > 12 else False
        
        # Принудительная установка ВСЕХ состояний карусели так, будто они уже нажаты
        self._carousel_last_y = (
            True if (y_axis > self.axis_deadzone or dpad_down) else False,  # DOWN
            True if (y_axis < -self.axis_deadzone or dpad_up) else False,   # UP
            hat[1] if hat[1] != 0 else 0,
            True if dpad_down else False,  # D-PAD DOWN
            True if dpad_up else False     # D-PAD UP
        )
        
        # Принудительная установка состояния для повторного открытия селектора категорий
        self._category_open_last_y = (
            True if (y_axis < -self.axis_deadzone or dpad_up) else False,  # Аналоговый UP
            hat[1] if hat[1] != 0 else 0,                                   # Hat Y
            True if dpad_up else False                                      # D-PAD UP
        )           
            
    def _handle_main_buttons(self):
        """Управление основными кнопками джойстика"""
        for i in range(self.joystick.get_numbuttons()):
            if not self.joystick.get_button(i) or not self._check_button_cooldown(i):
                continue
            
            # Сопоставление кнопок
            if i == 0:  # A/Крестик — Подтвердить
                self._simulate_key(Qt.Key.Key_Return)
            elif i == 1:  # B/Круг — Назад
                self._simulate_key(Qt.Key.Key_Escape)
            elif i == 2:  # X/Квадрат — Быстрая категория
                if not (hasattr(self.parent, 'reorder_active') and self.parent.reorder_active):
                    self._simulate_key(Qt.Key.Key_C)
            elif i == 3:  # Y/Треугольник — Удалить
                self._simulate_key(Qt.Key.Key_Delete)
            elif i == 4:  # LB/L1 — Быстрый поиск
                self._simulate_key(Qt.Key.Key_F)
            elif i == 5:  # RB/R1 — Режим изменения порядка
                self._simulate_key(Qt.Key.Key_R)
            elif i in (6, 7):  # L2/Start — Настройки
                self._open_settings()
            elif i == 9:  # Options (PS4) — Быстрый поиск
                self._simulate_key(Qt.Key.Key_F)
            elif i == 10:  # L3 (PS4) — Режим изменения порядка
                self._simulate_key(Qt.Key.Key_R)
    
    def _check_button_cooldown(self, button_index, cooldown_ms=300):
        """Проверка и обновление задержки (cooldown) кнопок"""
        current_time = pygame.time.get_ticks()
        
        if button_index in self.button_cooldown:
            if current_time - self.button_cooldown[button_index] < cooldown_ms:
                return False
        
        self.button_cooldown[button_index] = current_time
        return True
    
    def _simulate_key(self, key):
        """Симуляция нажатия клавиши"""
        event = QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        active_win = QCoreApplication.instance().activeWindow()
        if active_win:
            QCoreApplication.postEvent(active_win, event)
    
    def _open_settings(self):
        """Открытие меню настроек"""
        try:
            if hasattr(self.parent, 'settings_menu') and self.parent.settings_menu is not None:
                if not getattr(self.parent.settings_menu, 'is_open', False):
                    self.parent.settings_menu.open_menu(self.parent)
        except Exception as e:
            print(f"⚠️ Ошибка открытия настроек: {e}")
    
    def _handle_disconnection(self):
        """Обработка внезапного отключения джойстика"""
        if self.joystick_timer:
            self.joystick_timer.stop()
            self.joystick_timer = None
        
        self.joystick = None
        
        if hasattr(self.parent, 'volume_manager') and self.parent.volume_manager:
            self.parent.volume_manager.set_joystick(None)
        
        from modules.joystick_notification import show_joystick_disconnected
        self.joystick_notification = show_joystick_disconnected(
            self.parent, 
            self.scaling
        )
    
    def cleanup(self):
        """Очистка ресурсов перед закрытием"""
        if self.joystick_timer:
            self.joystick_timer.stop()
        if self.joystick_detection_timer:
            self.joystick_detection_timer.stop()
        if JOYSTICK_AVAILABLE:
            pygame.quit()

