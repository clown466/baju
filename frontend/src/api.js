async function http(method, url, body) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(url, opts)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch { /* 非 JSON 响应，保留 statusText */ }
    throw new Error(detail)
  }
  return res.json()
}

export const listProjects = () => http('GET', '/api/projects')
export const createProject = (name, videoDir) =>
  http('POST', '/api/projects', { name, video_dir: videoDir })
export const getProject = (pid) => http('GET', `/api/projects/${pid}`)
export const updateMapping = (pid, episodes) =>
  http('PUT', `/api/projects/${pid}/episodes-mapping`, { episodes })

export const stage1Start = (pid, episodes = null) =>
  http('POST', `/api/projects/${pid}/stage1/start`, { episodes })
export const stage1Cancel = (pid) => http('POST', `/api/projects/${pid}/stage1/cancel`)

export const getEpisodeScript = (pid, ep) =>
  http('GET', `/api/projects/${pid}/episodes/${ep}/script`)
export const putEpisodeScript = (pid, ep, content) =>
  http('PUT', `/api/projects/${pid}/episodes/${ep}/script`, { content })

export const stage2Generate = (pid) => http('POST', `/api/projects/${pid}/stage2/generate`)
export const stage3Suggest = (pid) => http('POST', `/api/projects/${pid}/stage3/suggest`)
export const stage3Refine = (pid, draft) =>
  http('POST', `/api/projects/${pid}/stage3/refine`, { draft })
export const stage4Generate = (pid) => http('POST', `/api/projects/${pid}/stage4/generate`)

export const stage5Generate = (pid, episode, extra = '') =>
  http('POST', `/api/projects/${pid}/stage5/generate`, { episode, extra })
export const stage5Start = (pid, episodes = null, extra = '') =>
  http('POST', `/api/projects/${pid}/stage5/start`, { episodes, extra })

export const getArtifact = (pid, kind) => http('GET', `/api/projects/${pid}/artifacts/${kind}`)
export const putArtifact = (pid, kind, content) =>
  http('PUT', `/api/projects/${pid}/artifacts/${kind}`, { content })

export const getNewScript = (pid, ep) => http('GET', `/api/projects/${pid}/scripts/${ep}`)
export const putNewScript = (pid, ep, content) =>
  http('PUT', `/api/projects/${pid}/scripts/${ep}`, { content })

export const exportUrl = (pid, which) => `/api/projects/${pid}/export?which=${which}`
