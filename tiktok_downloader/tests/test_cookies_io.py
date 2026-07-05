from cookies_io import write_netscape


def test_write_netscape(tmp_path):
    p = tmp_path / "c.txt"
    write_netscape([
        {"domain": ".tiktok.com", "path": "/", "secure": True,
         "expires": 1999999999, "name": "sid", "value": "abc"},
        {"domain": "www.tiktok.com", "path": "/", "secure": False,
         "expires": -1, "name": "s2", "value": "x"},
    ], str(p))
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "# Netscape HTTP Cookie File"
    assert ".tiktok.com\tTRUE\t/\tTRUE\t1999999999\tsid\tabc" in lines
    # 会话 cookie expires=-1 写 0；域不带点 domain_flag=FALSE
    assert "www.tiktok.com\tFALSE\t/\tFALSE\t0\ts2\tx" in lines
