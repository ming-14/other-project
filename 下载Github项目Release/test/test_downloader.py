#!/usr/bin/env python3
"""
GitHub Release Downloader 测试套件
使用pytest进行单元测试和集成测试
"""

import pytest
import re
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from requests import Response
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config, MirrorConfig, MirrorStrategy, RequestType
from fetcher import ReleaseFetcher, ApiReleaseFetcher, HtmlReleaseFetcher, ReleaseCache
from main import (
    HttpClient,
    FileDownloader,
    GitHubReleaseDownloader
)


class TestConfig:
    """测试Config类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = Config()
        assert config.token == ""
        assert config.mirrors == Config.DEFAULT_MIRRORS
        assert config.timeout == Config.DEFAULT_TIMEOUT
        assert config.download_timeout == Config.DOWNLOAD_TIMEOUT
        assert config.chunk_size == Config.CHUNK_SIZE
    
    def test_custom_token(self):
        """测试自定义token"""
        config = Config(token="test_token")
        assert config.token == "test_token"
    
    def test_custom_mirrors(self):
        """测试自定义镜像站"""
        custom_mirrors = [
            MirrorConfig("https://custom.mirror/"),
            MirrorConfig(None)
        ]
        config = Config(mirrors=custom_mirrors)
        assert config.mirrors == custom_mirrors
    
    def test_custom_timeouts(self):
        """测试自定义超时设置"""
        config = Config(timeout=60, download_timeout=600)
        assert config.timeout == 60
        assert config.download_timeout == 600
    
    def test_custom_chunk_size(self):
        """测试自定义chunk大小"""
        config = Config(chunk_size=16384)
        assert config.chunk_size == 16384
    
    def test_none_token_uses_default(self):
        """测试None token使用默认值"""
        config = Config(token=None)
        assert config.token == Config.DEFAULT_TOKEN
    
    def test_empty_string_token(self):
        """测试空字符串token"""
        config = Config(token="")
        assert config.token == ""


class TestMirrorConfig:
    """测试MirrorConfig类"""
    
    def test_prefix_strategy_build_url(self):
        """测试前缀拼接策略"""
        mc = MirrorConfig("https://gh-proxy.com", strategy=MirrorStrategy.PREFIX)
        url = mc.build_url("https://api.github.com/repos/owner/repo/releases/latest", RequestType.API)
        assert url == "https://gh-proxy.com/https://api.github.com/repos/owner/repo/releases/latest"
    
    def test_prefix_strategy_download(self):
        """测试前缀拼接策略下载URL"""
        mc = MirrorConfig("https://gh-proxy.com", strategy=MirrorStrategy.PREFIX)
        url = mc.build_url("https://github.com/owner/repo/releases/download/v1.0/file.exe", RequestType.DOWNLOAD)
        assert url == "https://gh-proxy.com/https://github.com/owner/repo/releases/download/v1.0/file.exe"
    
    def test_replace_strategy_build_url(self):
        """测试域名替换策略"""
        mc = MirrorConfig("https://mirror.example.com", strategy=MirrorStrategy.REPLACE,
                          domain_mappings={
                              'github.com': 'mirror.example.com',
                              'api.github.com': 'mirror.example.com'
                          })
        url = mc.build_url("https://api.github.com/repos/owner/repo", RequestType.API)
        assert "mirror.example.com" in url
        assert "/repos/owner/repo" in url
    
    def test_supports_check(self):
        """测试支持类型检查"""
        mc = MirrorConfig("https://gh-proxy.com", supported_types=[RequestType.API, RequestType.DOWNLOAD])
        assert mc.supports(RequestType.API) is True
        assert mc.supports(RequestType.DOWNLOAD) is True
        assert mc.supports(RequestType.HTML) is False
    
    def test_no_url_returns_original(self):
        """测试无URL时返回原始URL"""
        mc = MirrorConfig(None)
        original = "https://api.github.com/repos/owner/repo"
        assert mc.build_url(original, RequestType.API) == original
    
    def test_unsupported_type_returns_original(self):
        """测试不支持的类型返回原始URL"""
        mc = MirrorConfig("https://gh-proxy.com", supported_types=[RequestType.API])
        original = "https://github.com/owner/repo/releases"
        assert mc.build_url(original, RequestType.HTML) == original
    
    def test_to_dict_and_from_dict(self):
        """测试序列化和反序列化"""
        mc = MirrorConfig(
            "https://gh-proxy.com",
            strategy=MirrorStrategy.PREFIX,
            supported_types=[RequestType.API, RequestType.DOWNLOAD],
            name="测试镜像"
        )
        d = mc.to_dict()
        mc2 = MirrorConfig.from_dict(d)
        assert mc2.url == mc.url
        assert mc2.strategy == mc.strategy
        assert mc2.supported_types == mc.supported_types
        assert mc2.name == mc.name
    
    def test_create_mirror_from_string(self):
        """测试从字符串创建镜像配置"""
        mc = Config.create_mirror_from_string("https://gh-proxy.com")
        assert mc.url == "https://gh-proxy.com"
        assert mc.strategy == MirrorStrategy.PREFIX
    
    def test_create_mirror_from_empty_string(self):
        """测试从空字符串创建镜像配置"""
        mc = Config.create_mirror_from_string("")
        assert mc.url is None
    
    def test_name_defaults_to_url(self):
        """测试名称默认为URL"""
        mc = MirrorConfig("https://gh-proxy.com")
        assert mc.name == "https://gh-proxy.com"
    
    def test_name_defaults_to_original_for_none(self):
        """测试None URL时名称为原始GitHub"""
        mc = MirrorConfig(None)
        assert mc.name == "原始GitHub"


class TestReleaseCache:
    """测试ReleaseCache类"""
    
    def test_cache_miss(self):
        cache = ReleaseCache(ttl=3600)
        assert cache.get("owner/repo") is None
    
    def test_cache_set_and_get(self):
        cache = ReleaseCache(ttl=3600)
        data = {'tag_name': 'v1.0.0', 'assets': []}
        cache.set("owner/repo", data)
        assert cache.get("owner/repo") == data
    
    def test_cache_is_valid(self):
        cache = ReleaseCache(ttl=3600)
        assert cache.is_valid("owner/repo") is False
        cache.set("owner/repo", {'tag_name': 'v1.0.0', 'assets': []})
        assert cache.is_valid("owner/repo") is True
    
    def test_cache_invalidate_specific(self):
        cache = ReleaseCache(ttl=3600)
        cache.set("owner/repo1", {'tag_name': 'v1.0.0', 'assets': []})
        cache.set("owner/repo2", {'tag_name': 'v2.0.0', 'assets': []})
        cache.invalidate("owner/repo1")
        assert cache.get("owner/repo1") is None
        assert cache.get("owner/repo2") is not None
    
    def test_cache_invalidate_all(self):
        cache = ReleaseCache(ttl=3600)
        cache.set("owner/repo1", {'tag_name': 'v1.0.0', 'assets': []})
        cache.set("owner/repo2", {'tag_name': 'v2.0.0', 'assets': []})
        cache.invalidate()
        assert cache.get("owner/repo1") is None
        assert cache.get("owner/repo2") is None
    
    def test_cache_get_age(self):
        cache = ReleaseCache(ttl=3600)
        assert cache.get_age("owner/repo") is None
        cache.set("owner/repo", {'tag_name': 'v1.0.0', 'assets': []})
        age = cache.get_age("owner/repo")
        assert age is not None
        assert age >= 0
    
    def test_cache_expired(self):
        cache = ReleaseCache(ttl=0)
        cache.set("owner/repo", {'tag_name': 'v1.0.0', 'assets': []})
        import time
        time.sleep(0.01)
        assert cache.get("owner/repo") is None
        assert cache.is_valid("owner/repo") is False


class TestHttpClient:
    """测试HttpClient类"""
    
    @pytest.fixture
    def config(self):
        return Config()
    
    @pytest.fixture
    def http_client(self, config):
        return HttpClient(config)
    
    @patch('main.requests.get')
    def test_get_request(self, mock_get, http_client):
        """测试GET请求"""
        mock_response = Mock()
        mock_get.return_value = mock_response
        
        headers = {'User-Agent': 'test'}
        response = http_client.get('http://example.com', headers=headers)
        
        mock_get.assert_called_once_with(
            'http://example.com',
            headers=headers,
            stream=False,
            timeout=Config.DEFAULT_TIMEOUT
        )
        assert response == mock_response
    
    @patch('main.requests.get')
    def test_get_stream_request(self, mock_get, http_client):
        """测试流式GET请求"""
        mock_response = Mock()
        mock_get.return_value = mock_response
        
        response = http_client.get('http://example.com', stream=True)
        
        mock_get.assert_called_once_with(
            'http://example.com',
            headers={},
            stream=True,
            timeout=Config.DOWNLOAD_TIMEOUT
        )
        assert response == mock_response
    
    @patch('main.requests.get')
    def test_get_with_mirrors_with_token(self, mock_get, http_client):
        """测试使用token时直接访问原始URL"""
        config = Config(token="test_token")
        http_client = HttpClient(config)
        
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        def url_builder(base_url):
            return "/test/path"
        
        response = http_client.get_with_mirrors(
            "https://api.github.com",
            url_builder=url_builder
        )
        
        mock_get.assert_called_once()
        assert response == mock_response
    
    @patch('main.requests.get')
    def test_get_with_mirrors_without_token(self, mock_get, http_client):
        """测试无token时使用镜像站"""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        def url_builder(base_url):
            return "/test/path"
        
        response = http_client.get_with_mirrors(
            "https://api.github.com",
            url_builder=url_builder
        )
        
        assert response == mock_response
    
    @patch('main.requests.get')
    def test_get_with_mirrors_all_fail(self, mock_get, http_client):
        """测试所有镜像站都失败"""
        mock_get.side_effect = Exception("Connection error")
        
        def url_builder(base_url):
            return "/test/path"
        
        with pytest.raises(Exception, match="所有镜像都失败"):
            http_client.get_with_mirrors(
                "https://api.github.com",
                url_builder=url_builder
            )


class TestReleaseFetcher:
    """测试ReleaseFetcher抽象类"""
    
    def test_cannot_instantiate_abstract_class(self):
        """测试不能实例化抽象类"""
        config = Config()
        http_client = HttpClient(config)
        
        with pytest.raises(TypeError):
            ReleaseFetcher(config, http_client)


class TestApiReleaseFetcher:
    """测试ApiReleaseFetcher类"""
    
    @pytest.fixture
    def config(self):
        return Config()
    
    @pytest.fixture
    def http_client(self, config):
        return HttpClient(config)
    
    @pytest.fixture
    def api_fetcher(self, config, http_client):
        return ApiReleaseFetcher(config, http_client)
    
    @patch.object(HttpClient, 'get_with_mirrors')
    def test_fetch_success(self, mock_get, api_fetcher):
        """测试成功获取release信息"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'tag_name': 'v1.0.0',
            'assets': [
                {'name': 'test.exe', 'browser_download_url': 'https://example.com/test.exe'}
            ]
        }
        mock_get.return_value = mock_response
        
        result = api_fetcher.fetch('owner/repo')
        
        assert result['tag_name'] == 'v1.0.0'
        assert len(result['assets']) == 1
        mock_get.assert_called_once()
    
    @patch.object(HttpClient, 'get_with_mirrors')
    def test_fetch_failure(self, mock_get, api_fetcher):
        """测试获取失败"""
        mock_get.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            api_fetcher.fetch('owner/repo')
    
    def test_get_headers_without_token(self, api_fetcher):
        """测试无token时的请求头"""
        headers = api_fetcher._get_headers()
        assert 'Authorization' not in headers
        assert headers['User-Agent'] == 'GitHub-Release-Downloader'
    
    def test_get_headers_with_token(self, api_fetcher):
        """测试有token时的请求头"""
        api_fetcher.config.token = "test_token"
        headers = api_fetcher._get_headers()
        assert headers['Authorization'] == 'token test_token'
        assert headers['User-Agent'] == 'GitHub-Release-Downloader'


