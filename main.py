import socket
import threading
from datetime import datetime
from urllib.parse import urlparse


class SimpleProxy:
    def __init__(self, host='127.0.0.1', port=8888):
        self.host = host
        self.port = port
        self.allowed_hosts = ['example.com', 'live.legendy.by']
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        print("======================================")
        print("       ПРОКСИ-СЕРВЕР")
        print("======================================")
        print(f"Сервер запущен на {self.host}:{self.port}")
        print("======================================")

    def run(self):
        try:
            while True:
                client_socket, addr = self.server_socket.accept()
                threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,),
                    daemon=True
                ).start()
        except KeyboardInterrupt:
            print("\n[!] Сервер остановлен")
            self.server_socket.close()

    def handle_client(self, client_socket):
        try:
            request = client_socket.recv(4096).decode('utf-8', errors='ignore')
            if not request:
                return

            # Парсим первую строку запроса
            first_line = request.split('\r\n')[0]
            parts = first_line.split()
            if len(parts) < 3:
                return
            method, url, version = parts

            # Определяем хост и порт
            if url.startswith('http://'):
                # Полный URL (клиент -> прокси)
                parsed = urlparse(url)
                host = parsed.hostname
                port = parsed.port if parsed.port else 80
                path = parsed.path if parsed.path else '/'
                modify_request = True
            else:
                # Относительный путь (клиент -> сервер напрямую)
                # Ищем хост в заголовках
                host = None
                for line in request.split('\r\n'):
                    if line.lower().startswith('host:'):
                        host_port = line.split(': ')[1].strip()
                        if ':' in host_port:
                            host, port_str = host_port.split(':')
                            port = int(port_str)
                        else:
                            host = host_port
                            port = 80
                        break
                if not host:
                    return
                path = url
                modify_request = False

            # Проверяем, нужно ли логировать этот запрос
            should_log = any(allowed_host in host for allowed_host in self.allowed_hosts)

            # Подключаемся к целевому серверу
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.settimeout(10)
                try:
                    server_socket.connect((host, port))
                except Exception as e:
                    print(f"[!] Ошибка подключения к {host}:{port}: {str(e)}")
                    return

                # Модифицируем запрос (если был полный URL)
                if modify_request:
                    # Заменяем полный URL на путь
                    modified_request = request.replace(url, path)
                else:
                    modified_request = request

                # Отправляем запрос
                server_socket.sendall(modified_request.encode())

                # Получаем и пересылаем ответ
                first_chunk = True
                while True:
                    try:
                        data = server_socket.recv(4096)
                        if not data:
                            break

                        client_socket.sendall(data)

                        # Логируем первый чанк данных
                        if should_log and first_chunk:
                            try:
                                response_str = data.decode('utf-8', errors='ignore')
                                status_line = response_str.split('\r\n')[0]
                                if 'HTTP/' in status_line:
                                    status_code = status_line.split()[1] if len(status_line.split()) > 1 else "???"
                                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {host}:{port}{path} - {status_code}")
                                    print("--------------------------------------")
                            except:
                                pass
                            first_chunk = False

                    except socket.timeout:
                        # Для потокового контента (как радио) просто продолжаем
                        if ':8000/legendyfm' in path:
                            continue
                        break
                    except Exception as e:
                        print(f"[!] Ошибка передачи данных: {str(e)}")
                        break

        except Exception as e:
            print(f"[!] Ошибка обработки запроса: {str(e)}")
        finally:
            client_socket.close()


if __name__ == '__main__':
    proxy = SimpleProxy()
    proxy.run()