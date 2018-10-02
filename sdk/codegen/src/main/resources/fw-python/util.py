"""Provides utility functions"""

def seconds_to_years(seconds):
    """Convert seconds to years"""
    return seconds / 31557600.0

def years_to_seconds(years):
    """Convert years to seconds"""
    return int(years * 31557600.0)

def seconds_to_months(seconds):
    """Convert seconds to months"""
    return seconds / 2592000.0

def months_to_seconds(months):
    """Convert months to seconds"""
    return int(months * 2592000.0)

def seconds_to_weeks(seconds):
    """Convert seconds to weeks"""
    return seconds / 604800.0

def weeks_to_seconds(weeks):
    """Convert weeks to seconds"""
    return int(weeks * 604800.0)

def seconds_to_days(seconds):
    """Convert seconds to days"""
    return seconds / 86400.0

def days_to_seconds(days):
    """Convert days to seconds"""
    return int(days * 86400.0)
