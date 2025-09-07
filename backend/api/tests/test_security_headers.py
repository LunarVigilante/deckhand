def test_security_headers(client):
    rv = client.get('/health')
    assert rv.status_code == 200
    headers = {k.lower(): v for k, v in rv.headers.items()}

    # HSTS present (may be disabled in non-https dev, but enabled by default in app)
    assert 'strict-transport-security' in headers

    # Basic anti-mime sniffing and clickjacking
    assert headers.get('x-content-type-options', '').lower() == 'nosniff'
    assert headers.get('x-frame-options', '').upper() == 'DENY'

    # COOP/CORP and Permissions-Policy should be present
    assert 'permissions-policy' in headers
    assert 'cross-origin-opener-policy' in headers
    assert 'cross-origin-resource-policy' in headers


def test_cache_control_protected_routes(client, auth_headers):
    rv = client.get('/api/v1/users', headers=auth_headers)
    # If users blueprint implements list; if not, simulate a protected route e.g. privacy
    if rv.status_code == 404:
        rv = client.get('/api/v1/privacy/export', headers=auth_headers)
    headers = {k.lower(): v for k, v in rv.headers.items()}
    assert headers.get('cache-control') is not None
    assert 'no-store' in headers.get('cache-control', '').lower()
    assert headers.get('pragma', '').lower() == 'no-cache'
    assert headers.get('vary') is None or 'authorization' in headers.get('vary', '').lower()


def test_cors_allowlist(client):
    # Preflight request example
    rv = client.options(
        '/health',
        headers={
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Content-Type'
        }
    )
    assert rv.status_code in (200, 204)