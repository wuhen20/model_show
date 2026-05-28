module.exports = {
  // ============ 阿里云百炼 API 配置 ============
  dashscope: {
    apiKey: 'sk-01fc9e4829ff4617afe2aa3d4f0d3b97',
    baseURL: 'https://dashscope.aliyuncs.com/compatible-mode/v1'
  },

  // ============ 模型配置 ============
  models: [
    {
      id: 'qwen-plus',
      name: 'Qwen2-72B',
      type: '语言模型',
      description: '通义千问2 72B，高性能语言模型，支持复杂对话与分析',
      modelId: 'qwen-plus',
      maxTokens: 8192,
      temperature: 0.7,
      systemPrompt: '你是电力业务智能助手，专注于电力系统分析、台区线损诊断、设备缺陷识别、负荷预测等电力业务场景。请用专业、简洁、结构化的方式回答用户问题。'
    },
    {
      id: 'qwen-vl-plus',
      name: 'Qwen-VL-Plus',
      type: '视觉模型',
      description: '通义千问VL Plus，多模态视觉理解与图像分析',
      modelId: 'qwen-vl-plus',
      maxTokens: 4096,
      temperature: 0.7,
      systemPrompt: '你是电力业务多模态智能助手，擅长分析电力设备图像、巡检照片、图表等视觉内容。请结合图像信息给出专业的电力业务分析。'
    }
  ],

  // ============ 服务配置 ============
  server: {
    port: 3002,
    corsOrigin: '*'
  },

  // ============ 上传配置 ============
  upload: {
    maxFileSize: 10 * 1024 * 1024, // 10MB
    allowedTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp']
  }
}