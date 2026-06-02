import paho.mqtt.client as mqtt
import ssl
import threading
import time
import json

class MQTTClient:
    """MQTT Client mit Publisher und Subscriber Funktionalität (VERSION2)"""

    def __init__(self, broker, port=443, username=None, password=None, client_id=None):
        """
        Initialisiert den MQTT Client

        Args:
            broker: Broker-Host
            port: Broker-Port (default: 443) 8883 for vm
            username: MQTT-Benutzername (optional)
            password: MQTT-Passwort (optional)
            client_id: Client-ID (optional, wird automatisch generiert)
        """
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id

        # Message-Handler für verschiedene Topics
        self.message_callbacks = {}

        # Globaler Message-Handler
        self.on_message = None

        # Connection Status
        self._connected = False
        self._lock = threading.Lock()

        # Client erstellen mit VERSION2
        if client_id:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        else:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        self._setup_callbacks()
        self._setup_tls()

    def _setup_callbacks(self):
        """Registriert alle Callbacks"""
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message

    def _setup_tls(self):
        """TLS mit OS-Zertifikaten konfigurieren"""
        try:
            self.client.tls_set(
                ca_certs=None,
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None
            )
            self.client.tls_insecure = False
        except Exception as e:
            print(f"✗ Fehler beim TLS-Setup: {e}")
            raise

    def _on_connect(self, client, userdata, connect_flags, reason_code, properties):
        """Callback: Bei Verbindung (VERSION2)"""
        if reason_code == 0:
            with self._lock:
                self._connected = True
            print(f"✓ Verbunden mit {self.broker}:{self.port}")
        else:
            with self._lock:
                self._connected = False
            print(f"✗ Verbindungsfehler: Reason Code {reason_code}")
            self._print_error_code(reason_code)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """Callback: Bei Trennung (VERSION2)"""
        with self._lock:
            self._connected = False

        if reason_code != 0:
            print(f"✗ Unerwartete Trennung mit Code {reason_code}")
        else:
            print("✓ Verbindung beendet")

    def _on_publish(self, client, userdata, mid, reason_code, properties):
        """Callback: Bei Publikation (VERSION2)"""
        if reason_code == 0:
            print(f"✓ Message publiziert (MID: {mid})")
        else:
            print(f"✗ Publish fehlgeschlagen (MID: {mid}, Code: {reason_code})")

    def _on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        """Callback: Bei Subscription (VERSION2)"""
        print(f"✓ Subscribe erfolgreich (MID: {mid}, Reason Codes: {reason_code_list})")

    def _on_message(self, client, userdata, msg):
        """Callback: Bei empfangener Nachricht"""
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        qos = msg.qos

        print(f"\n:incoming_envelope: Nachricht empfangen:")
        print(f"   Topic: {topic}")
        print(f"   QoS: {qos}")
        print(f"   Payload: {payload}\n")

        # Topic-spezifischer Handler
        if topic in self.message_callbacks:
            try:
                self.message_callbacks[topic](topic, payload, qos)
            except Exception as e:
                print(f"✗ Fehler im Nachrichtenhandler: {e}")

        # Globaler Handler
        if self.on_message:
            try:
                self.on_message(topic, payload, qos)
            except Exception as e:
                print(f"✗ Fehler im globalen Nachrichtenhandler: {e}")

    def _print_error_code(self, reason_code):
        """Gibt aussagekräftige Fehlermeldung aus"""
        error_messages = {
            0: "Erfolg",
            1: "Unzulässige Protokollversion",
            2: "Ungültiger Client-Identifier",
            3: "Server nicht verfügbar",
            4: "Fehlerhafte Anmeldedaten",
            5: "Nicht autorisiert",
        }
        if reason_code in error_messages:
            print(f"   Grund: {error_messages[reason_code]}")

    def is_connected(self):
        """Prüft, ob Client verbunden ist"""
        with self._lock:
            return self._connected

    def connect(self):
        """Verbindet mit dem Broker"""
        try:
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            print(f"Verbinde zu {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()

            # Warten auf erfolgreiche Verbindung
            for _ in range(50):  # max 5 Sekunden
                if self.is_connected():
                    return True
                time.sleep(0.1)

            print("✗ Verbindung konnte nicht hergestellt werden")
            return False

        except Exception as e:
            print(f"✗ Verbindungsfehler: {e}")
            return False

    def disconnect(self):
        """Trennt die Verbindung"""
        self.client.loop_stop()
        self.client.disconnect()
        time.sleep(0.5)

    def publish(self, topic, message, qos=1, retain=False):
        """
        Publiziert eine Nachricht

        Args:
            topic: MQTT Topic
            message: Nachricht
            qos: Quality of Service (0, 1, 2)
            retain: Nachricht behalten (default: False)

        Returns:
            True bei Erfolg, False bei Fehler
        """
        if not self.is_connected():
            print("✗ Nicht verbunden mit Broker")
            return False

        try:
            result, mid = self.client.publish(topic, message, qos=qos, retain=retain)
            if result != mqtt.MQTT_ERR_SUCCESS:
                print(f"✗ Publish fehlgeschlagen: {result.rc}")
                return False
            return True

        except Exception as e:
            print(f"✗ Fehler beim Publizieren: {e}")
            return False

    def subscribe(self, topic, qos=1, callback=None):
        """
        Abonniert ein Topic

        Args:
            topic: MQTT Topic (unterstützt Wildcards: + und #)
            qos: Quality of Service (0, 1, 2)
            callback: Optionale Callback-Funktion für dieses Topic
                     Signatur: callback(topic, payload, qos)

        Returns:
            True bei Erfolg, False bei Fehler
        """
        if not self.is_connected():
            print("✗ Nicht verbunden mit Broker")
            return False

        try:
            result, mid = self.client.subscribe(topic, qos=qos)
            if result != mqtt.MQTT_ERR_SUCCESS:
                print(f"✗ Subscribe fehlgeschlagen: {result.rc}")
                return False

            # Callback registrieren, falls vorhanden
            if callback:
                self.message_callbacks[topic] = callback

            print(f"✓ Abonniert: {topic}")
            return True

        except Exception as e:
            print(f"✗ Fehler beim Subscribe: {e}")
            return False

    def unsubscribe(self, topic):
        """
        Beendet ein Abo

        Args:
            topic: MQTT Topic

        Returns:
            True bei Erfolg, False bei Fehler
        """
        if not self.is_connected():
            print("✗ Nicht verbunden mit Broker")
            return False

        try:
            result, mid = self.client.unsubscribe(topic)

            if result != mqtt.MQTT_ERR_SUCCESS:
                print(f"✗ Unsubscribe fehlgeschlagen: {result.rc}")
                return False

            # Callback entfernen
            if topic in self.message_callbacks:
                del self.message_callbacks[topic]

            print(f"✓ Abo beendet: {topic}")
            return True

        except Exception as e:
            print(f"✗ Fehler beim Unsubscribe: {e}")
            return False

    def subscribe_multiple(self, topics):
        """
        Abonniert mehrere Topics

        Args:
            topics: Liste von Tuples (topic, qos, callback)
                   Beispiel: [("topic1", 1, callback1), ("topic2", 1, None)]

        Returns:
            True wenn alle erfolgreich, False sonst
        """
        all_success = True

        for topic_config in topics:
            if len(topic_config) == 2:
                topic, qos = topic_config
                callback = None
            else:
                topic, qos, callback = topic_config

            if not self.subscribe(topic, qos, callback):
                all_success = False

        return all_success

    def get_version(self):
        """Gibt Versionsinformationen zurück"""
        return {
            "api_version": "VERSION2",
            "library_version": mqtt.__version__,
            "broker": self.broker,
            "port": self.port,
            "connected": self.is_connected()
        }

def handle_json_data(topic, payload, qos):
    """Parst und verarbeitet JSON-Daten"""
    try:
        data = json.loads(payload)
        print(f"JSON-Daten: {data}")
    except json.JSONDecodeError:
        print(f"Ungültiges JSON: {payload}")

def handle_status(topic, payload, qos):
    """Verarbeitet Status-Nachrichten"""
    if payload == "online":
        print("✓ System ist online")
    elif payload == "offline":
        print("✗ System ist offline")

if __name__ == "__main__":
    client = MQTTClient(
        broker="mqtt.farmspt.ai.edvsz.hs-osnabrueck.de",
        port=8883,
        username="herstellera",
        password="password"
    )

    if client.connect():
        # Mehrere Handler registrieren
        client.subscribe("/data/herstellera/sensors/json", callback=handle_json_data)
        client.subscribe("/data/herstellera/status", callback=handle_status)
        client.subscribe("/data/herstellera/debug")  # Ohne spezifischen Handler

        # Test-Daten publizieren
        client.publish("/data/herstellera/sensors/json", '{"temp": 23.5, "humidity": 45}')
        client.publish("/data/herstellera/status", "online")
        client.publish("/data/herstellera/debug", "Debug-Nachricht")
        client.publish("/data/herstellera/test", "Test-Nachricht")

        try:
            print("Laufe... (Strg+C zum Beenden)")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nBeende...")
            client.disconnect()