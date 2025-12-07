# Telegram Bot для создания конспектов

Бот на aiogram, который собирает конспекты из фотографий тетради и генерирует краткие резюме.

## Возможности

- Прием фотографий из тетради
- Автоматическое распознавание текста (OCR) с помощью Google Cloud Vision API или Tesseract
- Сбор конспекта из нескольких фото
- Генерация краткого резюме с помощью OpenAI GPT

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. (Опционально) Настройте Google Cloud Vision API для лучшего распознавания:
   - Создайте проект в [Google Cloud Console](https://console.cloud.google.com/)
   - Включите Cloud Vision API
   - Создайте сервисный аккаунт и скачайте JSON ключ
   - Установите переменную окружения: `export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/key.json"`
   - Или добавьте путь к ключу в `.env`: `GOOGLE_APPLICATION_CREDENTIALS=path/to/your/key.json`
   
   Если Google Vision API не настроен, будет использоваться Tesseract OCR.

4. Установите Tesseract OCR (используется как fallback, если Google Vision недоступен):
   - Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-rus`
   - macOS: `brew install tesseract tesseract-lang`
   - Windows: Скачайте установщик с [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

5. Создайте файл `.env` в корне проекта:
```
BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_APPLICATION_CREDENTIALS=path/to/google/key.json  # опционально
```

6. Получите токен бота:
   - Создайте бота через [@BotFather](https://t.me/BotFather) в Telegram
   - Скопируйте полученный токен в `.env`

7. Получите API ключ OpenAI:
   - Зарегистрируйтесь на [OpenAI](https://platform.openai.com/)
   - Создайте API ключ в настройках
   - Скопируйте ключ в `.env`

## Запуск

### Локальный запуск

```bash
python main.py
```

### Запуск через Docker

1. Убедитесь, что у вас установлены Docker и Docker Compose

2. Создайте файл `.env` с необходимыми переменными:
```
BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json  # опционально
```

3. Если используете Google Vision API:
   - Поместите файл с ключами в корень проекта как `google-credentials.json`
   - Добавьте в `docker-compose.yml` в секцию `volumes`:
     ```yaml
     volumes:
       - ./.env:/app/.env:ro
       - ./google-credentials.json:/app/google-credentials.json:ro
     ```
   - И в секцию `environment`:
     ```yaml
     environment:
       - GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json
     ```

4. Соберите и запустите контейнер:
```bash
docker-compose up -d
```

5. Просмотр логов:
```bash
docker-compose logs -f
```

6. Остановка контейнера:
```bash
docker-compose down
```

7. Пересборка после изменений:
```bash
docker-compose up -d --build
```

## Использование

1. Отправьте команду `/start` боту
2. Отправляйте фотографии из тетради
3. После добавления всех фото нажмите кнопку "Резюмировать"
4. Бот сгенерирует и отправит краткое резюме конспекта
5. Используйте `/clear` для очистки текущего конспекта

## Структура проекта

- `main.py` - основной файл с кодом бота
- `requirements.txt` - зависимости проекта
- `Dockerfile` - образ Docker для бота
- `docker-compose.yml` - конфигурация Docker Compose
- `.dockerignore` - файлы, исключаемые из Docker образа
- `.env` - переменные окружения (создайте сами)

