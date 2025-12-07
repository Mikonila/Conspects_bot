import os
import io
import logging
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from PIL import Image
import pytesseract
from pytesseract import TesseractNotFoundError
from openai import AsyncOpenAI

load_dotenv()

# Настройка логирования с выводом в stdout/stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Попытка импортировать Google Vision API
try:
    from google.cloud import vision
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False
    logger.warning("Google Cloud Vision API not available. Install with: pip install google-cloud-vision")

# Загружаем переменные окружения с явным логированием
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Проверяем наличие обязательных переменных перед созданием бота
if not BOT_TOKEN:
    error_msg = "BOT_TOKEN not found in environment variables"
    print(f"ERROR: {error_msg}", flush=True)
    raise ValueError(error_msg)
if not OPENAI_API_KEY:
    error_msg = "OPENAI_API_KEY not found in environment variables"
    print(f"ERROR: {error_msg}", flush=True)
    raise ValueError(error_msg)

print(f"INFO: BOT_TOKEN present: {bool(BOT_TOKEN)}", flush=True)
print(f"INFO: OPENAI_API_KEY present: {bool(OPENAI_API_KEY)}", flush=True)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Инициализация Google Vision API клиента (если доступен)
google_vision_client: Optional[vision.ImageAnnotatorClient] = None
if GOOGLE_VISION_AVAILABLE and GOOGLE_APPLICATION_CREDENTIALS:
    try:
        google_vision_client = vision.ImageAnnotatorClient()
        logger.info("Google Cloud Vision API initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Google Vision API: {e}")
        google_vision_client = None
elif GOOGLE_VISION_AVAILABLE:
    logger.info("Google Vision API available but GOOGLE_APPLICATION_CREDENTIALS not set, will use Tesseract")

class NotesState(StatesGroup):
    collecting_photos = State()

user_notes: Dict[int, List[str]] = {}

def extract_text_with_google_vision(image_bytes: bytes) -> Tuple[str, str]:
    """Извлекает текст используя Google Cloud Vision API"""
    if not google_vision_client:
        return ("", "Google Vision API не настроен")
    
    try:
        image = vision.Image(content=image_bytes)
        response = google_vision_client.document_text_detection(image=image)
        
        if response.error.message:
            return ("", f"Google Vision API error: {response.error.message}")
        
        text = response.full_text_annotation.text if response.full_text_annotation else ""
        text = text.strip()
        
        if text:
            preview = text[:200] + "..." if len(text) > 200 else text
            logger.info(f"Extracted text with Google Vision (preview): {preview}")
            return (text, "")
        else:
            return ("", "Google Vision API не распознал текст на изображении")
    except Exception as e:
        error_msg = f"Ошибка Google Vision API: {str(e)}"
        logger.error(error_msg)
        return ("", error_msg)

def extract_text_from_image(image_bytes: bytes) -> Tuple[str, str]:
    """
    Извлекает текст из изображения.
    Сначала пытается использовать Google Vision API, затем Tesseract.
    Returns: (text, error_message)
    Если успешно - возвращает (text, ""), иначе ("", error_message)
    """
    # Пробуем сначала Google Vision API (лучше для рукописного текста)
    if google_vision_client:
        text, error = extract_text_with_google_vision(image_bytes)
        if text:
            return (text, "")
        logger.warning(f"Google Vision failed: {error}, trying Tesseract")
    
    # Используем Tesseract как fallback
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image, lang='rus+eng')
        text = text.strip()
        
        # Логируем первые 200 символов распознанного текста для отладки
        preview = text[:200] + "..." if len(text) > 200 else text
        logger.info(f"Extracted text with Tesseract (preview): {preview}")
        
        return (text, "")
    except TesseractNotFoundError:
        error_msg = (
            "Tesseract OCR не установлен на сервере. "
            "Обратитесь к администратору для установки:\n"
            "sudo apt install tesseract-ocr tesseract-ocr-rus"
        )
        logger.error("Tesseract OCR is not installed")
        return ("", error_msg)
    except Exception as e:
        error_msg = f"Ошибка при распознавании текста: {str(e)}"
        logger.error(f"Error extracting text from image: {e}")
        return ("", error_msg)

async def generate_summary(text: str) -> str:
    try:
        if not text or len(text.strip()) < 10:
            return "<i>Текст конспекта слишком короткий или пустой для создания резюме.</i>"
        
        logger.info(f"Generating summary for text of length: {len(text)}")
        
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты помощник, который создает краткие и структурированные резюме конспектов. КРИТИЧЕСКИ ВАЖНО: резюмируй ТОЛЬКО то, что написано в предоставленном тексте. НЕ добавляй информацию, которой нет в исходном тексте. НЕ придумывай детали. Если текст непонятен или распознан плохо, укажи это. Всегда отвечай ТОЛЬКО в формате HTML, используя теги: <b> для жирного, <i> для курсива, <u> для подчеркивания, <code> для кода, <pre> для блоков кода. НЕ используй тег <br>. Для переносов строк используй обычные символы новой строки. Создавай четкое и структурированное резюме, выделяя основные моменты и концепции, которые есть в исходном тексте."},
                {"role": "user", "content": f"Создай краткое резюме следующего конспекта в формате HTML. Резюмируй ТОЛЬКО то, что написано ниже. НЕ добавляй информацию, которой нет в тексте:\n\n{text}"}
            ],
            temperature=0.5,
            max_tokens=1500
        )
        result = response.choices[0].message.content
        logger.info(f"Generated summary length: {len(result)}")
        
        # Заменяем <br> и <br/> на обычные переносы строк, так как Telegram не поддерживает эти теги
        result = result.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        
        return result
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return "<b>Ошибка при генерации резюме.</b> Попробуйте позже."

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    try:
        logger.info(f"Received /start command from user {message.from_user.id}")
        user_id = message.from_user.id
        user_notes[user_id] = []
        await state.set_state(NotesState.collecting_photos)
        await message.answer(
            "<b>Привет!</b> Отправляй фото из тетради, и я соберу из них конспект.\n\n"
            "Когда закончишь, нажми кнопку <b>'Резюмировать'</b> для получения краткого резюме.\n\n"
            "Команды:\n"
            "<code>/show</code> - показать распознанный текст\n"
            "<code>/clear</code> - очистить конспект",
            parse_mode="HTML"
        )
        logger.info(f"Successfully sent start message to user {user_id}")
    except Exception as e:
        logger.error(f"Error in cmd_start: {e}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при обработке команды. Попробуйте позже.")
        except:
            pass