class TestHtmlReleaseFetcher:
    """测试HtmlReleaseFetcher类"""
    
    @pytest.fixture
    def config(self):
        return Config()
    
    @pytest.fixture
    def http_client(self, config):
        return HttpClient(config)
    
    @pytest.fixture
    def html_fetcher(self, config, http_client):
        return HtmlReleaseFetcher(config, http_client)
    
    @patch.object(HttpClient, 'get')
    def test_fetch_success(self, mock_get, html_fetcher):
        """测试成功解析HTML"""
        html_content = """
        <html>
            <body>
                <section class="release">
                    <a class="tag" href="/tag/v1.0.0">v1.0.0</a>
                    <a href="/releases/download/v1.0.0/test.exe">test.exe</a>
                    <a href="/releases/download/v1.0.0/test.zip">test.zip</a>
                </section>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = html_fetcher.fetch('owner/repo')
        
        assert result['tag_name'] == 'v1.0.0'
        assert len(result['assets']) == 2
        assert result['assets'][0]['name'] == 'test.exe'
        # 验证直接访问原始GitHub URL
        mock_get.assert_called_once()
    
    @patch.object(HttpClient, 'get')
    def test_parse_html_success(self, mock_get, html_fetcher):
        """测试解析HTML页面"""
        html_content = """
        <html>
            <body>
                <section class="release">
                    <span class="tag">v2.0.0</span>
                    <a href="/releases/download/v2.0.0/app.dmg">app.dmg</a>
                </section>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = html_fetcher._parse_html('https://github.com/owner/repo/releases', {})
        
        assert result['tag_name'] == 'v2.0.0'
        assert len(result['assets']) == 1
    
    def test_parse_html_content_no_release_section(self, html_fetcher):
        """测试HTML中没有release section"""
        html_content = "<html><body><p>No release</p></body></html>"
        
        with pytest.raises(Exception, match="无法在页面中找到release信息"):
            html_fetcher._parse_html_content(html_content)
    
    def test_parse_html_content_no_tag(self, html_fetcher):
        """测试HTML中没有tag信息"""
        html_content = """
        <section class="release">
            <a href="/releases/download/v1.0.0/test.exe">test.exe</a>
        </section>
        """
        
        result = html_fetcher._parse_html_content(html_content)
        assert result['tag_name'] == 'unknown'


