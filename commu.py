#! /usr/bin/python3
# Python 3.10
# Autor: Jakub Martinak
# Login: xmartinakj

import socket
import struct
import binascii
import os
import math
import random
import threading
import time


# CONFIG    ====================================================
IP_CLIENT = "127.0.0.1"
PORT_CLIENT = 8000
IP_SERVER = "127.0.0.2"
PORT_SERVER = 8000
MAX_PACKET_SIZE = 1469
HEADER_SIZE = 10
MAX_DATA_SIZE = MAX_PACKET_SIZE - HEADER_SIZE
PACKET_TYPES = {
    "Init": 0x01,
    "Data": 0x02,
    "Ack": 0x03,
    "Fin": 0x04,
    "FinAck": 0x05,
    "Change": 0x06
}

"""
    Header:
        1b typ
        3b cislo sekvencie
        4b ID file
        2B crc
        1b flag - Not used
        Payload size = 1458 bytes
        full packet size = 1469 bytes
"""
# ==============================================================


# FUNCTIONS ====================================================

def corrupt_packet(packet, corruption_rate=0.01):
    """
    Simulates packet corruption by randomly altering some of the bytes.

    Args:
    - packet (bytes): The original packet data.
    - corruption_rate (float): The probability of each byte being altered.

    Returns:
    - bytes: The corrupted packet.
    """
    corrupted_packet = bytearray(packet)
    for i in range(len(corrupted_packet)):
        if random.random() < corruption_rate:
            corrupted_packet[i] = corrupted_packet[i] ^ random.getrandbits(8)
    return bytes(corrupted_packet)

def calculate_total_chunks(file_path, chunk_size):
    # Get the size of the file
    file_size = os.path.getsize(file_path)

    # Calculate the number of chunks
    total_chunks = math.ceil(file_size / chunk_size)
    return total_chunks


def file_to_chunks(file_p, chunk_size):
    """
    Generator that reads a file in chunks of chunk_size bytes.
    :param file_p:
    :param chunk_size:
    :return: chunk of data
    """

    with open(file_p, 'rb') as file:
        chunk_count = 0
        while True:
            chunky = file.read(chunk_size)
            if not chunky:
                break
            chunk_count += 1
            yield chunky


def calculate_crc16(data, initial_value=0):
    """
    Calculate the CRC16 checksum for the given data.

    Args:
    - data (bytes): The data for which to compute the checksum.
    - initial_value (int): The initial value of the checksum. Default is 0.

    Returns:
    - int: The computed CRC16 checksum.
    """
    return binascii.crc_hqx(data, initial_value)


def int_to_3bytes(num):
    """
    Convert an integer to a 3-byte long byte object.

    Args:
    - num (int): The integer to convert. Must be in the range 0 to 16,777,215.

    Returns:
    - bytes: The 3-byte long byte object.
    """
    if not 0 <= num <= 0xFFFFFF:
        raise ValueError("Number out of range for 3 bytes")
    return num.to_bytes(3, byteorder='big')


def send_packet(sock, packet, address, timeout=5):
    try:
        sock.settimeout(timeout)
        sock.sendto(packet, address)

        # Wait for ACK
        response, _ = sock.recvfrom(1024)  # Buffer size for ACK
        if int.from_bytes(response, byteorder='big') == 0x03:
            return response
    except socket.timeout:
        count = 0
        while count < 3:
            print("Timeout, resending packet...")
            sock.sendto(packet, address)
            try:
                ack, _ = sock.recvfrom(1024)  # Buffer size for ACK
                return ack
            except socket.timeout:
                count += 1
        print("Server not responding, closing connection...")
        # sock.close()
        return None
        # return None


# def get_input(timeout):
#     print(f"You have {timeout} seconds to type your input...")
#     input_thread = threading.Thread(target=input, args=("Choose input: 1 - client, 2 - server: ",))
#     input_thread.start()
#     input_thread.join(timeout)
#     if input_thread.is_alive():
#         print("\nTimeout! No input was entered.")
#         return None
#     else:
#         return input_thread.result


# ==============================================================


class CustomHeader:
    def __init__(self, command, sequence_number, file_path, crc):
        self.command = command
        self.sequence_number = sequence_number
        self.file_path = file_path
        self.crc = crc
        # self.flags = flags

    def serialize(self):
        # The sequence_number and file_path must be converted to bytes if they are not already
        # CRC is a numerical value, computed over the data
        # Flags is a numerical value, fitting within 1 byte
        return struct.pack('!B3s4sH', self.command, self.sequence_number, self.file_path, self.crc)

    @staticmethod
    def deserialize(data):
        unpacked_data = struct.unpack('!B3s4sH', data)
        return CustomHeader(*unpacked_data)


