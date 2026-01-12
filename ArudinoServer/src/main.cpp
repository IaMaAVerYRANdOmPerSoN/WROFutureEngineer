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

#define MOTOR_A      7   // motor pin a
#define MOTOR_B      8   // motor pin b
#define MOTOR_ENABLE 9   // Enable (also PWM pin)

#define STEERING_PWM 12 // Servo PWM

L293D motor(MOTOR_A, MOTOR_B, MOTOR_ENABLE);
Servo steering;

class Server {
    private:
        Stream* _serial;
        Hashtable<String, Request> CurrentProcesses;
        SimpleVector<String> commands;
        L293D& _motor;
        Servo& _steering;

        Request parseRequest() {
            Request req = {0, "", 0, 0, 0, 0, 1};
            
            if (_serial->available()) {
                String line = _serial->readStringUntil('\n');
                char serialBuff[32] = {0};
                char arg1Buff[32] = {0};
                char arg2Buff[32] = {0};

                req.count = sscanf(line.c_str(), "%d %31s %31s %31s", &req.tid, serialBuff, arg1Buff, arg2Buff);
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
            else if (request.command == "DRIVE_MOTORS") {
                unsigned long duration = (unsigned long)(fabs(request.arg2) * 1000.0f + 0.5f);
                request.timeout = millis() + duration;
                _serial->println(prefix + "WAITMS " + String(duration));
                _motor.SetMotorSpeed(request.arg1); // Speed passed in percent
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
            else if (request.command == "M_ANGLE") {
                request.timeout = 0;
                request.processed = 1;
                end("M_ANGLE");
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
            } else if (command == "DRIVE_MOTORS") {
                _motor.Stop();
                digitalWrite(5, LOW);
                _serial->println(prefix + "200 OK");
            } else if (command == "SET_LED") {
                // Keep the led's current state
                _serial->println(prefix + "200 OK");
            } else if (command == "SERVO_ANGLE") {
                _serial->println(prefix + _steering.read());
            }else if (command == "M_ANGLE") {
                _serial->println(prefix + _motor.GetCurrentMotorSpeed());
            } else if (command == "404 ERR") {
                digitalWrite(10, LOW);
            }
        }
        
    public:
        Server(Stream& s, L293D& motor, Servo& steering) : _serial(&s), _motor(motor), _steering(steering) {
            commands.push_back("PING");
            commands.push_back("SET_SERVO");
            commands.push_back("INC_SERVO");
            commands.push_back("DRIVE_MOTORS");
            commands.push_back("SET_LED");
            commands.push_back("SERVO_ANGLE");
            commands.push_back("M_ANGLE");
        }

    void ProcessRequest() {
        Request incoming = parseRequest();
        if (incoming.tid != 0) {
            if (CurrentProcesses[incoming.command].processed == 0) {
                end(incoming.command);
            }
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

    //L293D
    pinMode(MOTOR_A, OUTPUT);
    pinMode(MOTOR_B, OUTPUT);

    Serial.begin(115200);
    motor.begin(true);
    steering.attach(STEERING_PWM);
    server = new Server(Serial, motor, steering);
}

void loop() {
    server->ProcessRequest();
}