"""
Модуль менеджера изображений
Управление загрузкой и кэшированием изображений для приложений
"""
import os
from pathlib import Path


try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Предупреждение: библиотека requests не установлена. Онлайн-поиск изображений отключен.")


class ImageManager:
    """Управление загрузкой и кэшированием изображений для приложений"""
    
    def __init__(self, assets_dir="assets", api_key=None, tiles_dir=None):
        self.assets_dir = Path(assets_dir)
        self.assets_dir.mkdir(exist_ok=True)
        self.api_key = api_key
        # Если передан параметр tiles_dir (%APPDATA%\TVLauncher\tiles),
        # скачанные изображения сохраняются туда, а не внутрь папки приложения,
        # благодаря чему они сохраняются при обновлениях.
        if tiles_dir is not None:
            self.tiles_dir = Path(tiles_dir)
            self.tiles_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.tiles_dir = None
        
    def get_app_image(self, app_name, app_path):
        """
        Получение изображения для приложения.
        Сначала поиск в tiles_dir (AppData), затем локально, затем онлайн при необходимости.
        """
        # 1. Поиск в tiles_dir (AppData) — имеет приоритет, переживает обновления
        if self.tiles_dir:
            tile_image = self._find_tile_image(app_name)
            if tile_image:
                return str(tile_image)

        # 2. Поиск локально (в папке assets внутри приложения)
        local_image = self._find_local_image(app_name)
        if local_image:
            return str(local_image)
        
        # 3. Поиск онлайн (если доступен API-ключ и установлена библиотека requests)
        if self.api_key and REQUESTS_AVAILABLE:
            online_image = self._download_from_steamgriddb(app_name)
            if online_image:
                return str(online_image)
        
        # 4. Резервный вариант (fallback): иконка исполняемого файла (exe)
        return app_path if app_path and os.path.exists(app_path) else None
    
    def _find_tile_image(self, app_name):
        """Поиск изображения в tiles_dir (AppData) — плоские файлы, имя = safe_name"""
        safe_name = self._sanitize_filename(app_name)
        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
            image_path = self.tiles_dir / f"{safe_name}{ext}"
            if image_path.exists():
                return image_path
        return None

    def _find_local_image(self, app_name):
        """Поиск изображения в локальной папке активов (assets)"""
        safe_name = self._sanitize_filename(app_name)
        app_folder = self.assets_dir / safe_name
        
        if app_folder.exists():
            for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                image_path = app_folder / f"banner{ext}"
                if image_path.exists():
                    return image_path
                
                image_path = app_folder / f"{safe_name}{ext}"
                if image_path.exists():
                    return image_path
        
        return None
    
    def _download_from_steamgriddb(self, app_name):
        """Скачивание изображения с SteamGridDB"""
        if not self.api_key or not REQUESTS_AVAILABLE:
            return None
        
        try:
            from urllib.parse import quote
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            # 1. Поиск игры
            search_url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{quote(app_name)}"
            response = requests.get(search_url, headers=headers, timeout=5)
            
            if response.status_code != 200:
                return None
            
            results = response.json()
            if not results.get('data'):
                return None
            
            game_id = results['data'][0]['id']
            
            # 2. Получение изображений 16:9
            grids_url = f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}"
            params = {
                "dimensions": ["460x215", "920x430"],
                "types": ["static"]
            }
            grids_response = requests.get(grids_url, headers=headers, params=params, timeout=5)
            
            if grids_response.status_code != 200:
                return None
            
            grids = grids_response.json()
            if not grids.get('data'):
                return None
            
            # 3. Скачивание первого изображения
            image_url = grids['data'][0]['url']
            image_data = requests.get(image_url, timeout=10).content
            
            # 4. Сохранение локально
            safe_name = self._sanitize_filename(app_name)
            ext = '.png' if 'png' in image_url.lower() else '.jpg'

            if self.tiles_dir:
                # Сохранение в AppData\tiles\ как плоский файл — переживает обновления
                image_path = self.tiles_dir / f"{safe_name}{ext}"
            else:
                # Резервный вариант: старое поведение с подпапкой в assets
                app_folder = self.assets_dir / safe_name
                app_folder.mkdir(exist_ok=True)
                image_path = app_folder / f"banner{ext}"
            
            with open(image_path, 'wb') as f:
                f.write(image_data)
            
            print(f"✅ Скачано изображение для: {app_name}")
            return image_path
            
        except Exception as e:
            print(f"❌ Ошибка скачивания изображения для {app_name}: {e}")
            return None
    
    def _sanitize_filename(self, name):
        """Удаление недопустимых символов для имен файлов"""
        safe = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_'))
        return safe.strip().replace(' ', '_')

