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
        Hashtable<String, Request> currentProcesses;
        SimpleVector<String> commands;
        Servo& _motor;
        Servo& _steering;
        unsigned int _last_packet_time = millis();

        Request parseRequest() {
            Request req = {0, "", 0, 0, 0, 0, 1};
            
            if (_serial->available()) {
                _last_packet_time = millis();
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
                end("PING");
            } 
            else if (request.command == "SET_SERVO") {
                unsigned int current_angle = _steering.read();
                unsigned long duration = fabs(request.arg1 - current_angle);
                request.timeout = millis() + duration;
                _serial->println(prefix + "WAITMS " + String(duration));
                _steering.write(request.arg1);
            } 
            else if (request.command == "INC_SERVO") {
                unsigned long duration = (unsigned long)(request.arg1);
                request.timeout = millis() + duration;
                _serial->println(prefix + "WAITMS " + String(duration));
                _steering.write(_steering.read() + request.arg1);
            }
            else if (request.command == "SET_MOTOR") {
                unsigned long duration = (unsigned long)(fabs(request.arg2) * 1000.0f + 0.5f);
                request.timeout = millis() + duration;
                _serial->println(prefix + "WAITMS " + String(duration));
                _motor.writeMicroseconds(1500 + (int)(request.arg1 * 300.0f / 100.0f)); // Speed passed in percent
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
                _serial->println(prefix + "404 ERR");
                end("404 ERR");
            }
        }

        void end(String command) {
            Request& request = currentProcesses[command];
            String prefix = String(request.tid) + " ";

            if (command == "PING") {
                _serial->println(prefix + "PONG");
            } else if (command == "SET_SERVO") {
                _serial->println(prefix + "200 OK");
            } else if (command == "INC_SERVO") {
                _serial->println(prefix + "200 OK");
            } else if (command == "SET_MOTOR") {
                _motor.writeMicroseconds(1500); // Stop the motor
                _serial->println(prefix + "200 OK");
            } else if (command == "SET_LED") {
                // Keep the led's current state
                _serial->println(prefix + "200 OK");
            } else if (command == "SERVO_ANGLE") {
                _serial->println(prefix + _steering.read());
            } else if (command == "404 ERR") {}
        }
        
    public:
        Server(Stream& s, Servo& motor, Servo& steering) : _serial(&s), _motor(motor), _steering(steering) {
            commands.push_back("PING");
            commands.push_back("SET_SERVO");
            commands.push_back("INC_SERVO");
            commands.push_back("SET_MOTOR");
            commands.push_back("SET_LED");
            commands.push_back("SERVO_ANGLE");
        }

        void processRequest() {
            Request incoming = parseRequest();
            if (incoming.tid != 0) {
                currentProcesses[incoming.command] = incoming;
                start(currentProcesses[incoming.command]);
            }

            for (auto &cmd : commands) {
                Request& req = currentProcesses[cmd];
                
                if (req.timeout != 0 && req.processed == 0 && millis() >= req.timeout) {
                    end(cmd);
                    req.processed = 1; 
                }
            }
        }
        
        bool isIdle(unsigned int idleTime) {
            return (millis() - _last_packet_time) > idleTime;
        }

        void stop() {
            for (auto &cmd : commands) {
                end(cmd);
            }
            currentProcesses.clear();
        }
};

Server* server;

void setup() {
    pinMode(6, OUTPUT); // LED

    Serial.begin(115200);
    Serial.setTimeout(SERIAL_TIMEOUT); // Keep parser responsive when lines arrive in chunks.
    steering.attach(STEERING_PWM);
    motor.attach(MOTOR);
    motor.writeMicroseconds(1500); // Stop the motor
    delay(1000); // give the motor some time to stop before accepting commands
    server = new Server(Serial, motor, steering);
}

void loop() {
    server->processRequest();
    if (server->isIdle(40)) { // 30fps is 33ms, so 40ms is a safe threshold for idle detection
        server->stop();
    }
}


/*#include <Arduino.h>
#include <Servo.h>

#define STEERING_PWM 11 // Servo PWM

Servo steering;

void setup() {
    steering.attach(STEERING_PWM);
    steering.write(90);
}

void loop() {}*/
