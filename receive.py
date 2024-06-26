from PyQt5.QtCore import QThread, pyqtSignal

class FileReceiverWorker(QThread):
    received_signal = pyqtSignal(str)

    def __init__(self, socket):
        super().__init__()
        self.socket = socket
        self.running = True

    def run(self):
        while self.running:
            # Receive the multipart message
            message_parts = self.socket.recv_multipart()
            # Extract the message content
            message = message_parts[-1].decode()
            self.received_signal.emit(message)

    def stop(self):
        self.running = False
