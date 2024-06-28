from PyQt5.QtCore import QThread, pyqtSignal
import numpy as np
import hashlib
import os
import sys
import json
import base64
import time

with open('config.json') as f:
    config = json.load(f)["filetransfer"]
seg_length = config['segment_size']

qkdgkt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'QKD-Infra-GetKey'))
sys.path.append(qkdgkt_path)
import qkdgkt

class ReceivingFile:
    def __init__(self, program, from_name, file_path, msg_len, src_location):
        self.program = program
        self.from_name = from_name
        self.file_path = file_path
        self.msg_len = msg_len
        self.src_location = src_location
        
        self.remaining_len = msg_len
        self.total_segments = int(np.ceil(msg_len / seg_length))
        self.nr_segments = 0

        self.accumulated_data = bytearray()
        self.accumulated_keys = bytearray()
    
    def receive_segment(self, segment_data, keys):
        self.nr_segments += 1
        self.remaining_len -= len(segment_data)

        self.accumulated_data.extend(segment_data)
        keys = keys[:len(segment_data)]
        self.accumulated_keys.extend(keys)

    def check_file_ready_to_save(self):
        # if all segments have been received
        if self.nr_segments == self.total_segments:
            return True
    
    def save_file(self):
        encrypted_message = self.accumulated_data
        accumulated_keys = self.accumulated_keys

        decrypted_message = bytearray()
        for i in range(len(encrypted_message)):
            decrypted_byte = encrypted_message[i] ^ accumulated_keys[i]
            decrypted_message.append(decrypted_byte)

        md5_hash = hashlib.md5(decrypted_message).hexdigest()
        print("MD5 hash of original message:", md5_hash)
                
        with open(self.file_path, "wb") as file:
            file.write(decrypted_message)


class FileReceiverWorker(QThread):
    signal_list_clients = pyqtSignal(str)
    signal_start_progress = pyqtSignal(str, str)
    signal_update_progress = pyqtSignal(int, int)
    signal_end_progress = pyqtSignal()
    signal_received_ack = pyqtSignal(str)

    def __init__(self, socket, location):
        super().__init__()
        self.socket = socket
        self.running = True
        self.receiving_files = {}
        self.location = location

    def handle_relay(self, message_parts):
        from_name = message_parts[0].decode()
        message_parts = message_parts[1:]

        command = message_parts[0].decode()

        if command == "metadata":
            content = message_parts[1]
            msg_len = int(content.split("/".encode('utf-8'))[0])
            file_path = str(content.split("/".encode('utf-8'))[1], 'utf-8')
            src_location = str(content.split("/".encode('utf-8'))[2], 'utf-8')
            print("File name: " + file_path)
            print("Payload length: " + str(msg_len) + " bytes.")
            print("Location: " + src_location)

            # Create a new ReceivingFile object
            receiving_file = ReceivingFile(self, from_name, file_path, msg_len, src_location)
            self.receiving_files[from_name] = receiving_file
            self.signal_start_progress.emit("receive", from_name)
            print("EMITTED")

        elif command == "segment":
            receiving_file = self.receiving_files[from_name]
            segment_data = message_parts[1]

            keys = bytearray()
            key_ids = message_parts[2].decode()
            key_ids_list = key_ids.split('|')
            for key_id in key_ids_list:
                key = self.get_key(key_id, self.location, receiving_file.src_location)
                key = base64.b64decode(key)
                keys.extend(key)

            receiving_file.receive_segment(segment_data, keys)

            self.signal_update_progress.emit(receiving_file.nr_segments, receiving_file.total_segments)

            if receiving_file.check_file_ready_to_save():
                receiving_file.save_file()
                del self.receiving_files[from_name]
                self.signal_end_progress.emit()

            self.socket.send_multipart([f"relay:{from_name}".encode(), "ack".encode()])

            # print(f"Received segment from {from_name}", receiving_file.nr_segments, "/", receiving_file.total_segments)

        elif command == "ack":
            self.signal_received_ack.emit(from_name)

    def run(self):
        while self.running:
            message_parts = self.socket.recv_multipart()
            # print(message_parts)
            server_command = message_parts[0].decode()
            if server_command == "relay":
                self.handle_relay(message_parts[1:])
            elif server_command == "list_clients":
                client_reply = message_parts[1].decode()
                self.signal_list_clients.emit(client_reply)
            time.sleep(0.005)
            
    def stop(self):
        self.running = False

    def get_key(self, key_id, my_location, source):
        config = qkdgkt.qkd_get_config()

        cert = config['cert']
        cakey = config['key']
        cacert = config['cacert']
        pempassword = config['pempassword']
        ipport = [loc for loc in config['locations'] if loc['name'] == my_location][0]['ipport']
        endpoint = [loc for loc in config['locations'] if loc['name'] == source][0]['endpoint']

        output = qkdgkt.qkd_get_key_custom_params(endpoint, ipport, cert, cakey, cacert, pempassword, 'Response', key_id)
        response = json.loads(output)

        keys = response['keys']
        for key_data in keys:
            key = key_data['key']
            return key
