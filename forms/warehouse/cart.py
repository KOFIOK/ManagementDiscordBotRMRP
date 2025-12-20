"""
Управление корзиной запросов склада
"""

import discord
from datetime import datetime
from typing import Optional, Dict, List
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class WarehouseRequestItem:
    """Класс для представления одного предмета в корзине"""
    
    def __init__(self, category: str, item_name: str, quantity: int, user_name: str, 
                 user_static: str, position: str, rank: str):
        self.category = category
        self.item_name = item_name
        self.quantity = quantity
        self.user_name = user_name
        self.user_static = user_static
        self.position = position
        self.rank = rank
        self.timestamp = datetime.now()
    
    def __str__(self):
        return f"**{self.item_name}** × {self.quantity}"


class WarehouseRequestCart:
    """Класс для управления корзиной запросов склада"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.items: List[WarehouseRequestItem] = []
        self.created_at = datetime.now()
    
    def add_item(self, item: WarehouseRequestItem):
        """Добавить предмет в корзину"""
        # Проверяем, есть ли уже такой предмет
        for existing_item in self.items:
            if (existing_item.category == item.category and 
                existing_item.item_name == item.item_name):
                # Если есть, увеличиваем количество
                existing_item.quantity += item.quantity
                return
        # Если нет, добавляем новый предмет
        self.items.append(item)
    
    def remove_item_by_index(self, index: int):
        """Удалить предмет по индексу (0-based)"""
        if 0 <= index < len(self.items):
            self.items.pop(index)
            return True
        return False
    
    def clear(self):
        """Очистить корзину"""
        self.items.clear()
    
    def is_empty(self) -> bool:
        """Проверить, пуста ли корзина"""
        return len(self.items) == 0
    
    def get_total_items(self) -> int:
        """Получить общее количество предметов"""
        return sum(item.quantity for item in self.items)
    
    def get_summary(self) -> str:
        """Получить краткое описание корзины"""
        if self.is_empty():
            return "Корзина пуста"
        
        summary = []
        for i, item in enumerate(self.items, 1):
            summary.append(f"{i}. {str(item)}")
        
        return "\n".join(summary)
    
    def get_summary_without_numbers(self) -> str:
        """Получить краткое описание корзины без номеров (для финальной заявки)"""
        if self.is_empty():
            return "Корзина пуста"
        
        summary = []
        for item in self.items:
            summary.append(str(item))
        
        return "\n".join(summary)
    
    def get_item_quantity(self, category: str, item_name: str) -> int:
        """Получить текущее количество конкретного предмета в корзине"""
        for item in self.items:
            if item.category == category and item.item_name == item_name:
                return item.quantity
        return 0


# Глобальный словарь для хранения корзин пользователей
user_carts: Dict[int, WarehouseRequestCart] = {}

# Глобальный словарь для хранения сообщений корзин пользователей (для редактирования)
user_cart_messages: Dict[int, discord.Message] = {}


def get_user_cart(user_id: int) -> WarehouseRequestCart:
    """Получить корзину пользователя"""
    if user_id not in user_carts:
        user_carts[user_id] = WarehouseRequestCart(user_id)
    return user_carts[user_id]


def clear_user_cart(user_id: int):
    """Очистить корзину пользователя безопасно"""
    try:
        cart_cleared = False
        message_cleared = False
        
        if user_id in user_carts:
            del user_carts[user_id]
            cart_cleared = True
            
        if user_id in user_cart_messages:
            del user_cart_messages[user_id]
            message_cleared = True
            
        if cart_cleared or message_cleared:
            logger.info("CART CLEANUP: Очищены данные для пользователя %s (корзина: %s, сообщение: %s)", user_id, '' if cart_cleared else '', '' if message_cleared else '')
        
    except Exception as e:
        logger.warning("CART CLEANUP ERROR: Ошибка очистки корзины для %s: %s", user_id, e)


def clear_user_cart_safe(user_id: int, reason: str = "unknown"):
    """Безопасная очистка корзины с указанием причины"""
    try:
        logger.info("CART SAFE CLEAR: Начата очистка для пользователя %s, причина: %s", user_id, reason)
        clear_user_cart(user_id)
    except Exception as e:
        logger.warning("CART SAFE CLEAR ERROR: Критическая ошибка очистки корзины для %s: %s", user_id, e)


def get_user_cart_message(user_id: int) -> Optional[discord.Message]:
    """Получить сообщение корзины пользователя"""
    return user_cart_messages.get(user_id)


def set_user_cart_message(user_id: int, message: discord.Message):
    """Установить сообщение корзины пользователя"""
    user_cart_messages[user_id] = message
