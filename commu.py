#! /usr/bin/python3
# Autor: Jakub Martinak
# Login: xmartinakj

import socket
import struct
import binascii

# CONFIG    ====================================================
IP_CLIENT = "localhost"
PORT_CLIENT = 10000
IP_SERVER = "localhost"
PORT_SERVER = 10000
MAX_DATA_SIZE = 1469 - 11
"""
    Header:
        1b typ
        3b cislo sekvencie
        4b ID file
        2B crc
        1b flag
        Payload size = 1458 bytes
        full packet size = 1469 bytes
"""
# ==============================================================


# FUNCTIONS ====================================================
def file_to_chunks(file_p, chunk_size):
    with open(file_p, 'rb') as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            yield chunk


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

# ==============================================================

class CustomHeader:
    def __init__(self, command, sequence_number, file_path, crc, flags):
        self.command = command
        self.sequence_number = sequence_number
        self.file_path = file_path
        self.crc = crc
        self.flags = flags

    def serialize(self):
        # The sequence_number and file_path must be converted to bytes if they are not already
        # CRC is a numerical value, computed over the data
        # Flags is a numerical value, fitting within 1 byte
        return struct.pack('!B3s4sHb', self.command, self.sequence_number, self.file_path, self.crc, self.flags)

    @staticmethod
    def deserialize(data):
        unpacked_data = struct.unpack('!B3s4sHb', data)
        return CustomHeader(*unpacked_data)


chose_input = input("Choose input: 1 - client, 2 - server: ")


if chose_input == "1":  # Client Side
    # Create a UDP socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (IP_SERVER, PORT_SERVER)

    # Define the custom header fields
    command = 0x01  # Example command
    sequence_number = b'1'  # Example sequence number as 3 bytes
    file_path = b'./pks_pdf_git/ss'  # Example file path as 4 bytes
    crc = 0x1D0F  # Example CRC16 value
    flags = 0x02  # Example flags value

    file_or_text = input("Choose input: 1 - text, 2 - file: ")
    if file_or_text == "1":     # =========================     TEXT     =========================
        try:
            # Create a header instance
            header_text = CustomHeader(command, sequence_number, b'text_mess', crc, flags)
            message_body = b'This is the message.'
            total_message = header_text.serialize() + message_body
            print(f"Sending: {total_message}")
            sent = client_socket.sendto(total_message, server_address)

            print("Waiting to receive")
            dat, server = client_socket.recvfrom(1469)
            print(f"Received: {dat}")
        finally:
            print("Closing socket")
            client_socket.close()
    else:   # =========================     File     =========================
        try:
            # crate a sequence number in bytes that is 3 bytes long
            sequence_number = 0  # Example sequence number as 3 bytes
            sequence_bytes = int_to_3bytes(sequence_number)

            for chunk in file_to_chunks('./big_file.txt', MAX_DATA_SIZE):
                # Assume a function `compute_crc` computes the CRC for the chunk
                crc = calculate_crc16(chunk)
                # Assume flags are set correctly for your custom protocol
                # flags = get_flags()

                # Create header for this chunk
                header = CustomHeader(command, sequence_bytes, file_path, crc, flags)
                packet = header.serialize() + chunk

                # Send packet
                client_socket.sendto(packet, server_address)

                # Increment sequence number for the next packet
                # sequence_number += 1
                # Increment the sequence number
                sequence_number = (sequence_number + 1) % (1 << 24)  # Ensure it wraps around at 2^24
                # Convert the incremented sequence number to a 3-byte byte object
                sequence_bytes = int_to_3bytes(sequence_number)

            # Create a header instance
            # header_file = CustomHeader(command, sequence_number, file_path, crc, flags)
            # message_body = b'This is the message. It will be repeated, somehow.'
            # total_message = header_file.serialize() + message_body
            # print(f"Sending: {total_message}")
            # sent = client_socket.sendto(total_message, server_address)

            # print("Waiting to receive")
            # dat, server = client_socket.recvfrom(1469)
            # print(f"Received: {dat}")
        finally:
            print("Closing socket")
            client_socket.close()


else:   # Server Side

    # Set up the server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ("localhost", 10000)
    server_socket.bind(server_address)
    print(f"Starting up on {server_address[0]} port {server_address[1]}")
    try:
        while True:
            print("\nWaiting to receive message...")
            packet, address = server_socket.recvfrom(1469)
            print(f"[+DEBUG+]Received {len(packet)} bytes from {address}")
            # Assuming the custom header is at the beginning of the packet
            header_data = packet[:11]  # 1 + 3 + 4 + 2 + 1 = 11 bytes for the header
            message_data = packet[11:]  # The rest is the payload

            # Deserialize the header
            header = CustomHeader.deserialize(header_data)

            # You might want to verify the CRC to ensure data integrity
            received_crc = header.crc
            computed_crc = binascii.crc_hqx(message_data, 0)
            if received_crc != computed_crc:
                print("CRC check failed, packet corrupted.")

            # Output the received header and data for demonstration purposes
            print(
                f"Received header: Command={header.command}, "
                f"Sequence Number={int(header.sequence_number, 16)}, "
                f"File Path={header.file_path}, "
                f"CRC={header.crc:04x}, "
                f"Flags={header.flags}")
            print(f"Received data: {message_data}")

            # Here you can implement your logic to handle the received data
            # ...

    finally:
        server_socket.close()
