#prompt_vieo 用于qwen vl描述视频的内容的提示词
prompt_vieo = """
你是一个安全监控人员，正在分析最新的监控画面，请把你看到的行为和视频内容描述出来，从开始到结束的内容请都详细描述出来。
200字以内，不要输出第一张画面、第二张画面，只需相较简洁的描述即可。
"""

# [历史上下文]
# {Recursive_summary}
#prompt_detect 用于deepseek检测视频内容时的提示词
prompt_detect = """请分析以下视频监控描述，判断是否存在重要情况如：睡觉、玩手机、喝饮料、喝水、吃东西或者专注工作）或异常情况（如人员聚集、冲突等）。
请以JSON格式返回分析结果，包含type（important/warning/normal）、reason（具体原因）和confidence（置信度）字段。

监控时间：{time}
视频描述：
{description}

请按以下格式返回（只返回JSON，不要其他说明）：
{{
    "type": "important/warning/normal",
    "reason": "检测到的具体原因",
    "confidence": 0.95
}}
"""

#prompt_summary 用于将历史描述进行压缩总结的提示词，使得描述更加简洁
prompt_summary = """
[系统角色] 您将接收到一系列按时间顺序排列的监控视频描述。请根据以下要求，将这些描述内容整合为一篇连贯的总结：

[历史上下文]
{histroy}

只需要逐步描述开始发生了什么，中间发生了什么、最后发生了什么。
请在整合信息后，直接输出内容，请输出简洁一点，不要超过200字。
"""