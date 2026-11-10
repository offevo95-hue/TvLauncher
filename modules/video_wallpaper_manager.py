"""
video_wallpaper_manager.py

Менеджер потоковых видео-обоев (в стиле Projectivy «Overflight») с использованием
mpv в качестве встроенного механизма воспроизведения. Читает JSON-каталог,
совместимый с projectivy-plugin-wallpaper-overflight:

    [
        {
            "location": "...",
            "title": "...",
            "author": "...",
            "url_img": "...",
            "url_1080p": "...",
            "url_1080p_hdr": "...",
            "url_4k": "...",
            "url_4k_hdr": "..."
        },
        ...
    ]

Ни одно поле не является обязательным, кроме как минимум одного url_*. В оригинальном
формате нет поля «категория»: фильтрация (Night, China, Ocean, ...) выполняется путем
сопоставления ключевых слов по полям «location» + «title».

Требования:
    pip install python-mpv
    + бинарный файл libmpv (mpv-2.dll для Windows, libmpv.so.2 для Linux), присутствующий в:
        <assets_dir>/lib/mpv/<platform>/   либо уже установленный в системе.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
ctypes import ctypes.util
import json
import os
import pathlib
import platform
import random
import re
import sys
import time
from urllib.request import Request, urlopen

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QDesktopServices, QImage, QOpenGLContext, QPixmap, QSurfaceFormat
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QApplication, QLabel

# FRAME_MAX_WIDTH теперь рассчитывается динамически исходя из реального разрешения
# экрана (см. _init_mpv -> _screen_width()), больше не фиксируется на 1080px:
# на экранах 4K/1440p старое фиксированное значение давало кадр меньшего разрешения,
# который затем растягивался Qt (setScaledContents) -> была видна размытость.
# Это лишь фоллбэк на случай, когда размер экрана еще не удается определить.
FRAME_MAX_WIDTH_FALLBACK = 1920
FRAME_GRAB_INTERVAL_MS = (  # ~25fps: более стабильно при чтении GPU->RAM каждого отдельного кадра высокого разрешения
    40
)


class _FrameGrabWorker(QObject):
  """Захватывает кадры из mpv (headless, vo='null') в отдельном от UI потоке,

  чтобы цикл обработки событий Qt всегда оставался свободным.
  """

  frame_ready = pyqtSignal(QImage)

  def __init__(self, mpv_getter, interval_ms, max_width):
    super().__init__()
    self._mpv_getter = mpv_getter
    self._interval_ms = interval_ms
    self._max_width = max_width
    self._timer = None
    self._grabbing = False
    self._running = False

  @pyqtSlot()
  def start(self):
    # Одноразовый таймер с автоперезапуском: если захват занимает больше
    # времени, чем ожидалось, следующий вызов все равно начнется ПОСЛЕ текущего
    # (никогда не встает в очередь за опаздывающими захватами) -> более плавный ритм.
    self._running = True
    self._timer = QTimer()
    self._timer.setSingleShot(True)
    self._timer.timeout.connect(self._grab)
    self._timer.start(self._interval_ms)

  @pyqtSlot()
  def stop(self):
    self._running = False
    if self._timer:
      self._timer.stop()

  def _grab(self):
    if self._grabbing:
      self._reschedule()
      return
    mpv = self._mpv_getter()
    if mpv is None:
      self._reschedule()
      return
    # Перенастраиваем интервал захвата под реальный fps видео вместо использования
    # фиксированного начального значения: таймер, не привязанный к реальному
    # ритму кадров, создает периодическое несоответствие (иногда захватывается
    # тот же кадр дважды, иногда пропускается один), что является главной
    # причиной видимых подтормаживаний независимо от CPU/GPU.
    try:
      fps = mpv.fps or mpv.container_fps
      if fps and fps > 1:
        target_interval = max(16, round(1000 / fps))
        if target_interval != self._interval_ms:
          self._interval_ms = target_interval
    except Exception:
      pass
    self._grabbing = True
    try:
      img = mpv.screenshot_raw()
      if img is None:
        return
      if img.mode != "RGBA":
        img = img.convert("RGBA")
      # БЕЗ изменения размера (resize) здесь: фильтр vf=scale в mpv (на стороне GPU, быстрый)
      # уже привел кадр к целевому разрешению. Повторное изменение размера здесь
      # в Python с помощью PIL было бы двойной работой и главной причиной рывков:
      # изменение размера на CPU для каждого отдельного кадра, ~25-30 раз в секунду,
      # в дополнение к обычному чтению GPU->RAM.
      data = img.tobytes("raw", "RGBA")
      qimg = QImage(
          data, img.width, img.height, QImage.Format.Format_RGBA8888
      )
      qimg = qimg.copy()
      self.frame_ready.emit(qimg)
    except Exception as e:
      self._fail_count = getattr(self, "_fail_count", 0) + 1
      # Логируем только каждый 25-й сбой (~1 в секунду при 40мс/кадр) вместо
      # каждого потерянного кадра: при включенном hwdec лог заполнялся одинаковыми
      # ошибками, что само по себе замедляло поток и усиливало подтормаживания.
      if self._fail_count % 25 == 1:
        print(
            f"[VideoWallpaper] сбой захвата кадра ({self._fail_count} всего):"
            f" {e}"
        )
    finally:
      self._grabbing = False
      self._reschedule()

    def _reschedule(self):
      if self._running and self._timer:
        self._timer.start(self._interval_ms)


class _MpvGLWidget(QOpenGLWidget):
  """Виджет, отрисовывающий кадры mpv с помощью render API libmpv

  (на основе отправки, mpv пишет напрямую в OpenGL FBO) вместо передачи
  скриншотов по одному через IPC, как делает _FrameGrabWorker.

  В отличие от «нативной» вставки через winId/wid (настоящее окно на уровне ОС,
  игнорирующее порядок z-order в Qt), QOpenGLWidget компонует свое содержимое
  ВНУТРИ стандартного пайплайна рендеринга Qt: он ведет себя как обычный виджет
  для lower()/stackUnder(), поэтому плитки сверху остаются корректно поверх него.
  Это решает как проблему плавности (нет чтения с CPU для каждого кадра, mpv пишет
  туда, где все уже готово к отрисовке), так и проблему наложения слоев нативной вставки.
  """

  def __init__(self, mpv_instance, parent=None):
    super().__init__(parent)
    self._mpv = mpv_instance
    self._render_ctx = None
    self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
    self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)

    # Отключаем ожидание vsync (vsync-wait) в контексте GL ЭТОГО виджета.
    # Без этого каждый видеокадр (~30fps) вызывает собственный обмен буферов (swap-buffer),
    # который по умолчанию ждет следующий vsync, конкурируя с обменом главного
    # композитора Qt (который заставляет плитки работать на 60fps): главный поток GUI
    # в итоге ждет два vsync вместо одного, и все приложение проседает до частоты
    # кадров видео. С swapInterval=0vsync ждет только главный композитор, делая это
    # ровно один раз за кадр.
    fmt = QSurfaceFormat()
    fmt.setSwapInterval(0)
    self.setFormat(fmt)

  frame_ready = pyqtSignal()

  def _get_proc_address(self, _, name):
    glctx = QOpenGLContext.currentContext()
    if glctx is None:
      return 0
    addr = glctx.getProcAddress(bytes(name))
    return int(addr) if addr else 0

  def initializeGL(self):
    import mpv as mpv_module

    # get_proc_address должен быть настоящей функцией ctypes CFUNCTYPE (тип,
    # предоставляемый python-mpv как MpvGlGetProcAddressFn), а не методом Python
    # передаваемым «как есть»: kwargs_to_render_param_array выполняет строгие
    # преобразования ctypes, и «голый» метод падает с ошибкой TypeError. Также
    # сохраняем явную ссылку (self._get_proc_address_c), иначе сборщик мусора
    # Python может удалить обертку ctypes, пока libmpv еще использует ее -> краш.
    self._get_proc_address_c = mpv_module.MpvGlGetProcAddressFn(
        self._get_proc_address
    )
    self._render_ctx = mpv_module.MpvRenderContext(
        self._mpv,
        "opengl",
        opengl_init_params={"get_proc_address": self._get_proc_address_c},
    )
    # update_cb вызывается mpv из внутреннего потока при готовности каждого
    # нового кадра: мы не трогаем UI оттуда напрямую (это не поток Qt), а просто
    # отправляем потокобезопасный сигнал, который Qt передает в главный поток.
    self._render_ctx.update_cb = self._on_frame_ready

  def _on_frame_ready(self):
    self.frame_ready.emit()

  def paintGL(self):
    if self._render_ctx is None:
      return
    try:
      self._render_ctx.render(
          flip_y=True,
          opengl_fbo={
              "w": self.width(),
              "h": self.height(),
              "fbo": self.defaultFramebufferObject(),
          },
          # Без этого libmpv БЛОКИРУЕТ ВНУТРИ СЕБЯ вызывающий поток
          # (здесь: главный поток GUI Qt внутри paintGL), чтобы сопоставить
          # кадр с точным моментом времени (тайминг кадров / frame pacing).
          # Работая в главном потоке, эта блокировка останавливала также
          # анимацию плиток и открытие меню, а не только видео: все приложение
          # замедлялось синхронно с частотой кадров видео, хотя загрузка CPU/GPU
          # была минимальной (поток ждал, а не вычислял). При
          # block_for_target_time=False mpv сразу отображает текущий кадр,
          # никогда не блокируя вызывающий поток.
          block_for_target_time=False,
      )
    except Exception as e:
      print(f"[VideoWallpaper] сбой рендеринга кадра: {e}")

  def shutdown(self):
    if self._render_ctx is not None:
      try:
        self._render_ctx.update_cb = None
        self._render_ctx.free()
      except Exception:
        pass
      self._render_ctx = None


DEFAULT_CATALOG_URL = (
    "https://raw.githubusercontent.com/spocky/"
    "projectivy-plugin-wallpaper-overflight/main/videos.json"
)

# Приоритет качества: ключ конфигурации -> порядок запасных вариантов (fallback) для полей url_*
QUALITY_CHAINS = {
    "4k_hdr": ["url_4k_hdr", "url_4k", "url_1080p_hdr", "url_1080p"],
    "4k": ["url_4k", "url_4k_hdr", "url_1080p_hdr", "url_1080p"],
    "1080p_hdr": ["url_1080p_hdr", "url_1080p", "url_4k_hdr", "url_4k"],
    "1080p": ["url_1080p", "url_1080p_hdr", "url_4k", "url_4k_hdr"],
    "auto": ["url_1080p", "url_4k", "url_1080p_hdr", "url_4k_hdr"],
}

# Ключевые слова по умолчанию для «категорий», отображаемых в диалоге.
# Пользователь может расширять/изменять их в конфигурации (см. set_category_keywords).
DEFAULT_CATEGORIES = {
    "Nature": ["nature", "forest", "mountain", "valley", "canyon", "waterfall"],
    "City": ["city", "skyline", "urban", "downtown", "night city"],
    "Night": ["night", "notturn", "aurora night", "northern lights"],
    "Ocean": ["ocean", "sea", "coast", "beach", "reef", "wave"],
    "Space": ["space", "earth", "orbit", "galaxy", "iss", "satellite", "aurora"],
    "Countryside": ["countryside", "farm", "field", "rural", "vineyard"],
    "Desert": ["desert", "dune", "sahara"],
    "Snow": ["snow", "winter", "alps", "glacier", "ice"],
    "China": ["china", "beijing", "shanghai", "hong kong", "great wall"],
    "Japan": ["japan", "tokyo", "kyoto", "fuji"],
    "USA": ["usa", "america", "new york", "california", "hawaii"],
}


class VideoWallpaperManager:
  """Управление каталогом, фильтрами, воспроизведением mpv и автоматической сменой видео-обоев."""

  def __init__(
      self, parent, config_data, assets_dir, background_manager=None
  ):
    """Args:

    parent: главное окно (TVLauncher)
    config_data: словарь глобальной конфигурации (секция 'video_wallpaper')
    assets_dir: путь к папке assets
    background_manager: экземпляр BackgroundManager (для статического
                         фоллбэка и приостановки смены статических обоев,
                         когда активны видео)
    """
    self.parent = parent
    self.assets_dir = Path(assets_dir)
    self.background_manager = background_manager

    cfg = (
        dict(config_data.get("video_wallpaper", {})) if config_data else {}
    )
    self.enabled = cfg.get("enabled", False)
    self.quality = cfg.get("quality", "1080p")  # см. QUALITY_CHAINS
    self.interval_seconds = cfg.get("interval_seconds", 600)  # 10 минут по умолчанию
    self.categories = cfg.get("categories", [])  # пустой список = все
    self.catalog_url = cfg.get("catalog_url", DEFAULT_CATALOG_URL)
    self.muted = cfg.get("muted", True)
    self.volume = cfg.get("volume", 0)

    self.category_keywords = dict(DEFAULT_CATEGORIES)

    self.catalog = []  # список отфильтрованных/валидных записей
    self.current_entry = None
    self.rotation_timer = None
    self._dead_urls = (
        set()
    )  # URL, оказавшиеся нерабочими в текущей сессии
    self._consecutive_failures = 0
    self._max_consecutive_failures = 15
    self._skip_timer = None
    self._play_generation = 0

    self.mpv = None
    self._render_mode = (
        None  # 'gl' (render API, быстро) или 'legacy' (screenshot relay, фоллбэк)
    )
    self.video_label = (
        None  # _MpvGLWidget в режиме 'gl', QLabel в режиме 'legacy'
    )
    self.available = False  # True, если mpv успешно инициализирован
    self.last_error = None
    self._frame_thread = None
    self._frame_worker = None

    self._cache_file = (
        self.assets_dir / "wallpapers_video" / "catalog_cache.json"
    )
    self._cache_file.parent.mkdir(parents=True, exist_ok=True)

  # ==================== ИНИЦИАЛИЗАЦИЯ MPV ====================

  def _screen_width(self):
    """Ширина основного экрана в реальных пикселях, используемая для масштабирования

    mpv (через фильтр vf, на стороне GPU) ровно до целевого разрешения,
    вместо старого лимита в 1080px, который на больших экранах давал кадр
    ниже разрешения с последующим растягиванием в Qt.
    """
    try:
      screen = QApplication.primaryScreen().geometry()
      if screen.width() > 0:
        return screen.width()
    except Exception:
      pass
    return FRAME_MAX_WIDTH_FALLBACK

  def _locate_libmpv(self):
    """Ищет бинарник libmpv: сначала встроенный в assets/lib/mpv, затем системный."""
    system = platform.system()
    bundled_dir = self.assets_dir / "lib" / "mpv"

    candidates = []
    if system == "Windows":
      candidates.append(bundled_dir / "windows" / "libmpv-2.dll")
      candidates.append(bundled_dir / "windows" / "mpv-2.dll")
    else:
      candidates.append(bundled_dir / "linux" / "libmpv.so.2")
      candidates.append(bundled_dir / "linux" / "libmpv.so")

    for c in candidates:
      if c.exists():
        return str(c)

    # Фоллбэк: системная библиотека, установленная в системе
    found = ctypes.util.find_library("mpv")
    return found  # может быть None

  def _init_mpv(self):
    """Инициализирует libmpv + python-mpv в виде виджета позади оверлея.

    Сначала пробует Render API (vo='libmpv' + QOpenGLWidget, push-based,
    mpv записывает кадры прямо во фреймбуфер OpenGL (FBO) GPU без участия CPU).
    Если по какой-то причине это не удается (слишком старая libmpv, python-mpv
    без MpvRenderContext, проблемы с OpenGL драйвером...), автоматически
    переключается на старый механизм скриншотов, который медленнее, но совместимее.
    """
    if self.mpv is not None:
      return True

    lib_path = self._locate_libmpv()
    if lib_path is None:
      self.last_error = (
          "libmpv не найдена. Поместите mpv-2.dll (Windows) или libmpv.so.2"
          " (Linux) в assets/lib/mpv/<platform>/ либо установите mpv в систему."
      )
      self.available = False
      return False

    if platform.system() == "Windows":
      dll_dir = str(Path(lib_path).parent)
      try:
        os.add_dll_directory(dll_dir)
      except (AttributeError, OSError):
        pass
      os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
    else:
      if "wallpapers_video" not in lib_path and "lib/mpv" in lib_path:
        ctypes.CDLL(lib_path)

    if self._init_mpv_render_api():
      self._render_mode = "gl"
      self.available = True
      self.last_error = None
      return True

    print(
        f"[VideoWallpaper] Render API недоступен ({self.last_error}),"
        " переключение на screenshot relay."
    )
    if self._init_mpv_legacy():
      self._render_mode = "legacy"
      self.available = True
      self.last_error = None
      return True

    self.available = False
    return False

  def _common_mpv_kwargs(self, vo):
    return dict(
        vo=vo,
        loop_file="inf",
        keep_open="yes",
        idle="yes",
        osc=False,
        input_default_bindings=False,
        input_vo_keyboard=False,
        mute=self.muted,
        volume=self.volume,
        cache="yes",
        network_timeout=15,
        log_handler=self._mpv_log,
        loglevel="warn",
        ytdl=False,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        http_header_fields="Referer: https://www.apple.com/",
    )

  def _init_mpv_render_api(self):
    """Быстрый путь: mpv + QOpenGLWidget через render API libmpv."""
    try:
      import mpv

      mpv_kwargs = self._common_mpv_kwargs(vo="libmpv")
      # При использовании Render API кадр остается на GPU от начала до конца
      # (аппаратное декодирование -> текстура -> композитинг Qt): нет чтения с
      # CPU для каждого кадра, как в режиме скриншотов, поэтому здесь hwdec
      # дает преимущество, а не проблемы.
      mpv_kwargs["hwdec"] = "auto-safe"

      self.mpv = mpv.MPV(**mpv_kwargs)
      self.mpv.observe_property("eof-reached", self._on_eof_reached)
      self.mpv.event_callback("file-loaded")(self._on_file_loaded)
      self.mpv.event_callback("end-file")(self._on_end_file)

      self.video_label = _MpvGLWidget(self.mpv, self.parent)
      self.video_label.frame_ready.connect(self.video_label.update)
      screen = QApplication.primaryScreen().geometry()
      self.video_label.setGeometry(0, 0, screen.width(), screen.height())
      self.video_label.lower()
      if getattr(self, "overlay", None):
        self.video_label.stackUnder(self.overlay)
      self.video_label.show()  # принудительно вызывает initializeGL() -> создает контекст рендеринга

      if getattr(self.video_label, "_render_ctx", None) is None:
        raise RuntimeError(
            "MpvRenderContext не создан (initializeGL не был вызван или"
            " завершился ошибкой)"
        )

      return True
    except Exception as e:
      self.last_error = f"Render API не удался: {e}"
      if self.mpv is not None:
        try:
          self.mpv.terminate()
        except Exception:
          pass
        self.mpv = None
      if getattr(self, "video_label", None):
        self.video_label.deleteLater()
        self.video_label = None
      return False

  def _init_mpv_legacy(self):
    """Запасной вариант: mpv headless (vo='null') + скриншот каждого кадра

    на QLabel, как до внедрения render API.
    """
    try:
      import mpv

      self.video_label = QLabel(self.parent)
      self.video_label.setStyleSheet("background-color: black;")
      self.video_label.setScaledContents(True)
      screen = QApplication.primaryScreen().geometry()
      self.video_label.setGeometry(0, 0, screen.width(), screen.height())
      self.video_label.lower()
      if getattr(self, "overlay", None):
        self.video_label.stackUnder(self.overlay)
      self.video_label.show()

      mpv_kwargs = self._common_mpv_kwargs(vo="null")
      # hwdec отключен: с vo='null' и созданием скриншота каждого кадра через IPC,
      # аппаратно декодированный кадр все равно приходится скачивать с GPU при каждом
      # захвате -> периодические сбои (MPV_ERROR_COMMAND, -12) и пропущенные кадры.
      # См. _init_mpv_render_api для работы без этого ограничения.
      mpv_kwargs["hwdec"] = "no"
      mpv_kwargs["vf"] = f"lavfi=[scale={self._screen_width()}:-2]"

      self.mpv = mpv.MPV(**mpv_kwargs)
      self.mpv.observe_property("eof-reached", self._on_eof_reached)
      self.mpv.event_callback("file-loaded")(self._on_file_loaded)
      self.mpv.event_callback("end-file")(self._on_end_file)

      self._setup_frame_worker()
      return True

    except Exception as e:
      self.last_error = f"Не удалось инициализировать mpv: {e}"
      self.mpv = None
      if getattr(self, "video_label", None):
        self.video_label.deleteLater()
        self.video_label = None
      return False

  def _setup_frame_worker(self):
    self._frame_thread = QThread()
    self._frame_worker = _FrameGrabWorker(
        mpv_getter=lambda: self.mpv,
        interval_ms=FRAME_GRAB_INTERVAL_MS,
        max_width=self._screen_width(),
    )
    self._frame_worker.moveToThread(self._frame_thread)
    self._frame_worker.frame_ready.connect(self._apply_frame)
    self._frame_thread.started.connect(self._frame_worker.start)
    self._frame_thread.start()

  def _apply_frame(self, qimg):
    if self.video_label:
      self.video_label.setPixmap(QPixmap.fromImage(qimg))

  def _start_frame_grabbing(self):
    if self._frame_worker:
      from PyQt6.QtCore import QMetaObject

      QMetaObject.invokeMethod(self._frame_worker, "start")

  def _stop_frame_grabbing(self):
    if self._frame_worker:
      from PyQt6.QtCore import QMetaObject

      QMetaObject.invokeMethod(self._frame_worker, "stop")

  def resize_to_parent(self):
    """Изменяет размер QLabel видео под размер экрана (вызывать при resize)."""
    if self.video_label:
      screen = QApplication.primaryScreen().geometry()
      self.video_label.setGeometry(0, 0, screen.width(), screen.height())

  def _mpv_log(self, loglevel, component, message):
    """Получает внутренние логи mpv — критически важно для диагностики черного экрана без ошибок."""
    print(f"[mpv/{loglevel}] {component}: {message}")

  def _on_eof_reached(self, name, value):
    """Если текущий файл завершился (чего не должно быть с loop_file='inf', но для безопасности)

    или если загрузка не удалась и mpv сообщает eof, так и не воспроизведя ничего.
    """
    if value:
      print(
          "[VideoWallpaper] достигнут eof (eof-reached) для:"
          f" {self.current_entry.get('title') if self.current_entry else '?'}"
      )

  def _on_file_loaded(self, event=None):
    """Вызывается mpv при успешной загрузке файла."""
    self._consecutive_failures = 0

  def _log_playback_diagnostics(self):
    """Выводит внутреннее состояние mpv, чтобы понять, проблема в декодировании или рендеринге."""
    if not self.mpv:
      return
    try:
      params = self.mpv.video_params
      width = self.mpv.width
      height = self.mpv.height
      core_idle = self.mpv.core_idle
      pause = self.mpv.pause
      print(
          f"[VideoWallpaper][diag] video_params={params} width={width}"
          f" height={height} core_idle={core_idle} pause={pause}"
          f" label_size={self.video_label.size() if self.video_label else None}"
          " label_visible="
          f"{self.video_label.isVisible() if self.video_label else None}"
      )
    except Exception as e:
      print(
          f"[VideoWallpaper][diag] Не удалось прочитать состояние mpv: {e}"
      )

  def _on_end_file(self, event):
    """Вызывается mpv по окончании воспроизведения файла.

    ПРИМЕЧАНИЕ: мы больше не полагаемся здесь на event.get('reason'), поскольку
    объект, передаваемый python-mpv для события 'end-file', не является словарем
    (это MpvEvent с причиной внутри event.data в форматах, отличающихся в разных
    версиях библиотеки) — isinstance(event, dict) всегда возвращал False,
    функция немедленно завершалась, и битые ссылки НИКОГДА не обрабатывались:
    mpv навсегда зависал в состоянии idle -> постоянный черный экран без каких-либо
    логов ошибок. Настоящая логика обнаружения сбоев теперь находится в
    _check_playback_health(), тайм-аут-вотчере, запускаемом из play_entry(),
    который не зависит от формата события.
    """
    pass

  def stack_under(self, overlay=None):
    """Гарантирует, что видео-метка (QLabel/QOpenGLWidget) остается под плитками/оверлеем

    (дочерний виджет того же окна: стандартный порядок наложения Qt, не между окнами).
    """
    if self.video_label:
      self.video_label.lower()
      if overlay:
        self.video_label.stackUnder(overlay)

  # ==================== КАТАЛОГ ====================

  def fetch_catalog(self, force=False):
    """Загружает (или читает из кеша) JSON-каталог и нормализует его.

    Args:
        force: игнорировать кеш и загрузить заново
    Returns:
        bool: True, если каталог загружен (сеть или кеш), иначе False
    """
    raw = None

    if not force and self._cache_file.exists():
      try:
        cached = json.loads(self._cache_file.read_text(encoding="utf-8"))
        age = time.time() - cached.get("_fetched_at", 0)
        if age < 24 * 3600 and cached.get("url") == self.catalog_url:
          raw = cached.get("data")
      except Exception:
        raw = None

    if raw is None:
      try:
        req = Request(
            self.catalog_url, headers={"User-Agent": "TVLauncher/1.0"}
        )
        with urlopen(req, timeout=10) as resp:
          raw = json.loads(resp.read().decode("utf-8"))
        self._cache_file.write_text(
            json.dumps({
                "url": self.catalog_url,
                "_fetched_at": time.time(),
                "data": raw,
            }),
            encoding="utf-8",
        )
      except Exception as e:
        self.last_error = f"Не удалось загрузить каталог: {e}"
        # Фоллбэк: попробуем использовать кеш, даже если он просрочен или от другого URL
        if self._cache_file.exists():
          try:
            cached = json.loads(self._cache_file.read_text(encoding="utf-8"))
            raw = cached.get("data")
          except Exception:
            raw = None

    if not raw:
      self.catalog = []
      return False

    # Нормализация: оставляем только записи с хотя бы одним полем url_*
    url_fields = ("url_4k_hdr", "url_4k", "url_1080p_hdr", "url_1080p")
    normalized = []
    for entry in raw:
      if not isinstance(entry, dict):
        continue
      if any(entry.get(f) for f in url_fields):
        normalized.append(entry)

    self.catalog = normalized
    return True

  def set_catalog_url(self, url):
    self.catalog_url = url or DEFAULT_CATALOG_URL

  def get_available_categories(self):
    """Возвращает список настроенных имен категорий (для UI)."""
    return list(self.category_keywords.keys())

  def _entry_text(self, entry):
    return (
        f"{entry.get('location', '')} {entry.get('title', '')}"
        f" {entry.get('author', '')}"
    ).lower()

  def _matches_categories(self, entry):
    if not self.categories:
      return True
    text = self._entry_text(entry)
    for cat in self.categories:
      keywords = self.category_keywords.get(cat, [cat.lower()])
      for k in keywords:
        # Граница слова: избегает частичных совпадений вроде «night» внутри
        # «midnight» или «stars» внутри «Sea Stars», когда ищется не то.
        # \s+ в шаблоне также поддерживает ключевые слова из нескольких слов,
        # например «night city» или «aurora night».
        pattern = (
            r"\b" + re.escape(k.lower()).replace(r"\ ", r"\s+") + r"\b"
        )
        if re.search(pattern, text):
          return True
    return False

  def get_filtered_entries(self):
    entries = [e for e in self.catalog if self._matches_categories(e)]
    # Исключает записи, URL которых (для текущего качества) уже помечены как нерабочие в сессии
    return [
        e for e in entries if self.pick_video_url(e) not in self._dead_urls
    ]

  def validate_catalog(
      self, max_workers=16, timeout=4, progress_callback=None
  ):
    """Проверяет параллельно (HEAD запросы, затем фоллбэк GET Range 0-0), какие URL

    каталога (для выбранного качества) доступны, и добавляет нерабочие в self._dead_urls.
    Вызывать после fetch_catalog(), обычно по нажатию «Обновить каталог» в настройках:
    это позволяет избежать обнаружения битых ссылок поодиночке в виде черного экрана во время смены обоев.

    Args:
        max_workers: количество параллельных потоков
        timeout: тайм-аут в секундах для каждого запроса
        progress_callback: необязательно, callback(checked, total) для обновления UI

    Returns:
        tuple (alive_count, dead_count)
    """
    entries = [e for e in self.catalog if self._matches_categories(e)]
    urls = [self.pick_video_url(e) for e in entries]
    urls = [u for u in urls if u]
    total = len(urls)
    checked = 0
    dead = 0

    def _check(url):
      try:
        req = Request(
            url,
            method="HEAD",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0"
                    " Safari/537.36"
                )
            },
        )
        with urlopen(req, timeout=timeout) as resp:
          return url, resp.status < 400
      except Exception:
        # Некоторые серверы не поддерживают HEAD: попробуем GET с минимальным диапазоном (Range)
        try:
          req = Request(
              url,
              headers={
                  "User-Agent": (
                      "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                      " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0"
                      " Safari/537.36"
                  ),
                  "Range": "bytes=0-0",
              },
          )
          with urlopen(req, timeout=timeout) as resp:
            return url, resp.status < 400
        except Exception:
          return url, False

    if not urls:
      return 0, 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
      futures = {executor.submit(_check, u): u for u in urls}
      for future in as_completed(futures):
        url, alive = future.result()
        checked += 1
        if not alive:
          self._dead_urls.add(url)
          dead += 1
        if progress_callback:
          progress_callback(checked, total)

    return total - dead, dead

  def pick_video_url(self, entry):
    """Выбирает лучший URL видео для записи в соответствии с настроенным качеством."""
    chain = QUALITY_CHAINS.get(self.quality, QUALITY_CHAINS["1080p"])
    for field in chain:
      url = entry.get(field)
      if url:
        return url
    return None

  # ==================== ВОСПРОИЗВЕДЕНИЕ ====================

  def initialize(self, overlay=None):
    """Подготавливает менеджер (оверлей, конфигурация).

    ФАКТИЧЕСКАЯ инициализация mpv переносится в start_deferred(), которую нужно
    вызывать, когда главное окно уже видимо (например, сразу после launcher.show()),
    иначе вставка по id окна может привязаться к еще недействительному дескриптору
    и выдать черный экран.
    """
    self.overlay = overlay
    if not self.enabled:
      return
    # Если родитель уже видим (например, реинициализация во время работы), действуем сразу.
    if self.parent.isVisible():
      self.start_deferred()

  def start_deferred(self):
    """Вызывать, когда главное окно гарантированно видимо."""
    if not self.enabled:
      return

    if not self._init_mpv():
      print(
          f"[VideoWallpaper] {self.last_error} — фоллбэк на статичные обои."
      )
      return

    self.resize_to_parent()
    self.stack_under(getattr(self, "overlay", None))

    if not self.catalog:
      self.fetch_catalog()

    self.start_rotation()

  def play_entry(self, entry):
    """Запускает воспроизведение конкретной записи из каталога."""
    if not self.available or not self.mpv:
      return False

    url = self.pick_video_url(entry)
    if not url:
      return False

    try:
      self.mpv.play(url)
      self.current_entry = entry
      # Увеличивает «токен поколения» (generation token): нужен вотчеру, чтобы понять,
      # проверяет ли он все еще ЭТО воспроизведение или за это время уже началось
      # другое (например, ручной пропуск).
      self._play_generation += 1
      my_generation = self._play_generation

      if self.video_label:
        self.video_label.show()
        self.stack_under(getattr(self, "overlay", None))

      if self._render_mode == "legacy":
        self._start_frame_grabbing()

      # Диагностика: через 3 сек. проверяем, есть ли у mpv действительные видеопараметры
      # (т.е. идет ли декодирование). Полезно для отделения проблем с сетью/декодированием
      # от проблем отображения/вставки.
      QTimer.singleShot(3000, self._log_playback_diagnostics)

      # Вотчер контроля работоспособности (failure-detection): мы больше не полагаемся
      # на события 'end-file' от mpv (их формат через python-mpv не является словарем,
      # как ожидалось, из-за чего битые ссылки никогда не обнаруживались -> постоянный
      # черный экран без повторных попыток). Вместо этого состояние mpv проверяется
      # напрямую по истечении разумного времени.
      QTimer.singleShot(
          4500, lambda: self._check_playback_health(entry, url, my_generation)
      )

      return True
    except Exception as e:
      self.last_error = (
          f"Ошибка воспроизведения ({entry.get('title', '?')}): {e}"
      )
      print(f"[VideoWallpaper] {self.last_error}")
      return False

  def _check_playback_health(self, entry, url, generation):
    """Вотчер: если через 4.5с после старта mpv все еще в статусе idle без video_params,

    ссылка считается нерабочей (404, неподдерживаемый формат, таймаут сети и т.д.),
    и происходит автоматический переход к следующей.
    """
    if not self.enabled:
      # Пользователь тем временем отключил видео-обои: этот вотчер был запланирован
      # РАНИЕЕ (play_entry запускает его через QTimer.singleShot) и не отменялся
      # функцией toggle_enabled(). Без этой проверки вызов mpv.stop() (вызываемый
      # при отключении) ошибочно принимался за «битую ссылку», и воспроизведение
      # возобновлялось само по себе через несколько секунд, как будто переключатель
      # не сработал.
      return
    if generation != self._play_generation:
      # За это время уже началось другое воспроизведение: ничего не делаем.
      return
    if not self.mpv:
      return

    try:
      healthy = (not self.mpv.core_idle) or (
          self.mpv.video_params is not None
      )
    except Exception:
      healthy = False

    if healthy:
      self._consecutive_failures = 0
      return

    # Ссылка нерабочая: помечаем ее и исключаем из будущих попыток.
    self._dead_urls.add(url)
    title = entry.get("title") or entry.get("location") or "?"
    print(f"[VideoWallpaper] Ссылка недоступна, пропуск: {title}")

    self._consecutive_failures += 1
    if self._consecutive_failures >= self._max_consecutive_failures:
      self.last_error = (
          "Слишком много недоступных видео подряд"
          f" ({self._consecutive_failures}). Автоматические попытки остановлены:"
          " попробуйте обновить каталог или сменить URL/категории."
      )
      print(f"[VideoWallpaper] {self.last_error}")
      self.stop_rotation()
      return

    if self._skip_timer is None:
      self._skip_timer = QTimer()
      self._skip_timer.setSingleShot(True)
      self._skip_timer.timeout.connect(self.play_random)
    self._skip_timer.start(300)

  def play_random(self):
    """Выбирает и воспроизводит случайное видео из отфильтрованного набора (избегая текущего)."""
    entries = self.get_filtered_entries()
    if not entries:
      self.last_error = "Нет доступных видео для выбранных категорий."
      return False

    if len(entries) > 1 and self.current_entry in entries:
      entries = [e for e in entries if e is not self.current_entry]

    entry = random.choice(entries)
    return self.play_entry(entry)

  def next_video(self):
    return self.play_random()

  # ==================== АВТОМАТИЧЕСКАЯ СМЕНА ====================

  def start_rotation(self):
    if not self.enabled or not self.available:
      return

    # Скрываем статические обои (никакие изображения не должны конкурировать с видео
    # за то же пространство) и останавливаем их смену.
    if self.background_manager:
      self.background_manager.suspend_for_video()

    self.play_random()

    # suspend_for_video() мог пересоздать HWND лаунчера (изменение windowFlags + showFullScreen),
    # что может временно вернуть его поверх видеоокна в порядке z-order. play_entry()
    # уже вызывает stack_under(), но повторный отложенный вызов перекрывает случай,
    # когда пересоздание HWND произошло с задержкой в один кадр.
    QTimer.singleShot(
        150, lambda: self.stack_under(getattr(self, "overlay", None))
    )

    if self.rotation_timer is None:
      self.rotation_timer = QTimer()
      self.rotation_timer.timeout.connect(self.next_video)
    self.rotation_timer.start(max(30, self.interval_seconds) * 1000)

  def stop_rotation(self):
    if self.rotation_timer:
      self.rotation_timer.stop()
    if self._skip_timer:
      self._skip_timer.stop()
    self._stop_frame_grabbing()

  def toggle_enabled(self, enabled):
    """Включает/выключает режим видео-обоев, координируясь с BackgroundManager."""
    self.enabled = enabled

    if enabled:
      if not self.available:
        if not self._init_mpv():
          print(f"[VideoWallpaper] {self.last_error}")
          self.enabled = False
          return False
        self.resize_to_parent()

      if self.video_label:
        self.video_label.show()
      self.stack_under(getattr(self, "overlay", None))

      if not self.catalog:
        self.fetch_catalog()

      self.start_rotation()
    else:
      self.stop_rotation()
      if self.mpv:
        try:
          self.mpv.stop()
        except Exception:
          pass
      if self.video_label:
        self.video_label.hide()
      # Восстанавливаем статические обои
      if self.background_manager:
        self.background_manager.resume_after_video()

    return True

  # ==================== ПАУЗА ПРИ ПОТЕРЕ ФОКУСА ЛАУНЧЕРОМ ====================

  def pause_for_app_focus(self):
    """Лаунчер потерял фокус (другое приложение на переднем плане):

    останавливаем декодирование/рендеринг/сеть без выгрузки mpv-потока,
    чтобы возобновление происходило мгновенно и не требовало повторной загрузки источника.
    """
    if not self.available or not self.mpv:
      return
    try:
      self.mpv.pause = True
    except Exception:
      pass
    if self.rotation_timer:
      self.rotation_timer.stop()
    if self._skip_timer:
      self._skip_timer.stop()
    self._stop_frame_grabbing()
    # ПРИМЕЧАНИЕ: мы не скрываем video_label. Приостановленный mpv оставляет
    # последний отрисованный кадр застывшим на экране (эквивалент статических обоев),
    # поэтому метка продолжает закрывать то же пространство, не выдавая на мгновение
    # то, что находится под ней (QMainWindow / старые статические обои), пока стороннее
    # приложение еще открывается. Сокрытие и повторный показ метки создавали видимое
    5# мерцание и дополнительную задержку именно в самый чувствительный моменты смены фокуса.

  def resume_from_app_focus(self):
    """Лаунчер вернул фокус: возобновляем воспроизведение видео-обоев (если были включены)."""
    if not self.enabled or not self.available or not self.mpv:
      return
    self._start_frame_grabbing()
    try:
      self.mpv.pause = False
    except Exception:
      pass
    if self.rotation_timer:
      self.rotation_timer.start(max(30, self.interval_seconds) * 1000)

  def set_interval(self, seconds):
    self.interval_seconds = max(30, seconds)
    if self.rotation_timer and self.rotation_timer.isActive():
      self.rotation_timer.start(self.interval_seconds * 1000)

  def set_quality(self, quality):
    if quality in QUALITY_CHAINS:
      self.quality = quality
      if self.current_entry and self.available:
        self.play_entry(self.current_entry)

  def set_categories(self, categories):
    self.categories = list(categories or [])

  def set_muted(self, muted):
    self.muted = muted
    if self.mpv:
      try:
        self.mpv.mute = muted
      except Exception:
        pass

  # ==================== КОНФИГУРАЦИЯ ====================

  def get_config(self):
    return {
        "enabled": self.enabled,
        "quality": self.quality,
        "interval_seconds": self.interval_seconds,
        "categories": self.categories,
        "catalog_url": self.catalog_url,
        "muted": self.muted,
        "volume": self.volume,
    }

  def load_config(self, config_data):
    cfg = (
        dict(config_data.get("video_wallpaper", {})) if config_data else {}
    )
    self.enabled = cfg.get("enabled", False)
    self.quality = cfg.get("quality", "1080p")
    self.interval_seconds = cfg.get("interval_seconds", 600)
    self.categories = cfg.get("categories", [])
    self.catalog_url = cfg.get("catalog_url", DEFAULT_CATALOG_URL)
    self.muted = cfg.get("muted", True)
    self.volume = cfg.get("volume", 0)

  # ==================== ОЧИСТКА РЕСУРСОВ ====================

  def cleanup(self):
    self.stop_rotation()
    if self._frame_thread:
      self._stop_frame_grabbing()
      self._frame_thread.quit()
      self._frame_thread.wait(2000)
      self._frame_thread = None
      self._frame_worker = None
    if self._render_mode == "gl" and self.video_label is not None:
      try:
        self.video_label.shutdown()
      except Exception:
        pass
    if self.mpv:
      try:
        self.mpv.terminate()
      except Exception:
        pass
      self.mpv = None
    if self.video_label:
      self.video_label.close()
      self.video_label.deleteLater()
      self.video_label = None
    self._render_mode = None
    self.available = False


# ==================== ФУНКЦИЯ ИНТЕГРАЦИИ ====================


def integrate_video_wallpaper(launcher_class):
  """Интегрирует VideoWallpaperManager в класс TVLauncher.

  Должна вызываться ПОСЛЕ integrate_background_manager (или иным способом
  обеспечивать существование self.background_manager к моменту создания менеджера).
  """
  original_init = launcher_class.__init__

  def new_init(self):
    original_init(self)
    from modules.video_wallpaper_manager import VideoWallpaperManager

    self.video_wallpaper_manager = VideoWallpaperManager(
        parent=self,
        config_data=self.config_data,
        assets_dir=self.assets_dir,
        background_manager=getattr(self, "background_manager", None),
    )
    # Вызывайте self.video_wallpaper_manager.initialize(overlay=self.overlay)
    # сразу после self.background_manager.initialize(...) в вашем showEvent/__init__.

  launcher_class.__init__ = new_init

  original_close = launcher_class.closeEvent

  def new_close_event(self, event):
    if hasattr(self, "video_wallpaper_manager"):
      self.video_wallpaper_manager.cleanup()
    original_close(self, event)

  launcher_class.closeEvent = new_close_event

  original_resize = getattr(launcher_class, "resizeEvent", None)

  def new_resize_event(self, event):
    if original_resize:
      original_resize(self, event)
    if hasattr(self, "video_wallpaper_manager"):
      self.video_wallpaper_manager.resize_to_parent()

  launcher_class.resizeEvent = new_resize_event

