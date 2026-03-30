# weather_app.py
import pystray
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw
import requests
import threading
import tkinter as tk
from tkinter import messagebox
import json
import os

class WeatherApp:
    def __init__(self):
        self.api_key = "YOUR_API_KEY"  # Замените на ваш API ключ
        self.city = "Moscow"
        self.weather_data = None
        self.window = None
        
        # Создаем иконку для трея
        self.icon = Icon(
            "WeatherApp",
            self.create_icon_image(),
            "Погода",
            menu=self.create_menu()
        )
        
    def create_icon_image(self):
        """Создает иконку для трея"""
        image = Image.new('RGB', (64, 64), 'blue')
        draw = ImageDraw.Draw(image)
        draw.ellipse([10, 10, 54, 54], fill='yellow')
        return image
    
    def create_menu(self):
        """Создает меню трея"""
        return Menu(
            MenuItem('Показать погоду', self.show_weather_window, default=True),
            MenuItem('Обновить', self.update_weather),
            MenuItem('Выход', self.exit_app)
        )
    
    def get_weather(self):
        """Получает данные о погоде"""
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={self.city}&appid={self.api_key}&units=metric&lang=ru"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            self.weather_data = response.json()
            return True
        except Exception as e:
            print(f"Ошибка получения погоды: {e}")
            return False
    
    def show_weather_window(self, icon=None, item=None):
        """Показывает окно с погодой"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return
        
        if not self.weather_data:
            self.update_weather()
        
        self.window = tk.Tk()
        self.window.title("Погода")
        self.window.geometry("300x200")
        self.window.resizable(False, False)
        
        # Обработчик закрытия окна
        self.window.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        self.update_weather_display()
        
        # Показываем окно поверх других
        self.window.attributes('-topmost', True)
        self.window.after(100, lambda: self.window.attributes('-topmost', False))
        
        self.window.mainloop()
    
    def hide_window(self):
        """Скрывает окно вместо закрытия"""
        if self.window:
            self.window.withdraw()
    
    def update_weather_display(self):
        """Обновляет отображение погоды"""
        if not self.weather_data:
            label = tk.Label(
                self.window, 
                text="Нет данных о погоде", 
                font=("Arial", 14)
            )
            label.pack(pady=50)
            return
        
        data = self.weather_data
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        description = data['weather'][0]['description']
        city = data['name']
        
        # Создаем виджеты
        frame = tk.Frame(self.window)
        frame.pack(pady=20)
        
        tk.Label(
            frame, 
            text=f"🌤 {city}", 
            font=("Arial", 16, "bold")
        ).pack(pady=5)
        
        tk.Label(
            frame, 
            text=f"{temp:.1f}°C", 
            font=("Arial", 24)
        ).pack(pady=5)
        
        tk.Label(
            frame, 
            text=f"{description.capitalize()}", 
            font=("Arial", 12)
        ).pack(pady=5)
        
        tk.Label(
            frame, 
            text=f"Ощущается как: {feels_like:.1f}°C", 
            font=("Arial", 10),
            fg="gray"
        ).pack(pady=5)
        
        # Кнопка обновления
        tk.Button(
            self.window,
            text="🔄 Обновить",
            command=self.update_weather
        ).pack(pady=10)
    
    def update_weather(self, icon=None, item=None):
        """Обновляет данные о погоде"""
        threading.Thread(target=self._update_weather_thread, daemon=True).start()
    
    def _update_weather_thread(self):
        """Поток для обновления погоды"""
        if self.get_weather():
            if self.window and self.window.winfo_exists():
                self.window.after(0, self.update_weather_display)
            
            # Обновляем заголовок трея
            if self.weather_data:
                temp = self.weather_data['main']['temp']
                self.icon.title = f"🌤 {temp:.0f}°C"
    
    def exit_app(self, icon=None, item=None):
        """Выход из приложения"""
        if self.window:
            self.window.destroy()
        self.icon.stop()
    
    def run(self):
        """Запускает приложение"""
        # Получаем погоду при старте
        self.update_weather()
        
        # Запускаем иконку в трее
        self.icon.run()

if __name__ == "__main__":
    app = WeatherApp()
    app.run()
