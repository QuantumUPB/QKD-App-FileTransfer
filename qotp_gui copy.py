import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QTreeView, QFileSystemModel, QProgressBar, QStatusBar, QFrame, QMessageBox
)
from PyQt5.QtCore import QTimer, QTime

import subprocess
import json
import time
import asyncio
import hashlib
import socket
import threading
import sys
from tqdm import tqdm

from qasync import QEventLoop, asyncSlot

import sys
import signal

import numpy as np
import os

qkdgkt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'QKD-Infra-GetKey'))
sys.path.append(qkdgkt_path)
import qkdgkt

lock = asyncio.Lock()
seg_length = 220
key_length = 184


class KeyContainer:
    def __init__(self, key, key_ID):
        self.key = key
        self.key_ID = key_ID


class QKDTransferApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Main layout for the window
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # Initial screen setup
        self.init_connection_screen()

        # Window properties
        self.setWindowTitle('QKD Secure File Transfer')
        self.setGeometry(300, 100, 400, 100)
        self.show()

    def init_connection_screen(self):
        # Initial connection screen with IP and Port fields and Connect button
        self.message_label = QLabel('Connect to Broker')
        
        self.ip_label = QLabel('IP Address:')
        self.ip_field = QLineEdit('127.0.0.1')

        self.send_port_label = QLabel('Send Port:')
        self.send_port_field = QLineEdit('12344') 

        self.receive_port_label = QLabel('Receive Port:')
        self.receive_port_field = QLineEdit('12345') 

        self.connect_button = QPushButton('Connect')
        self.connect_button.clicked.connect(self.connect_to_server)

        # Layout for connection screen
        self.connection_layout = QVBoxLayout()
        self.connection_layout.addWidget(self.message_label)
        self.connection_layout.addWidget(self.ip_label)
        self.connection_layout.addWidget(self.ip_field)
        self.connection_layout.addWidget(self.send_port_label)
        self.connection_layout.addWidget(self.send_port_field)
        self.connection_layout.addWidget(self.receive_port_label)
        self.connection_layout.addWidget(self.receive_port_field)
        self.connection_layout.addWidget(self.connect_button)

        # Add connection layout to main layout
        self.main_layout.addLayout(self.connection_layout)

    def connect_to_server(self):
        # make connect button disabled
        self.connect_button.setEnabled(False)
        self.repaint()

        # Placeholder for connection logic
        ip = self.ip_field.text()
        port = int(self.receive_port_field.text())
                   
        # Here you would add the actual connection logic using ip and port
        print(f"Connecting to {ip}:{port}...")

        # # Create a client socket
        # client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # client_socket.settimeout(5)  # Set a timeout for the connection attempt

        # try:
        #     # Attempt to connect to the broker
        #     client_socket.connect((ip, port))
        # except (ConnectionRefusedError, socket.timeout):
        #     # Show an error message if the connection fails
        #     error_message = QMessageBox()
        #     error_message.setIcon(QMessageBox.Critical)
        #     error_message.setText("Connection failed")
        #     error_message.setInformativeText("Could not connect to the broker. Please check the IP and port, and ensure the broker is running.")
        #     error_message.setWindowTitle("Connection Error")
        #     error_message.exec_()

        #     client_socket.close()
        #     self.connect_button.setEnabled(True)
        #     return
        # except Exception as e:
        #     # Handle any other exceptions
        #     error_message = QMessageBox()
        #     error_message.setIcon(QMessageBox.Critical)
        #     error_message.setText("An error occurred")
        #     error_message.setInformativeText(f"An unexpected error occurred: {str(e)}")
        #     error_message.setWindowTitle("Error")
        #     error_message.exec_()

        #     client_socket.close()
        #     self.connect_button.setEnabled(True)
        #     return

        self.ip = ip
        self.send_port = int(self.send_port_field.text())
        self.receive_port = int(self.receive_port_field.text())

        # # If connection is successful, proceed to the main interface
        # client_socket.close()  # Close the socket as we just needed to check the connection
        self.switch_to_main_interface()

        # Start the receiver loop
        self.recv_loop()

    def switch_to_main_interface(self):
        self.setGeometry(300, 100, 800, 600)

        # Clear the initial connection screen
        for i in reversed(range(self.connection_layout.count())):
            widget = self.connection_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        self.main_layout.removeItem(self.connection_layout)

        # Setup main interface components
        self.init_main_interface()

    def init_main_interface(self):
        # Main layout for the file transfer interface
        self.main_transfer_layout = QHBoxLayout()

        # Explorer sidebar
        self.explorer_layout = QVBoxLayout()
        self.explorer_label = QLabel('File Explorer')
        self.explorer_label.setStyleSheet("font-weight: bold;")
        self.file_system_model = QFileSystemModel()
        self.file_system_model.setRootPath('')
        self.file_explorer = QTreeView()
        self.file_explorer.setModel(self.file_system_model)
        self.file_explorer.setRootIndex(self.file_system_model.index(''))
        self.file_explorer.setSelectionMode(QTreeView.SingleSelection)
        self.file_explorer.clicked.connect(self.file_selected)
        
        self.explorer_layout.addWidget(self.explorer_label)
        self.explorer_layout.addWidget(self.file_explorer)

        # Right-side layout for send and status
        self.right_layout = QVBoxLayout()

        self.send_button = QPushButton('SEND')
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_loop)

        self.instructions_label = QLabel('<b>Instructions and Status:</b>')
        self.listening_label = QLabel('Listening for incoming files...')

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage('Ready')

        self.right_layout.addWidget(self.instructions_label)
        self.right_layout.addWidget(self.send_button)
        self.right_layout.addWidget(self.listening_label)
        self.right_layout.addWidget(self.progress_bar)
        self.right_layout.addStretch(1)
        self.right_layout.addWidget(self.status_bar)

        # Add explorer and right layouts to main transfer layout
        self.main_transfer_layout.addLayout(self.explorer_layout, 1)
        self.main_transfer_layout.addLayout(self.right_layout, 2)

        # Add main transfer layout to the main layout of the window
        self.main_layout.addLayout(self.main_transfer_layout)

    def file_selected(self, index):
        # Get the selected file path
        self.selected_file_path = self.file_system_model.filePath(index)
        self.send_button.setEnabled(True)

    def update_progress(self):
        nr_segments = self.nr_segments
        total_segments = self.total_segments

        # Update the progress bar at nr_segments / total_segments
        self.progress_bar.setValue(int(nr_segments / total_segments * 100))
        elapsed_time = int(self.start_time.elapsed() / 1000)  # Elapsed time in seconds

        if self.progress_bar.value() >= 100:
            self.timer.stop()
            self.status_bar.showMessage('File sent successfully!')
            self.progress_bar.setVisible(False)
        else:
            self.status_bar.showMessage(f'Sending file [{elapsed_time // 60 :02d}:{(elapsed_time % 60):02d} elapsed]')

    @asyncSlot()
    async def send_file(self):
        async with lock:
            print(f"Sending file: {self.selected_file_path}")

            #  file sending and update progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_bar.showMessage('Sending file...')

            self.start_time = QTime.currentTime()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_progress)
            self.timer.start(100)  # Update progress every 100ms

            file_path = self.selected_file_path
            message = ""
            file_name = file_path.split('/')[-1]
            print("Sending: " + file_name)
            with open(file_path, "rb") as file:
                message = file.read()

            number_of_segments = int(np.ceil(len(message) / seg_length))
            self.nr_segments = 0
            self.total_segments = number_of_segments

            # Send the number of segments needed for the message
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            ip = self.ip
            sender_port = self.send_port

            try:
                # Connect to the server
                client_socket.connect((ip, sender_port))

                # Await for receiver to connect
                print("Awaiting for the receiver to connect.")
                goahead = client_socket.recv(1024)
                if not goahead:
                    print("Connection closed by broker")
                    client_socket.close()
                    return

                # Convert the number of segments to bytes
                encrypted_message_bytes = bytes(str(len(message)) + "/" + file_name, 'utf-8')

                # Send the metadata
                client_socket.sendall(encrypted_message_bytes)
                print("Metadata sent successfully!")

                print("Awaiting for the receiver to accept.")
                response = client_socket.recv(1024)
                if not response or str(response, 'utf-8') != "ok":
                    print("Transmission not accepted by receiver")
                    client_socket.close()
                    return
            except ConnectionRefusedError:
                print("Connection refused. Make sure the server is running.")
                client_socket.close()
                return

            # Execute the curl command periodically and accumulate keys
            for i in tqdm(range(number_of_segments)):
                self.nr_segments += 1
                self.update_progress()

                accumulated_keys = bytearray()
                key_objects = []
                for _ in range(5):
                    output = qkdgkt.qkd_get_key_custom_params('Campus', 'Precis', 'upb-ap.crt', 'qkd,key', 'qkd-ca.crt', 'pgpopescu', 'Request')
                    response = json.loads(output)

                    # Extract the key and key_ID values
                    keys = response['keys']
                    for key_data in keys:
                        key = key_data['key']
                        key_ID = key_data['key_ID']
                        key_object = KeyContainer(key, key_ID)
                        key_objects.append(key_object)

                        # Accumulate the key bytes
                        accumulated_keys.extend(bytearray(key, 'utf-8'))

                    # Delay execution for 100 milliseconds
                    # time.sleep(0.1)

                batch_len = min(len(accumulated_keys), len(message))

                # Perform OTP encryption by XORing the message with the accumulated keys
                encrypted_message = bytearray()
                for i in range(batch_len):
                    encrypted_byte = message[i] ^ accumulated_keys[i]
                    encrypted_message.append(encrypted_byte)

                # Print the encrypted message
                key_ids_list = []
                for key_obj in key_objects:
                    key_ids_list.append(key_obj.key_ID)

                message = message[batch_len:]

                try:
                    # Convert the encrypted message to bytes
                    encrypted_message_bytes = bytes(encrypted_message)

                    # Send the encrypted message
                    client_socket.sendall(encrypted_message_bytes)
                except ConnectionRefusedError:
                    print("Connection refused. Make sure the server is running.")

                try:
                    # Convert the key_ids to bytes
                    combined_key_ids = '|'.join(key_ids_list)
                    key_ids_bytes = combined_key_ids.encode('utf-8')

                    # Send the key ids
                    client_socket.sendall(key_ids_bytes)
                except ConnectionRefusedError:
                    print("ECONNREFUSED")

                ack = client_socket.recv(1024)

            self.nr_segments = self.total_segments
            self.update_progress()
            client_socket.close()
            print("MD5 Hash of original message:", hashlib.md5(message).hexdigest())

    async def receive_file(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        ip = self.ip
        receiver_port = self.receive_port

        try:
            client_socket.connect((ip, receiver_port))
        except ConnectionRefusedError:
            print("Connection refused. Make sure the broker is running.")
            client_socket.close()
            return

        print("Awaiting for sender to begin transmission.")
        metadata_raw = client_socket.recv(1024)
        print("Metadata received successfully!")
        msg_len = int(metadata_raw.split("/".encode('utf-8'))[0])
        file_path = str(metadata_raw.split("/".encode('utf-8'))[-1], 'utf-8')
        print("File name: " + file_path)
        print("Payload length: " + str(msg_len) + " bytes.")

        async with self.lock:  # Assuming `lock` is a member of the class
            print("Lock acquired")
            
            # Open PyQt5 dialog to confirm receive
            confirm = QMessageBox()
            confirm.setIcon(QMessageBox.Question)
            confirm.setText(f"Receive file {file_path} of {msg_len} bytes?")
            confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm.setDefaultButton(QMessageBox.Yes)
            
            response = await self.show_async_message_box(confirm)
            if response == QMessageBox.No:
                client_socket.send(bytes("reject", 'utf-8'))
                client_socket.close()
                return

            # Open PyQt5 dialog to select save location
            save_dialog = QFileDialog()
            file_path, _ = await self.show_async_file_dialog(save_dialog, "Save File", file_path)
            
            if not file_path:
                client_socket.send(bytes("reject", 'utf-8'))
                client_socket.close()
                return
            
            remaining_len = msg_len
            seg_no = int(np.ceil(msg_len / seg_length))
            self.total_segments = seg_no
            self.nr_segments = 0

            #  file sending and update progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_bar.showMessage('Sending file...')

            self.start_time = QTime.currentTime()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_progress)
            self.timer.start(100)  # Update progress every 100ms

            print("Payload length: " + str(msg_len) + " bytes.")
            accumulated_keys = bytearray()
            encrypted_message = bytearray()
            client_socket.send(bytes('ok', 'utf-8'))

            print(seg_no)

            for i in tqdm(range(seg_no)):
                # update progress bar
                self.nr_segments += 1
                self.update_progress()

                # Receive data from the client
                new_data = client_socket.recv(min(seg_length, remaining_len))
                encrypted_message.extend(new_data)
                remaining_len -= len(new_data)

                # Receive key ids from the client
                key_ids_enc = client_socket.recv(key_length)

                if encrypted_message:
                    # Perform further processing on the encrypted message as needed
                    key_ids = key_ids_enc.decode('utf-8').split('|')

                    for key_id in key_ids:
                        output = qkdgkt.qkd_get_key_custom_params('Precis', 'Campus', 'upb-ap.crt', 'qkd,key', 'qkd-ca.crt', 'pgpopescu', 'Response', key_id)
                        response = json.loads(output)
                        print(response)

                        keys = response['keys']
                        for key_data in keys:
                            key = key_data['key']
                            accumulated_keys.extend(bytearray(key, 'utf-8'))
                            
                client_socket.send(bytes('ok', 'utf-8'))

            # Close the client socket
            client_socket.close()

            decrypted_message = bytearray()
            for i in range(len(encrypted_message)):
                decrypted_byte = encrypted_message[i] ^ accumulated_keys[i]
                decrypted_message.append(decrypted_byte)

            md5_hash = hashlib.md5(decrypted_message).hexdigest()
            print("MD5 hash of original message:", md5_hash)

            self.nr_segments = self.total_segments
            self.update_progress()

            with open(file_path, "wb") as file:
                file.write(decrypted_message)

    # @asyncSlot()
    async def continuous_receive_file(self):
        while True:
            await self.receive_file()
        
    def start_asyncio_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def recv_loop(self):
        asyncio.create_task(self.continuous_receive_file())

    def send_loop(self):
        asyncio.create_task(self.send_file())
    
    async def show_async_message_box(self, msg_box):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, msg_box.exec_)
        return result

    async def show_async_file_dialog(self, dialog, caption, directory):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: dialog.getSaveFileName(None, caption, directory))
        return result


if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    app_close_event = asyncio.Event()
    app.aboutToQuit.connect(app_close_event.set)

    main_window = QKDTransferApp()
    main_window.show()

    loop.run_until_complete(app_close_event.wait())
    loop.close()