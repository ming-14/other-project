const inputTextarea = document.getElementById('input');
const outputTextarea = document.getElementById('output');
const outputDiv = document.getElementById('output-highlight');

document.addEventListener('DOMContentLoaded', function () {
    // 代码选项卡功能
    const sendBtn = document.getElementById('send-btn');
    const commentBtn = document.getElementById('comment-btn');
    const copyBtn = document.getElementById('copy-btn');

    // 选项卡切换
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');

            // 切换按钮状态
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            // 切换面板显示
            tabPanels.forEach(panel => {
                panel.classList.remove('active');
                if (panel.id === tabId) {
                    panel.classList.add('active');
                }
            });

            // 当切换到转换选项卡时执行代码
            if (tabId === 'convert') {
                executeConvertFunction();
            }
        });
    });

    // 点击output区域时切换到编辑模式
    outputDiv.addEventListener('click', (event) => {
        console.log('Container clicked');
        const selection = window.getSelection();
        const selectedText = selection.toString().trim();
        if(selectedText != "") return;

        setTimeout(() => {
            switchToEdit({ x: event.clientX, y: event.clientY });
        }, 200);
    });

    // 失去焦点时切换到高亮模式
    outputTextarea.addEventListener('blur', (event) => {
        console.log('Textarea blur');

            switchToHighlight(event);
    });

    // 发送按钮功能
    sendBtn.addEventListener('click', async () => {
        const input = inputTextarea.value.trim();
        if (input) {
            try {
                // 显示加载状态
                outputTextarea.value = '正在请求数据...';

                // 发送POST请求
                const response = await fetch('http://127.0.0.1:8080/api/get', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `q=${encodeURIComponent(input)}`
                });

                // 检查响应状态
                if (!response.ok) {
                    throw new Error(`HTTP错误! 状态码: ${response.status}`);
                }

                // 解析响应数据
                const result = await response.text();
                outputTextarea.value = result;

                // 高亮显示结果
                switchToHighlight();
            } catch (error) {
                outputTextarea.value = `请求失败:\n${error.message}`;
            }
        } else {
            outputTextarea.value = '请输入代码后再发送';
        }
    });

    // 代码注释按钮功能
    commentBtn.addEventListener('click', () => {
        const input = inputTextarea.value;
        if (input) {
            // 简单的代码注释功能示例
            const lines = input.split('\n');
            const commentedLines = lines.map(line => {
                // 检查行是否为空或已经有注释
                if (!line.trim() || line.trim().startsWith('//')) {
                    return line;
                }
                return `// ${line}`;
            });
            outputTextarea.value = commentedLines.join('\n');
        } else {
            outputTextarea.value = '请输入代码后再添加注释';
        }
    });

    // 复制按钮功能
    copyBtn.addEventListener('click', () => {
        const output = outputTextarea.value;
        if (output) {
            navigator.clipboard.writeText(output)
                .then(() => {
                    // 显示复制成功提示
                    const originalText = copyBtn.textContent;
                    copyBtn.textContent = '复制成功!';
                    copyBtn.style.backgroundColor = 'var(--success-color)';

                    setTimeout(() => {
                        copyBtn.textContent = originalText;
                        copyBtn.style.backgroundColor = '';
                    }, 2000);
                })
                .catch(err => {
                    console.error('复制失败:', err);
                    outputTextarea.value = '复制失败，请手动复制';
                });
        } else {
            outputTextarea.value = '没有可复制的内容';
        }
    });

    // 转换选项卡功能
    function executeConvertFunction() {

        // 获取代码选项卡中的输入内容
        const codeshow_ecode_1 = document.getElementById('codeshow_ecode_1');

        if (outputTextarea.value) {
            try {
                // 尝试将输入的内容作为HTML渲染
                codeshow_ecode_1.innerHTML = outputTextarea.value;
                trans("codeshow");
            } catch (error) {
                codeshow_ecode_1.innerHTML = `<div style="color: red;">渲染错误: ${error.message}</div>`;
            }
        } else {
            codeshow_ecode_1.innerHTML = '<div style="color: #6b7280;">请在代码选项卡中输入HTML内容，切换到转换选项卡后将自动渲染</div>';
        }
    }

    // 设置选项卡功能
    const themeSelect = document.getElementById('theme');
    const fontSizeSlider = document.getElementById('font-size');
    const fontSizeValue = document.getElementById('font-size-value');
    const autoSaveCheckbox = document.getElementById('auto-save');
    const saveSettingsBtn = document.getElementById('save-settings');

    // 初始化设置
    const savedSettings = JSON.parse(localStorage.getItem('codeToolSettings')) || {};

    if (savedSettings.theme) {
        themeSelect.value = savedSettings.theme;
        if (savedSettings.theme === 'dark') {
            document.body.classList.add('dark-mode');
        }
    }

    if (savedSettings.fontSize) {
        fontSizeSlider.value = savedSettings.fontSize;
        fontSizeValue.textContent = `${savedSettings.fontSize}px`;
        document.body.style.fontSize = `${savedSettings.fontSize}px`;
    }

    if (savedSettings.autoSave) {
        autoSaveCheckbox.checked = savedSettings.autoSave;
    }

    // 字体大小滑块变化
    fontSizeSlider.addEventListener('input', () => {
        const fontSize = fontSizeSlider.value;
        fontSizeValue.textContent = `${fontSize}px`;
        document.body.style.fontSize = `${fontSize}px`;
        document.querySelectorAll('#output, #output-highlight').forEach(el => {
            el.style.fontSize = `${fontSize}px`;
        });
    });

    // 保存设置按钮
    saveSettingsBtn.addEventListener('click', () => {
        const settings = {
            theme: themeSelect.value,
            fontSize: fontSizeSlider.value,
            autoSave: autoSaveCheckbox.checked
        };

        // 应用主题
        if (settings.theme === 'dark') {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }

        // 保存到本地存储
        localStorage.setItem('codeToolSettings', JSON.stringify(settings));

        // 显示保存成功提示
        const originalText = saveSettingsBtn.textContent;
        saveSettingsBtn.textContent = '保存成功!';
        saveSettingsBtn.style.backgroundColor = 'var(--success-color)';

        setTimeout(() => {
            saveSettingsBtn.textContent = originalText;
            saveSettingsBtn.style.backgroundColor = '';
        }, 2000);
    });
});

// disableEdit(outputDiv);