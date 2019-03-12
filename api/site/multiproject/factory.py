""""Provides factory function for creating provider pickers"""
def create_provider_picker(enable_multiproject):
    """Create a ProviderPicker strategy.

    Args:
        enable_multiproject (bool): Whether or not multiproject is enabled for the site

    Returns:
        ProviderPicker: The appropriate provider picker
    """
    # Lazy load to prevent circular dependencies between jobs.queue and this
    if enable_multiproject:
        from .multiproject_picker import MultiprojectProviderPicker
        return MultiprojectProviderPicker()

    from .fixed_picker import FixedProviderPicker
    return FixedProviderPicker()
