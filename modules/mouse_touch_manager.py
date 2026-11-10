"""
Модуль менеджера мыши и сенсорного ввода (Mouse / Touch Manager)
Добавляет поддержку мыши и сенсорного экрана в лаунчер, не изменяя остальные модули.

Функциональность:
- Клик по несфокусированной плитке -> выбирает её (карусель смещается к ней)
- Клик по уже сфокусированной плитке -> запускает приложение (эквивалент Enter)
- Двойной клик по плитке -> всегда запускает приложение, независимо от текущего фокуса
- Горизонтальное перетаскивание / свайп по карусели (мышью или касанием) -> навигация между приложениями
- Колесико мыши над каруселью -> навигация между приложениями
- Курсор «рука» (pointer) на плитках и кнопках для лучшей визуальной обратной связи
- Нажатия на кнопки меню (перезапуск / сон / выключение / закрытие), работающие по умолчанию
  (QPushButton поддерживает их нативно), здесь им просто назначается курсор-указатель.

Использование в tvlauncher.py:
    from modules.mouse_touch_manager import integrate_mouse_touch
    ...
    self.mouse_touch = integrate_mouse_touch(self)   # вызывать после создания carousel_container и menu_buttons
"""

from PyQt6.QtCore import Qt, QPoint, QEvent
from PyQt6.QtGui import QCursor


# Порог в пикселях, при превышении которого перетаскивание считается свайпом (а не простым кликом)
SWIPE_THRESHOLD = 40


