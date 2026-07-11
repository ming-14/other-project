#include <windows.h>
#include <tlhelp32.h>
#include <shlobj.h>
#include <iostream>
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <algorithm>

// 全局变量存储上一次处理的窗口句柄
static HWND lastHandledWindow = NULL;
static HWND lastFocusedWindow = NULL;
static bool killRequested = false;
static bool hideRequested = false;
static bool restartRequested = false;
static bool coKillRequested = false;
static bool coHideRequested = false;
static std::string lastProcessPath;

// 临界区用于线程同步
CRITICAL_SECTION g_cs;

// 检测窗口是否全屏
bool IsFullscreenWindow(HWND hwnd) {
    if (!hwnd || hwnd == GetDesktopWindow() || hwnd == GetShellWindow()) {
        return false;
    }

    RECT windowRect;
    if (!GetWindowRect(hwnd, &windowRect)) {
        return false;
    }

    // 获取窗口所在显示器的信息
    HMONITOR monitor = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST);
    MONITORINFO monitorInfo;
    monitorInfo.cbSize = sizeof(MONITORINFO);
    if (!GetMonitorInfo(monitor, &monitorInfo)) {
        return false;
    }

    // 比较窗口尺寸和显示器尺寸
    const RECT& screenRect = monitorInfo.rcMonitor;
    return windowRect.left == screenRect.left &&
        windowRect.top == screenRect.top &&
        windowRect.right == screenRect.right &&
        windowRect.bottom == screenRect.bottom;
}

// 强制将窗口窗口化
void ForceWindowedMode(HWND hwnd) {
    if (!hwnd || !IsWindow(hwnd)) return;

    std::cout << "Attempting to force window out of fullscreen..." << std::endl;

    // 记录当前处理的窗口
    lastHandledWindow = hwnd;

    // 获取并保存进程路径
    DWORD processId;
    GetWindowThreadProcessId(hwnd, &processId);
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, processId);
    if (hProcess) {
        char path[MAX_PATH];
        // 使用 GetModuleFileName 替代 GetModuleFileNameExA
        if (GetModuleFileNameA(NULL, path, MAX_PATH)) {
            lastProcessPath = path;
            std::cout << "Saved process path: " << lastProcessPath << std::endl;
        }
        else {
            std::cerr << "Failed to get process path. Error: " << GetLastError() << std::endl;
        }
        CloseHandle(hProcess);
    }
    else {
        std::cerr << "Failed to open process for path query. Error: " << GetLastError() << std::endl;
    }

    // 方法1: 尝试发送还原命令
    PostMessage(hwnd, WM_SYSCOMMAND, SC_RESTORE, 0);

    // 方法2: 尝试切换窗口样式
    LONG_PTR style = GetWindowLongPtr(hwnd, GWL_STYLE);
    if (style) {
        // 移除全屏相关的样式
        style &= ~(WS_POPUP | WS_BORDER);
        style |= WS_OVERLAPPEDWINDOW;
        SetWindowLongPtr(hwnd, GWL_STYLE, style);
    }

    // 方法3: 强制调整窗口大小和位置
    RECT rect;
    GetWindowRect(hwnd, &rect);
    rect.right = rect.left + 800;  // 新宽度
    rect.bottom = rect.top + 600;  // 新高度

    // 获取屏幕中心位置
    int screenWidth = GetSystemMetrics(SM_CXSCREEN);
    int screenHeight = GetSystemMetrics(SM_CYSCREEN);
    int centerX = (screenWidth - 800) / 2;
    int centerY = (screenHeight - 600) / 2;

    // 应用新位置和大小
    SetWindowPos(hwnd, HWND_TOP, centerX, centerY, 800, 600, SWP_SHOWWINDOW);

    // 刷新窗口
    ShowWindow(hwnd, SW_SHOWNORMAL);
    UpdateWindow(hwnd);
}

