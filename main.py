"""
AstrBot 三月七语句插件 

功能描述：
- 随机输出《崩坏·星穹铁道》三月七经典台词
- 支持用户自定义添加、删除、管理语句
- 用户级防刷屏与群聊日限机制

作者: HamLJYH
版本: 1.0.4
日期: 2026-08-10
"""

# 标准库
import os
import json
import time
import random
import functools
from typing import Dict, Any, AsyncGenerator, Tuple

# 第三方库
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

__version__ = "1.0.4"

# 常量
MAX_CONTENT_LENGTH = 500


def handle_errors(func):
    """统一错误处理装饰器"""
    @functools.wraps(func)
    async def wrapper(self, event: AstrMessageEvent, *args, **kwargs) -> AsyncGenerator[Any, None]:
        try:
            async for result in func(self, event, *args, **kwargs):
                yield result
        except ValueError as e:
            logger.warning(f"[{func.__name__}] 参数错误: {e}")
            yield event.plain_result(f"参数错误: {e}")
        except PermissionError:
            logger.error(f"[{func.__name__}] 权限不足")
            yield event.plain_result("权限不足，请检查文件权限")
        except Exception as e:
            logger.error(f"[{func.__name__}] 执行失败: {e}", exc_info=True)
            yield event.plain_result("操作失败，请稍后重试")
    return wrapper


