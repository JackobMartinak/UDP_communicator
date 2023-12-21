import copy
from dataclasses import dataclass
from enum import Enum
from random import random
from typing import ClassVar
from zlib import crc32

from BinaryRW import BinaryReader, BinaryWriter
from config import Config


class SegmentType(Enum):
    Init = 1
    Fin = 2
    OK = 3
    Text = 4
    File = 5
    Accept = 6
    Data = 7
    Done = 8
    Next = 9
    Ping = 10


@dataclass
class Segment:
    type: ClassVar[SegmentType]
    stream: int

    def get_printable(self):
        subject = copy.copy(self)
        for key in dir(subject):
            value = subject.__getattribute__(key)
            if isinstance(value, bytes) and value.__len__() > 50:
                value = value[0:50]
                if str(value).__len__() > 50:
                    value = value[0:10]
                pass
                subject.__setattr__(key, value + b"...")
            pass
        pass

        return str(subject)

    pass


@dataclass
class Message(Segment):
    id: int


@dataclass
class InitMessage(Message):
    type: ClassVar[SegmentType] = SegmentType.Init
    pass


@dataclass
class FinMessage(Message):
    type: ClassVar[SegmentType] = SegmentType.Fin
    pass


@dataclass
class OkMessage(Message):
    type: ClassVar[SegmentType] = SegmentType.OK
    pass


@dataclass
class TextMessage(Message):
    type: ClassVar[SegmentType] = SegmentType.Text
    text: str
    pass


@dataclass
class FileMessage(Message):
    type: ClassVar[SegmentType] = SegmentType.File
    path: str
    size: int
    pass


@dataclass
class AcceptMessage(Message):
    type: ClassVar[SegmentType] = SegmentType.Accept
    pass


@dataclass
class DoneMessage(Message):
    type: ClassVar[SegmentType] = SegmentType.Done
    pass


@dataclass
class NextMessage(Message):
    type: ClassVar[SegmentType] = SegmentType.Next
    fragments: list[int]
    pass


@dataclass
class PingMessage(Message):
    type: ClassVar[SegmentType] = SegmentType.Ping
    pass


@dataclass
class DataSegment(Segment):
    type: ClassVar[SegmentType] = SegmentType.Data
    fragment_id: int
    data: bytes | bytearray


def parse_segment(input: bytes) -> Segment | None:
    reader = BinaryReader(input)
    typeNumber = reader.readInt(1)

    if not (typeNumber in SegmentType._value2member_map_):
        print(f"Received segment with invalid type = {typeNumber}")
        return None
    pass
    type = SegmentType(typeNumber)

    length = reader.readInt(2)
    stream = reader.readInt(4)

    checksum_pointer = reader.index
    expected_checksum = reader.readInt(4)

    checksum_subject = bytearray(input)
    for i in range(4):
        checksum_subject[checksum_pointer + i] = 0
    pass
    actual_checksum = crc32(checksum_subject)

    if actual_checksum != expected_checksum:
        print("[CRC] Received corrupted segment")
        return None
    pass

    if type == SegmentType.Data:
        fragment_id = reader.readInt(2)
        data = reader.readBytes(length)
        return DataSegment(stream, fragment_id, data)
    else:
        id = reader.readInt(2)
        match type:
            case SegmentType.Init:
                return InitMessage(stream, id)
            case SegmentType.Fin:
                return FinMessage(stream, id)
            case SegmentType.OK:
                return OkMessage(stream, id)
            case SegmentType.Text:
                text = reader.readBytes(length).decode()
                return TextMessage(stream, id, text)
            case SegmentType.File:
                size = reader.readInt(2)
                path = reader.readBytes(length - 2).decode()
                return FileMessage(stream, id, path, size)
            case SegmentType.Accept:
                return AcceptMessage(stream, id)
            case SegmentType.Done:
                return DoneMessage(stream, id)
            case SegmentType.Ping:
                return PingMessage(stream, id)
            case SegmentType.Next:
                fragments: list[int] = []
                for _ in range(length // 2):
                    fragments.append(reader.readInt(2))
                return NextMessage(stream, id, fragments)
        pass
    pass


def emit_segment(segment: Segment):
    output = BinaryWriter()
    type = segment.type

    output.writeInt(1, type.value)
    lengthPlaceholder = output.writePlaceholder(2)
    output.writeInt(4, segment.stream)
    checksumPlaceholder = output.writePlaceholder(4)

    if isinstance(segment, DataSegment):
        output.writeInt(2, segment.fragment_id)
        output.writeBytes(segment.data)
        lengthPlaceholder(segment.data.__len__())
    elif isinstance(segment, Message):
        output.writeInt(2, segment.id)
        if isinstance(segment, TextMessage):
            text = segment.text.encode()
            output.writeBytes(text)
            lengthPlaceholder(text.__len__())
        elif isinstance(segment, FileMessage):
            output.writeInt(2, segment.size)
            path = segment.path.encode()
            output.writeBytes(path)
            lengthPlaceholder(path.__len__() + 2)
        elif isinstance(segment, NextMessage):
            for fragment in segment.fragments:
                output.writeInt(2, fragment)
            pass
            lengthPlaceholder(2 * segment.fragments.__len__())
        pass
    pass

    checksum = crc32(output.build())
    if (segment.type == SegmentType.Data or segment.type == SegmentType.Text) and Config.PACKET_LOSS > 0:
        checksum += 1
        Config.PACKET_LOSS -= 1
    pass
    checksumPlaceholder(checksum)

    return output.build()
