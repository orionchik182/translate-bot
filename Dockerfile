# Используем официальный образ Python
FROM python:3.12

# Устанавливаем необходимые системные пакеты
RUN apt-get update && apt-get install -y \
    libuuid1 \
    libasound2 \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Указываем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Команда для запуска приложения
CMD ["python", "main.py"]