"""Command-line interface for QKD file transfer.

This Click-based CLI mirrors the GUI application and allows users to list
connected clients, send files to a peer and wait in standby mode for incoming
files.  The underlying logic of the GUI workers is reused so no changes to the
core implementation are required.
"""

import os
import sys
import time
import signal
from typing import Tuple

import click
import zmq
from PyQt5.QtCore import QCoreApplication, QTimer

# Ensure relative imports find configuration and helper modules.
SCRIPT_DIR = os.path.dirname(__file__)
os.chdir(SCRIPT_DIR)

from receive import FileReceiverWorker  # noqa: E402
from send import FileSendWorker  # noqa: E402

qkdgkt_path = os.path.abspath(os.path.join(SCRIPT_DIR, 'QKD-Infra-GetKey'))
sys.path.append(qkdgkt_path)
import qkdgkt  # noqa: E402

try:  # pragma: no cover - Python <3.11
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

# Prefer a user-provided ``config.toml`` but fall back to the bundled sample
# configuration so the application can still run out of the box.  This allows
# overriding the broker settings without modifying repository files.
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.toml')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config_sample.toml')
with open(CONFIG_PATH, 'rb') as cfg_file:
    CONFIG = tomllib.load(cfg_file)


def _connect(broker_host: str, broker_port: int, name: str) -> Tuple[zmq.Context, zmq.Socket, str]:
    """Register with the broker and return a connected socket."""

    location = qkdgkt.qkd_get_myself()
    context = zmq.Context()
    socket = context.socket(zmq.DEALER)
    socket.connect(f"tcp://{broker_host}:{broker_port}")

    socket.send_string(f"register:{name}/{location}")
    reply = socket.recv_string()
    if reply != "ok":
        msg = f"Failed to register: {reply}"
        raise RuntimeError(msg)

    return context, socket, location


@click.group()
def cli() -> None:
    """QKD file transfer command-line utilities."""


@cli.command('list-clients')
@click.option('--broker-host', default=CONFIG['broker']['host'],
              show_default=True, help='Broker host')
@click.option('--broker-port', default=CONFIG['broker']['port'], type=int,
              show_default=True, help='Broker port')
@click.option('--name', required=True, help='Client name')
def list_clients(broker_host: str, broker_port: int, name: str) -> None:
    """List clients registered with the broker."""

    _context, socket, _ = _connect(broker_host, broker_port, name)
    socket.send_string('list_clients')
    parts = socket.recv_multipart()
    if parts and parts[0].decode() == 'list_clients':
        clients = parts[1].decode().split('|') if len(parts) > 1 else []
        click.echo('Connected clients:')
        for client in clients:
            click.echo(f'- {client}')
    else:
        click.echo('No client information received')

    _context.term()


@cli.command()
@click.argument('peer')
@click.option('--file', 'file_path', type=click.Path(exists=True, dir_okay=False),
              prompt='File to transfer', help='Path to the file to transfer')
@click.option('--broker-host', default=CONFIG['broker']['host'],
              show_default=True, help='Broker host')
@click.option('--broker-port', default=CONFIG['broker']['port'], type=int,
              show_default=True, help='Broker port')
@click.option('--name', required=True, help='Client name')
def run(peer: str, file_path: str, broker_host: str, broker_port: int, name: str) -> None:
    """Transfer ``file`` to the selected ``peer``."""

    context, socket, location = _connect(broker_host, broker_port, name)

    dest_location = None
    notified = False
    while dest_location is None:
        socket.send_string('list_clients')
        parts = socket.recv_multipart()
        clients = parts[1].decode().split('|') if len(parts) > 1 else []

        for entry in clients:
            client_name, client_loc = entry.split('/')
            if client_name == peer:
                dest_location = client_loc
                break

        if dest_location is None:
            if not notified:
                click.echo('PEER NOT CONNECTED, STANDBY')
                notified = True
            time.sleep(1)

    click.echo('PEER CONNECTED, YOU CAN PROCEED')
    input('Press Enter to begin transmission...')

    app = QCoreApplication([])

    receiver = FileReceiverWorker(socket, location)
    sender = FileSendWorker(socket)

    receiver.signal_received_ack.connect(sender.handle_ack)

    sender.signal_start_progress.connect(
        lambda t, c: click.echo(f'Starting {t} with {c}'))
    sender.signal_update_progress.connect(
        lambda n, tot: click.echo(f'Progress: {n}/{tot}'))
    sender.signal_end_progress.connect(lambda: QTimer.singleShot(0, app.quit))

    receiver.signal_start_progress.connect(
        lambda t, c: click.echo(f'Receiving {t} from {c}'))
    receiver.signal_end_progress.connect(
        lambda: click.echo('Reception complete'))
    receiver.signal_end_progress.connect(
        lambda: QTimer.singleShot(0, app.quit))

    receiver.start()
    sender.start()

    sender.add_file(peer, file_path, location, dest_location)

    app.exec_()

    sender.stop()
    receiver.stop()
    context.term()
    sender.wait()
    receiver.wait()
    sys.exit(0)


@cli.command('standby')
@click.option('--broker-host', default=CONFIG['broker']['host'],
              show_default=True, help='Broker host')
@click.option('--broker-port', default=CONFIG['broker']['port'], type=int,
              show_default=True, help='Broker port')
@click.option('--name', required=True, help='Client name')
def standby(broker_host: str, broker_port: int, name: str) -> None:
    """Register and wait for incoming transmissions."""

    context, socket, location = _connect(broker_host, broker_port, name)

    app = QCoreApplication([])

    click.echo('Entering standby mode. Waiting for incoming transmissions...')

    def _start_receiver() -> FileReceiverWorker:
        worker = FileReceiverWorker(socket, location)
        worker.signal_start_progress.connect(
            lambda t, c: click.echo(f'Receiving {t} from {c}'))
        worker.signal_update_progress.connect(
            lambda n, tot: click.echo(f'Progress: {n}/{tot}'))
        worker.signal_end_progress.connect(lambda: QTimer.singleShot(0, app.quit))
        worker.start()
        return worker

    receiver = _start_receiver()

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    try:
        while True:
            try:
                app.exec_()
            except KeyboardInterrupt:
                break

            click.echo('Reception complete')
            if click.confirm('Exit standby mode?', default=False):
                break
            receiver = _start_receiver()
    finally:
        receiver.stop()
        context.term()
        receiver.wait()


if __name__ == '__main__':
    cli()
