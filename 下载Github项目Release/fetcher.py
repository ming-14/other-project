import re
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from bs4 import BeautifulSoup

from config import Config, RequestType


class ReleaseCache:
    """Release信息缓存"""
    
    def __init__(self, ttl: int = 3600):
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl
    
    def get(self, repo: str) -> Optional[Dict[str, Any]]:
        if repo in self._cache:
            data, timestamp = self._cache[repo]
            if time.time() - timestamp < self._ttl:
                return data
            del self._cache[repo]
        return None
    
    def set(self, repo: str, data: Dict[str, Any]) -> None:
        self._cache[repo] = (data, time.time())
    
    def invalidate(self, repo: str = None) -> None:
        if repo:
            self._cache.pop(repo, None)
        else:
            self._cache.clear()
    
    def is_valid(self, repo: str) -> bool:
        if repo in self._cache:
            _, timestamp = self._cache[repo]
            return time.time() - timestamp < self._ttl
        return False
    
    def get_age(self, repo: str) -> Optional[int]:
        if repo in self._cache:
            _, timestamp = self._cache[repo]
            return int(time.time() - timestamp)
        return None


class ReleaseFetcher(ABC):
    """Release信息获取器抽象基类"""
    
    def __init__(self, config: Config, http_client):
        self.config = config
        self.http_client = http_client
    
    @abstractmethod
    def fetch(self, repo: str) -> Dict[str, Any]:
        pass
    
    def _get_headers(self, browser: bool = False) -> Dict[str, str]:
        if browser:
            headers = dict(self.config.browser_headers)
        else:
            headers = {
                'User-Agent': 'GitHub-Release-Downloader'
            }
        if self.config.token:
            headers['Authorization'] = f'token {self.config.token}'
        return headers


class ApiReleaseFetcher(ReleaseFetcher):
    """通过GitHub API获取release信息"""
    
    def fetch(self, repo: str) -> Dict[str, Any]:
        headers = self._get_headers()
        headers['Accept'] = 'application/vnd.github.v3+json'
        
        def url_builder(base_url: str) -> str:
            return f"{base_url}/repos/{repo}/releases/latest"
        
        response = self.http_client.get_with_mirrors(
            "https://api.github.com",
            headers,
            url_builder=url_builder,
            request_type=RequestType.API
        )
        return response.json()


class HtmlReleaseFetcher(ReleaseFetcher):
    """通过HTML解析获取release信息"""
    
    def fetch(self, repo: str) -> Dict[str, Any]:
        headers = self._get_headers(browser=True)
        
        release_url = f"https://github.com/{repo}/releases"
        print("直接访问原始GitHub HTML页面（镜像站不支持HTML）")
        return self._parse_html(release_url, headers)
    
    def _parse_html(self, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        print(f"爬取页面: {url}")
        response = self.http_client.get(url, headers)
        response.raise_for_status()
        return self._parse_html_content(response.text)
    
    def _parse_html_content(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, 'html.parser')
        
        latest_release_section = None
        
        boxes = soup.find_all('div', {'data-view-component': re.compile(r'Box', re.I)})
        for box in boxes:
            tag_link = box.find('a', href=re.compile(r'/releases/tag/'))
            if tag_link:
                latest_release_section = box
                break
        
        if not latest_release_section:
            latest_release_section = soup.find('section', {'class': 'release'})
        if not latest_release_section:
            latest_release_section = soup.find('div', {'class': 'release'})
        
        if not latest_release_section:
            latest_release_section = soup.find('div', {'class': 'markdown-body'})
            if latest_release_section:
                for _ in range(5):
                    if latest_release_section.parent:
                        latest_release_section = latest_release_section.parent
                        if latest_release_section.find('a', href=re.compile(r'/releases/tag/')):
                            break
        
        if not latest_release_section:
            raise Exception("无法在页面中找到release信息")
        
        tag_name = 'unknown'
        
        tag_link = latest_release_section.find('a', href=re.compile(r'/releases/tag/'))
        if tag_link:
            tag_name = tag_link.get_text(strip=True)
        
        if tag_name == 'unknown':
            tag_elem = latest_release_section.find(['a', 'span'], class_=re.compile(r'tag|version', re.I))
            if tag_elem:
                tag_name = tag_elem.get_text(strip=True)
        
        if tag_name == 'unknown':
            bold_elem = latest_release_section.find(['span', 'a'], class_=re.compile(r'f1.*text-bold', re.I))
            if bold_elem:
                tag_name = bold_elem.get_text(strip=True)
        
        assets = []
        
        asset_links = latest_release_section.find_all('a', href=re.compile(r'/releases/download/'))
        
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
        
        if not assets:
            include_fragments = latest_release_section.find_all('include-fragment')
            for fragment in include_fragments:
                src = fragment.get('src', '') or fragment.get('data-deferred-src', '')
                if 'expanded_assets' in src:
                    print(f"检测到动态加载的assets，尝试获取: {src}")
                    try:
                        if src.startswith('/'):
                            src = f"https://github.com{src}"
                        response = self.http_client.get(src, headers=self._get_headers())
                        response.raise_for_status()
                        fragment_soup = BeautifulSoup(response.text, 'html.parser')
                        asset_links = fragment_soup.find_all('a', href=re.compile(r'/releases/download/'))
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
                        print(f"从动态加载获取到 {len(assets)} 个assets")
                        break
                    except Exception as e:
                        print(f"获取动态assets失败: {e}")
                        break
            
            if not assets:
                all_fragments = soup.find_all('include-fragment')
                for fragment in all_fragments:
                    src = fragment.get('src', '') or fragment.get('data-deferred-src', '')
                    if 'expanded_assets' in src:
                        print(f"在整个页面中找到expanded_assets fragment: {src}")
                        try:
                            if src.startswith('/'):
                                src = f"https://github.com{src}"
                            response = self.http_client.get(src, headers=self._get_headers())
                            response.raise_for_status()
                            fragment_soup = BeautifulSoup(response.text, 'html.parser')
                            asset_links = fragment_soup.find_all('a', href=re.compile(r'/releases/download/'))
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
                            print(f"从动态加载获取到 {len(assets)} 个assets")
                            break
                        except Exception as e:
                            print(f"获取动态assets失败: {e}")
                            break
        
        print(f"HTML爬取成功，版本: {tag_name}")
        return {
            'tag_name': tag_name,
            'assets': assets
        }
