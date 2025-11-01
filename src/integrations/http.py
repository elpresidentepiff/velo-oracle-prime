"""
VÉLØ v10 - Robust HTTP Client
Resilient HTTP requests with retry, backoff, and timeout handling
"""

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import logging
from typing import Dict, Any, Optional
from src.core.settings import settings


logger = logging.getLogger("velo.http")


class HttpError(Exception):
    """HTTP request error"""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[requests.Response] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class HttpClient:
    """
    HTTP client with automatic retry and exponential backoff
    """
    
    def __init__(
        self,
        timeout: int = None,
        max_retries: int = None,
        backoff_min: float = None,
        backoff_max: float = None
    ):
        """
        Initialize HTTP client
        
        Args:
            timeout: Request timeout in seconds (default from settings)
            max_retries: Maximum retry attempts (default from settings)
            backoff_min: Minimum backoff time in seconds (default from settings)
            backoff_max: Maximum backoff time in seconds (default from settings)
        """
        self.timeout = timeout or settings.HTTP_TIMEOUT
        self.max_retries = max_retries or settings.HTTP_MAX_RETRIES
        self.backoff_min = backoff_min or settings.HTTP_BACKOFF_MIN
        self.backoff_max = backoff_max or settings.HTTP_BACKOFF_MAX
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "VELO-Oracle/10.0"
        })
    
    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, min=1, max=8),
        retry=retry_if_exception_type((
            requests.Timeout,
            requests.ConnectionError,
            requests.exceptions.ChunkedEncodingError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG)
    )
    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> requests.Response:
        """
        GET request with automatic retry
        
        Args:
            url: URL to request
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout (overrides default)
            **kwargs: Additional requests.get arguments
        
        Returns:
            Response object
        
        Raises:
            HttpError: On 4xx/5xx status codes
            requests.Timeout: On timeout (will retry)
            requests.ConnectionError: On connection error (will retry)
        """
        timeout = timeout or self.timeout
        
        try:
            logger.debug(f"GET {url} (timeout={timeout}s)")
            
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                **kwargs
            )
            
            # Raise for 4xx/5xx status codes
            if response.status_code >= 400:
                error_msg = f"GET {url} -> {response.status_code}"
                logger.error(error_msg)
                raise HttpError(
                    error_msg,
                    status_code=response.status_code,
                    response=response
                )
            
            logger.debug(f"GET {url} -> {response.status_code} OK")
            return response
            
        except requests.Timeout as e:
            logger.warning(f"GET {url} -> Timeout after {timeout}s")
            raise
        except requests.ConnectionError as e:
            logger.warning(f"GET {url} -> Connection error: {e}")
            raise
    
    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, min=1, max=8),
        retry=retry_if_exception_type((
            requests.Timeout,
            requests.ConnectionError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> requests.Response:
        """
        POST request with automatic retry
        
        Args:
            url: URL to request
            data: Form data
            json: JSON data
            headers: Additional headers
            timeout: Request timeout (overrides default)
            **kwargs: Additional requests.post arguments
        
        Returns:
            Response object
        
        Raises:
            HttpError: On 4xx/5xx status codes
        """
        timeout = timeout or self.timeout
        
        try:
            logger.debug(f"POST {url} (timeout={timeout}s)")
            
            response = self.session.post(
                url,
                data=data,
                json=json,
                headers=headers,
                timeout=timeout,
                **kwargs
            )
            
            if response.status_code >= 400:
                error_msg = f"POST {url} -> {response.status_code}"
                logger.error(error_msg)
                raise HttpError(
                    error_msg,
                    status_code=response.status_code,
                    response=response
                )
            
            logger.debug(f"POST {url} -> {response.status_code} OK")
            return response
            
        except requests.Timeout as e:
            logger.warning(f"POST {url} -> Timeout after {timeout}s")
            raise
        except requests.ConnectionError as e:
            logger.warning(f"POST {url} -> Connection error: {e}")
            raise
    
    def close(self):
        """Close the session"""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Global HTTP client instance
_http_client = None


def get_http_client() -> HttpClient:
    """Get or create global HTTP client"""
    global _http_client
    if _http_client is None:
        _http_client = HttpClient()
    return _http_client


# Convenience functions
def get(url: str, **kwargs) -> requests.Response:
    """
    Convenience function for GET requests
    
    Args:
        url: URL to request
        **kwargs: Additional arguments for HttpClient.get()
    
    Returns:
        Response object
    """
    client = get_http_client()
    return client.get(url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    """
    Convenience function for POST requests
    
    Args:
        url: URL to request
        **kwargs: Additional arguments for HttpClient.post()
    
    Returns:
        Response object
    """
    client = get_http_client()
    return client.post(url, **kwargs)

