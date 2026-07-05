// @file highlight.js
//
// ---------------------                                                   ---------------------------------
// | switchToHighlight |                                                   | id: output-highlight on click |
// ---------------------                                                   ---------------------------------
//           |                                                                              |
//           |                                                                              |
//  -------------------                 -------------------                          ----------------                         --------------------
//  | highlightOutput | <-------------- | 处理注释，系统命令 |                         | switchToEdit | <---------------------- | getCursorPosition |
//  -------------------                 -------------------                          ----------------                         --------------------
//           |                                                                              |
//           |                                                                              |                                 ---------------------
//    ---------------                    -----------------                                  | <------------------------------ | getCursorPosition |                     
//    | processLine | -----------------> |    语法处理    |                                  |                                 ---------------------
//    ---------------                    -----------------                                  |
//                                              |                                           |                                -------------------------
//                                              |                                           | <----------------------------- |  outputDiv.scrollTop  |                           
//          -----------------                   |                                           |                                 -------------------------
//          | processStrings | --- 处理字符串 ---|                                           |
//          -----------------                   |                                           |                            ---------------------------------                                                     -----------------------
//                                              |                                           | -------------------------> |  outputTextarea.style.display | 
//          -----------------                   |                                           |                            ---------------------------------                                                       
//          | processNumber | ---- 处理数字 -----|                                           | 
//          -----------------                   |                                           |                               ------------------------------
//                                              |                                           | ----------------------------> |  outputTextarea.scrollTop  | 
//          -------------------                 |                                           |                               ------------------------------
//          | processConstant | --- 处理常量 ----|                                           | 
//          -------------------                 |                                           |                                 -----------------------
//                                              |                                           | ------------------------------> |  setCursorPosition  | 
//          -------------------                 |                                           |                                 -----------------------
//          | processFunction | --- 处理函数 ----|                                           | 
//          -------------------                 |                                           | 
//                                      -----------------
//                                      |  processLine  |
//                                      -----------------                                             

// 高亮颜色
const color = {
	number: "",
	sysCommand: "#",
	sysCommandIgnore: "#",
	dataType: "#",
	function: "#",
	constant: "#",
	remark: "#",
	quto: "#"
};

const e_key = {
	sys_command_need_brackets: ["如果真", "如果", "判断开始",
		"计次循环首", "判断循环首", "变量循环首"],			// #0000FF 命令可能带括号
	sys_command: ["程序集变量", "局部变量", "参数"],										 // #0000FF
	sys_command_ignore_need_brackets: ["如果真结束", "如果结束", "判断结束",
		"计次循环尾", "判断循环尾", "变量循环尾"], // #808080 命令可能带括号
	sys_flowline: ["程序集", "子程序"],																	// #000080
	sys_flowline_ignore: ["版本", "支持库"],																		// #808080
	sys_data_type: ["整数型", "文本型", "子程序指针", "逻辑型", "整数型",
		"双精度小数型", "小数型", "长整数型",
		"短整数型", "短整数型", "字节型"]	// #DECB6B
};

// 中英文符号
const punct = "!\\\"#$%&'()*+,\\-./:;<=>?@[\\\\]^_`{|}~，。！？；：（）【】「」《》“”‘’";
// 字母数组部分符号
const allowedChars = `a-zA-Z_\u4e00-\u9fff#\\"“’`;
// 命名要求 中文、英文、数字，不能有空白字符，不能以数字开头，允许下划线
const name_regex = `[a-zA-Z_\u4e00-\u9fff][a-zA-Z0-9_\u4e00-\u9fff]*`;
function get_span_regex(r) { return `\\s*<\\s*span\\s*style\\s*=\\s*\["'\]\\s*color\\s*:\\s*#[0-9a-fA-F]{6}\\s*\["'\]\\s*>\\s*` + r + `\\s*<\\s*/\\s*span\\s*>\\s*`; }
// 有效的一段字符
const validSegment = `[ \t\r\f\v]*[^\n]*[ \t\r\f\v]*`;

// HTML 转码
function escapeHTML(str) {
	if (!str) return '';
	return str
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#039;');
}

