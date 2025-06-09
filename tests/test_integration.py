import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import discord


class TestBotIntegration:
    """Интеграционные тесты для основного функционала бота"""

    @pytest.mark.asyncio
    async def test_bot_startup_sequence(self):
        """Тест последовательности запуска бота"""
        with patch('discord.ext.commands.Bot') as MockBot:
            mock_bot = MockBot.return_value
            mock_bot.load_extension = AsyncMock()
            
            # Имитируем загрузку расширений
            extensions = ['cogs.channel_manager']
            
            for extension in extensions:
                await mock_bot.load_extension(extension)
            
            # Проверяем, что все расширения загружены
            assert mock_bot.load_extension.call_count == len(extensions)

    @pytest.mark.asyncio
    async def test_discord_permissions_check(self):
        """Тест проверки прав Discord"""
        # Создаем мок пользователя с правами администратора
        admin_user = MagicMock()
        admin_user.guild_permissions.administrator = True
        
        # Создаем мок пользователя без прав
        regular_user = MagicMock()
        regular_user.guild_permissions.administrator = False
        
        # Имитируем проверку прав модератора
        with patch('forms.role_assignment_form.load_config') as mock_config:
            mock_config.return_value = {
                'moderators': {
                    'users': [123456789],
                    'roles': [987654321]
                }
            }
            
            from forms.role_assignment_form import RoleApplicationApprovalView
            
            # Тест для администратора
            view = RoleApplicationApprovalView({})
            interaction_admin = MagicMock()
            interaction_admin.user = admin_user
            
            result = await view._check_moderator_permissions(interaction_admin)
            assert result is True
            
            # Тест для обычного пользователя
            interaction_regular = MagicMock()
            interaction_regular.user = regular_user
            interaction_regular.user.id = 999999999  # Не в списке модераторов
            interaction_regular.user.roles = []
            
            result = await view._check_moderator_permissions(interaction_regular)
            assert result is False

    @pytest.mark.asyncio
    async def test_error_handling_network_issues(self):
        """Тест обработки сетевых ошибок"""
        with patch('forms.role_assignment_form.load_config') as mock_config:
            mock_config.side_effect = Exception("Network error")
            
            # Создаем мок interaction
            interaction = AsyncMock()
            
            from forms.role_assignment_form import MilitaryApplicationModal
            modal = MilitaryApplicationModal()
            modal.static_input.value = "123-456"
            modal.name_input.value = "Иван Иванов"
            modal.rank_input.value = "Рядовой"
            modal.recruitment_type_input.value = "Экскурсия"
            
            # Ожидаем, что ошибка будет обработана корректно
            await modal.on_submit(interaction)
            
            # Проверяем, что пользователю отправлено сообщение об ошибке
            interaction.response.send_message.assert_called_once()


class TestDataValidation:
    """Тесты валидации данных"""

    def test_application_data_structure(self):
        """Тест структуры данных заявки"""
        # Тестовые данные военной заявки
        military_data = {
            "type": "military",
            "name": "Иван Иванов",
            "static": "123-456",
            "rank": "Рядовой",
            "recruitment_type": "экскурсия",
            "user_id": 123456789,
            "user_mention": "<@123456789>"
        }
        
        # Проверяем обязательные поля
        required_fields = ["type", "name", "static", "rank", "recruitment_type", "user_id", "user_mention"]
        for field in required_fields:
            assert field in military_data, f"Field {field} is required"
        
        # Тестовые данные гражданской заявки
        civilian_data = {
            "type": "civilian",
            "name": "Петр Петров",
            "static": "789-012",
            "faction": "МВД",
            "purpose": "Доступ к поставкам",
            "proof": "https://example.com/proof",
            "user_id": 987654321,
            "user_mention": "<@987654321>"
        }
        
        # Проверяем обязательные поля для гражданской заявки
        civilian_required = ["type", "name", "static", "faction", "purpose", "proof", "user_id", "user_mention"]
        for field in civilian_required:
            assert field in civilian_data, f"Field {field} is required for civilian application"

    def test_recruitment_type_validation(self):
        """Тест валидации типов набора"""
        valid_types = ["экскурсия", "призыв"]
        invalid_types = ["неверный", "тест", "", "ЭКСКУРСИЯ"]  # регистр имеет значение
        
        for valid_type in valid_types:
            assert valid_type in ["экскурсия", "призыв"], f"{valid_type} should be valid"
        
        for invalid_type in invalid_types:
            assert invalid_type not in ["экскурсия", "призыв"], f"{invalid_type} should be invalid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
