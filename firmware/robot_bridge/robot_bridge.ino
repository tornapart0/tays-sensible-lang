

#include <Arduino.h>
#include <driver/gpio.h>
#include <esp_arduino_version.h>

#if !CONFIG_IDF_TARGET_ESP32S3
#error "Select an ESP32-S3 board"
#endif
#if ESP_ARDUINO_VERSION_MAJOR < 3
#error "Install Arduino-ESP32 3.x or newer"
#endif

enum Role { FREE, INPUT_PIN, DIGITAL_PIN, PWM_PIN, SERVO_PIN, MOTOR_PIN };
Role roles[49] = {};
int channels[49];
bool usedChannels[8] = {};
int leftPins[3] = {-1, -1, -1};
int rightPins[3] = {-1, -1, -1};
int leftPower = 0, rightPower = 0;
bool motorsReady = false;
bool outputsActive = false;
uint32_t lastOutput = 0;
const uint32_t WATCHDOG_MS = 500;
char buffer[128];
size_t bufferLength = 0;
bool overflowed = false;

bool usable(int pin) {

  return GPIO_IS_VALID_OUTPUT_GPIO(pin) &&
    ((pin >= 1 && pin <= 18 && pin != 3) ||
     (pin >= 38 && pin <= 42) || pin == 47);
}

void error(const char *message) {
  Serial.printf("{\"ok\":false,\"error\":\"%s\"}\n", message);
}

void ok() { Serial.println("{\"ok\":true}"); }

void refreshed() {
  lastOutput = millis();
  outputsActive = true;
}

void stopOutputs() {
  for (int pin = 0; pin < 49; ++pin) {
    if (channels[pin] >= 0) ledcWrite(pin, 0);
    else if (roles[pin] == DIGITAL_PIN || roles[pin] == MOTOR_PIN) digitalWrite(pin, LOW);
  }
  leftPower = rightPower = 0;
  outputsActive = false;
}

bool claim(int pin, Role role) {
  if (!usable(pin)) { error("GPIO unavailable in S3 profile"); return false; }
  if (roles[pin] != FREE && roles[pin] != role) {
    error("GPIO role conflict; release it first"); return false;
  }
  return true;
}

bool attachOutput(int pin, Role role) {
  if (!claim(pin, role)) return false;
  if (roles[pin] == role) return true;

  int first = role == PWM_PIN ? 2 : 4;
  int end = role == PWM_PIN ? 4 : 8;
  for (int channel = first; channel < end; ++channel) {
    if (usedChannels[channel]) continue;
    int frequency = role == PWM_PIN ? 20000 : 50;
    int resolution = role == PWM_PIN ? 8 : 14;
    if (!ledcAttachChannel(pin, frequency, resolution, channel)) {
      error("PWM attach failed"); return false;
    }
    usedChannels[channel] = true;
    channels[pin] = channel;
    roles[pin] = role;
    return true;
  }
  error("No free channels for requested role");
  return false;
}

void setMotor(const int *pins, int power) {

  ledcWrite(pins[0], 0);
  digitalWrite(pins[1], LOW);
  digitalWrite(pins[2], LOW);
  delayMicroseconds(50);
  if (power > 0) digitalWrite(pins[1], HIGH);
  if (power < 0) digitalWrite(pins[2], HIGH);
  ledcWrite(pins[0], abs(power));
}

void configureMotors(int *pins) {
  if (motorsReady) {
    for (int i = 0; i < 6; ++i) {
      if (pins[i] != (i < 3 ? leftPins[i] : rightPins[i - 3])) {
        error("Motors already configured; reset board to change"); return;
      }
    }
    stopOutputs(); ok(); return;
  }
  for (int i = 0; i < 6; ++i) {
    if (!usable(pins[i]) || roles[pins[i]] != FREE) { error("Motor GPIO unavailable"); return; }
    for (int j = 0; j < i; ++j) {
      if (pins[i] == pins[j]) { error("Duplicate motor GPIO"); return; }
    }
  }

  if (!ledcAttachChannel(pins[0], 20000, 8, 0)) { error("Left PWM attach failed"); return; }
  if (!ledcAttachChannel(pins[3], 20000, 8, 1)) {
    ledcDetach(pins[0]); error("Right PWM attach failed"); return;
  }
  channels[pins[0]] = 0;
  channels[pins[3]] = 1;
  usedChannels[0] = usedChannels[1] = true;
  for (int i = 0; i < 6; ++i) {
    roles[pins[i]] = MOTOR_PIN;
    if (i % 3 != 0) {
      digitalWrite(pins[i], LOW);
      pinMode(pins[i], OUTPUT);
    }
    if (i < 3) leftPins[i] = pins[i];
    else rightPins[i - 3] = pins[i];
  }
  motorsReady = true;
  stopOutputs();
  ok();
}

