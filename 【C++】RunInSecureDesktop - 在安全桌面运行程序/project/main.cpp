#include <windows.h>
#include <tlhelp32.h>
#include <psapi.h>
#include <vector>
#include <string>
#include <iostream>

#pragma comment(lib, "advapi32.lib")

// 启用进程权限
bool EnablePrivilege(LPCTSTR privilegeName) {
    HANDLE hToken;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &hToken)) {
        std::cerr << "OpenProcessToken failed: " << GetLastError() << std::endl;
        return false;
    }

    TOKEN_PRIVILEGES tp;
    LUID luid;
    if (!LookupPrivilegeValue(NULL, privilegeName, &luid)) {
        std::cerr << "LookupPrivilegeValue failed: " << GetLastError() << std::endl;
        CloseHandle(hToken);
        return false;
    }

    tp.PrivilegeCount = 1;
    tp.Privileges[0].Luid = luid;
    tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;

    if (!AdjustTokenPrivileges(hToken, FALSE, &tp, sizeof(TOKEN_PRIVILEGES), NULL, NULL)) {
        std::cerr << "AdjustTokenPrivileges failed: " << GetLastError() << std::endl;
        CloseHandle(hToken);
        return false;
    }

    if (GetLastError() == ERROR_NOT_ALL_ASSIGNED) {
        std::cerr << "The token does not have the specified privilege." << std::endl;
        CloseHandle(hToken);
        return false;
    }

    CloseHandle(hToken);
    return true;
}

// 获取进程ID列表
std::vector<DWORD> GetProcessIdsByName(const char* processName) {
    std::vector<DWORD> pids;
    PROCESSENTRY32 pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32);

    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        std::cerr << "CreateToolhelp32Snapshot failed: " << GetLastError() << std::endl;
        return pids;
    }

    if (Process32First(hSnapshot, &pe32)) {
        do {
            if (_stricmp(pe32.szExeFile, processName) == 0) {
                pids.push_back(pe32.th32ProcessID);
            }
        } while (Process32Next(hSnapshot, &pe32));
    }

    CloseHandle(hSnapshot);
    return pids;
}

// 获取进程会话ID
DWORD GetProcessSessionId(DWORD pid) {
    DWORD sessionId = 0;
    if (!ProcessIdToSessionId(pid, &sessionId)) {
        std::cerr << "ProcessIdToSessionId failed: " << GetLastError() << std::endl;
        return 0;
    }
    return sessionId;
}

// 在安全桌面启动
bool LaunchInSecureDesktop(HANDLE hToken, const char* appPath) {
    STARTUPINFOA si = { sizeof(si) };
    PROCESS_INFORMATION pi = { 0 };

    // 指定安全桌面
    char desktop[] = "WinSta0\\Winlogon";
    si.lpDesktop = desktop;

    // 创建进程
    if (!CreateProcessAsUserA(
        hToken,            // 复制的令牌
        appPath,           // 应用程序路径
        NULL,              // 命令行参数
        NULL,              // 进程安全属性
        NULL,              // 线程安全属性
        FALSE,             // 不继承句柄
        CREATE_NEW_CONSOLE | CREATE_UNICODE_ENVIRONMENT, // 创建标志
        NULL,              // 环境块
        NULL,              // 当前目录
        &si,               // STARTUPINFO
        &pi))              // PROCESS_INFORMATION
    {
        std::cerr << "CreateProcessAsUserA failed: " << GetLastError() << std::endl;
        return false;
    }

    std::cout << "Successfully launched process in secure desktop. PID: " << pi.dwProcessId << std::endl;

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return true;
}

bool IsSecureDesktopActive() {
    HDESK hDesktop = OpenInputDesktop(0, FALSE, DESKTOP_SWITCHDESKTOP);
    if (!hDesktop) return false;

    WCHAR desktopName[256] = { 0 };
    GetUserObjectInformationW(hDesktop, UOI_NAME, desktopName, sizeof(desktopName), NULL);
    CloseDesktop(hDesktop);

    return _wcsicmp(desktopName, L"Winlogon") == 0;
}

int main(int argc, char* argv[]) {
    // 启用所需权限
    if (!EnablePrivilege(SE_DEBUG_NAME) || !EnablePrivilege(SE_TCB_NAME)) {
        std::cerr << "Failed to enable required privileges. Make sure you're running with Nsudo." << std::endl;
        return 1;
    }

    const char* targetProcess = "winlogon.exe";
    const char* helperApp = (argc == 1||argv[1][0] == '\0') ? "C:\\Windows\\System32\\cmd.exe" : argv[1]; // 修改为你的辅助程序路径

    std::cout << "helperApp: " << helperApp << std::endl;

    std::cout << "Waiting for secure desktop (winlogon in user session)..." << std::endl;

    while (true) {
        // 检查安全桌面是否激活
        if (IsSecureDesktopActive()) {
            // 获取所有winlogon.exe进程
            std::vector<DWORD> pids = GetProcessIdsByName(targetProcess);

            for (DWORD pid : pids) {
                // 跳过会话0的系统进程
                DWORD sessionId = GetProcessSessionId(pid);
                if (sessionId == 0) continue;

                std::cout << "Found winlogon.exe in session " << sessionId << " (PID: " << pid << ")" << std::endl;

                // 打开进程
                HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, pid);
                if (!hProcess) {
                    std::cerr << "OpenProcess failed: " << GetLastError() << std::endl;
                    continue;
                }

                // 打开进程令牌
                HANDLE hToken;
                if (!OpenProcessToken(hProcess, TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ASSIGN_PRIMARY, &hToken)) {
                    std::cerr << "OpenProcessToken failed: " << GetLastError() << std::endl;
                    CloseHandle(hProcess);
                    continue;
                }

                // 复制令牌
                HANDLE hDupToken;
                if (!DuplicateTokenEx(
                    hToken,
                    MAXIMUM_ALLOWED,
                    NULL,
                    SecurityImpersonation,
                    TokenPrimary,
                    &hDupToken))
                {
                    std::cerr << "DuplicateTokenEx failed: " << GetLastError() << std::endl;
                    CloseHandle(hToken);
                    CloseHandle(hProcess);
                    continue;
                }

                // 在安全桌面启动程序
                if (LaunchInSecureDesktop(hDupToken, helperApp)) {
                    CloseHandle(hDupToken);
                    CloseHandle(hToken);
                    CloseHandle(hProcess);
                    std::cout << "Successfully launched helper application." << std::endl;
                    system("pause");
                    return 0;
                }

                CloseHandle(hDupToken);
                CloseHandle(hToken);
                CloseHandle(hProcess);
            }

            Sleep(1000);
        }
    }

    system("pause");
    return 0;
}