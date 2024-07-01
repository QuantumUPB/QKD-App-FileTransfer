# This work has been implemented by Alin-Bogdan Popa and Bogdan-Calin Ciobanu,
# under the supervision of prof. Pantelimon George Popescu, within the Quantum
# Team in the Computer Science and Engineering department,Faculty of Automatic 
# Control and Computers, National University of Science and Technology 
# POLITEHNICA Bucharest (C) 2024. In any type of usage of this code or released
# software, this notice shall be preserved without any changes.


import zmq
import threading

host = "0.0.0.0"
port = 5555

class Broker:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.context = zmq.Context()

        # Create a ROUTER socket to handle incoming client connections
        self.socket = self.context.socket(zmq.ROUTER)
        self.socket.bind(f"tcp://{self.host}:{self.port}")

        # To keep track of client connections
        self.clients = {}
        self.client_locations = {}

    def start(self):
        print(f"Broker listening on {self.host}:{self.port}")
        while True:
            # Receive a message with routing information
            recv_parts = self.socket.recv_multipart()
            client_id = recv_parts[0]
            message = recv_parts[1].decode()
            
            print(f"Received message from client: {message}")

            # Split the message into command and content
            parts = message.split(":", 1)
            command = parts[0]
            content = parts[1] if len(parts) > 1 else ""

            if command == "register":
                client_name, location = content.split("/")
                self.clients[client_name] = client_id
                self.client_locations[client_name] = location
                self.socket.send_multipart([client_id, b"ok"])
                print(f"Client {client_name} registered")

            elif command == "list_clients":
                all_clients = []
                for client, location in self.client_locations.items():
                    all_clients.append(f"{client}/{location}")
                client_list = "|".join(all_clients)
                self.socket.send_multipart([client_id, "list_clients".encode(), client_list.encode()])
                print("Sent client list")

            elif command == "relay":
                target_client = content.split(":", 1)[0]
                if target_client in self.clients:
                    target_id = self.clients[target_client]
                    # get name of source client
                    source_client = [k for k, v in self.clients.items() if v == client_id][0]
                    relay_parts = recv_parts[2:]
                    self.socket.send_multipart([target_id, "relay".encode(), source_client.encode(), *relay_parts])
                    print(f"Relayed {command} to {target_client}")
                else:
                    self.socket.send_multipart([client_id, b"target_not_found"])
                    print(f"Target client {target_client} not found")

            else:
                self.socket.send_multipart([client_id, b"unknown_command"])
                print(f"Unknown command from client {str(client_id)}")

if __name__ == "__main__":
    broker = Broker(host, port)
    broker_thread = threading.Thread(target=broker.start)
    broker_thread.start()
    broker_thread.join()
