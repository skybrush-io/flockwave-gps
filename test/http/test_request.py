def test_request_header_case_sensitivity():
    from flockwave.gps.http.request import Request

    req = Request(b"http://example.com", headers={"Content-Type": b"text/plain"})
    assert req.headers["Content-Type"] == b"text/plain"
    assert req.headers["content-type"] == b"text/plain"
    assert req.headers["CONTENT-TYPE"] == b"text/plain"

    req.add_header("content-type", b"application/json")
    assert req.headers["Content-Type"] == b"application/json"
    assert req.headers["content-type"] == b"application/json"
    assert req.headers["CONTENT-TYPE"] == b"application/json"
