"""
配置文件示例
复制此文件为 config.py 并填写你的配置
"""

# LLM配置
LLM_CONFIG = {
    # DeepSeek配置
    "deepseek": {
        "provider": "deepseek/deepseek-chat",
        "api_token": "your-deepseek-api-key-here",  # 替换为你的 API Key
        "base_url": "https://api.deepseek.com"
    },

    # OpenAI配置（示例）
    "openai": {
        "provider": "openai/gpt-4o-mini",
        "api_token": "your-openai-api-key-here",
        "base_url": "https://api.openai.com"
    }
}

# 爬虫默认配置
CRAWLER_CONFIG = {
    "max_depth": 2,                                    # 最大递归深度
    "max_pages": 20,                                   # 最大爬取页面数
    "output_dir": "output",                            # 输出目录
    "headless": True,                                  # 无头模式
    "verbose": False,                                  # 详细日志
    "template_path": "templates/template_deepseek_pricing.json",  # 默认模板文件路径
    "start_url": "https://api-docs.deepseek.com/zh-cn/",  # 默认起始URL
    "enable_recursive": True,                          # 是否启用递归爬取
}

# 浏览器配置
BROWSER_CONFIG = {
    "headless": True,
    "verbose": False,
    "viewport_width": 1920,
    "viewport_height": 1080,
}