// 结束指定窗口的进程
void KillWindowProcess(HWND hwnd) {
    if (!hwnd || !IsWindow(hwnd)) {
        std::cout << "Invalid window handle." << std::endl;
        return;
    }

    DWORD processId;
    GetWindowThreadProcessId(hwnd, &processId);
    if (!processId) {
        std::cout << "Failed to get process ID." << std::endl;
        return;
    }

    HANDLE hProcess = OpenProcess(PROCESS_TERMINATE, FALSE, processId);
    if (!hProcess) {
        std::cout << "Failed to open process. Error: " << GetLastError() << std::endl;
        return;
    }

    if (TerminateProcess(hProcess, 0)) {
        std::cout << "Process terminated successfully." << std::endl;
    }
    else {
        std::cout << "TerminateProcess failed. Error: " << GetLastError() << std::endl;
    }

    CloseHandle(hProcess);
}

// 最小化指定窗口
void MinimizeWindow(HWND hwnd) {
    if (!hwnd || !IsWindow(hwnd)) {
        std::cout << "Invalid window handle." << std::endl;
        return;
    }

    // 最小化窗口
    if (ShowWindow(hwnd, SW_MINIMIZE)) {
        std::cout << "Window minimized successfully." << std::endl;
    }
    else {
        std::cout << "Minimize failed. Error: " << GetLastError() << std::endl;
    }
}

// 重启进程
void RestartLastProcess() {
    if (lastProcessPath.empty()) {
        std::cout << "No saved process path to restart." << std::endl;
        return;
    }

    std::cout << "Attempting to restart: " << lastProcessPath << std::endl;

    // 使用ShellExecute启动进程
    HINSTANCE hInstance = ShellExecuteA(
        NULL,               // 父窗口句柄
        "open",             // 操作
        lastProcessPath.c_str(), // 文件路径
        NULL,               // 参数
        NULL,               // 工作目录
        SW_SHOWNORMAL       // 显示方式
    );

    // 将HINSTANCE转换为INT_PTR以进行数值比较
    INT_PTR result = (INT_PTR)hInstance;

    // 检查执行结果
    if (result <= 32) {
        std::cerr << "Failed to restart process. Error code: " << (int)result << std::endl;
    }
    else {
        std::cout << "Process restarted successfully." << std::endl;
    }
}

// 控制台输入监听线程
DWORD WINAPI ConsoleInputListener(LPVOID lpParam) {
    std::string input;
    while (true) {
        std::getline(std::cin, input);
        EnterCriticalSection(&g_cs);
        if (input == "kill") {
            killRequested = true;
        }
        else if (input == "hide") {
            hideRequested = true;
        }
        else if (input == "restart") {
            restartRequested = true;
        }
        else if (input == "co-kill") {
            coKillRequested = true;
        }
        else if (input == "co-hide") {
            coHideRequested = true;
        }
        LeaveCriticalSection(&g_cs);
    }
    return 0;
}

// 声明未文档化的NTAPI函数
typedef NTSTATUS(NTAPI* pfnNtSetInformationProcess)(
    HANDLE ProcessHandle,
    ULONG ProcessInformationClass,
    PVOID ProcessInformation,
    ULONG ProcessInformationLength);

#define ProcessBreakOnTermination 29

// 结束指定进程
bool TerminateProcessByName(const char* processName) {
    // 动态获取NtSetInformationProcess函数
    HMODULE hNtdll = GetModuleHandleA("ntdll.dll");
    if (!hNtdll) {
        return false;
    }
    
    pfnNtSetInformationProcess NtSetInformationProcess = 
        (pfnNtSetInformationProcess)GetProcAddress(hNtdll, "NtSetInformationProcess");
    if (!NtSetInformationProcess) {
        return false;
    }

    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) 
        return false;
    
    PROCESSENTRY32 pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32);
    
    if (!Process32First(hSnapshot, &pe32)) {
        CloseHandle(hSnapshot);
        return false;
    }
    
    bool found = false;
    do {
        if (_stricmp(pe32.szExeFile, processName) == 0) {
            // 打开进程，需要PROCESS_SET_INFORMATION权限
            HANDLE hProcess = OpenProcess(PROCESS_TERMINATE | PROCESS_SET_INFORMATION, 
                                         FALSE, pe32.th32ProcessID);
            if (hProcess != NULL) {
                // 首先尝试移除关键进程标志
                ULONG BreakOnTermination = 0;
                NTSTATUS status = NtSetInformationProcess(hProcess, 
                    ProcessBreakOnTermination, 
                    &BreakOnTermination, 
                    sizeof(ULONG));
                
                // 无论是否成功移除关键标志，都尝试终止进程
                if (TerminateProcess(hProcess, 0)) {
                    found = true;
                }
                
                CloseHandle(hProcess);
            }
        }
    } while (Process32Next(hSnapshot, &pe32));
    
    CloseHandle(hSnapshot);
    return found;
}

