ESP32 TTS Example — POST base64 and play MP3

Overview

This example shows how an ESP32 can send base64-encoded UTF-8 Amharic text to the server's `/tts_b64` endpoint, save the returned MP3 to SPIFFS (or SD), then play it with `AudioGeneratorMP3`. It avoids character-encoding issues by sending base64.

Requirements

- ESP32 board
- SPIFFS or SD available for saving MP3 (SPIFFS example shown)
- Libraries:
  - `WiFi` (built-in)
  - `HTTPClient` (built-in)
  - `FS` and `SPIFFS` (or `SD`)
  - `Audio` libraries such as `ESP32-audioI2S` / `ESP8266Audio` port: `AudioGeneratorMP3`, `AudioFileSourceSPIFFS`, `AudioOutputI2S`

Steps

1. Upload the following sketch to ESP32 (adjust WiFi and server IP):

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include "SPIFFS.h"

#include "AudioGeneratorMP3.h"
#include "AudioFileSourceSPIFFS.h"
#include "AudioOutputI2S.h"

const char* ssid = "YOUR_SSID";
const char* password = "YOUR_PASS";
const char* server_url = "http://192.168.1.100:5000/tts_b64"; // change to your server

AudioGeneratorMP3 *mp3;
AudioFileSourceSPIFFS *file;
AudioOutputI2S *out;

void setup(){
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  if(!SPIFFS.begin(true)){
    Serial.println("SPIFFS begin failed");
    return;
  }

  // Base64-encoded UTF-8 Amharic text for "ሰላም ዓለም"
  String b64 = "4Yiw4YiL4YidIOGLk+GIiOGInQ==";

  // Prepare JSON
  String payload = "{\"b64\":\"" + b64 + "\"}";

  HTTPClient http;
  http.begin(server_url);
  http.addHeader("Content-Type", "application/json");

  int httpCode = http.POST(payload);
  if(httpCode == 200){
    WiFiClient *stream = http.getStreamPtr();
    // Save response to file
    const char *filename = "/tts.mp3";
    File f = SPIFFS.open(filename, FILE_WRITE);
    if(!f){
      Serial.println("Failed to open file for writing");
    } else {
      Serial.println("Saving MP3 to " + String(filename));
      uint8_t buf[512];
      while(http.connected() && stream->available()){
        int len = stream->read(buf, sizeof(buf));
        if(len > 0) f.write(buf, len);
      }
      f.close();
      Serial.println("Saved MP3");

      // Play saved file
      file = new AudioFileSourceSPIFFS(filename);
      out = new AudioOutputI2S(0, 1); // default I2S pins
      mp3 = new AudioGeneratorMP3();
      mp3->begin(file, out);
      while(mp3->isRunning()){
        mp3->loop();
        delay(10);
      }
      mp3->stop();
      Serial.println("Playback finished");
    }
  } else {
    Serial.printf("POST failed, code: %d\n", httpCode);
  }
  http.end();
}

void loop(){
  // nothing
}
```

Notes

- Replace `server_url` with your server IP reachable by the ESP32.
- If you prefer streaming without saving to SPIFFS, you can adapt the code to feed `AudioGeneratorMP3` from a memory buffer or to use `AudioFileSourceHTTPStream` if you switch to GET.
- For production use, handle retries, timeouts, and errors more robustly.

Alternative: Use GET with query (small payloads)

If your text is short you can encode the base64 into a URL-safe query param and GET `/tts_b64?b64=...`. This lets `AudioFileSourceHTTPStream` directly stream and play without saving.

Security

- Consider TLS (HTTPS) for production.
- Limit allowed clients or add authentication if the device is on an open network.
