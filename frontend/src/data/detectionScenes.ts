export interface DetectionScene {
  id: string
  name: string
  description: string
  defaultPrompt: string
  userPrompt: string
  endpoint: string
  modelId: string
  labelColors: Record<string, string>
}

export const detectionScenes: DetectionScene[] = [
  {
    id: 'meter-box',
    name: '计量箱缺陷检测',
    description: '对电力计量箱外观图像进行缺陷识别，包括箱体破损、封印缺失、接线异常等常见缺陷',
    defaultPrompt: '你是电力设备缺陷检测专家。请分析上传的计量箱图像，识别其中的缺陷并以JSON数组格式返回检测结果。每个检测结果包含bbox_2d和label字段，例如：[{"bbox_2d": [x1, y1, x2, y2], "label": "缺陷类型"}]。缺陷类型包括：箱体破损、封印缺失、接线松动、锈蚀、标签模糊、箱门未关、箱体老化、表面脏污。请直接返回JSON数组。',
    userPrompt: '请检测这张计量箱图片中的所有缺陷，以JSON数组格式返回，每个元素包含bbox_2d和label字段。',
    endpoint: 'http://localhost:11434/v1',
    modelId: 'qwen2.5-vl',
    labelColors: {
      '箱体破损': '#ff4444',
      '封印缺失': '#ff8800',
      '接线松动': '#ffcc00',
      '锈蚀': '#44aaff',
      '标签模糊': '#aa44ff',
      '箱门未关': '#ff4488',
      '箱体老化': '#cc8800',
      '表面脏污': '#88aa44'
    }
  },
  {
    id: 'meter-installation',
    name: '装表接电工艺检查',
    description: '对电表安装与接线工艺进行智能检查，识别接线错误、安装不规范、线缆裸露等工艺问题',
    defaultPrompt: '你是电力装表接电工艺检查专家。请分析上传的电表安装图像，检查接线工艺和安装质量，以JSON数组格式返回检测结果。每个检测结果包含bbox_2d和label字段，例如：[{"bbox_2d": [x1, y1, x2, y2], "label": "问题类型"}]。问题类型包括：接线错误、接线松动、线缆裸露、安装倾斜、螺丝缺失、线序错误、绝缘破损、接地不良。请直接返回JSON数组。',
    userPrompt: '请检查这张电表安装图片中的工艺问题，以JSON数组格式返回，每个元素包含bbox_2d和label字段。',
    endpoint: 'http://localhost:11434/v1',
    modelId: 'qwen2.5-vl',
    labelColors: {
      '接线错误': '#ff4444',
      '接线松动': '#ff8800',
      '线缆裸露': '#ffcc00',
      '安装倾斜': '#44aaff',
      '螺丝缺失': '#aa44ff',
      '线序错误': '#ff44aa',
      '绝缘破损': '#cc4400',
      '接地不良': '#44cc88'
    }
  },
  {
    id: 'meter-reading',
    name: '电表示数识别',
    description: '对电表显示屏进行智能识别，读取电表当前示数、峰谷平电量等数据信息',
    defaultPrompt: '你是电表读数识别专家。请分析上传的电表显示屏图像，识别电表示数信息并以JSON数组格式返回识别结果。每个识别结果包含bbox_2d和label字段，例如：[{"bbox_2d": [x1, y1, x2, y2], "label": "字段名称", "text": "识别内容"}]。需要识别的内容包括：正向有功总电量、正向有功峰电量、正向有功平电量、正向有功谷电量、反向有功总电量、电压、电流、功率。请直接返回JSON数组。',
    userPrompt: '请识别这张电表显示屏图片中的各项读数信息，以JSON数组格式返回，每个元素包含bbox_2d、label和text字段。',
    endpoint: 'http://localhost:11434/v1',
    modelId: 'qwen2.5-vl',
    labelColors: {
      '正向有功总电量': '#00d4ff',
      '正向有功峰电量': '#ff8800',
      '正向有功平电量': '#44aaff',
      '正向有功谷电量': '#00ff88',
      '反向有功总电量': '#ff4444',
      '电压': '#ffcc00',
      '电流': '#aa44ff',
      '功率': '#ff44aa'
    }
  }
]

export function getSceneById(id: string): DetectionScene {
  return detectionScenes.find(s => s.id === id) || detectionScenes[0]
}