void handle(char *command) {
  int pin, value, a, b, pins[6];
  char extra;
  if (strcmp(command, "INFO") == 0) {
    Serial.printf("{\"ok\":true,\"protocol\":1,\"board\":\"esp32-s3\",\"motors_ready\":%s,\"watchdog_ms\":500,\"motor_pins\":[%d,%d,%d,%d,%d,%d]}\n",
                  motorsReady ? "true" : "false", leftPins[0], leftPins[1], leftPins[2],
                  rightPins[0], rightPins[1], rightPins[2]);
  } else if (strcmp(command, "STOP") == 0) {
    stopOutputs(); ok();
  } else if (strcmp(command, "READ") == 0) {

    Serial.printf("{\"ok\":true,\"time_s\":%.3f,\"left\":%.4f,\"right\":%.4f,\"sensor_raw\":null}\n",
                  millis() / 1000.0, leftPower / 255.0, rightPower / 255.0);
  } else if (sscanf(command, "MOTORS %d %d %d %d %d %d %c", &pins[0], &pins[1], &pins[2], &pins[3], &pins[4], &pins[5], &extra) == 6) {
    configureMotors(pins);
  } else if (sscanf(command, "DRIVE %d %d %c", &a, &b, &extra) == 2) {
    if (!motorsReady) { error("Configure motors first"); return; }
    if (a < -255 || a > 255 || b < -255 || b > 255) { error("Motor power out of range"); return; }
    setMotor(leftPins, a); setMotor(rightPins, b);
    leftPower = a; rightPower = b; refreshed(); ok();
  } else if (sscanf(command, "WRITE %d %d %c", &pin, &value, &extra) == 2) {
    if (value != 0 && value != 1) { error("Digital value must be 0 or 1"); return; }
    if (!claim(pin, DIGITAL_PIN)) return;
    digitalWrite(pin, LOW); pinMode(pin, OUTPUT); digitalWrite(pin, value);
    roles[pin] = DIGITAL_PIN; refreshed(); ok();
  } else if (sscanf(command, "DIGITAL %d %d %c", &pin, &value, &extra) == 2) {
    if (value != 0 && value != 1) { error("Pullup must be 0 or 1"); return; }
    if (!claim(pin, INPUT_PIN)) return;
    pinMode(pin, value ? INPUT_PULLUP : INPUT); roles[pin] = INPUT_PIN;
    Serial.printf("{\"ok\":true,\"value\":%d}\n", digitalRead(pin));
  } else if (sscanf(command, "ANALOG %d %c", &pin, &extra) == 1) {
    if (!usable(pin) || pin > 10) { error("Use ADC1 GPIO 1-10 excluding 3"); return; }
    if (!claim(pin, INPUT_PIN)) return;
    pinMode(pin, INPUT); roles[pin] = INPUT_PIN;
    Serial.printf("{\"ok\":true,\"value\":%d}\n", analogRead(pin));
  } else if (sscanf(command, "PWM %d %d %c", &pin, &value, &extra) == 2) {
    if (value < 0 || value > 255) { error("PWM out of range"); return; }
    if (!attachOutput(pin, PWM_PIN)) return;
    ledcWrite(pin, value); refreshed(); ok();
  } else if (sscanf(command, "SERVO %d %d %c", &pin, &value, &extra) == 2) {
    if (value < 500 || value > 2500) { error("Servo pulse out of range"); return; }
    if (!attachOutput(pin, SERVO_PIN)) return;
    ledcWrite(pin, (uint32_t(value) * 16383 + 10000) / 20000);
    refreshed(); ok();
  } else if (sscanf(command, "RELEASE %d %c", &pin, &extra) == 1) {
    if (!usable(pin) || roles[pin] == MOTOR_PIN) { error("GPIO unavailable or reserved for motor"); return; }
    if (channels[pin] >= 0) {
      ledcWrite(pin, 0); ledcDetach(pin);
      usedChannels[channels[pin]] = false; channels[pin] = -1;
    }
    pinMode(pin, INPUT); roles[pin] = FREE; ok();
  } else {
    error("Unknown or malformed command");
  }
}

void setup() {
  for (int pin = 0; pin < 49; ++pin) channels[pin] = -1;
  Serial.begin(115200);
}

void loop() {
  if (outputsActive && uint32_t(millis() - lastOutput) >= WATCHDOG_MS) stopOutputs();

  for (int count = 0; count < 64 && Serial.available(); ++count) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (overflowed) { stopOutputs(); error("Command too long"); }
      else if (bufferLength) { buffer[bufferLength] = '\0'; handle(buffer); }
      bufferLength = 0; overflowed = false;
    } else if (!overflowed) {
      if (bufferLength < sizeof(buffer) - 1) buffer[bufferLength++] = c;
      else overflowed = true;
    }
  }
}
