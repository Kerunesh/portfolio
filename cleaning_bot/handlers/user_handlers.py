from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart

from config import CLEANING_TYPES, EXTRA_SERVICES, ADMIN_CHAT_ID
from database import add_order
from keyboards.inline import get_cleaning_type_kb, get_extra_services_kb

router = Router()

# Define steps of our order form
class OrderForm(StatesGroup):
    cleaning_type = State()
    area = State()
    extra_services = State()
    name = State()
    phone = State()
    date = State()

# 1. Start command -> Ask for cleaning type
@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привіт! Я допоможу розрахувати вартість прибирання.\n\nОберіть тип прибирання:",
        reply_markup=get_cleaning_type_kb()
    )
    await state.set_state(OrderForm.cleaning_type)

# 2. Process cleaning type selection
@router.callback_query(OrderForm.cleaning_type, F.data.startswith("type_"))
async def process_cleaning_type(callback: CallbackQuery, state: FSMContext):
    selected_type = callback.data.replace("type_", "")
    
    # Save selected type and initialize empty list for extra services
    await state.update_data(cleaning_type=selected_type, extra_services=[])
    
    type_name = CLEANING_TYPES[selected_type]['name']
    await callback.message.edit_text(
        f"✅ Ви обрали: **{type_name}**.\n\nВведіть площу приміщення в м² (наприклад: 50):",
        parse_mode="Markdown"
    )
    await state.set_state(OrderForm.area)

# 3. Process area input
@router.message(OrderForm.area)
async def process_area(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️️ Будь ласка, введіть тільки число (наприклад, 45).")
        return
    
    await state.update_data(area=int(message.text))
    user_data = await state.get_data()
    
    await message.answer(
        "🧹 Чи бажаєте додати додаткові послуги? (Можна обрати декілька)",
        reply_markup=get_extra_services_kb(user_data['extra_services'])
    )
    await state.set_state(OrderForm.extra_services)

# 4. Process extra services (multi-select)
@router.callback_query(OrderForm.extra_services, F.data.startswith("extra_"))
async def process_extra_services(callback: CallbackQuery, state: FSMContext):
    action = callback.data.replace("extra_", "")
    user_data = await state.get_data()
    selected = user_data.get('extra_services', [])
    
    # If user clicked "Done"
    if action == "done":
        await callback.message.edit_text("✅ Послуги збережено!\n\nЯк до вас звертатися? (Введіть ваше ім'я):")
        await state.set_state(OrderForm.name)
        return
        
    # Toggle logic: remove if already selected, add if not
    if action in selected:
        selected.remove(action)
    else:
        selected.append(action)
        
    await state.update_data(extra_services=selected)
    
    # Refresh keyboard with updated checkmarks
    await callback.message.edit_reply_markup(reply_markup=get_extra_services_kb(selected))

# 5. Process name
@router.message(OrderForm.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📱 Введіть ваш номер телефону:")
    await state.set_state(OrderForm.phone)

# 6. Process phone
@router.message(OrderForm.phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("📅 Напишіть зручну дату та час (наприклад: Завтра на 10:00):")
    await state.set_state(OrderForm.date)

# 7. Process date, calculate total, save to DB and notify Admin
@router.message(OrderForm.date)
async def process_date(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(date=message.text)
    data = await state.get_data()
    
    # Calculation
    base_price = CLEANING_TYPES[data['cleaning_type']]['price_per_m2'] * data['area']
    extras_price = sum(EXTRA_SERVICES[srv]['price'] for srv in data['extra_services'])
    total_price = base_price + extras_price
    
    cleaning_name = CLEANING_TYPES[data['cleaning_type']]['name']
    extras_names = ", ".join([EXTRA_SERVICES[srv]['name'] for srv in data['extra_services']]) or "Немає"
    
    # Save to SQLite
    await add_order(
        user_id=message.from_user.id,
        username=message.from_user.username or "None",
        name=data['name'],
        phone=data['phone'],
        cleaning_type=cleaning_name,
        area=data['area'],
        extra_services=extras_names,
        total_price=total_price,
        date=data['date']
    )
    
    # Receipt for User
    receipt = (
        f"🧾 **Ваш чек:**\n\n"
        f"🔹 **Тип:** {cleaning_name}\n"
        f"🔹 **Площа:** {data['area']} м²\n"
        f"🔹 **Додатково:** {extras_names}\n"
        f"🔹 **Дата:** {data['date']}\n\n"
        f"💰 **Загальна вартість: {total_price} грн**\n\n"
        f"Дякуємо! Менеджер зв'яжеться з вами найближчим часом."
    )
    await message.answer(receipt, parse_mode="Markdown")
    
    # Alert for Admin
    admin_msg = (
        f"🚨 **НОВА ЗАЯВКА!** 🚨\n\n"
        f"👤 Клієнт: {data['name']} (@{message.from_user.username})\n"
        f"📱 Телефон: {data['phone']}\n"
        f"🧹 Тип: {cleaning_name} ({data['area']} м²)\n"
        f"➕ Дод. послуги: {extras_names}\n"
        f"📅 Дата: {data['date']}\n\n"
        f"💵 Вартість: **{total_price} грн**"
    )
    try:
        await bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Failed to send admin message: {e}")
        
    await state.clear()