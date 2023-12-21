from __future__ import annotations

from queue import Queue
from socket import AF_INET, SOCK_DGRAM, socket
from sys import argv, exit
from threading import Thread

from config import Config
from ConnectionController import ConnectionController
from Segment import InitMessage, Segment, parse_segment


class UserInputThread(Thread):
    def run(self):
        while True:
            self.queue.put(input())
        pass

    def stop(self):
        self.queue.put(None)

    def __init__(self):
        super().__init__(daemon=True)
        self.queue = Queue[str | None]()


user_input = UserInputThread()
user_input.start()


class Application:
    def init(self):
        pass

    def start(self):
        pass

    def update(self, addr: tuple[str, int], segment: Segment):
        pass

    def tick(self):
        if self.controller == None:
            return
        self.controller.tick()
        pass

    def run(self):
        self.start()

        def listener():
            while True:
                line = user_input.queue.get()
                if line == None:
                    return
                pass

                if self.controller == None:
                    continue
                pass

                text = line
                if text.startswith("FIN"):
                    self.controller.request_fin()
                    continue
                pass

                if text.startswith("FILE"):
                    segments = text[4:].split(",")
                    if segments.__len__() != 2:
                        print("Expected source file, destination path")
                        continue
                    pass
                    source = segments[0].strip()
                    dest = segments[1].strip()
                    self.controller.next_stream().run(lambda v: v.send_file(source, dest))
                    continue
                pass

                if text.startswith("SIZE"):
                    new_size = None
                    try:
                        new_size = int(text[4:])
                    except ValueError:
                        print("Expected max fragment size")
                        continue
                    pass

                    if new_size <= 0:
                        print("Value must be at least 1")
                        continue
                    pass

                    Config.FRAGMENT_SIZE = new_size
                    print(f"Setting FRAGMENT_SIZE to {Config.FRAGMENT_SIZE}")
                    continue
                pass

                if text.startswith("LOSS"):
                    new_loss = None
                    try:
                        new_loss = int(text[4:])
                    except ValueError:
                        print("Expected max fragment size")
                        continue
                    pass

                    if new_loss <= 0:
                        print("Value must be at least 0")
                        continue
                    pass

                    Config.PACKET_LOSS = new_loss
                    print(f"Setting PACKET_LOSS to {Config.PACKET_LOSS}")
                    continue
                pass

                self.controller.next_stream().run(lambda v: v.send_text(text))
            pass

        listener_thread = Thread(target=listener)
        listener_thread.start()

        while self.controller == None or self.controller.open:
            try:
                data, addr = self.handle.recvfrom(2048)
                segment = parse_segment(data)
                if segment == None:
                    continue
                pass

                print("[<--]", segment.get_printable())

                self.update(addr, segment)
                self.tick()
            except (TimeoutError, OSError):
                self.tick()
                continue
            pass
        pass

        if self.controller != None:
            self.controller.dispose()
        pass

        user_input.stop()
        listener_thread.join()
        pass

    def __init__(self) -> None:
        self.init()
        self.controller: ConnectionController | None = None

        self.handle = socket(AF_INET, SOCK_DGRAM)
        self.handle.settimeout(0.1)

        pass


class ServerApplication(Application):
    def init(self):
        print(f"Starting server at {port}")

    def start(self):
        self.handle.bind(("", port))

    def update(self, addr: tuple[str, int], segment: Segment):
        if self.controller == None:
            if isinstance(segment, InitMessage):
                self.controller = ConnectionController(self.handle, addr, True)
                self.controller.handle_segment(segment)
                print(f"New client [{addr[0]}]:{addr[1]}")
            pass

            return
        pass

        self.controller.handle_segment(segment)
        pass

    def __init__(self, port: int) -> None:
        super().__init__()
        self.port = port


class ClientApplication(Application):
    def init(self):
        print(f"Starting client and connecting to [{addr}]:{port}")

    def start(self):
        self.controller = ConnectionController(self.handle, self.target, False)
        self.controller.next_stream().run(lambda v: v.send_init())

    def update(self, addr: tuple[str, int], segment: Segment):
        assert self.controller != None
        self.controller.handle_segment(segment)

    def __init__(self, addr: str, port: int) -> None:
        super().__init__()
        self.addr = addr
        self.port = port
        self.target = (addr, port)
        pass


if argv.__len__() < 2:
    exit("Expected arguments")

if argv[1] == "client":
    if argv.__len__() != 4:
        exit("Expected 4 arguments")
    addr = argv[2]
    port = int(argv[3])
    ClientApplication(addr, port).run()
    print("Done")
elif argv[1] == "server":
    if argv.__len__() != 3:
        exit("Expected 3 arguments")
    port = int(argv[2])
    ServerApplication(port).run()
    print("Done")
else:
    exit("Invalid type")
