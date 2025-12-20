import asyncio
import discord
from datetime import datetime, timedelta
from typing import Optional
from utils.config_manager import load_config
from forms.supplies.supplies_manager import SuppliesManager
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)


class SuppliesScheduler:
    """Планировщик уведомлений о поставках"""
    
    def __init__(self, bot):
        self.bot = bot
        self.supplies_manager = SuppliesManager(bot)
        self.task: Optional[asyncio.Task] = None
        self.is_running = False
    
    def start(self):
        """Запускает планировщик"""
        if self.is_running:
            logger.info("Планировщик поставок уже запущен")
            return
        
        self.is_running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info("Планировщик поставок запущен")
    
    def stop(self):
        """Останавливает планировщик"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.task:
            self.task.cancel()
        logger.info("Планировщик поставок остановлен")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика (проверка каждые 15 секунд для лучшего обновления)"""
        while self.is_running:
            try:
                await self._check_timers()
                await asyncio.sleep(15)  # Проверка каждые 15 секунд для лучшего UI
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Ошибка в планировщике поставок: %s", e)
                await asyncio.sleep(15)
    
    async def _check_timers(self):
        """Проверяет все активные таймеры и отправляет уведомления"""
        try:
            active_timers = self.supplies_manager.get_active_timers()
            config = load_config()
            
            # Получаем настройки
            notification_channel_id = config.get('supplies', {}).get('notification_channel_id')
            subscription_role_id = config.get('supplies', {}).get('subscription_role_id')
            warning_minutes = config.get('supplies', {}).get('warning_minutes', 20)
            
            if not notification_channel_id:
                if active_timers:  # Логируем только если есть таймеры
                    logger.info("Канал уведомлений не настроен")
                return
            
            notification_channel = self.bot.get_channel(notification_channel_id)
            if not notification_channel:
                if active_timers:  # Логируем только если есть таймеры
                    logger.info("Канал уведомлений не найден: %s", notification_channel_id)
                return
            
            current_time = datetime.now()
            timers_changed = False
            expired_timers = []  # Список истекших таймеров для обработки
            
            for object_key, timer_info in active_timers.items():
                end_time = datetime.fromisoformat(timer_info["end_time"])
                time_until_ready = end_time - current_time
                
                # Проверяем, истек ли таймер (готов к поставке)
                if current_time >= end_time:
                    expired_timers.append((object_key, timer_info))
                    continue
                
                # Проверяем, нужно ли отправить предупреждение
                warning_time = timedelta(minutes=warning_minutes)
                if (time_until_ready <= warning_time and 
                    not timer_info.get("warning_sent", False)):
                    
                    # Удаляем стартовое сообщение перед отправкой предупреждения
                    await self.supplies_manager.clear_start_message(object_key, notification_channel)
                    
                    await self._send_warning_notification(
                        notification_channel,
                        object_key,
                        timer_info,
                        subscription_role_id,
                        int(time_until_ready.total_seconds() // 60)  # минуты
                    )
                    
                    # Отмечаем, что предупреждение отправлено
                    await self._mark_warning_sent(object_key)
                    timers_changed = True
            
            # Сначала обновляем warning сообщения (пока таймеры еще существуют)
            await self._update_warning_messages(notification_channel)
            
            # Теперь обрабатываем истекшие таймеры
            for object_key, timer_info in expired_timers:
                await self._send_ready_notification(
                    notification_channel, 
                    object_key, 
                    timer_info, 
                    subscription_role_id
                )
                # Удаляем стартовое сообщение при завершении
                await self.supplies_manager.clear_start_message(object_key, notification_channel)
                # Удаляем истекший таймер
                self.supplies_manager.cancel_timer(object_key)
                timers_changed = True
            
            # Обновляем сообщение управления каждую минуту (не только при изменениях)
            # Это нужно для обновления оставшегося времени в embed'ах
            await self._update_control_message()
            
            # Обновляем сообщения в канале оповещений
            await self._update_notification_messages(notification_channel)
                    
        except Exception as e:
            logger.warning("Ошибка при проверке таймеров поставок: %s", e)
    
    async def _update_control_message(self):
        """Обновляет сообщение управления поставками"""
        try:
            from utils.supplies_restore import get_supplies_restore_manager
            restore_manager = get_supplies_restore_manager()
            if restore_manager:
                await restore_manager.update_control_message_timers()
            else:
                logger.warning("Менеджер восстановления не найден")
        except Exception as e:
            logger.warning("Ошибка обновления сообщения управления: %s", e)

    async def _update_notification_messages(self, notification_channel):
        """Обновляет сообщения в канале оповещений с актуальным временем"""
        try:
            if notification_channel:
                await self.supplies_manager.update_notification_messages(notification_channel)
        except Exception as e:
            logger.warning("Ошибка обновления сообщений оповещений: %s", e)
    
    async def _send_ready_notification(self, channel: discord.TextChannel, object_key: str, 
                                     timer_info: dict, subscription_role_id: Optional[int]):
        """Отправляет уведомление о готовности объекта"""
        try:
            object_name = timer_info.get("object_name", object_key)
            emoji = timer_info.get("emoji", "📦")
            started_by_name = timer_info.get("started_by_name", "Неизвестно")
            
            # Формируем сообщение
            role_mention = f"<@&{subscription_role_id}>" if subscription_role_id else "@everyone"
            
            embed = discord.Embed(
                title="🚚 Поставка готова!",
                description=f"{emoji} **{object_name}** готов к новой поставке материалов!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 Информация",
                value=(
                    f"🏭 **Объект:** {object_name}\n"
                    f"👤 **Запустил:** {started_by_name}\n"
                    f"✅ **Статус:** Готов к работе"
                ),
                inline=False
            )
            
            embed.set_footer(text="Система управления поставками")
            
            await channel.send(
                content=f"{role_mention} {emoji} **{object_name}** готов к поставке!",
                embed=embed
            )
            
            logger.info("Отправлено уведомление о готовности: %s", object_name)
            
        except Exception as e:
            logger.warning("Ошибка отправки уведомления о готовности для %s: %s", object_key, e)
    
    async def _send_warning_notification(self, channel: discord.TextChannel, object_key: str,
                                       timer_info: dict, subscription_role_id: Optional[int],
                                       minutes_left: int):
        """Отправляет предупреждение за N минут до готовности"""
        try:
            object_name = timer_info.get("object_name", object_key)
            emoji = timer_info.get("emoji", "📦")
            
            # Формируем сообщение
            role_mention = f"-# <@&{subscription_role_id}>" if subscription_role_id else ""
            
            embed = discord.Embed(
                title="⚠️ Скоро будет доступна поставка!",
                description=f"{emoji} **{object_name}** будет готов через **{minutes_left} минут**!",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="⏰ Предупреждение",
                value=(
                    f"**Объект:** {object_name}\n"
                    f"**Осталось:** {minutes_left} минут\n"
                ),
                inline=False
            )
            
            embed.set_footer(text="Система управления поставками")
            
            message = await channel.send(
                content=f"{role_mention}",
                embed=embed
            )
            
            # Сохраняем ID сообщения с предупреждением
            await self.supplies_manager.save_notification_message(object_key, message.id, 'warning')
            
            logger.warning("Отправлено предупреждение для %s: %s минут", object_name, minutes_left)
            
        except Exception as e:
            logger.warning("Ошибка отправки предупреждения для %s: %s", object_key, e)
    
    async def _mark_warning_sent(self, object_key: str):
        """Отмечает, что предупреждение для объекта было отправлено"""
        try:
            data = self.supplies_manager._load_data()
            if object_key in data.get("active_timers", {}):
                data["active_timers"][object_key]["warning_sent"] = True
                self.supplies_manager._save_data(data)
                
        except Exception as e:
            logger.warning("Ошибка при отметке отправленного предупреждения для %s: %s", object_key, e)

    async def _update_warning_messages(self, channel):
        """Обновляет сообщения предупреждений в канале оповещений"""
        try:
            if channel:
                await self.supplies_manager.update_warning_messages(channel)
        except Exception as e:
            logger.warning("Ошибка обновления сообщений предупреждений: %s", e)


# Глобальная переменная для планировщика
supplies_scheduler: Optional[SuppliesScheduler] = None


def initialize_supplies_scheduler(bot) -> SuppliesScheduler:
    """Инициализирует планировщик поставок"""
    global supplies_scheduler
    
    try:
        supplies_scheduler = SuppliesScheduler(bot)
        return supplies_scheduler
    except Exception as e:
        logger.warning("Ошибка инициализации планировщика поставок: %s", e)
        return None


def get_supplies_scheduler() -> Optional[SuppliesScheduler]:
    """Возвращает экземпляр планировщика поставок"""
    return supplies_scheduler