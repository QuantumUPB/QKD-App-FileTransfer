# This work has been implemented by Alin-Bogdan Popa and Bogdan-Calin Ciobanu,
# under the supervision of prof. Pantelimon George Popescu, within the Quantum
# Team in the Computer Science and Engineering department,Faculty of Automatic 
# Control and Computers, National University of Science and Technology 
# POLITEHNICA Bucharest (C) 2024. In any type of usage of this code or released
# software, this notice shall be preserved without any changes.


from PyQt5.QtCore import QThread, pyqtSignal
import numpy as np
import hashlib
import os
import sys
import json
import time
import base64

with open('config.json') as f:
    config = json.load(f)["filetransfer"]
seg_length = config['segment_size']

qkdgkt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'QKD-Infra-GetKey'))
sys.path.append(qkdgkt_path)
import qkdgkt

class SendFile:
    def __init__(self, to_name, file_path, src_location, dest_location):
        self.to_name = to_name
        self.file_path = file_path
        self.src_location = src_location
        self.dest_location = dest_location
        self.received_ack = True

        message = ""
        file_name = file_path.split('/')[-1]
        print("Sending: " + file_name)
        with open(file_path, "rb") as file:
            message = file.read()
        
        md5_hash = hashlib.md5(message).hexdigest()
        print("MD5 hash of original message:", md5_hash)

        self.file_name = file_name
        self.message = message
        
        self.nr_segments = 0
        self.total_segments = int(np.ceil(len(message) / seg_length))

        self.metadata_sent = False


class FileSendWorker(QThread):
    signal_start_progress = pyqtSignal(str, str)
    signal_update_progress = pyqtSignal(int, int)
    signal_end_progress = pyqtSignal()

    def __init__(self, socket):
        super().__init__()
        self.socket = socket
        self.running = True
        self.sending_files = []

    def add_file(self, to_name, file_path, src_location, dest_location):
        sending_file = SendFile(to_name, file_path, src_location, dest_location)
        self.sending_files.append(sending_file)
        self.signal_start_progress.emit("send", to_name)
    
    def handle_ack(self, to_name):
        for sending_file in self.sending_files:
            if sending_file.to_name == to_name:
                sending_file.received_ack = True
                break

    def run(self):
        while self.running:
            if self.sending_files:
                for i in range(len(self.sending_files)):
                    sending_file = self.sending_files[i]

                    if not sending_file.received_ack:
                        continue

                    if not sending_file.metadata_sent:
                        self.send_metadata(sending_file)
                    elif sending_file.nr_segments < sending_file.total_segments:
                        self.send_segment(sending_file)
                    else:
                        self.sending_files.pop(i)
                        self.signal_end_progress.emit()
            time.sleep(0.005)
    
    def send_metadata(self, sending_file):
        # Send the number of segments needed for the message via zmq
        try:
            # Convert the number of segments to bytes
            encrypted_message_bytes = bytes(str(len(sending_file.message)) + "/" + sending_file.file_name + "/" + sending_file.src_location, 'utf-8')

            # Send the metadata to relay via zmq
            self.socket.send_multipart([f"relay:{sending_file.to_name}".encode(), "metadata".encode(), encrypted_message_bytes])
            sending_file.metadata_sent = True
            print("Metadata sent successfully!")
        except ConnectionRefusedError:
            print("Connection refused. Make sure the server is running.")
            return
        
    def send_segment(self, sending_file):
        i = sending_file.nr_segments
        message = sending_file.message

        # sending_file.update_progress()
        accumulated_keys = bytearray()
        key_ids_list = []
        while len(accumulated_keys) < seg_length:
            key, key_ID = self.get_key(sending_file.dest_location, sending_file.src_location)
            key = base64.b64decode(key)
            accumulated_keys.extend(key)
            key_ids_list.append(key_ID)

        batch_len = min(seg_length, len(message))

        # Perform OTP encryption by XORing the message with the accumulated keys
        encrypted_message = bytearray()
        for i in range(batch_len):
            encrypted_byte = message[i] ^ accumulated_keys[i]
            encrypted_message.append(encrypted_byte)

        try:
            # Convert the encrypted message to bytes
            encrypted_message_bytes = bytes(encrypted_message)
        
            # Convert the key_ids to bytes
            combined_key_ids = '|'.join(key_ids_list)
            key_ids_bytes = combined_key_ids.encode('utf-8')

            # Send the key ids
            self.socket.send_multipart([f"relay:{sending_file.to_name}".encode(), "segment".encode(), encrypted_message_bytes, key_ids_bytes])

        except ConnectionRefusedError:
            print("ECONNREFUSED")
        
        sending_file.nr_segments += 1
        sending_file.message = message[batch_len:]

        self.signal_update_progress.emit(sending_file.nr_segments, sending_file.total_segments)
        sending_file.received_ack = False

    def stop(self):
        self.running = False

    def get_key(self, destination, source):
        time.sleep(0.2)
        config = qkdgkt.qkd_get_config()

        cert = config['cert']
        cakey = config['key']
        cacert = config['cacert']
        pempassword = config['pempassword']
        ipport = [loc for loc in config['locations'] if loc['name'] == source][0]['ipport']
        endpoint = [loc for loc in config['locations'] if loc['name'] == destination][0]['endpoint']

        base_url = ipport
        if os.environ.get("ADD_KME", "") != "":
            base_url += "/" + os.getenv("LOCATION", "ADD_LOCATION") + "/" + os.getenv("CONSUMER", "ADD_CONSUMER")

        output = qkdgkt.qkd_get_key_custom_params(endpoint, base_url, cert, cakey, cacert, pempassword, 'Request')
        response = json.loads(output)
        # print(response)

        keys = response['keys']
        for key_data in keys:
            key = key_data['key']
            key_ID = key_data['key_ID']
            return key, key_ID
