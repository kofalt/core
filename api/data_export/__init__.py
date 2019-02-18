"""Provides data export functionality.

Download handlers can now be written independent from the logic that locates containers,
retrieves file contents, and writes the resulting tarball.

Submodules:
- models: Provides the DownloadTicket and DownloadTarget models
- mappers: Provides mapping functionality between models and the database
- handlers: Provides Application logic / endpoint handling for downloads
- strategy: Provides strategies for generating downloads
"""
