"""
video_wallpaper_dialog.py

Диалог конфигурации для Живых видео-обоев (видеопоток в стиле Projectivy
Overflight). Предназначен для интеграции в существующий SettingsMenu с помощью
функции add_video_wallpaper_button_to_settings(self) — см. в конце файла.
"""

from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


QUALITY_LABELS = [
    ("1080p", "1080p"),
    ("1080p_hdr", "1080p HDR"),
    ("4k", "4K"),
    ("4k_hdr", "4K HDR"),
    ("auto", "Автоматически (адаптивно)"),
]


class VideoWallpaperSettingsDialog(QDialog):
  """Диалог для настройки видео-обоев в режиме стриминга."""

  def __init__(self, parent, video_manager, scaling=None):
    super().__init__(parent)
    self.video_manager = video_manager
    # Если масштабирование не передано, создаем фоллбэк-объект,
    # чтобы диалог оставался адаптивным даже при вызове из места,
    # где параметр scaling не передается явно.
    if scaling is None:
      from modules.responsive_scaling import ResponsiveScaling

      scaling = ResponsiveScaling()
    self.scaling = scaling
    s = self.scaling
    self.setWindowTitle("Видео-обои")
    self.setModal(True)
    self.resize(s.scale(600), s.scale(680))

    self.setStyleSheet(f"""
            QDialog {{ background-color: #1a1a1a; }}
            QLabel {{ color: white; font-size: {s.scale_font(13)}px; }}
            QComboBox, QSpinBox, QLineEdit {{
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #444;
                border-radius: {s.scale(5)}px;
                padding: {s.scale(5)}px;
                font-size: {s.scale_font(13)}px;
                min-height: {s.scale(22)}px;
            }}
            QPushButton {{
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #444;
                border-radius: {s.scale(6)}px;
                padding: {s.scale(8)}px {s.scale(14)}px;
                font-size: {s.scale_font(13)}px;
            }}
            QPushButton:hover {{ background-color: #3a3a3a; }}
            QCheckBox {{ color: white; font-size: {s.scale_font(13)}px; }}
            QCheckBox::indicator {{
                width: {s.scale(18)}px;
                height: {s.scale(18)}px;
            }}
        """)

    self._category_checkboxes = {}
    self._build_ui()
    self._load_from_manager()

  # ---------------------------------------------------------------

  def _section_title(self, text):
    lbl = QLabel(text)
    s = self.scaling
    lbl.setStyleSheet(
        f"font-size: {s.scale_font(15)}px; font-weight: bold; "
        f"color: #ffffff; margin-top: {s.scale(8)}px;"
    )
    return lbl

  def _build_ui(self):
    s = self.scaling
    layout = QVBoxLayout(self)
    layout.setSpacing(s.scale(12))
    layout.setContentsMargins(
        s.scale(16), s.scale(16), s.scale(16), s.scale(16)
    )

    # Активация
    self.enable_checkbox = QCheckBox("Включить стриминг видео-обоев")
    layout.addWidget(self.enable_checkbox)

    info = QLabel(
        "Видео транслируются по сети (без постоянной загрузки на диск). "
        "Требуется активное интернет-соединение."
    )
    info.setWordWrap(True)
    info.setStyleSheet(f"color: #999; font-size: {s.scale_font(11)}px;")
    layout.addWidget(info)

    # Качество
    layout.addWidget(self._section_title("Качество видео"))
    self.quality_combo = QComboBox()
    for key, label in QUALITY_LABELS:
      self.quality_combo.addItem(label, key)
    layout.addWidget(self.quality_combo)

    # Интервал смены
    layout.addWidget(self._section_title("Менять видео каждые (минут)"))
    interval_row = QHBoxLayout()
    self.interval_spin = QSpinBox()
    self.interval_spin.setRange(1, 180)
    self.interval_spin.setSuffix(" мин")
    interval_row.addWidget(self.interval_spin)
    interval_row.addStretch()
    layout.addLayout(interval_row)

    # Аудио
    self.mute_checkbox = QCheckBox("Без звука (рекомендуется для обоев)")
    layout.addWidget(self.mute_checkbox)

    # Категории
    layout.addWidget(
        self._section_title("Категории (если ничего не выбрано — все)")
    )
    cat_scroll = QScrollArea()
    cat_scroll.setWidgetResizable(True)
    cat_scroll.setFixedHeight(s.scale(160))
    cat_scroll.setStyleSheet(
        f"QScrollArea {{ border: 1px solid #444; border-radius: {s.scale(6)}px;"
        " }}"
    )

    cat_container = QWidget()
    cat_grid = QGridLayout(cat_container)
    cat_grid.setSpacing(s.scale(6))
    categories = self.video_manager.get_available_categories()
    for i, cat in enumerate(categories):
      cb = QCheckBox(cat)
      self._category_checkboxes[cat] = cb
      cat_grid.addWidget(cb, i // 2, i % 2)
    cat_scroll.setWidget(cat_container)
    layout.addWidget(cat_scroll)

    # Пользовательский URL каталога
    layout.addWidget(self._section_title("URL JSON-каталога"))
    self.catalog_url_edit = QLineEdit()
    layout.addWidget(self.catalog_url_edit)

    reset_url_btn = QPushButton("Восстановить URL по умолчанию (Projectivy)")
    reset_url_btn.clicked.connect(self._reset_catalog_url)
    layout.addWidget(reset_url_btn)

    # Состояние / тест
    self.status_label = QLabel("")
    self.status_label.setWordWrap(True)
    self.status_label.setStyleSheet(
        f"color: #ffb74d; font-size: {s.scale_font(11)}px;"
    )
    layout.addWidget(self.status_label)

    test_row = QHBoxLayout()
    test_row.setSpacing(s.scale(8))
    refresh_btn = QPushButton("Обновить каталог")
    refresh_btn.clicked.connect(self._refresh_catalog)
    test_row.addWidget(refresh_btn)

    test_btn = QPushButton("Тест / Воспроизвести видео")
    test_btn.clicked.connect(self._test_video)
    test_row.addWidget(test_btn)
    layout.addLayout(test_row)

    layout.addStretch()

    # Кнопки внизу
    btn_row = QHBoxLayout()
    btn_row.setSpacing(s.scale(8))
    cancel_btn = QPushButton("Отмена")
    cancel_btn.clicked.connect(self.reject)
    save_btn = QPushButton("Сохранить")
    save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: {s.scale(6)}px;
                padding: {s.scale(8)}px {s.scale(14)}px;
                font-size: {s.scale_font(13)}px;
                color: white;
            }}
            QPushButton:hover {{ background-color: #3a3a3a; }}
        """)
    save_btn.clicked.connect(self._save_and_close)
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(save_btn)
    layout.addLayout(btn_row)

  # ---------------------------------------------------------------

  def _load_from_manager(self):
    vm = self.video_manager
    self.enable_checkbox.setChecked(vm.enabled)

    idx = self.quality_combo.findData(vm.quality)
    if idx >= 0:
      self.quality_combo.setCurrentIndex(idx)

    self.interval_spin.setValue(max(1, vm.interval_seconds // 60))
    self.mute_checkbox.setChecked(vm.muted)
    self.catalog_url_edit.setText(vm.catalog_url)

    for cat, cb in self._category_checkboxes.items():
      cb.setChecked(cat in vm.categories)

    if not vm.available and vm.enabled:
      self.status_label.setText(
          f"⚠ mpv недоступен: {vm.last_error or 'библиотека не найдена'}"
      )

  def _reset_catalog_url(self):
    from modules.video_wallpaper_manager import DEFAULT_CATALOG_URL

    self.catalog_url_edit.setText(DEFAULT_CATALOG_URL)

  def _selected_categories(self):
    return [
        cat for cat, cb in self._category_checkboxes.items() if cb.isChecked()
    ]

  def _refresh_catalog(self):
    self.video_manager.set_catalog_url(self.catalog_url_edit.text().strip())
    self.video_manager._dead_urls.clear()
    self.video_manager._consecutive_failures = 0
    ok = self.video_manager.fetch_catalog(force=True)
    if ok:
      self.status_label.setStyleSheet("color: #81c784; font-size: 11px;")
      self.status_label.setText(
          f"Каталог загружен: {len(self.video_manager.catalog)} видео. Идет"
          " проверка ссылок..."
      )
      from PyQt6.QtWidgets import QApplication as _QApp

      _QApp.processEvents()

      def _progress(checked, total):
        self.status_label.setText(f"Проверка ссылок: {checked}/{total}...")
        _QApp.processEvents()

      alive, dead = self.video_manager.validate_catalog(
          progress_callback=_progress
      )
      self.status_label.setStyleSheet("color: #81c784; font-size: 11px;")
      self.status_label.setText(
          f"✓ Каталог обновлен: {alive} рабочих видео, {dead} недоступных ссылок."
      )
    else:
      self.status_label.setStyleSheet("color: #e57373; font-size: 11px;")
      self.status_label.setText(f"✗ {self.video_manager.last_error}")

  def _test_video(self):
    vm = self.video_manager

    # Временно применяем текущие параметры из диалога для тестирования
    vm.set_catalog_url(self.catalog_url_edit.text().strip())
    vm.set_quality(self.quality_combo.currentData())
    vm.set_categories(self._selected_categories())
    vm.set_muted(self.mute_checkbox.isChecked())

    if not vm.available:
      if not vm._init_mpv():
        QMessageBox.warning(
            self,
            "Видео-обои недоступны",
            f"Не удалось инициализировать mpv:\n{vm.last_error}\n\nУбедитесь,"
            " что установлен python-mpv и присутствует библиотека libmpv.",
        )
        return
      vm.resize_to_parent()
      vm.stack_under(getattr(vm, "overlay", None))

    if not vm.catalog:
      vm.fetch_catalog()

    # Приводим тест к тому же поведению, что и реальная смена видео:
    # приостанавливаем статический фон перед воспроизведением, иначе во время
    # теста он остается «активным» на заднем плане, и визуальный результат
    # отличается от того, что будет после нажатия кнопки «Сохранить».
    if vm.background_manager:
      vm.background_manager.suspend_for_video()

    ok = vm.play_random()
    if ok and vm.current_entry:
      title = (
          vm.current_entry.get("title")
          or vm.current_entry.get("location")
          or "видео"
      )
      self.status_label.setStyleSheet("color: #81c784; font-size: 11px;")
      self.status_label.setText(f"▶ Воспроизведение: {title}")
    else:
      self.status_label.setStyleSheet("color: #e57373; font-size: 11px;")
      self.status_label.setText(
          f"✗ {vm.last_error || 'Нет доступных видео.'}"
      )

  def _save_and_close(self):
    vm = self.video_manager
    vm.set_catalog_url(self.catalog_url_edit.text().strip())
    vm.set_quality(self.quality_combo.currentData())
    vm.set_interval(self.interval_spin.value() * 60)
    vm.set_categories(self._selected_categories())
    vm.set_muted(self.mute_checkbox.isChecked())

    want_enabled = self.enable_checkbox.isChecked()
    if want_enabled != vm.enabled:
      success = vm.toggle_enabled(want_enabled)
      if not success and want_enabled:
        QMessageBox.warning(
            self,
            "Видео-обои недоступны",
            f"Не удалось активировать видео-обои:\n{vm.last_error}",
        )
    elif want_enabled and vm.available:
      # Уже активны: перезапускаем смену с новыми параметрами
      vm.start_rotation()

    # Сохраняем на диск. Без этого все изменения, сделанные в диалоге
    # (качество, интервал, категории, включение/выключение и т.д.), останутся
    # только в памяти менеджера vm и пропадут при перезапуске лаунчера — точно
    # так же, как это сделано для остальных настроек в settings_menu.py, которые
    # обновляют launcher.config_data['video_wallpaper'] и вызывают
    # launcher.save_config().
    launcher = getattr(vm, "parent", None)
    if launcher is not None and hasattr(launcher, "config_data"):
      launcher.config_data["video_wallpaper"] = vm.get_config()
    if launcher is not None and hasattr(launcher, "save_config"):
      launcher.save_config()

    self.accept()


# ==================== ИНТЕГРАЦИЯ В SETTINGS MENU ====================


def add_video_wallpaper_button_to_settings(
    settings_menu, launcher, layout, menu_items, icon_dir
):

  def _open_dialog():
    current_launcher = settings_menu.launcher
    if current_launcher is None or not hasattr(
        current_launcher, "video_wallpaper_manager"
    ):
      QMessageBox.warning(
          settings_menu,
          "Недоступно",
          "Модуль video_wallpaper_manager не интегрирован в лаунчер.",
      )
      return
    dlg = VideoWallpaperSettingsDialog(
        current_launcher,
        current_launcher.video_wallpaper_manager,
        getattr(settings_menu, "scaling", None),
    )
    dlg.exec()

  btn = settings_menu._create_menu_button(
      "Видео-обои",
      "Живые видео-обои в стриминге (в стиле Projectivy)",
      _open_dialog,
      str(Path(icon_dir) / "video.png"),
  )
  layout.addWidget(btn)
  menu_items.append(btn)
  return btn

