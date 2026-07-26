// ==UserScript==
// @name         蓝奏云自动填写密码
// @namespace    http://tampermonkey.net/
// @version      1.5
// @description  自动提取蓝奏云URL中的密码参数
// @author       Rikka
// @match        *://lanzou.com/u
// @match        *://www.lanzou.com/u
// @match        *://www.lanzou.com/account.php*
// @match        *://up.woozooo.com/u
// @match        *://up.woozooo.com/mydisk.php*
// @match        *://pc.woozooo.com/u
// @match        *://pc.woozooo.com/mydisk.php*
// @match        *://pan.lanzou.com/*
// @match        *://*.lanzoub.com/*
// @match        *://*.lanzoue.com/*
// @match        *://*.lanzouf.com/*
// @match        *://*.lanzouh.com/*
// @match        *://*.lanzoui.com/*
// @match        *://*.lanzouj.com/*
// @match        *://*.lanzoul.com/*
// @match        *://*.lanzoum.com/*
// @match        *://*.lanzouo.com/*
// @match        *://*.lanzoup.com/*
// @match        *://*.lanzouq.com/*
// @match        *://*.lanzout.com/*
// @match        *://*.lanzouu.com/*
// @match        *://*.lanzouv.com/*
// @match        *://*.lanzouw.com/*
// @match        *://*.lanzoux.com/*
// @match        *://*.lanzouy.com/*
// @match        *://*.lanzob.com/*
// @match        *://*.lanzoe.com/*
// @match        *://*.lanzof.com/*
// @match        *://*.lanzoh.com/*
// @match        *://*.lanzoi.com/*
// @match        *://*.lanzoj.com/*
// @match        *://*.lanzol.com/*
// @match        *://*.lanzom.com/*
// @match        *://*.lanzoo.com/*
// @match        *://*.lanzop.com/*
// @match        *://*.lanzoq.com/*
// @match        *://*.lanzot.com/*
// @match        *://*.lanzov.com/*
// @match        *://*.lanzow.com/*
// @match        *://*.lanzox.com/*
// @match        *://*.lanzoy.com/*
// @match        *://*.lanzb.com/*
// @match        *://*.lanze.com/*
// @match        *://*.lanzf.com/*
// @match        *://*.lanzh.com/*
// @match        *://*.lanzi.com/*
// @match        *://*.lanzj.com/*
// @match        *://*.lanzl.com/*
// @match        *://*.lanzm.com/*
// @match        *://*.lanzo.com/*
// @match        *://*.lanzp.com/*
// @match        *://*.lanzq.com/*
// @match        *://*.lanzt.com/*
// @match        *://*.lanzv.com/*
// @match        *://*.lanzw.com/*
// @match        *://*.lanzx.com/*
// @match        *://*.lanzy.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ==================== 常量定义 ====================
    // 可能包含密码的 URL 参数名列表（含常见拼写错误）
    const PASSWORD_PARAM_NAMES = ['password', 'pwd', 'passowrd', 'passwrod', 'pd', 'p'];
    // 密码截断字符：遇到这些字符时，后续部分视为无效内容，予以截断
    const TRUNCATE_CHARS = "#$%^*()+=|\\\"':;<>,?/";
    // 触发自动填充后，等待页面响应的延时（毫秒）
    const SUBMIT_DELAY = 800;
    // 防止无限重定向的最大 "?password=" 出现次数
    const MAX_REDIRECT_ATTEMPTS = 3;

    // ==================== 工具函数 ====================

    /**
     * 从当前 URL 查询参数中提取密码
     * - 依次尝试预定义的参数名
     * - 使用 decodeURIComponent 解码（支持中文密码）
     * - 遇到截断字符时，舍弃其后所有内容
     * @returns {string|null} 提取到的密码，未找到时返回 null
     */
    function getPasswordFromURL() {
        const urlParams = new URLSearchParams(window.location.search);

        for (const name of PASSWORD_PARAM_NAMES) {
            const rawValue = urlParams.get(name);
            if (rawValue === null) continue;

            // 解码 URL 编码（如 %E5%AF%86%E7%A0%81 -> 密码）
            let decodedValue = decodeURIComponent(rawValue);

            // 查找第一个截断字符并截断
            let truncateIndex = -1;
            for (let i = 0; i < decodedValue.length; i++) {
                if (TRUNCATE_CHARS.includes(decodedValue[i])) {
                    truncateIndex = i;
                    break;
                }
            }
            if (truncateIndex !== -1) {
                decodedValue = decodedValue.substring(0, truncateIndex);
            }

            // 返回非空密码
            if (decodedValue.trim() !== '') {
                return decodedValue;
            }
        }
        return null;
    }

    /**
     * 处理“链接中直接拼接密码”的情况（即 URL 中包含“密码:XXX”）
     * 解析密码并重定向到标准带参数形式：原链接?password=XXX
     */
    function redirectWithPassword() {
        // 防止无限重定向：若 URL 中已多次出现 ?password= 则停止
        const passwordParamCount = (window.location.href.match(/\?password=/g) || []).length;
        if (passwordParamCount > MAX_REDIRECT_ATTEMPTS) return;

        // 解码当前完整 URL，以便匹配中文“密码”
        const decodedUrl = decodeURIComponent(window.location.href);

        // 匹配“密码:XXX”或“密码：XXX”，提取密码部分。
        // 密码可以包含常见字符，但会在后面的截断字符处或空白处停止。
        const passwordMatch = decodedUrl.match(
            /密码[：:]\s*([^\s~`#$%^&*()=+:?"|\\';/,<>?]+?)(?=[\s~`#$%^&*()=+:?"|\\';/,<>?]|$)/iu
        );

        if (passwordMatch && passwordMatch[1]) {
            // 取“密码”之前的部分作为基 URL
            const baseUrl = decodedUrl.split('密码')[0].trim();
            // 构造新 URL，对密码进行编码避免特殊字符问题
            const newUrl = `${baseUrl}?password=${encodeURIComponent(passwordMatch[1])}`;
            window.location.replace(newUrl);
        }
    }

    /**
     * 尝试调用页面中的下载函数（旧版/新版兼容）
     */
    function invokeNativeDownload() {
        if (typeof window.file === 'function') {
            window.file();
        }
        if (typeof window.down_p === 'function') {
            window.down_p();
        }
    }

    /**
     * 自动填充密码输入框，并触发下载
     */
    function fillPasswordAndDownload() {
        const password = getPasswordFromURL();
        if (!password) return;

        const pwdInput = document.getElementById('pwd');
        if (!pwdInput) return;

        // 填入密码并触发 input 事件，使页面逻辑感知到输入
        pwdInput.value = password;
        pwdInput.dispatchEvent(new Event('input', { bubbles: true }));

        // 延时后尝试触发下载按钮，若找不到按钮则直接调用原生下载函数
        setTimeout(() => {
            const downloadBtn = document.querySelector('.passwddiv-btn') || document.querySelector('.btnpwd');
            if (downloadBtn) {
                downloadBtn.click();
            } else {
                invokeNativeDownload();
            }
        }, SUBMIT_DELAY);
    }

    // ==================== 主流程 ====================

    // 检测 URL 中是否含有“密码”字样（在地址栏中通常为编码形式）
    const hasEncodedPassword = window.location.href.indexOf(encodeURIComponent('密码')) !== -1;

    if (hasEncodedPassword) {
        // 情况 1：URL 中包含“密码:XXX” → 解析并跳转为标准参数形式
        redirectWithPassword();
    } else if (document.readyState === 'complete') {
        // 情况 2：页面已完全加载，尝试提取参数密码并自动下载
        fillPasswordAndDownload();
    } else {
        // 等待页面加载完成后再尝试
        window.addEventListener('load', fillPasswordAndDownload);
    }

})();