"""
Personnel management commands for Discord bot
Includes audit command integrated with PersonnelManager and PostgreSQL
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from utils.config_manager import load_config, is_moderator_or_admin, is_administrator
from utils.database_manager import PersonnelManager
from utils.nickname_manager import nickname_manager


class PersonnelCommands(commands.Cog):
    """Commands for personnel management using PersonnelManager and PostgreSQL"""
    
    def __init__(self, bot):
        self.bot = bot
        self.temporarily_disabled = False
        self._cached_settings = None
        self._cache_timestamp = None
        self._cache_duration = 300  # 5 minutes cache
    
    async def _check_disabled(self, interaction):
        """Проверка на временное отключение команд"""
        if self.temporarily_disabled:
            await interaction.response.send_message(
                "⚠️ Команды персонала временно отключены в процессе миграции на PostgreSQL.\n"
                "Основные функции бота (найм, увольнение через формы) работают в обычном режиме.",
                ephemeral=True
            )
            return True
        return False
    
    async def _get_settings_from_postgresql(self):
        """Получение настроек из PostgreSQL базы данных"""
        try:
            current_time = datetime.now()
            
            # Check cache
            if (self._cached_settings and self._cache_timestamp and 
                (current_time - self._cache_timestamp).seconds < self._cache_duration):
                return self._cached_settings
            
            # Get settings from database using get_db_cursor
            from utils.postgresql_pool import get_db_cursor
            
            settings = {
                'actions': [],
                'ranks': [],
                'departments': [],
                'positions': []
            }
            
            with get_db_cursor() as cursor:
                # Get actions
                try:
                    cursor.execute("SELECT name FROM actions ORDER BY name")
                    actions_result = cursor.fetchall()
                    settings['actions'] = [row['name'] for row in actions_result] if actions_result else []
                except Exception as e:
                    print(f"⚠️ Actions table not available: {e}")
                    settings['actions'] = []
                
                # Get ranks
                try:
                    cursor.execute("SELECT name FROM ranks ORDER BY name")
                    ranks_result = cursor.fetchall()
                    settings['ranks'] = [row['name'] for row in ranks_result] if ranks_result else []
                except Exception as e:
                    print(f"⚠️ Ranks table not available: {e}")
                    settings['ranks'] = []
                
                # Get subdivisions
                try:
                    cursor.execute("SELECT name FROM subdivisions ORDER BY name")
                    subdivisions_result = cursor.fetchall()
                    settings['departments'] = [row['name'] for row in subdivisions_result] if subdivisions_result else []
                except Exception as e:
                    print(f"⚠️ Subdivisions table not available: {e}")
                    settings['departments'] = []
                
                # Get positions
                try:
                    cursor.execute("SELECT name FROM positions ORDER BY name")
                    positions_result = cursor.fetchall()
                    settings['positions'] = [row['name'] for row in positions_result] if positions_result else []
                except Exception as e:
                    print(f"⚠️ Positions table not available: {e}")
                    settings['positions'] = []
            
            # If no data from PostgreSQL, use fallback
            if not any(settings.values()):
                print("⚠️ No data from PostgreSQL, using fallback settings")
                return self._get_fallback_settings()
            
            # Update cache
            self._cached_settings = settings
            self._cache_timestamp = current_time
            
            print(f"🔄 PostgreSQL settings loaded: {len(settings['actions'])} actions, {len(settings['ranks'])} ranks, {len(settings['departments'])} subdivisions, {len(settings['positions'])} positions")
            return settings
            
        except Exception as e:
            print(f"❌ Error loading settings from PostgreSQL: {e}")
            return self._get_fallback_settings()
    
    def _get_fallback_settings(self):
        """Возвращает базовые настройки если PostgreSQL недоступен"""
        return {
            'actions': [
                'Принят на службу',
                'Принят в подразделение',
                'Переведён в подразделение', 
                'Повышен в звании',
                'Понижен в звании',
                'Назначен на должность',
                'Снят с должности',
                'Уволен со службы'
            ],
            'departments': [
                'Военная Академия', 'УВП', 'ССО', 'РОиО', 'МР'
            ],
            'positions': [
                'Стрелок', 'Снайпер', 'Пулеметчик', 'Гранатометчик',
                'Командир отделения', 'Заместитель командира взвода',
                'Командир взвода', 'Командир роты'
            ],
            'ranks': [
                'Рядовой', 'Ефрейтор', 'Младший сержант', 'Сержант',
                'Старший сержант', 'Старшина', 'Прапорщик', 'Старший прапорщик',
                'Младший лейтенант', 'Лейтенант', 'Старший лейтенант', 'Капитан'
            ]
        }
    
    @app_commands.command(name="аудит", description="Добавить запись в кадровый аудит")
    @app_commands.describe(
        сотрудник="Выберите сотрудника",
        действие="Выберите действие",
        подразделение="Подразделение (необязательно)",
        должность="Должность (необязательно)", 
        звание="Звание (необязательно)",
        причина="Причина (для увольнения/приема на службу)"
    )
    async def audit_command(
        self,
        interaction: discord.Interaction,
        сотрудник: discord.Member,
        действие: str,
        подразделение: str = None,
        должность: str = None,
        звание: str = None,
        причина: str = None
    ):
        """Add personnel audit record using PersonnelManager"""
        
        # Check if disabled
        if await self._check_disabled(interaction):
            return
        
        # Check permissions
        config = load_config()
        if not is_moderator_or_admin(interaction.user, config):
            embed = discord.Embed(
                title="❌ Недостаточно прав",
                description="Эта команда доступна только модераторам и администраторам.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check if action is disabled
        disabled_audit_actions = config.get('disabled_audit_actions', [])
        if действие in disabled_audit_actions:
            embed = discord.Embed(
                title="❌ Действие отключено",
                description=f"Действие '{действие}' отключено администратором для команды /аудит.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Defer response as this might take time
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate required fields
            if действие == "Уволен со службы" and not причина:
                embed = discord.Embed(
                    title="❌ Требуется причина увольнения",
                    description="Для увольнения необходимо указать причину.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            elif действие == "Принят на службу" and not причина:
                embed = discord.Embed(
                    title="❌ Требуется причина принятия",
                    description="Для принятия на службу необходимо указать причину.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            elif действие not in ["Уволен со службы", "Принят на службу"] and not any([подразделение, должность, звание]):
                embed = discord.Embed(
                    title="❌ Ошибка заполнения",
                    description="Необходимо заполнить хотя бы одно из полей: подразделение, должность или звание.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Handle different actions with nickname integration
            if действие == "Принят на службу":
                # Это приём на службу - используем PersonnelManager + nickname_manager
                application_data = {
                    'user_id': сотрудник.id,
                    'username': сотрудник.display_name,
                    'name': сотрудник.display_name,  # Will be overridden if user provides specific name
                    'type': 'military',
                    'recruitment_type': 'призыв',
                    'rank': звание or 'Рядовой',
                    'subdivision': подразделение or 'Военная Академия',
                    'position': должность,
                    'reason': причина
                }
                
                # Используем PersonnelManager для приёма
                pm = PersonnelManager()
                success, message = await pm.process_role_application_approval(
                    application_data,
                    сотрудник.id,
                    interaction.user.id,
                    interaction.user.display_name
                )
                
                # Автоматически обновляем никнейм
                try:
                    # Извлекаем имя и фамилию из display_name или пользовательского ввода
                    full_name = сотрудник.display_name
                    name_parts = full_name.split()
                    
                    if len(name_parts) >= 2:
                        first_name = name_parts[0]
                        last_name = ' '.join(name_parts[1:])
                    else:
                        first_name = full_name
                        last_name = ''
                    
                    print(f"🎆 AUDIT COMMAND: Приём на службу {full_name} (звание: {звание})")
                    
                    # Используем nickname_manager
                    new_nickname = await nickname_manager.handle_hiring(
                        member=сотрудник,
                        rank_name=звание or 'Рядовой',
                        first_name=first_name,
                        last_name=last_name
                    )
                    
                    if new_nickname:
                        await сотрудник.edit(nick=new_nickname, reason=f"Команда аудита: {действие}")
                        print(f"✅ AUDIT NICKNAME: Установлен никнейм {new_nickname}")
                    
                except Exception as nickname_error:
                    print(f"⚠️ AUDIT NICKNAME ERROR: {nickname_error}")
                
                if success:
                    embed = discord.Embed(
                        title="✅ Принят на службу",
                        description=f"Пользователь {сотрудник.mention} успешно принят на службу.\n\n**Детали:**\n{message}",
                        color=discord.Color.green()
                    )
                else:
                    embed = discord.Embed(
                        title="❌ Ошибка при приеме на службу",
                        description=f"Не удалось принять пользователя {сотрудник.mention} на службу.\n\n**Ошибка:**\n{message}",
                        color=discord.Color.red()
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            
            elif действие == "Повышен в звании":
                # Повышение в звании с автоматическим обновлением никнейма
                try:
                    if not звание:
                        embed = discord.Embed(
                            title="❌ Ошибка валидации",
                            description="Для повышения в звании необходимо указать новое звание.",
                            color=discord.Color.red()
                        )
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
                    
                    print(f"🎆 AUDIT COMMAND: Повышение в звании {сотрудник.display_name} -> {звание}")
                    
                    # Используем nickname_manager для повышения
                    new_nickname = await nickname_manager.handle_promotion(
                        member=сотрудник,
                        new_rank_name=звание
                    )
                    
                    if new_nickname:
                        await сотрудник.edit(nick=new_nickname, reason=f"Команда аудита: {действие}")
                        embed = discord.Embed(
                            title="✅ Повышен в звании",
                            description=f"{сотрудник.mention} успешно повышен до звания **{звание}**.\n\nНикнейм автоматически обновлён: `{new_nickname}`",
                            color=discord.Color.green()
                        )
                        print(f"✅ AUDIT PROMOTION: Никнейм обновлён: {new_nickname}")
                    else:
                        embed = discord.Embed(
                            title="⚠️ Повышение с предупреждением",
                            description=f"{сотрудник.mention} повышен до звания **{звание}**, но никнейм не мог быть автоматически обновлён.\n\nПожалуйста, обновите никнейм вручную.",
                            color=discord.Color.orange()
                        )
                    
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    
                except Exception as e:
                    print(f"❌ AUDIT PROMOTION ERROR: {e}")
                    embed = discord.Embed(
                        title="❌ Ошибка повышения",
                        description=f"Произошла ошибка при повышении {сотрудник.mention}: {e}",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
            
            elif действие == "Переведён в подразделение":
                # Перевод в подразделение с автоматическим обновлением никнейма
                try:
                    if not подразделение:
                        embed = discord.Embed(
                            title="❌ Ошибка валидации",
                            description="Для перевода в подразделение необходимо указать подразделение.",
                            color=discord.Color.red()
                        )
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
                    
                    print(f"🎆 AUDIT COMMAND: Перевод {сотрудник.display_name} -> {подразделение}")
                    
                    # Маппинг названий подразделений на ключи
                    subdivision_mapping = {
                        'Военная Академия': 'military_academy',
                        'УВП': 'УВП',
                        'ССО': 'ССО',
                        'РОиО': 'РОиО',
                        'МР': 'МР'
                    }
                    
                    subdivision_key = subdivision_mapping.get(подразделение, подразделение)
                    
                    # Используем nickname_manager для перевода
                    new_nickname = await nickname_manager.handle_transfer(
                        member=сотрудник,
                        subdivision_key=subdivision_key,
                        rank_name=звание or 'Рядовой'
                    )
                    
                    if new_nickname:
                        await сотрудник.edit(nick=new_nickname, reason=f"Команда аудита: {действие}")
                        embed = discord.Embed(
                            title="✅ Переведён в подразделение",
                            description=f"{сотрудник.mention} успешно переведён в **{подразделение}**.\n\nНикнейм автоматически обновлён: `{new_nickname}`",
                            color=discord.Color.green()
                        )
                        print(f"✅ AUDIT TRANSFER: Никнейм обновлён: {new_nickname}")
                    else:
                        embed = discord.Embed(
                            title="⚠️ Перевод с предупреждением",
                            description=f"{сотрудник.mention} переведён в **{подразделение}**, но никнейм не мог быть автоматически обновлён.\n\nПожалуйста, обновите никнейм вручную.",
                            color=discord.Color.orange()
                        )
                    
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    
                except Exception as e:
                    print(f"❌ AUDIT TRANSFER ERROR: {e}")
                    embed = discord.Embed(
                        title="❌ Ошибка перевода",
                        description=f"Произошла ошибка при переводе {сотрудник.mention}: {e}",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                
            else:
                # Other actions - for now show that they need manual implementation
                embed = discord.Embed(
                    title="🚧 В разработке",
                    description=f"Действие '{действие}' пока не интегрировано с новой системой PersonnelManager.\n\n"
                               f"**Данные для обработки:**\n"
                               f"• Сотрудник: {сотрудник.mention}\n"
                               f"• Действие: {действие}\n"
                               f"• Подразделение: {подразделение or 'Не указано'}\n"
                               f"• Должность: {должность or 'Не указано'}\n"
                               f"• Звание: {звание or 'Не указано'}\n"
                               f"• Причина: {причина or 'Не указано'}",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            print(f"Error in audit command: {e}")
            embed = discord.Embed(
                title="❌ Ошибка команды",
                description="Произошла ошибка при выполнении команды аудита.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Autocomplete functions
    @audit_command.autocomplete('действие')
    async def action_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            settings = await self._get_settings_from_postgresql()
            actions = settings.get('actions', [])
            
            # Filter out disabled actions from config
            config = load_config()
            disabled_audit_actions = config.get('disabled_audit_actions', [])
            enabled_actions = [action for action in actions if action not in disabled_audit_actions]
            
            # Filter actions based on current input
            filtered = [action for action in enabled_actions if current.lower() in action.lower()]
            return [app_commands.Choice(name=action, value=action) for action in filtered[:25]]
        except Exception as e:
            print(f"Error in action autocomplete: {e}")
            # Fallback to basic settings
            settings = self._get_fallback_settings()
            actions = settings.get('actions', [])
            
            # Also apply filtering for fallback
            try:
                config = load_config()
                disabled_audit_actions = config.get('disabled_audit_actions', [])
                actions = [action for action in actions if action not in disabled_audit_actions]
            except:
                pass
            
            filtered = [action for action in actions if current.lower() in action.lower()]
            return [app_commands.Choice(name=action, value=action) for action in filtered[:25]]
    
    @audit_command.autocomplete('подразделение')
    async def department_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            settings = await self._get_settings_from_postgresql()
            departments = settings.get('departments', [])
            
            filtered = [dept for dept in departments if current.lower() in dept.lower()]
            return [app_commands.Choice(name=dept, value=dept) for dept in filtered[:25]]
        except Exception as e:
            print(f"Error in department autocomplete: {e}")
            settings = self._get_fallback_settings()
            departments = settings.get('departments', [])
            filtered = [dept for dept in departments if current.lower() in dept.lower()]
            return [app_commands.Choice(name=dept, value=dept) for dept in filtered[:25]]
    
    @audit_command.autocomplete('должность')
    async def position_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            settings = await self._get_settings_from_postgresql()
            positions = settings.get('positions', [])
            
            filtered = [pos for pos in positions if current.lower() in pos.lower()]
            return [app_commands.Choice(name=pos, value=pos) for pos in filtered[:25]]
        except Exception as e:
            print(f"Error in position autocomplete: {e}")
            settings = self._get_fallback_settings()
            positions = settings.get('positions', [])
            filtered = [pos for pos in positions if current.lower() in pos.lower()]
            return [app_commands.Choice(name=pos, value=pos) for pos in filtered[:25]]
    
    @audit_command.autocomplete('звание')
    async def rank_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            settings = await self._get_settings_from_postgresql()
            ranks = settings.get('ranks', [])
            
            filtered = [rank for rank in ranks if current.lower() in rank.lower()]
            return [app_commands.Choice(name=rank, value=rank) for rank in filtered[:25]]
        except Exception as e:
            print(f"Error in rank autocomplete: {e}")
            settings = self._get_fallback_settings()
            ranks = settings.get('ranks', [])
            filtered = [rank for rank in ranks if current.lower() in rank.lower()]
            return [app_commands.Choice(name=rank, value=rank) for rank in filtered[:25]]
    
    @app_commands.command(name="чс", description="Добавить пользователя в чёрный список")
    @app_commands.describe(
        нарушитель="Пользователь, которого нужно добавить в чёрный список",
        срок="Срок действия чёрного списка",
        причина="Причина добавления в чёрный список",
        доказательства="Ссылка на доказательства (кадровый аудит, сообщение и т.д.)"
    )
    @app_commands.choices(срок=[
        app_commands.Choice(name="14 дней", value=14),
        app_commands.Choice(name="30 дней", value=30)
    ])
    async def blacklist_add_command(
        self,
        interaction: discord.Interaction,
        нарушитель: discord.Member,
        срок: int,
        причина: str,
        доказательства: str = None
    ):
        """Add user to blacklist"""
        
        # Check if disabled
        if await self._check_disabled(interaction):
            return
        
        # Check permissions
        config = load_config()
        if not is_moderator_or_admin(interaction.user, config):
            embed = discord.Embed(
                title="❌ Недостаточно прав",
                description="Эта команда доступна только модераторам и администраторам.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Defer response
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Import audit logger
            from utils.audit_logger import audit_logger
            
            # Add to blacklist
            success, message = await audit_logger.add_to_blacklist_manual(
                guild=interaction.guild,
                target_user=нарушитель,
                moderator=interaction.user,
                reason=причина,
                duration_days=срок,
                evidence_url=доказательства,
                config=config
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Добавлен в чёрный список",
                    description=message,
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Ошибка добавления",
                    description=message,
                    color=discord.Color.red()
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in blacklist_add_command: {e}")
            import traceback
            traceback.print_exc()
            
            embed = discord.Embed(
                title="❌ Ошибка команды",
                description="Произошла ошибка при выполнении команды добавления в чёрный список.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="чс-удалить", description="Удалить пользователя из чёрного списка")
    @app_commands.describe(
        пользователь="Пользователь, которого нужно удалить из чёрного списка"
    )
    async def blacklist_remove_command(
        self,
        interaction: discord.Interaction,
        пользователь: discord.Member
    ):
        """Remove user from blacklist"""
        
        # Check if disabled
        if await self._check_disabled(interaction):
            return
        
        # Check permissions
        config = load_config()
        if not is_administrator(interaction.user, config):
            embed = discord.Embed(
                title="❌ Недостаточно прав",
                description="Эта команда доступна только администраторам.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Defer response
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Import audit logger
            from utils.audit_logger import audit_logger
            
            # Remove from blacklist
            success, message = await audit_logger.remove_from_blacklist(
                пользователь.id,
                interaction.user
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Удалён из чёрного списка",
                    description=message,
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Ошибка удаления",
                    description=message,
                    color=discord.Color.red()
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"Error in blacklist_remove_command: {e}")
            import traceback
            traceback.print_exc()
            
            embed = discord.Embed(
                title="❌ Ошибка команды",
                description="Произошла ошибка при выполнении команды удаления из чёрного списка.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(PersonnelCommands(bot))