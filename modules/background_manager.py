import os
import random
from pathlib import Path
from PyQt6.QtWidgets import QLabel, QFileDialog, QApplication, QGraphicsOpacityEffect
from PyQt6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, Qt
from PyQt6.QtGui import QPixmap, QBrush


class BackgroundManager:
    """Управление фоном, анимациями и автоматической сменой обоев"""
    
    def __init__(self, parent, config_data, assets_dir):
        """
        Инициализация менеджреа фона
        
        Args:
            parent: Главное окно (TVLauncher)
            config_data: Словарь с конфигурацией (background, auto_change_wallpaper)
            assets_dir: Путь к папке активов (assets)
        """
        self.parent = parent
        self.assets_dir = Path(assets_dir)
        
        # Конфигурация
        self.background_image = config_data.get('background', '')
        self.auto_change_wallpaper = config_data.get('auto_change_wallpaper', False)
        self.wallpaper_interval = 300000  # 3 минуты по умолчанию (в миллисекундах)
        
        # Папка с обоями
        self.wallpaper_folder = self.assets_dir / 'wallpapers'
        self.wallpaper_folder.mkdir(parents=True, exist_ok=True)
        
        # Анимации
        self.fade_widget = None
        self.fade_animation = None
        self.pending_background = None
        
        # Таймер для автосмены
        self.wallpaper_timer = None
        
    def initialize(self, overlay=None):
        """
        Инициализация фона
        
        Args:
            overlay: Виджет оверлея для учета порядка отрисовки (z-order)
        """
        self.overlay = overlay
        self.update_background(fade=False)
        
        # Запуск автосмены, если она включена
        if self.auto_change_wallpaper:
            self.start_wallpaper_rotation()
    
    def update_background(self, fade=False):
        """
        Обновление фонового изображения окна
        
        Args:
            fade: Если True, применяется плавная анимация затухания (fade)
        """
        if self.background_image and Path(self.background_image).exists():
            if fade:
                self._fade_to_background(self.background_image)
            else:
                self._set_scaled_background(self.background_image)
        else:
            # По умолчанию: использование фона из папки assets/wallpapers
            default_wallpaper = self.wallpaper_folder / 'default.jpg'
            if default_wallpaper.exists():
                if fade:
                    self._fade_to_background(str(default_wallpaper))
                else:
                    self._set_scaled_background(str(default_wallpaper))
            else:
                # Резервный вариант (fallback): темно-серый фон
                self._set_fallback_background()
    
    def _set_fallback_background(self):
        """Применение резервного фона при отсутствии изображений"""
        self.parent.setStyleSheet("""
            QMainWindow {
                background-color: #2a2a2a;
            }
        """)
        if self.overlay:
            self.overlay.setStyleSheet("background-color: transparent;")

    # ==================== КООРДИНАЦИЯ С ВИДЕООБОЯМИ ====================
    #
    # Когда видеообои активны, не должно быть НИКАКИХ статических изображений:
    # видео занимает ровно тот же «слой» (отрисовку фона QMainWindow), а не отдельный слой,
    # конкурирующий с ним по z-порядку. Видеовиджет (QWindowContainer, lower()) всегда
    # отрисовывается поверх фоновой заливки окна и ПОД дочерними виджетами верхнего уровня
    # (плитками/меню) в соответствии со стандартной моделью рисования Qt — поэтому здесь
    # просто не должно быть никаких картинок, «засоряющих» это пространство.

    def suspend_for_video(self):
        """Приостановка статического фона на время работы видеообоев.

        Видео представляет собой дочерний QLabel для QMainWindow (тот же механизм,
        что и статический fade_widget), а не отдельное окно: без прозрачности окна,
        без хаков DWM. Здесь достаточно просто убрать статическую картинку.
        """
        self.stop_wallpaper_rotation()
        if self.fade_animation and self.fade_animation.state() == QPropertyAnimation.State.Running:
            self.fade_animation.stop()
        if self.fade_widget:
            self.fade_widget.hide()

    def resume_after_video(self):
        """Восстановление статического фона (с эффектом fade) после отключения
        видеообоев."""
        self.update_background(fade=True)
        if self.auto_change_wallpaper:
            self.start_wallpaper_rotation()
    
    def _fade_to_background(self, image_path):
        """
        Плавный переход к новому фону (эффект fade)
        
        Args:
            image_path: Путь к загружаемому изображению
        """
        # Если переход уже выполняется, завершить его немедленно
        if self.fade_animation and self.fade_animation.state() == QPropertyAnimation.State.Running:
            self.fade_animation.stop()
            if self.fade_widget:
                self.fade_widget.deleteLater()
                self.fade_widget = None
        
        # Создание виджета для нового фона
        screen = QApplication.primaryScreen().geometry()
        self.fade_widget = QLabel(self.parent)
        self.fade_widget.setGeometry(0, 0, screen.width(), screen.height())
        self.fade_widget.setScaledContents(True)
        
        # Загрузка и масштабирование изображения
        pixmap = QPixmap(image_path)
        scaled_pixmap = self._scale_pixmap_to_screen(pixmap, screen)
        self.fade_widget.setPixmap(scaled_pixmap)
        
        # Размещение под оверлеем, но поверх основного фона
        self.fade_widget.lower()
        if self.overlay:
            self.fade_widget.stackUnder(self.overlay)
        
        # Создание эффекта прозрачности
        opacity_effect = QGraphicsOpacityEffect()
        opacity_effect.setOpacity(0)
        self.fade_widget.setGraphicsEffect(opacity_effect)
        
        self.fade_widget.show()
        
        # Сохранение пути для применения после завершения анимации
        self.pending_background = image_path
        
        # Анимация прозрачности от 0 до 1
        self.fade_animation = QPropertyAnimation(opacity_effect, b"opacity")
        self.fade_animation.setDuration(800)  # 800мс — плавная растворяющаяся анимация
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Применение реального фона по окончании анимации
        self.fade_animation.finished.connect(self._on_fade_finished)
        self.fade_animation.start()
    
    def _on_fade_finished(self):
        """Вызывается по завершении анимации перехода"""
        # Применение настоящего фона
        if self.pending_background:
            self._set_scaled_background(self.pending_background)
            self.pending_background = None
        
        # Удаление вспомогательного виджета перехода
        if self.fade_widget:
            self.fade_widget.deleteLater()
            self.fade_widget = None
        
        self.fade_animation = None
    
    def _set_scaled_background(self, image_path):
        """
        Установка масштабированного фона для заполнения окна
        
        Args:
            image_path: Путь к изображению
        """
        screen = QApplication.primaryScreen().geometry()
        pixmap = QPixmap(image_path)
        
        # Масштабирование пиксмапа для заполнения экрана
        scaled_pixmap = self._scale_pixmap_to_screen(pixmap, screen)
        
        # Установка фона через QPalette
        palette = self.parent.palette()
        brush = QBrush(scaled_pixmap)
        palette.setBrush(self.parent.backgroundRole(), brush)
        self.parent.setPalette(palette)
        
        # Применение темного оверлея для улучшения читаемости
        if self.overlay:
            self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.3);")
    
    def _scale_pixmap_to_screen(self, pixmap, screen):
        """
        Масштабирование изображения под размер экрана (режим cover)
        
        Args:
            pixmap: QPixmap для масштабирования
            screen: QRect с размерами экрана
            
        Returns:
            Масштабированный и откадрированный по центру QPixmap
        """
        # Масштабирование с заполнением экрана (эквивалент background-size: cover)
        scaled_pixmap = pixmap.scaled(
            screen.width(), 
            screen.height(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Центрирование изображения, если оно больше экрана
        if scaled_pixmap.width() > screen.width() or scaled_pixmap.height() > screen.height():
            x = (scaled_pixmap.width() - screen.width()) // 2
            y = (scaled_pixmap.height() - screen.height()) // 2
            scaled_pixmap = scaled_pixmap.copy(x, y, screen.width(), screen.height())
        
        return scaled_pixmap
    
    # ==================== УПРАВЛЕНИЕ ОБОЯМИ ====================
    
    def set_background_from_dialog(self):
        """
        Открытие диалогового окна для ручного выбора фона
        
        Returns:
            bool: True, если фон был изменен, иначе False
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent,
            "Выбрать фоновое изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.bmp);;Все файлы (*.*)"
        )
        
        if file_path:
            self.background_image = file_path
            
            # Отключение автосмены при ручном выборе фона
            if self.auto_change_wallpaper:
                self.auto_change_wallpaper = False
                self.stop_wallpaper_rotation()
                
            self.update_background(fade=True)
            return True
        
        return False
    
    def start_wallpaper_rotation(self):
        """Запуск таймера для автоматической смены фоновых изображений"""
        if not self.auto_change_wallpaper:
            return
            
        # Смена изображения сразу с эффектом fade
        self.change_random_wallpaper()
        
        # Запуск таймера
        self.wallpaper_timer = QTimer()
        self.wallpaper_timer.timeout.connect(self.change_random_wallpaper)
        self.wallpaper_timer.start(self.wallpaper_interval)
        
    def stop_wallpaper_rotation(self):
        """Остановка таймера автоматической смены обоев"""
        if self.wallpaper_timer:
            self.wallpaper_timer.stop()
            self.wallpaper_timer = None
            
    def change_random_wallpaper(self):
        """Смена фона на случайный из папки"""
        if not self.wallpaper_folder.exists():
            print(f"⚠️ Папка с обоями не найдена: {self.wallpaper_folder}")
            return
        
        # Поиск всех файлов изображений
        wallpapers = (
            list(self.wallpaper_folder.glob("*.jpg")) + 
            list(self.wallpaper_folder.glob("*.png")) + 
            list(self.wallpaper_folder.glob("*.jpeg"))
        )
        
        if not wallpapers:
            print(f"⚠️ Обои не найдены в папке {self.wallpaper_folder}")
            return
        
        # Выбор случайного фона (по возможности исключая текущий)
        if len(wallpapers) > 1 and self.background_image:
            current = Path(self.background_image)
            wallpapers = [w for w in wallpapers if w != current]
        
        random_wallpaper = random.choice(wallpapers)
        
        # Установка фона с эффектом fade
        self.background_image = str(random_wallpaper)
        self.update_background(fade=True)
        
    def toggle_wallpaper_rotation(self, enabled):
        """
        Включение/выключение автоматической смены обоев
        
        Args:
            enabled: True для включения, False для выключения
        """
        self.auto_change_wallpaper = enabled
        
        if enabled:
            self.start_wallpaper_rotation()
        else:
            self.stop_wallpaper_rotation()
    
    def set_wallpaper_interval(self, interval_seconds):
        """
        Установка интервала смены обоев
        
        Args:
            interval_seconds: Интервал в секундах
        """
        self.wallpaper_interval = interval_seconds * 1000  # Конвертация в миллисекунды
        
        # Перезапуск таймера, если он активен
        if self.wallpaper_timer and self.wallpaper_timer.isActive():
            self.stop_wallpaper_rotation()
            self.start_wallpaper_rotation()
    
    # ==================== КОНФИГУРАЦИЯ ====================
    
    def get_config(self):
        """
        Получение текущей конфигурации
        
        Returns:
            dict: Словарь с конфигурацией фона
        """
        return {
            'background': self.background_image,
            'auto_change_wallpaper': self.auto_change_wallpaper,
            'wallpaper_interval': self.wallpaper_interval
        }
    
    def load_config(self, config_data):
        """
        Загрузка конфигурации
        
        Args:
            config_data: Словарь с конфигурацией
        """
        self.background_image = config_data.get('background', '')
        self.auto_change_wallpaper = config_data.get('auto_change_wallpaper', False)
        self.wallpaper_interval = config_data.get('wallpaper_interval', 180000)
    
    # ==================== ОЧИСТКА РЕСУРСОВ ====================
    
    def cleanup(self):
        """Очистка ресурсов при закрытии приложения"""
        self.stop_wallpaper_rotation()
        
        # Остановка выполняющихся анимаций
        if self.fade_animation and self.fade_animation.state() == QPropertyAnimation.State.Running:
            self.fade_animation.stop()
        
        # Удаление виджета затухания
        if self.fade_widget:
            self.fade_widget.deleteLater()
            self.fade_widget = None


# ==================== ФУНКЦИИ ИНТЕГРАЦИИ ====================

def integrate_background_manager(launcher_class):
    """
    Интеграция BackgroundManager в класс TVLauncher
    
    Args:
        launcher_class: Изменяемый класс TVLauncher
    """
    
    # Сохранение оригинального конструктора __init__
    original_init = launcher_class.__init__
    
    def new_init(self):
        """Новый метод __init__ с инициализацией BackgroundManager"""
        # Вызов оригинального init
        original_init(self)
        
        # Инициализация BackgroundManager
        from modules.background_manager import BackgroundManager
        self.background_manager = BackgroundManager(
            parent=self,
            config_data=self.config_data,
            assets_dir=self.assets_dir
        )
        
        # Инициализация фона (вызывается после создания оверлея)
        # self.background_manager.initialize(overlay=self.overlay)
    
    # Подмена методов класса
    launcher_class.__init__ = new_init
    launcher_class.set_background = lambda self: self.background_manager.set_background_from_dialog()
    launcher_class.update_background = lambda self, fade=False: self.background_manager.update_background(fade)
    launcher_class.start_wallpaper_rotation = lambda self: self.background_manager.start_wallpaper_rotation()
    launcher_class.stop_wallpaper_rotation = lambda self: self.background_manager.stop_wallpaper_rotation()
    launcher_class.change_random_wallpaper = lambda self: self.background_manager.change_random_wallpaper()
    launcher_class.toggle_wallpaper_rotation = lambda self, enabled: self.background_manager.toggle_wallpaper_rotation(enabled)
    
    # Добавление очистки ресурсов в closeEvent
    original_close = launcher_class.closeEvent if hasattr(launcher_class, 'closeEvent') else None
    
    def new_close_event(self, event):
        """Очистка перед закрытием приложения"""
        if hasattr(self, 'background_manager'):
            self.background_manager.cleanup()
        
        if original_close:
            original_close(self, event)
        else:
            event.accept()
    
    launcher_class.closeEvent = new_close_event