class MouseTouchManager:
    """Добавляет взаимодействие с мышью и сенсорным вводом для карусели и интерфейса лаунчера."""

    def __init__(self, launcher):
        self.launcher = launcher
        self._drag_start_pos = None
        self._drag_start_index = None
        self._dragged = False

        self._patch_build_infinite_carousel()
        self._enable_carousel_drag_and_wheel()
        self._enable_menu_buttons_cursor()

        # Если карусель уже была построена до интеграции, сразу применяем обработчики к плиткам
        if getattr(launcher, "tiles", None):
            self._attach_tile_handlers()

    # ------------------------------------------------------------------
    # Плитки (Tile): клик для выбора / запуска
    # ------------------------------------------------------------------

    def _patch_build_infinite_carousel(self):
        """Обеспечивает автоматическое добавление поддержки мыши для новых плиток
        при каждом перестроении карусели."""
        launcher = self.launcher
        original_build = launcher.build_infinite_carousel

        def patched_build(*args, **kwargs):
            result = original_build(*args, **kwargs)
            self._attach_tile_handlers()
            return result

        launcher.build_infinite_carousel = patched_build

    def _attach_tile_handlers(self):
        launcher = self.launcher
        for tile in launcher.tiles:
            tile.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            # Удаляем предыдущие обработчики перед переназначением
            tile.mousePressEvent = self._make_tile_mouse_press(tile)
            tile.mouseDoubleClickEvent = self._make_tile_double_click(tile)

    def _make_tile_mouse_press(self, tile):
        def handler(event):
            if event.button() != Qt.MouseButton.LeftButton:
                return
            launcher = self.launcher
            if not launcher.inputs_enabled or launcher.is_animating:
                return
            if launcher.progress_dialog and launcher.progress_dialog.isVisible():
                return

            app_index = getattr(tile, "app_index", None)
            if app_index is None:
                return

            # Если открыто меню (фокус на нижних кнопках), клик по плитке
            # возвращает фокус на карусель, на выбранное приложение
            if launcher.is_in_menu:
                launcher.is_in_menu = False
                launcher._reset_menu_styles()

            if app_index == launcher.current_index:
                # Плитка уже выбрана: клик = запуск приложения (как нажатие Enter)
                launcher.sound_manager.select()
                launcher.launch_current_app()
            else:
                # Плитка не выбрана: клик = выбор (как навигация стрелками)
                launcher.sound_manager.navigate()
                launcher.current_index = app_index
                launcher.build_infinite_carousel()

        return handler

    def _make_tile_double_click(self, tile):
        def handler(event):
            if event.button() != Qt.MouseButton.LeftButton:
                return
            launcher = self.launcher
            if not launcher.inputs_enabled or launcher.is_animating:
                return
            app_index = getattr(tile, "app_index", None)
            if app_index is None:
                return
            # Двойной клик: выбирает (если требуется) и сразу запускает, удобно для сенсорных экранов
            if app_index != launcher.current_index:
                launcher.current_index = app_index
                launcher.build_infinite_carousel()
            launcher.sound_manager.select()
            launcher.launch_current_app()

        return handler

    # ------------------------------------------------------------------
    # Карусель: перетаскивание (drag/swipe) и колесико мыши
    # ------------------------------------------------------------------

    def _enable_carousel_drag_and_wheel(self):
        launcher = self.launcher
        container = launcher.carousel_container
        container.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        container.mousePressEvent = self._container_mouse_press
        container.mouseMoveEvent = self._container_mouse_move
        container.mouseReleaseEvent = self._container_mouse_release
        container.wheelEvent = self._container_wheel

    def _container_mouse_press(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_start_pos = event.position() if hasattr(event, "position") else event.pos()
        self._drag_start_index = self.launcher.current_index
        self._dragged = False
        self.launcher.carousel_container.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def _container_mouse_move(self, event):
        if self._drag_start_pos is None:
            return
        current_pos = event.position() if hasattr(event, "position") else event.pos()
        delta_x = current_pos.x() - self._drag_start_pos.x()
        if abs(delta_x) > SWIPE_THRESHOLD:
            self._dragged = True

    def _container_mouse_release(self, event):
        launcher = self.launcher
        launcher.carousel_container.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        if self._drag_start_pos is None:
            return

        current_pos = event.position() if hasattr(event, "position") else event.pos()
        delta_x = current_pos.x() - self._drag_start_pos.x()

        self._drag_start_pos = None

        if not launcher.inputs_enabled or launcher.is_animating:
            return
        if not launcher.apps:
            return

        if abs(delta_x) > SWIPE_THRESHOLD:
            if delta_x < 0:
                self._navigate("right")
            else:
                self._navigate("left")

    def _container_wheel(self, event):
        launcher = self.launcher
        if not launcher.inputs_enabled or launcher.is_animating or not launcher.apps:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.angleDelta().x()
        if delta < 0:
            self._navigate("right")
        elif delta > 0:
            self._navigate("left")

    def _navigate(self, direction):
        """Повторяет логику навигации из keyPressEvent (стрелки влево/вправо)."""
        launcher = self.launcher
        num_apps = len(launcher.apps)
        if num_apps == 0:
            return

        if direction == "right":
            if num_apps <= 5:
                if launcher.current_index < num_apps - 1:
                    launcher.current_index += 1
                    launcher.animate_carousel("right")
            else:
                launcher.current_index = (launcher.current_index + 1) % num_apps
                launcher.animate_carousel("right")
        else:
            if num_apps <= 5:
                if launcher.current_index > 0:
                    launcher.current_index -= 1
                    launcher.animate_carousel("left")
            else:
                launcher.current_index = (launcher.current_index - 1) % num_apps
                launcher.animate_carousel("left")

    # ------------------------------------------------------------------
    # Кнопки меню (перезапуск / сон / выключение / закрытие): только курсор-указатель,
    # клик уже обрабатывается нативно через QPushButton
    # ------------------------------------------------------------------

    def _enable_menu_buttons_cursor(self):
        launcher = self.launcher
        if not hasattr(launcher, "menu_buttons"):
            return
        for _action, btn in launcher.menu_buttons:
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))


def integrate_mouse_touch(launcher):
    """Точка входа, вызываемая в tvlauncher.py после построения пользовательского интерфейса
    (carousel_container и menu_buttons уже должны существовать)."""
    return MouseTouchManager(launcher)

