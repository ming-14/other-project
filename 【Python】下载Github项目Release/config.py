from urllib.parse import urlparse
from typing import List, Optional, Dict, Any
from enum import Enum


class MirrorStrategy(Enum):
    PREFIX = "prefix"
    REPLACE = "replace"


class RequestType(Enum):
    API = "api"
    HTML = "html"
    DOWNLOAD = "download"
    RAW = "raw"
    GIST = "gist"
    GIT = "git"


class MirrorConfig:
    """镜像站配置类"""
    
    def __init__(
        self,
        url: str,
        strategy: MirrorStrategy = MirrorStrategy.PREFIX,
        supported_types: List[RequestType] = None,
        domain_mappings: Dict[str, str] = None,
        name: str = ""
    ):
        self.url = url.rstrip('/') if url else None
        self.strategy = strategy
        self.name = name or (self.url if self.url else "原始GitHub")
        self.supported_types = supported_types if supported_types is not None else [
            RequestType.API,
            RequestType.DOWNLOAD,
            RequestType.RAW,
            RequestType.GIST,
        ]
        self.domain_mappings = domain_mappings
    
    def supports(self, request_type: RequestType) -> bool:
        return request_type in self.supported_types
    
    def build_url(self, original_url: str, request_type: RequestType) -> str:
        if not self.url:
            return original_url
        
        if not self.supports(request_type):
            return original_url
        
        if self.strategy == MirrorStrategy.PREFIX:
            return f"{self.url}/{original_url}"
        elif self.strategy == MirrorStrategy.REPLACE:
            parsed = urlparse(original_url)
            domain = parsed.netloc
            
            if self.domain_mappings and domain in self.domain_mappings:
                mapped_domain = self.domain_mappings[domain]
            else:
                mapped_domain = self.url
            
            new_url = parsed._replace(netloc=mapped_domain)
            return new_url.geturl()
        
        return original_url
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'url': self.url,
            'strategy': self.strategy.value,
            'supported_types': [t.value for t in self.supported_types],
            'domain_mappings': self.domain_mappings,
            'name': self.name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MirrorConfig':
        return cls(
            url=data.get('url', ''),
            strategy=MirrorStrategy(data.get('strategy', 'prefix')),
            supported_types=[RequestType(t) for t in data.get('supported_types', ['api', 'download', 'raw', 'gist'])],
            domain_mappings=data.get('domain_mappings'),
            name=data.get('name', '')
        )


class Config:
    """配置管理类"""
    
    DEFAULT_MIRRORS = [
        MirrorConfig(
            "https://gh-proxy.com",
            strategy=MirrorStrategy.PREFIX,
            supported_types=[RequestType.API, RequestType.DOWNLOAD, RequestType.RAW, RequestType.GIST],
            name="gh-proxy.com"
        ),
        MirrorConfig(
            "https://ghproxy.com",
            strategy=MirrorStrategy.PREFIX,
            supported_types=[RequestType.API, RequestType.DOWNLOAD, RequestType.RAW, RequestType.GIST],
            name="ghproxy.com"
        ),
        MirrorConfig(
            "https://gh.llkk.cc",
            strategy=MirrorStrategy.PREFIX,
            supported_types=[RequestType.API, RequestType.DOWNLOAD, RequestType.RAW, RequestType.GIST],
            name="gh.llkk.cc"
        ),
        MirrorConfig(
            "https://gh.jasonzeng.dev",
            strategy=MirrorStrategy.PREFIX,
            supported_types=[RequestType.DOWNLOAD, RequestType.RAW, RequestType.GIST],
            name="gh.jasonzeng.dev"
        ),
        MirrorConfig(None, name="原始GitHub")
    ]
    
    DEFAULT_TOKEN = ""
    DEFAULT_TIMEOUT = 30
    DOWNLOAD_TIMEOUT = 300
    CHUNK_SIZE = 8192
    
    BROWSER_HEADERS = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'sec-ch-ua': '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'sec-gpc': '1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0',
    }
    
    def __init__(
        self,
        token: Optional[str] = None,
        mirrors: Optional[List[MirrorConfig]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        download_timeout: int = DOWNLOAD_TIMEOUT,
        chunk_size: int = CHUNK_SIZE,
        browser_headers: Optional[Dict[str, str]] = None
    ):
        self.token = token or self.DEFAULT_TOKEN
        self.mirrors = mirrors if mirrors is not None else self.DEFAULT_MIRRORS
        self.timeout = timeout
        self.download_timeout = download_timeout
        self.chunk_size = chunk_size
        self.browser_headers = browser_headers if browser_headers is not None else dict(self.BROWSER_HEADERS)
    
    @staticmethod
    def create_mirror_from_string(mirror_str: str, strategy: str = "prefix",
                                   supported_types: List[str] = None) -> MirrorConfig:
        if not mirror_str:
            return MirrorConfig(None)
        
        st = MirrorStrategy(strategy)
        types = [RequestType(t) for t in (supported_types or ['api', 'download', 'raw', 'gist'])]
        
        return MirrorConfig(
            mirror_str,
            strategy=st,
            supported_types=types
        )
