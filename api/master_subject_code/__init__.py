"""Provides master subject code functionality.

The basic idea is to generate a unique identifier for the given patient information.
Future requests with the same identifying information will receive the same code.

Main workflow:
- Client sends patient ID (e.g., MRN), first name, last name, DOB
- Client indicates whether to use patient ID for identification or first name, last name, DOB
- Query the database to find MSC code with the given identifying information, if not exists
generate a new code and store it and the identifying information in the database

Submodules:
- models: Provides the MasterSubjectCode model
- mappers: Provides mapping functionality between models and the database
- handlers: Provides Application logic / endpoint handling for master subject codes
"""
