#! /usr/bin/python3
# Autor: Jakub Martinak
# Login: xmartinakj

import socket

# Create a UDP socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_address = ('localhost', 10000)

try:
    message = b'This is the message. It will be repeated, somehow.'
    print(f"Sending: {message}")
    sent = client_socket.sendto(message, server_address)

    print("Waiting to receive")
    data, server = client_socket.recvfrom(4096)
    print(f"Received: {data}")
finally:
    print("Closing socket")
    client_socket.close()


# Create a UDP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to a port
server_address = ("localhost", 10000)
print(f"Starting up on {server_address[0]} port {server_address[1]}")
server_socket.bind(server_address)

while True:
    print("\nWaiting to receive message...")
    data, address = server_socket.recvfrom(4096)
    print(f"Received {len(data)} bytes from {address}")
    print(data)

    if data:
        sent = server_socket.sendto(data, address)
        print(f"Sent {sent} bytes back to {address}")
    else:
        print(f"Not sent {address}")