import json
from pathlib import Path
from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

# Пытаемся импортировать requests
try:
  import requests

  REQUESTS_AVAILABLE = True
except ImportError:
  REQUESTS_AVAILABLE = False
  print("⚠️ Библиотека requests не установлена. Виджет погоды отключен.")
  print("Установите ее с помощью: pip install requests")


class WeatherFetcher(QThread):
  """Отдельный поток для запросов API без блокировки пользовательского интерфейса (UI)"""

  weather_received = pyqtSignal(dict)
  error_occurred = pyqtSignal(str)

  def __init__(
      self, city, country_code, units, latitude=None, longitude=None
  ):
    super().__init__()
    self.city = city
    self.country_code = country_code
    self.units = units
    self.latitude = latitude
    self.longitude = longitude

  def run(self):
    """Выполняет запрос API в фоновом режиме"""
    if not REQUESTS_AVAILABLE:
      self.error_occurred.emit("библиотека requests не установлена")
      return

    # Если координаты отсутствуют, пытаемся получить их по названию города (геокодирование)
    if self.latitude is None or self.longitude is None:
      coords = self._geocode_city()
      if not coords:
        self.error_occurred.emit(
            f"Не удалось найти координаты для города {self.city}"
        )
        return
      self.latitude, self.longitude = coords

    # Сначала пробуем Open-Meteo
    success = self._fetch_open_meteo()

    if not success:
      # Запасной вариант (fallback) — wttr.in
      print("   Пробуем запасной сервис: wttr.in...")
      success = self._fetch_wttr()

    if not success:
      self.error_occurred.emit("Все погодные сервисы недоступны")

  def _geocode_city(self):
    """Получает GPS-координаты по названию города через Open-Meteo Geocoding (бесплатно)"""
    try:
      location = (
          f"{self.city},{self.country_code}"
          if self.country_code
          else self.city
      )
      url = "https://geocoding-api.open-meteo.com/v1/search"
      params = {
          "name": self.city,
          "count": 1,
          "language": "en",
          "format": "json",
      }

      response = requests.get(url, params=params, timeout=10)

      if response.status_code == 200:
        data = response.json()
        if data.get("results"):
          result = data["results"][0]
          lat = result["latitude"]
          lon = result["longitude"]
          print(f"   Найдено: {result.get('name', self.city)}")
          return (lat, lon)

      return None

    except Exception as e:
      print(f"   Ошибка геокодирования: {e}")
      return None

  def _fetch_open_meteo(self):
    """Запрос данных из Open-Meteo"""
    try:
      url = "https://api.open-meteo.com/v1/forecast"

      params = {
          "latitude": self.latitude,
          "longitude": self.longitude,
          "current_weather": "true",
          "windspeed_unit": "kmh",
          "timezone": "auto",
      }

      response = requests.get(url, params=params, timeout=10)

      if response.status_code == 200:
        data = response.json()

        weather_data = self._parse_open_meteo(data)

        # Определяем единицы измерения для логов
        temp_celsius = weather_data["temp_celsius"]
        if self.units == "imperial":
          temp_display = round((temp_celsius * 9 / 5) + 32)
          unit = "°F"
        else:
          temp_display = round(temp_celsius)
          unit = "°C"

        self.weather_received.emit(weather_data)
        print(
            f"Open-Meteo: {temp_display}{unit} — {weather_data['condition']}"
        )
        return True
      else:
        print(f"Ошибка Open-Meteo: {response.status_code}")
        return False

    except Exception as e:
      print(f"Исключение Open-Meteo: {e}")
      return False

  def _fetch_wttr(self):
    """Запрос данных из wttr.in (ФОЛЛБЭК)"""
    try:
      location = (
          f"{self.city},{self.country_code}"
          if self.country_code
          else self.city
      )
      url = f"https://wttr.in/{location}"
      params = {
          "format": "j1"  # Формат JSON
      }

      response = requests.get(url, params=params, timeout=10)

      if response.status_code == 200:
        data = response.json()

        # Преобразуем в стандартизированный формат
        weather_data = self._parse_wttr(data)

        # Определяем единицы измерения для логов
        temp_celsius = weather_data["temp_celsius"]
        if self.units == "imperial":
          temp_display = round((temp_celsius * 9 / 5) + 32)
          unit = "°F"
        else:
          temp_display = round(temp_celsius)
          unit = "°C"

        self.weather_received.emit(weather_data)
        print(f"wttr.in: {temp_display}{unit} — {weather_data['condition']}")
        return True
      else:
        print(f"Ошибка wttr.in: {response.status_code}")
        return False

    except Exception as e:
      print(f"Исключение wttr.in: {e}")
      return False

  def _parse_open_meteo(self, data):
    """Преобразует данные Open-Meteo в стандартизированный формат"""
    current = data["current_weather"]

    temp_celsius = current["temperature"]

    # Сопоставление погодных кодов Open-Meteo с читаемыми условиями
    weather_codes = {
        0: ("Ясно", "01d"),
        1: ("Преимущественно ясно", "02d"),
        2: ("Переменная облачность", "02d"),
        3: ("Пасмурно", "03d"),
        45: ("Туман", "50d"),
        48: ("Туман", "50d"),
        51: ("Небольшая морось", "09d"),
        53: ("Морось", "09d"),
        55: ("Сильная морось", "09d"),
        61: ("Небольшой дождь", "10d"),
        63: ("Дождь", "10d"),
        65: ("Сильный дождь", "10d"),
        71: ("Небольшой снег", "13d"),
        73: ("Снег", "13d"),
        75: ("Сильный снег", "13d"),
        77: ("Снежные зерна", "13d"),
        80: ("Небольшой ливень", "09d"),
        81: ("Ливень", "09d"),
        82: ("Сильный ливень", "09d"),
        85: ("Небольшой снегопад", "13d"),
        86: ("Снегопад", "13d"),
        95: ("Гроза", "11d"),
        96: ("Гроза с градом", "11d"),
        99: ("Гроза с градом", "11d"),
    }

    code = current.get("weathercode", 0)
    condition, icon_code = weather_codes.get(code, ("Неизвестно", "01d"))

    return {
        "temp_celsius": temp_celsius,  # Сохраняем температуру в градусах Цельсия
        "condition": condition,
        "icon": icon_code,
        "humidity": 0,
        "feels_like_celsius": temp_celsius,
    }

  def _parse_wttr(self, data):
    """Преобразует данные wttr.in в стандартизированный формат"""
    current = data["current_condition"][0]

    # wttr предоставляет значения как в Цельсиях, так и в Фаренгейтах
    temp_c = float(current["temp_C"])
    temp_f = float(current["temp_F"])

    # Всегда сохраняем Цельсий в качестве базового значения
    temp_celsius = temp_c

    # Примерное преобразование текстового описания wttr в код иконки
    desc = current["weatherDesc"][0]["value"].lower()
    icon_code = self._weather_desc_to_icon(desc)

    return {
        "temp_celsius": temp_celsius,  # Сохраняем температуру в градусах Цельсия
        "condition": current["weatherDesc"][0]["value"],
        "icon": icon_code,
        "humidity": int(current.get("humidity", 0)),
        "feels_like_celsius": float(current["FeelsLikeC"]),
    }

  def _weather_desc_to_icon(self, description):
    """Преобразует текстовое описание в код иконки"""
    desc = description.lower()

    if "clear" in desc or "sunny" in desc:
      return "01d"
    elif "partly cloudy" in desc or "partly cloud" in desc:
      return "02d"
    elif "cloudy" in desc or "overcast" in desc:
      return "03d"
    elif "rain" in desc or "drizzle" in desc:
      return "10d"
    elif "thunder" in desc or "storm" in desc:
      return "11d"
    elif "snow" in desc:
      return "13d"
    elif "mist" in desc or "fog" in desc:
      return "50d"
    else:
      return "02d"


