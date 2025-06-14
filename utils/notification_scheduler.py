"""
Notification scheduler for promotion reports
Sends daily notifications at 21:00 MSK
"""
import asyncio
import discord
import os
from datetime import datetime, time
import pytz
from utils.config_manager import load_config


class PromotionNotificationScheduler:
    """Handles scheduling and sending of daily promotion notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.task = None
        self.moscow_tz = pytz.timezone('Europe/Moscow')
        
    def start(self):
        """Start the notification scheduler"""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._scheduler_loop())
            print("🔔 Планировщик уведомлений запущен")
    
    def stop(self):
        """Stop the notification scheduler"""
        if self.task and not self.task.done():
            self.task.cancel()
            print("🔔 Планировщик уведомлений остановлен")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while True:
            try:
                # Get configured notification time
                config = load_config()
                schedule_config = config.get('notification_schedule', {'hour': 21, 'minute': 0})
                target_hour = schedule_config.get('hour', 21)
                target_minute = schedule_config.get('minute', 0)
                
                # Calculate seconds until next configured time MSK
                now_moscow = datetime.now(self.moscow_tz)
                target_time = now_moscow.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                
                # If it's already past target time today, schedule for tomorrow
                if now_moscow >= target_time:
                    target_time = target_time.replace(day=target_time.day + 1)
                
                sleep_seconds = (target_time - now_moscow).total_seconds()
                
                print(f"⏰ Следующая отправка уведомлений: {target_time.strftime('%d.%m.%Y %H:%M')} МСК")
                print(f"⏳ Ожидание: {int(sleep_seconds // 3600)}ч {int((sleep_seconds % 3600) // 60)}м")
                
                # Sleep until target time
                await asyncio.sleep(sleep_seconds)
                
                # Send notifications
                await self._send_daily_notifications()
                
                # Wait a bit to avoid running multiple times in the same minute
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Ошибка в планировщике уведомлений: {e}")
                # Wait 5 minutes before retrying
                await asyncio.sleep(300)
    
    async def _send_daily_notifications(self):
        """Send all enabled daily notifications"""
        try:
            config = load_config()
            promotion_notifications = config.get('promotion_notifications', {})
            promotion_channels = config.get('promotion_report_channels', {})
            
            sent_count = 0
            
            for dept_code, notification_config in promotion_notifications.items():
                if not notification_config.get('enabled', False):
                    continue
                
                channel_id = promotion_channels.get(dept_code)
                if not channel_id:
                    continue
                
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    print(f"⚠️ Канал для {dept_code} не найден (ID: {channel_id})")
                    continue
                  # Prepare notification content
                text = notification_config.get('text')
                image_filename = notification_config.get('image')
                
                if not text and not image_filename:
                    continue
                
                try:
                    # Send content exactly as specified by admin, no extra formatting
                    file = None
                    
                    # Prepare image file if specified
                    if image_filename:
                        image_path = os.path.join('files', 'reports', image_filename)
                        if os.path.exists(image_path):
                            file = discord.File(image_path, filename=image_filename)
                        else:
                            print(f"⚠️ Изображение не найдено: {image_path}")
                            image_filename = None  # Don't reference missing file
                    
                    # Send message based on what admin configured
                    if text and file:
                        # Both text and image
                        await channel.send(content=text, file=file)
                    elif text:
                        # Only text
                        await channel.send(content=text)
                    elif file:
                        # Only image
                        await channel.send(file=file)
                    else:
                        # Nothing to send (image file missing)
                        continue
                    
                    sent_count += 1
                    print(f"✅ Уведомление отправлено в {channel.name} ({dept_code})")
                    
                except Exception as e:
                    print(f"❌ Ошибка отправки уведомления для {dept_code}: {e}")
            
            print(f"📊 Отправлено уведомлений: {sent_count}")
            
        except Exception as e:
            print(f"❌ Ошибка при отправке ежедневных уведомлений: {e}")
