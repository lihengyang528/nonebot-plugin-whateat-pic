from nonebot.adapters.onebot.v11 import (
    MessageSegment,
    MessageEvent,
    Bot,
    Message,
    GroupMessageEvent,
    GROUP_OWNER,
    GROUP_ADMIN,
)
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.exception import ActionFailed
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.matcher import Matcher
from nonebot.params import Arg, RegexGroup
from nonebot.typing import T_State
from typing import Tuple, Any
from pathlib import Path
from .check_pass import check_cd, check_max
from .menu.menu import Menu
import os
import io
import nonebot
import httpx
from httpx import AsyncClient
import random
import base64

__plugin_meta__ = PluginMetadata(
    name="今天吃喝什么呢",
    description="随机推荐吃的和喝的",
    usage="""今天吃什么:随机推荐吃的\n
    今天喝什么:随机推荐喝的\n
    查看菜单:查看所有菜单\n
    查看菜单 菜单名:查看具体菜单\n
    查看饮料:查看所有饮料\n
    查看饮料 饮料名:查看具体饮料\n
    添加菜单 菜名:添加菜单\n
    添加饮料 饮料名:添加饮料\n
    删除菜单 菜名:删除菜单\n
    删除饮料 饮料名:删除饮料""",
    type="application",
    homepage="https://github.com/Cvandia/nonebot-plugin-whateat-pic",
    supported_adapters={"~onebot.v11"},
    extra={
        "unique_name": "nonebot-plugin-whateat-pic",
        "example": """
        今天吃什么\n
        今天喝什么\n
        查看菜单\n
        查看菜单 菜名\n
        查看饮料\n
        查看饮料 饮料名\n
        添加菜单 菜名\n
        添加饮料 饮料名\n
        删除菜单 菜名\n
        删除饮料 饮料名""",
        "author": "divandia <106718176+Cvandia@users.noreply.github.com>",
        "version": "1.1.5",
    },
)



what_eat = on_regex(
    r"^(/)?[今|明|后]?[天|日]?(早|中|晚)?(上|午|餐|饭|夜宵|宵夜)吃(什么|啥|点啥)$",
    priority=20,
)
what_drink = on_regex(
    r"^(/)?[今|明|后]?[天|日]?(早|中|晚)?(上|午|餐|饭|夜宵|宵夜)喝(什么|啥|点啥)$",
    priority=20,
)
view_all_dishes = on_regex(r"^(/)?查[看|寻]?全部(菜[单|品]|饮[料|品])$", priority=5)
view_dish = on_regex(r"^(/)?查[看|寻]?(菜[单|品]|饮[料|品])[\s]?(.*)?", priority=5)
add_dish = on_regex(
    r"^(/)?添[加]?(菜[品|单]|饮[品|料])[\s]?(.*)?",
    priority=20,
    permission=SUPERUSER | GROUP_OWNER | GROUP_ADMIN,
)
del_dish = on_regex(
    r"^(/)?删[除]?(菜[品|单]|饮[品|料])[\s]?(.*)?",
    priority=20,
    permission=SUPERUSER | GROUP_OWNER | GROUP_ADMIN,
)

# 今天吃什么路径
img_eat_path = Path(os.path.join(os.path.dirname(__file__), "eat_pic"))
all_file_eat_name = os.listdir(str(img_eat_path))

# 今天喝什么路径
img_drink_path = Path(os.path.join(os.path.dirname(__file__), "drink_pic"))
all_file_drink_name = os.listdir(str(img_drink_path))

# 载入bot名字
NICKNAME = list(nonebot.get_driver().config.nickname)
Bot_NICKNAME = NICKNAME[0] if NICKNAME else "脑积水"


@del_dish.handle()
async def _(state: T_State, matcher: Matcher, args: Tuple[Any, ...] = RegexGroup()):
    state["type"] = args[1]
    if args[2]:
        matcher.set_arg("name", args[2])