// 获取当前用户的SID
std::string GetCurrentUserSID() {
    HANDLE hToken = NULL;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &hToken)) {
        return "";
    }
    DWORD dwSize = 0;
    GetTokenInformation(hToken, TokenUser, NULL, 0, &dwSize);
    if (dwSize == 0) {
        CloseHandle(hToken);
        return "";
    }
    PTOKEN_USER pTokenUser = (PTOKEN_USER)malloc(dwSize);
    if (!pTokenUser) {
        CloseHandle(hToken);
        return "";
    }
    if (!GetTokenInformation(hToken, TokenUser, pTokenUser, dwSize, &dwSize)) {
        free(pTokenUser);
        CloseHandle(hToken);
        return "";
    }

    // 手动构建SID字符串
    PSID pSid = pTokenUser->User.Sid;
    if (!IsValidSid(pSid)) {
        free(pTokenUser);
        CloseHandle(hToken);
        return "";
    }
    SID_IDENTIFIER_AUTHORITY* pSia = GetSidIdentifierAuthority(pSid);
    DWORD dwSubAuthCount = *GetSidSubAuthorityCount(pSid);
    std::ostringstream oss;
    oss << "S-1-";
    if ((pSia->Value[0] != 0) || (pSia->Value[1] != 0)) {
        oss << "0x";
        for (int i = 0; i < 6; i++) {
            oss << std::hex << static_cast<int>(pSia->Value[i]);
        }
    } else {
        oss << std::dec << (static_cast<DWORD>(pSia->Value[5]) +
            (static_cast<DWORD>(pSia->Value[4]) << 8) +
            (static_cast<DWORD>(pSia->Value[3]) << 16) +
            (static_cast<DWORD>(pSia->Value[2]) << 24));
    }
    for (DWORD i = 0; i < dwSubAuthCount; i++) {
        oss << "-" << std::dec << *GetSidSubAuthority(pSid, i);
    }
    std::string sid = oss.str();
    free(pTokenUser);
    CloseHandle(hToken);
    return sid;
}

// 删除注册表值
bool DeleteRegistryValue(HKEY hKey, const char* subKey, const char* valueName) {
    HKEY hSubKey;
    if (RegOpenKeyExA(hKey, subKey, 0, KEY_SET_VALUE, &hSubKey) != ERROR_SUCCESS) {
        return false;
    }
    LSTATUS status = RegDeleteValueA(hSubKey, valueName);
    RegCloseKey(hSubKey);
    return status == ERROR_SUCCESS;
}

// 设置注册表DWORD值
bool SetRegistryDWORD(HKEY hKey, const char* subKey, const char* valueName, DWORD value) {
    HKEY hSubKey;
    if (RegOpenKeyExA(hKey, subKey, 0, KEY_SET_VALUE, &hSubKey) != ERROR_SUCCESS) {
        return false;
    }
    
    LSTATUS status = RegSetValueExA(hSubKey, valueName, 0, REG_DWORD, 
                                   (const BYTE*)&value, sizeof(DWORD));
    RegCloseKey(hSubKey);
    return status == ERROR_SUCCESS;
}

// 删除注册表键
bool DeleteRegistryKey(HKEY hKey, const char* subKey) {
    return RegDeleteKeyA(hKey, subKey) == ERROR_SUCCESS;
}

// 删除文件
bool DeleteFileIfExists(const std::string& filePath) {
    if (GetFileAttributesA(filePath.c_str()) != INVALID_FILE_ATTRIBUTES) {
        return DeleteFileA(filePath.c_str());
    }
    return true;
}

