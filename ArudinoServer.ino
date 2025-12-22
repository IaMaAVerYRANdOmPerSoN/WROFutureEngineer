#include <regex>

void setup() {
    Serial.begin(115200);
}

void loop() {
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        
        if (line.startsWith("SET_SERVO") || 
            line.startsWith("INC_SERVO") || 
            line.startsWith("DRIVE_MOTORS") || 
            line.startsWith("SET_LED")) {
            Serial.println("200 OK");
        } else if (line.length() > 0) {
            Serial.println("400 ERROR");
        }
    }
}