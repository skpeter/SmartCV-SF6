from zeroconf import Zeroconf, ServiceInfo
import socket
import time

def register_instance():
    zeroconf = Zeroconf()
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)

    service_type = "_smartcv._tcp.local."
    service_name = f"{hostname}.{service_type}"
    service_port = 6500 # do not change this

    info = ServiceInfo(
        type_=service_type,
        name=service_name,
        port=service_port,
        properties={"device": hostname},
        server=f"{hostname}.local.",
    )

    print(f"Registering SmartCV instance {service_name} at {ip}:{service_port}")
    zeroconf.register_service(info)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        zeroconf.unregister_service(info)
        zeroconf.close()

if __name__ == "__main__": #for testing only
    register_instance()
