from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from pydantic.dataclasses import dataclass
import asyncio
import adapters.api_adapter

@register("MHWSearch", "Cshyolin", "一个简单的搜索怪物猎人世界Wiki插件", "1.0.1")
class MHWSearch(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""

    @filter.command("mhws")
    async def search(self,event: AstrMessageEvent,key:str):    
        """搜索怪物猎人世界百科"""
        user_name=event.get_sender_name()
        #message=event.message_str
        yield event.plain_result(f"Hello {user_name},你尝试搜索了{key}")
        # 读取 api_adapter.py 中 main() 的返回值（它是 async 函数，需 await）
        res = await adapters.api_adapter.main(key)
        umo = event.unified_msg_origin
        provider_id = await self.context.get_current_chat_provider_id(umo=umo)
        llm_resp = await self.context.llm_generate(
            chat_provider_id=provider_id, # 聊天模型 ID
            prompt=f"请用中文翻译有关怪物猎人世界的如下内容：{res}",
        )
        yield event.plain_result(llm_resp.completion_text)
