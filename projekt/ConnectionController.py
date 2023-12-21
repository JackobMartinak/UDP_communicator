from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from enum import Enum
from io import BufferedIOBase, FileIO
from os import fstat
from queue import Empty, Queue
from random import random
from socket import socket
from sys import exit
from threading import Semaphore, Thread
from typing import Callable

from config import Config
from Segment import AcceptMessage, DataSegment, DoneMessage, FileMessage, FinMessage, InitMessage, Message, NextMessage, OkMessage, PingMessage, Segment, SegmentType, TextMessage, emit_segment


class KeepAliveState(Enum):
    Normal = 0
    Notified = 1
    Terminating = 2


@dataclass
class PendingFragment:
    age = 0
    data: bytes


class Stream:
    def receive(self):
        segment = self.queue.get(timeout=Config.TIMEOUT)
        if segment == None:
            exit()
        return segment

    def receive_message(self):
        while True:
            segment = self.receive()
            if isinstance(segment, Message):
                if segment.id != self.next_message_id:
                    print(f"[ORD] Received fragment out of order {segment.get_printable()}")
                    continue
                pass

                self.next_message_id = segment.id + 1
                return segment
            else:
                assert isinstance(segment, DataSegment)
                if self.file == None:
                    continue
                pass

                self.received_segments.append(segment.fragment_id)

                if segment.fragment_id < self.next_fragment:
                    print(f"[ORD] Received fragment out of order {segment.get_printable()}")
                    continue
                pass

                if segment.fragment_id == self.next_fragment:
                    self.next_fragment += 1
                    self.file.write(segment.data)
                else:
                    heapq.heappush(self.fragment_queue, (segment.fragment_id, segment.data))
                pass

                while self.fragment_queue.__len__() > 0 and self.fragment_queue[0][0] <= self.next_fragment:
                    id, data = heapq.heappop(self.fragment_queue)
                    if id < self.next_fragment:
                        continue
                    self.next_fragment += 1
                    self.file.write(data)
                pass

            pass
        pass

    def send_message(self, segment: Message, expect_type: SegmentType | None = None, repeat=0):
        self.next_message_id = segment.id + 1

        for _ in range(repeat):
            self.owner.send(segment)

        recv: Message | None = None
        for _ in range(Config.REPEAT_LIMIT):
            try:
                self.owner.send(segment)
                recv = self.receive_message()
                break
            except Empty:
                pass
            pass
        else:
            print(f"Reached REPEAT_LIMIT on stream {self.id}")
            self.owner.close()
            exit()
        pass

        if expect_type != None and recv.type != expect_type:
            print("Received unexpected segment, expected type " + expect_type.name)
            self.owner.close()
            exit()
        pass

        return recv

    def send_ok(self):
        self.owner.send(OkMessage(self.id, self.next_message_id))
        try:
            while True:
                recv = self.receive()
                self.owner.send(OkMessage(self.id, self.next_message_id))
            pass
        except Empty:
            return
        pass

    def send_text(self, text: str):
        for i in range(0, text.__len__(), Config.FRAGMENT_SIZE):
            subtext = text[i : i + Config.FRAGMENT_SIZE]
            self.send_message(TextMessage(self.id, self.next_message_id, subtext), expect_type=SegmentType.Next, repeat=Config.FORCE_REPEAT)

        self.send_ok()

    def send_init(self):
        self.send_message(InitMessage(self.id, self.next_message_id), expect_type=SegmentType.OK)

    def send_ping(self):
        self.send_message(PingMessage(self.id, self.next_message_id), expect_type=SegmentType.OK)

    def send_fin(self):
        self.send_message(FinMessage(self.id, self.next_message_id), expect_type=SegmentType.OK)
        time.sleep(0.01)
        self.owner.close()

    def send_file(self, source: str, dest: str):
        try:
            self.file = open(source, "rb")
        except Exception as error:
            print(f"[FILE] Cannot open file: {error}")
            return
        pass

        size = fstat(self.file.fileno()).st_size
        reply = self.send_message(FileMessage(self.id, self.next_message_id, dest, size))

        if not isinstance(reply, AcceptMessage):
            if isinstance(reply, TextMessage):
                print(f"[FILE] Cannot send file {reply.text}")
                self.send_ok()
                return
            else:
                print(f"Received unexpected segment {reply.type.name}")
                self.owner.close()
                exit()
            pass
        pass

        next_fragment_id = 0
        fragment_buffer: dict[int, PendingFragment] = {}
        send_limit = Config.WINDOW_SIZE
        reading_finished = False
        while True:
            if not reading_finished:
                while fragment_buffer.__len__() < Config.WINDOW_SIZE and send_limit > 0:
                    fragment_data = self.file.read(Config.FRAGMENT_SIZE)
                    if fragment_data.__len__() == 0:
                        reading_finished = True
                        break
                    pass

                    fragment_buffer[next_fragment_id] = PendingFragment(fragment_data)
                    for _ in range(Config.FORCE_REPEAT):
                        self.owner.send(DataSegment(self.id, next_fragment_id, fragment_data))
                    send_limit -= 1
                    next_fragment_id += 1
                pass
            pass

            if fragment_buffer.__len__() == 0:
                print(f"[FILE] Upload finished, destination: {dest}, size: {size}, fragment count: {next_fragment_id}")
                self.file.close()
                self.file = None
                self.send_ok()
                return
            pass

            reply = self.send_message(DoneMessage(self.id, self.next_message_id), expect_type=SegmentType.Next)
            send_limit = Config.WINDOW_SIZE
            assert isinstance(reply, NextMessage)
            for confirmed_fragment in reply.fragments:
                if not confirmed_fragment in fragment_buffer:
                    continue
                fragment_buffer.pop(confirmed_fragment)
            pass

            for fragment_id in fragment_buffer:
                fragment = fragment_buffer[fragment_id]
                fragment.age += 1
                if fragment.age > Config.FRAGMENT_MAX_AGE and send_limit > 0:
                    self.owner.send(DataSegment(self.id, fragment_id, fragment.data))
                    fragment.age = 0
                    send_limit -= 1
                pass
            pass
        pass

    def listen(self):
        segment = self.receive_message()

        if isinstance(segment, TextMessage):
            text = ""
            text += segment.text
            while True:
                response = self.send_message(NextMessage(self.id, self.next_message_id, []))
                if isinstance(response, OkMessage):
                    break
                elif isinstance(response, TextMessage):
                    text += response.text
                else:
                    print(f"Received unexpected segment {response.type.name}")  # type: ignore
                    self.owner.close()
                    exit()
                pass
            pass
            print(text)
        elif isinstance(segment, InitMessage):
            self.send_ok()
        elif isinstance(segment, PingMessage):
            self.send_ok()
        elif isinstance(segment, FinMessage):
            print("[SIG] Fin")
            self.send_ok()
            self.owner.close()
        elif isinstance(segment, FileMessage):
            path = segment.path
            size = segment.size

            try:
                self.file = open(path, mode="wb")
            except Exception as error:
                error_text = f"Cannot receive file: {error}"
                print("[FILE]", error_text)
                self.send_message(TextMessage(self.id, self.next_message_id, error_text), expect_type=SegmentType.OK)
                return
            pass

            self.fragment_queue = []
            reply = self.send_message(AcceptMessage(self.id, self.next_message_id))
            while True:
                if isinstance(reply, OkMessage):
                    print(f"[FILE] Download complete, destination: {path}, size: {size}, fragment count: {self.next_fragment}")
                    self.file.close()
                    self.file = None
                    return
                elif isinstance(reply, DoneMessage):
                    received_segments = self.received_segments
                    self.received_segments = []
                    reply = self.send_message(NextMessage(self.id, self.next_message_id, received_segments))
                else:
                    print(f"Received unexpected segment {reply.type.name}")
                    self.owner.close()
                    exit()
                pass
            pass
        pass

    def run(self, method: Callable[[Stream], None]):
        self.action = method
        self.thread.start()
        pass

    def __init__(self, owner: ConnectionController, id: int) -> None:
        self.owner = owner
        self.id = id
        self.queue = Queue[Segment | None]()
        self.next_message_id = 0
        self.action: Callable[[Stream], None] | None = None
        self.file: BufferedIOBase | None = None

        self.next_fragment = 0
        self.fragment_queue: list[tuple[int, bytes]] = []
        self.fragment_count = 0
        self.received_segments: list[int] = []

        def start():
            assert self.action != None
            self.action(self)
            self.owner.streams.pop(self.id)

            try:
                while True:
                    self.receive()
                pass
            except Empty:
                return
            pass

        self.thread = Thread(target=start)
        pass


