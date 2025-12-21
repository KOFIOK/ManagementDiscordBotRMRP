"""
Static validation utilities for Discord bot
Provides standardized static number validation and formatting
"""
import re
from typing import Tuple, Optional


class StaticValidator:
    """
    Unified static validation and formatting for the bot
    Supports 1-6 digits with proper formatting
    """

    @staticmethod
    def validate_and_format(static_input: str) -> Tuple[bool, str]:
        """
        Validate and format static number

        Args:
            static_input: Raw static input from user

        Returns:
            Tuple[bool, str]: (is_valid, formatted_static)
            - is_valid: True if static is valid (1-6 digits)
            - formatted_static: Formatted static or empty string if invalid
        """
        if not static_input or not isinstance(static_input, str):
            return False, ""

        # Remove all non-digits
        digits_only = re.sub(r'\D', '', static_input.strip())

        # Check length (1-6 digits)
        if not 1 <= len(digits_only) <= 6:
            return False, ""

        # Format based on length
        formatted = StaticValidator._format_digits(digits_only)
        return True, formatted

    @staticmethod
    def _format_digits(digits: str) -> str:
        """
        Format digits into standard static format

        Args:
            digits: String of digits (1-6 characters)

        Returns:
            str: Formatted static (no dash for 1-3 digits, X-XXX, XX-XXX, XXX-XXX for 4+ digits)
        """
        length = len(digits)

        if length == 1:
            return digits  # 1
        elif length == 2:
            return digits  # 11
        elif length == 3:
            return digits  # 111
        elif length == 4:
            return f"{digits[0]}-{digits[1:]}"  # X-XXX (1-111)
        elif length == 5:
            return f"{digits[:2]}-{digits[2:]}"  # XX-XXX (11-111)
        elif length == 6:
            return f"{digits[:3]}-{digits[3:]}"  # XXX-XXX (111-111)
        else:
            # This should not happen due to validation, but fallback
            return digits

    @staticmethod
    def is_valid_format(static: str) -> bool:
        """
        Check if static is already in valid format

        Args:
            static: Static string to check

        Returns:
            bool: True if static matches expected format
        """
        if not static:
            return False

        # Check format pattern: X-X, X-XX, XX-XX, XX-XXX, XXX-XXX
        pattern = r'^\d{1,3}-\d{1,3}$'
        return bool(re.match(pattern, static))

    @staticmethod
    def extract_digits(static: str) -> str:
        """
        Extract only digits from static string

        Args:
            static: Static string (may contain separators)

        Returns:
            str: Only digits
        """
        if not static:
            return ""
        return re.sub(r'\D', '', static)

    @staticmethod
    def get_validation_error_message() -> str:
        """
        Get standardized validation error message

        Returns:
            str: Error message for invalid static
        """
        from utils.message_manager import get_message
        return get_message(0, 'templates.errors.static_format')