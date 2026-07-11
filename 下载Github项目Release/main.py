#!/usr/bin/env python3
"""
GitHub Release Downloader
自动从GitHub下载最新release中匹配指定正则的文件
支持指定GitHub镜像站
"""

import re
import requests
import argparse
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from config import Config, MirrorConfig, MirrorStrategy, RequestType
from fetcher import ReleaseFetcher, ApiReleaseFetcher, HtmlReleaseFetcher, ReleaseCache


def log_step(msg):
    print(f"  -> {msg}")

def log_ok(msg):
    print(f"  OK {msg}")

def log_fail(msg):
    print(f"  XX {msg}")


class HttpClient:
    """HTTP客户端类，处理HTTP请求"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None, stream: bool = False) -> requests.Response:
        """发送GET请求"""
        timeout = self.config.download_timeout if stream else self.config.timeout
        return requests.get(url, headers=headers or {}, stream=stream, timeout=timeout)
    
    def get_with_mirrors(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        stream: bool = False,
        url_builder: Optional[callable] = None,
        request_type: RequestType = RequestType.API
    ) -> requests.Response:
        """使用镜像站尝试请求"""
        if self.config.token:
            url = url_builder(base_url) if url_builder else base_url
            log_step("Using token, direct access")
            return self.get(url, headers, stream)

        last_error = None
        for mirror_config in self.config.mirrors:
            try:
                original_url = url_builder(base_url) if url_builder else base_url

                if mirror_config.url:
                    if not mirror_config.supports(request_type):
                        mirror_name = mirror_config.name or mirror_config.url
                        log_step(f"Mirror {mirror_name} does not support {request_type.value}, skip")
                        continue

                    url = mirror_config.build_url(original_url, request_type)
                    log_step(f"Trying mirror: {mirror_config.name}")
                else:
                    url = original_url
                    log_step("Using original GitHub URL")

                response = self.get(url, headers, stream)
                response.raise_for_status()
                log_ok("Request success")
                return response
            except Exception as e:
                last_error = e
                mirror_name = mirror_config.name or (mirror_config.url or 'GitHub')
                log_fail(f"Mirror {mirror_name} failed: {e}")
                continue

        raise Exception(f"All mirrors failed, last error: {last_error}")


class FileDownloader:
    """文件下载器类"""
    
    def __init__(self, config: Config, http_client: HttpClient):
        self.config = config
        self.http_client = http_client
    
    def download(self, url: str, dest_path: Path) -> None:
        """下载文件到指定路径"""
        headers = {}
        if self.config.token:
            headers['Authorization'] = f'token {self.config.token}'
            download_url = url
            log_step("Using token, direct download from GitHub")
            self._download_file(download_url, dest_path, headers)
            return

        request_type = self._determine_request_type(url)

        last_error = None
        for mirror_config in self.config.mirrors:
            try:
                if mirror_config.url:
                    if not mirror_config.supports(request_type):
                        mirror_name = mirror_config.name or mirror_config.url
                        log_step(f"Mirror {mirror_name} does not support {request_type.value}, skip")
                        continue

                    download_url = mirror_config.build_url(url, request_type)
                    log_step(f"Trying download mirror: {mirror_config.name}")
                else:
                    download_url = url
                    log_step("Using original GitHub download")

                self._download_file(download_url, dest_path, headers)
                return
            except Exception as e:
                last_error = e
                mirror_name = mirror_config.name or (mirror_config.url or 'GitHub')
                log_fail(f"Mirror {mirror_name} failed: {e}")
                if dest_path.exists():
                    dest_path.unlink()
                continue

        raise Exception(f"All mirrors failed, last error: {last_error}")
    
    def _determine_request_type(self, url: str) -> RequestType:
        """根据URL确定请求类型"""
        if 'api.github.com' in url:
            return RequestType.API
        elif 'raw.githubusercontent.com' in url:
            return RequestType.RAW
        elif 'gist.githubusercontent.com' in url:
            return RequestType.GIST
        elif 'releases/download' in url or 'archive/refs' in url:
            return RequestType.DOWNLOAD
        else:
            return RequestType.DOWNLOAD
    
    def _download_file(self, url: str, dest_path: Path, headers: Dict[str, str]) -> None:
        """执行文件下载"""
        log_step(f"Downloading from: {url}")
        response = self.http_client.get(url, headers, stream=True)
        response.raise_for_status()

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        total = int(response.headers.get('content-length', 0))
        downloaded = 0
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 // total
                        bar_len = 20
                        filled = pct * bar_len // 100
                        bar = '[' + '#' * filled + '.' * (bar_len - filled) + ']'
                        size_mb = downloaded / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        print(f"\r    {bar} {pct}%  {size_mb:.1f}/{total_mb:.1f} MB  ", end='', flush=True)

        print()
        log_ok(f"Saved: {dest_path}")


class GitHubReleaseDownloader:
    """GitHub Release下载器主类"""
    
    def __init__(self, config: Optional[Config] = None, cache_ttl: int = 3600):
        self.config = config or Config()
        self.http_client = HttpClient(self.config)
        self.fetchers: List[ReleaseFetcher] = [
            ApiReleaseFetcher(self.config, self.http_client),
            HtmlReleaseFetcher(self.config, self.http_client)
        ]
        self.file_downloader = FileDownloader(self.config, self.http_client)
        self.cache = ReleaseCache(ttl=cache_ttl)
    
    def add_fetcher(self, fetcher: ReleaseFetcher) -> None:
        """添加自定义fetcher"""
        self.fetchers.append(fetcher)
    
    def get_latest_release(self, repo: str, force: bool = False) -> Dict[str, Any]:
        """获取最新release信息
        
        Args:
            repo: 仓库地址 owner/repo
            force: 是否强制刷新，忽略缓存
        """
        if not force:
            cached = self.cache.get(repo)
            if cached is not None:
                age = self.cache.get_age(repo)
                log_step(f"Using cached data ({age}s old): {repo}")
                return cached

        log_step(f"Fetching release info: {repo}")

        last_error = None
        for fetcher in self.fetchers:
            try:
                release = fetcher.fetch(repo)
                tag_name = release.get('tag_name', 'unknown')
                log_ok(f"Latest version: {tag_name}")
                self.cache.set(repo, release)
                return release
            except Exception as e:
                last_error = e
                log_fail(f"{fetcher.__class__.__name__} failed: {e}")
                continue

        raise Exception(f"All fetchers failed, last error: {last_error}")
    
    def list_matching_files(
        self,
        repo: str,
        pattern: str,
        force: bool = False
    ) -> List[Dict[str, Any]]:
        """列出匹配正则的文件（不下载）"""
        release = self.get_latest_release(repo, force=force)
        tag_name = release.get('tag_name', 'unknown')
        assets = release.get('assets', [])

        regex = re.compile(pattern)
        matched = [
            a for a in assets
            if regex.search(a.get('name', ''))
        ]

        print(f"TAG:{tag_name}")
        for a in matched:
            print(a.get('browser_download_url', ''))

        return matched

    def clear_cache(self, repo: str = None) -> None:
        """清除缓存"""
        self.cache.invalidate(repo)
        if repo:
            log_ok(f"Cleared cache: {repo}")
        else:
            log_ok("Cleared all caches")

    def download_matching_files(
        self,
        repo: str,
        pattern: str,
        output_dir: str = '.',
        force: bool = False
    ) -> None:
        """下载匹配正则的文件"""
        release = self.get_latest_release(repo, force=force)
        assets = release.get('assets', [])

        if not assets:
            log_fail("No assets found")
            return

        regex = re.compile(pattern)
        matched_assets = [
            asset for asset in assets
            if regex.search(asset.get('name', ''))
        ]

        if not matched_assets:
            log_fail(f"No match for pattern: {pattern}")
            log_step("Available files:")
            for asset in assets:
                log_step(f"  - {asset.get('name', '')}")
            return

        log_step(f"Found {len(matched_assets)} matching file(s):")
        for asset in matched_assets:
            log_step(f"  - {asset.get('name', '')}")

        for asset in matched_assets:
            name = asset.get('name', '')
            download_url = asset.get('browser_download_url', '')
            dest_path = Path(output_dir) / name
            self.file_downloader.download(download_url, dest_path)

        log_ok("Download complete!")




def main():
    parser = argparse.ArgumentParser(
        description='从GitHub下载最新release中匹配指定正则的文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 下载最新release中所有 .exe 文件
  python 下载Github项目Release.py --repo owner/repo --pattern "\\.exe$"
  
  # 指定输出目录
  python 下载Github项目Release.py --repo owner/repo --pattern "linux-amd64" --output ./downloads
  
  # 使用自定义token
  python 下载Github项目Release.py --repo owner/repo --pattern "\\.exe$" --token YOUR_TOKEN
  
  # 强制刷新缓存
  python 下载Github项目Release.py --repo owner/repo --pattern "\\.exe$" --force
  
  # 清除缓存
  python 下载Github项目Release.py --clear-cache
        """
    )
    
    parser.add_argument('--repo', help='GitHub仓库，格式: owner/repo')
    parser.add_argument('--pattern', help='文件名正则表达式')
    parser.add_argument('--output', default='.', help='输出目录 (默认: 当前目录)')
    parser.add_argument('--token', default='', help='GitHub token (为空则使用匿名请求)')
    parser.add_argument('--force', action='store_true', help='强制刷新，忽略缓存')
    parser.add_argument('--list', action='store_true', help='仅列出匹配文件URL，不下载')
    parser.add_argument('--clear-cache', action='store_true', help='清除所有缓存')
    parser.add_argument('--cache-ttl', type=int, default=3600, help='缓存有效期(秒)，默认3600(1小时)')

    args = parser.parse_args()

    config = Config(token=args.token or None)
    downloader = GitHubReleaseDownloader(config, cache_ttl=args.cache_ttl)

    if args.clear_cache:
        downloader.clear_cache()
        return

    if not args.repo:
        parser.error("需要指定 --repo 参数")
    if not args.pattern:
        parser.error("需要指定 --pattern 参数")

    if args.list:
        downloader.list_matching_files(
            repo=args.repo,
            pattern=args.pattern,
            force=args.force
        )
    else:
        downloader.download_matching_files(
            repo=args.repo,
            pattern=args.pattern,
            output_dir=args.output,
            force=args.force
        )


if __name__ == '__main__':
    main()