class TestFileDownloader:
    """测试FileDownloader类"""
    
    @pytest.fixture
    def config(self):
        return Config()
    
    @pytest.fixture
    def http_client(self, config):
        return HttpClient(config)
    
    @pytest.fixture
    def file_downloader(self, config, http_client):
        return FileDownloader(config, http_client)
    
    @patch.object(HttpClient, 'get')
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_with_token(self, mock_open_func, mock_mkdir, mock_get, file_downloader):
        """测试使用token下载"""
        file_downloader.config.token = "test_token"
        
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.return_value = [b'test data']
        mock_get.return_value = mock_response
        
        dest_path = Path('/tmp/test.exe')
        file_downloader.download('https://example.com/file.exe', dest_path)
        
        mock_get.assert_called_once()
        mock_open_func.assert_called_once()
    
    @patch.object(HttpClient, 'get')
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_without_token(self, mock_open_func, mock_mkdir, mock_get, file_downloader):
        """测试无token下载"""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.iter_content.return_value = [b'test data']
        mock_get.return_value = mock_response
        
        dest_path = Path('/tmp/test.exe')
        file_downloader.download('https://github.com/owner/repo/releases/download/v1.0.0/file.exe', dest_path)
        
        mock_get.assert_called_once()
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.unlink')
    def test_download_failure_cleanup(self, mock_unlink, mock_exists, file_downloader):
        """测试下载失败时清理文件"""
        mock_exists.return_value = True
        file_downloader.config.mirrors = [MirrorConfig("https://invalid.mirror/")]
        
        dest_path = Path('/tmp/test.exe')
        
        with pytest.raises(Exception):
            file_downloader.download('https://example.com/file.exe', dest_path)
        
        mock_unlink.assert_called_once()