// 处理数字
function processNumber(temp) {
	// 分割处理非字符串区域
	const parts = temp.split(/(<span[^>]*>.*?<\/span>)/g);
	return parts.map((part, index) => {
		if (index % 2 === 1) return part;
		return part.replace(
			new RegExp(`(?<![${allowedChars}\\d])\\d+(?![${allowedChars}\\d])`, 'g'),
			match => wrapColor(match, color.number)
		);
	}).join('');
}

// 处理数据类型
function processDataType(temp) {
	// 分割处理非字符串区域
	const parts = temp.split(/(<span[^>]*>.*?<\/span>)/g);
	return parts.map((part, index) => {
		if (index % 2 === 1) return part;
		return part.replace(
			new RegExp(`(?<![^\\s${punct}\\S])[ 　]*(?:${e_key.sys_data_type.join("|")})[ 　]*(?![^\\s${punct}\\S])`, 'g'),
			match => wrapColor(match, color.dataType)
		);
	}).join('');
}

// 处理函数
function processFunction(temp) {
	return temp.replace(new RegExp(`(${name_regex})\\s*[（(]`, 'g'), (match, p1) => {
		if (/^\d/.test(p1) || e_key.sys_command_need_brackets.concat(e_key.sys_command_ignore_need_brackets)
			.includes(p1)) return match;
		const bracketPair = match.includes('（') ? '）' : ')';
		if (match.includes(bracketPair)) return match;
		return wrapColor(p1, color.function) + match.slice(p1.length);
	});
}

