# This file is deprecated and will be removed in future versions.
# Please use the new modular structure in forms.settings package.

import warnings
warnings.warn(
    "forms.settings_form is deprecated. Use forms.settings package instead.",
    DeprecationWarning,
    stacklevel=2
)

# For backward compatibility, we re-export all components from the new modular structure
from forms.settings import *
