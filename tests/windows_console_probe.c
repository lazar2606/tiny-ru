/* Test the actual wide-character console path in a separate hidden console. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

static int type_line(HANDLE input, const WCHAR *text)
{
    INPUT_RECORD events[512];
    DWORD count = 0, written;
    while (*text && count + 2 <= 512) {
        ZeroMemory(&events[count], sizeof(INPUT_RECORD));
        events[count].EventType = KEY_EVENT;
        events[count].Event.KeyEvent.bKeyDown = TRUE;
        events[count].Event.KeyEvent.wRepeatCount = 1;
        events[count].Event.KeyEvent.uChar.UnicodeChar = *text;
        events[count].Event.KeyEvent.wVirtualKeyCode = *text == L'\r' ? VK_RETURN : 0;
        events[count + 1] = events[count];
        events[count + 1].Event.KeyEvent.bKeyDown = FALSE;
        count += 2; text++;
    }
    return WriteConsoleInputW(input, events, count, &written) && written == count;
}

static WCHAR *screen(HANDLE output, DWORD *width, DWORD *rows)
{
    CONSOLE_SCREEN_BUFFER_INFO info;
    COORD start = {0, 0};
    DWORD length, got;
    WCHAR *text;
    if (!GetConsoleScreenBufferInfo(output, &info)) return NULL;
    *width = info.dwSize.X;
    *rows = (DWORD)info.dwCursorPosition.Y + 2;
    if (*rows > (DWORD)info.dwSize.Y) *rows = info.dwSize.Y;
    length = *width * *rows;
    text = (WCHAR *)calloc((size_t)length + 1, sizeof(WCHAR));
    if (!text) return NULL;
    if (!ReadConsoleOutputCharacterW(output, text, length, start, &got)) { free(text); return NULL; }
    text[got] = 0;
    return text;
}

int wmain(int argc, WCHAR **argv)
{
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    HANDLE input = INVALID_HANDLE_VALUE, output = INVALID_HANDLE_VALUE;
    WCHAR command[32768], windows_directory[MAX_PATH], *text = NULL;
    DWORD width = 0, rows = 0, code = 1, started, error = 0;
    int ok = 0;
    FILE *report;
    const WCHAR *question = L"\u043a\u0442\u043e \u043f\u0440\u0435\u0437\u0438\u0434\u0435\u043d\u0442 \u0440\u043e\u0441\u0441\u0438\u0438?\r";
    const WCHAR *answer = L"\u0432\u043b\u0430\u0434\u0438\u043c\u0438\u0440 \u043f\u0443\u0442\u0438\u043d";
    const WCHAR *title = L"\u0440\u0443\u0441\u0441\u043a\u0430\u044f \u043d\u0435\u0439\u0440\u043e\u0441\u0435\u0442\u044c";
    if (argc != 4) return 2;
    ZeroMemory(&startup, sizeof(startup));
    ZeroMemory(&process, sizeof(process));
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = SW_HIDE;
    swprintf(command, 32768, L"\"%ls\" /P 0", argv[1]);
    if (!GetWindowsDirectoryW(windows_directory, MAX_PATH)) return 3;
    if (!CreateProcessW(argv[1], command, NULL, NULL, FALSE, CREATE_NEW_CONSOLE,
                        NULL, windows_directory, &startup, &process)) return 3;
    FreeConsole();
    started = GetTickCount();
    while (!AttachConsole(process.dwProcessId)) {
        if (GetTickCount() - started > 5000) goto finished;
        Sleep(50);
    }
    input = CreateFileW(L"CONIN$", GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    output = CreateFileW(L"CONOUT$", GENERIC_READ | GENERIC_WRITE,
                         FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (input == INVALID_HANDLE_VALUE || output == INVALID_HANDLE_VALUE) goto finished;
    /* Unicode I/O must work even with a deliberately non-Cyrillic codepage. */
    SetConsoleCP(1252); SetConsoleOutputCP(1252);
    if (!type_line(input, question)) goto finished;
    started = GetTickCount();
    while (GetTickCount() - started < 30000) {
        free(text); text = screen(output, &width, &rows);
        if (text && wcsstr(text, answer) && wcsstr(text, title)) { ok = 1; break; }
        if (WaitForSingleObject(process.hProcess, 0) == WAIT_OBJECT_0) break;
        Sleep(50);
    }
    if (text) {
        FILE *file = _wfopen(argv[2], L"wb");
        if (file) {
            DWORD row;
            for (row = 0; row < rows; row++) {
                DWORD length = width;
                char utf8[4096];
                int bytes;
                while (length && text[row * width + length - 1] == L' ') length--;
                bytes = WideCharToMultiByte(CP_UTF8, 0, text + row * width, length,
                                            utf8, sizeof(utf8), NULL, NULL);
                if (bytes > 0) fwrite(utf8, 1, bytes, file);
                fputc('\n', file);
            }
            fclose(file);
        }
    }
    if (ok) {
        type_line(input, L"quit\r");
        if (WaitForSingleObject(process.hProcess, 10000) != WAIT_OBJECT_0) ok = 0;
        GetExitCodeProcess(process.hProcess, &code);
        if (code) ok = 0;
    }
finished:
    error = ok ? ERROR_SUCCESS : GetLastError();
    if (!ok) TerminateProcess(process.hProcess, 1);
    if (input != INVALID_HANDLE_VALUE) CloseHandle(input);
    if (output != INVALID_HANDLE_VALUE) CloseHandle(output);
    FreeConsole();
    CloseHandle(process.hThread); CloseHandle(process.hProcess);
    free(text);
    report = _wfopen(argv[3], L"wb");
    if (report) {
        fprintf(report, "{\"ok\":%s,\"console_codepage\":1252,\"exit_code\":%lu,\"last_error\":%lu}\n",
                ok ? "true" : "false", (unsigned long)code, (unsigned long)error);
        fclose(report);
    }
    return ok ? 0 : 1;
}
