#!/usr/bin/env python3
"""
测试HTML解析功能
"""
import re
from bs4 import BeautifulSoup
from typing import Dict, Any

def parse_html_content(html: str) -> Dict[str, Any]:
    """解析HTML内容"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 查找最新的release - GitHub现在使用Box结构
    # 尝试多种选择器
    latest_release_section = None
    
    # 方法1: 查找包含release信息的Box
    boxes = soup.find_all('div', {'data-view-component': re.compile(r'Box', re.I)})
    print(f"找到 {len(boxes)} 个Box组件")
    for box in boxes:
        # 查找包含tag链接的Box
        tag_link = box.find('a', href=re.compile(r'/releases/tag/'))
        if tag_link:
            latest_release_section = box
            print(f"找到包含tag链接的Box")
            break
    
    # 方法2: 查找section或div with release class
    if not latest_release_section:
        latest_release_section = soup.find('section', {'class': 'release'})
        if latest_release_section:
            print("找到section.release")
    if not latest_release_section:
        latest_release_section = soup.find('div', {'class': 'release'})
        if latest_release_section:
            print("找到div.release")
    
    # 方法3: 查找包含markdown-body的元素（release描述通常在这里）
    if not latest_release_section:
        latest_release_section = soup.find('div', {'class': 'markdown-body'})
        if latest_release_section:
            print("找到markdown-body，向上查找父容器")
            # 向上查找父容器
            for _ in range(5):
                if latest_release_section.parent:
                    latest_release_section = latest_release_section.parent
                    if latest_release_section.find('a', href=re.compile(r'/releases/tag/')):
                        print("在父容器中找到tag链接")
                        break
    
    if not latest_release_section:
        raise Exception("无法在页面中找到release信息")
    
    # 获取tag name - 尝试多种方式
    tag_name = 'unknown'
    
    # 方法1: 查找releases/tag链接
    tag_link = latest_release_section.find('a', href=re.compile(r'/releases/tag/'))
    if tag_link:
        tag_name = tag_link.get_text(strip=True)
        print(f"通过tag链接获取版本: {tag_name}")
    
    # 方法2: 查找包含tag/version class的元素
    if tag_name == 'unknown':
        tag_elem = latest_release_section.find(['a', 'span'], class_=re.compile(r'tag|version', re.I))
        if tag_elem:
            tag_name = tag_elem.get_text(strip=True)
            print(f"通过tag/version class获取版本: {tag_name}")
    
    # 方法3: 查找f1 text-bold class（GitHub现在的标题样式）
    if tag_name == 'unknown':
        bold_elem = latest_release_section.find(['span', 'a'], class_=re.compile(r'f1.*text-bold', re.I))
        if bold_elem:
            tag_name = bold_elem.get_text(strip=True)
            print(f"通过f1 text-bold获取版本: {tag_name}")
    
    # 获取所有assets
    assets = []
    
    # 方法1: 查找releases/download链接
    asset_links = latest_release_section.find_all('a', href=re.compile(r'/releases/download/'))
    print(f"找到 {len(asset_links)} 个releases/download链接")
    
    for link in asset_links:
        name = link.get_text(strip=True)
        href = link.get('href', '')
        if href.startswith('/'):
            href = f"https://github.com{href}"
        elif href.startswith('http'):
            pass
        else:
            continue
        
        if name:
            assets.append({
                'name': name,
                'browser_download_url': href
            })
    
    # 方法2: 如果没有找到assets，尝试从include-fragment获取
    if not assets:
        include_fragments = latest_release_section.find_all('include-fragment')
        print(f"在release section中找到 {len(include_fragments)} 个include-fragment")
        for fragment in include_fragments:
            src = fragment.get('src', '') or fragment.get('data-deferred-src', '')
            if 'expanded_assets' in src:
                # 这是一个动态加载的assets列表，需要额外请求
                print(f"检测到动态加载的assets，尝试获取: {src}")
                print("注意: 实际应用中会请求此URL获取assets列表")
                print(f"  Fragment src: {src}")
                break
        
        # 如果在release section中没找到，在整个页面中查找
        if not assets:
            all_fragments = soup.find_all('include-fragment')
            print(f"在整个页面中找到 {len(all_fragments)} 个include-fragment")
            for fragment in all_fragments:
                src = fragment.get('src', '') or fragment.get('data-deferred-src', '')
                if 'expanded_assets' in src:
                    print(f"在页面中找到expanded_assets fragment: {src}")
                    break
    
    print(f"HTML爬取成功，版本: {tag_name}")
    return {
        'tag_name': tag_name,
        'assets': assets
    }

if __name__ == '__main__':
    # 读取HTML文件
    with open('release.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 解析HTML
    try:
        result = parse_html_content(html_content)
        print("\n" + "="*50)
        print("解析结果:")
        print(f"Tag: {result['tag_name']}")
        print(f"Assets数量: {len(result['assets'])}")
        for i, asset in enumerate(result['assets'], 1):
            print(f"  {i}. {asset['name']}")
            print(f"     URL: {asset['browser_download_url']}")
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()
