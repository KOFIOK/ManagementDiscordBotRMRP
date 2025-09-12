"""
Система помощи и справочной информации
Интерактивное меню с подробной документацией по всем командам и функциям бота
"""
import discord
from discord import app_commands
from discord.ext import commands
from utils.config_manager import is_moderator_or_admin, is_administrator, load_config


class HelpView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, is_mod: bool, is_admin: bool):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id
        self.is_mod = is_mod
        self.is_admin = is_admin
        
        # Добавляем кнопки в зависимости от прав пользователя
        self._setup_buttons()
    
    def _setup_buttons(self):
        """Настройка кнопок в зависимости от прав пользователя"""
        if self.is_mod:
            # Кнопки для модераторов
            self.add_item(ModeratorCommandsButton())
            self.add_item(PersonnelProcessesButton())
            self.add_item(WarehouseButton())
            self.add_item(PromotionSystemButton())  # Отключенная кнопка
            self.add_item(ModerationButton())
            self.add_item(AboutSystemButton())
            
        if self.is_admin:
            # Дополнительные кнопки для администраторов
            self.add_item(AdminCommandsButton())
            self.add_item(TechnicalCommandsButton())
            
        # Кнопка "Главная" для всех (модераторов и выше)
        if self.is_mod:
            self.add_item(BackToMainButton())

    async def on_timeout(self):
        # Отключаем кнопки при истечении времени
        for item in self.children:
            item.disabled = True


class ModeratorCommandsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Команды модераторов", style=discord.ButtonStyle.primary, emoji="👮")
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👮 Команды модераторов",
            description="Основные команды для модераторов",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Доступные команды:",
            value=(
                "`/аудит сотрудник:@user действие:список-действий` **`необязательно:`***`подразделение: должность: звание: причина:`* - Добавить запись в кадровый аудит\n"
                "`/чс нарушитель:@user срок:14/30-дней причина:текст доказательства:ссылка-на-кадровый` - Добавить пользователя в чёрный список\n"
                "`/help`, `/хэлп`, `/помощь` - Показать это меню помощи\n"
                "\n**Поддерживается система __приложений__ Discord!**\n"
                "- Нажмите ПКМ по пользователю, затем выберите `Приложения`.\n"
                "- Выберите необходимый пункт модерации и заполните краткую форму."
            ),
            inline=False
        )
        
        embed.set_footer(text="👮 Команды доступны только модераторам и выше")
        await interaction.response.edit_message(embed=embed, view=self.view)


class PersonnelProcessesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Кадровые процессы", style=discord.ButtonStyle.success, emoji="📝")
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📝 Кадровые процессы и заявки",
            description="Автоматические системы обработки кадровых документов",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📄 Рапорты на увольнение",
            value=(
                "• **Подача** - отдельный канал для рапортов на увольнение\n"
                "• **Модерация** - кнопки ✅ Одобрить / ❌ Отказать / ✏️ Изменить / 🗑️ Удалить\n"
                "• **Автоувольнение** - при покидании сервера рапорт будет подан автоматически\n"
                "• **Роли и никнейм** - автоматически снимаются и изменяются после увольнения."
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 Заявления в подразделения",
            value=(
                "• **Автозаполнение** - данные подтягиваются из системы\n"
                "• **Автоматизация ролей** - назначение должностей при одобрении."
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎖️ Заявки на получение ролей",
            value=(
                "• **Роли военнослужащих** - для рядовых с призывов\n"
                "• **Роли гос. служащих** - для замов и лидеров фракций\n"
            ),
            inline=False
        )
        
        embed.set_footer(text="📋 Все процессы автоматизированы и интегрированы с Google Sheets")
        await interaction.response.edit_message(embed=embed, view=self.view)


class WarehouseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Склад (от Майора)", style=discord.ButtonStyle.secondary, emoji="📦")
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📦 Система складского учёта",
            description="Управление складским имуществом и аудит",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📋 Запросы складского имущества",
            value=(
                "• **Множественные заявки** - групповые запросы\n"
                "• **Кэширование** - быстрый доступ к данным пользователей"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔍 Аудит склада",
            value=(
                "• **Отчёты** - детальная отчётность\n"
                "• **Автоматические уведомления** - система оповещений"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚡ Оптимизация производительности",
            value=(
                "• **Предзагрузка кэша** - быстрый доступ к данным\n"
                "• **Батчевые запросы** - оптимизированные запросы к БД\n"
                "• **Система кэширования** - минимизация нагрузки\n"
                "• **Фоновые задачи** - асинхронная обработка"
            ),
            inline=False
        )
        
        embed.set_footer(text="📦 Складская система оптимизирована для высокой производительности")
        await interaction.response.edit_message(embed=embed, view=self.view)


class PromotionSystemButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Система повышения", style=discord.ButtonStyle.secondary, emoji="⭐", disabled=True)
    
    async def callback(self, interaction: discord.Interaction):
        # Эта кнопка отключена, но на всякий случай
        await interaction.response.send_message("⚠️ Система повышения временно недоступна", ephemeral=True)


class ModerationButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Модерация", style=discord.ButtonStyle.danger, emoji="🛡️")
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ Система модерации",
            description="Права доступа и возможности модераторов",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="👮 Права модераторов",
            value=(
                "• **Обработка увольнений** - кнопки одобрения/отклонения\n"
                "• **Модерация ролевых заявок** - контроль назначения ролей\n"
                "• **Складские запросы** - одобрение выдачи имущества\n"
                "• **Иерархическая модерация** - согласно воинским званиям\n"
                "• **Кадровый аудит** - доступ к системе учёта"
            ),
            inline=False
        )
        
        embed.add_field(
            name="👑 Права администраторов",
            value=(
                "• **Все права модератора** + расширенные возможности\n"
                "• **Настройка системы** - команда `/settings`\n"
                "• **Управление персоналом** - команды `/moder` и `/admin`\n"
                "• **Самомодерация** - могут одобрять собственные заявки\n"
                "• **Высший уровень иерархии** - модерируют всех"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔒 Система безопасности",
            value=(
                "• **Иерархические ограничения** - строгий контроль прав\n"
                "• **Автоматические уведомления** - при назначении модераторов\n"
                "• **Логирование действий** - полный аудит операций\n"
                "• **Защита конфигурации** - резервное копирование"
            ),
            inline=False
        )
        
        embed.set_footer(text="🛡️ Система защищена многоуровневой иерархией прав доступа")
        await interaction.response.edit_message(embed=embed, view=self.view)


class AdminCommandsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Команды администраторов", style=discord.ButtonStyle.primary, emoji="👑")
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👑 Команды администраторов",
            description="Полный список всех команд бота (22 команды)",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="🔧 Команды горячей перезагрузки",
            value=(
                "`/reload_config` - Горячая перезагрузка конфигурации\n"
                "`/migrate-ping-settings` - Миграция настроек пингов"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Управление системой",
            value=(
                "`/settings` - Универсальная настройка каналов и системы\n"
                "`/config-backup` - Управление резервными копиями конфигурации\n"
                "`/config-export` - Экспорт конфигурации для переноса\n"
                "`/moder add/remove/list` - Управление модераторами\n"
                "`/admin add/remove/list` - Управление администраторами\n"
                "`/send_welcome_message` - Отправить приветственное сообщение"
            ),
            inline=False
        )
        
        embed.add_field(
            name="👥 Кадровые команды",
            value=(
                "`/аудит сотрудник:@user действие:список-действий` **`необязательно:`***`подразделение: должность: звание: причина:`* - Добавить запись в кадровый аудит\n"
                "`/чс нарушитель:@user срок:14/30-дней причина:текст доказательства:ссылка-на-кадровый` - Добавить пользователя в чёрный список\n"
                "`/help`, `/хэлп`, `/помощь` - Показать это меню помощи\n"
                "`/расформ` **`необязательно:`***`роль:название-роли`* - Расформировать роли (убрать у всех)\n"
                "`/выгрузить-кадровый начиная_с:дата` - Экспорт кадрового аудита в CSV"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Технические команды",
            value=(
                "`/reload_config` - Горячая перезагрузка конфигурации\n"
                "`/migrate-ping-settings` - Миграция настроек пингов\n"
                "`/cache-stats` - Статистика использования кэша\n"
                "`/cache-refresh` - Обновление кэша пользователя\n"
                "`/cache_clear` - Полная очистка кэша\n"
                "`/cache_invalidate` - Удалить пользователя из кэша\n"
                "`/cache_test_user` - Тестирование кэша пользователя\n"
                "`/global_cache_status` - Полный статус кэширования\n"
                "`/warehouse_test_user` - Тестирование складского кэша"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📅 Уведомления и расписание",
            value=(
                "`/set_notification_time` - Настроить время уведомлений\n"
                "`/show_notification_schedule` - Показать расписание\n"
                "`/test_notification` - Отправить тестовое уведомление\n"
                "`/help` `/хелп` `/помощь` - Показать меню помощи"
            ),
            inline=False
        )
        
        embed.set_footer(text="👑 Полный доступ ко всем командам системы")
        await interaction.response.edit_message(embed=embed, view=self.view)


class TechnicalCommandsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Технические команды", style=discord.ButtonStyle.secondary, emoji="🔧")
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔧 Технические команды и диагностика",
            description="Команды для администрирования и диагностики системы",
            color=discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="📊 Система кэширования",
            value=(
                "`/reload_config` - Горячая перезагрузка конфигурации\n"
                "`/migrate-ping-settings` - Миграция настроек пингов\n"
                "`/cache_stats` - Статистика использования кэша\n"
                "`/cache_clear` - Полная очистка кэша\n"
                "`/cache_invalidate` - Удалить пользователя из кэша\n"
                "`/cache_test_user` - Тестирование кэша пользователя\n"
                "`/global_cache_status` - Полный статус кэширования\n"
                "`/warehouse_test_user` - Тестирование складского кэша"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📅 Система уведомлений",
            value=(
                "`/set_notification_time` - Настроить время уведомлений\n"
                "`/show_notification_schedule` - Показать расписание\n"
                "`/test_notification` - Отправить тестовое уведомление\n"
                "• **Автоматические ежедневные напоминания**\n"
                "• **Уведомления по подразделениям**"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🛠️ Диагностика и мониторинг",
            value=(
                "• **Мониторинг производительности** - отслеживание нагрузки\n"
                "• **Логирование ошибок** - детальные логи операций\n"
                "• **Статистика использования** - анализ активности\n"
                "• **Проверка целостности данных** - валидация конфигурации"
            ),
            inline=False
        )
        
        embed.set_footer(text="🔧 Технические команды для поддержания стабильности системы")
        await interaction.response.edit_message(embed=embed, view=self.view)


class AboutSystemButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="О системе", style=discord.ButtonStyle.secondary, emoji="ℹ️")
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 О системе кадрового управления ВС РФ",
            description="Комплексная автоматизированная система управления",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name="🎯 Основные возможности",
            value=(
                "• **Автоматизация кадровых процессов** - от подачи до исполнения\n"
                "• **Система заявлений в подразделения** - двухэтапная подача с автозаполнением\n"
                "• **Горячая перезагрузка** - изменения без перезапуска бота\n"
                "• **Интеграция с Google Sheets** - централизованное хранение\n"
                "• **Многоуровневая модерация** - иерархический контроль\n"
                "• **Складской учёт** - полный контроль имущества\n"
                "• **Медицинская система** - управление мед. процессами"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Статистика системы",
            value=(
                "• **Команд:** 25+ (слэш-команды)\n"
                "• **Модулей:** 10+ cogs + 20+ utils\n"
                "• **Интеграций:** Google Sheets, Discord API\n"
                "• **Автоматических процессов:** 20+\n"
                "• **Поддерживаемых ролей:** Неограниченно"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Технические особенности",
            value=(
                "• **Горячая перезагрузка** - изменения без перезапуска\n"
                "• **Высокая производительность** - оптимизированные алгоритмы\n"
                "• **Надёжность** - система резервного копирования\n"
                "• **Масштабируемость** - поддержка больших серверов\n"
                "• **Безопасность** - многоуровневая защита данных\n"
                "• **Автоматизация** - минимум ручной работы"
            ),
            inline=False
        )
        
        embed.set_footer(
            text="💻 Система разработана специально для нужд ВС РФ",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        await interaction.response.edit_message(embed=embed, view=self.view)


class BackToMainButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Главная", style=discord.ButtonStyle.success, emoji="🏠")
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 Система кадрового управления ВС РФ",
            description="Добро пожаловать в центр помощи! Выберите категорию для получения подробной информации.",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow()
        )
        
        # Определяем, какие категории показать в зависимости от прав
        categories = []
        if self.view.is_mod:
            categories.extend([
                "👮 **Команды модераторов** - основные команды для модераторов",
                "📝 **Кадровые процессы** - увольнения, заявления в подразделения, роли",
                "📦 **Склад (от Майора)** - складской учёт и инвентаризация",
                "⭐ **Система повышения** - (временно недоступна)",
                "🛡️ **Модерация** - права доступа и система безопасности",
                "ℹ️ **О системе** - техническая информация и возможности"
            ])
        
        if self.view.is_admin:
            categories.extend([
                "👑 **Команды администраторов** - полный список всех команд",
                "🔧 **Технические команды** - горячая перезагрузка, диагностика, кэширование"
            ])
        
        embed.add_field(
            name="📋 Доступные категории:",
            value="\n".join(categories),
            inline=False
        )
        
        embed.add_field(
            name="🚀 Быстрые команды:",
            value=(
                "`/settings` - Настройка системы\n"
                "`/reload_config` - Горячая перезагрузка конфигурации\n"
                "`/moder` - Управление модераторами\n"
                "`/admin` - Управление администраторами\n"
                "`/help` - Это меню помощи"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Полезная информация:",
            value=(
                "• Все заявки обрабатываются через **кнопки** в интерфейсе\n"
                "• **Двухэтапные заявления** в подразделения с автозаполнением\n"
                "• **Горячая перезагрузка** изменений без перезапуска бота\n"
                "• Система автоматически **логирует** все действия\n"
                "• **Права доступа** строго контролируются иерархией\n"
                "• Данные синхронизируются с **Google Sheets**"
            ),
            inline=False
        )
        
        embed.set_footer(
            text="Выберите категорию ниже для получения подробной информации",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def _process_help_command(self, interaction: discord.Interaction):
        """Общая логика обработки команд помощи"""
        try:
            # Загружаем конфигурацию
            config = load_config()
            
            # Проверяем права пользователя
            is_mod = is_moderator_or_admin(interaction.user, config)
            is_admin = is_administrator(interaction.user, config)
        except Exception as e:
            # Если не удалось загрузить конфигурацию, считаем пользователя обычным
            print(f"Ошибка при загрузке конфигурации в help_system: {e}")
            is_mod = False
            is_admin = False
        
        if is_mod:
            # Для модераторов и выше - интерактивное меню с кнопками
            embed = discord.Embed(
                title="🤖 Система кадрового управления ВС РФ",
                description="Добро пожаловать в центр помощи! Выберите категорию для получения подробной информации.",
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow()
            )
            
            # Определяем, какие категории показать в зависимости от прав
            categories = []
            if is_mod:
                categories.extend([
                    "👮 **Команды модераторов** - основные команды для модераторов",
                    "📝 **Кадровые процессы** - увольнения, роли, медицина, отгулы",
                    "📦 **Склад (от Майора)** - складской учёт и инвентаризация",
                    "⭐ **Система повышения** - (временно недоступна)",
                    "🛡️ **Модерация** - права доступа и система безопасности",
                    "ℹ️ **О системе** - техническая информация и возможности"
                ])
            
            if is_admin:
                categories.extend([
                    "👑 **Команды администраторов** - полный список всех команд",
                    "🔧 **Технические команды** - диагностика и кэширование"
                ])
            
            embed.add_field(
                name="📋 Доступные категории:",
                value="\n".join(categories),
                inline=False
            )
            
            embed.add_field(
                name="🚀 Быстрые команды:",
                value=(
                    "`/settings` - Настройка системы\n"
                    "`/moder` - Управление модераторами\n"
                    "`/admin` - Управление администраторами\n"
                    "`/help` - Это меню помощи"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💡 Полезная информация:",
                value=(
                    "• Все заявки обрабатываются через **кнопки** в интерфейсе\n"
                    "• Система автоматически **логирует** все действия\n"
                    "• **Права доступа** строго контролируются иерархией\n"
                    "• Данные синхронизируются с **Google Sheets**"
                ),
                inline=False
            )
            
            embed.set_footer(
                text="Выберите категорию ниже для получения подробной информации",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            view = HelpView(interaction.user.id, interaction.guild.id, is_mod, is_admin)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        else:
            # Для обычных пользователей - простое сообщение БЕЗ кнопок
            embed = discord.Embed(
                title="📖 Справочная информация",
                description="Добро пожаловать в систему кадрового управления ВС РФ!",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="🎯 Основные возможности:",
                value=(
                    "• **Подача заявок** - через кнопки в соответствующих каналах\n"
                    "• **Увольнение** - рапорт на увольнение в канале увольнений\n"
                    "• **Получение ролей** - заявки на военные и гражданские роли\n"
                    "• **Складские заявки** - запросы имущества через канал склада\n"
                    "• **Медицинские услуги** - запись к врачу и мед. регистрация"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📋 Как подать заявку:",
                value=(
                    "1. Найдите соответствующий канал (увольнения, роли, склад, мед. часть)\n"
                    "2. Нажмите на кнопку для подачи заявки\n"
                    "3. Заполните появившуюся форму\n"
                    "4. Дождитесь рассмотрения модератором\n"
                    "5. Получите уведомление о результате"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💡 Полезные советы:",
                value=(
                    "• Внимательно заполняйте все поля в формах\n"
                    "• Указывайте корректные данные\n"
                    "• Следите за уведомлениями в личных сообщениях\n"
                    "• При возникновении проблем обращайтесь к модераторам"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🔍 Нужна помощь?",
                value=(
                    "Если у вас есть вопросы или проблемы с использованием системы, "
                    "обратитесь к модераторам или администраторам сервера. "
                    "Они помогут вам разобраться с любыми вопросами."
                ),
                inline=False
            )
            
            embed.set_footer(
                text="Система автоматически обрабатывает все заявки и уведомления",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="help", description="Показать справочную информацию о боте")
    async def help_command(self, interaction: discord.Interaction):
        await self._process_help_command(interaction)

    @app_commands.command(name="хелп", description="Показать справочную информацию о боте")
    async def help_command_ru(self, interaction: discord.Interaction):
        await self._process_help_command(interaction)

    @app_commands.command(name="помощь", description="Показать справочную информацию о боте")
    async def help_command_help(self, interaction: discord.Interaction):
        await self._process_help_command(interaction)


async def setup(bot):
    await bot.add_cog(HelpSystem(bot))
