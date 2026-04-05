from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from pydantic.dataclasses import dataclass
import asyncio
from .adapters import api_adapter,wikiSearch
from typing import List,Dict,Any

from typing import Any

def _tables_to_markdown(
    tables: list[dict],
    user_prompt: str = "",
    # 全局白名单：允许输出的表格标题关键词（caption 或 headers 中包含这些词之一才有资格）
    whitelist_keywords: list[str] | None = None,
) -> str:
    """
    根据“白名单 + 用户提示词”筛选表格，并转为 Markdown。
    并在返回前输出一条日志，记录最终保留的表格信息。
    """
    if whitelist_keywords is None:
        # 根据现在这个页面的结构，起一个合理的默认白名单
        whitelist_keywords = [
            # 任务 & 基础信息
            "任务", "Quest",

            # 肉质 & 耐性
            "肉质", "耐性", "Hitzone",

            # 部位破坏
            "破坏部位", "部位", "Part", "Sever",

            # 状态异常
            "状态异常", "Ailment", "Status",

            # 掉落 & 素材相关
            "剥取素材", "任务报酬", "Investigation Reward",
            "报酬", "Reward", "掉落物", "素材",

            # 怪物动作
            "Monster Attacks", "攻击动作", "Attack Move",
        ]

    # 统一小写，方便不区分大小写匹配
    wl_kw_lower = [w.lower() for w in whitelist_keywords]

    user_prompt_lower = user_prompt.lower()

    def is_in_whitelist(table: dict) -> bool:
        caption = (table.get("caption") or "").lower()
        headers_join = " ".join(table.get("headers") or []).lower()
        haystack = caption + " " + headers_join
        if not haystack.strip():
            return False
        return any(kw in haystack for kw in wl_kw_lower)

    def matches_user_intent(table: dict) -> bool:
        # 非空提示词才做最简单的包含判断
        if not user_prompt_lower.strip():
            return True

        caption = (table.get("caption") or "").lower()
        headers_join = " ".join(table.get("headers") or []).lower()
        haystack = caption + " " + headers_join

        # 只要 user_prompt 中的任意一个词出现在 caption/headers 中就通过
        # 非常宽松，但基本不会“啥都没有”
        if any(word in haystack for word in user_prompt_lower.split()):
            return True

        # 否则，退回到只依赖白名单（即不过滤掉）
        return True

    parts: list[str] = []
    kept_tables: list[dict] = []

    for t in tables:
        # 先通过白名单过滤“不值得考虑的表”
        if not is_in_whitelist(t):
            continue

        # 再通过用户意图过滤当前会话不需要的表
        if not matches_user_intent(t):
            continue

        kept_tables.append(t)

        caption = t.get("caption") or ""
        headers = t.get("headers") or []
        rows = t.get("rows") or []

        if caption:
            parts.append(f"### {caption}")

        if headers:
            parts.append("| " + " | ".join(headers) + " |")
            parts.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for r in rows:
            parts.append("| " + " | ".join(r) + " |")

        parts.append("")  # 空行分隔

    # 日志输出：记录过滤结果
    try:
        summary = []
        for t in kept_tables:
            cap = (t.get("caption") or "").strip()
            headers = t.get("headers") or []
            summary.append(
                {
                    "caption": cap,
                    "headers_preview": headers[:5],
                    "row_count": len(t.get("rows") or []),
                }
            )
        logger.info(
            f"[gameinfo] tables_to_markdown 过滤完成，"
            f"用户提示词='{user_prompt}', "
            f"白名单关键词={whitelist_keywords}, "
            f"保留表格数量={len(kept_tables)}, "
            f"详情={summary}"
        )
    except Exception as e:
        logger.error(f"[gameinfo] tables_to_markdown 日志输出失败: {e}")

    return "\n".join(parts)

@register("MHWSearch", "Cshyolin", "一个简单的搜索怪物猎人世界Wiki插件", "1.1.1")
class MHWSearch(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.url="https://mhworld.kiranico.com/zh/monsters"

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
        res = await apiGate.searcher(key)
        umo = event.unified_msg_origin
        provider_id = await self.context.get_current_chat_provider_id(umo=umo) # type: ignore
        llm_resp = await self.context.llm_generate( # type: ignore
            chat_provider_id=provider_id, # 聊天模型 ID
            prompt=f"Please describe the following Monster Hunter World content in English, avoid using any markdown syntax nor formatting: {res}",
        )
        yield event.plain_result(llm_resp.completion_text)

    @filter.command("搜索世界百科")
    async def newSearch(self,event: AstrMessageEvent,name:str,key:str):
        '''新式搜索wiki'''
        user_name=event.get_sender_name()
        if not name:
            yield event.plain_result("查询项目不可为空！")
            return
        yield event.plain_result(f"你好，{user_name}，我已开始搜索，这可能会花一些时间！")
        #读取返回的正文文本内容
        plain_text,tables=await wikiSearch.runner(name,self.url)
        yield event.plain_result("已获取相关数据！大模型生成中...")
        tables_md=_tables_to_markdown(tables,key)
        prompt_body=(
            f"下面是用户查询的怪物猎人中的{name}的完整数据，包括描述文本和多张表格：\n"
            "【文本部分】\n"
            f"{plain_text}\n"
            "【表格部分(markdown)】\n"
            f"{tables_md}\n"
            f"用户希望了解这些内容中关于{key}的内容。请选取其中与之有关的内容，以markdown表格复述。复述数据时不得修改数据，不需要总结要点"
        )
        umo = event.unified_msg_origin
        provider_id = await self.context.get_current_chat_provider_id(umo=umo)
        llm_resp = await self.context.llm_generate(
            chat_provider_id=provider_id,
            prompt=prompt_body
        )
        yield event.plain_result(llm_resp.completion_text)
        yield event.plain_result("除数据外一切内容由LLM生成，请注意甄别！")