@del_dish.got("name", prompt="请告诉我你要删除哪个菜品或饮料,发送“取消”可取消操作")
async def del_(state: T_State, name: Message = Arg()):
    if str(name) == "取消":
        await del_dish.finish("已取消")
    if state["type"] in ["菜单", "菜品"]:
        # 删除all_file_eat_name中的文件名
        all_file_eat_name.remove(str(name) + ".jpg")
        img = img_eat_path / (str(name) + ".jpg")
    elif state["type"] in ["饮料", "饮品"]:
        # 删除all_file_drink_name中的文件名
        all_file_drink_name.remove(str(name) + ".jpg")
        img = img_drink_path / (str(name) + ".jpg")

    try:
        os.remove(img)
    except OSError:
        await del_dish.finish(f"不存在该{state['type']}，请检查下菜单再重试吧")
    await del_dish.send(f"已成功删除{state['type']}:{name}", at_sender=True)


@add_dish.handle()
async def got_dish_name(
    matcher: Matcher, state: T_State, args: Tuple[Any, ...] = RegexGroup()
):
    state["type"] = args[1]
    if args[2]:
        matcher.set_arg("dish_name", args[2])


@add_dish.got("dish_name", prompt="⭐请发送名字\n发送“取消”可取消添加")
async def got(state: T_State, dish_name: Message = Arg()):
    state["name"] = str(dish_name)
    if str(dish_name) == "取消":
        await add_dish.finish("已取消")


@add_dish.got("img", prompt="⭐图片也发给我吧\n发送“取消”可取消添加")
async def _(state: T_State, img: Message = Arg()):
    if str(img) == "取消":
        await add_dish.finish("已取消")
    img_url = extract_image_urls(img)
    if not img_url:
        await add_dish.finish("没有找到图片(╯▔皿▔)╯，请稍后重试", at_sender=True)

    if state["type"] in ["菜品", "菜单"]:
        path = img_eat_path
        # 添加到all_file_eat_name中
        all_file_eat_name.append(str(state["name"] + ".jpg"))
    elif state["type"] in ["饮料", "饮品"]:
        path = img_drink_path
        # 添加到all_file_drink_name中
        all_file_drink_name.append(str(state["name"] + ".jpg"))
    try:
        async with AsyncClient() as client:
            dish_img = await client.get(url=img_url[0])
            with open(path.joinpath(str(state["name"] + ".jpg")), "wb") as f:
                f.write(dish_img.content)
        await add_dish.finish(
            f"成功添加{state['type']}:{state['name']}\n"
            + MessageSegment.image(img_url[0])
        )
    except (
        OSError,
        ActionFailed,
        IndexError,
        httpx.ConnectError,
        httpx.ConnectTimeout,
    ):
        await add_dish.finish("添加失败，请稍后重试", at_sender=True)


@view_dish.handle()
async def got_name(
    matcher: Matcher, state: T_State, args: Tuple[Any, ...] = RegexGroup()
):
    # 设置下一步got的arg
    if args[1] in ["菜单", "菜品"]:
        state["type"] = "吃的"
    elif args[1] in ["饮料", "饮品"]:
        state["type"] = "喝的"

    # 设置下一步got的arg
    if args[2]:
        matcher.set_arg("name", args[2])


@view_dish.got("name", prompt=f"请告诉{Bot_NICKNAME}具体菜名或者饮品名吧")
async def _(state: T_State, name: Message = Arg()):
    if state["type"] == "吃的":
        img = img_eat_path / (str(name) + ".jpg")
    elif state["type"] == "喝的":
        img = img_drink_path / (str(name) + ".jpg")

    try:
        await view_dish.send(MessageSegment.image(img))
    except ActionFailed:
        await view_dish.finish("没有找到你所说的，请检查一下菜单吧", at_sender=True)


