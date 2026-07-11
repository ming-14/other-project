#include <windows.h>

void _start(void) {
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD written;
    WriteFile(hOut, "This is a demo program.\r\n", 25, &written, NULL);
    ExitProcess(0);
}