@register("march7th_quotes", "HamLJYH", "三月七语句插件", "1.0.2", "https://github.com/yourname/astrbot_plugin_march7th")
class March7thQuotesPlugin(Star):
    def __init__(self, context: Context, config: Dict[str, Any] = None):
        super().__init__(context)

        # 读取配置
        self.config = config or {}
        self.anti_spam_enabled = self.config.get("anti_spam_enabled", True)
        self.anti_spam_interval = self.config.get("anti_spam_interval", 10)
        self.group_daily_limit_enabled = self.config.get("group_daily_limit_enabled", True)
        self.group_daily_limit = self.config.get("group_daily_limit", 50)

        # 防刷屏记录
        self.user_cooldown: Dict[str, float] = {}

        # 群聊每日触发记录：{group_id: {"count": int, "date": str}}
        self.group_daily_count: Dict[str, Dict[str, Any]] = {}

        # 三月七默认语句库（纯字符串列表）
        self.default_quotes = [
            "我的过去或许不在从前，而是在我的未来里，所以我一定会一站站走下去，哪怕有一天没有列车。",
            "你好，开拓者。欢迎入职星穹列车，我是三月七，星穹列车的乘员，也是你的同事。现在，请先拍摄入职照…瞧把你吓的，咱是在开玩笑啦~！",
            "哎呀，你来得正好，今天还没一起拍过照呢。",
            "我整理完今天的照片就休息啦，你也别熬夜打游戏哦！",
            "名字是我自己取的，大家也叫我三月、小三月…你呢？你想叫我什么？",
            "我的过去，或许不在从前，而是在我的未来里。所以我一定会一站站走下去，哪怕有一天…没有列车。",
            "果汁…一说就觉得馋，一馋就忒想喝，一喝就…停不下来……",
            "照片当然不是现实，但如果有足够多的照片，是不是就能更接近现实一些呢？",
            "拍照，写日记，还用说嘛~",
            "要是没人和我聊天，我就闷得要命。但在列车上的时候，姬子很忙，杨叔很忙，帕姆很忙，丹恒倒是不忙，可他不喜欢聊天……",
            "每次坐在书桌前整理完相册，抬头看向窗外，即使那一幕已经见过千遍万遍，我总是想再拍一张照片…现在咱能坐在列车里，像这样看着星星，真的很幸福。",
            "我平时很喜欢仙舟幻戏嘛，心里一直有点剑侠情结。等我真正开始学剑之后，才发现比起幻戏里飞天遁地的大侠，还是教我一招一式的两位小师父更厉害！",
            "即使看起来很「黑暗」的料理，也要拿出「开拓」的精神来面对！但，实话实说，砂鳗冻和姬子泡的咖啡真不太好……",
            "丹恒…他在我之前上的车，从没透露过自己的来历…你要是有机会，也帮我打探打探？",
            "美丽的姬子姐姐，成熟，可靠，又优雅，还是列车的领航员…以后，我也可以成为那样的大人吧！不过咱现在这样也很好~",
            "听说杨叔曾经是秘密组织的首领，拯救过星球，当过老师，还画过动画的原画！哎，简直是外星人了……",
            "列车长就是最棒的！",
            "即使知道了他的神秘过去，他还是我们认识的那个丹恒呀！",
            "彦卿师父的教学风格非常严谨，也一直把「将军当年是这么教我的」挂在嘴边…看来，景元将军教给他的，他都记得清清楚楚。",
            "云璃师父的教学风格非常自由，她最常和我说的话是：「这是一种感觉！」…也许这就是「体验式教学」吧？",
            "如果让列车长听到那段「七休日」的主张，不知道会是什么反应呀。",
            "我的过去，正在一点点变多呢。",
            "今天的我比昨天更棒了~",
            "没错没错，我还藏着几招哪~",
            "有咱俩在，那就见一个打一个喽~",
            "本姑娘要展现真正的技术了…呃，丹恒你那是什么眼神？",
            "本姑娘要展现真正的技术了…呃，丹恒你总该相信我了吧！",
            "万一有个万一，姬子你要帮帮我哦！",
            "有万能的杨叔在，好耶！我是不是说太响了？",
            "云璃师父，来检验一下我的修行成果吧！",
            "彦卿师父放心，咱不会给你丢人的！",
            "嗯！看着比用指挥棒的时候厉害多了！",
            "一二三，三月七！",
        ]

        # 用户自定义语句文件路径
        self.custom_quotes_file = os.path.join(os.path.dirname(__file__), "custom_quotes.json")
        self.custom_quotes = self._load_custom_quotes()

        # 合并默认和用户自定义
        self.all_quotes = self.default_quotes + self.custom_quotes
        logger.info(f"三月七语句插件加载完成，共 {len(self.all_quotes)} 条语句（默认 {len(self.default_quotes)} 条，自定义 {len(self.custom_quotes)} 条）")

    def _load_custom_quotes(self) -> list:
        """加载用户自定义语句"""
        if os.path.exists(self.custom_quotes_file):
            try:
                with open(self.custom_quotes_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载自定义语句失败: {e}")
                return []
        return []

    def _save_custom_quotes(self) -> bool:
        """保存用户自定义语句"""
        try:
            with open(self.custom_quotes_file, "w", encoding="utf-8") as f:
                json.dump(self.custom_quotes, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存自定义语句失败: {e}")
            return False

    def _format_quote(self, quote: str, is_custom: bool = False) -> str:
        """格式化语句输出

        Args:
            quote: 语句内容
            is_custom: 是否为自定义语句

        Returns:
            格式化后的字符串
        """
        result = ""
        if is_custom:
            result += "[自定义]\n\n"
        result += quote
        return result

    def _get_today_str(self) -> str:
        """获取今天的日期字符串 (YYYY-MM-DD)"""
        return time.strftime("%Y-%m-%d", time.localtime())

    def _clean_expired_records(self) -> None:
        """清理过期的用户冷却记录和群聊计数记录"""
        current_time = time.time()
        expire_time = current_time - 86400

        # 清理用户冷却记录
        expired_users = [
            uid for uid, t in self.user_cooldown.items() 
            if t < expire_time
        ]
        for uid in expired_users:
            del self.user_cooldown[uid]

        # 清理群聊计数记录（非今天的）
        today = self._get_today_str()
        expired_groups = [
            gid for gid, data in self.group_daily_count.items() 
            if data.get("date") != today
        ]
        for gid in expired_groups:
            del self.group_daily_count[gid]

    def _check_user_spam(self, user_id: str) -> Tuple[bool, str]:
        """检查用户是否触发个人防刷屏机制

        Args:
            user_id: 用户ID

        Returns:
            (是否允许触发, 提示信息)
        """
        if not self.anti_spam_enabled:
            return True, ""

        self._clean_expired_records()

        current_time = time.time()
        last_time = self.user_cooldown.get(user_id, 0)

        if current_time - last_time < self.anti_spam_interval:
            remaining = int(self.anti_spam_interval - (current_time - last_time))
            return False, f"触发太快了啦！请 {remaining} 秒后再试~"

        self.user_cooldown[user_id] = current_time
        return True, ""

    def _check_group_limit(self, group_id: str) -> Tuple[bool, str]:
        """检查群聊是否达到每日触发上限

        Args:
            group_id: 群聊ID

        Returns:
            (是否允许触发, 提示信息)
        """
        if not self.group_daily_limit_enabled:
            return True, ""

        self._clean_expired_records()

        today = self._get_today_str()

        if group_id not in self.group_daily_count:
            self.group_daily_count[group_id] = {"count": 0, "date": today}

        group_data = self.group_daily_count[group_id]

        # 如果日期不是今天，重置计数
        if group_data.get("date") != today:
            group_data = {"count": 0, "date": today}
            self.group_daily_count[group_id] = group_data

        if group_data["count"] >= self.group_daily_limit:
            return False, f"本群今天的三月七语句次数已经用完啦！明天再来吧~（上限: {self.group_daily_limit}次/天）"

        group_data["count"] += 1
        return True, ""

    def _validate_content(self, content: str) -> None:
        """验证语句内容

        Args:
            content: 待验证的内容

        Raises:
            ValueError: 内容不合法时抛出
        """
        if not content or not content.strip():
            raise ValueError("内容不能为空")
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"内容过长，最多 {MAX_CONTENT_LENGTH} 字符")

    @filter.command_group("三月七")
    def march7th_group(self) -> None:
        """三月七语句插件指令组"""
        pass

    @march7th_group.command("语句")
    @handle_errors
    async def march7th_quote(self, event: AstrMessageEvent):
        '''随机输出一条三月七的语句'''
        user_id = str(event.get_sender_id())
        group_id = str(event.get_group_id()) if event.get_group_id() else "private_" + user_id

        # 个人防刷屏检查
        allowed, msg = self._check_user_spam(user_id)
        if not allowed:
            yield event.plain_result(msg)
            return

        # 群聊每日限制检查
        allowed, msg = self._check_group_limit(group_id)
        if not allowed:
            yield event.plain_result(msg)
            return

        if not self.all_quotes:
            yield event.plain_result("暂无语句，请先使用 /三月七 添加 添加一些吧！")
            return

        quote = random.choice(self.all_quotes)
        is_custom = quote in self.custom_quotes
        yield event.plain_result(self._format_quote(quote, is_custom))

    @march7th_group.command("添加")
    @handle_errors
    async def add_quote(self, event: AstrMessageEvent):
        '''添加一条自定义三月七语句。用法: /三月七 添加 语句内容'''
        # 从消息文本解析参数
        message = event.message_str
        # 去掉命令前缀
        if message.startswith("/三月七 添加"):
            args_str = message[len("/三月七 添加"):].strip()
        else:
            args_str = message[len("三月七 添加"):].strip()

        if not args_str or not args_str.strip():
            yield event.plain_result(
                "语句内容不能为空！\n"
                "用法: /三月七 添加 语句内容\n"
                "示例: /三月七 添加 三月七最可爱啦！"
            )
            return

        # 解析参数：支持引号包裹的内容
        if args_str.startswith('"') or args_str.startswith("'"):
            quote_char = args_str[0]
            end_idx = args_str.find(quote_char, 1)
            if end_idx != -1:
                new_content = args_str[1:end_idx].strip()
            else:
                new_content = args_str.strip().strip('"').strip("'")
        else:
            new_content = args_str.strip()

        # 验证内容
        self._validate_content(new_content)

        # 检查是否已存在
        if new_content in self.all_quotes:
            yield event.plain_result("这条语句已经存在啦！")
            return

        self.custom_quotes.append(new_content)
        self.all_quotes = self.default_quotes + self.custom_quotes

        if self._save_custom_quotes():
            yield event.plain_result(
                "语句添加成功！\n\n"
                + self._format_quote(new_content, is_custom=True) + "\n\n"
                + f"当前共有 {len(self.all_quotes)} 条语句（自定义 {len(self.custom_quotes)} 条）"
            )
        else:
            yield event.plain_result("语句添加失败，请检查文件权限。")

    @march7th_group.command("删除")
    @handle_errors
    async def delete_quote(self, event: AstrMessageEvent):
        '''删除包含指定关键词的自定义语句。用法: /三月七 删除 关键词'''
        # 从消息文本解析参数
        message = event.message_str
        if message.startswith("/三月七 删除"):
            keyword = message[len("/三月七 删除"):].strip()
        else:
            keyword = message[len("三月七 删除"):].strip()

        if not keyword or not keyword.strip():
            yield event.plain_result(
                "关键词不能为空！\n"
                "用法: /三月七 删除 关键词\n"
                "示例: /三月七 删除 开拓者"
            )
            return

        keyword = keyword.strip()

        # 只能删除自定义语句
        original_count = len(self.custom_quotes)
        self.custom_quotes = [
            q for q in self.custom_quotes 
            if keyword not in q
        ]
        deleted_count = original_count - len(self.custom_quotes)

        if deleted_count == 0:
            yield event.plain_result("未找到包含「" + keyword + "」的自定义语句。\n注意：默认语句无法删除。")
            return

        self.all_quotes = self.default_quotes + self.custom_quotes

        if self._save_custom_quotes():
            yield event.plain_result(
                "已删除 " + str(deleted_count) + " 条包含「" + keyword + "」的语句。\n"
                + f"当前共有 {len(self.all_quotes)} 条语句（自定义 {len(self.custom_quotes)} 条）"
            )
        else:
            yield event.plain_result("删除失败，请检查文件权限。")

    @march7th_group.command("列表")
    @handle_errors
    async def list_quotes(self, event: AstrMessageEvent, page: int = 1):
        '''列出所有自定义语句。用法: /三月七 列表 [页码]'''
        if not self.custom_quotes:
            yield event.plain_result("暂无自定义语句。\n使用 /三月七 添加 来添加你的第一条语句吧！")
            return

        per_page = 10
        total_pages = (len(self.custom_quotes) + per_page - 1) // per_page

        if page < 1:
            page = 1
        if page > total_pages:
            page = total_pages

        start = (page - 1) * per_page
        end = start + per_page
        page_quotes = self.custom_quotes[start:end]

        result = "自定义语句列表（第 " + str(page) + "/" + str(total_pages) + " 页，共 " + str(len(self.custom_quotes)) + " 条）\n"
        result += "-" * 30 + "\n"

        for i, quote in enumerate(page_quotes, start=start + 1):
            content = quote
            # 截断过长的内容
            if len(content) > 30:
                content = content[:30] + "..."
            result += str(i) + ". " + content + "\n"

        if total_pages > 1:
            result += "\n使用 /三月七 列表 " + str(page + 1 if page < total_pages else 1) + " 翻页"

        yield event.plain_result(result)

    @march7th_group.command("统计")
    @handle_errors
    async def stats_quotes(self, event: AstrMessageEvent):
        '''查看语句统计信息'''
        result = "三月七语句统计\n"
        result += "-" * 30 + "\n"
        result += "总语句数: " + str(len(self.all_quotes)) + "\n"
        result += "  - 默认语句: " + str(len(self.default_quotes)) + "\n"
        result += "  - 自定义语句: " + str(len(self.custom_quotes)) + "\n"

        yield event.plain_result(result)

    @march7th_group.command("帮助")
    @handle_errors
    async def help_quotes(self, event: AstrMessageEvent):
        '''查看三月七语句插件帮助信息'''
        # 配置状态
        user_spam_status = "已开启" if self.anti_spam_enabled else "已关闭"
        user_spam_interval = f"{self.anti_spam_interval}秒" if self.anti_spam_enabled else "N/A"
        group_limit_status = "已开启" if self.group_daily_limit_enabled else "已关闭"
        group_limit = f"{self.group_daily_limit}次/天" if self.group_daily_limit_enabled else "N/A"

        help_lines = [
            "三月七语句插件",
            "",
            "配置信息:",
            "  用户防刷屏: " + user_spam_status + "（间隔: " + user_spam_interval + "）",
            "  群聊日限: " + group_limit_status + "（上限: " + group_limit + "）",
            "",
            "指令列表:",
            "------------------------------",
            "/三月七 语句 - 随机输出一条三月七语句",
            "/三月七 添加 <内容> - 添加自定义语句",
            "/三月七 删除 <关键词> - 删除包含关键词的自定义语句",
            "/三月七 列表 [页码] - 查看自定义语句列表",
            "/三月七 统计 - 查看语句统计信息",
            "/三月七 帮助 - 显示此帮助信息",
            "",
            "使用示例:",
            "------------------------------",
            "/三月七 语句",
            "-> 随机输出一条三月七语句",
            "",
            '/三月七 添加 三月七最可爱啦！',
            "-> 添加一条自定义语句",
            "",
            "/三月七 删除 开拓者",
            "-> 删除所有包含\"开拓者\"的自定义语句",
            "",
            "/三月七 列表 2",
            "-> 查看第2页自定义语句",
            "",
            "注意事项:",
            "------------------------------",
            "- 默认语句无法删除，只能删除自定义语句",
            "- 自定义语句保存在插件目录的 custom_quotes.json 中",
            "- 添加语句时内容必填",
            "- 防刷屏配置可在 AstrBot 控制台修改",
        ]
        help_text = "\n".join(help_lines)
        yield event.plain_result(help_text)

    async def terminate(self):
        '''插件卸载时保存数据'''
        self._save_custom_quotes()
        logger.info("三月七语句插件已卸载，数据已保存。")