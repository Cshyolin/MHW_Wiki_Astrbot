import aiohttp
from selectolax.parser import HTMLParser
from astrbot.api import logger
from typing import Optional, Any, Dict, List, Tuple

class NewSearcher:
    def _cleanup_multiline_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]  # 去除空行
        return "\n".join(lines)
    
    def _extract_cell_text(self, cell_node) -> str:
        """
        从一个 <td>/<th> 节点中提取对 LLM 有用的文本，尽量去掉多余噪音：
        - 忽略图片自身，只保留旁边的文字
        - 处理 abbr 的 title + 文本
        - 合并多行 div 到一行
        """
        # 特殊：abbr 优先使用 title 信息
        abbr = cell_node.css_first("abbr")
        if abbr is not None:
            title = abbr.attributes.get("title", "").strip()
            visible = abbr.text(separator=" ", strip=True)
            if title and visible and title != visible:
                return f"{title} ({visible})"
            return title or visible

        # 去掉 img 标签（不删除节点，只是不从中取文字）
        for img in cell_node.css("img"):
            img.decompose()

        # 有时候会嵌套很多 div / span / a；直接用 text() 会把它们串起来
        raw = cell_node.text(separator=" ", strip=True)

        # 简单规整一下空白
        if not raw:
            return ""

        # 把多余空格压缩为单空格
        import re
        raw = re.sub(r"\s+", " ", raw)

        return raw
    
    def _parse_html_table(self, table_node) -> Optional[Dict[str, Any]]:
        """
        将一个 Kiranico 怪物页面里的 <table> 解析为结构化数据：
        {
            "caption": "剥取素材" / "肉质与耐性" 等（若能识别）,
            "headers": [列名...],
            "rows": [[单元格文本...], ...]
        }
        """
        # 1. caption（有就用，没有就留空）
        caption_text = ""
        caption_node = table_node.css_first("caption")
        if caption_node:
            caption_text = self._cleanup_multiline_text(
                caption_node.text(separator=" ", strip=True)
            )
    
        # 2. 表头
        headers: list[str] = []
        data_rows_nodes = []
    
        thead_rows = table_node.css("thead tr")
        if thead_rows:
            for tr in thead_rows:
                for cell in tr.css("th, td"):
                    headers.append(self._extract_cell_text(cell))
            data_rows_nodes = table_node.css("tbody tr") or []
        else:
            body_rows = table_node.css("tbody tr") or table_node.css("tr")
            if body_rows:
                first_row = body_rows[0]
                for cell in first_row.css("th, td"):
                    headers.append(self._extract_cell_text(cell))
                data_rows_nodes = body_rows[1:]
            else:
                data_rows_nodes = []
    
        # 3. 数据行
        raw_rows: list[list[str]] = []
        max_cols = len(headers) if headers else 0
    
        for tr in data_rows_nodes:
            row: list[str] = []
            for cell in tr.css("td, th"):
                txt = self._extract_cell_text(cell)
                row.append(txt)
            if any(col for col in row):
                raw_rows.append(row)
                if len(row) > max_cols:
                    max_cols = len(row)
    
        # 4. 归一列数
        target_cols = len(headers) if headers else max_cols
        normalized_rows: list[list[str]] = []
        for row in raw_rows:
            if len(row) < target_cols:
                row = row + [""] * (target_cols - len(row))
            elif len(row) > target_cols:
                row = row[:target_cols]
            normalized_rows.append(row)
    
        if not headers and not normalized_rows:
            return None
    
        return {
            "caption": caption_text,
            "headers": headers,
            "rows": normalized_rows,
    }

    async def fetch_html(self,url:str)->str:
        '''获取HTML文件'''
        logger.info(f"开始抓取HTML文件")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        timeout=aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")
                return await resp.text()
    
    async def search_in_page(self,name:str,base_url:str)->Optional[str]:
        '''抓取列表并搜索角色的URL
        结构：
        <a href="https://mhworld.kiranico.com/zh/monsters/wA8F8/ming-deng-long">冥灯龙</a>
        '''
        html=await self.fetch_html(base_url)
        tree=HTMLParser(html)
        anchors=tree.css("a")
        candidates=[]
        for a in anchors:
            text = a.text(separator="", strip=True)  # 链接文字
            if not text:
                continue

            if text == name:
                href = (a.attributes.get("href") or "").strip()
                if not href:
                    continue

                # 绝对链接直接返回
                if href.startswith("http://") or href.startswith("https://"):
                    return href
                else:
                    # 相对链接使用 urljoin 拼接
                    from urllib.parse import urljoin
                    return urljoin(base_url, href)
        return None
    
    def extract_text(self,html:str)->Dict[str,Any]:
        '''从详情页HTML提取内容'''
        '''
        XPATH = //*[@id="app"]/div/div/div[3]/div[3]/div[1]
        结构示例：
        {
            "plain_text": "......整个主要内容的纯文本......",
            "tables": [
                {
                    "caption": "表格标题（如果能识别到）",
                    "headers": ["列1", "列2", "列3"],
                    "rows": [
                        ["单元格11", "单元格12", "单元格13"],
                        ["单元格21", "单元格22", "单元格23"],
                        ...
                    ]
                },
                ...
            ]
        }
        '''
        tree = HTMLParser(html)

        # 1. 主容器：根据页面实际结构，怪物数据都在 #mhworld-article 里面
        article = tree.css_first("#mhworld-article")
        if article is None:
            # 兜底：用整个 content-box（以 h6 标题“任务 / 肉质与耐性 / 剥取素材”等为特征）
            # 这里简单退回 body，必要时可以再按 class 精细化
            article = tree.body

        if article is None:
            return {"plain_text": "", "tables": []}

        # 2. 在 article 中解析所有表格
        tables: List[Dict[str, Any]] = []
        for table in article.css("table"):
            parsed = self._parse_html_table(table)
            if parsed is not None:
                tables.append(parsed)

        # 3. 提取主文本（不做强过滤，交给 LLM 自己归纳）
        #    如果你想更“干净”，可以先移除某些区块再取 text()
        plain_text_raw = article.text(separator="\n", strip=True)
        plain_text = self._cleanup_multiline_text(plain_text_raw)

        return {
            "plain_text": plain_text,
            "tables": tables,
        }

async def runner(name:str,url:str):
    x=NewSearcher()
    content_url=await x.search_in_page(name,url)
    html=await x.fetch_html(content_url)
    content=x.extract_text(html)
    plain_text = content["plain_text"]
    tables = content["tables"]
    return plain_text,tables