// 处理常量
function processConstant(temp) {
	const parts = temp.split(/(<span[^>]*>.*?<\/span>)/g);
	return parts.map((part, index) => {
		if (index % 2 === 1) return part;
		return part.replace(/(?<![a-zA-Z_\u4e00-\u9fff#"'“‘’])#[\u4e00-\u9fa5a-zA-Z_][\u4e00-\u9fa5a-zA-Z0-9_]*/g, match =>
			wrapColor(match, color.constant)
		);
	}).join('');
}

// 处理.子程序的注释
// .子程序 函数名 , 参数一 , 参数二 , 注释
function processSubroutineComment(temp) {
	const subroutineRegex = `^\\s*\\.子程序\\s+(${name_regex})\\s*[,，]\\s*(${name_regex}||${get_span_regex(name_regex)})\\s*[,，]\\s*(${validSegment}|)\\s*[,，]\\s*(.*)$`;
	const match = temp.match(subroutineRegex);
	// 如果匹配成功且注释内容不为空，对注释内容进行高亮处理
	if (match && match[4]) {
		return temp.replace(match[4], wrapColor(match[4], color.remark));
	}
	return temp;
}

// 处理参数的注释
// .参数 参数名, 类型, 参考 可空 数组, 注释
function processParameterComment(temp) {
	const subroutineRegex = `^\\s*\\.参数\\s+(${name_regex})\\s*[,，]\\s*(${name_regex}||${get_span_regex(name_regex)})\\s*[,，]\\s*(${validSegment}|)\\s*[,，]\\s*(.*)$`;
	const match = temp.match(subroutineRegex);
	// 如果匹配成功且注释内容不为空，对注释内容进行高亮处理
	if (match && match[4]) {
		return temp.replace(match[4], wrapColor(match[4], color.remark));
	}
	return temp;
}

// 处理一行（处理系统指令和注释）
function processLine(line, dataTyprOnly = false) {
	line = escapeHTML(line);

	if (dataTyprOnly) return processDataType(line);

	let result = line;
	// 注释已排除
	result = processStrings(result); 	// 处理字符串	// 后续请用 const parts = temp.split(/(<span[^>]*>.*?<\/span>)/g);
	result = processNumber(result)		// 处理数字		// 
	result = processDataType(result)	// 处理数据类型
	result = processConstant(result)	// 处理常量
	result = processFunction(result)	// 处理函数

	return result;
}

// 处理字符串
function processStrings(line) {
	let result = line;
	const quotePairs = [{
		left: '“',
		right: '”',
		color: color.quto
	},
	{
		left: '&quot;',
		right: '&quot;',
		color: color.quto
	}];

	let currentQuote = null;
	let startIndex = -1;

	for (let i = 0; i < line.length; i++) {
		if (!currentQuote) {
			const found = quotePairs.find(q =>
				line.substring(i, i + q.left.length) === q.left
			);
			if (found) {
				currentQuote = found;
				startIndex = i;
				i += found.left.length - 1; // 跳过整个左引号
			}
		} else {
			if (line.substring(i, i + currentQuote.right.length) === currentQuote.right) {
				const content = line.slice(startIndex, i + currentQuote.right.length);
				result = result.replace(content, wrapColor(content, currentQuote.color));
				i += currentQuote.right.length - 1; // 使用currentQuote替代quotePairs[i]
				currentQuote = null;
			} else if (quotePairs.some(q =>
				line.substring(i, i + q.left.length) === q.left ||
				line.substring(i, i + q.right.length) === q.right
			)) {
				currentQuote = null; // 遇到其他引号中断匹配
			}
		}
	}
	return result;
}

// 删首尾空
function trim(string) {
	var i = 0;
	str = string;
	for (i = 0; i < str.length; i++) {
		if (str.charAt(i) != " ") {
			break
		};
	}
	str = str.substring(i, str.length);
	for (i = str.length - 1; i >= 0; i--) {
		if (str.charAt(i) != " ") {
			break
		};
	}
	str = str.slice(0, i + 1);
	return str;
}

// 包装颜色
function wrapColor(text, color) {
	return "<span style='color:" + color + "'>" + text + "</span>";
}

// 高亮输出
function highlightOutput() {
	const outputTextarea = document.getElementById('output');
	const outputDiv = document.getElementById('output-highlight');

	// 如果高亮div不存在，则创建
	if (!outputDiv) {
		const outputContainer = outputTextarea.parentNode;
		const newDiv = document.createElement('div');
		newDiv.id = 'output-highlight';
		newDiv.style.cssText = `
      width: 100%;
      height: 300px;
      padding: 12px;
      border: 1px solid var(--border-color);
      border-radius: 6px;
      background-color: var(--background-color);
      color: var(--text-color);
      font-family: 'Consola', 'Courier New', Courier, monospace;
      font-size: 14px;
      resize: none;
      overflow: auto;
      white-space: pre-wrap;
      display: none;
    `;
		outputContainer.insertBefore(newDiv, outputTextarea);
	}

	// 获取textarea的值并进行高亮处理
	const code = outputTextarea.value;

	// 使用正则表达式匹配```e代码块和其余内容
	const parts = code.split(/(^\s*```e\s*$[\s\S]*?^\s*```\s*$)/gm);
	let highlightedCode = '';

	for (let i = 0; i < parts.length; i++) {
		const part = parts[i];

		// 检查是否是```e代码块
		const codeBlockMatch = part.match(/^\s*```e\s*$([\s\S]*?)^\s*```\s*$/m);

		if (codeBlockMatch) {
			// 是代码块，提取内容并进行高亮处理
			const codeContent = codeBlockMatch[1];
			const lines = codeContent.split('\n');

			for (let j = 0; j < lines.length; j++) {
				const line = lines[j];

				const prevLine = j > 0 ? lines[j - 1] : '';
				const nextLine = j < lines.length - 1 ? lines[j + 1] : '';
				let nextIndentLevel = Math.floor((prevLine.match(/^\s*/) || [''])[0].length / 4);
				let lastIndentLevel = Math.floor((nextLine.match(/^\s*/) || [''])[0].length / 4);

				// 空行，缩进引导线
				if (line.trim() === '') {
					let guidesHTML = '';
					for (let level = 0; level < Math.max(nextIndentLevel, lastIndentLevel); level++) {
						guidesHTML += `<div class="indent-guide" style="left:${level * 2.5 + 0.5}em"></div>`;
					}
					highlightedCode += `<div style="position:relative">${guidesHTML}\n</div>`;
					continue;
				}

				// 计算缩进层级
				const indent = line.match(/^\s*/)[0].length;
				const indentLevel = Math.floor(indent / 4);

				// 生成缩进引导线
				let guidesHTML = '';
				for (let level = 0; level < indentLevel; level++) {
					guidesHTML += `<div class="indent-guide" style="left:${level * 2.5 + 0.5}em"></div>`;
				}

				// 处理特殊关键字
				let highlightedLine = line;

				// 预处理：处理注释
				const commentIndex = line.indexOf("'");
				if (commentIndex !== -1) {
					const codePart = line.substring(0, commentIndex);
					const commentPart = line.substring(commentIndex);
					highlightedLine = processLine(codePart, line.trim().startsWith(".参数") ? true : false) + wrapColor(commentPart, color.remark);
				} else {
					highlightedLine = processLine(line, line.trim().startsWith(".参数") ? true : false);
				}

				// 处理系统命令
				if (line.trim().startsWith(".")) {
					const parts = line.trim().split(" ");
					const command = parts[0].substring(1);

					const commandIndex = [command.indexOf('（'), command.indexOf('(')].find(i => i > -1);
					if (commandIndex > -1) {
						command = command.substring(0, commandIndex);
					}

					const spaceCount = line.match(/^\s*/)[0].length;
					const lineTrim = line.substring(0, spaceCount);

					if (e_key.sys_command.concat(e_key.sys_command_need_brackets).includes(command)) {
						highlightedLine = processParameterComment(highlightedLine);
						highlightedLine = lineTrim + wrapColor(parts[0], color.sysCommand) + highlightedLine.substring(spaceCount + parts[0].length);
					} else if (e_key.sys_command_ignore_need_brackets.includes(command)) {
						highlightedLine = lineTrim + wrapColor(parts[0], color.sysCommandIgnore) + highlightedLine.substring(spaceCount + parts[0].length);
					} else if (e_key.sys_flowline.includes(command)) {
						highlightedLine = processSubroutineComment(highlightedLine);
						highlightedLine = lineTrim + wrapColor(parts[0], color.sysCommandIgnore) + highlightedLine.substring(spaceCount + parts[0].length);
					} else if (e_key.sys_flowline_ignore.includes(command)) {
						highlightedLine = lineTrim + wrapColor(parts[0], "#808080") + line.substring(spaceCount + parts[0].length);
					}
				}

				highlightedCode += `<div style="position:relative">${guidesHTML}${highlightedLine}</div>`;
			}
		} else { // 不是代码块，原样输出（进行HTML转义）
			highlightedCode += escapeHTML(part);
		}
	}

	// 更新高亮div的内容
	document.getElementById('output-highlight').innerHTML = highlightedCode;
}

// 设置 textarea 光标位置
function setCursorPosition(textarea, pos) {
	// 确保位置在有效范围内
	if (pos < 0) pos = 0;
	if (pos > textarea.value.length) pos = textarea.value.length;

	// 设置光标位置
	textarea.selectionStart = pos;
	textarea.selectionEnd = pos;
}

// 切换到编辑模式
// Bug: 错位
function switchToEdit() {
	if (outputDiv.style.display == 'none') return;

	const cursorPosition = getCursorPosition(outputDiv)
	const temp = outputDiv.scrollTop / (outputDiv.scrollHeight - outputDiv.clientHeight);
	outputDiv.style.display = 'none';
	outputTextarea.style.display = 'block';
	outputTextarea.focus()
	outputTextarea.scrollTop = temp * (outputTextarea.scrollHeight - outputTextarea.clientHeight); // 同步滚轮位置
	setCursorPosition(outputTextarea, cursorPosition); // 同步光标位置
}

// 获取光标（Div）在文本中的位置索引
function getCursorPosition(Div) {
	const selection = window.getSelection();
	// 检查是否有选中范围且在当前元素内
	if (selection.rangeCount === 0 || !Div.contains(selection.focusNode)) {
		return -1; // 光标不在当前元素内
	}
	const range = selection.getRangeAt(0);
	const preCaretRange = range.cloneRange();
	// 从元素开始到光标位置创建一个范围
	preCaretRange.selectNodeContents(Div);
	preCaretRange.setEnd(range.endContainer, range.endOffset);
	// 返回光标前的文本长度，即光标位置索引
	return preCaretRange.toString().length;
}

// 切换到高亮显示模式
function switchToHighlight() {
	if (outputTextarea.style.display == 'none') return;

	const temp = outputTextarea.scrollTop / (outputTextarea.scrollHeight - outputTextarea.clientHeight);
	outputTextarea.style.display = 'none';
	outputDiv.style.display = 'block';

	highlightOutput(); // 先高亮代码
	outputDiv.scrollTop = temp * (outputDiv.scrollHeight - outputDiv.clientHeight); // 同步滚轮位置
}