import asyncio


async def create_project(client, video_dir) -> str:
    r = await client.post("/api/projects",
                          json={"name": "测试剧", "video_dir": str(video_dir)})
    assert r.status_code == 200
    return r.json()["id"]


async def wait_stage1(client, pid):
    for _ in range(100):
        r = await client.get(f"/api/projects/{pid}")
        eps = r.json()["episodes"]
        if all(e["status"] in ("done", "failed") for e in eps):
            return eps
        await asyncio.sleep(0.05)
    raise TimeoutError


async def test_project_crud(client, video_dir):
    pid = await create_project(client, video_dir)
    r = await client.get("/api/projects")
    assert [p["id"] for p in r.json()] == [pid]
    r = await client.get(f"/api/projects/{pid}")
    body = r.json()
    assert body["name"] == "测试剧"
    assert [e["episode"] for e in body["episodes"]] == [1, 2]
    assert all(e["status"] == "pending" for e in body["episodes"])


async def test_stage1_and_script_io(client, video_dir):
    pid = await create_project(client, video_dir)
    r = await client.post(f"/api/projects/{pid}/stage1/start", json={})
    assert r.status_code == 200
    eps = await wait_stage1(client, pid)
    assert all(e["status"] == "done" for e in eps)
    r = await client.get(f"/api/projects/{pid}/episodes/1/script")
    assert "第1集开场" in r.json()["content"]
    r = await client.put(f"/api/projects/{pid}/episodes/1/script",
                         json={"content": "人工修改后的剧本"})
    assert r.status_code == 200
    r = await client.get(f"/api/projects/{pid}/episodes/1/script")
    assert r.json()["content"] == "人工修改后的剧本"


async def test_stage2_to_5_flow(client, video_dir):
    pid = await create_project(client, video_dir)
    await client.post(f"/api/projects/{pid}/stage1/start", json={})
    await wait_stage1(client, pid)

    r = await client.post(f"/api/projects/{pid}/stage2/generate")
    assert r.status_code == 200
    r = await client.get(f"/api/projects/{pid}/artifacts/analysis")
    assert r.json()["content"] == "模拟LLM输出"

    r = await client.post(f"/api/projects/{pid}/stage3/suggest")
    assert r.json()["content"] == "模拟LLM输出"
    r = await client.post(f"/api/projects/{pid}/stage3/refine",
                          json={"draft": "我的草稿"})
    assert r.status_code == 200

    r = await client.post(f"/api/projects/{pid}/stage4/generate")
    assert r.status_code == 200

    r = await client.post(f"/api/projects/{pid}/stage5/generate",
                          json={"episode": 1})
    assert r.status_code == 200
    r = await client.get(f"/api/projects/{pid}/scripts/1")
    assert r.json()["content"] == "模拟LLM输出"

    r = await client.get(f"/api/projects/{pid}/export", params={"which": "new"})
    assert "全剧剧本汇总" in r.text


async def test_stage2_requires_episodes(client, video_dir):
    pid = await create_project(client, video_dir)
    r = await client.post(f"/api/projects/{pid}/stage2/generate")
    assert r.status_code == 400   # 还没有任何已扒的剧本


async def test_missing_resources(client, video_dir):
    pid = await create_project(client, video_dir)
    r = await client.get(f"/api/projects/{pid}/episodes/1/script")
    assert r.status_code == 404
    r = await client.get("/api/projects/nonexist")
    assert r.status_code == 404


# ---------- 模型设置 ----------

async def test_get_settings(client):
    r = await client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["gemini"]["api_key"] == "gk"
    assert data["text_llm"]["provider"] == "fake"
    assert data["text_llm"]["providers"]["fake"]["base_url"] == "http://x"


async def test_put_settings_updates_and_persists(client):
    body = {
        "gemini": {"api_key": "new-gk", "model": "g2",
                   "base_url": "https://proxy.example.com", "upload": "inline"},
        "text_llm": {"provider": "lemon",
                     "providers": {"lemon": {"base_url": "https://l/v1",
                                             "api_key": "sk-1", "model": "m1"}}},
    }
    r = await client.put("/api/settings", json=body)
    assert r.status_code == 200
    r = await client.get("/api/settings")
    data = r.json()
    assert data["gemini"]["api_key"] == "new-gk"
    assert data["gemini"]["upload"] == "inline"
    assert data["text_llm"]["provider"] == "lemon"


async def test_put_settings_invalid_provider(client):
    body = {
        "gemini": {"api_key": "gk", "model": "m"},
        "text_llm": {"provider": "nope",
                     "providers": {"fake": {"base_url": "http://x",
                                            "api_key": "k", "model": "m"}}},
    }
    r = await client.put("/api/settings", json=body)
    assert r.status_code == 400
