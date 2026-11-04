import errno
import socket
import unittest
from unittest.mock import patch
from app import bind_server
from http.server import BaseHTTPRequestHandler

class PortTests(unittest.TestCase):
    def test_occupied_port_falls_back_to_actual_available_port(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1',0)); occupied.listen()
            port=occupied.getsockname()[1]
            server=bind_server(BaseHTTPRequestHandler,port)
            try: self.assertNotEqual(server.server_port,port)
            finally:server.server_close()

    def test_permission_denied_falls_back_but_other_errors_do_not(self):
        sentinel=object()
        with patch('app.ThreadingHTTPServer',side_effect=[OSError(errno.EACCES,'denied'),sentinel]) as factory:
            self.assertIs(bind_server(BaseHTTPRequestHandler,48371),sentinel)
            self.assertEqual(factory.call_args.args[0],('127.0.0.1',0))
        with patch('app.ThreadingHTTPServer',side_effect=OSError(errno.EIO,'failure')):
            with self.assertRaises(OSError):bind_server(BaseHTTPRequestHandler,48371)

    def test_invalid_port(self):
        for port in (-1,65536):
            with self.assertRaises(ValueError):bind_server(BaseHTTPRequestHandler,port)