class TestGitHubReleaseDownloader:
    """测试GitHubReleaseDownloader主类"""
    
    @pytest.fixture
    def downloader(self):
        return GitHubReleaseDownloader()
    
    def test_initialization(self, downloader):
        """测试初始化"""
        assert downloader.config is not None
        assert downloader.http_client is not None
        assert len(downloader.fetchers) == 2
        assert downloader.file_downloader is not None
    
    def test_add_custom_fetcher(self, downloader):
        """测试添加自定义fetcher"""
        class CustomFetcher(ReleaseFetcher):
            def fetch(self, repo):
                return {'tag_name': 'custom', 'assets': []}
        
        custom_fetcher = CustomFetcher(downloader.config, downloader.http_client)
        downloader.add_fetcher(custom_fetcher)
        
        assert len(downloader.fetchers) == 3
    
    @patch.object(ApiReleaseFetcher, 'fetch')
    def test_get_latest_release_success(self, mock_fetch, downloader):
        """测试成功获取最新release"""
        mock_fetch.return_value = {
            'tag_name': 'v1.0.0',
            'assets': [{'name': 'test.exe', 'browser_download_url': 'https://example.com/test.exe'}]
        }
        
        result = downloader.get_latest_release('owner/repo')
        
        assert result['tag_name'] == 'v1.0.0'
        mock_fetch.assert_called_once_with('owner/repo')
    
    @patch.object(ApiReleaseFetcher, 'fetch')
    def test_get_latest_release_uses_cache(self, mock_fetch, downloader):
        """测试缓存命中时不重新获取"""
        mock_fetch.return_value = {
            'tag_name': 'v1.0.0',
            'assets': [{'name': 'test.exe', 'browser_download_url': 'https://example.com/test.exe'}]
        }
        
        result1 = downloader.get_latest_release('owner/repo')
        result2 = downloader.get_latest_release('owner/repo')
        
        assert result1 == result2
        mock_fetch.assert_called_once()
    
    @patch.object(ApiReleaseFetcher, 'fetch')
    def test_get_latest_release_force_refresh(self, mock_fetch, downloader):
        """测试强制刷新忽略缓存"""
        mock_fetch.return_value = {
            'tag_name': 'v1.0.0',
            'assets': [{'name': 'test.exe', 'browser_download_url': 'https://example.com/test.exe'}]
        }
        
        downloader.get_latest_release('owner/repo')
        downloader.get_latest_release('owner/repo', force=True)
        
        assert mock_fetch.call_count == 2
    
    @patch.object(ApiReleaseFetcher, 'fetch')
    @patch.object(HtmlReleaseFetcher, 'fetch')
    def test_get_latest_release_fallback(self, mock_html_fetch, mock_api_fetch, downloader):
        """测试API失败后回退到HTML"""
        mock_api_fetch.side_effect = Exception("API Error")
        mock_html_fetch.return_value = {
            'tag_name': 'v1.0.0',
            'assets': [{'name': 'test.exe', 'browser_download_url': 'https://example.com/test.exe'}]
        }
        
        result = downloader.get_latest_release('owner/repo')
        
        assert result['tag_name'] == 'v1.0.0'
        mock_api_fetch.assert_called_once()
        mock_html_fetch.assert_called_once()
    
    @patch.object(ApiReleaseFetcher, 'fetch')
    @patch.object(HtmlReleaseFetcher, 'fetch')
    def test_get_latest_release_all_fail(self, mock_html_fetch, mock_api_fetch, downloader):
        """测试所有fetcher都失败"""
        mock_api_fetch.side_effect = Exception("API Error")
        mock_html_fetch.side_effect = Exception("HTML Error")
        
        with pytest.raises(Exception, match="所有获取方式都失败"):
            downloader.get_latest_release('owner/repo')
    
    @patch.object(GitHubReleaseDownloader, 'get_latest_release')
    def test_download_matching_files_no_assets(self, mock_get_release, downloader):
        """测试没有assets的情况"""
        mock_get_release.return_value = {'tag_name': 'v1.0.0', 'assets': []}
        
        downloader.download_matching_files('owner/repo', r'\.exe$', '/tmp')
        
        mock_get_release.assert_called_once()
    
    @patch.object(GitHubReleaseDownloader, 'get_latest_release')
    def test_download_matching_files_no_match(self, mock_get_release, downloader):
        """测试没有匹配文件的情况"""
        mock_get_release.return_value = {
            'tag_name': 'v1.0.0',
            'assets': [
                {'name': 'test.zip', 'browser_download_url': 'https://example.com/test.zip'}
            ]
        }
        
        downloader.download_matching_files('owner/repo', r'\.exe$', '/tmp')
    
    @patch.object(GitHubReleaseDownloader, 'get_latest_release')
    @patch.object(FileDownloader, 'download')
    def test_download_matching_files_success(self, mock_download, mock_get_release, downloader):
        """测试成功下载匹配文件"""
        mock_get_release.return_value = {
            'tag_name': 'v1.0.0',
            'assets': [
                {'name': 'test.exe', 'browser_download_url': 'https://example.com/test.exe'},
                {'name': 'test.zip', 'browser_download_url': 'https://example.com/test.zip'}
            ]
        }
        
        downloader.download_matching_files('owner/repo', r'\.exe$', '/tmp')
        
        mock_download.assert_called_once()
    
    @patch.object(GitHubReleaseDownloader, 'get_latest_release')
    @patch.object(FileDownloader, 'download')
    def test_download_matching_files_multiple(self, mock_download, mock_get_release, downloader):
        """测试下载多个匹配文件"""
        mock_get_release.return_value = {
            'tag_name': 'v1.0.0',
            'assets': [
                {'name': 'app-x86_64.exe', 'browser_download_url': 'https://example.com/app-x86_64.exe'},
                {'name': 'app-arm64.exe', 'browser_download_url': 'https://example.com/app-arm64.exe'}
            ]
        }
        
        downloader.download_matching_files('owner/repo', r'\.exe$', '/tmp')
        
        assert mock_download.call_count == 2


