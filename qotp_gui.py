import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QTreeView, QFileSystemModel, QProgressBar, QStatusBar, QFrame, QMessageBox
)
from PyQt5.QtCore import QTimer, QTime
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

import subprocess
import json
import time
import asyncio
import hashlib
import socket
import threading
import sys
from tqdm import tqdm

import sys
import signal

import numpy as np
import os

import threading

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
        self.sending = None
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

        self.instructions_label = QLabel('<b>Send and Receive:</b>')
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

        # create an about section in the right layout
        # configure about section
        self.about_layout = QVBoxLayout()
        # bold title label
        self.about_label = QLabel('<b>QKD Unconditionally Secure File Transfer</b>')
        self.about_label.setWordWrap(True)
        self.about_layout.addWidget(self.about_label)
        # add two logos to about section
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap("Logo.png").scaled(200, 200, Qt.KeepAspectRatio))
        self.logo2 = QLabel()
        self.logo2.setPixmap(QPixmap("upb.png").scaled(100, 100, Qt.KeepAspectRatio))
        self.logo_layout = QHBoxLayout()
        self.logo_layout.addWidget(self.logo)
        self.logo_layout.addWidget(self.logo2)
        self.about_layout.addLayout(self.logo_layout)
        self.about_label_website = QLabel('<a href="https://quantum.upb.ro/">Visit Website</a>')
        self.about_label_website.setOpenExternalLinks(True)
        self.about_label_github = QLabel('<a href="https://github.com/QuantumUPB/QKD-App-FileTransfer">GitHub Repository</a>')
        self.about_label_github.setOpenExternalLinks(True)
        self.about_layout.addWidget(self.about_label_website)
        self.about_layout.addWidget(self.about_label_github)
        self.about_layout.addStretch(1)
        # fix about section width
        self.about_label.setFixedWidth(400)

        # Add about section to right layout
        self.right_layout.addLayout(self.about_layout)
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
            message = 'File sent successfully!' if self.sending else 'File received successfully!'
            self.status_bar.showMessage(message)
            self.progress_bar.setVisible(False)
        else:
            self.status_bar.showMessage(f'Sending file [{elapsed_time // 60 :02d}:{(elapsed_time % 60):02d} elapsed]')

    async def send_file(self):
        async with lock:
            self.sending=True
            print(f"Sending file: {self.selected_file_path}")

            #  file sending and update progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_bar.showMessage('Sending file...')

            # hide the "listening for incoming files" label
            self.listening_label.setVisible(False)

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
                    output = qkdgkt.qkd_get_key_custom_params('UPB-AP-UPBC', '141.85.241.65:12443', 'upb-ap.crt', 'qkd.key', 'qkd-ca.crt', 'pgpopescu', 'Request')
                    print(output)
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

            # re-show the "listening for incoming files" label
            self.listening_label.setVisible(True)

            print("MD5 Hash of original message:", hashlib.md5(message).hexdigest())

    def receive_file(self):
        self.sending=False
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

        # async with lock:
        if True:
            print("Lock acquired")
            # open pyqt5 dialog to confirm receive

            # confirm = QMessageBox()
            # confirm.setIcon(QMessageBox.Question)
            # confirm.setText(f"Receive file {file_path} of {msg_len} bytes?")
            # confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            # confirm.setDefaultButton(QMessageBox.Yes)
            # response = confirm.exec_()
            # print(response)
            # if response == QMessageBox.No:
            #     client_socket.send(bytes("reject", 'utf-8'))
            #     client_socket.close()
            #     return
            
            # open pyqt5 dialog to select save location

            # file_path = QFileDialog.getSaveFileName(None, "Save File", file_path)[0]
            # if not file_path:
            #     client_socket.send(bytes("reject", 'utf-8'))
            #     client_socket.close()
            #     return
            
            remaining_len = msg_len
            seg_no = int(np.ceil(msg_len / seg_length))
            self.total_segments = seg_no
            self.nr_segments = 0

            #  file sending and update progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_bar.showMessage('Receiving file...')

            self.start_time = QTime.currentTime()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_progress)
            self.timer.start(100)  # Update progress every 100ms

            # hide the "listening for incoming files" label
            self.listening_label.setVisible(False)

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
                        output = qkdgkt.qkd_get_key_custom_params('UPB-AP-UPBP', '141.85.241.65:22443', 'upb-ap.crt', 'qkd.key', 'qkd-ca.crt', 'pgpopescu', 'Response', key_id)
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

            # re-show the "listening for incoming files" label
            self.listening_label.setVisible(True)

            with open(file_path, "wb") as file:
                file.write(decrypted_message)

    def continuous_receive_file(self):
        while True:
            try:
                self.receive_file()
            except Exception as e:
                print(f"Error occurred: {str(e)}")
                continue

    def start_receive_file_thread(self):
        # Create a thread to run the `receive_file` method
        receive_thread = threading.Thread(target=self.continuous_receive_file)
        receive_thread.start()

    def start_send_file_thread(self):
        # Create a thread to run the `send_file` method
        send_thread = threading.Thread(target=self.send_file)
        send_thread.start()
        
    def start_asyncio_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def recv_loop(self):
        # loop = asyncio.new_event_loop()
        # threading.Thread(target=self.start_asyncio_loop, args=(loop,), daemon=True).start()
        # # Schedule the continuous_receive_file function to run in the asyncio event loop
        # asyncio.run_coroutine_threadsafe(self.continuous_receive_file(), loop)
        self.start_receive_file_thread()

    def send_loop(self):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.send_file())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = QKDTransferApp()
    sys.exit(app.exec_())