class WeatherWidget(QWidget):
  """Погодный виджет, отображающий текущую температуру и погодные условия"""

  # Сигнал, испускаемый при обновлении погодных данных
  weather_updated = pyqtSignal(dict)

  def __init__(self, scaling, parent=None):
    super().__init__(parent)
    self.scaling = scaling
    self.city = "Rome"  # Город по умолчанию
    self.country_code = "IT"  # Страна по умолчанию
    self.units = "metric"  # metric = Цельсий, imperial = Фаренгейт

    # GPS-координаты (кеш для предотвращения повторного геокодирования)
    self.latitude = None
    self.longitude = None

    # Поток для запросов API
    self.fetcher = None

    # Таймер автоматического обновления (каждые 30 минут)
    self.update_timer = QTimer()
    self.update_timer.timeout.connect(self.fetch_weather)
    self.update_timer.setInterval(30 * 60 * 1000)  # 30 минут

    # Таймер отложенного запроса (может быть остановлен)
    self.delayed_fetch_timer = QTimer()
    self.delayed_fetch_timer.setSingleShot(True)
    self.delayed_fetch_timer.timeout.connect(self.fetch_weather)

    # Текущие данные о погоде
    self.current_weather = {
        "temp": "--",
        "condition": "Загрузка...",
        "icon": "01d",
        "humidity": "--",
        "feels_like": "--",
    }

    # Флаг видимости, управляемый пользователем (по умолчанию: False = скрыт)
    self._user_visible = False

    # Эффект прозрачности + анимация плавного появления (fade-in)
    self._opacity_effect = QGraphicsOpacityEffect(self)
    self._opacity_effect.setOpacity(0.0)
    self.setGraphicsEffect(self._opacity_effect)

    self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
    self._fade_anim.setDuration(400)  # 400 мс – плавно, но не медленно
    self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    self.init_ui()

    def setVisible(self, visible):
      """Переопределение метода: сохраняет выбор пользователя.

      Если visible=True, но реальных данных еще нет, виджет остается скрытым
      (opacity=0) до момента вызова _update_weather_data, который запустит
      fade-in. Если данные уже есть (например, при смене единиц измерения),
      fade-in запускается немедленно.
      """
      self._user_visible = visible

      if visible and self.city:
        # Запускаем запрос и таймер, если они еще не активны
        if not self.update_timer.isActive():
          self.delayed_fetch_timer.start(2000)
          self.update_timer.start()

        # Показываем виджет только при наличии реальных данных
        if self.current_weather.get("temp_celsius") is not None:
          super().setVisible(True)
          self._fade_in()
        else:
          # Остается скрытым: появится с анимацией в _update_weather_data
          super().setVisible(False)
      else:
        # Виджет отключен – останавливаем всё и скрываем
        if self.update_timer.isActive():
          self.update_timer.stop()
        if self.delayed_fetch_timer.isActive():
          self.delayed_fetch_timer.stop()
        if self.fetcher and self.fetcher.isRunning():
          self.fetcher.quit()
          self.fetcher.wait(1000)
        self._fade_anim.stop()
        self._opacity_effect.setOpacity(0.0)
        super().setVisible(False)

  def _fade_in(self):
    """Запускает анимацию плавного появления (fade-in) от текущей прозрачности до 1.0"""
    self._fade_anim.stop()
    self._fade_anim.setStartValue(self._opacity_effect.opacity())
    self._fade_anim.setEndValue(1.0)
    self._fade_anim.start()

  def init_ui(self):
    """Инициализация интерфейса виджета"""
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(self.scaling.scale(2))

    # Основной контейнер
    container = QWidget()
    container.setStyleSheet("background-color: transparent;")
    container_layout = QHBoxLayout(container)
    container_layout.setContentsMargins(0, 0, self.scaling.scale(20), 0)
    container_layout.setSpacing(self.scaling.scale(12))

    # Вертикальный макет для иконки + города
    icon_city_layout = QVBoxLayout()
    icon_city_layout.setSpacing(self.scaling.scale(2))
    icon_city_layout.setContentsMargins(0, 0, 0, 0)
    icon_city_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

    # Иконка погоды
    self.weather_icon = QLabel()
    self.weather_icon.setFixedSize(
        self.scaling.scale(64), self.scaling.scale(64)
    )
    self.weather_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._set_weather_emoji("☁️")  # Иконка по умолчанию

    # Название города (под иконкой)
    self.city_label = QLabel(self.city.title())
    self.city_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.city_label.setWordWrap(True)
    self.city_label.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.7);
            font-size: {self.scaling.scale_font(14)}px;
            font-weight: 600;
        """)

    icon_city_layout.addWidget(self.weather_icon)
    icon_city_layout.addWidget(self.city_label)

    # Информация о погоде (температура + состояние)
    info_layout = QVBoxLayout()
    info_layout.setSpacing(self.scaling.scale(2))
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

    # Температура (высота совпадает с иконкой)
    self.temp_label = QLabel("--°")
    self.temp_label.setAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
    )
    self.temp_label.setMinimumHeight(self.scaling.scale(64))
    self.temp_label.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.9);
            font-size: {self.scaling.scale_font(36)}px;
            font-weight: 700;
        """)

    self.condition_label = QLabel("Загрузка...")
    self.condition_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
    self.condition_label.setWordWrap(True)
    self.condition_label.setStyleSheet(f"""
            color: rgba(255, 255, 255, 0.6);
            font-size: {self.scaling.scale_font(14)}px;
            font-weight: 500;
        """)

    info_layout.addWidget(self.temp_label)
    info_layout.addWidget(self.condition_label)

    container_layout.addLayout(icon_city_layout)
    container_layout.addLayout(info_layout)

    layout.addWidget(container)

    # Скрываем виджет до появления валидных данных
    self.hide()

  def _set_weather_emoji(self, emoji):
    """Устанавливает погодное эмодзи"""
    font_size = max(self.scaling.scale_font(48), 1)
    self.weather_icon.setStyleSheet(f"""
            font-size: {font_size}px;
        """)
    self.weather_icon.setText(emoji)

  def set_location(self, city, country_code=""):
    """Устанавливает населенный пункт для прогноза"""
    self.city = city.strip()
    self.country_code = country_code.strip()

    # Обновляем метку города
    if hasattr(self, "city_label"):
      self.city_label.setText(self.city.title())

    # Сбрасываем координаты (будет выполнено повторное геокодирование)
    self.latitude = None
    self.longitude = None

    if self.city:
      if self._user_visible and not self.delayed_fetch_timer.isActive():
        self.delayed_fetch_timer.start(2000)

      # Запускаем таймер обновления только если виджет видим
      if self._user_visible and not self.update_timer.isActive():
        self.update_timer.start()
    else:
      self.update_timer.stop()
      self.delayed_fetch_timer.stop()
      self.hide()

  def set_units(self, units):
    """Устанавливает единицы измерения (metric/imperial)"""
    old_units = self.units
    self.units = units

    if self.current_weather.get("temp_celsius") is not None:
      temp_celsius = self.current_weather["temp_celsius"]

      if self.units == "imperial":
        temp = round((temp_celsius * 9 / 5) + 32)
        unit_symbol = "°F"
      else:
        temp = round(temp_celsius)
        unit_symbol = "°C"

      # Обновляем внутренние данные
      self.current_weather["temp"] = temp

      # Обновляем UI
      self.temp_label.setText(f"{temp}{unit_symbol}")

      print(f"   Отображение температуры обновлено: {temp}{unit_symbol}")

      was_visible = self.isVisible()

      # Принудительное обновление
      self.temp_label.update()
      self.temp_label.repaint()
      self.update()
      self.repaint()

      if was_visible and self._user_visible:
        if not self.isVisible():
          super().setVisible(True)
        self._fade_in()

      # Принудительно обновляем родительский компонент
      if self.parent():
        self.parent().update()
        self.parent().repaint()

    elif self.city and self._user_visible:
      print("   Данные отсутствуют, получаем погоду...")
      # Используем отложенный таймер, чтобы избежать дублирующих запросов,
      # если setVisible/set_location были вызваны незадолго до этого
      self.delayed_fetch_timer.stop()
      self.delayed_fetch_timer.start(100)

  def fetch_weather(self):
    """Выполняет запрос API для получения погоды"""
    if not REQUESTS_AVAILABLE:
      print("⚠️ Погода: библиотека requests недоступна")
      return

    if not self.city:
      print("⚠️ Погода: город не задан")
      return

    # Если запрос уже выполняется, ждем
    if self.fetcher and self.fetcher.isRunning():
      return

    # Создаем и запускаем поток запроса
    self.fetcher = WeatherFetcher(
        self.city,
        self.country_code,
        self.units,
        self.latitude,
        self.longitude,
    )
    self.fetcher.weather_received.connect(self._update_weather_data)
    self.fetcher.error_occurred.connect(self._show_error_message)
    self.fetcher.start()

  def _show_error_message(self, error_msg):
    """Отображает сообщение об ошибке"""
    print(f"❌ Погода: {error_msg}")
    self._show_error()

  def _update_weather_data(self, data):
    """Обновляет погодные данные из JSON-ответа API"""
    try:
      if self.fetcher:
        self.latitude = self.fetcher.latitude
        self.longitude = self.fetcher.longitude

      # Получаем температуру в Цельсиях от API
      temp_celsius = data.get("temp_celsius", data.get("temp", 0))

      # Конвертируем в соответствии с текущими единицами измерения виджета
      if self.units == "imperial":
        temp = round((temp_celsius * 9 / 5) + 32)
        unit_symbol = "°F"
        print(f"   Конвертировано: {temp_celsius}°C → {temp}°F")
      else:
        temp = round(temp_celsius)
        unit_symbol = "°C"

      condition = data["condition"]
      icon_code = data["icon"]

      # Обновляем внутренние данные
      self.current_weather = {
          "temp": temp,
          "temp_celsius": temp_celsius,
          "condition": condition,
          "icon": icon_code,
          "humidity": data.get("humidity", 0),
          "feels_like": temp,
      }

      # Обновляем UI
      self.temp_label.setText(f"{temp}{unit_symbol}")
      self.condition_label.setText(condition)

      # Устанавливаем эмодзи на основе кода иконки
      emoji = self._get_weather_emoji(icon_code)
      self._set_weather_emoji(emoji)

      # Показываем виджет с fade-in только если он разрешен пользователем
      if self._user_visible:
        if not self.isVisible():
          super().setVisible(True)
        self._fade_in()

      # Отправляем сигнал
      self.weather_updated.emit(self.current_weather)

    except KeyError as e:
      print(f"❌ Отсутствует поле погодных данных: {e}")
      self._show_error()

  def _get_weather_emoji(self, icon_code):
    """Преобразует код иконки в эмодзи"""
    icon_map = {
        "01d": "☀️",  # ясное небо днем
        "01n": "🌙",  # ясное небо ночью
        "02d": "⛅",  # малооблачно днем
        "02n": "☁️",  # малооблачно ночью
        "03d": "☁️",  # рассеянные облака
        "03n": "☁️",
        "04d": "☁️",  # разорванная облачность
        "04n": "☁️",
        "09d": "🌧️",  # ливневый дождь
        "09n": "🌧️",
        "10d": "🌦️",  # дождь днем
        "10n": "🌧️",  # дождь ночью
        "11d": "⛈️",  # гроза
        "11n": "⛈️",
        "13d": "❄️",  # снег
        "13n": "❄️",
        "50d": "🌫️",  # туман / дымка
        "50n": "🌫️",
    }

    return icon_map.get(icon_code, "🌤️")

  def _show_error(self):
    """Отображает состояние ошибки"""
    self.temp_label.setText("--°")
    self.condition_label.setText("Нет данных")
    self._set_weather_emoji("❌")

  def stop(self):
    """Останавливает таймер обновления"""
    if self.update_timer.isActive():
      self.update_timer.stop()

    # Останавливаем поток запроса, если он выполняется
    if self.fetcher and self.fetcher.isRunning():
      self.fetcher.quit()
      self.fetcher.wait(1000)

  def cleanup(self):
    """Очистка ресурсов"""
    self.stop()


