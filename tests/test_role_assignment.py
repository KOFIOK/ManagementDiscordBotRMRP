import pytest
import asyncio
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from forms.role_assignment_form import MilitaryApplicationModal, CivilianApplicationModal
import re


class TestMilitaryApplicationModal:
    """Тесты для формы военных заявок"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.modal = MilitaryApplicationModal()

    def test_modal_initialization(self):
        """Тест инициализации модального окна"""
        assert self.modal.title == "Заявка на получение роли военнослужащего"
        assert len(self.modal.children) == 4
        assert self.modal.rank_input.default == "Рядовой"

    def test_validate_static_valid_formats(self):
        """Тест валидации статика - корректные форматы"""
        valid_statics = ["123-456", "12345", "1234567", "12-345", "123-45"]
        
        for static in valid_statics:
            assert self.modal._validate_static(static), f"Static {static} should be valid"

    def test_validate_static_invalid_formats(self):
        """Тест валидации статика - некорректные форматы"""
        invalid_statics = ["1234", "12345678", "abc-def", "123-", "-456", "123--456"]
        
        for static in invalid_statics:
            assert not self.modal._validate_static(static), f"Static {static} should be invalid"

    @pytest.mark.asyncio
    async def test_on_submit_invalid_static(self):
        """Тест отправки формы с некорректным статиком"""
        # Мокаем interaction
        interaction = AsyncMock()
        
        # Устанавливаем некорректные данные
        self.modal.static_input.value = "invalid"
        self.modal.name_input.value = "Иван Иванов"
        self.modal.rank_input.value = "Рядовой"
        self.modal.recruitment_type_input.value = "Экскурсия"
        
        await self.modal.on_submit(interaction)
        
        # Проверяем, что был отправлен ответ об ошибке
        interaction.response.send_message.assert_called_once()
        args = interaction.response.send_message.call_args[1]
        assert "Неверный формат статика" in args['content']
        assert args['ephemeral'] is True

    @pytest.mark.asyncio
    async def test_on_submit_invalid_recruitment_type(self):
        """Тест отправки формы с некорректным типом набора"""
        interaction = AsyncMock()
        
        self.modal.static_input.value = "123-456"
        self.modal.name_input.value = "Иван Иванов"
        self.modal.rank_input.value = "Рядовой"
        self.modal.recruitment_type_input.value = "Неверный тип"
        
        await self.modal.on_submit(interaction)
        
        interaction.response.send_message.assert_called_once()
        args = interaction.response.send_message.call_args[1]
        assert "Порядок набора должен быть" in args['content']


class TestCivilianApplicationModal:
    """Тесты для формы гражданских заявок"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.modal = CivilianApplicationModal()

    def test_modal_initialization(self):
        """Тест инициализации модального окна"""
        assert self.modal.title == "Заявка на получение роли гражданского"
        assert len(self.modal.children) == 5

    def test_validate_url_valid_formats(self):
        """Тест валидации URL - корректные форматы"""
        valid_urls = [
            "https://example.com",
            "http://test.ru",
            "https://discord.com/channels/123/456",
            "https://docs.google.com/document/d/123"
        ]
        
        for url in valid_urls:
            assert self.modal._validate_url(url), f"URL {url} should be valid"

    def test_validate_url_invalid_formats(self):
        """Тест валидации URL - некорректные форматы"""
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "example.com",
            "https://",
            ""
        ]
        
        for url in invalid_urls:
            assert not self.modal._validate_url(url), f"URL {url} should be invalid"

    @pytest.mark.asyncio
    async def test_on_submit_invalid_url(self):
        """Тест отправки формы с некорректной ссылкой"""
        interaction = AsyncMock()
        
        self.modal.static_input.value = "123-456"
        self.modal.name_input.value = "Иван Иванов"
        self.modal.faction_input.value = "МВД"
        self.modal.purpose_input.value = "Тест"
        self.modal.proof_input.value = "invalid-url"
        
        await self.modal.on_submit(interaction)
        
        interaction.response.send_message.assert_called_once()
        args = interaction.response.send_message.call_args[1]
        assert "корректную ссылку" in args['content']


class TestIntegration:
    """Интеграционные тесты"""

    @pytest.mark.asyncio
    async def test_full_military_application_flow(self):
        """Тест полного потока военной заявки"""
        with patch('forms.role_assignment_form.load_config') as mock_config, \
             patch('forms.role_assignment_form.RoleApplicationApprovalView'):
            
            # Настройка мока конфигурации
            mock_config.return_value = {
                'role_assignment_channel': 123456789,
                'military_role_assignment_ping_roles': []
            }
            
            # Создание мока interaction
            interaction = AsyncMock()
            guild_mock = MagicMock()
            channel_mock = AsyncMock()
            guild_mock.get_channel.return_value = channel_mock
            interaction.guild = guild_mock
            interaction.user.id = 987654321
            interaction.user.mention = "<@987654321>"
            
            # Настройка модального окна
            modal = MilitaryApplicationModal()
            modal.static_input.value = "123-456"
            modal.name_input.value = "Иван Иванов"
            modal.rank_input.value = "Рядовой"
            modal.recruitment_type_input.value = "Экскурсия"
            
            await modal.on_submit(interaction)
            
            # Проверяем, что заявка была отправлена
            interaction.response.send_message.assert_called_once()
            args = interaction.response.send_message.call_args[1]
            assert "отправлена на рассмотрение" in args['content']
            
            # Проверяем, что сообщение было отправлено в канал
            channel_mock.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_manager_integration(self):
        """Тест интеграции с менеджером конфигурации"""
        with patch('forms.role_assignment_form.load_config') as mock_load:
            mock_load.return_value = {
                'role_assignment_channel': None
            }
            
            interaction = AsyncMock()
            modal = MilitaryApplicationModal()
            modal.static_input.value = "123-456"
            modal.name_input.value = "Иван Иванов"
            modal.rank_input.value = "Рядовой"
            modal.recruitment_type_input.value = "Экскурсия"
            
            await modal.on_submit(interaction)
            
            # Проверяем обработку отсутствующего канала
            interaction.response.send_message.assert_called_once()
            args = interaction.response.send_message.call_args[1]
            assert "не настроен" in args['content']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
