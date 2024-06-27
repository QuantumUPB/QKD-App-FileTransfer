from PyQt5.QtCore import QThread, pyqtSignal
import numpy as np
import hashlib
import os
import sys
import json
import time

seg_length = 220
key_length = 184


qkdgkt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'QKD-Infra-GetKey'))
sys.path.append(qkdgkt_path)
import qkdgkt

class SendFile:
    def __init__(self, to_name, file_path, src_location, dest_location):
        self.to_name = to_name
        self.file_path = file_path
        self.src_location = src_location
        self.dest_location = dest_location

        message = ""
        file_name = file_path.split('/')[-1]
        print("Sending: " + file_name)
        with open(file_path, "rb") as file:
            message = file.read()

        self.file_name = file_name
        self.message = message
        
        self.nr_segments = 0
        self.total_segments = int(np.ceil(len(message) / seg_length))

        self.metadata_sent = False


class FileSendWorker(QThread):
    signal_start_progress = pyqtSignal()
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
        self.signal_start_progress.emit()

    def run(self):
        while self.running:
            if self.sending_files:
                sending_file = self.sending_files[0]
                if not sending_file.metadata_sent:
                    self.send_metadata(sending_file)
                elif sending_file.nr_segments < sending_file.total_segments:
                    self.send_segment(sending_file)
                else:
                    self.sending_files.pop(0)
                    self.signal_end_progress.emit()
    
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
        for _ in range(5):
            key, key_ID = self.get_key(sending_file.dest_location, sending_file.src_location)
            accumulated_keys.extend(bytearray(key, 'utf-8'))
            key_ids_list.append(key_ID)

        batch_len = min(len(accumulated_keys), len(message))

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

            # sleep 1 second using sleep
            time.sleep(1)
            
        except ConnectionRefusedError:
            print("ECONNREFUSED")
        
        sending_file.nr_segments += 1
        sending_file.message = message[batch_len:]

        self.signal_update_progress.emit(sending_file.nr_segments, sending_file.total_segments)

    def stop(self):
        self.running = False

    def get_key(self, destination, source):
        config = qkdgkt.qkd_get_config()

        cert = config['cert']
        cakey = config['key']
        cacert = config['cacert']
        pempassword = config['pempassword']
        ipport = [loc for loc in config['locations'] if loc['name'] == source][0]['ipport']
        endpoint = [loc for loc in config['locations'] if loc['name'] == destination][0]['endpoint']

        output = qkdgkt.qkd_get_key_custom_params(endpoint, ipport, cert, cakey, cacert, pempassword, 'Request')
        response = json.loads(output)
        # print(response)

        keys = response['keys']
        for key_data in keys:
            key = key_data['key']
            key_ID = key_data['key_ID']
            return key, key_ID