def integrate_weather_widget(launcher, base_dir):
  # Создаем погодный виджет
  launcher.weather_widget = WeatherWidget(launcher.scaling, launcher)

  # Сохраняем base_dir для дальнейшего использования
  launcher.weather_base_dir = base_dir


def add_weather_to_header(launcher, header_layout):
  """Добавляет погодный виджет в хедер лаунчера.

  Вызывать в TVLauncher.init_ui() после создания clock_layout

  Args:
      launcher: Экземпляр TVLauncher
      header_layout: QHBoxLayout хедера
  """
  pass


def save_weather_config(launcher, city, country_code, units):
  """УСТАРЕЛО: Эта функция больше не используется!

  Конфигурация погоды теперь сохраняется напрямую в launcher_apps.json
  через launcher.save_config(), вызываемый из weather_settings.py

  Args:
      launcher: Экземпляр TVLauncher
      city: Название города (игнорируется)
      country_code: Код страны (игнорируется)
      units: Единицы измерения (игнорируется)
  """
  pass


def force_launcher_refresh(launcher):
  """Принудительно обновляет лаунчер и хедер целиком.

  Вызывать после обновления погодного виджета.
  """
  if not launcher:
    print("⚠️ Лаунчер равен None, невозможно обновить")
    return

  # Обновляем погодный виджет
  if hasattr(launcher, "weather_widget"):
    launcher.weather_widget.update()
    launcher.weather_widget.repaint()

  # Находим и обновляем центральный виджет
  try:
    central = launcher.centralWidget()
    if central:
      central.update()
      central.repaint()

      # Обновляем макет центрального виджета, сохраняя видимость погоды
      layout = central.layout()
      if layout:
        layout.update()
        # Сохраняем видимость перед activate(), которая может ее сбросить
        _wv = None
        if hasattr(launcher, "weather_widget") and launcher.weather_widget:
          _wv = launcher.weather_widget._user_visible
        layout.activate()
        # Восстанавливаем видимость после activate()
        if _wv is not None:
          launcher.weather_widget._user_visible = _wv
          launcher.weather_widget.setVisible(_wv)
  except Exception as e:
    print(f"   ⚠️ Ошибка обновления центрального виджета: {e}")

  # Обновляем главное окно
  try:
    launcher.update()
    launcher.repaint()
  except Exception as e:
    print(f"   ⚠️ Ошибка обновления лаунчера: {e}")

  try:
    from PyQt6.QtCore import QCoreApplication

    QCoreApplication.processEvents()
  except Exception as e:
    print(f"   ⚠️ Ошибка обработки событий: {e}")


def cleanup_weather_widget(launcher):
  if hasattr(launcher, "weather_widget"):
    launcher.weather_widget.cleanup()

