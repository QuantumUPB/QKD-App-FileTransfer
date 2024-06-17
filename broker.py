#!/bin/python3
import socket
import threading

host = "0.0.0.0"
sender_port_alice = 12344
receiver_port_alice = 12345
sender_port_bob = 12346
receiver_port_bob = 12347

class Broker:
    def __init__(self, host, server_port, client_port):
        self.host = host
        self.server_port = server_port
        self.client_port = client_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def handle_sender(self):
        self.server_socket.bind((self.host, self.server_port))
        self.server_socket.listen(1)
        print("Start listening for sender")
        while True:
            server_conn, _ = self.server_socket.accept()
            print("Sender accepted")
            while self.client_conn is None: # Wait until client connects
                continue
            print("Receiver connected, continuing")
            server_conn.send(bytes("ok", 'utf-8'))
            # Send the number of segments and name
            data = server_conn.recv(1024)
            if not data:
                continue
            self.client_conn.sendall(data)
            # Receive confirmation from the receiver
            data = self.client_conn.recv(1024)
            server_conn.send(data)
            while True: # Keep receiving packets until server closes the connection
                data = server_conn.recv(220)
                data += server_conn.recv(184)
                if not data:
                    break
                self.client_conn.sendall(data)
                server_conn.send(self.client_conn.recv(1024))
            server_conn.close()
            self.client_conn.close()
            self.client_conn = None

    def handle_receiver(self):
        self.client_socket.bind((self.host, self.client_port))
        self.client_socket.listen(1)
        print("Start listening for receiver")
        while True:
            while self.client_conn is not None: # Wait until the previous transaction has completed
                continue
            self.client_conn, _ = self.client_socket.accept()
            print("Receiver accepted")

    def start(self):
        self.client_conn = None

        server_thread = threading.Thread(target=self.handle_sender)
        client_thread = threading.Thread(target=self.handle_receiver)

        server_thread.start()
        client_thread.start()

if __name__ == "__main__":
    brokerAB = Broker(host, sender_port_alice, receiver_port_bob)
    brokerBA = Broker(host, sender_port_bob, receiver_port_alice)

    brokerAB_thread = threading.Thread(target=brokerAB.start)
    brokerBA_thread = threading.Thread(target=brokerBA.start)

    brokerAB_thread.start()
    brokerBA_thread.start()

    brokerAB_thread.join()
    brokerBA_thread.join()
