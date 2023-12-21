class BinaryReader:
    def readInt(self, size: int):
        result = 0
        for _ in range(size):
            value = self.data[self.index]
            self.index += 1
            result <<= 8
            result |= value
            pass

        return result

    def readBytes(self, size: int):
        result = self.data[self.index : (self.index + size)]
        self.index += size
        return result

    def __init__(self, data: bytes | bytearray):
        self.data = data
        self.index = 0
        pass


def write_value(chunk: bytearray, value: int):
    for i in range(chunk.__len__()):
        chunk[chunk.__len__() - 1 - i] = value & 0xFF
        value = value >> 8
    pass


class BinaryWriter:
    def writeInt(self, size: int, value: int):
        chunk = bytearray(size)
        write_value(chunk, value)
        self.chunks.append(chunk)
        pass

    def writePlaceholder(self, size: int):
        placeholder = bytearray(size)
        self.chunks.append(placeholder)

        def write(value: int):
            write_value(placeholder, value)

        return write

    def writeBytes(self, value: bytes | bytearray):
        self.chunks.append(value)
        pass

    def build(self):
        return bytearray().join(self.chunks)

    def __init__(self) -> None:
        self.chunks: list[bytes | bytearray] = []
        pass
