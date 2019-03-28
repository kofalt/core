"""Provides functionality for writing a download ticket"""
import tarfile

from fs.time import datetime_to_epoch

class TarDownloadWriter(object):
    """Class that writes files to the given tar file"""

    # The size of file chunks to read/write
    CHUNKSIZE = 2 ** 20

    def __init__(self, log, fileobj):
        """Create a new TarDownloadWriter.

        Args:
            log (Logger): The logging instance
            fileobj (file): The file-like object to write to.
        """
        self.log = log
        self.fileobj = fileobj
        self._tarfile = tarfile.open(mode='w|', fileobj=self.fileobj)

    def write(self, file_source):
        """Given a DownloadFileSource, write each entry to the tarfile.

        Args:
            file_source (DownloadFileSource): The file source
        """
        for target in file_source:
            try:
                fileobj = file_source.open(target)
                try:
                    tarinfo = tarfile.TarInfo()
                    tarinfo.name = target.dst_path.lstrip('/')
                    tarinfo.size = target.size
                    tarinfo.mtime = datetime_to_epoch(target.modified)

                    self._addfile(tarinfo, fileobj)
                finally:
                    fileobj.close()
            except OSError:
                msg = ("Error happened during sending file content in archive stream, file path: %s, "
                    "container: %s/%s, archive path: %s" % (target.src_path, target.container_type,
                    target.container_id, target.dst_path))
                self.log.critical(msg)
                self.log.exception("Error opening file for streaming")

                # Write a placeholder instead
                tarinfo = tarfile.TarInfo()
                tarinfo.name = target.dst_path + '.MISSING'
                self._tarfile.addfile(tarinfo)

    def _addfile(self, tarinfo, fileobj):
        """Write the given archive member to the tar stream.

        Args:
            tarinfo (TarInfo): The TarInfo details
            fileobj (file): The file-like object to write
        """
        try:
            # Write header
            self.fileobj.write(tarinfo.tobuf())

            # Write the contents directly to the underlying fileobj,
            # In order to use a larger CHUNKSIZE for transfer
            chunk = ''
            last_chunk_len = 0
            while True:
                chunk = fileobj.read(self.CHUNKSIZE)
                if not chunk:
                    break
                self.fileobj.write(chunk)
                last_chunk_len = len(chunk)

            remainder = last_chunk_len % tarfile.BLOCKSIZE
            if remainder > 0:
                self.fileobj.write(b'\0' * (tarfile.BLOCKSIZE - remainder))
        except:
            self.log.exception('Error writing contents to archive stream for file: %s', tarinfo.name)
            raise
        finally:
            fileobj.close()

    def close(self):
        """Closes the tarfile, and the underlying file object."""
        if self._tarfile:
            self._tarfile.close()
            self._tarfile = None

        if self.fileobj:
            self.fileobj.close()
            self.fileobj = None