// 删除目录（递归）
bool DeleteDirectoryRecursive(const std::string& path) {
    WIN32_FIND_DATAA findData;
    std::string searchPath = path + "\\*";
    HANDLE hFind = FindFirstFileA(searchPath.c_str(), &findData);
    
    if (hFind == INVALID_HANDLE_VALUE)
        return false;

    do {
        if (strcmp(findData.cFileName, ".") != 0 && 
            strcmp(findData.cFileName, "..") != 0) {
            
            std::string filePath = path + "\\" + findData.cFileName;
            
            if (findData.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                DeleteDirectoryRecursive(filePath);
            } else {
                DeleteFileA(filePath.c_str());
            }
        }
    } while (FindNextFileA(hFind, &findData));

    FindClose(hFind);
    return RemoveDirectoryA(path.c_str());
}

// 停止并删除服务
bool StopAndDeleteService(const char* serviceName) {
    SC_HANDLE scm = OpenSCManagerA(NULL, NULL, SC_MANAGER_ALL_ACCESS);
    if (!scm) return false;

    SC_HANDLE service = OpenServiceA(scm, serviceName, SERVICE_ALL_ACCESS);
    if (!service) {
        CloseServiceHandle(scm);
        return false;
    }

    SERVICE_STATUS status;
    ControlService(service, SERVICE_CONTROL_STOP, &status);
    Sleep(1000); // 等待服务停止

    bool result = DeleteService(service);
    CloseServiceHandle(service);
    CloseServiceHandle(scm);
    return result;
}

// 恢复hosts文件
void RestoreHostsFile() {
    char systemDir[MAX_PATH];
    GetSystemDirectoryA(systemDir, MAX_PATH);
    std::string hostsPath = std::string(systemDir) + "\\drivers\\etc\\hosts";

    // 强制删除文件
    DWORD attributes = GetFileAttributesA(hostsPath.c_str());
    if (attributes != INVALID_FILE_ATTRIBUTES) {
        if (attributes & FILE_ATTRIBUTE_READONLY) {
            SetFileAttributesA(hostsPath.c_str(), attributes & ~FILE_ATTRIBUTE_READONLY);
        }
        DeleteFileA(hostsPath.c_str());
    }

    std::ofstream hostsFile(hostsPath.c_str(), std::ios::out);
    if (hostsFile.is_open()) {
        hostsFile << "127.0.0.1       localhost\n";
        hostsFile << "::1             localhost\n";
        hostsFile.close();
    }
}

// 重启Explorer
void RestartExplorer() {
    // 结束Explorer进程
    TerminateProcessByName("explorer.exe");
    Sleep(1000);
    // 启动新的Explorer进程
    STARTUPINFOA si;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    PROCESS_INFORMATION pi;
    CreateProcessA(NULL, (LPSTR)"explorer.exe", NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
}

// 删除f开头的文件夹（包含about.exe）
void DeleteFStartFolders() {
    char systemDrive[MAX_PATH] = {0};
    GetSystemDirectoryA(systemDrive, MAX_PATH);
    systemDrive[3] = '\0'; // 提取盘符如 "C:\\"

    WIN32_FIND_DATAA findData;
    std::string searchPath = std::string(systemDrive) + "f*";
    HANDLE hFind = FindFirstFileA(searchPath.c_str(), &findData);
    
    if (hFind != INVALID_HANDLE_VALUE) {
        do {
            if (findData.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                std::string folderPath = std::string(systemDrive) + findData.cFileName;
                std::string aboutExe = folderPath + "\\about.exe";
                
                if (GetFileAttributesA(aboutExe.c_str()) != INVALID_FILE_ATTRIBUTES) {
                    DeleteDirectoryRecursive(folderPath);
                }
            }
        } while (FindNextFileA(hFind, &findData));
        FindClose(hFind);
    }
}

// 请求管理员权限
bool IsAdmin() {
    BOOL isAdmin = FALSE;
    SID_IDENTIFIER_AUTHORITY NtAuthority = SECURITY_NT_AUTHORITY;
    PSID AdministratorsGroup;
    
    if (AllocateAndInitializeSid(&NtAuthority, 2, SECURITY_BUILTIN_DOMAIN_RID, 
        DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0, &AdministratorsGroup)) {
        if (!CheckTokenMembership(NULL, AdministratorsGroup, &isAdmin)) {
            isAdmin = FALSE;
        }
        FreeSid(AdministratorsGroup);
    }
    return isAdmin != FALSE;
}

void RunAsAdmin() {
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    
    SHELLEXECUTEINFOA sei;
    ZeroMemory(&sei, sizeof(sei));
    sei.cbSize = sizeof(sei);
    sei.lpVerb = "runas";
    sei.lpFile = path;
    sei.hwnd = NULL;
    sei.nShow = SW_NORMAL;
    
    ShellExecuteExA(&sei);
    ExitProcess(0);
}

int p() {
    // 请求管理员权限
    if (!IsAdmin()) {
        RunAsAdmin();
        return 0;
    }

    std::cout << "开始系统恢复操作..." << std::endl << std::endl;

    // 获取当前用户SID
    std::string userSID = GetCurrentUserSID();
    if (!userSID.empty()) {
        std::cout << "检测到用户SID: " << userSID << std::endl << std::endl;
    }
    
    // 恢复CMD禁用
    std::cout << "恢复系统工具访问..." << std::endl;
    if (!userSID.empty()) {
        DeleteRegistryValue(HKEY_USERS, (userSID + "\\SOFTWARE\\Policies\\Microsoft\\Windows\\System").c_str(), "DisableCMD");
    }

    // 结束进程
    std::cout << "结束恶意进程..." << std::endl;
    const char* processes[] = {
        "jfglzsp.exe", "mmijp.exe", "abcut.exe", "about.exe", 
        "dtmmyz.exe", "instsrv.exe", "jfglzs.exe", "password.exe", 
        "prozs.exe", "przs.exe", "regini.exe", "sct.exe", 
        "set.exe", "srvany.exe", "uninstal1.exe", "yz.exe", 
        "zmserv.exe", "zmsrv.exe", "更新器.exe"
    };
    
    for (int i = 0; i < sizeof(processes)/sizeof(processes[0]); i++) {
        TerminateProcessByName(processes[i]);
    }

    // 1. 恢复注册表设置
    std::cout << "恢复注册表设置..." << std::endl;
    if (!userSID.empty()) {
        DeleteRegistryKey(HKEY_USERS, (userSID + "\\SOFTWARE\\jfglzs").c_str());
    }
    DeleteRegistryValue(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run", "prozs");
    DeleteRegistryValue(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run", "jfglzsp");
    SetRegistryDWORD(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "EnableLUA", 1);

    // 2. 恢复系统策略设置
    std::cout << "恢复系统策略..." << std::endl;
    if (!userSID.empty()) {
        SetRegistryDWORD(HKEY_USERS, (userSID + "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System").c_str(), "DisableRegistryTools", 0);
        SetRegistryDWORD(HKEY_USERS, (userSID + "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System").c_str(), "DisableLockWorkstation", 0);
        SetRegistryDWORD(HKEY_USERS, (userSID + "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer").c_str(), "NoRun", 0);
    }

    // 3. 恢复防火墙设置
    std::cout << "恢复防火墙设置..." << std::endl;
    SetRegistryDWORD(HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Services\\SharedAccess\\Parameters\\FirewallPolicy\\StandardProfile", "EnableFirewall", 1);
    SetRegistryDWORD(HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Services\\SharedAccess\\Parameters\\FirewallPolicy\\DomainProfile", "EnableFirewall", 1);
    SetRegistryDWORD(HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Services\\SharedAccess\\Parameters\\FirewallPolicy\\PublicProfile", "EnableFirewall", 1);
    system("netsh advfirewall set allprofiles state on >nul 2>&1");

    // 4. 删除创建的文件和目录
    std::cout << "清理恶意文件..." << std::endl;
    char desktopPath[MAX_PATH];
    SHGetSpecialFolderPathA(NULL, desktopPath, CSIDL_DESKTOP, FALSE);
    
    std::string desktopNull = std::string(desktopPath) + "\\null.exe2";
    DeleteFileIfExists(desktopNull);
    
    DeleteFStartFolders();
    
    char systemDrive[MAX_PATH] = {0};
    GetSystemDirectoryA(systemDrive, MAX_PATH);
    systemDrive[3] = '\0';
    
    std::string mijpPath = std::string(systemDrive) + "Program Files (x86)\\mijp";
    DeleteDirectoryRecursive(mijpPath);
    
    std::string jfPath = std::string(systemDrive) + "Windows\\jf";
    DeleteDirectoryRecursive(jfPath);
    
    std::string desktopShortcut = std::string(desktopPath) + "\\百度搜索&网址导航.url";
    DeleteFileIfExists(desktopShortcut);
    
    char favoritesPath[MAX_PATH];
    SHGetSpecialFolderPathA(NULL, favoritesPath, CSIDL_FAVORITES, FALSE);
    std::string favShortcut = std::string(favoritesPath) + "\\Links\\百度搜索&网址导航.url";
    DeleteFileIfExists(favShortcut);

    // 5. 恢复hosts文件
    std::cout << "恢复hosts文件..." << std::endl;
    RestoreHostsFile();

    // 6. 恢复浏览器策略
    std::cout << "恢复浏览器设置..." << std::endl;
    DeleteRegistryKey(HKEY_LOCAL_MACHINE, "SOFTWARE\\Policies\\Google");
    DeleteRegistryKey(HKEY_LOCAL_MACHINE, "SOFTWARE\\Policies\\Microsoft\\Edge");
    DeleteRegistryKey(HKEY_LOCAL_MACHINE, "SOFTWARE\\Policies\\Mozilla");

    // 7. 恢复文件夹选项和隐藏文件设置
    std::cout << "恢复文件夹选项..." << std::endl;
    if (!userSID.empty()) {
        SetRegistryDWORD(HKEY_USERS, (userSID + "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced").c_str(), "Hidden", 1);
        SetRegistryDWORD(HKEY_USERS, (userSID + "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced").c_str(), "ShowSuperHidden", 0);
        SetRegistryDWORD(HKEY_USERS, (userSID + "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced").c_str(), "HideFileExt", 0);
        DeleteRegistryValue(HKEY_USERS, (userSID + "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer").c_str(), "NoFolderOptions");
    }
    SetRegistryDWORD(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced\\Folder\\Hidden\\SHOWALL", "CheckedValue", 1);

    // 8. 删除创建的服务
    std::cout << "清理恶意服务..." << std::endl;
    StopAndDeleteService("zmserv");

    // 9. 恢复任务栏和开始菜单设置
    std::cout << "恢复任务栏设置..." << std::endl;
    if (!userSID.empty()) {
        SetRegistryDWORD(HKEY_USERS, (userSID + "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Search").c_str(), "SearchboxTaskbarMode", 1);
        SetRegistryDWORD(HKEY_USERS, (userSID + "\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced").c_str(), "ShowTaskViewButton", 1);
    }
    
    // 删除右键菜单项
    DeleteRegistryKey(HKEY_CLASSES_ROOT, "*\\shell\\runas");
    DeleteRegistryKey(HKEY_CLASSES_ROOT, "exefile\\shell\\runas2");
    DeleteRegistryKey(HKEY_CLASSES_ROOT, "Directory\\shell\\runas");
    
    // 还原系统策略设置
    SetRegistryDWORD(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "EnableLUA", 1);
    DeleteRegistryValue(HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "HideFastUserSwitching");
    
    // 删除IE主页设置
    const char* ieKeys[] = {
        "SOFTWARE\\Policies\\Microsoft\\Internet Explorer\\Main",
        "Software\\Microsoft\\Internet Explorer\\Main",
        "SOFTWARE\\Microsoft\\Internet Explorer\\MAIN",
        "SOFTWARE\\Software\\Microsoft\\Internet Explorer\\Main",
        "SOFTWARE\\Wow6432Node\\Baidu\\BaiduProtect\\LockIEStartPage",
        "SOFTWARE\\Wow6432Node\\Software\\Microsoft\\Internet Explorer\\Main"
    };
    
    for (int i = 0; i < sizeof(ieKeys)/sizeof(ieKeys[0]); i++) {
        DeleteRegistryValue(HKEY_LOCAL_MACHINE, ieKeys[i], "Start Page");
        DeleteRegistryValue(HKEY_LOCAL_MACHINE, ieKeys[i], "Default_Page_URL");
        DeleteRegistryValue(HKEY_LOCAL_MACHINE, ieKeys[i], "First Home Page");
    }
    
    DeleteRegistryValue(HKEY_CURRENT_USER, "Software\\Microsoft\\Internet Explorer\\Main", "Default_Page_URL");
    DeleteRegistryValue(HKEY_CURRENT_USER, "Software\\Microsoft\\Internet Explorer\\Main", "Start Page");
    DeleteRegistryValue(HKEY_USERS, ".DEFAULT\\Software\\Microsoft\\Internet Explorer\\Main", "Start Page");
    DeleteRegistryValue(HKEY_USERS, ".DEFAULT\\Software\\Microsoft\\Internet Explorer\\Main", "First Home Page");
    
    // 删除键盘布局映射
    DeleteRegistryValue(HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Control\\Keyboard Layout", "Scancode Map");
    
    // 删除资源管理器策略
    DeleteRegistryValue(HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer", "NoTrayContextMenu");
    
    // 删除Internet安全区域设置
    DeleteRegistryValue(HKEY_CURRENT_USER, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\\Zones\\3", "1803");
    DeleteRegistryValue(HKEY_CURRENT_USER, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Internet Settings\\Zones\\3", "2200");
    
    // 删除IE限制
    DeleteRegistryValue(HKEY_CURRENT_USER, "Software\\Policies\\Microsoft\\Internet Explorer\\Restrictions", "NoBrowserSaveAs");
    
    // 删除Windows商店策略
    DeleteRegistryValue(HKEY_LOCAL_MACHINE, "SOFTWARE\\Policies\\Microsoft\\WindowsStore", "RemoveWindowsStore");
    
    // 删除映像文件执行选项
    const char* exeFiles[] = {
        "taskkill.exe", "ntsd.exe", "sidebar.exe", "Chess.exe", "FreeCell.exe",
        "Hearts.exe", "Minesweeper.exe", "PurblePlace.exe", "Mahjong.exe",
        "SpiderSolitaire.exe", "bckgzm.exe", "chkrzm.exe", "shvlzm.exe",
        "Solitaire.exe", "winmine.exe", "Magnify.exe", "sethc.exe", "tasklist.exe"
    };
    
    for (int i = 0; i < sizeof(exeFiles)/sizeof(exeFiles[0]); i++) {
        std::string keyPath = std::string("SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Image File Execution Options\\") + exeFiles[i];
        DeleteRegistryKey(HKEY_LOCAL_MACHINE, keyPath.c_str());
    }
    
    // 删除Windows Defender策略
    DeleteRegistryValue(HKEY_LOCAL_MACHINE, "SOFTWARE\\Policies\\Microsoft\\Windows Defender", "DisableAntiSpyware");
    DeleteRegistryValue(HKEY_LOCAL_MACHINE, "SOFTWARE\\Policies\\Microsoft\\Windows Defender", "DisableAntiVirus");
    DeleteRegistryValue(HKEY_LOCAL_MACHINE, "SOFTWARE\\Policies\\Microsoft\\Windows Defender", "ServiceKeepAlive");
    DeleteRegistryValue(HKEY_LOCAL_MACHINE, "SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection", "DisableRealtimeMonitoring");

    // 重启Explorer应用更改
    std::cout << "重启Explorer..." << std::endl;
    RestartExplorer();

    std::cout << std::endl << "系统恢复完成!" << std::endl;
    std::cout << "建议重启计算机以确保所有更改生效。" << std::endl;
    std::cout << "开始全屏保护" << std::endl;
    return 0;
}

int main(int argc, char* argv[]) {
    p();
    if (argc > 1 && std::string(argv[1]) == "-h") {
        std::cout << "Usage: PreventFullScreen.exe" << std::endl;
        std::cout << "  -h: Show this help message." << std::endl;
        std::cout << "  Running: kill, hide, restart, co-kill, co-hide" << std::endl;
        std::cout << "    co-kill: Kill the last focused window." << std::endl;
        std::cout << "    co-hide: Minimize the last focused window." << std::endl;
        std::cout << "    kill: Kill the last handled window." << std::endl;
        std::cout << "    hide: Minimize the last handled window." << std::endl;
        std::cout << "    restart: Restart the last handled process." << std::endl;
    }

    // 初始化临界区
    InitializeCriticalSection(&g_cs);
    // 获取控制台窗口句柄（用于排除自身）
    HWND consoleWindow = GetConsoleWindow();
    // 启动控制台输入监听线程
    HANDLE hThread = CreateThread(NULL, 0, ConsoleInputListener, NULL, 0, NULL);
    if (hThread == NULL) {
        std::cerr << "Failed to create input thread. Error: " << GetLastError() << std::endl;
        return 1;
    }
    CloseHandle(hThread);

    bool wasFullscreen = false;

    while (true) {
        // 获取当前焦点窗口
        HWND foregroundWindow = GetForegroundWindow();
        // 记录上一次焦点窗口（排除控制台自身）
        if (foregroundWindow && foregroundWindow != consoleWindow) {
            lastFocusedWindow = foregroundWindow;
        }

        // 处理请求标志（使用临界区保护）
        bool localKillRequested = false;
        bool localHideRequested = false;
        bool localRestartRequested = false;
        bool localCoKillRequested = false;
        bool localCoHideRequested = false;

        EnterCriticalSection(&g_cs);
        localKillRequested = killRequested;
        killRequested = false;
        localHideRequested = hideRequested;
        hideRequested = false;
        localRestartRequested = restartRequested;
        restartRequested = false;
        localCoKillRequested = coKillRequested;
        coKillRequested = false;
        localCoHideRequested = coHideRequested;
        coHideRequested = false;
        LeaveCriticalSection(&g_cs);
        // 处理kill请求
        if (localKillRequested) {
            if (lastHandledWindow && IsWindow(lastHandledWindow)) {
                std::cout << "Killing last handled window..." << std::endl;
                KillWindowProcess(lastHandledWindow);
            }
            else {
                std::cout << "No valid window to kill." << std::endl;
            }
        }
        // 处理hide请求
        if (localHideRequested) {
            if (lastHandledWindow && IsWindow(lastHandledWindow)) {
                std::cout << "Minimizing last handled window..." << std::endl;
                MinimizeWindow(lastHandledWindow);
            }
            else {
                std::cout << "No valid window to minimize." << std::endl;
            }
        }
        // 处理restart请求
        if (localRestartRequested) {
            std::cout << "Restarting last handled process..." << std::endl;
            RestartLastProcess();
        }
        // 处理co-kill请求
        if (localCoKillRequested) {
            if (lastFocusedWindow && IsWindow(lastFocusedWindow) && lastFocusedWindow != consoleWindow) {
                std::cout << "Killing last focused window..." << std::endl;
                KillWindowProcess(lastFocusedWindow);
            }
            else {
                std::cout << "No valid window to co-kill." << std::endl;
            }
        }
        // 处理co-hide请求
        if (localCoHideRequested) {
            if (lastFocusedWindow && IsWindow(lastFocusedWindow) && lastFocusedWindow != consoleWindow) {
                std::cout << "Minimizing last focused window..." << std::endl;
                MinimizeWindow(lastFocusedWindow);
            }
            else {
                std::cout << "No valid window to co-hide." << std::endl;
            }
        }
        if (foregroundWindow) {
            bool isFullscreen = IsFullscreenWindow(foregroundWindow);
            // 检测到进入全屏状态
            if (isFullscreen && !wasFullscreen) {
                std::cout << "Fullscreen detected! Forcing windowed mode..." << std::endl;
                ForceWindowedMode(foregroundWindow);
            }
            wasFullscreen = isFullscreen;
        }
        // 每500毫秒检测一次
        Sleep(500);
    }
    // 清理临界区（理论上不会执行到这里）
    DeleteCriticalSection(&g_cs);
    return 0;
}