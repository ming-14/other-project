/* global HTMLLint, minify */
(function() {
  'use strict';

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHTML(str) {
    return (str + '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function getOptions() {
    return {
      removeIgnored:                  byId('remove-ignored').checked,
      removeComments:                 byId('remove-comments').checked,
      removeCommentsFromCDATA:        byId('remove-comments-from-cdata').checked,
      removeCDATASectionsFromCDATA:   byId('remove-cdata-sections-from-cdata').checked,
      collapseWhitespace:             byId('collapse-whitespace').checked,
      conservativeCollapse:           byId('conservative-collapse').checked,
      collapseBooleanAttributes:      byId('collapse-boolean-attributes').checked,
      removeAttributeQuotes:          byId('remove-attribute-quotes').checked,
      removeRedundantAttributes:      byId('remove-redundant-attributes').checked,
      useShortDoctype:                byId('use-short-doctype').checked,
      removeEmptyAttributes:          byId('remove-empty-attributes').checked,
      removeEmptyElements:            byId('remove-empty-elements').checked,
      removeOptionalTags:             byId('remove-optional-tags').checked,
      removeScriptTypeAttributes:     byId('remove-script-type-attributes').checked,
      removeStyleLinkTypeAttributes:  byId('remove-style-link-type-attributes').checked,
      caseSensitive:                  byId('case-sensitive').checked,
      keepClosingSlash:               byId('keep-closing-slash').checked,
      minifyJS:                       byId('minify-js').checked,
      processScripts:                 byId('minify-js-templates').checked ? byId('minify-js-templates-type').value : false,
      minifyCSS:                      byId('minify-css').checked,
      minifyURLs:                     byId('minify-urls').checked ? { site:byId('minify-urls-siteurl').value } : false,
      lint:                           byId('use-htmllint').checked ? new HTMLLint() : null,
      maxLineLength:                  parseInt(byId('max-line-length').value, 10)
    };
  }

  function commify(str) {
    return String(str)
      .split('').reverse().join('')
      .replace(/(...)(?!$)/g, '$1,')
      .split('').reverse().join('');
  }

  function minifyTextarea() {
    try {
      var options = getOptions(),
          lint = options.lint,
          originalValue = byId('input').value,
          minifiedValue = minify(originalValue, options),
          diff = originalValue.length - minifiedValue.length,
          savings = originalValue.length ? ((100 * diff) / originalValue.length).toFixed(2) : 0;

      byId('output').value = minifiedValue;

      byId('stats').innerHTML =
        '<span class="success">' +
          'Original size: <strong>' + commify(originalValue.length) + '</strong>' +
          '. Minified size: <strong>' + commify(minifiedValue.length) + '</strong>' +
          '. Savings: <strong>' + commify(diff) + ' (' + savings + '%)</strong>.' +
        '</span>';

      if (lint) {
        lint.populate(byId('report'));
      }
    }
    catch (err) {
      byId('output').value = '';
      byId('stats').innerHTML = '<span class="failure">' + escapeHTML(err) + '</span>';
    }
  }

  byId('max-line-length').oninput = function() { minifyTextarea(); };
  byId('minify-btn').onclick = function() { minifyTextarea(); };

  function setCheckedAttrOnCheckboxes(attrValue) {
    var checkboxes = byId('options').getElementsByTagName('input');
    for (var i = checkboxes.length; i--; ) {
      checkboxes[i].checked = attrValue;
    }
  }

  byId('select-all').onclick = function() {
    setCheckedAttrOnCheckboxes(true);
    return false;
  };

  byId('select-none').onclick = function() {
    setCheckedAttrOnCheckboxes(false);
    return false;
  };

  byId('select-safe').onclick = function() {
    setCheckedAttrOnCheckboxes(true);
    var inputEls = byId('options').getElementsByTagName('input');
    inputEls[10].checked = false;
    inputEls[11].checked = false;
    inputEls[18].checked = false;
    return false;
  };

  // 文件上传功能
  byId('upload-btn').onclick = function() {
    byId('file-input').click();
  };

  byId('file-input').onchange = function(e) {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = function(e) {
        byId('input').value = e.target.result;
      };
      reader.readAsText(file);
    }
  };

  // 粘贴剪贴板功能
  byId('paste-btn').onclick = async function() {
    try {
      const text = await navigator.clipboard.readText();
      byId('input').value = text;
    } catch (err) {
      console.error('无法读取剪贴板内容: ', err);
    }
  };

  // 复制结果功能
  byId('copy-btn').onclick = async function() {
    try {
      const text = byId('output').value;
      await navigator.clipboard.writeText(text);
      alert('复制成功!');
    } catch (err) {
      console.error('无法复制到剪贴板: ', err);
    }
  };

  // 下载文件功能
  byId('download-btn').onclick = function() {
    const text = byId('output').value;
    const blob = new Blob([text], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'minified.html';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

})();

/* jshint ignore:start */

var _gaq = _gaq || [];
_gaq.push(['_setAccount', 'UA-1128111-22']);
_gaq.push(['_trackPageview']);



/* jshint ignore:end */