class TestIntegration:
    """集成测试"""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """临时目录fixture"""
        return tmp_path
    
    def test_config_integration(self):
        """测试配置集成"""
        config = Config(
            token="test_token",
            mirrors=[MirrorConfig("https://test.mirror/"), MirrorConfig(None)],
            timeout=60
        )
        
        http_client = HttpClient(config)
        assert http_client.config.token == "test_token"
        assert http_client.config.timeout == 60
    
    def test_full_downloader_integration(self):
        """测试完整下载器集成"""
        config = Config(token="test")
        downloader = GitHubReleaseDownloader(config)
        
        assert len(downloader.fetchers) == 2
        assert downloader.config.token == "test"
    
    def test_custom_fetcher_integration(self):
        """测试自定义fetcher集成"""
        class MockFetcher(ReleaseFetcher):
            def __init__(self, config, http_client):
                super().__init__(config, http_client)
                self.call_count = 0
            
            def fetch(self, repo):
                self.call_count += 1
                return {'tag_name': f'mock-{self.call_count}', 'assets': []}
        
        config = Config()
        downloader = GitHubReleaseDownloader(config)
        
        mock_fetcher = MockFetcher(config, downloader.http_client)
        downloader.add_fetcher(mock_fetcher)
        
        # 移除默认fetcher，只使用mock
        downloader.fetchers = [mock_fetcher]
        
        result = downloader.get_latest_release('test/repo')
        assert result['tag_name'] == 'mock-1'
        assert mock_fetcher.call_count == 1


class TestEdgeCases:
    """边缘情况测试"""
    
    def test_empty_mirrors_list(self):
        """测试空镜像列表"""
        config = Config(mirrors=[])
        assert config.mirrors == []
    
    def test_mirrors_with_none_only(self):
        """测试只有None的镜像列表"""
        config = Config(mirrors=[MirrorConfig(None)])
        assert len(config.mirrors) == 1
        assert config.mirrors[0].url is None
    
    def test_zero_chunk_size(self):
        """测试零chunk大小"""
        config = Config(chunk_size=0)
        assert config.chunk_size == 0
    
    def test_very_large_timeout(self):
        """测试非常大的超时值"""
        config = Config(timeout=999999)
        assert config.timeout == 999999
    
    def test_special_characters_in_token(self):
        """测试token中的特殊字符"""
        config = Config(token="ghp_1234567890abcdef!@#$%")
        assert config.token == "ghp_1234567890abcdef!@#$%"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
