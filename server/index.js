const express = require('express')
const cors = require('cors')
const multer = require('multer')
const path = require('path')
const fs = require('fs')
const OpenAI = require('openai')
const config = require('./config')

const app = express()
const PORT = config.server.port

app.use(cors({ origin: config.server.corsOrigin }))
app.use(express.json())

const client = new OpenAI({
  apiKey: config.dashscope.apiKey,
  baseURL: config.dashscope.baseURL
})

const uploadDir = path.join(__dirname, 'uploads')
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true })
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9)
    cb(null, uniqueSuffix + path.extname(file.originalname))
  }
})
const upload = multer({
  storage,
  limits: { fileSize: config.upload.maxFileSize }
})

function getModelConfig(modelId) {
  const model = config.models.find(m => m.id === modelId)
  if (!model) {
    return config.models[0]
  }
  return model
}

function buildMessages(modelConfig, question, history) {
  const messages = [
    { role: 'system', content: modelConfig.systemPrompt }
  ]

  if (history && Array.isArray(history)) {
    messages.push(...history)
  }

  messages.push({ role: 'user', content: question })

  return messages
}

function buildVisionMessages(modelConfig, question, imageBase64, mimeType) {
  const messages = [
    { role: 'system', content: modelConfig.systemPrompt }
  ]

  const userContent = []

  if (question) {
    userContent.push({
      type: 'text',
      text: question
    })
  }

  userContent.push({
    type: 'image_url',
    image_url: {
      url: `data:${mimeType};base64,${imageBase64}`
    }
  })

  messages.push({
    role: 'user',
    content: userContent
  })

  return messages
}

app.get('/api/models', (req, res) => {
  const modelList = config.models.map(m => ({
    id: m.id,
    name: m.name,
    type: m.type,
    description: m.description
  }))
  res.json({ code: 0, data: modelList })
})

app.post('/api/chat', async (req, res) => {
  const { modelId, question, history } = req.body

  if (!question) {
    return res.json({ code: -1, message: '请输入问题内容' })
  }

  const modelConfig = getModelConfig(modelId)

  try {
    const messages = buildMessages(modelConfig, question, history)

    // 设置流式响应头
    res.setHeader('Content-Type', 'text/plain; charset=utf-8')
    res.setHeader('Transfer-Encoding', 'chunked')
    res.setHeader('Cache-Control', 'no-cache')
    res.setHeader('Connection', 'keep-alive')

    const completion = await client.chat.completions.create({
      model: modelConfig.modelId,
      messages,
      max_tokens: modelConfig.maxTokens,
      temperature: modelConfig.temperature,
      stream: true // 开启流式输出
    })

    let tokens = 0

    // 处理流式响应
    for await (const chunk of completion) {
      const content = chunk.choices[0]?.delta?.content || ''
      if (content) {
        res.write(content)
        // 强制刷新缓冲区
        if (res.flush) res.flush()
      }
      // 记录token使用
      if (chunk.usage) {
        tokens = chunk.usage.total_tokens
      }
    }

    // 发送结束标记
    res.write(`\n\n---END---\n${JSON.stringify({
      tokens,
      model: modelConfig.name,
      timestamp: new Date().toISOString()
    })}`)
    res.end()
  } catch (error) {
    console.error('模型调用失败:', error.message)
    // 确保在错误情况下也能正确结束响应
    if (!res.headersSent) {
      res.json({
        code: -1,
        message: `模型服务调用失败: ${error.message}`
      })
    } else {
      res.write(`\n\n---ERROR---\n${JSON.stringify({ message: error.message })}`)
      res.end()
    }
  }
})

app.post('/api/chat/upload', upload.single('file'), async (req, res) => {
  const { modelId, question } = req.body
  const file = req.file

  if (!question && !file) {
    return res.json({ code: -1, message: '请输入问题或上传文件' })
  }

  const modelConfig = getModelConfig(modelId)
  const fileInfo = file
    ? {
        name: file.originalname,
        size: file.size,
        url: `/uploads/${file.filename}`
      }
    : null

  try {
    const isImage = file && config.upload.allowedTypes.includes(file.mimetype)

    let messages
    if (isImage) {
      const imageBuffer = fs.readFileSync(file.path)
      const imageBase64 = imageBuffer.toString('base64')
      messages = buildVisionMessages(modelConfig, question || '请分析这张图片', imageBase64, file.mimetype)
    } else {
      let fullQuestion = question || ''
      if (file && !isImage) {
        fullQuestion = `[用户上传了文件: ${file.originalname}]\n${question || '请分析这个文件'}`
      }
      messages = buildMessages(modelConfig, fullQuestion, [])
    }

    const completion = await client.chat.completions.create({
      model: modelConfig.modelId,
      messages,
      max_tokens: modelConfig.maxTokens,
      temperature: modelConfig.temperature
    })

    const content = completion.choices[0]?.message?.content || ''
    const usage = completion.usage

    res.json({
      code: 0,
      data: {
        content,
        suggestions: [],
        tokens: usage?.total_tokens || 0,
        model: modelConfig.name,
        timestamp: new Date().toISOString(),
        file: fileInfo
      }
    })
  } catch (error) {
    console.error('模型调用失败:', error.message)
    res.json({
      code: -1,
      message: `模型服务调用失败: ${error.message}`
    })
  }
})

app.use('/uploads', express.static(uploadDir))

app.listen(PORT, () => {
  console.log(`服务已启动: http://localhost:${PORT}`)
  console.log(`API 接口:`)
  console.log(`  GET  /api/models       - 获取模型列表`)
  console.log(`  POST /api/chat         - 发送问答`)
  console.log(`  POST /api/chat/upload  - 带文件上传的问答`)
  console.log(`已配置模型:`)
  config.models.forEach(m => {
    console.log(`  - ${m.name} (${m.type})`)
  })
})