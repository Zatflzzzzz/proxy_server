import socket
import threading
from urllib.parse import urlparse
import re
from datetime import datetime


class Proxy:
    BUFFER = 8192
    HOST = '127.0.0.1'
    PORT = 8888
    ALLOWED_HOSTS = ['example.com', 'live.legendy.by']

    @classmethod
    def start(cls):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((cls.HOST, cls.PORT))
            listener.listen(5)

            print("======================================")
            print("       ПРОКСИ-СЕРВЕР                  ")
            print("======================================")
            print(f"Сервер запущен на {cls.HOST}:{cls.PORT}")
            print("======================================")

            try:
                while True:
                    client_sock, _ = listener.accept()
                    thread = threading.Thread(target=cls.listen, args=(client_sock,))
                    thread.daemon = True
                    thread.start()
            except KeyboardInterrupt:
                print("\n[!] Сервер остановлен")

    @classmethod
    def listen(cls, client_sock):
        with client_sock:
            client_stream = client_sock.makefile('rwb', buffering=0)
            http_request = cls.receive(client_stream)
            if http_request:
                cls.response(client_stream, http_request)

    @classmethod
    def receive(cls, stream):
        data = bytearray()
        while True:
            chunk = stream.read(cls.BUFFER)
            if not chunk:
                break
            data.extend(chunk)

            if b'\r\n\r\n' in data:
                break
        return bytes(data)

    @classmethod
    def response(cls, client_stream, http_request):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            request_str = http_request.decode('utf-8', errors='ignore')
            host = None
            ip_end = cls.get_end_point(request_str, host)
            host = ip_end[0]

            message = cls.get_relative_path(request_str)
            full_url = cls.get_full_url(request_str, host)

            server_sock.connect(ip_end)
            server_stream = server_sock.makefile('rwb', buffering=0)

            server_stream.write(message.encode('utf-8'))
            http_response = cls.receive(server_stream)

            client_stream.write(http_response)
            cls.output_response(http_response, full_url)

            while True:
                data = server_stream.read(cls.BUFFER)
                if not data:
                    break
                client_stream.write(data)

        except Exception as e:
            print(f"[!] Ошибка: {str(e)}")
        finally:
            server_sock.close()

    @classmethod
    def get_full_url(cls, request, host):
        lines = request.split('\n')
        if not lines:
            return host

        parts = lines[0].split()
        if len(parts) < 2:
            return host

        path = parts[1]
        if path.startswith(('http://', 'https://')):
            return path.split()[0]

        return f"http://{host}{path}"

    @classmethod
    def get_relative_path(cls, message):

        pattern = re.compile(r'http://[a-z0-9а-я\.:]*', re.IGNORECASE)
        match = pattern.search(message)
        if match:
            host = match.group()
            return message.replace(host, "")
        return message

    @classmethod
    def get_end_point(cls, request, host):

        pattern = re.compile(r'Host: (((?P<host>.+?):(?P<port>\d+?))|(?P<host2>.+?))\s+',
                             re.MULTILINE | re.IGNORECASE)
        match = pattern.search(request)

        if match:
            host = match.group('host') or match.group('host2')
            port = int(match.group('port')) if match.group('port') else 80
        else:

            parts = request.split()
            if len(parts) >= 2 and parts[1].startswith('http://'):
                parsed = urlparse(parts[1])
                host = parsed.hostname
                port = parsed.port if parsed.port else 80
            else:
                raise ValueError("Could not determine host from request")


        ip_host = socket.gethostbyname(host)
        return (ip_host, port)

    @classmethod
    def output_response(cls, http_response, url):
        try:
            response_str = http_response.decode('utf-8', errors='ignore')
            buf_response = response_str.split('\r\n')
            if buf_response:
                status_line = buf_response[0]
                code = status_line.split()[1] if len(status_line.split()) > 1 else "???"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {url} - {code}")
                print("--------------------------------------")
        except Exception as e:
            print(f"[!] Ошибка вывода ответа: {str(e)}")

    @classmethod
    def load_error_page(cls, client_stream, host):
        try:
            with open('error_page.html', 'rb') as file_stream:
                buf_error_page = file_stream.read()
                error = f"HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\nContent-Length: {len(buf_error_page)}\r\n\r\n<p>{host}"
                error_page = error.encode('utf-8') + buf_error_page
                client_stream.write(error_page)
        except Exception as e:
            print(f"[!] Ошибка загрузки страницы ошибки: {str(e)}")


if __name__ == '__main__':
    Proxy.start()