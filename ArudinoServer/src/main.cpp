#include <Arduino.h>
#include <math.h>
#include <Hashtable.h>
#include <L293D.h>
#include <Servo.h>

struct Request {
    int tid;
    String command;
    float arg1;
    float arg2;
    int count;
    unsigned long timeout;
    int processed;
};

#define MOTOR 9   // Motor PWM
#define STEERING_PWM 11 // Servo PWM
#define SERIAL_TIMEOUT 10 // Serial read timeout in milliseconds

Servo steering;
Servo motor;

class Server {
    private:
        Stream* _serial;
        Hashtable<String, Request> CurrentProcesses;
        SimpleVector<String> commands;
        Servo& _motor;
        Servo& _steering;

        Request parseRequest() {
            Request req = {0, "", 0, 0, 0, 0, 1};
            
            if (_serial->available()) {
                String line = _serial->readStringUntil('\n');
                line.trim();
                if (line.length() == 0) {
                    return req;
                }
                char serialBuff[32] = {0};
                char arg1Buff[32] = {0};
                char arg2Buff[32] = {0};

                req.count = sscanf(line.c_str(), "%d %31s %31s %31s", &req.tid, serialBuff, arg1Buff, arg2Buff);
                if (req.count < 2) {
                    req.tid = 0;
                    return req;
                }
                req.command = String(serialBuff);
                if (req.count >= 3) {
                    req.arg1 = atof(arg1Buff);
                }
                if (req.count >= 4) {
                    req.arg2 = atof(arg2Buff);
                }
                req.processed = 0;
            }
            return req;
        }

        void start(Request& request) {
            String prefix = String(request.tid) + " ";

            if (request.command == "PING") {
                request.timeout = 0;
                request.processed = 1;
                digitalWrite(2, HIGH);
                end("PING");
            } 
            else if (request.command == "SET_SERVO") {
                unsigned int current_angle = _steering.read();
                unsigned long duration = fabs(request.arg1 - current_angle);
                request.timeout = millis() + duration;
                _serial->println(prefix + "WAITMS " + String(duration));
                _steering.write(request.arg1);
                digitalWrite(3, HIGH);
            } 
            else if (request.command == "INC_SERVO") {
                unsigned long duration = (unsigned long)(request.arg1);
                request.timeout = millis() + duration;
                _serial->println(prefix + "WAITMS " + String(duration));
                _steering.write(_steering.read() + request.arg1);
                digitalWrite(4, HIGH);
            }
            else if (request.command == "SET_MOTOR") {
                unsigned long duration = (unsigned long)(fabs(request.arg2) * 1000.0f + 0.5f);
                request.timeout = millis() + duration;
                _serial->println(prefix + "WAITMS " + String(duration));
                _motor.writeMicroseconds(1500 + (int)(request.arg1 * 500.0f / 100.0f)); // Speed passed in percent
                digitalWrite(5, HIGH);
            }
            else if (request.command == "SET_LED") {
                request.timeout = 0;
                request.processed = 1;
                if (request.arg1 > 1e-6) {
                    digitalWrite(6, HIGH);
                } else {
                    digitalWrite(6, LOW); // Only 1 is on
                }
                end("SET_LED");
            } 
            else if (request.command == "SERVO_ANGLE") {
                request.timeout = 0;
                request.processed = 1;
                end("SERVO_ANGLE");
            }
            else {
                digitalWrite(10, HIGH);
                _serial->println(prefix + "404 ERR");
                end("404 ERR");
            }
        }

        void end(String command) {
            Request& request = CurrentProcesses[command];
            String prefix = String(request.tid) + " ";

            if (command == "PING") {
                _serial->println(prefix + "PONG");
                digitalWrite(2, LOW);
            } else if (command == "SET_SERVO") {
                digitalWrite(3, LOW);
                _serial->println(prefix + "200 OK");
            } else if (command == "INC_SERVO") {
                digitalWrite(4, LOW);
                _serial->println(prefix + "200 OK");
            } else if (command == "SET_MOTOR") {
                _motor.writeMicroseconds(1500); // Stop the motor
                digitalWrite(5, LOW);
                _serial->println(prefix + "200 OK");
            } else if (command == "SET_LED") {
                // Keep the led's current state
                _serial->println(prefix + "200 OK");
            } else if (command == "SERVO_ANGLE") {
                _serial->println(prefix + _steering.read());
            } else if (command == "404 ERR") {
                digitalWrite(10, LOW);
            }
        }
        
    public:
        Server(Stream& s, Servo& motor, Servo& steering) : _serial(&s), _motor(motor), _steering(steering) {
            commands.push_back("PING");
            commands.push_back("SET_SERVO");
            commands.push_back("INC_SERVO");
            commands.push_back("SET_MOTOR");
            commands.push_back("SET_LED");
            commands.push_back("SERVO_ANGLE");
            commands.push_back("M_ANGLE");
        }

    void ProcessRequest() {
        Request incoming = parseRequest();
        if (incoming.tid != 0) {
            CurrentProcesses[incoming.command] = incoming;
            start(CurrentProcesses[incoming.command]);
        }

        for (unsigned int i = 0; i < commands.size(); i++) {
            String cmd = commands[i];
            Request& req = CurrentProcesses[cmd];
            
            if (req.timeout != 0 && req.processed == 0 && millis() >= req.timeout) {
                end(cmd);
                req.processed = 1; 
            }
        }
    }
};

Server* server;

void setup() {
    // these are all LEDs for testing
    pinMode(2, OUTPUT);
    pinMode(3, OUTPUT);
    pinMode(4, OUTPUT);
    pinMode(5, OUTPUT);
    pinMode(6, OUTPUT);
    pinMode(10, OUTPUT);

    Serial.begin(115200);
    Serial.setTimeout(SERIAL_TIMEOUT); // Keep parser responsive when lines arrive in chunks.
    steering.attach(STEERING_PWM);
    motor.attach(MOTOR);
    motor.writeMicroseconds(1500); // Stop the motor
    delay(1000); // give the motor some time to stop before accepting commands
    server = new Server(Serial, motor, steering);
}

void loop() {
    server->ProcessRequest();
}