#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ESP32Ping.h>
#include <esp_heap_caps.h>

// Function to print free heap memory
void printHeapStatus() {
  Serial.print("Free heap: ");
  Serial.println(ESP.getFreeHeap());
  Serial.print("Largest free block: ");
  Serial.println(heap_caps_get_largest_free_block(MALLOC_CAP_8BIT));
  Serial.print("Total free blocks: ");
  Serial.println(heap_caps_get_free_size(MALLOC_CAP_8BIT));
}

const char* ssid = "LungFi";  // SSID of the first ESP32
const char* password = "LH/RH_3Lobe";  // Password of the first ESP32

WebSocketsClient webSocket;
IPAddress remote_ip(192, 168, 4, 1);

unsigned long lastTime = 0;
unsigned long timerDelay = 500;  // delay setting

long rtt = 0;
long rssi = 0;
int setPowerLevel = 0;
int powerLevels[] = {82, 70, 60, 50, 40, 30, 20, 10};

int ws_conn_test_success = 0;

String material_name = "<unknown>";

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      Serial.println("Disconnected!");
      break;
    case WStype_CONNECTED:
      Serial.println("Connected to server");
      webSocket.sendTXT("Hello from ESP32 Client");
      break;
    case WStype_TEXT:
      Serial.printf("Received: %s\n", payload);
      String reply = String((char*)payload);
      if (reply.startsWith("TX_POWER:")) {
        setPowerLevel = reply.substring(9).toInt();
        Serial.printf("updated setPowerLevel = %d\n",setPowerLevel);
      } else if (reply.startsWith("ACKNOWLEDGED")) {
        ws_conn_test_success += 1;
        Serial.printf("updated ws_conn_test_success = %d\n",ws_conn_test_success);
      } else if (reply.startsWith("RENAME:")) {
        material_name = reply.substring(7);
        Serial.printf("updated material_name = %s\n",material_name);
      }
      break;
  }
  printHeapStatus();
}

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }

  Serial.println("Connected to WiFi");

  webSocket.begin("192.168.4.1", 81, "/");  // IP address of the first ESP32
  webSocket.onEvent(webSocketEvent);

  printHeapStatus();
}

void loop() {
  webSocket.loop();

  String message = "";

  // Reconnect if disconnected
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected, reconnecting...");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
      delay(1000);
      Serial.println("Reconnecting to WiFi...");
    }
    Serial.println("Reconnected to WiFi");
    webSocket.begin("192.168.4.1", 81, "/");  // Reconnect WebSocket
  }

  // Send a message every 2 seconds
  if ((millis() - lastTime) > timerDelay) {
    message = "TEST: WebSocket test message sent @ ";
    message += String(millis());
    webSocket.sendTXT(message);
    Serial.println(message);
    lastTime = millis();
    webSocket.loop();
  }

  // run tests
  if (ws_conn_test_success >= 5) {
    for (int i = 0; i < sizeof(powerLevels) / sizeof(powerLevels[0]); i++) {

      // send power level command
      setPowerLevel = 0;
      message = "SETPOWER:" + String(powerLevels[i]);
      webSocket.sendTXT(message);
      Serial.println("COMMAND:" + message);
      
      // wait for acknowledgement
      while (setPowerLevel == 0) {
        Serial.println("awaiting power setting acknowledgment");
        webSocket.loop();
      }

      // test data
      rssi = WiFi.RSSI();
      if (Ping.ping(remote_ip, 1)) {
        rtt = Ping.averageTime();
      } else {
        rtt = -1;
        ws_conn_test_success = 0; // reset connection success metric
      }

      // broadcast data
      message = "DATA: TIMESTAMP:" + String(millis()) + " ms\t";
      message += "MATERIAL:" + material_name + "\t";
      message += "Power: " + String(setPowerLevel) + " dBm\t";
      message += "RTT: " + String(rtt) + " ms\t";
      message += "RSSI: " + String(rssi) + " dBm\n";
      webSocket.sendTXT(message);
      webSocket.loop();
      Serial.println("SHARED:" + message);

      // relay to serial monitor / plotter
      Serial.print("POWER:");
      Serial.print(setPowerLevel);
      Serial.print(", RTT:");
      Serial.print(rtt);
      Serial.print(", RSSI:");
      Serial.println(rssi);
    }
  }
  printHeapStatus();
}