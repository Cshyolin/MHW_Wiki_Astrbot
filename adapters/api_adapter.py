import asyncio
from typing import Any, Dict, List, Optional, Tuple

import aiohttp


class MHWDBMonstersSearchClient:
    """
    仅搜索 monsters：
    - 拉取 /monsters 数据
    - 本地关键词匹配（name + description）
    """

    def __init__(self, base_url: str = "https://mhw-db.com", timeout: int = 20):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session and not self.session.closed:
            await self.session.close()

    async def _get_json(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if self.session is None:
            raise RuntimeError("ClientSession 未初始化，请使用 async with MHWDBMonstersSearchClient()")
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        async with self.session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    @staticmethod
    def _normalize(text: Any) -> str:
        return str(text or "").strip().lower()

    def _match_score(self, item: Dict[str, Any], keyword: str) -> Tuple[int, int]:
        """
        返回排序分值（分值越小越靠前）：
        0: name 精确相等
        1: name 包含关键词
        2: description 包含关键词
        3: 其他（不命中）
        第二个值用于稳定排序（id）
        """
        kw = self._normalize(keyword)
        name = self._normalize(item.get("name"))
        desc = self._normalize(item.get("description"))
        _id = item.get("id", 10**9)

        if not kw:
            return (0, _id)

        if name == kw:
            return (0, _id)
        if kw in name:
            return (1, _id)
        if kw in desc:
            return (2, _id)
        return (3, _id)

    def _filter_monsters(self, data: List[Dict[str, Any]], keyword: str) -> List[Dict[str, Any]]:
        scored = []
        for item in data:
            score = self._match_score(item, keyword)
            if score[0] < 3:  # 命中 name 或 description
                scored.append((score, item))

        scored.sort(key=lambda x: x[0])
        return [item for _, item in scored]

    async def search_monsters(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            data = await self._get_json("/monsters")
            if not isinstance(data, list):
                data = [data]
            matched = self._filter_monsters(data, keyword)
            return matched[:limit]
        except Exception as e:
            print(f"[WARN] monsters search failed: {e}")
            return []


def print_monsters_results(keyword: str, monsters: List[Dict[str, Any]]) -> str:
    if not monsters:
        return f"The results of keyword '{keyword}' are as follows:\nNo matched monsters found."

    lines = [f"The results of keyword '{keyword}' are as follows:"]
    for idx, item in enumerate(monsters, 1):
        _id = item.get("id", "N/A")
        name = item.get("name", "N/A")
        description = item.get("description", "N/A")
        lines.append(f"{idx}. id={_id}, name={name}, description={description}")

    return "\n".join(lines)


async def main(keyword: str) -> str:
    """主函数，输入关键词，输出搜索结果字符串"""
    limit = 10
    async with MHWDBMonstersSearchClient(timeout=20) as client:
        monsters = await client.search_monsters(keyword=keyword, limit=limit)
        return print_monsters_results(keyword, monsters)


#if __name__ == "__main__":
    #asyncio.run(main())
