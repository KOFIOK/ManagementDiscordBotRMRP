"""
Department Application Forms - Two-stage modal forms for department applications
"""
import discord
from discord import ui
import re
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from utils.database_manager import personnel_manager
from utils.ping_manager import ping_manager

logger = logging.getLogger(__name__)


class DepartmentApplicationStage1Modal(ui.Modal):
    """Stage 1: IC Information modal for department applications"""
    
    def __init__(self, department_code: str, application_type: str, user_id: int, skip_data_loading: bool = False):
        self.department_code = department_code
        self.application_type = application_type  # 'join' or 'transfer'
        self.user_id = user_id
        self.user_ic_data = None  # Будет загружено позже при необходимости
        self.skip_data_loading = skip_data_loading
        
        title = f"Заявление в {department_code} - IC Информация"
        if application_type == 'transfer':
            title += " (Перевод)"
        
        super().__init__(title=title, timeout=300)
        
        if not skip_data_loading:
            # Старый способ - синхронная загрузка (может быть медленным)
            self._try_load_user_data_sync()
        else:
            # Быстрая инициализация - ВСЕГДА пытаемся загрузить из кэша синхронно
            # Кэш быстрый (мгновенный), не замедлит инициализацию
            logger.info(f"⚡ Fast initialization for user {user_id} - loading from cache only")
            self._try_load_from_cache_only()
        
        # Создаем поля с данными (если загрузились) или пустые
        self._setup_fields_with_data()
    
    def _try_load_from_cache_only(self):
        """Быстрая загрузка ТОЛЬКО из кэша - мгновенная операция"""
        try:
            # Попробуем загрузить через публичный API кэша
            cache_data = self._try_load_from_cache_public()
            if cache_data:
                self.user_ic_data = cache_data
                logger.info(f"⚡ User data loaded from cache for {self.user_id} - form will be autofilled")
            else:
                logger.info(f"ℹ️  No cached data for {self.user_id} - form will be empty (can load async later)")
                self.user_ic_data = None
                
        except Exception as e:
            logger.error(f"💥 Error in cache-only loading for {self.user_id}: {e}")
            self.user_ic_data = None

    def _try_load_user_data_sync(self):
        """Пытается загрузить данные пользователя из кэша синхронно, затем асинхронно из базы"""
        try:
            # Шаг 1: Проверяем кэш синхронно (быстро)
            cache_data = self._try_load_from_cache()
            if cache_data:
                self.user_ic_data = cache_data
                logger.info(f"✅ User data loaded from cache for {self.user_id} - form will be autofilled")
                return
            
            # Шаг 2: Если в кэше нет - проверяем, можем ли загрузить из базы
            try:
                loop = asyncio.get_running_loop()
                # Если loop уже запущен - не можем делать синхронную загрузку из базы
                # Оставляем поля пустыми, пользователь заполнит вручную
                logger.info(f"ℹ️  No cached data for {self.user_id}, event loop running - form will be empty")
                self.user_ic_data = None
                return
            except RuntimeError:
                # Нет активного loop - можем попробовать загрузить из базы
                logger.info(f"ℹ️  No cached data for {self.user_id}, trying database load...")
                self._try_load_from_database_sync()
                
        except Exception as e:
            logger.error(f"💥 Critical error in sync data loading for {self.user_id}: {e}")
            self.user_ic_data = None
    
    def _try_load_from_cache_public(self) -> Optional[Dict[str, Any]]:
        """Публичный способ загрузки из кэша через API"""
        try:
            from utils.user_cache import get_cached_user_info_sync
            
            # Используем публичный синхронный API кэша
            cached_data = get_cached_user_info_sync(self.user_id)
            if cached_data:
                logger.info(f"✅ Cache data found for user {self.user_id}")
                return cached_data
            else:
                logger.info(f"ℹ️  No cached data for user {self.user_id}")
                return None
                
        except Exception as e:
            logger.warning(f"❌ Error accessing cache for {self.user_id}: {e}")
            # Fallback к прямому доступу
            return self._try_load_from_cache_direct()
    
    def _try_load_from_cache(self) -> Optional[Dict[str, Any]]:
        """Пытается получить данные из кэша синхронно"""
        return self._try_load_from_cache_direct()
    
    def _try_load_from_cache_direct(self) -> Optional[Dict[str, Any]]:
        """Прямой доступ к кэшу"""
        try:
            from utils.user_cache import _global_cache
            
            # Прямой доступ к кэшу (синхронно)
            if hasattr(_global_cache, '_cache') and self.user_id in _global_cache._cache:
                # Проверяем, не истек ли кэш
                if hasattr(_global_cache, '_expiry') and self.user_id in _global_cache._expiry:
                    if _global_cache._expiry[self.user_id] > datetime.now():
                        cached_data = _global_cache._cache[self.user_id]
                        # Проверяем, что это не маркер "NOT_FOUND"
                        if cached_data and cached_data != "NOT_FOUND":
                            return cached_data
                        else:
                            logger.info(f"ℹ️  User {self.user_id} marked as NOT_FOUND in cache")
                            return None
                    else:
                        logger.info(f"ℹ️  Cached data for {self.user_id} expired")
                        return None
                else:
                    # Нет информации об истечении - считаем устаревшим
                    return None
            else:
                logger.info(f"ℹ️  No cached data for user {self.user_id}")
                return None
                
        except Exception as e:
            logger.warning(f"❌ Error accessing cache for {self.user_id}: {e}")
            return None
    
    def _try_load_from_database_sync(self):
        """Пытается синхронно загрузить данные из базы (только если нет event loop)"""
        try:
            import asyncio
            
            # Создаем новый event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Загружаем данные с таймаутом
            try:
                task = asyncio.create_task(self._load_user_data_fast())
                start_time = loop.time()
                self.user_ic_data = loop.run_until_complete(asyncio.wait_for(task, timeout=3.0))
                load_time = loop.time() - start_time
                
                if self.user_ic_data:
                    logger.info(f"✅ User data loaded from database for {self.user_id} in {load_time:.3f}s - form will be autofilled")
                else:
                    logger.info(f"ℹ️  User {self.user_id} not found in database in {load_time:.3f}s - form will be empty")
                    
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Timeout (>3s) loading user data from database for {self.user_id} - form will be empty")
                self.user_ic_data = None
            except Exception as e:
                logger.warning(f"❌ Error loading user data from database for {self.user_id}: {e} - form will be empty")
                self.user_ic_data = None
                
        except Exception as e:
            logger.error(f"💥 Critical error in database sync loading for {self.user_id}: {e}")
            self.user_ic_data = None
    
    async def _load_user_data_fast(self):
        """Быстрая загрузка данных пользователя - унифицированная с кэшем"""
        try:
            # Сначала попробуем загрузить из кэша асинхронно
            from utils.user_cache import get_cached_user_info
            cached_data = await get_cached_user_info(self.user_id)
            
            if cached_data:
                logger.info(f"✅ User data loaded from cache for {self.user_id}")
                return cached_data
            
            # Если в кэше нет - загружаем из базы напрямую
            from utils.database_manager import PersonnelManager
            pm = PersonnelManager()
            user_data = await pm.get_personnel_summary(self.user_id)
            if user_data:
                # Преобразуем в унифицированный формат (совместимый с кэшем)
                formatted_data = {
                    'full_name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                    'static': user_data.get('static', ''),
                    'first_name': user_data.get('first_name', ''),  # Для совместимости
                    'last_name': user_data.get('last_name', ''),   # Для совместимости
                    'position': user_data.get('position', 'Не указано'),  # Теперь есть в данных
                    'rank': user_data.get('rank', 'Не указано'),     # Теперь есть в данных
                    'department': user_data.get('department', 'Не определено')  # Теперь есть в данных
                }
                logger.info(f"✅ User data loaded from database for {self.user_id}")
                return formatted_data
                
        except Exception as e:
            logger.error(f"❌ Error loading user data for {self.user_id}: {e}")
        
        return None
    
    def _setup_fields_with_data(self):
        """Setup form fields with loaded data or empty if not available"""
        
        # Подготавливаем данные для автозаполнения
        default_name = ""
        default_static = ""
        
        if self.user_ic_data:
            # Данные найдены в базе/кэше - автозаполняем
            # Проверяем формат данных (может быть как full_name, так и first_name/last_name)
            full_name = ""
            if 'full_name' in self.user_ic_data:
                # Данные из кэша (новый формат)
                full_name = self.user_ic_data.get('full_name', '')
            else:
                # Данные из базы (старый формат)
                ic_first_name = self.user_ic_data.get('first_name', '')
                ic_last_name = self.user_ic_data.get('last_name', '')
                full_name = f"{ic_first_name} {ic_last_name}".strip()
            
            ic_static = self.user_ic_data.get('static', '')
            
            if full_name:
                default_name = full_name
                name_placeholder = f"✅ Автозаполнено: {full_name}"
                logger.info(f"⚡ Autofilled name for {self.user_id}: {full_name}")
            else:
                name_placeholder = "Введите ваше Имя Фамилия"
            
            if ic_static:
                default_static = ic_static
                static_placeholder = f"✅ Автозаполнено: {ic_static}"
                logger.info(f"⚡ Autofilled static for {self.user_id}: {ic_static}")
            else:
                static_placeholder = "Введите ваш статик (123-456)"
        elif self.skip_data_loading:
            # Быстрая инициализация - показываем что данные могут загрузиться позже
            name_placeholder = "Например: Олег Дубов"
            static_placeholder = "Например: 123-456"
            logger.info(f"ℹ️  Fast modal for {self.user_id} - autofill available on submit")
        else:
            # Данные не найдены - поля пустые
            name_placeholder = "например: Олег Дубов"
            static_placeholder = "например: 123-456"

        # Full name field
        self.name_input = ui.TextInput(
            label="Имя Фамилия",
            placeholder=name_placeholder,
            default=default_name,
            max_length=100,
            required=True
        )
        self.add_item(self.name_input)
        
        # Static field
        self.static_input = ui.TextInput(
            label="Статик",
            placeholder=static_placeholder,
            default=default_static,
            max_length=10,
            required=True
        )
        self.add_item(self.static_input)
        
        # Document copy (link to image)
        self.document_input = ui.TextInput(
            label="Ксерокопия служебного документа",
            placeholder="Ссылка на изображение документа",
            style=discord.TextStyle.short,
            max_length=500,
            required=True
        )
        self.add_item(self.document_input)
        
        # Reason for department choice
        self.reason_input = ui.TextInput(
            label="Причины выбора подразделения",
            placeholder="Опишите, почему вы выбрали именно это подразделение...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.reason_input)
    
    async def _load_user_data_async(self):
        """Асинхронно загружает данные пользователя из базы данных"""
        try:
            from utils.database_manager import PersonnelManager
            pm = PersonnelManager()
            user_data = await pm.get_personnel_summary(self.user_id)
            if user_data:
                # Преобразуем в ожидаемый формат
                self.user_ic_data = {
                    'full_name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                    'static': user_data.get('static', ''),
                    'position': user_data.get('position', 'Не указано'),
                    'rank': user_data.get('rank', 'Не указано'),
                    'department': user_data.get('department', 'Не определено')
                }
            
            if self.user_ic_data:
                # Автозаполняем поля если данные найдены
                ic_first_name = self.user_ic_data.get('first_name', '')
                ic_last_name = self.user_ic_data.get('last_name', '')
                ic_static = self.user_ic_data.get('static', '')
                
                full_name = f"{ic_first_name} {ic_last_name}".strip()
                
                # Обновляем значения по умолчанию (но пользователь может их изменить)
                if full_name and full_name.strip():
                    self.name_input.default = full_name
                    self.name_input.placeholder = "Данные автозаполнены из базы"
                
                if ic_static:
                    self.static_input.default = ic_static
                    self.static_input.placeholder = "Данные автозаполнены из базы"
                
                logger.info(f"Successfully loaded user data for {self.user_id}: {full_name}, {ic_static}")
            else:
                logger.warning(f"User {self.user_id} not found in personnel database - form will be empty")
                self.name_input.placeholder = "Введите ваше Имя Фамилия (данные не найдены в базе)"
                self.static_input.placeholder = "Введите ваш статик (данные не найдены в базе)"
                
        except Exception as e:
            logger.error(f"Error loading user data for {self.user_id}: {e}")
            # Если ошибка загрузки - оставляем поля пустыми
            self.name_input.placeholder = "Введите ваше Имя Фамилия (ошибка загрузки данных)"
            self.static_input.placeholder = "Введите ваш статик (ошибка загрузки данных)"
    
    def format_static(self, static_input: str) -> str:
        """Auto-format static number to standard format"""
        digits_only = re.sub(r'\D', '', static_input.strip())
        
        if len(digits_only) == 5:
            return f"{digits_only[:2]}-{digits_only[2:]}"
        elif len(digits_only) == 6:
            return f"{digits_only[:3]}-{digits_only[3:]}"
        else:
            return ""
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle Stage 1 submission"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # ПРОВЕРКА АКТИВНЫХ ЗАЯВЛЕНИЙ В ПЕРВУЮ ОЧЕРЕДЬ
            # Если пропустили проверку при нажатии кнопки - проверяем здесь
            from .views import check_user_active_applications
            active_check = await check_user_active_applications(
                interaction.guild, 
                interaction.user.id
            )
            
            if active_check['has_active']:
                departments_list = ", ".join(active_check['departments'])
                await interaction.followup.send(
                    f"❌ **У вас уже есть активное заявление на рассмотрении**\n\n"
                    f"📋 Подразделения: **{departments_list}**\n"
                    f"⏳ Дождитесь рассмотрения текущего заявления перед подачей нового.\n\n"
                    f"💡 Активные заявления можно найти в каналах заявлений соответствующих подразделений.",
                    ephemeral=True
                )
                return
            
            # УМНОЕ АВТОЗАПОЛНЕНИЕ - попытка загрузить данные если их не было
            name_value = self.name_input.value.strip()
            static_value = self.static_input.value.strip()
            
            # Если пользователь НЕ заполнил поля, пытаемся загрузить из базы
            if (not name_value or not static_value) and self.user_ic_data is None:
                logger.info(f"🔄 User {self.user_id} has empty fields, trying to load from database...")
                await self._load_user_data_async()
                
                # Автозаполняем пустые поля, если данные загрузились
                if self.user_ic_data:
                    ic_first_name = self.user_ic_data.get('first_name', '')
                    ic_last_name = self.user_ic_data.get('last_name', '')
                    ic_static = self.user_ic_data.get('static', '')
                    
                    full_name = f"{ic_first_name} {ic_last_name}".strip()
                    
                    # Автозаполняем только пустые поля
                    if not name_value and full_name:
                        name_value = full_name
                        logger.info(f"✅ Auto-filled name for {self.user_id}: {full_name}")
                    
                    if not static_value and ic_static:
                        static_value = ic_static  
                        logger.info(f"✅ Auto-filled static for {self.user_id}: {ic_static}")
            
            # Загружаем данные пользователя асинхронно (если еще не загружены)
            if self.user_ic_data is None:
                await self._load_user_data_async()
            
            # Validate static - используем заполненное значение
            formatted_static = self.format_static(static_value)
            if not formatted_static:
                await interaction.followup.send(
                    "❌ **Ошибка валидации статика**\n"
                    "Статик должен содержать ровно 5 или 6 цифр.\n"
                    "**Примеры:** `123456` → `123-456`, `12345` → `12-345`",
                    ephemeral=True
                )
                return
            
            # Validate document link
            document_url = self.document_input.value.strip()
            if not self._validate_url(document_url):
                await interaction.followup.send(
                    "❌ **Ошибка валидации ссылки**\n"
                    "Пожалуйста, укажите корректную ссылку на документ.\n"
                    "Поддерживаются внешние ссылки на изображения.",
                    ephemeral=True
                )
                return
            
            # Store Stage 1 data - используем автозаполненные значения
            stage1_data = {
                'name': name_value,
                'static': formatted_static,
                'document_url': document_url,
                'reason': self.reason_input.value.strip(),
                'department_code': self.department_code,
                'application_type': self.application_type
            }
            
            # Create draft embed
            draft_embed = self._create_draft_embed(stage1_data, interaction.user)
            
            # Create view with continue/cancel buttons
            view = Stage1ReviewView(stage1_data)
            
            await interaction.followup.send(
                "📋 **Черновик заявления - IC Информация**\n"
                "Проверьте данные и выберите действие:",
                embed=draft_embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in Stage 1 application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                ephemeral=True
            )
    
    def _validate_url(self, url: str) -> bool:
        """Validate if URL is a valid link"""
        if not url:
            return False
        
        # Basic URL validation
        url_lower = url.lower()
        return (
            url.startswith(('http://', 'https://')) or
            url.startswith('https://cdn.discordapp.com/') or
            url.startswith('https://media.discordapp.net/')
        )
    
    def _create_draft_embed(self, stage1_data: Dict, user: discord.Member) -> discord.Embed:
        """Create draft embed for Stage 1 data"""
        app_type_text = "Заявление на вступление" if stage1_data['application_type'] == 'join' else "Заявление на перевод"
        
        embed = discord.Embed(
            title=f"📋 Черновик: {app_type_text} в {stage1_data['department_code']}",
            description="**Этап 1: IC Информация**",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone(timedelta(hours=3)))
        )
        
        embed.set_author(
            name=f"{user.display_name} ({user.name})",
            icon_url=user.display_avatar.url
        )
        
        embed.add_field(
            name="👤 Имя Фамилия",
            value=stage1_data['name'],
            inline=True
        )
        
        embed.add_field(
            name="🏷️ Статик",
            value=stage1_data['static'],
            inline=True
        )
        
        embed.add_field(
            name="📄 Документ",
            value=f"[Ссылка на документ]({stage1_data['document_url']})",
            inline=False
        )
        
        embed.add_field(
            name="💭 Причины выбора подразделения",
            value=stage1_data['reason'],
            inline=False
        )
        
        embed.set_footer(text="Этап 1/2 - IC Информация заполнена")
        
        return embed


