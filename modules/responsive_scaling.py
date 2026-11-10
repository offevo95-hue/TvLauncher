"""
Модуль адаптивного масштабирования (Responsive Scaling Module)
Управление адаптивным изменением размеров на основе разрешения экрана
"""
import platform
from PyQt6.QtWidgets import QApplication


class ResponsiveScaling:
    """Адаптивное масштабирование на основе разрешения экрана"""
   
    def __init__(self):
        # Базовое разрешение 
        self.BASE_WIDTH = 1920
        self.BASE_HEIGHT = 1080
       
        screen = QApplication.primaryScreen()
        geometry = screen.geometry()
        self.screen_width = geometry.width()
        self.screen_height = geometry.height()
        dpr = screen.devicePixelRatio()

        
        if platform.system() == "Windows":
            physical_width = self.screen_width
            physical_height = self.screen_height
        else:
            physical_width = self.screen_width * dpr
            physical_height = self.screen_height * dpr

        width_scale = physical_width / self.BASE_WIDTH
        height_scale = physical_height / self.BASE_HEIGHT
       
        
        self.scale_factor = min(width_scale, height_scale)
       
        print(f"📐 Экран: {self.screen_width}x{self.screen_height} (логические)")
        print(f"📐 Физические размеры: {int(physical_width)}x{int(physical_height)} (DPR: {dpr})")
        print(f"📐 Коэффициент масштабирования: {self.scale_factor:.2f}")
   
    def scale(self, value):
        """Масштабирование значения в зависимости от разрешения"""
        return int(value * self.scale_factor)
   
    def scale_font(self, base_size):
        """Масштабирование размера шрифта"""
        return int(base_size * self.scale_factor)

