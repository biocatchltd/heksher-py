class NoMatchError(Exception):
    """
    Raised either internally when resolving a ruleset fails, or externally when a setting has no default and no
    matching rules
    """
