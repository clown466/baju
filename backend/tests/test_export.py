from app.export import export_full

def test_export_full():
    out = export_full("测试剧", {1: "第一集剧本内容", 2: None, 3: "第三集剧本内容"})
    assert out.startswith("《测试剧》全剧剧本汇总")
    assert "- 总集数:3" in out
    assert "- 成功:2 集 / 失败:1 集" in out
    assert "- [第1集](#第1集)" in out
    assert "第一集剧本内容" in out
    assert "（本集缺失）" in out
    # 目录在正文之前
    assert out.index("- [第3集]") < out.index("第三集剧本内容")
