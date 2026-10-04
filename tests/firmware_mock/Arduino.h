#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>
#define CONFIG_IDF_TARGET_ESP32S3 1
#define LOW 0
#define HIGH 1
#define OUTPUT 1
#define INPUT 0
#define INPUT_PULLUP 2
inline uint32_t clockMs = 0;
inline int levels[49] = {};
inline uint32_t duties[49] = {};
inline uint32_t frequencies[8] = {};
inline int pinChannels[49];
inline uint32_t millis() { return clockMs; }
inline void delayMicroseconds(int) {}
inline void pinMode(int, int) {}
inline void digitalWrite(int pin, int value) { levels[pin] = value; }
inline int digitalRead(int pin) { return levels[pin]; }
inline int analogRead(int) { return 1234; }
inline bool ledcAttachChannel(int pin, uint32_t freq, int, int channel) {
  pinChannels[pin] = channel; frequencies[channel] = freq; return true;
}
inline bool ledcWrite(int pin, uint32_t duty) { duties[pin] = duty; return true; }
inline bool ledcDetach(int pin) { duties[pin] = 0; pinChannels[pin] = -1; return true; }
struct SerialMock {
  char output[8192] = {};
  void begin(int) {}
  int available() { return 0; }
  char read() { return '\n'; }
  void println(const char *text) { strcat(output, text); strcat(output, "\n"); }
  void printf(const char *format, ...) {
    char text[512]; va_list args; va_start(args, format);
    vsnprintf(text, sizeof(text), format, args); va_end(args); strcat(output, text);
  }
};
inline SerialMock Serial;
