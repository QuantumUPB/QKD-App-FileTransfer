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

    def start(self):
        print(f"Broker listening on {self.host}:{self.port}")
        while True:
            # Receive a message with routing information
            parts = self.socket.recv_multipart()
            print(parts)
            if len(parts) == 3:
                client_id, empty, message = parts
            elif len(parts) == 2:
                client_id, message = parts
            else:
                print(f"Unexpected message format: {parts}")
                continue
            
            message = message.decode()
            print(f"Received message from client: {message}")

            # Split the message into command and content
            parts = message.split(":", 1)
            command = parts[0]
            content = parts[1] if len(parts) > 1 else ""

            if command == "register":
                client_name = content
                self.clients[client_name] = client_id
                self.socket.send_multipart([client_id, b"ok"])
                print(f"Client {client_name} registered")

            elif command == "list_clients":
                client_list = ",".join(self.clients.keys())
                self.socket.send_multipart([client_id, client_list.encode()])
                print("Sent client list")

            elif command == "relay":
                target_client, data = content.split(":", 1)
                if target_client in self.clients:
                    target_id = self.clients[target_client]
                    message = f"{target_client}:{data}".encode()
                    self.socket.send_multipart([target_id, message])
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
