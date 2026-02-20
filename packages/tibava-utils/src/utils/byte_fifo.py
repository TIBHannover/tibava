class ByteFIFO:
    def __init__(self):
        self.buffer = bytearray()

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    def read(self, chunk_size: int = None) -> bytes:
        if not chunk_size:
            data = self.buffer[:]
            del self.buffer[:]
            return bytes(data)
        data = self.buffer[:chunk_size]
        del self.buffer[:chunk_size]
        return bytes(data)

    def __len__(self):
        return len(self.buffer)
