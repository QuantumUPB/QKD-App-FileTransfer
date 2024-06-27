import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QTreeView, QFileSystemModel, QProgressBar, QStatusBar, QFrame, QMessageBox
)
from PyQt5.QtCore import QTimer, QTime
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QComboBox

from receive import FileReceiverWorker
from send import FileSendWorker

import asyncio
import sys
import os

qkdgkt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'QKD-Infra-GetKey'))
sys.path.append(qkdgkt_path)
import qkdgkt

import zmq

class QKDTransferApp(QWidget):
    def __init__(self):
        self.sending = None
        self.config = qkdgkt.qkd_get_config()
        self.locations = qkdgkt.qkd_get_locations()
        self.client_list = []
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

        self.port_label = QLabel('Port:')
        self.port_field = QLineEdit('5555') 

        # name label and field
        self.name_label = QLabel('Name:')
        self.name_field = QLineEdit('Alice')

        # dropdown select location of client
        self.location_label = QLabel('Location:')
        self.location_dropdown = QComboBox()
        self.location_dropdown.addItems(self.locations)
        # find the index of myname
        myloc = qkdgkt.qkd_get_myself()
        myloc_index = self.locations.index(myloc)
        self.location_dropdown.setCurrentIndex(myloc_index)

        self.connect_button = QPushButton('Connect')
        self.connect_button.clicked.connect(self.connect_to_server)

        # Layout for connection screen
        self.connection_layout = QVBoxLayout()
        self.connection_layout.addWidget(self.message_label)
        self.connection_layout.addWidget(self.ip_label)
        self.connection_layout.addWidget(self.ip_field)
        self.connection_layout.addWidget(self.port_label)
        self.connection_layout.addWidget(self.port_field)
        self.connection_layout.addWidget(self.name_label)
        self.connection_layout.addWidget(self.name_field)
        self.connection_layout.addWidget(self.location_label)
        self.connection_layout.addWidget(self.location_dropdown)
        self.connection_layout.addWidget(self.connect_button)

        # Add connection layout to main layout
        self.main_layout.addLayout(self.connection_layout)

    def update_client_list(self):
        self.socket.send_string("list_clients")
    
    @pyqtSlot(str)
    def handle_updated_client_list(self, reply):
        client_list = reply.split("|")
        print("Connected clients:", client_list)
        self.client_list = [client.split("/") for client in client_list]
        self.client_dropdown.clear()
        self.client_dropdown.addItems([client[0] for client in self.client_list if client[0] != self.client_name])

    def connect_to_server(self):
        # make connect button disabled
        self.connect_button.setEnabled(False)
        self.repaint()

        # Placeholder for connection logic
        ip = self.ip_field.text()
        port = int(self.port_field.text())
        self.location = self.location_dropdown.currentText()
                   
        # Here you would add the actual connection logic using ip and port
        print(f"Connecting to {ip}:{port}...")

        self.client_name = self.name_field.text()
        self.context = zmq.Context()

        # Create a DEALER socket to communicate with the broker
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.connect(f"tcp://{ip}:{port}")

        self.socket.send_string(f"register:{self.client_name}/{self.location}")
        reply = self.socket.recv_string()
        if reply == "ok":
            print(f"Registered as {self.client_name}")
        else:
            print(f"Failed to register: {reply}")

        self.update_client_list()

        # Start the file receiver worker
        self.file_receiver_worker = FileReceiverWorker(self.socket, self.location)
        self.file_receiver_worker.signal_list_clients.connect(self.handle_updated_client_list)
        self.file_receiver_worker.signal_start_progress.connect(self.start_progress)
        self.file_receiver_worker.signal_update_progress.connect(self.update_progress)
        self.file_receiver_worker.signal_end_progress.connect(self.end_progress)
        self.file_receiver_worker.start()

        # Start the file send worker
        self.file_send_worker = FileSendWorker(self.socket)
        self.file_send_worker.signal_start_progress.connect(self.start_progress)
        self.file_send_worker.signal_update_progress.connect(self.update_progress)
        self.file_send_worker.signal_end_progress.connect(self.end_progress)
        self.file_send_worker.start()

        # # If connection is successful, proceed to the main interface
        self.switch_to_main_interface()

    @pyqtSlot(str, list)
    def handle_received_data(self, from_name, message_parts):
        pass

    def closeEvent(self, event):
        if hasattr(self, 'file_send_worker'):
            self.file_send_worker.stop()
        if hasattr(self, 'file_receiver_worker'):
            self.file_receiver_worker.stop()
        event.accept()

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

        # button to refresh client list
        self.refresh_button = QPushButton('Refresh Client List')
        self.refresh_button.clicked.connect(self.update_client_list)

        # dropdown select client to send file to
        self.client_label = QLabel('Send to:')
        self.client_dropdown = QComboBox()

        self.send_button = QPushButton('SEND')
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.add_sending_file)

        self.instructions_label = QLabel('<b>Send and Receive:</b>')
        self.listening_label = QLabel('Listening for incoming files...')

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage('Ready')

        self.right_layout.addWidget(self.instructions_label)
        self.right_layout.addWidget(self.refresh_button)
        self.right_layout.addWidget(self.client_label)
        self.right_layout.addWidget(self.client_dropdown)
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

    def update_timer(self):
        elapsed_time = int(self.start_time.elapsed() / 1000)
        self.status_bar.showMessage(f'Sending file [{elapsed_time // 60 :02d}:{(elapsed_time % 60):02d} elapsed]')

    @pyqtSlot(int, int)
    def update_progress(self, nr_segments, total_segments):
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

    @pyqtSlot()
    def start_progress(self):
        #  file sending and update progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage('Sending file...')
        self.listening_label.setVisible(False)
        self.start_time = QTime.currentTime()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(100)  # Update progress every 100ms

    @pyqtSlot()
    def end_progress(self):
        self.progress_bar.setValue(100)
        self.status_bar.showMessage('File sent successfully!')
        self.progress_bar.setVisible(False)

    def add_sending_file(self):
        # get selected client
        selected_client = self.client_dropdown.currentText()
        client_location = [client[1] for client in self.client_list if client[0] == selected_client][0]
        self.file_send_worker.add_file(selected_client, self.selected_file_path, self.location, client_location)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = QKDTransferApp()
    sys.exit(app.exec_())
