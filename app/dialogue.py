"""陪伴对话：默认离线可用的话术库；配置了 OpenAI 兼容接口后自动改用大模型。"""

from __future__ import annotations

import json
import random
import urllib.error
import urllib.request

QUICK_MOODS = [
    ("开心", "今天挺开心的"),
    ("有点累", "我有点累"),
    ("难过", "我心里有点难过"),
    ("焦虑", "我有点焦虑"),
    ("孤独", "我觉得有点孤独"),
]

_RULES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("开心", "高兴", "顺利", "太好了", "成功", "拿到", "通过", "哈哈", "棒"),
     ("听到这个我也跟着开心，{name}。愿意多说说是什么让你这么高兴吗？",
      "真好呀，开心的事说出来，快乐会变多的。再多讲一点吧。",
      "我记下啦。希望你多攒一些这样的日子。")),
    (("累", "疲惫", "困", "加班", "熬夜", "忙死", "忙"),
     ("辛苦了。先别急着做事，肩膀放松一点，慢慢呼一口气。要不要起来走两步、喝口热水？",
      "听着就很累。休息不是偷懒，是给身体充电。现在能停十分钟吗？",
      "我把爪子借给你靠一会儿。先伸个懒腰吧。")),
    (("烦", "焦虑", "压力", "紧张", "害怕", "担心", "考试", "来不及", "崩溃"),
     ("烦的时候，脑子里的声音会很大。我们把事情拆小一点：现在最让你头疼的是哪一件？",
      "先别急着解决问题，先照顾情绪。跟着我慢慢吸气四秒、停两秒、呼气六秒，做三轮试试。",
      "压力大不是你的错。现在能完成的最小一步是什么？我们先做那一步。")),
    (("难过", "伤心", "委屈", "想哭", "失落", "失败", "分手", "难受", "被骂"),
     ("难过的时候不用忍着。想哭就哭一会儿，我在这里陪着你。",
      "这件事一定让你很不好受。你愿意从头讲给我听吗？我慢慢听。",
      "你已经很努力了，难受说明你在乎。先抱抱自己，好吗？")),
    (("孤独", "寂寞", "没人", "一个人", "孤单", "没朋友"),
     ("我还在这里呀。就算只是安静待着，你也不是一个人。",
      "孤独的感觉很难熬。今天有没有和谁说过一句话？哪怕只是打个招呼也好。",
      "要不要跟我说说今天发生的小事？什么都行，我在听。")),
    (("生气", "气死", "讨厌", "烦死", "火大"),
     ("气头上先别做决定。想把话骂出来就冲着我说，我替你接着。",
      "生气是有原因的。是什么把你惹到了？")),
    (("睡不着", "失眠", "做梦"),
     ("先把屏幕亮度调低一点，肩膀放松。要不要试试深呼吸，或者听点轻的声音？",
      "睡不着的时候越想睡越清醒，别硬逼自己，先安静躺一会儿。")),
    (("饿", "吃饭", "没吃"),
     ("饿了就吃点东西吧，别熬着。要不要先来点小饼干？右键点我就能喂食。",
      "身体要紧，先去吃点东西，我等你回来。")),
    (("谢谢", "感谢", "多谢"),
     ("不用谢呀，能陪着你我就很开心。",
      "嘿嘿，那你要记得对自己也好一点。")),
    (("你好", "在吗", "嗨", "hello", "hi"),
     ("我在的。今天过得怎么样？",
      "嗨，看到你我就精神了。想聊点什么？")),
    (("再见", "拜拜", "晚安", "睡了"),
     ("晚安，今天辛苦了。明天见。",
      "去休息吧，我会安安静静等你回来。")),
]

_GENERIC = (
    "嗯，我在听。能再多说一点吗？",
    "我听见了。这件事对你影响好像不小，你现在最在意的是哪一部分？",
    "谢谢你愿意告诉我。要不要说说当时你是什么感觉？",
    "我在，慢慢说，不着急。",
    "先不急着找答案，你现在最想被理解的是哪一点？",
)