class ConnectionController:
    def send(self, segment: Segment):
        print("[-->]", segment.get_printable())

        self.handle.sendto(emit_segment(segment), self.target)
        pass

    def close(self):
        if not self.dispose_lock.acquire(blocking=False):
            exit()
        self.open = False
        print("[SIG] Close")
        self.handle.close()

    def dispose(self):
        for stream in self.streams.values():
            stream.queue.put(None)
        pass

        for stream in self.streams.values():
            if stream.thread.is_alive():
                stream.thread.join()
            pass
        pass

        self.streams.clear()
        pass

    def next_stream(self):
        id = self.next_stream_id
        self.next_stream_id += 2
        stream = Stream(self, id)
        self.streams[id] = stream
        return stream

    def request_fin(self):
        self.next_stream().run(lambda v: v.send_fin())
        print("[SIG] Sending fin.")

    def handle_segment(self, segment: Segment):
        self.last_segment_time = time.monotonic() + (Config.PING_INTERVAL * 0.1 * random())

        streamID = segment.stream
        stream = self.streams.get(streamID)

        if stream == None:
            stream = Stream(self, streamID)
            stream.queue.put(segment)
            stream.run(lambda v: v.listen())
            self.streams[streamID] = stream
            return
        pass

        stream.queue.put(segment)
        pass

    def tick(self):
        time_since_last_segment = time.monotonic() - self.last_segment_time
        if self.keep_alive_state == KeepAliveState.Normal:
            if time_since_last_segment > Config.PING_INTERVAL:
                self.next_stream().run(lambda v: v.send_ping())
                self.keep_alive_state = KeepAliveState.Notified
            pass
        else:
            if time_since_last_segment < Config.PING_INTERVAL:
                self.keep_alive_state = KeepAliveState.Normal
                return
            pass

            if self.keep_alive_state == KeepAliveState.Notified and time_since_last_segment > Config.PING_INTERVAL * 2:
                self.close()
            pass
        pass

    def __init__(self, handle: socket, target: tuple[str, int], is_server: bool) -> None:
        self.handle = handle
        self.is_server = is_server
        self.target = target

        self.open = True
        self.streams: dict[int, Stream] = {}
        self.next_stream_id = 0 if is_server else 1
        self.target_next_stream_id = 1 if is_server else 0
        self.dispose_lock = Semaphore(1)

        self.last_segment_time = time.monotonic()
        self.keep_alive_state = KeepAliveState.Normal
        pass
