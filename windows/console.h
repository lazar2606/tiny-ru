#ifndef TINY_WINDOWS_CONSOLE_H
#define TINY_WINDOWS_CONSOLE_H
#include <stdio.h>
void tiny_win_init(int argc, char **argv);
int tiny_win_printf(const char *format, ...);
int tiny_win_putchar(int c);
int tiny_win_read_line(char *line, unsigned capacity);
FILE *tiny_win_open_model(const char *name);
#endif
