#include <assert.h>
#include "../../firmware/robot_bridge/robot_bridge.ino"
void command(const char *text) {
  char data[128]; snprintf(data, sizeof(data), "%s", text);
  Serial.output[0] = '\0'; handle(data);
}
int main() {
  setup();
  command("SERVO 19 1500");
  assert(strstr(Serial.output, "false") != nullptr);
  command("SERVO 10 1500");
  assert(duties[10] > 1000 && frequencies[pinChannels[10]] == 50);
  command("PWM 11 128");
  assert(duties[11] == 128 && frequencies[pinChannels[11]] == 20000);
  assert(frequencies[pinChannels[10]] == 50);
  command("MOTORS 4 5 6 7 8 9");
  assert(motorsReady);
  command("DRIVE 128 -128");
  assert(duties[4] == 128 && duties[7] == 128 && levels[5] == HIGH && levels[9] == HIGH);
  command("SERVO 10 1500");
  command("WRITE 12 1");
  clockMs = 499; loop();
  assert(duties[4] == 128);
  clockMs = 500; loop();
  assert(duties[4] == 0 && duties[7] == 0 && duties[10] == 0 && levels[12] == LOW);
  command("WRITE 4 1");
  assert(strstr(Serial.output, "false") != nullptr);
  command("DRIVE 999 0");
  assert(strstr(Serial.output, "false") != nullptr && duties[4] == 0);
  command("MOTORS 4 5 6 7 8 9");
  assert(strstr(Serial.output, "true") != nullptr);
  command("READ");
  assert(strstr(Serial.output, "\"sensor_raw\":null") != nullptr);
  puts("Firmware logic checks passed (mock GPIO/serial)");
}
