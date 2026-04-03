# astrbot_plugin_mhw_wiki

创建自AstrBot 插件模板 / Created from a template plugin for AstrBot plugin feature

这是一个使用astrbot查询《怪物猎人：荒野》Wiki的插件。本人第一次制作插件，难免有错，请多多包涵

# Functions

| 指令格式                         | 输入语言 | 搜索目标                     | 关键词含义                         | 返回内容语言 | 返回内容示例/用途                                               |
|----------------------------------|----------|------------------------------|------------------------------------|--------------|------------------------------------------------------------------|
| `/mhws <keyword>`               | 英文     | 怪物简介 / 概览信息         | `<keyword>` 为怪物英文名或相关词 | 英文         | 直接返回该怪物的英文简介，用于查阅原版 wiki 描述     |
| `/搜索世界百科 <name> <keyword>` | 中文     | 某怪物在某一方面的详细数据 | `<name>` 为怪物中文名，`<keyword>` 为要看的数据类型（如“肉质”“状态异常”“任务报酬”“素材掉落”等） | 中文         | 抓取怪物在对应方面的结构化数据（表格等），送入大模型按中文提示整理后用中文输出，适合做攻略/分析 |

数据来自 Monster Hunter World API 和 KIRANICO MH:WORLD 百科（见下）

# Supports

- [MHWDB-API](https://github.com/LartTyler/MHWDB-API)
- [MHWDB-DOCS](https://github.com/LartTyler/MHWDB-Docs)
- [KIRANICO MH:WORLD](https://mhworld.kiranico.com/zh)
- GPT-5.3 CODEX