class Stage1ReviewView(ui.View):
    """View for reviewing Stage 1 data with continue/cancel options"""
    
    def __init__(self, stage1_data: Dict):
        super().__init__(timeout=300)
        self.stage1_data = stage1_data
    
    @ui.button(label="❌ Отменить", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel the application"""
        await interaction.response.edit_message(
            content="❌ **Заявление отменено**\n"
                   "Вы можете начать заново в любое время.\n\n"
                   "*Это сообщение будет удалено через 5 секунд...*",
            embed=None,
            view=None
        )
        
        # Delete the ephemeral message after a short delay
        await asyncio.sleep(5)
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass  # Message already deleted
    
    @ui.button(label="➡️ Продолжить", style=discord.ButtonStyle.green)
    async def continue_button(self, interaction: discord.Interaction, button: ui.Button):
        """Continue to Stage 2"""
        try:
            # Create Stage 2 modal
            modal = DepartmentApplicationStage2Modal(self.stage1_data)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error proceeding to Stage 2: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при переходе к следующему этапу.",
                ephemeral=True
            )


class DepartmentApplicationStage2Modal(ui.Modal):
    """Stage 2: OOC Information modal for department applications"""
    
    def __init__(self, stage1_data: Dict):
        self.stage1_data = stage1_data
        
        super().__init__(
            title=f"Заявление в {stage1_data['department_code']} - OOC Информация",
            timeout=300
        )
        
        self._setup_fields()
    
    def _setup_fields(self):
        """Setup OOC fields"""
        
        self.real_name_input = ui.TextInput(
            label="Реальное имя",
            placeholder="Как к вам обращаться в голосовом чате",
            max_length=50,
            required=True
        )
        self.add_item(self.real_name_input)
        
        self.age_input = ui.TextInput(
            label="Возраст",
            placeholder="Ваш возраст (или укажите предпочитаемый диапазон)",
            max_length=20,
            required=True
        )
        self.add_item(self.age_input)
        
        self.timezone_input = ui.TextInput(
            label="Часовой пояс",
            placeholder="МСК, МСК+3, МСК-1 и т.д.",
            max_length=20,
            required=True
        )
        self.add_item(self.timezone_input)
        
        self.online_hours_input = ui.TextInput(
            label="Онлайн в день",
            placeholder="Примерно сколько часов в день вы играете",
            max_length=50,
            required=True
        )
        self.add_item(self.online_hours_input)
        
        self.prime_time_input = ui.TextInput(
            label="Прайм-тайм",
            placeholder="В какое время вы обычно наиболее активны",
            max_length=100,
            required=True
        )
        self.add_item(self.prime_time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle Stage 2 submission and create final application"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get age value (no validation)
            age_value = self.age_input.value.strip()
            
            # Combine all data
            complete_application_data = {
                **self.stage1_data,
                'ooc_data': {
                    'real_name': self.real_name_input.value.strip(),
                    'age': age_value,
                    'timezone': self.timezone_input.value.strip(),
                    'online_hours': self.online_hours_input.value.strip(),
                    'prime_time': self.prime_time_input.value.strip()
                },
                'user_id': interaction.user.id,
                'timestamp': datetime.now(timezone(timedelta(hours=3))).isoformat(),
                'status': 'pending'
            }
            
            # Create final draft embed
            final_embed = self._create_final_draft_embed(complete_application_data, interaction.user)
            
            # Create final review view
            view = FinalReviewView(complete_application_data)
            
            await interaction.followup.send(
                "📋 **Финальный черновик заявления**\n"
                "Проверьте все данные перед отправкой:",
                embed=final_embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in Stage 2 application: {e}")
            await interaction.followup.send(
                "❌ Произошла ошибка. Попробуйте еще раз.",
                ephemeral=True
            )
    
    def _create_final_draft_embed(self, application_data: Dict, user: discord.Member) -> discord.Embed:
        """Create final draft embed with all data"""
        app_type_text = "Заявление на вступление" if application_data['application_type'] == 'join' else "Заявление на перевод"
        
        embed = discord.Embed(
            title=f"📋 {app_type_text} в {application_data['department_code']}",
            description="**Финальный черновик - готов к отправке**",
            color=discord.Color.blue(),
            timestamp=datetime.fromisoformat(application_data['timestamp']).replace(tzinfo=timezone(timedelta(hours=3)))
        )
        
        embed.set_author(
            name=f"{user.display_name} ({user.name})",
            icon_url=user.display_avatar.url
        )
        
        # IC Data
        embed.add_field(
            name="📋 IC Информация",
            value=f"**Имя:** {application_data['name']}\n"
                  f"**Статик:** {application_data['static']}\n"
                  f"**Документ:** [Ссылка]({application_data['document_url']})",
            inline=False
        )
        
        embed.add_field(
            name="💭 Причины выбора подразделения",
            value=application_data['reason'],
            inline=False
        )
        
        # OOC Data
        ooc_data = application_data['ooc_data']
        embed.add_field(
            name="👤 OOC Информация",
            value=f"**Имя:** {ooc_data['real_name']}\n"
                  f"**Возраст:** {ooc_data['age']}\n"
                  f"**Часовой пояс:** {ooc_data['timezone']}\n"
                  f"**Онлайн в день:** {ooc_data['online_hours']}\n"
                  f"**Прайм-тайм:** {ooc_data['prime_time']}",
            inline=False
        )
        
        embed.set_footer(text="Готов к отправке - проверьте данные")
        
        return embed


class FinalReviewView(ui.View):
    """Final review view with send/cancel options"""
    
    def __init__(self, application_data: Dict):
        super().__init__(timeout=300)
        self.application_data = application_data
    
    @ui.button(label="❌ Отменить", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel the application"""
        await interaction.response.edit_message(
            content="❌ **Заявление отменено**\n"
                   "Вы можете начать заново в любое время.\n\n"
                   "*Это сообщение будет удалено через 5 секунд...*",
            embed=None,
            view=None
        )
        
        # Delete the ephemeral message after a short delay
        await asyncio.sleep(5)
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass  # Message already deleted
    
    @ui.button(label="📨 Отправить заявление", style=discord.ButtonStyle.green)
    async def send_button(self, interaction: discord.Interaction, button: ui.Button):
        """Send the final application"""
        try:
            await interaction.response.defer()
            
            # Check for duplicate applications before sending
            from .views import check_user_active_applications
            active_check = await check_user_active_applications(
                interaction.guild, 
                interaction.user.id
            )
            
            if active_check['has_active']:
                departments_list = ", ".join(active_check['departments'])
                await interaction.edit_original_response(
                    content=f"❌ **У вас уже есть активное заявление на рассмотрении**\n\n"
                            f"📋 Подразделения: **{departments_list}**\n"
                            f"⏳ Дождитесь рассмотрения текущего заявления перед подачей нового.\n\n"
                            f"💡 Активные заявления можно найти в каналах заявлений соответствующих подразделений.",
                    embed=None,
                    view=None
                )
                return
            
            # Get department channel
            channel_id = ping_manager.get_department_channel_id(self.application_data['department_code'])
            if not channel_id:
                await interaction.edit_original_response(
                    content="❌ Канал для заявлений в это подразделение не настроен. Обратитесь к администратору.",
                    embed=None,
                    view=None
                )
                return
            
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.edit_original_response(
                    content="❌ Канал для заявлений не найден. Обратитесь к администратору.",
                    embed=None,
                    view=None
                )
                return
            
            # Create application embed for moderation
            embed = self._create_moderation_embed(self.application_data, interaction.user)
            
            # Create moderation view
            from .views import DepartmentApplicationView
            view = DepartmentApplicationView(self.application_data)
            view.setup_buttons()
            
            # Prepare content with pings for target department
            content = self._create_application_content(interaction.user, interaction.guild)
            
            # Send to department channel
            message = await channel.send(content=content, embed=embed, view=view)
            
            # Clear user's cache since they now have an active application
            from .views import _clear_user_cache
            _clear_user_cache(interaction.user.id)
            
            # Store application data
            self.application_data['message_id'] = message.id
            self.application_data['channel_id'] = channel.id
            
            # Confirm to user and delete the ephemeral message
            await interaction.edit_original_response(
                content=f"✅ **Заявление отправлено!**\n"
                        f"Ваше заявление в подразделение **{self.application_data['department_code']}** "
                        f"отправлено на рассмотрение модерации.\n\n"
                        f"📍 Канал: {channel.mention}\n"
                        f"⏰ Время обработки: обычно до 24 часов\n\n"
                        f"*Это сообщение будет удалено через 10 секунд...*",
                embed=None,
                view=None
            )
            
            # Delete the ephemeral message after a short delay
            await asyncio.sleep(10)
            try:
                await interaction.delete_original_response()
            except discord.NotFound:
                pass  # Message already deleted
            
        except Exception as e:
            logger.error(f"Error sending application: {e}")
            await interaction.edit_original_response(
                content="❌ Произошла ошибка при отправке заявления. Попробуйте еще раз.",
                embed=None,
                view=None
            )
    
    def _create_moderation_embed(self, application_data: Dict, user: discord.Member) -> discord.Embed:
        """Create embed for moderation"""
        app_type_text = "Заявление на вступление" if application_data['application_type'] == 'join' else "Заявление на перевод"
        
        embed = discord.Embed(
            description=f"## {app_type_text} в {application_data['department_code']} от {user.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.fromisoformat(application_data['timestamp']).replace(tzinfo=timezone(timedelta(hours=3)))
        )
        
        embed.set_author(
            name=f"{user.display_name} ({user.name})",
            icon_url=user.display_avatar.url
        )
        
        # IC Information
        embed.add_field(
            name="📋 IC Информация",
            value=f"**Имя Фамилия:** {application_data['name']}\n"
                  f"**Статик:** {application_data['static']}\n"
                  f"**Документ:** [Ссылка на документ]({application_data['document_url']})",
            inline=False
        )
        
        embed.add_field(
            name="💭 Причины выбора подразделения",
            value=application_data['reason'],
            inline=False
        )
        
        # OOC Information
        ooc_data = application_data['ooc_data']
        embed.add_field(
            name="👤 OOC Информация",
            value=f"**Имя:** {ooc_data['real_name']}\n"
                  f"**Возраст:** {ooc_data['age']}\n"
                  f"**Часовой пояс:** {ooc_data['timezone']}\n"
                  f"**Онлайн в день:** {ooc_data['online_hours']}\n"
                  f"**Прайм-тайм:** {ooc_data['prime_time']}",
            inline=False
        )
        
        # Status
        embed.add_field(
            name="📊 Статус",
            value="🔄 На рассмотрении",
            inline=True
        )
        
        embed.set_footer(text=f"ID заявления: {application_data['user_id']}")
        
        return embed
    
    def _create_application_content(self, user: discord.Member, guild: discord.Guild) -> str:
        """
        Create content with pings for the application message
        
        For new applications: ping roles for target department  
        For transfers: ping roles for target department + current department
        """
        from utils.ping_manager import PingManager
        ping_manager = PingManager()
        
        content_lines = []
        
        # Get ping roles for target department (where application is being submitted)
        target_ping_roles = ping_manager.get_ping_roles_for_context(
            self.application_data['department_code'], 
            'applications', 
            guild
        )
        
        if target_ping_roles:
            target_mentions = [role.mention for role in target_ping_roles]
            content_lines.append(' '.join(target_mentions))
        
        # Check if this is a transfer (user has current department)
        current_department = ping_manager.get_user_department_code(user)
        if current_department and current_department != self.application_data['department_code']:
            # This is a transfer - add pings for current department on second line
            current_ping_roles = ping_manager.get_ping_roles_for_context(
                current_department,
                'applications',  # или можно использовать 'general'
                guild
            )
            
            if current_ping_roles:
                current_mentions = [role.mention for role in current_ping_roles]
                content_lines.append(' '.join(current_mentions))
        
        return '\n'.join(content_lines) if content_lines else ""
