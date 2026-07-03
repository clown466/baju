# 短剧扒剧与仿写 — 后端

## 安装

```bash
cd backend
pip install -r requirements.txt
cp config.yaml.example config.yaml   # 填入真实 API key
```

## 运行

```bash
cd backend
python -m app.main
# API 文档: http://127.0.0.1:8000/docs
```

## 冒烟测试（需真实 Gemini key 与一个短视频）

```bash
# 1. 创建项目（video_dir 指向含 1 个短视频的目录）
curl -X POST http://127.0.0.1:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "冒烟测试", "video_dir": "D:/test_videos"}'

# 2. 启动扒剧（用返回的项目 id）
curl -X POST http://127.0.0.1:8000/api/projects/<pid>/stage1/start -H "Content-Type: application/json" -d '{}'

# 3. 查看进度
curl http://127.0.0.1:8000/api/projects/<pid>

# 4. 查看扒出的剧本
curl http://127.0.0.1:8000/api/projects/<pid>/episodes/1/script
```

## 测试

```bash
cd backend && python -m pytest tests/ -v
```
