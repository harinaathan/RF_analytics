#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include <WebSocketsServer.h>
#include "esp_wifi.h"

const char* ssid = "LungFi";
const char* password = "LH/RH_3Lobe";

IPAddress local_IP(192, 168, 4, 1);
IPAddress gateway(192, 168, 4, 1);
IPAddress subnet(255, 255, 255, 0);

AsyncWebServer server(80);
WebSocketsServer webSocket = WebSocketsServer(81);

void setup() {
  Serial.begin(115200);
  WiFi.softAP(ssid, password);
  WiFi.softAPConfig(local_IP, gateway, subnet);

  IPAddress IP = WiFi.softAPIP();
  Serial.print("AP IP address: ");
  Serial.println(IP);

  webSocket.begin();
  webSocket.onEvent(onWebSocketEvent);

  server.begin();
}

void onWebSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  String message = "";
  String command = "";
  if (type == WStype_TEXT) {
    Serial.printf("[%u] Received: %s\n", num, payload);
    // casewise
    command = String((char*)payload);
    if (command.startsWith("SETPOWER:")) {
      int powerLevel = command.substring(9).toInt();
      WiFi.setTxPower((wifi_power_t)powerLevel);
      delay(50);
      int8_t currentPowerLevel;
      esp_wifi_get_max_tx_power(&currentPowerLevel);
      message = "TX_POWER:" + String(currentPowerLevel);
      for (int i = 0; i < webSocket.connectedClients(); i++) {
        webSocket.sendTXT(i, message);
      }
      Serial.printf("acknowledged power setting to %d\n",powerLevel);
    } else if (command.startsWith("DATA:") || (command.startsWith("RENAME:"))) {
      for (int i = 0; i < webSocket.connectedClients(); i++) {
        if (i == num) {
          continue;
        }
        webSocket.sendTXT(i, command);
      }
      Serial.println("broadcasted data");
    } else if (command.startsWith("TEST:")) {
      message = "ACKNOWLEDGED" + String((char*)payload);
      for (int i = 0; i < webSocket.connectedClients(); i++) {
        webSocket.sendTXT(i, message);
      }
      Serial.println("acknowledged test request");
    } else {
      // Broadcast the received message to all other connected clients
      message = "Client " + String(num) + " says: " + String((char*)payload);
      for (int i = 0; i < webSocket.connectedClients(); i++) {
        if (i == num) {
          continue;
        }
        webSocket.sendTXT(i, message);
      }
    }
  }
}

void loop() {
  webSocket.loop();
}