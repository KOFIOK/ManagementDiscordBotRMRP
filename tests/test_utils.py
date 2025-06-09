import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from utils.config_manager import load_config, save_config
import json
import os
import tempfile


class TestConfigManager:
    """Тесты для менеджера конфигурации"""

    def setup_method(self):
        """Настройка временного файла конфигурации для тестов"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_config_path = os.path.join(self.temp_dir, "test_config.json")
        
        # Пропатчиваем путь к конфигурации для тестов
        self.config_patcher = patch('utils.config_manager.CONFIG_FILE', self.test_config_path)
        self.config_patcher.start()

    def teardown_method(self):
        """Очистка после тестов"""
        self.config_patcher.stop()
        if os.path.exists(self.test_config_path):
            os.remove(self.test_config_path)
        os.rmdir(self.temp_dir)

    def test_load_config_empty_file(self):
        """Тест загрузки конфигурации из пустого файла"""
        config = load_config()
        assert config == {}

    def test_save_and_load_config(self):
        """Тест сохранения и загрузки конфигурации"""
        test_config = {
            "role_assignment_channel": 123456789,
            "military_roles": [111, 222, 333],
            "moderators": {
                "users": [987654321],
                "roles": [555, 666]
            }
        }
        
        save_config(test_config)
        loaded_config = load_config()
        
        assert loaded_config == test_config

    def test_config_file_corruption_handling(self):
        """Тест обработки поврежденного файла конфигурации"""
        # Создаем поврежденный JSON файл
        with open(self.test_config_path, 'w', encoding='utf-8') as f:
            f.write('{"invalid": json}')
        
        config = load_config()
        assert config == {}  # Должен вернуть пустой словарь при ошибке


class TestUtilityFunctions:
    """Тесты утилитарных функций"""

    def test_static_validation_regex(self):
        """Тест регулярного выражения для валидации статика"""
        import re
        pattern = r'^\d{2,3}-?\d{3}$'
        
        # Корректные форматы
        valid_cases = ["123-456", "12-345", "1234567", "12345"]
        for case in valid_cases:
            assert re.match(pattern, case), f"Pattern should match {case}"
        
        # Некорректные форматы
        invalid_cases = ["1234", "12345678", "abc-def", "123-", "-456"]
        for case in invalid_cases:
            assert not re.match(pattern, case), f"Pattern should not match {case}"

    def test_url_validation_regex(self):
        """Тест регулярного выражения для валидации URL"""
        import re
        pattern = r'https?://[^\s/$.?#].[^\s]*'
        
        # Корректные URL
        valid_urls = [
            "https://example.com",
            "http://test.ru",
            "https://discord.com/channels/123/456"
        ]
        for url in valid_urls:
            assert re.match(pattern, url), f"Pattern should match {url}"
        
        # Некорректные URL
        invalid_urls = ["not-a-url", "ftp://example.com", "https://"]
        for url in invalid_urls:
            assert not re.match(pattern, url), f"Pattern should not match {url}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