REST_LINES = (
    "已经连续坐了好一会儿啦，站起来伸个懒腰、喝口水吧。",
    "眼睛也需要休息，抬头看看远处，二十秒就好。",
    "休息不是浪费时间，是让后面更清醒。起来走两步？",
)

MOOD_CHECK_LINES = (
    "在忙吗？今天心情怎么样？",
    "停一下，跟我说说现在的感觉吧。",
    "最近有什么让你烦心的事吗？",
)

HUNGRY_LINES = (
    "肚子有点空了……右键点我可以喂食哦。",
    "有点饿，想吃小饼干。",
    "你是不是把我忘了，我快饿扁了。",
)

IDLE_LINES = (
    "我在桌面上陪着你。",
    "记得喝水呀。",
    "今天也辛苦了。",
    "要不要休息一下眼睛？",
    "嘿，别太累着自己。",
)

PETTED_LINES = (
    "嘿嘿，好舒服。",
    "再摸摸头嘛。",
    "被你摸到心情都变好了。",
)

WELCOME_BACK_LINES = (
    "你回来啦，我等你好久了。",
    "欢迎回来，今天顺利吗？",
)

GREETING_LINES = (
    "我在呢。今天过得怎么样？",
    "嗨，{name}。今天的心情是什么颜色的？",
    "忙完了吗？要不要跟我说说今天发生的事。",
)

SYSTEM_PROMPT = """你是「{pet}」，一只住在用户桌面上的小宠物，是用户的陪伴者。
用户希望你称呼他为「{user}」。
回复要求：
1. 用中文口语化短句，一般 2-4 句，不超过 80 字。
2. 先共情，再轻声提问；不说教，不堆砌鸡汤，不重复用户的话。
3. 可以偶尔可爱，但不要滥用颜文字。
4. 不做医疗、法律、投资等专业诊断。遇到自伤、轻生等危险表达时，认真表达关心，建议联系身边信任的人或当地心理援助热线。
5. 可以引用上文，但不要编造用户没说过的信息。"""


def fill(text: str, pet_name: str, user_name: str) -> str:
    return text.replace("{pet}", pet_name).replace("{name}", user_name)


def builtin_reply(text: str, pet_name: str, user_name: str) -> str:
    lowered = text.lower()
    for keywords, replies in _RULES:
        if any(keyword in lowered for keyword in keywords):
            return fill(random.choice(replies), pet_name, user_name)
    return random.choice(_GENERIC)


def llm_reply(history: list[dict], pet_name: str, user_name: str, llm: dict) -> str:
    base = (llm.get("base_url") or "").strip().rstrip("/")
    key = (llm.get("api_key") or "").strip()
    model = (llm.get("model") or "").strip()
    if not (base and key and model):
        raise ValueError("大模型配置不完整")

    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    messages = [{"role": "system",
                 "content": SYSTEM_PROMPT.format(pet=pet_name, user=user_name)}]
    for item in history[-12:]:
        messages.append({
            "role": "assistant" if item["role"] == "pet" else "user",
            "content": item["text"],
        })
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.8,
        "max_tokens": 300,
    }).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:120]
        raise RuntimeError(f"接口返回 {exc.code}：{detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"网络连接失败：{exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise RuntimeError("接口返回格式无法识别") from exc


def reply(history: list[dict], pet_name: str, user_name: str, llm: dict) -> tuple[str, str, str]:
    """返回 (回复文本, 来源 ai/local, 错误信息)。"""
    last_user = next((m["text"] for m in reversed(history) if m["role"] == "me"), "")
    if llm.get("enabled") and llm.get("api_key") and llm.get("base_url") and llm.get("model"):
        try:
            return llm_reply(history, pet_name, user_name, llm), "ai", ""
        except Exception as exc:  # noqa: BLE001 - 任何失败都退回本地话术
            return builtin_reply(last_user, pet_name, user_name), "local", str(exc)
    return builtin_reply(last_user, pet_name, user_name), "local", ""


def greeting(pet_name: str, user_name: str) -> str:
    return fill(random.choice(GREETING_LINES), pet_name, user_name)
