# mirror-fetch-curl-cffi

A Mirror Fetch provider backed by
[`curl_cffi`](https://github.com/yifeikong/curl_cffi) (curl-impersonate).

curl_cffi wraps libcurl and exposes a `requests`-style API, including browser
TLS/HTTP2 fingerprint impersonation for environments that block plain
automation clients. It is one of the three industry-grade fetch providers
(httpx, playwright, curl_cffi) that saturate the `fetch` capability
(ADR-0046).

## Usage

```python
from mirror_fetch_curl_cffi.provider import CurlCFFIProvider
from mirror_fetch.models import FetchRequest

provider = CurlCFFIProvider()  # or CurlCFFIProvider(settings=...)
await provider.setup()
result = await provider.fetch(FetchRequest(url="https://example.com"))
await provider.teardown()
```

Set `impersonate="chrome"` in `CurlCFFISettings` to enable curl-impersonate
TLS/HTTP2 fingerprint masking.