@dp.message(Command("clear"))
async def cmd_clear(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_notes[user_id] = []
    await state.clear()
    await message.answer("<b>Конспект очищен.</b> Можете начать заново.", parse_mode="HTML")

@dp.message(Command("show"))
async def cmd_show(message: Message):
    """Показать распознанный текст конспекта"""
    user_id = message.from_user.id
    
    if user_id not in user_notes or not user_notes[user_id]:
        await message.answer("<b>Конспект пуст.</b> Отправьте фото сначала.", parse_mode="HTML")
        return
    
    # Собираем текст с нумерацией страниц
    text_parts = []
    for i, page_text in enumerate(user_notes[user_id], 1):
        text_parts.append(f"--- Страница {i} ---\n\n{page_text}")
    full_text = "\n\n".join(text_parts)
    
    # Экранируем HTML символы для отображения в <pre>
    full_text_escaped = full_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Разбиваем на части, если текст слишком длинный
    if len(full_text_escaped) > 4000:
        preview = full_text_escaped[:4000] + "\n\n... (текст обрезан)"
        await message.answer(f"<b>Распознанный текст конспекта:</b>\n\n<pre>{preview}</pre>", parse_mode="HTML")
    else:
        await message.answer(f"<b>Распознанный текст конспекта:</b>\n\n<pre>{full_text_escaped}</pre>", parse_mode="HTML")

@dp.message(NotesState.collecting_photos, F.photo)
async def process_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        image_bytes = file_bytes.read()
        
        await message.answer("<i>Обрабатываю фото...</i>", parse_mode="HTML")
        
        extracted_text, error_msg = extract_text_from_image(image_bytes)
        
        if error_msg:
            await message.answer(
                f"<b>Ошибка:</b>\n\n<code>{error_msg}</code>",
                parse_mode="HTML"
            )
            return
        
        if extracted_text:
            if user_id not in user_notes:
                user_notes[user_id] = []
            user_notes[user_id].append(extracted_text)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Резюмировать", callback_data="summarize")]
            ])
            
            await message.answer(
                f"✅ <b>Текст распознан и добавлен в конспект.</b>\n\n"
                f"Всего страниц: <b>{len(user_notes[user_id])}</b>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "<b>Не удалось распознать текст на фото.</b>\n\n"
                "<b>Возможные причины:</b>\n"
                "• Изображение нечеткое или размытое\n"
                "• Текст слишком мелкий\n"
                "• Недостаточное освещение\n\n"
                "<i>Попробуйте отправить более четкое изображение.</i>",
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await message.answer(
            "<b>Произошла ошибка</b> при обработке фото. Попробуйте еще раз.",
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "summarize")
async def summarize_notes(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if user_id not in user_notes or not user_notes[user_id]:
        await callback.answer("Конспект пуст. Отправьте фото сначала.")
        return
    
    await callback.answer("Генерирую резюме...")
    await callback.message.edit_reply_markup(reply_markup=None)
    
    full_text = "\n\n".join(user_notes[user_id])
    
    # Логируем первые 500 символов для отладки
    preview = full_text[:500] + "..." if len(full_text) > 500 else full_text
    logger.info(f"Summarizing text (total length: {len(full_text)}): {preview}")
    
    await callback.message.answer(
        "<i>Создаю резюме, это может занять некоторое время...</i>",
        parse_mode="HTML"
    )
    
    summary = await generate_summary(full_text)
    
    await callback.message.answer(
        f"📝 <b>Резюме конспекта:</b>\n\n{summary}",
        parse_mode="HTML"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Резюмировать снова", callback_data="summarize")]
    ])
    await callback.message.answer(
        "Вы можете создать резюме снова, если нужно.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.message(NotesState.collecting_photos)
async def process_other_messages(message: Message):
    await message.answer(
        "<b>Отправьте фото</b> из тетради для добавления в конспект.\n\n"
        "Используйте <code>/clear</code> для очистки конспекта.",
        parse_mode="HTML"
    )

async def main():
    try:
        logger.info("Starting bot...")
        logger.info(f"Bot token present: {bool(BOT_TOKEN)}")
        logger.info(f"OpenAI API key present: {bool(OPENAI_API_KEY)}")
        logger.info(f"Google Vision available: {GOOGLE_VISION_AVAILABLE}")
        logger.info(f"Google Vision client initialized: {google_vision_client is not None}")
        
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise

