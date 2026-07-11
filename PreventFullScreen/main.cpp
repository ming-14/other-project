#include <Windows.h>
#include <iostream>
#include <string>
#include <thread>
#include <atomic>
#include <Psapi.h>
#include <shellapi.h>

// 全局变量存储上一次处理的窗口句柄
static HWND lastHandledWindow = nullptr;
static HWND lastFocusedWindow = nullptr;
static std::atomic<bool> killRequested(false);
static std::atomic<bool> hideRequested(false);
static std::atomic<bool> restartRequested(false);
static std::atomic<bool> coKillRequested(false);
static std::atomic<bool> coHideRequested(false); // 新增：co-hide请求标志
static std::string lastProcessPath;

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
    MONITORINFO monitorInfo = { sizeof(MONITORINFO) };
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
        if (GetModuleFileNameExA(hProcess, NULL, path, MAX_PATH)) {
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
    HINSTANCE result = ShellExecuteA(
        NULL,               // 父窗口句柄
        "open",             // 操作
        lastProcessPath.c_str(), // 文件路径
        NULL,               // 参数
        NULL,               // 工作目录
        SW_SHOWNORMAL       // 显示方式
    );

    // 检查执行结果
    if ((int)result <= 32) {
        std::cerr << "Failed to restart process. Error code: " << (int)result << std::endl;
    }
    else {
        std::cout << "Process restarted successfully." << std::endl;
    }
}

// 控制台输入监听线程
void ConsoleInputListener() {
    std::string input;
    while (true) {
        std::getline(std::cin, input);
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
        else if (input == "co-hide") { // 新增：处理co-hide命令
            coHideRequested = true;
        }
    }
}

int main(int argc, char* argv[]) {
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

    // 获取控制台窗口句柄（用于排除自身）
    HWND consoleWindow = GetConsoleWindow();

    // 启动控制台输入监听线程
    std::thread inputThread(ConsoleInputListener);
    inputThread.detach();

    bool wasFullscreen = false;

    while (true) {
        // 获取当前焦点窗口
        HWND foregroundWindow = GetForegroundWindow();

        // 记录上一次焦点窗口（排除控制台自身）
        if (foregroundWindow && foregroundWindow != consoleWindow) {
            lastFocusedWindow = foregroundWindow;
        }

        // 处理kill请求
        if (killRequested) {
            if (lastHandledWindow && IsWindow(lastHandledWindow)) {
                std::cout << "Killing last handled window..." << std::endl;
                KillWindowProcess(lastHandledWindow);
            }
            else {
                std::cout << "No valid window to kill." << std::endl;
            }
            killRequested = false;
        }

        // 处理hide请求
        if (hideRequested) {
            if (lastHandledWindow && IsWindow(lastHandledWindow)) {
                std::cout << "Minimizing last handled window..." << std::endl;
                MinimizeWindow(lastHandledWindow);
            }
            else {
                std::cout << "No valid window to minimize." << std::endl;
            }
            hideRequested = false;
        }

        // 处理restart请求
        if (restartRequested) {
            std::cout << "Restarting last handled process..." << std::endl;
            RestartLastProcess();
            restartRequested = false;
        }

        // 处理co-kill请求
        if (coKillRequested) {
            if (lastFocusedWindow && IsWindow(lastFocusedWindow) && lastFocusedWindow != consoleWindow) {
                std::cout << "Killing last focused window..." << std::endl;
                KillWindowProcess(lastFocusedWindow);
            }
            else {
                std::cout << "No valid window to co-kill." << std::endl;
            }
            coKillRequested = false;
        }

        // 处理co-hide请求（新增）
        if (coHideRequested) {
            if (lastFocusedWindow && IsWindow(lastFocusedWindow) && lastFocusedWindow != consoleWindow) {
                std::cout << "Minimizing last focused window..." << std::endl;
                MinimizeWindow(lastFocusedWindow);
            }
            else {
                std::cout << "No valid window to co-hide." << std::endl;
            }
            coHideRequested = false;
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

    return 0;
}