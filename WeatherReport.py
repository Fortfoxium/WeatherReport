import sys
import json
import requests
import threading
import time
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QSystemTrayIcon, 
                             QMenu, QMessageBox, QLineEdit, QGroupBox, QFormLayout,
                             QDialog, QDialogButtonBox, QGridLayout)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QRect
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QLinearGradient, QColor, QBrush
import os

# Конфигурация
CONFIG_FILE = "weather_config.json"
ICON_PATH = "icon.png"
UPDATE_INTERVAL = 300  # Интервал обновления погоды в секундах (5 минут)

# Глобальные переменные для настроек
ACCESS_KEY = ""
LAT = 55.7558  # Широта (Москва по умолчанию)
LON = 37.6173  # Долгота (Москва по умолчанию)

def load_config():
    """Загрузка настроек из файла"""
    global ACCESS_KEY, LAT, LON
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                ACCESS_KEY = config.get('api_key', '')
                LAT = config.get('lat', 55.7558)
                LON = config.get('lon', 37.6173)
                return True
    except Exception as e:
        print(f"Ошибка загрузки настроек: {e}")
    return False

def save_config(api_key, lat, lon):
    """Сохранение настроек в файл"""
    try:
        config = {
            'api_key': api_key,
            'lat': lat,
            'lon': lon
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Ошибка сохранения настроек: {e}")
        return False

def get_weather_emoji(condition):
    """Получение эмодзи для погодных условий"""
    weather_emoji = {
        'clear': '☀️', 'partly-cloudy': '⛅', 'cloudy': '☁️',
        'overcast': '☁️', 'light-rain': '🌧️', 'rain': '🌧️',
        'heavy-rain': '🌧️', 'showers': '🌧️', 'light-snow': '🌨️',
        'snow': '🌨️', 'heavy-snow': '🌨️', 'thunderstorm': '⛈️',
        'fog': '🌫️', 'mist': '🌫️'
    }
    return weather_emoji.get(condition, '🌡️')

def get_condition_name(condition):
    """Получение названия погодных условий на русском"""
    conditions = {
        'clear': 'Ясно', 'partly-cloudy': 'Переменная облачность',
        'cloudy': 'Облачно', 'overcast': 'Пасмурно',
        'light-rain': 'Небольшой дождь', 'rain': 'Дождь',
        'heavy-rain': 'Сильный дождь', 'showers': 'Ливень',
        'light-snow': 'Небольшой снег', 'snow': 'Снег',
        'heavy-snow': 'Сильный снег', 'thunderstorm': 'Гроза',
        'fog': 'Туман', 'mist': 'Дымка'
    }
    return conditions.get(condition, condition)

def get_uv_index_description(uv_index):
    """Описание УФ-индекса"""
    if uv_index <= 2:
        return "Низкий", "🟢"
    elif uv_index <= 5:
        return "Средний", "🟡"
    elif uv_index <= 7:
        return "Высокий", "🟠"
    elif uv_index <= 10:
        return "Очень высокий", "🔴"
    else:
        return "Экстремальный", "🟣"

class GradientWidget(QWidget):
    """Виджет с градиентным фоном"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_color = QColor(135, 206, 235)  # Голубой (SkyBlue)
        self.end_color = QColor(255, 255, 255)    # Белый
        
    def paintEvent(self, event):
        """Отрисовка градиента"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Создаем вертикальный градиент от голубого к белому
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, self.start_color)
        gradient.setColorAt(1.0, self.end_color)
        
        painter.fillRect(self.rect(), QBrush(gradient))