count_of_starts = 0
while True:
    if count_of_starts == 0:
        print("==========================================================")
        print("Hello! Please choose if you want to be a client or server")
        print("After sending message/file, you will be asked to choose again")
        print("If you want to exit, press CTRL+C")
        print("Or wait for timeout")
        print("==========================================================")
    else:
        print("==========================================================")
        print("Choose if you want to be a client or server")
        print("==========================================================")

    chose_input = input("Choose input: 1 - client, 2 - server: ")

    if chose_input == "1":  # Client Side
        IP_SERVER = input("Enter server IP: ")
        PORT_SERVER = int(input("Enter server port: "))
        # Create a UDP socket
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_address = (IP_SERVER, PORT_SERVER)

        # Define the custom header fields
        command = 0x01  # Example command
        flags = 0x02  # Example flags value

        file_or_text = input("Choose input: 1 - text, 2 - file: ")
        if file_or_text == "1":     # =========================     TEXT     =========================
            try:
                # Send TEXT
                message_body = bytes(input("Enter the message: "), 'utf-8')
                crc = calculate_crc16(message_body)

                sequence_number = 0  # Example sequence number as 3 bytes
                sequence_bytes = int_to_3bytes(sequence_number)

                # Create a header instance
                if sequence_number == 0:    # send init packet
                    # crc = calculate_crc16("Init")
                    header_init = CustomHeader(PACKET_TYPES.get("Init"), sequence_bytes, b'Init', crc)
                    response = send_packet(client_socket, header_init.serialize(), server_address)
                    if response:
                        print("Connection Innitiated")
                    else:
                        client_socket.close()
                        exit(1)
                else:
                    header_text = CustomHeader(command, sequence_bytes, b'text_mess', crc)

                    total_message = header_text.serialize() + message_body
                    print(f"Sending: {message_body}")
                    sent = client_socket.sendto(total_message, server_address)

                    print("Waiting to receive")
                    dat, server = client_socket.recvfrom(MAX_PACKET_SIZE)
                    print(f"Received: {dat}")
            finally:
                print("Text sent successfully")
                continue
            # finally:
            #     print("Closing socket")
            #     client_socket.close()
        else:   # =========================     File     =========================
            response = None
            try:
                # Input the file path
                file_path_input = input("Enter the file path: ")
                file_path = bytes(file_path_input, 'utf-8')
                # crate a sequence number in bytes that is 3 bytes long
                sequence_number = 0  # Example sequence number as 3 bytes
                sequence_bytes = int_to_3bytes(sequence_number)

                # Calculate the total number of chunks
                total_chunks = calculate_total_chunks(file_path_input, MAX_DATA_SIZE) - 1

                if sequence_number == 0:    # send init packet
                    crc = calculate_crc16(b"Init")
                    header_init = CustomHeader(PACKET_TYPES.get("Init"), sequence_bytes, b'Init', crc)
                    response = send_packet(client_socket, header_init.serialize(), server_address)
                    if response:
                        print("Connection Innitiated")
                        sequence_number += 1
                    else:
                        client_socket.close()
                        exit(1)

                for chunk in file_to_chunks(file_path_input, MAX_DATA_SIZE):
                    # Assume a function `compute_crc` computes the CRC for the chunk
                    crc = calculate_crc16(chunk)
                    # Assume flags are set correctly for your custom protocol
                    # flags = get_flags()

                    # Create header for this chunk
                    if not (len(chunk) > MAX_DATA_SIZE - 1):
                        print("last packet, sending FIN")
                        fin_header = CustomHeader(PACKET_TYPES.get("Fin"), sequence_bytes, file_path, crc)
                        packet = fin_header.serialize() + chunk
                    else:
                        header = CustomHeader(PACKET_TYPES.get("Data"), sequence_bytes, file_path, crc)
                        packet = header.serialize() + chunk
                    # if sequence_number == 716:
                    #     print("Corrupting packet")
                    #     packet = corrupt_packet(packet)
                    # Send packet
                    response = send_packet(client_socket, packet, server_address)
                    if response is None:
                        # print("Server not responding, closing connection...")
                        client_socket.close()
                        break

                    # client_socket.sendto(packet, server_address)
                    # Increment the sequence number
                    sequence_number = (sequence_number + 1) % (1 << 24)  # Ensure it wraps around at 2^24

                    # Convert the incremented sequence number to a 3-byte byte object
                    sequence_bytes = int_to_3bytes(sequence_number)

                    # dat, server = client_socket.recvfrom(MAX_PACKET_SIZE)
                    # print(f"Received: {dat.decode('utf-8')}")
                if response is not None:
                    print(f"File sent successfully = {total_chunks} packets")
                # print("File sent successfully = ", total_chunks)
            finally:
                print("file sent successfully")
                continue
                # print("Closing socket")
                # client_socket.close()


    else:   # Server Side

        # Set up the server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_address = (IP_SERVER, PORT_SERVER)
        server_socket.bind(server_address)
        print(f"Starting up on {server_address[0]} port {server_address[1]}")
        try:
            while True:
                print("\nWaiting to receive message...")
                packet, address = server_socket.recvfrom(MAX_PACKET_SIZE)
                print(f"[+DEBUG+]Received {len(packet)} bytes from {address}")
                # Assuming the custom header is at the beginning of the packet
                header_data = packet[:HEADER_SIZE]  # 1 + 3 + 4 + 2 + 1 = 11 bytes for the header
                message_data = packet[HEADER_SIZE:]  # The rest is the payload

                # Deserialize the header
                header = CustomHeader.deserialize(header_data)

                # You might want to verify the CRC to ensure data integrity
                received_crc = header.crc
                computed_crc = binascii.crc_hqx(message_data, 0)
                if header.command == 0x01:
                    print("Init packet received")
                    server_socket.sendto(int.to_bytes(0x03, length=1, byteorder='big'), address)
                    continue

                if received_crc != computed_crc:
                    print("CRC check failed, packet corrupted.")
                else:
                    if header.command == 0x02:
                        print("Data packet received")
                        # send back to client
                        server_socket.sendto(int.to_bytes(0x03, length=1, byteorder='big'), address)
                    elif header.command == 0x04:
                        print("FIN packet received")
                        # send back to client
                        server_socket.sendto(int.to_bytes(0x05, length=1, byteorder='big'), address)
                # Output the received header and data for demonstration purposes
                print(
                    f"Received header: Command={header.command}, "
                    f"Sequence Number={int.from_bytes(header.sequence_number, byteorder='big')}, "
                    f"File Path={header.file_path}, "
                    f"CRC={header.crc:04x}, ")
                print(f"Received data: {message_data}")

                # Here you can implement your logic to handle the received data
                # ...

        finally:
            server_socket.close()

