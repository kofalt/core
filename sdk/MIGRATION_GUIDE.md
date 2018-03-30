# SDK Migration Guide

## Migrating from SDK 0.x.y

In general, the core APIs are largely unchanged. Objects returned by APIs are now models rather than pure dictionaries or structs, 
but are still addressable in the same way. For API methods that take an object, you can pass either a dictionary (as in SDK1) or one
of the new models. See individual API doc strings for details.

* The **searchRaw** method is no longer provided.

### Python Notes

Downloading a file directly to memory is now supported, for example:
```python
data = fw.download_file_from_project_as_data(project_id, filename)
```

### Matlab Notes

#### Gears

The following gear fields have been renamed as part of the model changes:

* **git0x2Dcommit** -> **gitCommit**
* **rootfs0x2Dhash** -> **rootfsHash**
* **rootfs0x2Durl** -> **rootfsUrl**
 