class WeatherWorker(QThread):
    """Поток для получения данных о погоде"""
    weather_updated = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, lat, lon, api_key):
        super().__init__()
        self.lat = lat
        self.lon = lon
        self.api_key = api_key
        self.running = True
        
    def run(self):
        while self.running:
            if self.api_key:
                try:
                    weather_data = self.get_weather()
                    self.weather_updated.emit(weather_data)
                except Exception as e:
                    self.error_occurred.emit(str(e))
            else:
                self.error_occurred.emit("API ключ не установлен")
            
            # Ждем перед следующим обновлением
            for _ in range(UPDATE_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)
    
    def stop(self):
        """Остановка потока"""
        self.running = False
        
    def get_weather(self):
        """Получение данных о погоде из REST API Яндекс"""
        if not self.api_key:
            raise Exception("API ключ не установлен")
        
        # Используем REST API вместо GraphQL
        url = f"https://api.weather.yandex.ru/v2/forecast"
        params = {
            "lat": self.lat,
            "lon": self.lon,
            "limit": 1,  # Только текущая погода
            "hours": False  # Не нужны почасовые данные
        }
        headers = {
            "X-Yandex-Weather-Key": self.api_key
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                fact = data.get('fact', {})
                
                if fact:
                    return {
                        'temperature': fact.get('temp'),
                        'condition': fact.get('condition'),
                        'humidity': fact.get('humidity'),
                        'pressure': fact.get('pressure_mm'),  # В REST API давление уже в мм рт. ст.
                        'windSpeed': fact.get('wind_speed'),
                        'uvIndex': fact.get('uv_index'),
                        'feels_like': fact.get('feels_like'),  # Ощущается как
                        'timestamp': datetime.now()
                    }
                else:
                    raise Exception("Не удалось получить данные о погоде из ответа API")
            elif response.status_code == 403:
                raise Exception("Неверный API ключ. Проверьте ключ доступа Яндекс Погоды")
            elif response.status_code == 400:
                raise Exception("Неверный запрос. Проверьте координаты")
            else:
                raise Exception(f"Ошибка API: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка сети: {str(e)}")

class ClockWidget(QLabel):
    """Виджет для отображения часов"""
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        font = QFont("Arial", 48, QFont.Bold)
        self.setFont(font)
        self.setStyleSheet("color: #2c3e50;")  # Темно-синий цвет для текста
        self.update_clock()
        
        # Таймер для обновления часов каждую секунду
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_clock)
        self.timer.start(1000)
    
    def update_clock(self):
        """Обновление времени"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.setText(current_time)

class SettingsDialog(QDialog):
    """Диалог настроек (отдельное окно)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Настройки")
        self.setGeometry(200, 200, 450, 350)
        self.setFixedSize(450, 350)
        self.setWindowModality(Qt.ApplicationModal)
        
        # Устанавливаем иконку окна
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        
        layout = QVBoxLayout()
        
        # Группа API настроек
        api_group = QGroupBox("Настройки API Яндекс Погоды")
        api_layout = QFormLayout()
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Введите ваш API ключ Яндекс Погоды")
        if ACCESS_KEY:
            self.api_key_input.setText(ACCESS_KEY)
        api_layout.addRow("API ключ:", self.api_key_input)
        
        # Информация о получении ключа
        info_label = QLabel("Как получить ключ:\n1. Перейдите на https://developer.weather.yandex.ru/\n2. Зарегистрируйтесь\n3. Создайте ключ в личном кабинете\n\n⚠️ Важно: Используйте ключ для REST API (v2)")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        api_layout.addRow(info_label)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Группа координат
        coord_group = QGroupBox("Координаты")
        coord_layout = QFormLayout()
        
        self.lat_input = QLineEdit()
        self.lat_input.setText(str(LAT))
        self.lat_input.setPlaceholderText("Широта (например: 55.7558)")
        coord_layout.addRow("Широта:", self.lat_input)
        
        self.lon_input = QLineEdit()
        self.lon_input.setText(str(LON))
        self.lon_input.setPlaceholderText("Долгота (например: 37.6173)")
        coord_layout.addRow("Долгота:", self.lon_input)
        
        # Подсказка по координатам
        coord_hint = QLabel("💡 Найдите координаты города на https://yandex.ru/maps")
        coord_hint.setStyleSheet("color: gray; font-size: 9px;")
        coord_layout.addRow(coord_hint)
        
        coord_group.setLayout(coord_layout)
        layout.addWidget(coord_group)
        
        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
    def save_settings(self):
        """Сохранение настроек"""
        global ACCESS_KEY, LAT, LON
        
        api_key = self.api_key_input.text().strip()
        try:
            lat = float(self.lat_input.text())
            lon = float(self.lon_input.text())
            
            if api_key:
                ACCESS_KEY = api_key
                LAT = lat
                LON = lon
                
                # Сохраняем в файл
                if save_config(api_key, lat, lon):
                    # Перезапускаем рабочий поток с новыми настройками
                    if hasattr(self.parent, 'weather_worker') and self.parent.weather_worker:
                        self.parent.weather_worker.stop()
                        self.parent.weather_worker.wait()
                    
                    self.parent.init_weather()
                    QMessageBox.information(self, "Успех", "Настройки сохранены и применены")
                    self.accept()
                else:
                    QMessageBox.warning(self, "Ошибка", "Не удалось сохранить настройки")
            else:
                QMessageBox.warning(self, "Ошибка", "Введите API ключ")
                
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Неверный формат координат")

