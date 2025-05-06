import tarfile
import zipfile


class Archive:
    def __init__(self):
        pass

    def __enter__(self):

        pass

    def __exit__(self):
        pass


class TarArchive(Archive):
    def __init__(self, path):
        self.path = path
        self.f = None

    def __enter__(self):
        self.f = tarfile.open(self.path, mode="r")
        return self

    def members(self):
        if self.f is None:
            return []
        else:
            for info in self.f.getmembers():
                yield info.name

    def read(self, name):
        if self.f is None:
            return None

        try:
            return self.f.extractfile(name).read()
        except KeyError:
            return None

    def __exit__(self, type, value, traceback):
        self.f.close()
        self.f = None


class ZipArchive(Archive):
    def __init__(self, path):
        self.path = path
        self.f = None

    def __enter__(self):
        self.f = zipfile.ZipFile(self.path, "r")
        return self

    def members(self):
        if self.f is None:
            return []
        else:
            for name in self.f.namelist():
                yield name

    def read(self, name):
        if self.f is None:
            return None

        try:
            return self.f.open(name).read()
        except KeyError:
            return None

    def __exit__(self, type, value, traceback):
        self.f.close()
        self.f = None
