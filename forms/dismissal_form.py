"""
Dismissal System - Legacy Interface

This file has been refactored for better maintainability. 
The functionality has been split into multiple modules in the dismissal/ directory.

This file now serves as a compatibility layer to maintain existing imports.
"""

import warnings
warnings.warn(
    "forms.dismissal_form is now modular. Consider importing from forms.dismissal package directly.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export all components from the new modular structure
from .dismissal import *
