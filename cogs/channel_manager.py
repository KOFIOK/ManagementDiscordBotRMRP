import discord
from discord import app_commands
from discord.ext import commands

from forms.settings_form import send_settings_message
from utils.config_manager import load_config, save_config

class ChannelManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings", description="⚙️ Настройка каналов Discord бота")
    @app_commands.checks.has_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        """Unified command for bot configuration with interactive interface"""
        await send_settings_message(interaction)

    @app_commands.command(name="addmoder", description="👮 Добавить модератора (роль или пользователя)")
    @app_commands.describe(target="Роль или пользователь для назначения модератором")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_moderator(self, interaction: discord.Interaction, target: discord.Member | discord.Role):
        """Add a user or role as moderator"""
        try:
            config = load_config()
            moderators = config.get('moderators', {'users': [], 'roles': []})
            
            if isinstance(target, discord.Member):
                if target.id not in moderators['users']:
                    moderators['users'].append(target.id)
                    config['moderators'] = moderators
                    save_config(config)
                    
                    await interaction.response.send_message(
                        f"✅ Пользователь {target.mention} добавлен в список модераторов.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Пользователь {target.mention} уже является модератором.",
                        ephemeral=True
                    )
            
            elif isinstance(target, discord.Role):
                if target.id not in moderators['roles']:
                    moderators['roles'].append(target.id)
                    config['moderators'] = moderators
                    save_config(config)
                    
                    await interaction.response.send_message(
                        f"✅ Роль {target.mention} добавлена в список модераторских ролей.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Роль {target.mention} уже является модераторской.",
                        ephemeral=True
                    )
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при добавлении модератора: {e}",
                ephemeral=True
            )
            print(f"Add moderator error: {e}")

    @app_commands.command(name="removemoder", description="🚫 Убрать модератора (роль или пользователя)")
    @app_commands.describe(target="Роль или пользователь для удаления из модераторов")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_moderator(self, interaction: discord.Interaction, target: discord.Member | discord.Role):
        """Remove a user or role from moderators"""
        try:
            config = load_config()
            moderators = config.get('moderators', {'users': [], 'roles': []})
            
            if isinstance(target, discord.Member):
                if target.id in moderators['users']:
                    moderators['users'].remove(target.id)
                    config['moderators'] = moderators
                    save_config(config)
                    
                    await interaction.response.send_message(
                        f"✅ Пользователь {target.mention} удален из списка модераторов.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Пользователь {target.mention} не является модератором.",
                        ephemeral=True
                    )
            
            elif isinstance(target, discord.Role):
                if target.id in moderators['roles']:
                    moderators['roles'].remove(target.id)
                    config['moderators'] = moderators
                    save_config(config)
                    
                    await interaction.response.send_message(
                        f"✅ Роль {target.mention} удалена из списка модераторских ролей.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"⚠️ Роль {target.mention} не является модераторской.",
                        ephemeral=True
                    )
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при удалении модератора: {e}",
                ephemeral=True
            )
            print(f"Remove moderator error: {e}")

    @app_commands.command(name="listmoders", description="📋 Показать список модераторов")
    @app_commands.checks.has_permissions(administrator=True)
    async def list_moderators(self, interaction: discord.Interaction):
        """List all moderators and moderator roles"""
        try:
            config = load_config()
            moderators = config.get('moderators', {'users': [], 'roles': []})
            
            embed = discord.Embed(
                title="👮 Список модераторов",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Moderator users
            user_list = []
            for user_id in moderators.get('users', []):
                user = interaction.guild.get_member(user_id)
                if user:
                    user_list.append(f"• {user.mention} ({user.display_name})")
                else:
                    user_list.append(f"• <@{user_id}> (пользователь не найден)")
            
            if user_list:
                embed.add_field(
                    name="👤 Пользователи-модераторы",
                    value="\n".join(user_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="👤 Пользователи-модераторы",
                    value="Нет назначенных пользователей",
                    inline=False
                )
              # Moderator roles
            role_list = []
            for role_id in moderators.get('roles', []):
                role = interaction.guild.get_role(role_id)
                if role:
                    role_list.append(f"• {role.mention}")
                else:
                    role_list.append(f"• <@&{role_id}> (роль не найдена)")
            
            if role_list:
                embed.add_field(
                    name="🛡️ Модераторские роли",
                    value="\n".join(role_list),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🛡️ Модераторские роли",
                    value="Нет назначенных ролей",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Ошибка при получении списка модераторов: {e}",
                ephemeral=True
            )
            print(f"List moderators error: {e}")    # Error handling for commands
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle app command errors"""
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ У вас нет прав для выполнения этой команды. Требуются права администратора.", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Произошла ошибка: {error}", 
                ephemeral=True
            )
            print(f"App command error: {error}")

# Setup function for adding the cog to the bot
async def setup(bot):
    await bot.add_cog(ChannelManagementCog(bot))