class WeatherApp(QMainWindow):
    """Главное окно приложения"""
    def __init__(self):
        super().__init__()
        self.weather_worker = None
        self.init_ui()
        self.init_tray()
        self.init_weather()
        
    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("WeatherReport")
        self.setGeometry(100, 100, 500, 600)
        self.setFixedSize(500, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        
        # Устанавливаем иконку окна
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
        
        # Создаем центральный виджет с градиентом
        central_widget = GradientWidget()
        self.setCentralWidget(central_widget)
        
        # Создаем контейнер для содержимого с прозрачным фоном
        content_widget = QWidget()
        content_widget.setAttribute(Qt.WA_TranslucentBackground)
        content_layout = QVBoxLayout(content_widget)
        
        # Часы
        self.clock = ClockWidget()
        content_layout.addWidget(self.clock)
        
        # Виджет погоды с сеткой
        weather_widget = QWidget()
        weather_widget.setStyleSheet("background-color: rgba(255, 255, 255, 0.7); border-radius: 15px; padding: 10px;")
        weather_layout = QGridLayout(weather_widget)
        weather_layout.setSpacing(15)
        
        # Температура
        self.temp_label = QLabel("Загрузка...")
        self.temp_label.setAlignment(Qt.AlignCenter)
        temp_font = QFont("Arial", 48, QFont.Bold)
        self.temp_label.setFont(temp_font)
        self.temp_label.setStyleSheet("color: #2c3e50;")
        weather_layout.addWidget(self.temp_label, 0, 0, 1, 2)
        
        # Ощущается как
        self.feels_like_label = QLabel("")
        self.feels_like_label.setAlignment(Qt.AlignCenter)
        feels_font = QFont("Arial", 12)
        self.feels_like_label.setFont(feels_font)
        self.feels_like_label.setStyleSheet("color: #34495e;")
        weather_layout.addWidget(self.feels_like_label, 1, 0, 1, 2)
        
        # Погодные условия
        self.condition_label = QLabel("")
        self.condition_label.setAlignment(Qt.AlignCenter)
        condition_font = QFont("Arial", 16)
        self.condition_label.setFont(condition_font)
        self.condition_label.setStyleSheet("color: #2c3e50;")
        weather_layout.addWidget(self.condition_label, 2, 0, 1, 2)
        
        # Влажность
        humidity_widget = QWidget()
        humidity_layout = QHBoxLayout(humidity_widget)
        humidity_layout.addWidget(QLabel("💧 Влажность:"))
        self.humidity_label = QLabel("--%")
        humidity_layout.addWidget(self.humidity_label)
        humidity_layout.addStretch()
        weather_layout.addWidget(humidity_widget, 3, 0)
        
        # Давление
        pressure_widget = QWidget()
        pressure_layout = QHBoxLayout(pressure_widget)
        pressure_layout.addWidget(QLabel("🌡️ Давление:"))
        self.pressure_label = QLabel("-- мм рт. ст.")
        pressure_layout.addWidget(self.pressure_label)
        pressure_layout.addStretch()
        weather_layout.addWidget(pressure_widget, 3, 1)
        
        # Ветер
        wind_widget = QWidget()
        wind_layout = QHBoxLayout(wind_widget)
        wind_layout.addWidget(QLabel("💨 Ветер:"))
        self.wind_label = QLabel("-- м/с")
        wind_layout.addWidget(self.wind_label)
        wind_layout.addStretch()
        weather_layout.addWidget(wind_widget, 4, 0)
        
        # УФ-индекс
        uv_widget = QWidget()
        uv_layout = QHBoxLayout(uv_widget)
        uv_layout.addWidget(QLabel("☀️ УФ-индекс:"))
        self.uv_label = QLabel("--")
        uv_layout.addWidget(self.uv_label)
        uv_layout.addStretch()
        weather_layout.addWidget(uv_widget, 4, 1)
        
        # Время последнего обновления
        self.update_time_label = QLabel("")
        self.update_time_label.setAlignment(Qt.AlignCenter)
        self.update_time_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        weather_layout.addWidget(self.update_time_label, 5, 0, 1, 2)
        
        content_layout.addWidget(weather_widget)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Обновить погоду")
        self.refresh_btn.clicked.connect(self.manual_refresh)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        buttons_layout.addWidget(self.refresh_btn)
        
        settings_btn = QPushButton("⚙️ Настройки")
        settings_btn.clicked.connect(self.open_settings)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        buttons_layout.addWidget(settings_btn)
        
        exit_btn = QPushButton("🚪 Выход")
        exit_btn.clicked.connect(self.exit_app)
        exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        buttons_layout.addWidget(exit_btn)
        
        content_layout.addLayout(buttons_layout)
        
        # Устанавливаем основной контейнер в центральный виджет
        main_layout = QVBoxLayout(central_widget)
        main_layout.addWidget(content_widget)
        
    def init_tray(self):
        """Инициализация системного трея"""
        if os.path.exists(ICON_PATH):
            icon = QIcon(ICON_PATH)
        else:
            icon = QIcon()
            print(f"Предупреждение: файл иконки {ICON_PATH} не найден")
        
        self.tray_icon = QSystemTrayIcon(icon, self)
        
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Показать")
        show_action.triggered.connect(self.show_window)
        settings_action = tray_menu.addAction("Настройки")
        settings_action.triggered.connect(self.open_settings)
        tray_menu.addSeparator()
        exit_action = tray_menu.addAction("Выход")
        exit_action.triggered.connect(self.exit_app)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("Погода и часы")
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        
        self.hide()
        
    def init_weather(self):
        """Инициализация получения погоды"""
        if ACCESS_KEY:
            if self.weather_worker:
                self.weather_worker.stop()
                self.weather_worker.wait()
            
            self.weather_worker = WeatherWorker(LAT, LON, ACCESS_KEY)
            self.weather_worker.weather_updated.connect(self.update_weather)
            self.weather_worker.error_occurred.connect(self.show_error)
            self.weather_worker.start()
            self.refresh_btn.setEnabled(True)
            self.temp_label.setText("Загрузка...")
        else:
            self.temp_label.setText("⚙️ Нажмите 'Настройки'")
            self.refresh_btn.setEnabled(False)
        
        self.tray_timer = QTimer()
        self.tray_timer.timeout.connect(self.update_tray_tooltip)
        self.tray_timer.start(60000)
        
    def update_weather(self, weather_data):
        """Обновление отображения погоды"""
        # Температура
        temp = weather_data.get('temperature')
        if temp is not None:
            self.temp_label.setText(f"{temp}°C")
        
        # Ощущается как
        feels_like = weather_data.get('feels_like')
        if feels_like is not None:
            self.feels_like_label.setText(f"Ощущается как {feels_like}°C")
        
        # Погодные условия
        condition = weather_data.get('condition')
        if condition:
            emoji = get_weather_emoji(condition)
            condition_name = get_condition_name(condition)
            self.condition_label.setText(f"{emoji} {condition_name}")
        
        # Влажность
        humidity = weather_data.get('humidity')
        if humidity is not None:
            self.humidity_label.setText(f"{humidity}%")
        
        # Давление (уже в мм рт. ст.)
        pressure = weather_data.get('pressure')
        if pressure is not None:
            self.pressure_label.setText(f"{pressure} мм рт. ст.")
        
        # Ветер
        wind_speed = weather_data.get('windSpeed')
        if wind_speed is not None:
            self.wind_label.setText(f"{wind_speed} м/с")
        
        # УФ-индекс
        uv_index = weather_data.get('uvIndex')
        if uv_index is not None:
            uv_desc, uv_emoji = get_uv_index_description(uv_index)
            self.uv_label.setText(f"{uv_emoji} {uv_index} ({uv_desc})")
        
        # Обновляем время последнего обновления
        update_time = weather_data.get('timestamp', datetime.now()).strftime("%H:%M:%S")
        self.update_time_label.setText(f"Обновлено: {update_time}")
        
        # Обновляем подсказку в трее
        self.update_tray_tooltip()
        
    def update_tray_tooltip(self):
        """Обновление всплывающей подсказки в трее"""
        temp_text = self.temp_label.text()
        condition_text = self.condition_label.text()
        
        if temp_text not in ["Загрузка...", "⚙️ Нажмите 'Настройки'", "❌ Ошибка загрузки", "⚙️ Настройте API ключ", "❌ Неверный API ключ"]:
            current_time = datetime.now().strftime("%H:%M:%S")
            tooltip = f"{current_time}\n{temp_text}\n{condition_text}"
            self.tray_icon.setToolTip(tooltip)
        
    def manual_refresh(self):
        """Ручное обновление погоды"""
        if ACCESS_KEY and self.weather_worker:
            self.temp_label.setText("Обновление...")
            refresh_thread = threading.Thread(target=self.force_refresh)
            refresh_thread.daemon = True
            refresh_thread.start()
        
    def force_refresh(self):
        """Принудительное обновление"""
        try:
            weather_data = self.weather_worker.get_weather()
            self.update_weather(weather_data)
        except Exception as e:
            self.show_error(str(e))
        
    def show_error(self, error_msg):
        """Показ ошибки"""
        if "Неверный API ключ" in error_msg:
            QMessageBox.warning(self, "Ошибка", f"{error_msg}\n\nПожалуйста, проверьте API ключ в настройках")
            self.temp_label.setText("❌ Неверный API ключ")
            self.condition_label.setText("")
        elif "API ключ не установлен" in error_msg:
            self.temp_label.setText("⚙️ Настройте API ключ")
            self.condition_label.setText("")
        else:
            QMessageBox.warning(self, "Ошибка", f"Не удалось получить данные о погоде:\n{error_msg}")
            self.temp_label.setText("❌ Ошибка загрузки")
            self.condition_label.setText("")
        
    def open_settings(self):
        """Открытие окна настроек"""
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec_()
        
    def show_window(self):
        """Показ главного окна"""
        self.show()
        self.activateWindow()
        self.raise_()
        
    def on_tray_activated(self, reason):
        """Обработчик клика по иконке в трее"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()
        elif reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()
                
    def exit_app(self):
        """Выход из приложения"""
        if self.weather_worker:
            self.weather_worker.stop()
            self.weather_worker.wait()
        self.tray_icon.hide()
        QApplication.quit()
        
    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        event.ignore()
        self.hide()

def main():
    # Загружаем сохраненные настройки
    load_config()
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))
    
    window = WeatherApp()
    
    if not ACCESS_KEY:
        QMessageBox.information(window, "Добро пожаловать", 
                               "Для работы приложения необходимо настроить API ключ Яндекс Погоды.\n\n"
                               "1. Перейдите на https://developer.weather.yandex.ru/\n"
                               "2. Зарегистрируйтесь\n"
                               "3. Создайте ключ (REST API)\n"
                               "4. Введите ключ в настройках\n\n"
                               "⚠️ Важно: Используйте бесплатный тариф, он работает через REST API")
        window.open_settings()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
