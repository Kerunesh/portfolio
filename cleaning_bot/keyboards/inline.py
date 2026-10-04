from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import CLEANING_TYPES, EXTRA_SERVICES

def get_cleaning_type_kb() -> InlineKeyboardMarkup:
    """Генерує кнопки для вибору типу прибирання."""
    builder = InlineKeyboardBuilder()
    for key, data in CLEANING_TYPES.items():
        # Текст кнопки: "Підтримуюче (50 грн/м²)"
        text = f"{data['name']} ({data['price_per_m2']} грн/м²)"
        # callback_data - це те, що бот отримає "під капотом" при натисканні
        builder.button(text=text, callback_data=f"type_{key}")
    
    # Вишиковуємо кнопки в 1 стовпчик
    builder.adjust(1)
    return builder.as_markup()

def get_extra_services_kb(selected_services: list[str]) -> InlineKeyboardMarkup:
    """Генерує кнопки для додаткових послуг із можливістю мульти-вибору."""
    builder = InlineKeyboardBuilder()
    for key, data in EXTRA_SERVICES.items():
        # Якщо послуга вже обрана, додаємо галочку
        mark = "✅ " if key in selected_services else ""
        text = f"{mark}{data['name']} (+{data['price']} грн)"
        
        builder.button(text=text, callback_data=f"extra_{key}")
    
    # Додаємо кнопку переходу до наступного кроку
    builder.button(text="➡️ Продовжити", callback_data="extra_done")
    
    # Вишиковуємо всі кнопки по одній у ряд
    builder.adjust(1)
    return builder.as_markup()