@view_all_dishes.handle()
async def handle(bot: Bot, event: MessageEvent, args: Tuple[Any, ...] = RegexGroup()):
    # 设置下一步got的arg
    if args[1] in ["菜单", "菜品"]:
        menu_type = "eat"
    elif args[1] in ["饮料", "饮品"]:
        menu_type = "drink"

    try:
        menu = Menu(menu_type)
        send_msg_list = [MessageSegment.text("菜单如下：")]
        for img in menu.draw_menu():
            img_bytesio = io.BytesIO()
            img.save(img_bytesio, format="JPEG")
            send_msg_list.append(MessageSegment.image(img_bytesio))
    except OSError:
        await view_all_dishes.finish("没有找到菜单，请稍后重试", at_sender=True)

    await send_forward_msg(bot, event, Bot_NICKNAME, bot.self_id, send_msg_list)


# 初始化内置时间的last_time
time = 0
# 用户数据
user_count = {}


@what_drink.handle()
async def wtd(event: MessageEvent):
    global time, user_count
    check_result, remain_time, new_last_time = check_cd(time)
    if not check_result:
        time = new_last_time
        await what_drink.finish(f"cd冷却中,还有{remain_time}秒", at_sender=True)
    else:
        is_max, user_count = check_max(event, user_count)
        if is_max:
            await what_drink.finish(random.choice(max_msg), at_sender=True)
        time = new_last_time
        img_name = random.choice(all_file_drink_name)
        img = img_drink_path / img_name
        with open(img, "rb") as im:
            img_bytes = im.read()
        base64_str = "base64://" + base64.b64encode(img_bytes).decode()
        send_msg = MessageSegment.text(
            f"{Bot_NICKNAME}建议你喝: \n⭐{img.stem}⭐\n"
        ) + MessageSegment.image(base64_str)
        try:
            await what_drink.send("正在为你找好喝的……")
            await what_drink.send(send_msg, at_sender=True)
        except ActionFailed:
            await what_drink.finish("出错啦！没有找到好喝的~")


@what_eat.handle()
async def wte(event: MessageEvent):
    global time, user_count
    check_result, remain_time, new_last_time = check_cd(time)
    if not check_result:
        time = new_last_time
        await what_eat.finish(f"cd冷却中,还有{remain_time}秒", at_sender=True)
    else:
        is_max, user_count = check_max(event, user_count)
        if is_max:
            await what_eat.finish(random.choice(max_msg), at_sender=True)
        time = new_last_time
        img_name = random.choice(all_file_eat_name)
        img = img_eat_path / img_name
        with open(img, "rb") as im:
            img_bytes = im.read()
        base64_str = "base64://" + base64.b64encode(img_bytes).decode()
        send_msg = MessageSegment.text(
            f"{Bot_NICKNAME}建议你吃: \n⭐{img.stem}⭐\n"
        ) + MessageSegment.image(base64_str)
        try:
            await what_eat.send("正在为你找好吃的……")
            await what_eat.send(send_msg, at_sender=True)
        except ActionFailed:
            await what_eat.finish("出错啦！没有找到好吃的~")



# 上限回复消息
max_msg = (
    "你今天吃的够多了！不许再吃了(´-ωก`)",
    "吃吃吃，就知道吃，你都吃饱了！明天再来(▼皿▼#)",
    "(*｀へ´*)你猜我会不会再给你发好吃的图片",
    f"没得吃的了，{Bot_NICKNAME}的食物都被你这坏蛋吃光了！",
    "你在等我给你发好吃的？做梦哦！你都吃那么多了，不许再吃了！ヽ(≧Д≦)ノ",
)


# 调用合并转发api函数
async def send_forward_msg(
    bot: Bot,
    event: MessageEvent,
    name: str,
    uin: str,
    msgs: list,
) -> dict:
    def to_json(msg: Message):
        return {"type": "node", "data": {"name": name, "uin": uin, "content": msg}}

    messages = [to_json(msg) for msg in msgs]
    if isinstance(event, GroupMessageEvent):
        return await bot.call_api(
            "send_group_forward_msg", group_id=event.group_id, messages=messages
        )
    else:
        return await bot.call_api(
            "send_private_forward_msg", user_id=event.user_id, messages=messages
        )
