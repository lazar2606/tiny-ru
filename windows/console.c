/* Windows Unicode console/UTF-8 streams around the shared CP866 neural core. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <io.h>
#include <fcntl.h>
#include "console.h"

static HANDLE input_handle, output_handle;
static int console_input, console_output, skip_lf, first_file_line = 1;
static UINT input_codepage;
static WCHAR console_buffer[256];
static DWORD console_length, console_position;

void tiny_win_init(int argc, char **argv)
{
    DWORD mode;
    int i;
    input_handle = GetStdHandle(STD_INPUT_HANDLE);
    output_handle = GetStdHandle(STD_OUTPUT_HANDLE);
    console_input = GetConsoleMode(input_handle, &mode) != 0;
    console_output = GetConsoleMode(output_handle, &mode) != 0;
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
    for (i = 1; i < argc; i++) {
        if (_stricmp(argv[i], "/CP866") == 0) input_codepage = 866;
        if (_stricmp(argv[i], "/CP1251") == 0) input_codepage = 1251;
        if (_stricmp(argv[i], "/UTF8") == 0) input_codepage = CP_UTF8;
    }
}

static int write_wide(const WCHAR *text, DWORD count)
{
    DWORD written, offset = 0;
    int bytes;
    char *utf8;
    if (console_output) {
        WCHAR *cooked = (WCHAR *)malloc(((size_t)count * 2 + 1) * sizeof(WCHAR));
        DWORD i, cooked_count = 0;
        if (!cooked) return -1;
        for (i = 0; i < count; i++) {
            if (text[i] == L'\n' && (!i || text[i - 1] != L'\r')) cooked[cooked_count++] = L'\r';
            cooked[cooked_count++] = text[i];
        }
        while (offset < cooked_count) {
            if (!WriteConsoleW(output_handle, cooked + offset, cooked_count - offset, &written, NULL) || !written) {
                free(cooked);
                return -1;
            }
            offset += written;
        }
        free(cooked);
        return 0;
    }
    bytes = WideCharToMultiByte(CP_UTF8, 0, text, (int)count, NULL, 0, NULL, NULL);
    if (bytes <= 0) return -1;
    utf8 = (char *)malloc((size_t)bytes);
    if (!utf8) return -1;
    WideCharToMultiByte(CP_UTF8, 0, text, (int)count, utf8, bytes, NULL, NULL);
    while (offset < (DWORD)bytes) {
        if (!WriteFile(output_handle, utf8 + offset, (DWORD)bytes - offset, &written, NULL) || !written) {
            free(utf8);
            return -1;
        }
        offset += written;
    }
    free(utf8);
    return 0;
}

static int write_cp866(const char *text, int count)
{
    WCHAR local[2048], *wide = local;
    int length, result;
    if (!count) return 0;
    length = MultiByteToWideChar(866, 0, text, count, NULL, 0);
    if (length <= 0) return -1;
    if (length > (int)(sizeof(local) / sizeof(local[0]))) {
        wide = (WCHAR *)malloc((size_t)length * sizeof(WCHAR));
        if (!wide) return -1;
    }
    MultiByteToWideChar(866, 0, text, count, wide, length);
    result = write_wide(wide, (DWORD)length);
    if (wide != local) free(wide);
    return result;
}

int tiny_win_printf(const char *format, ...)
{
    char local[2048], *text = local;
    int count, result;
    va_list args;
    va_start(args, format);
    count = vsnprintf(local, sizeof(local), format, args);
    va_end(args);
    if (count < 0) return -1;
    if (count >= (int)sizeof(local)) {
        text = (char *)malloc((size_t)count + 1);
        if (!text) return -1;
        va_start(args, format);
        vsnprintf(text, (size_t)count + 1, format, args);
        va_end(args);
    }
    result = write_cp866(text, count);
    if (text != local) free(text);
    return result < 0 ? -1 : count;
}

int tiny_win_putchar(int c)
{
    char byte = (char)c;
    return write_cp866(&byte, 1) < 0 ? EOF : (unsigned char)c;
}

static int console_character(void)
{
    if (console_position == console_length) {
        if (!ReadConsoleW(input_handle, console_buffer, 256, &console_length, NULL) || !console_length)
            return EOF;
        console_position = 0;
    }
    return console_buffer[console_position++];
}

static int wide_to_core(const WCHAR *wide, int count, char *line, unsigned capacity)
{
    int needed;
    if (!count) { line[0] = 0; return 1; }
    needed = WideCharToMultiByte(866, WC_NO_BEST_FIT_CHARS, wide, count, NULL, 0, "?", NULL);
    if (needed <= 0 || (unsigned)needed >= capacity) { line[0] = 0; return -1; }
    WideCharToMultiByte(866, WC_NO_BEST_FIT_CHARS, wide, count, line, needed, "?", NULL);
    line[needed] = 0;
    return 1;
}

int tiny_win_read_line(char *line, unsigned capacity)
{
    char raw[4096];
    WCHAR wide[4096];
    unsigned count = 0;
    int c, overflow = 0, length;
    UINT cp;
    for (;;) {
        c = console_input ? console_character() : fgetc(stdin);
        if (skip_lf) {
            skip_lf = 0;
            if (c == '\n') continue;
        }
        if (c == EOF || c == 26) {
            if (!count && !overflow) { line[0] = 0; return 0; }
            break;
        }
        if (c == '\r' || c == '\n') { skip_lf = c == '\r'; break; }
        if (count < 4095) {
            if (console_input) wide[count++] = (WCHAR)c;
            else raw[count++] = (char)c;
        } else overflow = 1;
    }
    if (overflow) { line[0] = 0; return -1; }
    if (console_input) return wide_to_core(wide, (int)count, line, capacity);
    if (first_file_line && count >= 3 && memcmp(raw, "\xef\xbb\xbf", 3) == 0) {
        memmove(raw, raw + 3, count - 3); count -= 3;
    }
    first_file_line = 0;
    if (!count) { line[0] = 0; return 1; }
    cp = input_codepage ? input_codepage : CP_UTF8;
    length = MultiByteToWideChar(cp, cp == CP_UTF8 ? MB_ERR_INVALID_CHARS : 0,
                                 raw, (int)count, wide, 4096);
    if (!length && !input_codepage) {
        cp = GetConsoleCP();
        if (!cp) cp = GetOEMCP();
        length = MultiByteToWideChar(cp, 0, raw, (int)count, wide, 4096);
    }
    if (!length) { line[0] = 0; return -1; }
    return wide_to_core(wide, length, line, capacity);
}

FILE *tiny_win_open_model(const char *name)
{
    WCHAR path[32768];
    DWORD length = GetModuleFileNameW(NULL, path, 32768), base;
    int count;
    if (!length || length >= 32768) return NULL;
    base = length;
    while (base && path[base - 1] != L'\\' && path[base - 1] != L'/') base--;
    count = MultiByteToWideChar(866, 0, name, -1, path + base, (int)(32768 - base));
    if (!count) return NULL;
    return _wfopen(path, L"rb");
}
