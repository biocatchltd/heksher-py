class NoMatchError(Exception):
    """
    Raised either internally when matching in a branch fails, or externally when a setting has no default and no
    matching rules
    """
